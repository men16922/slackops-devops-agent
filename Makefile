# slackops-devops-agent — Makefile
# overnight 하네스 커밋 게이트 = `make check` (harness-config.gate). 오프라인·결정적 검증만.

.PHONY: check test lint typecheck smoke-local mcp-server agent-monitor

check: test lint typecheck   ## 커밋 게이트 3계층 (pytest + ruff + mypy)

test:        ## pytest 전체
	python3 -m pytest tests/ -q
lint:        ## ruff
	python3 -m ruff check src tests
typecheck:   ## mypy (strict)
	python3 -m mypy src
smoke-local: ## 빠른 스모크(overnight-seed 용) — pytest 전체(현재 ~2s)
	python3 -m pytest tests/ -q

# ===== 운영 에이전트 (MCP 제안 루프) =====
# DDB_ENDPOINT 로 DynamoDB Local 연결(docker compose 의 dynamodb-local 8931). 런북: docs/runbooks/agent-mcp-demo.md
mcp-server:    ## propose_job MCP 서버(stdio) — 보통 claude --mcp-config 가 자동 기동(수동 점검용)
	DDB_ENDPOINT=$${DDB_ENDPOINT:-http://localhost:8931} python3 -m app.mcp_server
agent-monitor: ## 에이전트 모니터 1회(Tier1 시뮬레이터). 실제는 `python3 -m app.agent_monitor --real`
	DDB_ENDPOINT=$${DDB_ENDPOINT:-http://localhost:8931} python3 -m app.agent_monitor

# ===== overnight harness targets (scripts/overnight/Makefile.harness.snippet) =====
OVN := scripts/overnight

overnight:           ## run the unattended loop (caffeinate keeps macOS awake)
	caffeinate -dimsu $(OVN)/run.sh &
overnight-watch: overnight ## start the loop and tail its log
	@sleep 1; tail -f $(OVN)/logs/runner.log
overnight-once:      ## single iteration (smoke test the loop)
	$(OVN)/run.sh --once
overnight-stop:      ## graceful stop after the current iteration
	@touch $(OVN)/STOP && echo "STOP created — loop will exit after current iteration"
overnight-clean:     ## clear STOP/DONE sentinels before the next run
	@rm -f $(OVN)/STOP $(OVN)/DONE && echo "cleared STOP/DONE"
overnight-status:    ## aggregate iteration status across lanes
	@bash $(OVN)/status.sh
overnight-logs:      ## tail the runner log
	@tail -f $(OVN)/logs/runner.log
overnight-dashboard: ## tmux dashboard (falls back to status.sh)
	@bash $(OVN)/dashboard.sh

.PHONY: overnight overnight-watch overnight-once overnight-stop overnight-clean overnight-status overnight-logs overnight-dashboard
# ===== end overnight harness targets =====
