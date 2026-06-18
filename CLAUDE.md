# CLAUDE.md — slackops-devops-agent
최종 갱신: 2026-06-17

> 하네스 진입 규칙. 설계 근간은 harness/CORE_MANDATES.md, 현재 맥락은 harness/CONTEXT_BRIDGE.md 최우선 참조.
> 세션 시작 시 /sync, 작업 묶음 완료 시 /checkpoint, 문서 비대 시 /tidy-docs
>   — 스킬은 **overnight-harness 플러그인** 제공(리포 특화는 .claude/harness-config.json,
>     바이블↔리포 매핑은 docs/engineering/interp/INTERPRETATION.md).
> Read Path: harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md → docs/STATUS.md → docs/NEXT_PLAN.md.
> docs/ 전체 bulk-read 금지. 운영 규칙은 docs/DOCS_POLICY.md. gate = `make check`(pytest+ruff+mypy).

- 통신: 한국어. 단, 식별자/명령/경로/코드는 영어 원문 그대로.

---

## 프로젝트 개요

**One-liner:** Slack-controlled DevOps agent — Claude Code Headless 를 원격 운영 엔지니어로 전환.
최소 권한 보안 + prompt-injection 방어 + 전체 OpenTelemetry 계측이 차별화 축.

Slack 자연어 명령 → EC2 의 Claude Code Headless 가 AWS/K8s/Terraform/GitHub 컨텍스트 분석 → 운영 자동화.
MVP = **Read-Only 분석 + PR 생성**까지.

### 아키텍처
```
Slack (Socket Mode — no inbound port)
  ▼
EC2 DevOps Agent (c7i.large, EventBridge 스케줄 가동)
  ├── FastAPI + Slack Bolt (Socket Mode client)
  ├── Job Queue (SQLite — MVP 한정)
  ├── Permission Engine (Level 0/1/2)
  ├── Context Sanitizer            ← 보안
  ├── Claude Code Headless (AWS CLI/kubectl/terraform/gh/helm/jq, MCP)
  ├── OTel SDK → ADOT Collector    ← 계측
  └── IAM Instance Profile (Access Key 저장 금지)
```

### 권한 모델
| Level | 이름 | 허용 | MVP |
| --- | --- | --- | --- |
| 0 | Observe | logs/describe/get — 읽기 전용 | ✅ |
| 1 | Prepare | branch, code modify, unit test, terraform plan, PR 생성 | ✅ |
| 2 | Execute | apply, rollout restart | ❌ 비활성 |

**금지 불변:** Production 변경, 배포(apply/deploy), IAM 변경, DB 변경.

### Prompt Injection 방어 4계층
1. Context Sanitizer — 로그·diff 를 `<untrusted_data>` 태그로 격리 주입.
2. Tool Allowlist — 명령별 허용 도구 사전 정의.
3. 출력 게이트 — Level 1 쓰기(PR)는 diff Slack 선게시 후 사람 확인(branch protection).
4. Template Prompt 강제 — Slack 입력 직접 전달 금지.

### Slack 명령 (MVP)
`/devops ping` · `/devops logs <service>` · `/devops diagnose <service>` · `/devops tf-review` · `/devops pr <설명>`

---

## Development Guidelines
- 불변 엔지니어링 표준은 **harness/CORE_MANDATES.md** 참조(runtime/security/observability/cost/code·test/docs).
- 핵심: Python 3.11+, Bolt Socket Mode 전용, Claude Code Headless subprocess, IAM Instance Profile 만,
  타입 힌트 필수, `print` 금지, 멀티파일 변경 후 `python -m pytest tests/ -q` 전체 실행·보고.
- 비-목표/범위 밖은 docs/STATUS.md Open Risks 및 BOOTSTRAP.md A8 참조.

## 작업 방식 (운영 규칙 — /insights 반영)
- **Status 질문:** "상태/진행" 요청엔 git/코드 탐색 전에 **Read Path(/sync)·docs 먼저** 읽는다.
- **Overnight 회차:** 한 회차 = 상태복원(/sync) → `[auto]` **정확히 1개** → 전체 `pytest` → /checkpoint
  → 로컬 commit. **commit 전략·scope 를 과분석하지 말고 그냥 커밋**한다. 규약은 scripts/overnight/{run.sh,PROMPT.md}
  (러너: `make overnight` / 단발 `make overnight-once`).
- **Testing:** 멀티파일 변경 후 전체 `pytest` 실행 + **pass 카운트 보고**(예: "216 passed, 1 skipped").
- **Shell & 검증:** 절대경로 사용·`cd` 후 상태 의존 금지. **복합 bash(`&&`/`;` 다단계)는 단계 분리**
  (권한 거부·디버그난 회피). 커밋 전 `git status`로 기대 파일이 실제 반영됐는지 확인(write 유실/중단 방어).
- **보고 간결:** 상태 보고는 짧게/불릿(과대 출력 회피).

## Quarkify (선택적 탐색 가속)
`.quarkify/src/`는 `make quarkify`로 생성하는 코드 심볼·호출그래프 인덱스다(gitignore 생성물, 제로 의존).
- **언제 써라**: 대형 패키지에서 흔한 심볼·넓은 탐색일 때 grep 보다 먼저 —
  `find .quarkify/src/quark -type d -iname '*<symbol>*'` / `ls .quarkify/src/_mirror/by_role/<role>`.
- **언제 쓰지 마라**: 드문 리터럴·단일 후보는 grep 이 더 싸다. **본 repo 는 ~3.6K LOC 소형 — 일상 탐색은 grep 우선**,
  인덱스는 넓은 심볼 탐색에서만(measured adoption — harness/CORE_MANDATES.md §7).
- **권위는 항상 원본**: 리프는 빈 폴더(위치만, 라인 번호 없음) → 위치를 짚은 뒤 본문은 원본 파일을 읽는다.
- 없거나 stale 면 `make quarkify`(최초 `make quarkify-setup`). 신선도 점검 `make quarkify-check`(비차단, `make check` 미포함).
