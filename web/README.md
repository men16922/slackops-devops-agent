# web/ — SlackOps 대시보드 (Next.js)

단일테이블 DynamoDB(`slackops-agent`)의 Job/Audit/Telemetry 를 보여주고, 승인 대기 작업을
approve/reject 하는 대시보드. v0/Vercel 타깃.

## 로컬 실행 (오프라인, 실 AWS 불필요)
```sh
docker compose up --build
# → http://localhost:8930
```
- `dynamodb-local`(오프라인) + `seed`(mock 데이터 주입) + `web` 으로 구성.
- 포트 충돌 시 `docker-compose.yml` 의 `web.ports` 만 변경(`"8930:3000"`).

## 페이지
- `/` — Job 큐 피드(상태/명령/비용)
- `/jobs/[id]` — 상세 + diff 출력게이트 + Approve/Reject + audit 타임라인
- `/metrics` — 텔레메트리 집계(비용/토큰/tool calls/성공률)

## 데이터 소스 전환
- `DDB_ENDPOINT` 설정 → DynamoDB Local(로컬).
- `DDB_ENDPOINT` 미설정 → 실 DynamoDB(Vercel/EC2). 자격증명·배포는 루트 **USER_GUIDE.md** 참조.

스키마/전이 계약의 단일 진실원은 `src/app/store/`(Python). 이 앱은 그 계약을 미러링만 한다.
