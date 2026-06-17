# H0 제출 준비 계획 — slackops-devops-agent

최종 갱신: 2026-06-17
> 제출 마감 **2026-06-29** · 심사 6/30~7/24. 권위: NEXT_PLAN > 이 문서(historical plan).
> 근거: H0 Requirements(Track 2 B2B) + Devpost 채점 안내 메일(메모리 [[h0-judging-guidance]]).

---

## 1. Context — 왜 이 계획인가
로컬 코드(백엔드 + web/ 대시보드)는 완성·검증됨. 남은 일은 **AWS/Vercel 배포 + 제출 아티팩트**.
채점은 **앱 직접 테스트가 아니라 데모영상 + 제출 설명 비중이 큼** → 인프라 상시가동보다
*설명·영상·아키텍처 표현*에 투자한다. AWS 크레딧 신청은 거절 → 보유 $63.91 + 무료티어로 진행.

### 채점 4축 → 우리 대응
| 축 | 무엇을 본다 | 우리 카드 |
| --- | --- | --- |
| Technical | DB 통합이 의도적 엔지니어링인가 | **single-table + conditional write atomic claim/승인게이트**(검증됨) |
| Design | 프론트-백엔드 정합, 풀스택 | Vercel 대시보드 ↔ 같은 DynamoDB 큐 ↔ Slack, 출력게이트 UI |
| Impact | 구체 대상의 실문제 | 소규모 팀 온콜 엔지니어의 안전한 운영 자동화 |
| Originality | 스택으로 가능한 통찰 | "AI 에이전트를 프로덕션에서 안전하게 운영하는 법"(권한+주입방어+OTel) |

### DB 정당화 한 문장 (제출 설명·영상에 그대로)
> Slack과 Vercel 두 control plane이 하나의 작업 큐를 공유 → **DynamoDB conditional write** 로
> 별도 코디네이터 없이 atomic job claim + optimistic-lock 승인 게이트 구현. (Aurora 아닌 DynamoDB인 이유)

---

## 2. Workstream A — 인프라/배포 ([manual], 운영자 AWS 필요)
- [ ] **DynamoDB provision**: `bash deploy/dynamodb/create-table.sh` (리전 결정 = 이후 전부 동일).
      검증 `describe-table` → ACTIVE / PAY_PER_REQUEST / GSI1·GSI2.
- [ ] **읽기/쓰기 IAM 키 발급**(USER_GUIDE §5): Vercel 가 실 DynamoDB 접근용 최소권한 키.
- [ ] **Vercel 배포**: web/ → Root Directory `web`, env(`DDB_ENDPOINT` 미설정 + `AWS_REGION`/`DDB_TABLE`/키).
      → **Published Vercel Project Link + Team ID** 확보(제출 필수).
- [ ] **실 데이터 채우기**(빈 대시보드 방지) — 택1:
      (A) Slack App + EC2 e2e 로 실데이터 생성(정석), 또는 (B) 실 DynamoDB 데모 시드(seed `--real` 옵션 추가 필요).
- [ ] **EC2 e2e 1회**(영상·수치용): diagnose/pr 동작 + N초/$0.0X/tool call M회 캡처. 이후 **EC2 stop**.

## 3. Workstream B — 제출 아티팩트
- [ ] **텍스트 설명**: 무엇/누구/왜 + "AWS Database used: DynamoDB". AI 초안을 본인 목소리로 편집(필수).
- [ ] `[auto 가능]` **아키텍처 다이어그램**: Slack+Vercel→DynamoDB single-table→EC2 worker→Claude/도구, OTel, 권한·주입방어. (Mermaid → PNG)
- [ ] **데모영상 <3분**(YouTube): 문제→대상→앱 동작(diagnose, 대시보드 승인게이트)→DB 통합 설명. README 낭독 금지.
- [ ] **DynamoDB 스크린샷**: AWS Console → `slackops-agent` 테이블(provision 시 캡처).
- [ ] **Vercel 링크 + Team ID** (Workstream A 산출).

## 4. Workstream C — 보너스 (+0.6점, 6/29 전 발행)
- [ ] `[auto 가능]` **아티클 초안**: "DynamoDB single-table로 dual control-plane 큐 만들기" 회고.
      공개 발행(dev.to/medium/LinkedIn 등) + 해커톤 참가 목적 명시 + **#H0Hackathon**.

---

## 5. 타임라인 (제출 6/29 역산)
- **D-12~10 (6/17~19):** A) DynamoDB provision + Vercel 배포 / B) 아키텍처 다이어그램 + 설명 초안.
- **D-9~6 (6/20~23):** 실데이터(EC2 e2e 또는 실-시드) → 스크린샷·수치 / 데모영상 녹화. (6/22 Tech Session 선택 참석)
- **D-5~2 (6/24~27):** 영상 편집 + 설명 본인목소리 편집 + 아티클 발행(보너스).
- **D-1 (6/28~29):** 제출물 최종 점검 → **6/29 제출**.
- **심사기간:** EC2 stop, DynamoDB+Vercel 유지(~$0).

## 6. 제출 체크리스트 (H0 Requirements)
- [ ] Text description (+ DynamoDB 명시)
- [ ] <3분 데모영상(YouTube) — 문제/대상/이유 + 동작 footage + DB 설명
- [ ] Published Vercel Project Link & Team ID
- [ ] Architecture Diagram (백엔드 연결 표현)
- [ ] AWS Database 사용 증빙 스크린샷
- [ ] (보너스) 공개 콘텐츠 + #H0Hackathon

## 7. 비-목표 / 주의
- 프로젝트명 AI식 버즈워드 금지(현 `slackops-devops-agent` 유지 — 기능 서술형).
- 제출 설명을 AI 생성 그대로 제출 금지(편집 필수).
- 금지 불변 유지: Production 변경/배포/IAM·DB 변경/Level 2 비활성/인바운드 포트 없음.
