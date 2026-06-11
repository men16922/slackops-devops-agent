# docs/ — slackops-devops-agent
최종 갱신: 2026-06-11

> docs 인덱스 + Read Path. 전체 bulk-read 금지 — Read Path 순서대로만.

## Read Path (세션 시작/재개)
```
harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md → docs/STATUS.md → docs/NEXT_PLAN.md
→ (필요 시) docs/PROGRESS_LOG.md 상단 → (필요 시) bin/docs/archive/
```

## 인덱스
| 문서 | 역할 | 예산 |
| --- | --- | --- |
| `AGENT_BRIEF.md` | 1분 압축 진입점 | ≤60줄 |
| `STATUS.md` | 현재 상태/검증/risks (source of truth) | ≤120줄 |
| `NEXT_PLAN.md` | 열린 작업만 | ≤120줄 |
| `PROGRESS_LOG.md` | 최신 증분(최신이 위) | ≤120줄 |
| `COMPLETED_SUMMARY.md` | 완료 milestone 압축+링크 | — |
| `DECISIONS.md` | 비가역 결정(Decision/Reason/Impact) | — |
| `DOCS_POLICY.md` | 문서 운영 규칙(context budget) | — |
| `plans/` | dated 스냅샷(YYYY-MM-DD-<topic>.md, historical) | — |

## 운영
- 읽기 `/sync` · 기록 `/checkpoint` · 정리 `/tidy-docs`. 경계는 DOCS_POLICY.md.
- 불변 표준은 `harness/CORE_MANDATES.md`. 핸드오프는 `harness/CONTEXT_BRIDGE.md`.
- 비대해진 원문/로그는 `bin/docs/archive/`(기본 컨텍스트 제외).
