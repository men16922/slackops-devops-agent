# DEVPOST 제출 설명 (한글 가이드)

> **제출 본문은 영어**가 정본 — [../en/DEVPOST.md](../en/DEVPOST.md) 를 본인 목소리로 편집해 사용.
> 이 문서는 한글 체크포인트. 데크 = `docs/ppt/PRESENTATION.md`, 데모 = [DEMO_SCRIPT.md](DEMO_SCRIPT.md).

## 반드시 포함(심사 필수)
- **"AWS Database used: DynamoDB"** 명시.
- **DB 정당화 한 문장**(영상·설명에 그대로):
  > Slack 과 Vercel 두 control plane 이 하나의 작업 큐를 공유 → **DynamoDB conditional write** 로
  > 별도 코디네이터 없이 atomic job claim + optimistic-lock 승인 게이트.

## 강조 축 (4 심사 기준)
- **Technical** — 단일테이블 + conditional write(atomic claim·중복승인 락) + GSch2 FEED/AUDIT/METRIC + 탐지 토글까지 같은 테이블(거버넌스 컨트롤 플레인).
- **Design** — 웹 TS `lib/ddb` 가 파이썬 `store/` 계약 미러(알림 벨·Slack 알림도 같은 큐를 읽음 — one source, two surfaces).
- **Impact** — 온콜이 *폴링이 아니라 ping* 받음 + 컴플라이언스/감사 자세. 공개 포트 0 + 최소권한 + 사람 게이트 = 출시 가능.
- **Originality** — 자율 *감지→알림→사람 승인* 루프. "감지를 발명"이 아니라 *기존 신호/감사를 안전한 조치로*.

## 정직한 한계(설명에 포함 — 신뢰)
- DynamoDB Local 은 in-memory(데모). 상주 모니터는 라이브 피드 없으면 heartbeat. 실 스캔 findings 는 클라우드(EC2+IAM)에서만. L2/prod/IAM/DB 변경 비활성. (상세 [QA_TEST.md](QA_TEST.md) §3)
