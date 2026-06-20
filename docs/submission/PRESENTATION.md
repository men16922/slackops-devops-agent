# PRESENTATION — SlackOps DevOps Agent (H0)

> 발표/제출용 슬라이드 **초안** (방향 판단용). 슬라이드 노출 = **English**(제출 언어), `🗣️ 노트` = 한글 발표/근거.
> 분량 12 슬라이드 / 3분 데모 영상과 짝(데모 스크립트는 `docs/guide/kr/DEMO_SCRIPT.md` 예정). 4축 매핑은 슬라이드 10.

---

## Slide 1 — Title
**SlackOps DevOps Agent**
*Turn Claude Code Headless into a safe, Slack-controlled operations engineer.*
`Security-first · Human-in-the-loop · Fully instrumented`

> 🗣️ 한 줄 후크: "AI가 운영을 *제안*하고, 사람이 *경계*를 쥔다." 로고/팀명/H0 표기.

---

## Slide 2 — Problem
- Small-team oncall = **console round-trips + manual diagnosis toil**.
- Letting an AI *act* on infra is scary: prod changes, leaked creds, prompt injection.
- "Give the bot access" and "stay safe" usually conflict.

> 🗣️ 청중 공감 포인트. 콘솔 왔다갔다, 한밤 알림, 그런데 AI한테 권한 주긴 무섭다 — 이 긴장이 핵심.

---

## Slide 3 — Who it's for
- **Small-team DevOps / platform engineers / oncall.**
- Need fast triage from where they already are (Slack), without standing up a heavy platform or handing an agent the keys.

> 🗣️ 구체 대상 = Impact 축. "누구의 어떤 실문제"를 또렷이.

---

## Slide 4 — Solution
**Slack natural-language command → Claude Code Headless on EC2 → analyzes AWS/K8s/Terraform/GitHub → ops automation.**
`/devops ping · logs · diagnose · tf-review · pr`
MVP scope = **Read-only analysis + PR creation** (no prod changes).

> 🗣️ "단순 챗봇이 아니다" 선언. MVP 범위를 정직하게 못박아 신뢰 확보.

---

## Slide 5 — ⭐ The safe-autonomy loop (the core idea)
```
existing alert (CloudWatch alarm / SLO burn / failed deploy)
   → agent triages → 🔔 Slack ping + dashboard bell
   → human reads rationale → ✅ diff approval gate → worker executes → 📊 telemetry
```
- We **don't** invent a new monitoring system — we sit **on top of alerts you already have**.
- The agent **triages & proposes**; the human **holds the approval boundary**.
- Autonomy made **visible** (notifications) and **safe** (approval gate).

> 🗣️ **데모의 척추이자 Originality 축.** 핵심 재프레이밍: "우리는 감지기가 아니라 *alert→안전한 조치* 사이의 빈칸을 채운다." 신호 소스 상세 = Appendix A. 이 한 장이 클라이맥스.

---

## Slide 6 — Architecture
```
Slack (Socket Mode, no inbound port)        Web Dashboard (Next.js / Vercel)
            \                                   /
             ▼                                 ▼
        ┌─────────── DynamoDB single-table (one shared job queue) ───────────┐
        │  conditional-write: atomic claim + optimistic-lock approval gate    │
        └─────────────────────────────────────────────────────────────────────┘
             ▲                                 ▲
   EC2 agent (IAM Instance Profile) ── worker · chat-agent · monitor (systemd)
   Claude Code Headless + AWS API MCP (read-only) · OTel → ADOT
```
- **Dual control plane** (Slack + web) over **one** queue.

> 🗣️ Design 축 = 풀스택 정합. 두 컨트롤 플레인이 단일 테이블을 공유 — 알림(Slack/벨)도 같은 큐를 읽는다. "one source, two surfaces."

---

## Slide 7 — Why DynamoDB (DB justification)
> *"Slack and Vercel share one job queue — a **DynamoDB conditional write** gives atomic job claim + duplicate-approval lock **without a separate coordinator**."*
- GSI2 = FEED / AUDIT / METRIC feeds. TS `web/lib/ddb` mirrors Python `store/` contract.
- **AWS Database used: DynamoDB.**

> 🗣️ Technical Implementation 축 = "DB가 의도적·실엔지니어링인가". 이 문장을 영상·DevPost에 그대로. Aurora 아닌 이유까지 한 호흡에.

---

## Slide 8 — Security model (differentiator #1)
- **Socket Mode** → no inbound port, no public endpoint.
- **IAM Instance Profile only** → zero stored Access Keys on EC2.
- **Permission L0/L1 only**; L2(Execute)/prod/IAM/DB changes = **hard-forbidden invariant**.
- **Prompt-injection defense, 4 layers**: Sanitizer(`<untrusted_data>`) · Tool Allowlist · Output gate(diff→human) · Template prompt.

> 🗣️ "안전하게 운영하는 법의 레퍼런스" 주장의 근거. 4계층을 한 줄씩, 출력 게이트는 데모와 연결.

---

## Slide 9 — Observability (differentiator #2)
- Every run instrumented: **latency / tokens / cost(USD) / tool-calls** via OTel → ADOT.
- Dashboard Telemetry surfaces per-command cost — *usually a few cents per run*.

> 🗣️ "투명성". 실측 수치(N초/$0.0X/M calls)는 배포 후 캡처해 채운다(현재 placeholder).

---

## Slide 10 — Judging axes mapping
| Axis | Our evidence |
| --- | --- |
| **Technical Impl.** | DynamoDB single-table + conditional-write claim/lock; no coordinator. |
| **Design** | TS `lib/ddb` mirrors Python `store/`; notifications read the same queue. |
| **Impact** | Oncall gets *pinged*, not polling; Socket Mode + least-privilege + approval gate = shippable. |
| **Originality** | Autonomous detect→notify→**human-approval** loop. Proposes & alerts, human holds boundary. |

> 🗣️ 심사 루브릭에 1:1로 대응. 슬라이드 5·7이 각각 Originality·Technical의 앵커.

---

## Slide 11 — Demo (≤3 min, single take)
**The trigger is real, and we say so on screen.** Recommended: cloud, force a real CloudWatch alarm.
1. **(0:00) Problem/target** — oncall toil, "AI proposes, human gates."
2. **(0:20) Trigger** — `aws cloudwatch set-alarm-state --alarm-name checkout-5xx --state-value ALARM`
   → caption: *"In prod this fires on a threshold; here we force the transition to show the pipeline."*
3. **(0:40) Triage + notify** — EventBridge → resident `agent_monitor` → `propose_job(diagnose)`
   → **Slack channel ping + dashboard bell** light up (the wow).
4. **(1:10) Human gate** — open proposal → read rationale + (for `pr`) **diff** → ✅ Approve.
   Show the **optimistic lock**: a second approve → "already handled".
5. **(1:50) Execute** — `worker` runs Claude + **AWS API MCP (read-only)** against real CloudWatch
   → DONE. Show a write attempt → **"denied by security policy"**.
6. **(2:20) Telemetry + audit** — per-run cost/tokens + Audit timeline (who/when approved).
7. **(2:40) Close** — overlay: Socket Mode (no inbound) · IAM profile (no keys) · injection isolation · L0/L1.

> 🗣️ 연출이 아니라 *파이프라인 증명*. `set-alarm-state`로 실 alarm 전이를 투명하게 강제 → "임계치 대신 손으로 당겼다"고 자막. 로컬 fallback(=`--signals-file`)은 Appendix C. README 낭독 금지, 연속 take. 샷 상세 = DEMO_SCRIPT.md(예정).

---

## Slide 12 — Honest limits & roadmap
- **Detection is bring-your-own-signal.** We are the triage/response layer, not a monitor. The demo
  **forces** an alarm (`set-alarm-state`) or feeds a captured signal — in prod you wire your real
  CloudWatch alarms / Datadog / PagerDuty into the signal bus. We don't claim to *find* novel failures.
- Resident monitor without a live feed = heartbeat, not an observer; roadmap = EventBridge alarm feed + Tier2 `--real`.
- DynamoDB Local = in-memory (demo); prod = real table. SQLite = MVP/test only.
- L2(Execute) intentionally disabled (hard invariant). Roadmap: live alarm feed, persistent notification dedupe, ADOT live numbers.

> 🗣️ 정직성 = 신뢰. "감지를 잘한다"가 아니라 "기존 alert를 안전한 조치로 바꾼다"로 한계를 *재정의*해 오히려 출시성을 강화. (QA_TEST §3 동기화)

---

### Closing line
> *"AI proposes the operation and rings the bell. A human reads the diff and holds the boundary. That's how you run an agent in production — safely."*

> 🗣️ 보너스(+0.6): 6/29 전 아티클 + #H0Hackathon. 마지막 한 문장으로 안전-자율 메시지 봉인.

---

# Appendix A — "뭘 자동 감지하나?" (신호 소스 문제 정면돌파)

**문제(정직하게):** 갓 배포된 건강한 EC2엔 장애가 없다. `_DEMO_SIGNALS`를 하드코딩하면 "감지" 데모가 *연출*처럼 보인다 — 심사 신뢰도의 최대 리스크.

**재프레이밍(엔터프라이즈 정답):** 우리는 **새 모니터링 시스템이 아니다.** 이미 사람을 깨우는 *기존 alert* 위에 얹히는 **triage·안전조치 레이어**다.
- 기존 인프라엔 이미 신호가 있다: CloudWatch Alarm, SLO/error-budget burn, OOMKilled/CrashLoop, **실패한 배포**, terraform drift, 비용 이상.
- 가치 = "새벽에 사람이 페이지 받음" → "에이전트가 이미 triage 해서 *사람이 승인만 하면 되는* 조치를 큐에 올려둠".
- `agent_monitor`는 **신호 소스 무관**(텍스트를 읽음) → 어떤 알림 스택이든 앞단에 붙는다.

**아키텍처(엔터프라이즈):**
```
CloudWatch Alarm ─┐
Datadog/PagerDuty ─┼─► (webhook/EventBridge) ─► signal bus ─► agent_monitor ─► propose_job ─► 사람 승인
Prometheus Alert  ─┘
```

**그래서 "감지 대상" = 당신을 이미 깨우는 모든 것.** 우리가 *발명*하는 건 감지가 아니라 **alert→안전한 실행 사이의 빈칸**이다.

**데모에서 신뢰성 있게 보여주는 3가지 방법:**
| 방식 | 환경 | 신뢰도 | 비용/수고 |
| --- | --- | --- | --- |
| **A. 실 alarm 강제 전이** `aws cloudwatch set-alarm-state … ALARM` | 클라우드 | 높음(실 AWS, 투명) | ~0, 권장 |
| B. 실 장애 유발(에러 Lambda + 부하) → 실 임계 돌파 | 클라우드 | 최고(진짜) | 셋업 큼 |
| C. 캡처된 실 CloudWatch payload를 `--signals-file`로 | 로컬 | 중(녹화용) | ~0 |

> 권장: **A**(투명하게 "임계치 대신 손으로 당겼다" 자막) + 로컬 녹화는 **C**.

---

# Appendix B — 엔터프라이즈가 실제로 보고 싶어하는 것 (proof points)

각 항목은 이미 구현돼 있고 화면으로 증명 가능 — 바이어의 실제 우려에 1:1 대응.

| 엔터프라이즈 우려 | 우리 증명 (화면) |
| --- | --- |
| **Blast radius / 권한** | IAM Instance Profile(저장 키 0) + AWS MCP `READ_OPERATIONS_ONLY` + write 시도 → "denied by security policy" |
| **변경 관리 / 직무분리(SoD)** | diff 승인 게이트 + optimistic-lock(중복 승인 차단) = change-approval 워크플로 |
| **감사 / 컴플라이언스** | 모든 액션에 Audit timeline(누가·언제·승인) — SOC2/감사 추적 |
| **AI 위험 / 주입 공격** | 4계층 주입 방어(`<untrusted_data>` 격리 + tool allowlist + 출력 게이트 + 템플릿) |
| **네트워크 노출** | Socket Mode = 인바운드 포트 0, 공개 엔드포인트 없음 |
| **비용 거버넌스(FinOps)** | 액션당 토큰/$ 계측 + OTel → 기존 관측 스택 연동 |
| **정책 경계** | L0/L1만 활성, prod/IAM/DB/L2 = 하드 불변(policy-as-code) |
| **기존 스택 통합** | 모니터링 대체 아님 — 기존 alert 위에 얹힘(Appendix A) |

> 🗣️ 발표 시 슬라이드 8~10에 이 표의 좌측 우려를 얹어 "해커톤 토이가 아니라 *운영 가능한 패턴*"임을 강조. 데모 중 **write-denied 한 컷**이 가장 강력.

---

# Appendix C — 로컬 / 클라우드 테스트·시연 매트릭스

각 기능을 **어디서 어떻게 검증/녹화**하는지. (로컬 = 무비용·재현, 클라우드 = "진짜" 증명)

| 기능 | 로컬 테스트 | 클라우드 테스트 |
| --- | --- | --- |
| **대화형 producer**(chat) | `make demo` → 채팅 입력 → 스트리밍 응답/제안 (실 Claude, DynamoDB Local) | Vercel 대시보드 채팅 → 실 DynamoDB |
| **자율 제안**(monitor) | `make agent-monitor [--real]` 또는 `--signals-file <captured>` → 🤖 PENDING | systemd 상주 + `set-alarm-state`→EventBridge→propose |
| **Slack 알림**(신규) | `app.main` 로컬 실행(실 Slack 토큰 + `SLACK_NOTIFY_CHANNEL`) → 채널 ping. Socket Mode라 인바운드 불필요 | EC2 systemd `app.main` → 채널 ping |
| **대시보드 벨**(신규) | `make demo` → 제안 발생 시 벨 카운트↑ / "mark seen" | Vercel 빌드에 포함 → 실 DynamoDB 폴링 |
| **승인 게이트 + 락** | 대시보드 Approve → 재승인 "이미 처리됨" | 동일(실 DynamoDB) |
| **실행 + 계측** | `make worker --once` → done + 비용/토큰 (diagnose는 **git diff 폴백**) | worker → **실 CloudWatch**(AWS MCP) + write-denied 증명 |
| **read-only 경계** | (해당 없음 — 로컬은 자격증명 없음) | write op 시도 → "denied by security policy" ★ |
| **유닛 정합** | `make check`(pytest/ruff/mypy strict) + `next build` | — |

**핵심 갈림길:**
- **로컬로 충분히 보이는 것:** 채팅·제안·알림(Slack/벨)·승인·락·실행·계측 — 풀 루프 *기능*은 로컬 녹화 가능.
- **클라우드여야 "진짜"인 것:** ① 실 CloudWatch diagnose ② write-denied 보안 증명 ③ alarm→EventBridge 파이프라인 ④ IAM Instance Profile(키 0). → 이 4컷은 EC2 1회 가동해 캡처(비용 ~$1 미만, 캡처 후 stop).
- **Slack은 로컬에서도 됨**(Socket Mode는 아웃바운드) → 토큰만 있으면 `app.main` 로컬 실행으로 ping 녹화 가능.

> 🗣️ 추천 녹화 전략: **로컬 `make demo`로 루프 본편 + Slack ping** 녹화 → EC2 1회 가동해 **실 CloudWatch + write-denied** 4컷만 별도 캡처 → 편집으로 합본. 비용 최소, 신뢰도 최대.
