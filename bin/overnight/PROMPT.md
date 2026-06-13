# Overnight 회차 지시문 — slackops-devops-agent

너는 무인(overnight) 회차로 실행 중이다. 사용자에게 질문할 수 없다 — 모호하면 보수적으로 판단하고
근거를 기록하라. 이번 회차에서 **작업 1묶음만** 수행한다.

## 절차 (순서 고정)
1. **상태 복원**: Skill `sync` 호출 (Read Path: harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md
   → docs/STATUS.md → docs/NEXT_PLAN.md).
2. **잔여물 복구**: `git status --porcelain` 으로 작업 트리 확인. 깨끗하면 3단계로.
   dirty 면 이전 회차가 중단된 잔여물이다 — **복구가 이번 회차의 작업 1묶음**이 된다
   (잔여물 위에 새 작업을 시작하거나, 5–6단계에서 잔여물을 새 작업 커밋에 섞지 않는다):
   - `python3 -m pytest tests/ -q` 전체 green → `git diff` 로 어떤 작업의 잔여물인지 식별 후
     그대로 5–6단계(checkpoint+commit)로 직행. 커밋 메시지 앞에 `[recovered]` 를 붙인다.
   - red → 잔여물을 **건드리지 않는다**(restore/삭제 금지 — 사람 검수 필요 상태).
     PROGRESS_LOG 에 Blocker(`git status --porcelain` 목록 + pytest 실패 요약) 기록 후
     `bin/overnight/STOP` 을 생성하고 즉시 종료(러너가 graceful 정지). 커밋하지 않는다.
3. **작업 선택**: docs/NEXT_PLAN.md 에서 `[auto]` 태그가 붙은 **최상위 미완료 작업 1개만** 선택.
   `[manual]` 태그는 절대 수행하지 않는다(AWS/Slack 수동 단계). `[blocked]` 태그도 건너뛴다.
   - 선택 전 docs/PROGRESS_LOG.md 에서 후보 항목의 Blocker 이력 확인 — **같은 항목 Blocker 가
     이미 2회**면 같은 방식 재시도 금지: NEXT_PLAN 해당 줄에 `[blocked]` 태그를 덧붙이고(사유 1줄)
     다음 `[auto]` 후보로 넘어간다.
   - 남은 `[auto]` 가 없거나 전부 `[blocked]` 면: `bin/overnight/DONE` 파일을 생성하고
     (내용: 사유 1줄 — 소진/전원 blocked 구분) 즉시 종료.
4. **구현**: 선택한 작업을 항목의 완료 기준대로 구현 + 테스트 추가. 게이트 3계층 **전부 green 까지**:
   `python3 -m pytest tests/ -q` + `python3 -m ruff check src tests` + `python3 -m mypy src`.
   통과시키지 못하면 해당 변경을 `git restore` 로 되돌리고 PROGRESS_LOG 에 Blocker 로 기록 후
   5단계로 진행.
5. **기록**: Skill `checkpoint` 호출 — PROGRESS_LOG append(Verified 는 실제 실행한 검증만),
   STATUS/NEXT_PLAN 갱신(완료 항목 제거), 비가역 결정 시 DECISIONS 기록.
6. **커밋**: 먼저 `git status`로 이번에 구현/수정한 파일이 실제로 변경 목록에 있는지 확인한다 —
   비어 있으면 write 가 유실된 것이니 보고 후 재작성(false success 방지). 확인되면
   `git add -A && git commit` (로컬 커밋만, 메시지에 작업 한 줄 요약).

## 불변 (위반 금지)
- harness/CORE_MANDATES.md 전체 준수 (타입힌트, `print` 금지, lazy import 유지 등).
- `aws` CLI 실 호출 금지(자격증명 없음/금지). AWS 연동 코드는 **mock/주입 가능한 의존성**으로
  단위테스트까지만.
- `git push` 금지, 외부 네트워크(curl/wget/WebFetch) 금지.
- 새 의존성은 pyproject.toml 갱신 + 미설치 환경에서도 테스트 통과(lazy import) 유지.
- 작업 1묶음 초과 금지 — 다음 작업은 다음 회차가 한다.
- usage limit 등으로 중단될 것 같으면 즉시 5–6단계(checkpoint+commit)를 먼저 수행.
