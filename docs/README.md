# docs/ — slackops-devops-agent
최종 갱신: 2026-06-17

> docs 인덱스 + Read Path. 전체 bulk-read 금지 — Read Path 순서대로만.

## Read Path (세션 시작/재개)
```
harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md → docs/STATUS.md → docs/NEXT_PLAN.md
→ (필요 시) docs/PROGRESS_LOG.md 상단 → (필요 시) docs/archive/
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
| `engineering/` | 하네스 엔지니어링 bibles(제네릭) + `interp/INTERPRETATION.md`(리포 매핑) | — |

## 운영
- 읽기 `/sync` · 기록 `/checkpoint` · 정리 `/tidy-docs`(overnight-harness 플러그인 제공). 경계는 DOCS_POLICY.md.
- 무인 자율 가동: `make overnight`(=`scripts/overnight/run.sh`) — NEXT_PLAN `[auto]` 백로그를 회차(작업 1묶음
  → `make check` → checkpoint → commit) 단위로 진행. 단발 `make overnight-once`, 중단 `make overnight-stop`.
- 불변 표준은 `harness/CORE_MANDATES.md`. 핸드오프는 `harness/CONTEXT_BRIDGE.md`.
  하네스 엔지니어링 설명서는 `docs/engineering/`(+ `interp/INTERPRETATION.md`).
- 비대해진 원문/로그는 `docs/archive/`(기본 컨텍스트 제외).
