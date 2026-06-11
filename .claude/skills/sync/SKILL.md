---
name: sync
description: 세션 시작/재개 시 Read Path 대로 current docs 만 읽고 5–10줄로 상태 복원. 경계=읽기만 (기록은 checkpoint, 정리는 tidy-docs).
---

# /sync — 상태 복원 (읽기만)

세션 시작/재개 시 작은 컨텍스트로 현재 상태를 복원한다. **읽기만 한다 — 어떤 문서도 수정하지 않는다.**

## 절차
1. Read Path 순서대로만 읽는다 (docs/ 전체 bulk-read 금지):
   ```
   harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md → docs/STATUS.md → docs/NEXT_PLAN.md
   → (필요 시) docs/PROGRESS_LOG.md 상단 → (필요 시) bin/docs/archive/
   ```
2. 권위 순서: NEXT_PLAN.md > docs/plans/(historical). 불변 표준 = harness/CORE_MANDATES.md.
3. 5–10줄로 요약 출력: 현재 상태 / active focus / 다음 작업 / open risks.

## 경계
- **읽기만.** PROGRESS_LOG append, STATUS/BRIEF/NEXT 갱신, 정리/삭제 모두 금지(그건 checkpoint/tidy-docs 일).
- 추측 금지 — 문서에 없으면 "문서에 없음".

## 참고: 검증 명령
- `python -m pytest tests/ -q`
