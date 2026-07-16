# V2_TEST — 검증·테스트 통합 가이드 (v2)

> 대상: 개발/리뷰/발표 준비. 목적: v2의 **테스트·검증 표면 전체**를 한 곳에.
> 기준: 2026-07-16. 게이트 권위 = `make check`. (구 `docs/guide/kr/QA_TEST.md`는 pass 수치가
> 오래됨 — 이 문서가 현행.) 상세 시나리오: `docs/guide/kr/DEMO_SCRIPT.md`.

## 1. 3층 게이트 — `make check`

커밋 게이트. 오프라인·결정적. 4개 서브타깃을 순서대로 실행(`check: test lint typecheck check-doc-budget`).

| 서브타깃 | 명령 | 목적 |
| --- | --- | --- |
| `make test` | `python3 -m pytest tests/ -q` | 전체 스위트 |
| `make lint` | `python3 -m ruff check src tests` | ruff |
| `make typecheck` | `python3 -m mypy src` | mypy strict |
| `make check-doc-budget` | `bash harness/check-doc-budget.sh` | 진입문서 라인 캡 |

- **현재 baseline: `540 passed` (~4.6s)** — STATUS와 일치. 스위트 42개 파일 / 420개 `def test_`.
- 게이트의 `make test`는 bare `pytest`(순수). 데모/에이전트 타깃만 `DEV_ENV`
  (`PYTHONPATH=src DDB_ENDPOINT=…:8931 AWS_REGION=us-east-1 AWS_*=local`)를 씀.
- `make smoke-local` = 동일 pytest(overnight-seed 빠른 스모크).

## 2. 테스트 스위트 맵 (영역 → 파일)

| 영역 | 대표 파일 (테스트 수) |
| --- | --- |
| **보안/guard** | `test_command_guard`(22, argv 경계 `;`/`$()` 거부) · `test_allowlist`(21) · `test_permissions`(5, L0/L1·L2 비활성) · `test_policy_boundary`(5, P2 scope) · `test_sanitizer`(13) · `test_security_corpus`(3, 인젝션 corpus) |
| **write credential** | `test_write_credentials`(17, 승인후 mint→revoke→audit) · `test_worker_write_grant`(9) · `test_execution_plan`(8)/`test_execution_plan_risk`(9, hash+RISK_CEILING=10) · `test_observed_tool_calls`(16, capability_drift 게이트) |
| **store** | `test_store`(14, 상태머신+atomic claim) · `test_chat_store`(6) · `test_audit_telemetry_store`(16, Sqlite+DynamoDb moto) · `test_audit_trajectory`(8, step-tree) |
| **worker/pr** | `test_worker`(16, output gate) · `test_pr_command`(13, 2-stage) · `test_tf_review_command`(10, no-apply) · `test_claude_runner`(25, stream-json→ToolCall) |
| **slack/assistant** | `test_slack_routing`(18, default-deny) · `test_assistant_handler`(12) · `test_assistant_flow`(4) · `test_assistant_console`(6) · `test_approval_actions`(16, Modal/Shortcut/approver allowlist) · `test_chat_agent`(4) · `test_proposal_notifier`(10, 🔔) · `test_canvas`(7, 포스트모템) · `test_main`(1) |
| **commands** | `test_logs_command`(15) · `test_diagnose_command`(19) · `test_detect`(6, L0 거버넌스 스캔) · `test_detection_config`(4) · `test_agent_monitor`(12, Tier1+실 claude) · `test_mcp_propose`(10) · `test_mcp_registry`(4) · `test_managed_mcp_pilot`(4, P3 scaffold) |
| **telemetry** | `test_telemetry`(9, devops.run span) |
| **deploy** | `test_deploy_security`(7) · `test_security_audit_deploy`(3, P1 sink) · `test_egress_proxy_config`(1, D17 egress) · `test_alarm_lambda`(9, 이벤트 구동) |
| **smoke** | `test_smoke`(3, import-safety) |

## 3. 로컬 e2e / 데모 검증

준비: `export CLAUDE_CODE_OAUTH_TOKEN="$(claude setup-token)"` 후 데모 타깃.

| 타깃 | 내용 |
| --- | --- |
| `make demo` | 풀 스택 한 방 — **web + DynamoDB Local(docker)** + chat_agent + worker 폴러. Ctrl-C 정리. |
| `make demo-all` | 위 + **Slack 앱**(`app.main`, Socket Mode). `.env` SLACK 토큰 필요. |
| `make slack` | `app.main` 단독(`.env` 자동 로드). web/docker 먼저 띄울 것. |
| `make demo-assistant` | 데모 스택 위 Assistant 콘솔(실 Slack 없이 동일 흐름, 실 Claude). |
| `make demo-assistant-mock` | **오프라인 canned replay** — 네트워크/Claude/docker 불필요, $0(라이브 폴백). |
| `make demo-incident SIGNAL="…"` | mock 장애 신호 → Tier1 규칙이 제안 적재. |

- **포트**: 대시보드 web **8930**, DynamoDB Local **8931**(`DDB_ENDPOINT` 로 로컬↔실 DDB 토글, D7). 컨테이너: `dynamodb-local` + `seed`(22 mock) + `web`.
- **로컬 검증 가능 플로우**: NL 채팅→스트리밍 렌더→pr 제안→diff 프리뷰+✅/❌ 버튼→승인(optimistic lock, "approved by @…")→**포스트모템 Canvas 자동 생성**→cost/token/tool-call footer; 🔔 벨/Detections 토글+Scan now; 인젝션 거부(`make demo-assistant`). `/devops ping` 로컬 동작.
- **pr execute(실 push)는 로컬에서 의도적으로 생략** — 실 push는 GitHub 인증 필요(=EC2/GitHub App 경로, `docs/runbooks/pr-write-credential-rehearsal.md`).

## 4. 클라우드 리허설 완료분 (STATUS 근거)

| 항목 | 검증 (일자) |
| --- | --- |
| **D4** 실 AWS | `make cloud-up`→EC2가 실 CloudWatch 진단(`checkout-service`, ~90s)→write op "denied by security policy"→`make cloud-stop`. ~$0.01 (2026-07-06) |
| **D15** | secure runtime 배포 — GitHub OAuth, plan/approval hash, workspace/tool/postcondition 검증, approver allowlist, EC2 hardening; Vercel+실 GitHub 로그인 통과 (07-15) |
| **D16** | fixed boto3 read adapter + sanitizer 격리; 모델 tool allowlist 비움; 범용 AWS MCP/uvx·불필요 S3·광범위 SSM 제거 (07-15) |
| **D17** 실 EC2 | 1h runtime/MCP STS + 45m 회전, fixed AWS read IAM, 4서비스/타이머, IMDS/직접 egress 거부, GitHub proxy allow·미등록 도메인 deny (07-15) |
| **P1** 실 EC2 | 30일 `/slackops/security-boundary-audit` sink; root-only audit role append만; runtime write 명시 deny; `credential_refresh`+URL-free `proxy_denied` 기록 (07-15) |
| **P2** 실 EC2 | root-owned env가 account/region/log-prefix/workspace 고정; 매 명령 scope 재검사; out-of-prefix fetch 거부→`policy_denied` (07-15) |
| 이벤트 루프 | CloudWatch ALARM→EventBridge→Lambda→DDB 큐→worker(Claude)→DONE→Slack ($0.15/2.7K–6K tok), EC2-off에서도 발화 (2026-06-20) |
| `/devops ping` | 실 EC2→Slack pong (2026-06-20) · **신 워크스페이스 로컬 pong 확인(2026-07-16)** |

## 5. 수동/미검증 잔여 (사람 필요)

- **GitHub App write 경로(pr execute / D19)** — 유일한 미검증 코드 경로. App 미등록 → mint→revoke·실 push 미검증. 절차: `docs/runbooks/pr-write-credential-rehearsal.md`. 발표 라이브 EC2 회차에 검증 예정.
- **Slack Message Shortcut 등록(`review_slackops_job`)** — 코드 완료(07-15), 등록은 수동. 비허용 사용자 modal 차단 + 허용 결정의 원본 메시지/감사 반영 확인.
- **approver 리허설 / Part B 실 AWS** — `make cloud-up`→Assistant로 실 CloudWatch 진단→write "denied"→`make cloud-stop`. 비용 사람 승인(~$1).
- **D19–D23 EC2 리허설 없음** — 로컬 `claude -p` 대상만 검증.
- **Canvas 무료 트라이얼 2026-07-19 종료** — 캡처/데모는 그 전에(또는 유료 워크스페이스).
- **알려진 한계**: 비스트리밍 `worker` 경로의 `tool_calls` 텔레메트리는 아직 `None`(스트리밍 chat_agent/Assistant만 수집).
