"""EventBridge 타깃 — CloudWatch "Alarm State Change"(→ALARM) → 큐에 제안 적재.

이벤트 구동 producer. 상주 monitor 의 타이머 폴링/`cloud-alarm.sh` 의 수동 다리를
대체한다: alarm 이 ALARM 으로 바뀌면 EventBridge 가 이 Lambda 를 호출 → 실시간 제안.

보안/불변:
  - alarm StateReason 은 **untrusted** — 그대로 명령으로 쓰지 않는다. `detect()`(결정적
    regex)만 신호→(command,args,rationale) 매핑하므로 명령 주입 불가(명령은 코드의
    마커 매칭에서만 나온다).
  - Lambda 는 **제안(PENDING/source=agent)만** 적재 — 직접 실행하지 않는다. 실행/승인은
    기존 worker + 출력 게이트(L0 자동 / L1 사람 승인).
  - 같은 단일테이블(`slackops-agent`)에 적재 → 대시보드/Slack 에 라이브 노출.

핸들러: `app.alarm_lambda.handler`. 의존성은 import-safe(boto3 만 lazy, Lambda 런타임 제공).
"""

from __future__ import annotations

from typing import Any, Callable

from app.agent_monitor import detect
from app.mcp_server import propose_job_impl, store_from_env

ALARM_STATE = "ALARM"

# ── ① "문제 인지" 알림 (적재 즉시 — worker 실행/notifier 폴링 race 무관) ──────────
# notifier(EC2)는 PENDING→DONE 이 빠른 L0 제안에선 PENDING(=제안) 알림을 놓친다. producer 인
# 이 Lambda 가 적재 직후 직접 Slack 에 알려 "① 문제 감지 → ② 완료"의 첫 단계를 보장한다.
SLACK_POST_URL = "https://slack.com/api/chat.postMessage"
NOTIFY_TOKEN_PARAM = "/slackops/SLACK_BOT_TOKEN"  # SecureString
NOTIFY_CHANNEL_PARAM = "/slackops/SLACK_NOTIFY_CHANNEL"


def _post_slack(text: str) -> None:
    """SSM 토큰/채널로 chat.postMessage. boto3/SSM 은 lazy — Lambda 런타임 제공.

    토큰은 SecureString(WithDecryption), 채널은 평문 파라미터. 호출자가 예외를 swallow 한다.
    """
    import urllib.parse
    import urllib.request

    import boto3  # lazy: 테스트/미설치 환경 import-safe

    ssm = boto3.client("ssm")
    token = ssm.get_parameter(Name=NOTIFY_TOKEN_PARAM, WithDecryption=True)["Parameter"]["Value"]
    # 채널은 평문이지만 WithDecryption=True 는 평문에도 무해 → SecureString 으로 저장돼도 안전.
    channel = ssm.get_parameter(Name=NOTIFY_CHANNEL_PARAM, WithDecryption=True)["Parameter"]["Value"]
    data = urllib.parse.urlencode({"channel": channel, "text": text}).encode()
    req = urllib.request.Request(
        SLACK_POST_URL, data=data, headers={"Authorization": f"Bearer {token}"}
    )
    urllib.request.urlopen(req, timeout=5)  # noqa: S310 — 고정 https Slack endpoint


def format_detected(command: str, args: str, rationale: str) -> str:
    """① "문제 감지/triage 시작" Slack 텍스트 — notifier 의 done(②) 포맷과 짝.

    Slack 게시이므로 이모지는 `:shortcode:`(Slack 렌더). rationale 이 '왜 감지했는지'를 보여준다.
    """
    cmd = f"`{command}`" + (f" `{args}`" if args else "")
    why = f"\n> {rationale}" if rationale else ""
    return f":mag: *Detected — triaging* {cmd}{why}"


def notify_detected(
    command: str, args: str, rationale: str, *, post: Callable[[str], None] | None = None
) -> bool:
    """제안 적재 직후 ① 알림. 게시 성공 시 True. 실패는 swallow(제안은 이미 적재됨)."""
    sender = post or _post_slack
    try:
        sender(format_detected(command, args, rationale))
        return True
    except Exception:  # noqa: BLE001 — 알림 실패가 producer/제안을 막지 않는다.
        return False


def _detail(event: dict[str, Any]) -> dict[str, Any]:
    detail = event.get("detail")
    return detail if isinstance(detail, dict) else {}


def _state(event: dict[str, Any]) -> dict[str, Any]:
    state = _detail(event).get("state")
    return state if isinstance(state, dict) else {}


def is_alarm_event(event: dict[str, Any]) -> bool:
    """detail.state.value == ALARM 일 때만 처리(OK/INSUFFICIENT_DATA 전이는 무시)."""
    return _state(event).get("value") == ALARM_STATE


def build_signal(event: dict[str, Any]) -> str:
    """이벤트에서 detect() 가 스캔할 신호 텍스트 구성(alarmName + StateReason).

    alarmName 은 서비스/증상 힌트("...checkout-5xx")를, StateReason 은 강제 데모 시
    `service=...`·`5xx`·`504` 마커를 담는다. 둘 다 넣어 데모/실운영 매칭률을 높인다.
    reason 은 untrusted 지만 detect 는 결정적이라 안전.
    """
    detail = _detail(event)
    name = str(detail.get("alarmName", "")).strip()
    reason = str(_state(event).get("reason", "")).strip()
    return f"CloudWatch alarm {name} in ALARM — {reason}"


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """EventBridge 진입점 — ALARM 이벤트면 detect→propose, 아니면 무시.

    Returns:
        {"ok", "proposed", ...} — propose_job_impl 결과(중복=deduped, 거부=ok False) 포함.
    """
    del context  # 미사용(서명 통일)
    if not is_alarm_event(event):
        return {"ok": True, "proposed": False, "ignored": "state != ALARM"}
    decision = detect(build_signal(event))
    if decision is None:
        return {"ok": True, "proposed": False, "reason": "no detection rule matched"}
    command, args, rationale = decision
    result = propose_job_impl(store_from_env(), command, args, rationale)
    # 새 제안만 ① 알림(중복=deduped 는 무해 no-op 이라 재알림 안 함).
    if result.get("ok") and not result.get("deduped"):
        notify_detected(command, args, rationale)
    return {"ok": True, "proposed": bool(result.get("ok")), "result": result}
