# Engineering Interpretation — slackops-devops-agent

이 문서는 `docs/engineering/*_ENGINEERING.md` **바이블(범용 개념)** 을 **이 repo의 실제 파일·명령·메커니즘에 매핑**한다.
바이블 = "무엇/왜"(portable), 이 문서 = "이 repo에서 어떻게". (구 `docs/LOOP_ENGINEERING.md` 내용 흡수.)
리포 불변 표준은 `harness/CORE_MANDATES.md`, 핸드오프는 `harness/CONTEXT_BRIDGE.md`.

## HARNESS — 성숙도/검증/권한 (바이블 `HARNESS_ENGINEERING.md`)
- gate(검증): `make check` = `pytest tests/ -q` + `ruff check src tests` + `mypy src`(strict).
  전부 green 못 하면 커밋 안 함 → 깨진/저품질 코드 누적 방지(아침 인간 리뷰 비용↓). baseline 229 passed, 1 skipped.
- 권한 경계: `scripts/overnight/overnight-settings.json` (`--settings` 격리 적용 — 인터랙티브 settings 불변).
  allow=gate 타깃(make/python3/git 일부), deny=`aws`·`git push`·`curl`/`wget`·`rm -rf`·`sudo`·Web*·github MCP.
- 성숙도: 로컬 [auto] 백로그 소진 단계 — 잔여는 [manual](AWS/Slack/UI). 다음 투자처 = 실 e2e/관측 캡처.

## LOOP — 무인 루프 (바이블 `LOOP_ENGINEERING.md`)
- 러너: `scripts/overnight/run.sh` (단일 엔진 claude). 회차마다 `claude -p PROMPT --settings overnight-settings.json`.
  env: `GATE_CMD`(=make check)/`MAX_ITER`(50)/`ITER_TIMEOUT`(3600s)/`LIMIT_WAIT`(1800s)/`PAUSE`(30s)/
  `MAX_CONSEC_FAIL`(3)/`MAX_NO_PROGRESS`(2)/`KEEP_ITER_LOGS`(30)/`--once`.
- 결과 분류: `--output-format json` 마지막 객체 `is_error==false` → success(성공 회차 텍스트의 'rate limit'
  언급 무시), 아니면 limit 텍스트 검사 → limit(대기·재시도), 그 외 failure. success 시 HEAD 전후 비교로
  no_progress 판정(빈 회차/Blocker 반복 차단).
- 회차 프롬프트: `scripts/overnight/PROMPT.md` — ①sync ②잔여물 복구(dirty+green=`[recovered]` 커밋,
  red=무수정+STOP) ③`[auto]` 최상위 1개(2회 Blocker→`[blocked]`, 소진→DONE) ④구현+gate ⑤checkpoint ⑥로컬 커밋.
- 백로그 태그: `[auto]`/`[manual]`/`[blocked]` in `docs/NEXT_PLAN.md`. 위→아래 1개씩, 완료 시 제거.
- **품질 리뷰 회차 패턴**: 구현 milestone 뒤 read-only 리뷰형 `[auto]`(보안/타입/단순화 관점, 코드 무수정)
  → findings 를 `[auto]` 로 환류 → 다음 회차가 수정. 1회차=1작업 불변 유지하며 품질 루프 형성.
- skills: `/overnight-harness:{sync,checkpoint,tidy-docs,overnight-report,overnight-seed}` (플러그인 제공).

## AGENTIC — 멀티에이전트 (바이블 `AGENTIC_ENGINEERING.md`)
- 현재 단일 엔진(claude). 멀티 도입 시 레인/도메인 분할·worktree 격리·builder≠reviewer 를 여기 매핑.

## CONTEXT — 컨텍스트/문서 규율 (바이블 `CONTEXT_ENGINEERING.md`)
- Read Path: `harness/CONTEXT_BRIDGE.md` → `docs/AGENT_BRIEF.md` → `docs/STATUS.md` → `docs/NEXT_PLAN.md`
  → (필요 시) `docs/PROGRESS_LOG.md` 상단 → (필요 시) `docs/archive/`. docs/ 전체 bulk-read 금지.
- 라인 예산: brief ≤60 · status/plan/log ≤120 (`.claude/harness-config.json` budgets). 운영 규칙 `docs/DOCS_POLICY.md`.
- 상태는 파일에: `NEXT_PLAN`(백로그)·`PROGRESS_LOG`(이력)·git history 가 source of truth(메모리 아님).
- archive: `docs/archive/progress-YYYY-MM.md` (`/tidy-docs` 가 PROGRESS_LOG 초과분 월별 분리).

## PROMPT — 프롬프트 레이어 (바이블 `PROMPT_ENGINEERING.md`)
- 하네스 프롬프트: `scripts/overnight/PROMPT.md` (+ 리포 불변 절: CORE_MANDATES/aws→mock/lazy import/한국어).
- 런타임/도메인 프롬프트: `src/app/sanitizer.py`(wrap_untrusted + build_prompt template) — Slack 입력 직접
  전달 금지·로그/diff 는 `<untrusted_data>` 격리(주입 방어 4계층의 일부).

## 한계 / 알려진 동작 (구 LOOP_ENGINEERING §5)
- Mac 절전: `caffeinate` 필수, 전원 연결 권장. 회차 단위 손실: 한도가 회차 중간에 닥치면 진행 중 1회차만
  미커밋 손실(직전까진 커밋, 다음 회차 `/sync` 복원 — PROMPT 2단계 [recovered] 자동화, red 는 사람 검수).
