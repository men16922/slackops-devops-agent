# Vercel 배포 가이드 — 대시보드 공개 링크 (H0 제출 필수)

목표: web/ 대시보드를 **실 DynamoDB(`slackops-agent`, us-east-1)** 에 연결해 Vercel 에 배포 →
**Published Link + Team ID** 확보. (제출 항목: "Published Vercel Project Link & Team ID")

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

## 3. 환경변수 (Settings → Environment Variables)

| Key | Value | 비고 |
| --- | --- | --- |
| `DDB_TABLE` | `slackops-agent` | 테이블명 |
| `AWS_REGION` | `us-east-1` | 테이블 생성 리전과 동일 |
| `AWS_ACCESS_KEY_ID` | `AKIA…` | 1단계 출력 |
| `AWS_SECRET_ACCESS_KEY` | `…` | 1단계 출력(Secret) |
| `DASHBOARD_APPROVER` | 표시할 승인자명(예: `men16922`) | 감사 로그용 |

> ⚠️ **`DDB_ENDPOINT` 는 절대 설정하지 않는다** — 미설정 시 실 DynamoDB 연결(설정하면 로컬 모드 → 빈 대시보드).

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

- [ ] `/` jobs 피드에 실 작업 보임(diagnose api/checkout-service, done/pending)
- [ ] job 상세 → Output Gate(diff) + Approve/Reject 버튼 렌더
- [ ] (승인 키 포함 시) Approve 클릭 → 상태 전이 + audit 추가(optimistic lock)
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
