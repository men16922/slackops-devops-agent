---
name: overnight-report
description: overnight 러너 상태/결과 점검 보고 — 프로세스 생존, 회차 로그, 밤새 커밋, PROGRESS_LOG, pytest 재검증, 잔여 [auto] 백로그를 한 화면으로. 경계=읽기+검증 실행만 (기록은 checkpoint, 정리는 tidy-docs).
---

# /overnight-report — 무인 가동 결과 보고 (읽기 + 검증만)

`bin/overnight/run.sh` 가 밤새 한 일을 점검해 한 화면으로 보고한다.
**문서를 수정하지 않는다** — 기록할 게 있으면 /checkpoint 를 안내.

## 절차
1. **러너 상태**
   - `pgrep -fl "overnight/run.sh"` → 살아있는지 / 종료됐는지.
   - `ls bin/overnight/` → `STOP`(수동 중단) / `DONE`(백로그 소진) 파일 유무와 DONE 내용.
2. **회차 요약**: `tail -40 bin/overnight/logs/runner.log`
   - 총 회차 수, ok/FAILED 수, limit 대기 발생 여부, 연속 실패 중단 여부.
   - FAILED 회차가 있으면 해당 `iter-*.log` 끝부분을 열어 원인 1줄 요약.
3. **밤새 산출물**: `git log --oneline` 에서 러너 시작 시각 이후 커밋 나열 +
   `docs/PROGRESS_LOG.md` 상단의 해당 항목들(Status/Verified/Blockers 위주).
4. **독립 재검증**: 게이트 3계층 직접 실행 — 에이전트 주장이 아닌 실측으로 green 확인:
   `python3 -m pytest tests/ -q` + `python3 -m ruff check src tests` + `python3 -m mypy src`.
   실패 시 마지막 green 커밋을 `git log` 로 식별해 보고.
5. **잔여 백로그**: `docs/NEXT_PLAN.md` 의 남은 `[auto]` / `[manual]` 항목 수와 다음 작업.
6. **보고 형식** (10–15줄):
   ```
   ## Overnight Report — YYYY-MM-DD
   - 러너: 종료(DONE|STOP|실패중단|max_iter) 또는 가동 중
   - 회차: N회 (ok M / fail K / limit 대기 L회)
   - 커밋: <해시 목록 한 줄씩>
   - pytest 실측: X passed, Y skipped
   - 잔여: [auto] N개 (다음: <항목>) / [manual] M개
   - 권고: <리뷰 필요 항목 / 재시작 여부 / 다음 액션 1–2개>
   ```

## 권고 판단 기준
- fail 회차 존재 → 해당 iter 로그 + revert 여부 확인을 첫 권고로.
- pytest 실측 red → **즉시 중단 권고**(STOP) + 마지막 green 커밋 명시.
- DONE → `/code-review` 등 사람 리뷰 단계 제안.
- 가동 중 + 정상 → 그대로 두기 / 관찰 명령 안내.

## 경계
- **읽기 + 검증 실행만.** PROGRESS_LOG/STATUS 갱신 금지(→ /checkpoint), 로그/문서 정리 금지(→ /tidy-docs).
- 추측 금지 — 로그에 없으면 "로그에 없음".
