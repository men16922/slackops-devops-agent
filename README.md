# SlackOps DevOps Agent

> Slack 자연어 명령을 **안전하게** AWS/K8s/Terraform/GitHub 운영 작업으로 바꾸는 DevOps 에이전트.
> Claude Code Headless 를 "원격 운영 엔지니어"로 EC2 위에서 구동합니다.

Slack에서 `/devops diagnose checkout-service` 라고 치면 → EC2의 에이전트가 CloudWatch·kubectl·git diff 증거를 모아 원인을 진단하고, `/devops pr ...` 는 브랜치·수정·테스트를 거쳐 PR을 만들되 **사람 승인 게이트**를 통과해야 실제로 열립니다.

이 프로젝트의 핵심은 편의 봇이 아니라 **"에이전트를 안전하게 운영하는 레퍼런스"** 입니다.

- 🔒 **최소 권한** — IAM Instance Profile만 사용(저장된 Access Key 없음), 읽기/쓰기 경로 분리, 단기 STS 역할
- 🛡️ **프롬프트 인젝션 방어 4계층** — Sanitizer / Tool Allowlist / Output Gate / Template Prompt
- 👁️ **관측성** — OpenTelemetry 계측(토큰·비용·툴콜 스팬) + DynamoDB 감사 추적
- ✋ **휴먼 게이트** — 쓰기 작업(PR)은 diff를 Slack에 먼저 보여주고 승인받아야 실행

---

## 아키텍처

```
Slack (Socket Mode — 인바운드 포트 없음)
  ▼
EC2 DevOps Agent (c7i.large, EventBridge 스케줄로 기동 — 상시가동 아님)
  ├── FastAPI + Slack Bolt (Socket Mode 클라이언트)
  ├── Job Queue (DynamoDB single-table / SQLite=로컬)
  ├── Permission Engine (Level 0/1/2)
  ├── Context Sanitizer            ← 보안
  ├── Claude Code Headless (AWS CLI / kubectl / terraform / gh / helm / jq, MCP)
  ├── OTel SDK → ADOT Collector    ← 관측성
  └── IAM Instance Profile (저장 Access Key 없음)
```

이벤트 구동 루프: `CloudWatch ALARM → EventBridge → Lambda(detect→propose) → DynamoDB 큐 → Worker(Claude) → 사람 승인 → DONE → Slack 알림`.

웹 대시보드(Next.js, `web/`)에서 Job 피드 / 상세(diff 승인 게이트) / 메트릭을 확인합니다.

## 권한 모델

| Level | 이름 | 허용 범위 | MVP |
| --- | --- | --- | --- |
| 0 | Observe | logs / describe / get — 읽기 전용 | ✅ |
| 1 | Prepare | 브랜치·코드 수정·단위 테스트·`terraform plan`·PR 생성 | ✅ |
| 2 | Execute | apply / rollout restart | ❌ 비활성 |

**금지 불변식(하드 가드):** 프로덕션 변경, 배포(apply/deploy), IAM 변경, DB 변경.

## 프롬프트 인젝션 방어 — 4계층

1. **Context Sanitizer** — 주입된 로그/diff는 `<untrusted_data>` 태그로 격리, 위조 태그 무력화
2. **Tool Allowlist** — 명령별로 미리 정의된 툴만 허용(기본 deny)
3. **Output Gate** — Level 1 쓰기(PR)는 diff를 Slack에 먼저 게시 후 사람 확인 필요
4. **Template Prompt** — Slack 입력을 프롬프트에 직접 넣지 않고 강제 템플릿에 격리

## Slack 명령 (MVP)

| 명령 | 설명 |
| --- | --- |
| `/devops ping` | 헬스 체크 |
| `/devops logs <service>` | CloudWatch 조회 + 분석 |
| `/devops diagnose <service>` | CloudWatch + kubectl + git diff 종합 진단 |
| `/devops tf-review` | `terraform plan` 위험/비용/보안 리뷰 (apply 경로 없음) |
| `/devops pr <description>` | 브랜치 → 수정 → 테스트 → PR (사람 승인 게이트) |

---

## 리포지토리 구성

```
src/app/          # 에이전트 본체
  commands/       #   ping / logs / diagnose / tf_review / pr — 명령 핸들러
  store/          #   H0 single-table (Job/Audit/Telemetry, SQLite + DynamoDB)
  permissions.py  #   권한 엔진 (L0/1/2)
  sanitizer.py    #   인젝션 방어 (untrusted 격리 + 템플릿 프롬프트)
  allowlist.py    #   명령별 Tool Allowlist + 단일 실행 진입점
  command_guard.py#   PreToolUse argv 스키마 = 실행 경계
  claude_runner.py#   Claude Code Headless subprocess (stream-json)
  worker.py       #   claim → 실행 → output-gate → 감사/메트릭 기록
  pr_execution.py, write_credentials.py  # 승인 후 스코프드 GitHub App 토큰 쓰기 경로
  telemetry.py    #   OpenTelemetry 계측
web/              # Next.js 대시보드 (Job 피드 / diff 승인 / 메트릭)
deploy/           # IAM · EC2(user-data) · EventBridge · Lambda · ADOT · Vercel 배포 산출물
tests/            # pytest (권한/인젝션 코퍼스/스토어/워커/PR/정책 경계 등)
docs/guide/kr/    # 운영 가이드 (Slack 앱 / 대시보드 / Vercel 배포)
docs/runbooks/    # 배포 체크리스트 · 쓰기 자격증명 리허설 · 에이전트 MCP 데모
docs/article/     # 설계 회고 아티클
```

## 빠른 시작 (로컬)

```sh
# 1) 의존성 설치 (Python 3.11+)
python3 -m pip install -e '.[dev]'

# 2) 검증 게이트 (pytest + ruff + mypy strict)
make check

# 3) 로컬 풀스택 데모 (web + DynamoDB Local + chat_agent + worker)
make demo
```

Slack 앱 등록·SSM 시크릿·EC2/IAM 배포 순서는 다음 문서를 참고하세요.

- 배포 순서 — [`deploy/README.md`](deploy/README.md), 체크리스트 [`docs/runbooks/deploy-checklist.md`](docs/runbooks/deploy-checklist.md)
- Slack 앱 설정 — [`docs/guide/kr/SLACK_GUIDE.md`](docs/guide/kr/SLACK_GUIDE.md) (매니페스트: [`docs/guide/kr/slack-app-manifest.yaml`](docs/guide/kr/slack-app-manifest.yaml))
- 대시보드 — [`docs/guide/kr/DASHBOARD_GUIDE.md`](docs/guide/kr/DASHBOARD_GUIDE.md) · [`docs/guide/kr/VERCEL_DEPLOY.md`](docs/guide/kr/VERCEL_DEPLOY.md)
- 설계 회고 — [`docs/article/`](docs/article/)

## 검증

3계층 게이트(`make check`): **pytest** + **ruff** + **mypy(strict)**. 모든 모듈은 lazy-import 설계라 `fastapi`/`slack_bolt` 미설치 상태에서도 import-safe 합니다.

## 보안 원칙

- 자격증명은 **IAM Instance Profile 만** 사용 — Access Key를 저장/커밋하지 않습니다(`.env` 는 예시 전용).
- EC2는 **EventBridge 스케줄로만 기동** — 상시가동 아님.
- 인바운드 공개 엔드포인트 없음(Slack Socket Mode = 아웃바운드 WebSocket).
- Level 2(Execute), 프로덕션/배포/IAM/DB 변경은 **비활성**이 기본값입니다.

---

이 리포는 AWSKRUG 발표용 데모로 개발되었습니다. 상시 인프라 비용은 ≈ $0(EC2 종료 + 서버리스 유휴)로 유지됩니다.
