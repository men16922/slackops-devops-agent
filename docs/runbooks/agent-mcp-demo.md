# 런북 — 자율 운영 에이전트 (MCP 제안 → 사람 승인)

운영 에이전트가 시스템 신호를 관찰하고 **MCP `propose_job` 도구**로 작업을 큐에 제안하면,
사람이 web 대시보드에서 승인을 내린다. 권한 모델과 포개진다: 에이전트는 L0(관찰)은 자유,
L1(쓰기, pr 등)은 기존 출력 게이트에서 `awaiting_approval` 로 멈춰 사람 승인을 기다린다.

```
agent_monitor (감지) ──MCP: propose_job──▶ Job Queue(source=agent, +rationale, pending)
                                                  │  worker(기존): L0 즉시 / L1 은 출력게이트
                                                  ▼
                                   web 대시보드 ── diff+근거 → Approve/Reject
```

## 구성요소

| 파일 | 역할 |
| --- | --- |
| `src/app/mcp_server.py` | `propose_job`/`list_pending` MCP 도구(FastMCP, stdio). server name `slackops` → 도구 `mcp__slackops__propose_job`. default-deny(permissions 레지스트리). |
| `src/app/agent_monitor.py` | Tier1 시뮬레이터(`simulate_detection`, 규칙기반·토큰불필요) + Tier2 실제(`run_monitor_headless`, claude -p). |
| `src/app/claude_runner.py` | `build_command(..., mcp_config)` — `--mcp-config` + `--strict-mcp-config`. |
| `web/` 대시보드 | `source=agent` 뱃지 + 제안 근거(rationale) 표시 + Approve/Reject. |

## Tier 1 — 시뮬레이터 (기본, 토큰 불필요)

LLM 없이 결정적 규칙으로 신호 → 제안. CI/데모에서 항상 재현. **에이전트 대역**(실 추론 아님).

```bash
# 1) 대시보드 + DynamoDB Local 기동 (dynamodb-local 호스트 포트 8931 노출)
cd web && docker compose up -d --build

# 2) 모니터 1회 — 데모 신호(504 spike)로 제안 적재
cd ..
DDB_ENDPOINT=http://localhost:8931 python3 -m app.agent_monitor
#   → log: monitor.sim.proposed job_id=… command=pr/diagnose …
#   또는: make agent-monitor

# 3) 직접 신호 주입 / 반복(EventBridge 스케줄 대역)
DDB_ENDPOINT=http://localhost:8931 python3 -m app.agent_monitor --signals-file ./signals.txt
DDB_ENDPOINT=http://localhost:8931 python3 -m app.agent_monitor --loop 30
```

대시보드(http://localhost:8930) 피드 최상단에 `🤖 agent` 제안이 뜨고, 상세에서 근거 + (PR이면)
diff 와 Approve/Reject 를 확인한다.

## Tier 2 — 실제 Claude Code Headless (옵션, 토큰 필요)

실제 에이전트가 신호를 보고 직접 `propose_job` 을 호출한다.

```bash
# 전제: claude CLI 설치 + 구독 토큰
export CLAUDE_CODE_OAUTH_TOKEN="$(... 또는 claude setup-token)"
export DDB_ENDPOINT=http://localhost:8931   # MCP 서버가 같은 DynamoDB Local 에 적재

python3 -m app.agent_monitor --real
#   내부적으로 다음과 동치:
#   claude -p "<관찰 프롬프트>" \
#     --mcp-config '{"mcpServers":{"slackops":{"command":"python","args":["-m","app.mcp_server"],
#                     "env":{"DDB_ENDPOINT":"http://localhost:8931"}}}}' \
#     --strict-mcp-config \
#     --allowedTools mcp__slackops__propose_job mcp__slackops__list_pending \
#     --output-format json
```

### 주의 / 버전 의존
- 도구명 `mcp__<server>__<tool>` 규약과 `--mcp-config`/`--strict-mcp-config` 플래그는 claude CLI
  버전에 따라 차이 가능 — `claude --version` 확인 후 1회 스모크 권장.
- `--allowedTools` 로 **propose/list 만** 허용(직접 실행 도구 없음) — 에이전트는 제안만 한다.

## 캐비엇
- 로컬 데모엔 worker 가 안 떠 있어 제안은 `pending`(또는 seed 의 `awaiting_approval`)에서 정지한다.
  전체 실행 루프(worker→게이트→승인 후 실제 pr push)는 claude + worker 가 필요.
- L2(Execute)/Production/IAM/DB 변경 불변 유지 — `propose_job` 도 permissions default-deny 게이트 안에서만.
- DynamoDB Local 은 in-memory — `docker compose down` 시 데이터 소멸, `up` 시 seed 재주입.
