---
name: checkpoint
description: 작업 묶음 완료 시 변경을 수집해 PROGRESS_LOG append + STATUS/BRIEF/NEXT 조건부 갱신 + milestone/결정 기록. 경계=기록만 (읽기는 sync, 정리는 tidy-docs).
---

# /checkpoint — 진행 기록 (기록만)

작업 묶음 완료 시 정해진 자리에 상태를 기록한다. **기록만 한다 — 정리/압축/삭제는 하지 않는다.**

## 절차
1. 이번 묶음의 변경 수집(무엇을 바꿨고 무엇을 검증했나).
2. `docs/PROGRESS_LOG.md` 최상단에 항목 append (형식 아래). **실제로 돌린 검증만** 기록, 안 돌렸으면 "미검증".
3. 조건부 갱신:
   - `STATUS.md` — 현재 상태/검증 baseline/active focus/risks 가 바뀌었으면.
   - `AGENT_BRIEF.md` — snapshot/현재 초점이 바뀌었으면.
   - `NEXT_PLAN.md` — 완료 작업 제거, 새로 열린 작업 추가.
   - `COMPLETED_SUMMARY.md` — milestone 완료 시 한 줄+링크.
   - `DECISIONS.md` — 비가역 결정 발생 시 Decision/Reason/Impact.
4. 각 문서 상단 `최종 갱신: YYYY-MM-DD` 갱신. Context Budget 준수.
5. 커밋은 **사용자가 요청할 때만**.

## PROGRESS_LOG 항목 형식
```text
## YYYY-MM-DD — <한 줄 제목>
- Status:
- Changed:
- Verified:   # 실제로 돌린 검증만. 안 돌렸으면 "미검증".
- Blockers:
- Next:
```

## 경계
- **기록만.** Read Path 복원 요약(sync), archive 분리·중복 통합·삭제(tidy-docs)는 하지 않는다.
- 예산 초과/중복이 보이면 직접 정리하지 말고 /tidy-docs 를 안내.

## 검증 명령 (게이트 3계층 — 전부 green 이어야 "완료")
- `python3 -m pytest tests/ -q` (멀티파일 변경 후 전체 실행, pass/fail 보고. 통과 전 "완료" 선언 금지.)
- `python3 -m ruff check src tests`
- `python3 -m mypy src`
