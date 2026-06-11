# Overnight 회차 지시문 — slackops-devops-agent

너는 무인(overnight) 회차로 실행 중이다. 사용자에게 질문할 수 없다 — 모호하면 보수적으로 판단하고
근거를 기록하라. 이번 회차에서 **작업 1묶음만** 수행한다.

## 절차 (순서 고정)
1. **상태 복원**: Skill `sync` 호출 (Read Path: harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md
   → docs/STATUS.md → docs/NEXT_PLAN.md).
2. **작업 선택**: docs/NEXT_PLAN.md 에서 `[auto]` 태그가 붙은 **최상위 미완료 작업 1개만** 선택.
   `[manual]` 태그는 절대 수행하지 않는다(AWS/Slack 수동 단계).
   - `[auto]` 작업이 하나도 없으면: `bin/overnight/DONE` 파일을 생성하고(내용: 사유 1줄) 즉시 종료.
3. **구현**: 선택한 작업을 항목의 완료 기준대로 구현 + 테스트 추가.
   `python3 -m pytest tests/ -q` **전체 통과까지**. 통과시키지 못하면 해당 변경을 `git restore` 로
   되돌리고 PROGRESS_LOG 에 Blocker 로 기록 후 4단계로 진행.
4. **기록**: Skill `checkpoint` 호출 — PROGRESS_LOG append(Verified 는 실제 실행한 검증만),
   STATUS/NEXT_PLAN 갱신(완료 항목 제거), 비가역 결정 시 DECISIONS 기록.
5. **커밋**: `git add -A && git commit` (로컬 커밋만, 메시지에 작업 한 줄 요약).

## 불변 (위반 금지)
- harness/CORE_MANDATES.md 전체 준수 (타입힌트, `print` 금지, lazy import 유지 등).
- `aws` CLI 실 호출 금지(자격증명 없음/금지). AWS 연동 코드는 **mock/주입 가능한 의존성**으로
  단위테스트까지만.
- `git push` 금지, 외부 네트워크(curl/wget/WebFetch) 금지.
- 새 의존성은 pyproject.toml 갱신 + 미설치 환경에서도 테스트 통과(lazy import) 유지.
- 작업 1묶음 초과 금지 — 다음 작업은 다음 회차가 한다.
- usage limit 등으로 중단될 것 같으면 즉시 4–5단계(checkpoint+commit)를 먼저 수행.
