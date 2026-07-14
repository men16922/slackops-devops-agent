# web/ — SlackOps 대시보드 (Next.js)

단일테이블 DynamoDB(`slackops-agent`)의 Job/Audit/Telemetry 를 보여주고, 승인 대기 작업을
approve/reject 하는 대시보드. GitHub OAuth와 GitHub login allowlist로 보호된다.

## 로컬 실행 (오프라인, 실 AWS 불필요)
```sh
docker compose up --build
# → http://localhost:8930
```
- `dynamodb-local`(오프라인) + `seed`(mock 데이터 주입) + `web` 으로 구성.
- 포트 충돌 시 `docker-compose.yml` 의 `web.ports` 만 변경(`"8930:3000"`).
- Compose는 local DynamoDB일 때만 명시적 개발용 인증 우회를 켠다. Vercel에서는
  `AUTH_GITHUB_ID`, `AUTH_GITHUB_SECRET`, `AUTH_SECRET`, `GITHUB_ALLOWED_USERS`가 필수다.

## 페이지
- `/` — Job 큐 피드(상태/명령/비용)
- `/jobs/[id]` — 상세 + diff 출력게이트 + Approve/Reject + audit 타임라인
- `/metrics` — 텔레메트리 집계(비용/토큰/tool calls/성공률)

## 데이터 소스 전환
- `DDB_ENDPOINT` 설정 → DynamoDB Local(로컬).
- `DDB_ENDPOINT` 미설정 → 실 DynamoDB(Vercel/EC2). 자격증명·배포는 루트 **DASHBOARD_GUIDE.md** 참조.

스키마/전이 계약의 단일 진실원은 `src/app/store/`(Python). 이 앱은 그 계약을 미러링만 한다.
`/jobs/[id]`의 승인에는 실행 계획 hash가 함께 기록되며, worker는 실행 직전과 PR 생성 후 이를 재검증한다.
