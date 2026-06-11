---
name: tidy-docs
description: context budget 초과/중복 시 PROGRESS_LOG 월별 archive 분리·완료 압축·중복 통합/은퇴. 경계=정리만 (읽기는 sync, 기록은 checkpoint).
---

# /tidy-docs — 문서 정리 (정리만)

문서가 비대해지거나 중복되면 정리한다. **정리만 한다 — 새 진행/결정 기록은 하지 않는다.**

## 절차
1. Context Budget 점검(DOCS_POLICY.md):
   - `AGENT_BRIEF.md` ≤60줄, `STATUS.md`/`NEXT_PLAN.md`/`PROGRESS_LOG.md` ≤120줄.
2. `PROGRESS_LOG.md` 가 예산 초과면 오래된 항목을 `bin/docs/archive/progress-YYYY-MM.md` 로 분리(원문 보존).
3. 완료 체크리스트/장문 이력은 `COMPLETED_SUMMARY.md` 로 압축 + 링크.
4. 중복 문서/항목 통합·은퇴. archive 로 옮긴 원문은 링크로 추적.
5. 각 문서 상단 `최종 갱신: YYYY-MM-DD` 갱신.

## 경계
- **정리만.** 새 PROGRESS_LOG 항목/결정 기록(checkpoint), 상태 복원 요약(sync)은 하지 않는다.
- **삭제는 마지막 수단.** 파괴적 작업(삭제/덮어쓰기) 전 사용자 승인. 가능하면 archive 이동으로 보존.

## 검증 명령
- `python -m pytest tests/ -q`
