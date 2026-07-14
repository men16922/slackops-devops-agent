# DASHBOARD_GUIDE — 웹 대시보드 가이드

> **한 문서, 두 독자.** ① **대시보드를 보고 누르는 사람** → §1~§6(로컬, 실 AWS 불필요).
> ② **대시보드를 Vercel 에 배포하는 운영자** → §7. 에이전트 백엔드는 [SLACK_GUIDE.md](SLACK_GUIDE.md),
> 미결 검증은 [QA_TEST.md](QA_TEST.md), 인프라 실행은 `docs/runbooks/deploy-checklist.md`.

이중 컨트롤 플레인: Slack(Socket Mode) + 웹 대시보드(Next.js)가 **단일 job 큐(DynamoDB 단일테이블)** 를 공유.

---

## 1. 빠른 시작 (실 AWS 불필요)
```sh
cd web
docker compose up --build
```
- 브라우저: **http://localhost:8930**
- 구성: `dynamodb-local`(오프라인) → `seed`(mock Job/Audit/Metric) → `web`. **자격증명 불필요**(더미 키).
- 포트 8930 충돌 시 `web/docker-compose.yml` 의 `web.ports` 한 줄만 교체(예: `"9930:3000"`).

> **한 방 실행(실 Claude 포함):** `export CLAUDE_CODE_OAUTH_TOKEN="$(claude setup-token)"` 후 `make demo`
> — web+DynamoDB Local+`chat_agent`+`worker` 동시 기동, Ctrl-C 정리.

---

## 2. 화면 읽는 법
상단 메뉴 2개 — **Job Queue**(명령 목록·상태) / **Telemetry**(사용량 통계).

| 뱃지 | 뜻 | 할 일 |
| --- | --- | --- |
| 🟡 `awaiting_approval` | 사람 승인 대기 | **클릭해서 확인** |
| 🔵 `running` | 실행 중 | 기다리기 |
| 🟢 `done` | 완료 | — |
| 🔴 `failed` | 실패 | 상세에서 원인 확인 |

- 파란 **명령어 글씨**(`pr`/`diagnose`/`logs`) 클릭 → 상세 화면.
- 🤖 **agent 뱃지 + rationale** = 에이전트가 자율 제안한 작업(왜 제안했는지 근거 표시).

---

## 3. 작업 상세 + 승인 데모 ⭐ (안전장치 핵심)
작업 클릭 → 기본 정보(명령/요청자/비용/토큰) + 맨 아래 **Audit Timeline**.
🟡 승인 대기 작업이면 **📝 diff 미리보기 + ✅ Approve / ❌ Reject**.

1. 🟡 작업 클릭 → diff 읽기 → ✅ **Approve** → 상태 `approved` + 타임라인에 "누가 언제 승인".
2. 새로고침 후 **같은 작업 재승인** → **"이미 처리된 작업"** 거부 = **낙관적 락**(중복 실행 방지) 동작.

> **AI가 코드를 만들어도, 사람이 버튼을 눌러야만 실제로 진행된다** — 출력 게이트(주입 방어 3계층).

---

## 4. 대화형 producer — 에이전트와 대화해 작업 제안받기
첫 화면 상단의 **채팅**에 자연어로 입력(예: `api 5xx 늘었어, 원인 봐줘`). 입력은 Claude 에 직접
가지 않고 **DynamoDB 대화 버스**에 적재되고, 에이전트(`chat_agent`)가 폴링·sanitizer 격리 후 Claude 로
**스트리밍 응답**(~800ms 폴링으로 자라나는 답을 Markdown 렌더). 에이전트가 구체 작업이 필요하다 판단하면
**propose_job** 으로 Job Queue 에 제안 → "🤖 작업이 제안되었습니다" 콜아웃 → 아래 큐에서 **승인/거절**.

> 🔒 자유 텍스트지만 Claude 에 **직접 전달하지 않는다** — 대화 버스 경유 + sanitizer 격리 +
> 에이전트는 `propose_job`(read-only)만 호출 가능. DynamoDB **폴링(outbound)만** 하므로
> 인바운드 포트 0 / Socket Mode 불변 유지 → **Vercel 배포본에서도 동작**.

---

## 5. 전체 실행 루프 — 대화/제안 → 승인 → 실제 실행
실 Claude 로 돌리려면(`CLAUDE_CODE_OAUTH_TOKEN` 필요):
```sh
export CLAUDE_CODE_OAUTH_TOKEN="$(claude setup-token)"
make chat-agent ARGS=--once     # 채팅: 대기 대화 1건 처리(스트리밍 응답 + 필요시 propose_job)
make agent-monitor              # (대안) 신호 감지 → 자율 제안(pending)
# 웹 8930 에서 제안 Approve
make worker ARGS=--once          # 승인분 실제 실행 → done + audit/metric 반영
```
- L0(diagnose)는 즉시 실행→`done`, L1(pr)은 prepare→`awaiting_approval`, 승인분은 execute→`done`.
- 운영(EC2)에선 chat-agent/worker 가 systemd 로 상주 폴링. 루프 상세는 `docs/runbooks/agent-mcp-demo.md`.

---

## 6. Telemetry + FAQ
**Telemetry** — 위쪽 카드(실행 횟수/총비용/토큰/도구 호출/성공률) + 아래 명령어별 집계·최근 실행. 비용은 보통 한 번에 몇 센트.

- **목록이 비어요** — 시드 미주입/DB 연결 끊김. 잠시 후 새로고침.
- **버튼이 거부돼요** — 이미 다른 사람이 먼저 승인/거부했거나 상태가 바뀜(정상, 낙관적 락).
- **데이터가 진짜인가요?** — 기본은 **샘플 시드**. 실 운영/배포 시 Slack·에이전트 명령이 실시간 적재.
- **끄기** — `cd web && docker compose down`. 메모리 DB라 끄면 사라지고 다시 켜면 시드 재생성.

---

## 7. Vercel 배포 — 실 DynamoDB 읽기 (운영자, 제출용)
로컬 오프라인 모드(§1)엔 **불필요**. 아래는 **Vercel 배포 대시보드**가 실 DynamoDB 를 읽기 위한 절차.
구조: 브라우저 → Vercel(Next.js 서버) → **AWS SDK + 읽기전용 키** → DynamoDB.
(EC2 아님 → Instance Profile 불가라 **여기서만** Access Key 사용 = 읽기전용·테이블 스코프.)

### 7-1. 읽기전용 IAM 사용자 키
IAM → Users → Create user(콘솔 OFF, 프로그래매틱 전용) → 인라인 정책:
```json
{ "Version": "2012-10-17", "Statement": [{
  "Sid": "DashboardRead", "Effect": "Allow",
  "Action": ["dynamodb:GetItem", "dynamodb:Query"],
  "Resource": ["arn:aws:dynamodb:*:*:table/slackops-agent",
               "arn:aws:dynamodb:*:*:table/slackops-agent/index/*"] }]}
```
- 승인(쓰기)까지 허용하려면 `Action` 에 `dynamodb:UpdateItem`, `dynamodb:PutItem` 추가.
- Security credentials → **Create access key**("Application outside AWS") → `AKIA…`/secret 확보(secret 은 이때만 — 안전 보관, git 금지).

### 7-2. Vercel 프로젝트 + 환경변수
- New Project → repo 연결 → **Root Directory = `web`**.
- Settings → Environment Variables:
  | Key | Value |
  | --- | --- |
  | `DDB_TABLE` | `slackops-agent` |
  | `AWS_REGION` | `us-east-1` (테이블 생성 리전과 일치) |
  | `AWS_ACCESS_KEY_ID` | `AKIA...` |
  | `AWS_SECRET_ACCESS_KEY` | `...` |
  | `AUTH_GITHUB_ID` | GitHub OAuth Client ID |
  | `AUTH_GITHUB_SECRET` | GitHub OAuth Client secret |
  | `AUTH_SECRET` | `openssl rand -base64 32` 출력 |
  | `GITHUB_ALLOWED_USERS` | 허용 GitHub login을 쉼표로 구분 |
- ⚠️ **`DDB_ENDPOINT` 는 설정하지 않는다** — 미설정 시 실 DynamoDB 로 연결(설정 시 로컬 모드).
- GitHub OAuth App callback URL은 `https://<Vercel domain>/api/auth/callback/github`로 설정한다. allowlist가 비어 있으면 fail-closed로 모든 로그인이 거부된다.
- Deploy → **배포 URL + Team ID 기록**(제출물).

> **로컬에서 실 DynamoDB 확인:** `web/.env.local.example` → `web/.env.local` 복사 후 모드 B 블록 채움(`DDB_ENDPOINT` 줄 삭제/주석). `.env.local` 은 커밋되지 않는다.

### 7-3. 키 회전/폐기
심사 종료 후 또는 노출 의심 시 IAM → 키 **Deactivate → Delete** → 새 키 교체.
