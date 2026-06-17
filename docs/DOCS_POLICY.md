# DOCS_POLICY — slackops-devops-agent
최종 갱신: 2026-06-17

> 문서 운영 규칙(context budget). 상세 표준은 harness/CORE_MANDATES.md.
> 스킬·예산은 **overnight-harness 플러그인** + `.claude/harness-config.json`(budgets) 가 단일 소스.

## Context Budget (생명선)
| 문서 | 예산 | 내용 |
| --- | --- | --- |
| `AGENT_BRIEF.md` | ≤ 60줄 | 1분 압축 문맥, snapshot, 현재 초점, guardrails |
| `STATUS.md` | ≤ 120줄 | 현재 구현 상태, 검증 baseline, active focus, open risks |
| `NEXT_PLAN.md` | ≤ 120줄 | **열린 작업만**(완료 이력 아님) |
| `PROGRESS_LOG.md` | ≤ 120줄 | 최신 3–5개 증분. 넘치면 docs/archive/progress-YYYY-MM.md 분리 |

규칙: `docs/` 전체 bulk-read 금지(Read Path 만). 완료 체크리스트는 `COMPLETED_SUMMARY.md` 로 압축+링크.
비가역 선택은 `DECISIONS.md`(Decision/Reason/Impact). 추측 금지 — 없으면 "문서에 없음".

## Read Path (세션 시작/재개)
```
harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md → docs/STATUS.md → docs/NEXT_PLAN.md
→ (필요 시) docs/PROGRESS_LOG.md 상단 → (필요 시) docs/archive/
```
권위 순서: `NEXT_PLAN.md` > `docs/plans/`(historical). 불변 표준 = `harness/CORE_MANDATES.md`.

## skill 경계 (overnight-harness 플러그인 제공 — 겹치지 않게)
| skill | 언제 | 한 일 |
| --- | --- | --- |
| `/sync` | 세션 시작/재개 | Read Path 대로 current docs 만 읽고 5–10줄 요약. **읽기만.** |
| `/checkpoint` | 작업 묶음 완료 | 변경 수집 → PROGRESS_LOG append → STATUS/BRIEF/NEXT 조건부 갱신 → milestone/결정 기록. **기록만.** 커밋은 요청 시만. |
| `/tidy-docs` | 예산 초과/중복 | PROGRESS_LOG 월별 archive 분리, 완료 압축, 중복 통합·은퇴. **정리만.** 삭제는 마지막 수단, 파괴 전 승인. |
| `/overnight-report` | 아침 검수 | 러너 상태·회차·커밋·gate 재실측·잔여 백로그 보고. **읽기+검증만.** |
| `/overnight-seed` | 무인 가동 전 | `[auto]` 백로그 충분량 판단·후보 조사·승인분만 plan 에 기록. **기록만.** |

경계 원칙: **/sync 는 읽기만, /checkpoint 는 기록만, /tidy-docs 는 정리만.** 서로의 일을 하지 않는다.

## PROGRESS_LOG 항목 형식
```text
## YYYY-MM-DD — <한 줄 제목>
- Status:
- Changed:
- Verified:   # 실제로 돌린 검증만. 안 돌렸으면 "미검증".
- Blockers:
- Next:
```
