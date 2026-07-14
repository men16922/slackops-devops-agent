# Vercel 배포 가이드 — GitHub 인증 대시보드

목표: web/ 대시보드를 **실 DynamoDB(`slackops-agent`, us-east-1)** 에 연결해 Vercel 에 배포 →
**GitHub OAuth로 보호된 링크 + Team ID** 확보. (제출 항목: "Published Vercel Project Link & Team ID")

> 구조: 브라우저 → Vercel(Next.js 서버) → AWS SDK + **읽기/승인 키** → DynamoDB.
> EC2 가 아니라 Vercel 이므로 Instance Profile 불가 → **여기서만** 최소권한 Access Key 사용(테이블 스코프).
> 비용: Vercel **Hobby 무료**(100GB/월, 비상업) — 카드 불필요.

---

## 1. 읽기/승인 IAM 키 발급 — `make cloud-vercel-key` (★ 본인 터미널에서 직접)

> AI 가 대신 만들지 않는다(시크릿이 로그에 남지 않게) — **직접** 실행하고 출력 키를 안전 보관.
> 기본 = 읽기 + 승인 쓰기(대시보드 Approve/Reject 라이브). 화면만 보여줄 거면 `READONLY=1`.

```sh
make cloud-vercel-key            # read + approve(write) — 테이블 스코프 키 발급
# 또는 읽기전용:
READONLY=1 make cloud-vercel-key
```

출력 표의 `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` 를 복사(Secret 은 이때만 표시).
정리(노출 의심·제출 후): `make cloud-vercel-key-clean`.

> ⚠️ Secret 은 **repo·.env 커밋 금지**. Vercel 환경변수에만 넣는다.
> (스크립트: `deploy/vercel/create-key.sh` — 사용자/정책 멱등, 테이블+GSI 스코프.)

---

## 2. Vercel 프로젝트 생성

1. https://vercel.com → 로그인 → **Add New… → Project**
2. GitHub repo `men16922/slackops-devops-agent` 연결(Import)
3. **Root Directory = `web`** 로 지정 (⚠️ 모노레포라 루트가 아니라 `web`)
4. Framework Preset = **Next.js** (자동 감지)

---

## 3. GitHub OAuth App + 환경변수 (Settings → Environment Variables)

GitHub → **Settings → Developer settings → OAuth Apps → New OAuth App**에서 앱을 만든다.

| OAuth App field | Value |
| --- | --- |
| Homepage URL | 배포할 Vercel URL (예: `https://slackops-devops-agent.vercel.app`) |
| Authorization callback URL | `https://<Vercel domain>/api/auth/callback/github` |

생성 후 Client ID와 Client secret을 Vercel에만 저장한다. `AUTH_SECRET`은 `openssl rand -base64 32`로 생성한다.

| Key | Value | 비고 |
| --- | --- | --- |
| `DDB_TABLE` | `slackops-agent` | 테이블명 |
| `AWS_REGION` | `us-east-1` | 테이블 생성 리전과 동일 |
| `AWS_ACCESS_KEY_ID` | `AKIA…` | 1단계 출력 |
| `AWS_SECRET_ACCESS_KEY` | `…` | 1단계 출력(Secret) |
| `AUTH_GITHUB_ID` | GitHub OAuth Client ID | GitHub OAuth App |
| `AUTH_GITHUB_SECRET` | GitHub OAuth Client secret | GitHub OAuth App |
| `AUTH_SECRET` | `openssl rand -base64 32` 출력 | 세션 서명 키 |
| `GITHUB_ALLOWED_USERS` | `login1,login2` | 승인된 GitHub login allowlist; 빈 값은 로그인 거부 |

### Makefile로 `.env` 동기화 후 배포

루트 `.env`에 `VERCEL_TOKEN`, `VERCEL_PROJECT_ID`, `VERCEL_ORG_ID`와 위 네 인증
변수를 설정한 뒤 다음 명령을 실행한다.

```bash
make vercel-deploy
```

이 명령은 `.env`의 네 인증 변수만 Vercel **Production** 환경에 동기화한 뒤
Vercel 프로젝트 설정의 Root Directory=`web`을 사용해 배포한다. `VERCEL_*` 값은 로컬 CLI 인증용이므로 Vercel 런타임 환경에는
올리지 않는다. Git 연동 배포도 마지막으로 이 명령이 동기화한 원격 값을 사용한다.

> ⚠️ **`DDB_ENDPOINT` 는 절대 설정하지 않는다** — 미설정 시 실 DynamoDB 연결(설정하면 로컬 모드 → 빈 대시보드).
> ⚠️ `AUTH_BYPASS_FOR_LOCAL_DEVELOPMENT`도 절대 설정하지 않는다. local DynamoDB endpoint와 함께 있을 때만 개발용 우회가 동작한다.

---

## 4. 배포 + 산출물 확보

1. **Deploy** 클릭 → 빌드 완료까지 대기
2. 배포 URL 접속 → jobs 피드/상세(Output Gate)/metrics 가 **실데이터**로 렌더되는지 확인
   (현재 DynamoDB 에 diagnose Job/Audit/Metric 적재됨 → 빈 화면이면 `DDB_ENDPOINT`/키/리전 점검)
3. **제출용 기록**:
   - **Published Link**: 배포 URL (예: `https://slackops-devops-agent.vercel.app`)
   - **Team ID**: Vercel → Settings → General → **Team ID** (또는 URL 의 team slug)

---

## 5. 검증 체크 (배포 후)

- [ ] 로그아웃 상태에서 `/` 접속 → `/login`으로 redirect
- [ ] allowlist에 없는 GitHub 계정 로그인 → 접근 거부
- [ ] allowlist의 GitHub 계정 로그인 → `/` jobs 피드에 실 작업 표시
- [ ] job 상세 → Output Gate(diff) + Approve/Reject 버튼 렌더
- [ ] (승인 키 포함 시) Approve 클릭 → GitHub login을 actor로 상태 전이 + approval hash audit 추가(optimistic lock)
- [ ] metrics 페이지에 비용/토큰 집계
- [ ] DOM 에 한글 없음(영어 UI — H0)

---

## 6. 제출 후 / 비용

- DynamoDB(온디맨드)·Vercel(Hobby) 은 **심사기간 유지**(idle ~$0, 링크 살아있어야 심사 가능).
- 키 노출 의심 시: `aws iam delete-access-key` → 재발급, 또는 사용자 삭제.
- 정리(완전): `aws iam delete-user-policy --user-name slackops-vercel-dashboard --policy-name dashboard-access` →
  `aws iam delete-access-key …` → `aws iam delete-user --user-name slackops-vercel-dashboard`.

---

## 부록 — 빈 대시보드 트러블슈팅

| 증상 | 점검 |
| --- | --- |
| 전부 빈 화면 | `DDB_ENDPOINT` 가 설정됐는지(미설정이어야 실 DynamoDB) |
| `AccessDenied` | 키 정책 Resource/Action + 리전(`us-east-1`) 일치 |
| 일부만 보임 | GSI 쿼리 권한(`…/index/*`) 포함됐는지 |
| Approve 실패 | 읽기전용 키면 정상(승인하려면 UpdateItem/PutItem 추가 재발급) |
| GitHub 로그인 뒤 접근 거부 | `GITHUB_ALLOWED_USERS`에 GitHub **login**(표시 이름 아님)이 포함됐는지 확인 |
