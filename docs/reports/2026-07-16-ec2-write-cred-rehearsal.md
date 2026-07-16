# EC2 write-credential rehearsal — findings report (2026-07-16)

> 목적: task #3 "GitHub App write credential 경로 실검증"을 실 EC2에서 end-to-end로 확인.
> 결과: **write-credential 코드 경로는 검증됨(로컬)**, EC2 full-flow는 리허설 중 발견된
> **실 배포 버그 4건**에 막혀 최종 PR 생성까지는 미도달. 그중 2건은 수정·커밋·배포 완료.
> 이 리허설은 그 자체로 "cloud MCP path 미검증"(STATUS)을 처음으로 실측한 의미가 있다.

## 1. 검증 완료 (green)

| 항목 | 결과 | 근거 |
| --- | --- | --- |
| write-credential **코드**(`GitHubAppGrantIssuer.issue/revoke`) | ✅ 실 GitHub 통과 | 로컬 mint 스모크: repo-scoped installation token 발급(len 40, ~600s 만료) → 즉시 회수. App ID `4313190` + Installation `146935243` + PEM 유효 |
| GitHub App 등록·설치 | ✅ | 대상 repo 1개(`men16922/slackops-devops-agent`), 권한 `contents`+`pull_requests` write만 |
| SSM 4종 저장 | ✅ | `PR_REPOSITORY`/`GITHUB_APP_ID`/`GITHUB_INSTALLATION_ID`(String) + `GITHUB_APP_PRIVATE_KEY_B64`(SecureString) |
| branch protection | ✅ | require PR before merge + Required approvals=1 (봇 self-merge 차단) |
| **MCP `propose_job` on EC2** | ✅ (수정 후) | 에이전트가 pr job 큐 적재 성공 — 이전엔 미검증("cloud redeploy pending") |
| **P2 결정적 scope 경계** | ✅ 실증 | 자율 diagnose('api')가 `policy_denied: resource_not_allowed`로 fetch 전 차단 |
| **D23 capability-drift 게이트** | ✅ 실증 | pr prepare 중 복합명령 `git status && git branch`를 감지·거부(전체 궤적 감사 기록) |

## 2. 발견한 실 배포 버그 4건

### #1 MCP 서버 런치 — bare `"python"` (수정·커밋·배포 완료)
`mcp_config_json`이 propose_job MCP 서버를 `command:"python"`으로 실행. EC2 AL2023엔 `python`이
없고(`python3`만) app 패키지는 venv에만 설치돼 있어 서버가 안 뜸 → "connector connecting but tool
never loaded" → agent가 propose_job 호출 불가. **로컬은 `python`이 있어 통과했던 미검증 지점.**
- 수정: `command: sys.executable` (실행 중인 인터프리터 = EC2 venv python). 커밋 `1bb34f2`. 회귀 테스트 갱신.

### #2 credential refresher 부팅 미가동 (문서화 — 정식 수정 필요)
`slackops-runtime-credentials-refresh.timer` 첫 발화가 **부팅 +43분**. 그 전까지 서비스가 runtime
role이 아닌 **bootstrap `slackops-devops-agent-role`**로 동작 → 이 role엔 `dynamodb:Query`가 없어
worker가 job을 claim 못 함(GSI1 Query AccessDenied). 자율/사용자 job이 전부 PENDING에 방치.
- 임시 언블록: `systemctl start slackops-runtime-credentials-refresh.service`(정식 메커니즘 수동 발화)
  → 신원이 `...-runtime-role`로 전환, Query 성공, worker가 즉시 claim 시작.
- **정식 수정 후보**: refresher timer에 `OnBootSec`(부팅 직후 1회) 추가, 또는 부팅 시 서비스가 runtime
  credential을 동기 확보한 뒤 시작.

### #3 credential 회전이 진행 중 job을 끊음 (문서화 — 정식 수정 필요)
refresher(45분 주기)의 `ExecStartPost=systemctl try-restart`가 4개 서비스를 재시작 → **실행 중인
worker의 pr prepare(claude, 다분 소요)를 죽임** → job이 "running"에 고아로 남고(claim 대상 아님) 복구
안 됨. 실측: 12:27 claim → 12:29 회전 → prepare 중단, job 영구 running.
- **정식 수정 후보**: (a) 회전 시 in-flight job이 있으면 유예/드레인, (b) worker가 오래된 "running" job을
  타임아웃·재큐, (c) worker를 회전 재시작 대상에서 제외(자체 credential 갱신).

### #4 capability-drift가 guard-차단 호출을 drift로 오판 (수정·커밋·배포 완료)
D23 게이트가 PreToolUse guard가 **차단한**(is_error, 실행 안 됨) 툴콜까지 관측 capability에 넣어 job을
FAILED 처리. EC2에서 claude가 복합 `git status && git branch`를 냈고, guard가 정상 차단→claude가 두
명령으로 재시도했는데도 job이 `capability_drift`로 실패.
- 수정: `_enforce_observed_capability`가 **실제 실행된(is_error=False)** 호출만 enforce(궤적엔 차단
  호출도 기록 유지). D23 본래 목적("guard를 우회해 **실행된** 호출을 잡는다")에 부합. 커밋 `0daf506` + 회귀 테스트.

### #5 diff 없는 pr prepare 가 DONE(성공)으로 완료됨 (수정·커밋 완료)
EC2에서 pr prepare 의 claude 호출이 **read-only 조사만 하다(~280s, 300s 타임아웃 근처) diff 를 못
만들고** 끝났는데, worker 가 이를 **조용히 DONE(성공)** 처리했다(`578821eb`). 사용자가 "PR 만들어줘"
했는데 "완료됨"이라 표시되지만 PR·diff 는 없다 = 거짓 성공. (사용자 지적으로 확인)
- 원인: `worker.process_one` 이 `outcome.diff is None` 이면 승인 게이트를 건너뛰고 fall-through 해
  `complete(DONE)`. read-only 명령엔 맞지만 **pr prepare 는 diff 가 반드시 있어야** 한다.
- 수정: pr prepare(미승인) 가 diff 없이 이 지점에 오면 `PrPrepareProducedNoDiff` 로 **FAIL**(명확한
  사유). read-only 명령·pr execute(승인 후 push)는 정상적으로 diff 없이 DONE. 회귀 테스트
  `test_pr_prepare_without_diff_fails_not_done`.
- 부수: prepare 자체가 300s 안에 실제 변경을 못 내는 것(그 값이 이 PR 의 대상)은 별개의 튜닝 이슈 —
  더 좁은 요청(파일·변경 명시) 또는 timeout 상향으로 해소.

## 3. 미도달

**write grant → 실 PR 오픈 → `write_credentials_issued` 감사** (Done 조건 1~3의 execute 단계)는
아직 관측 못 함. 이유: pr prepare가 #3(회전 재시작)에 반복적으로 끊기고, 최종 전송·승인 외부 액션은
자동화가 안전경계에 막힘(사람이 클릭해야 함 — 아래 §5).

## 4. 관련 커밋

- `1bb34f2` fix(mcp): launch propose_job MCP server with sys.executable
- `0daf506` fix(worker): capability-drift gate must not fail on guard-denied tool calls
- `76cf08e`/`ea21229` docs (Slack 이전·문서통합·task#3 진행)

## 5. 남은 사람 몫 (2 클릭) + 정리

깨끗한 credential-회전 창(직전 회전 직후 ~40분) 안에서:
1. Slack 봇 DM에 `Open a PR to raise the Claude Code headless timeout from 300s to 600s` 전송
2. worker가 diff 준비 후 뜨는 **Approve** 클릭 → execute → 실 PR + 감사

> 자율 에이전트/브라우저 자동화로 이 2개(외부 write)를 대신 누르는 것은 auto-mode 분류기가 차단한다.
> 이는 "사람이 실행 경계를 쥔다"는 SlackOps 원칙과 일치한다.

**인프라**: EC2 `i-0975c8e190affa86c` running 중(t3.medium, 소액 과금). 완료(또는 보류) 결정 시
`make cloud-stop`으로 정지 권장. `i-0472…`는 이미 terminated.

## 6. 검증 방식 전환 — TC (Slack/EC2 불필요)

**핵심 통찰(사용자)**: pr prepare→diff→승인→execute→write grant 전 과정은 **injected runner/mock 으로
TC 검증하면 동일**하다. Slack/EC2 는 *배포* 버그를 잡는 데 유효했지만(5건), *코드 correctness* 는 TC 가
맞다. 현재 **`make check` = 542 passed** + ruff + mypy(strict) + doc-budget 전부 green 으로 아래가 검증됨:

| 흐름 | 커버 TC |
| --- | --- |
| write credential 발급(승인 hash 재검증 후에만, 실패 조건들, 회수) | `test_write_credentials`(17) |
| worker 의 승인당 scoped write grant / 부분설정 fail-closed | `test_worker_write_grant`(9) |
| immutable plan hash / capability 5-class / RISK_CEILING=10 | `test_execution_plan`(8)+`_risk`(9) |
| pr 2-stage(prepare push제거·diff마커, execute push복원) | `test_pr_command`(13) |
| 출력 게이트(diff→AWAITING_APPROVAL, 승인→execute→DONE, TOCTOU fail) | `test_worker`(17) |
| capability-drift(우회실행 fail, guard차단 무시, 관측 재집계) | `test_observed_tool_calls`(17) |
| **diff 없는 pr prepare → FAIL (신규, #5)** | `test_pr_prepare_without_diff_fails_not_done` |
| MCP config = sys.executable / registry 정합(#1) | `test_agent_monitor`·`test_mcp_registry` |

## 7. 결론

write-credential **코드 경로 correctness 는 TC 로 검증 완료**(542 passed), 실 GitHub 발급→회수도 로컬
스모크로 확인됨. EC2 리허설은 D17 하드닝 배포의 실 버그 **6건을 드러냈다**(#1·#4·#5 수정·커밋, #2·#3
문서화, prepare-timeout 튜닝). 보안 메커니즘(P2 scope / D23 drift / MCP propose)은 실 EC2에서 **정상
작동이 관측**됐다. 남은 것은 운영 배포 안정화(#2/#3)와, 원하면 사람 승인 2클릭으로 실 PR 1회 확인이다.
