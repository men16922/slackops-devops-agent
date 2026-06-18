# slackops-devops-agent — Makefile
# overnight 하네스 커밋 게이트 = `make check` (harness-config.gate). 오프라인·결정적 검증만.

.PHONY: check test lint typecheck smoke-local demo mcp-server agent-monitor worker chat-agent quarkify-setup quarkify quarkify-check

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
# 공통 로컬 env: src 를 import 경로에(루트에서 `python -m app.*` 가능) + DynamoDB Local 더미 자격증명.
DEV_ENV := PYTHONPATH=src DDB_ENDPOINT=$${DDB_ENDPOINT:-http://localhost:8931} \
	AWS_REGION=$${AWS_REGION:-us-east-1} \
	AWS_ACCESS_KEY_ID=$${AWS_ACCESS_KEY_ID:-local} AWS_SECRET_ACCESS_KEY=$${AWS_SECRET_ACCESS_KEY:-local}

demo:          ## 로컬 데모 풀스택 한 번에 — web+DB(docker) + chat_agent/worker poller (Ctrl-C 정리). 토큰 필요.
	@bash scripts/demo.sh
mcp-server:    ## propose_job MCP 서버(stdio) — 보통 claude --mcp-config 가 자동 기동(수동 점검용)
	$(DEV_ENV) python3 -m app.mcp_server
agent-monitor: ## 에이전트 모니터 1회(Tier1 시뮬레이터). 실제는 `make agent-monitor ARGS=--real`
	$(DEV_ENV) python3 -m app.agent_monitor $(ARGS)
worker:        ## 공유 큐 폴링 worker(승인된 job 실행 — 실 Claude). 1건만: `make worker ARGS=--once`
	$(DEV_ENV) python3 -m app.worker $(ARGS)
chat-agent:    ## 대화 버스 폴링 에이전트(Claude 스트리밍 응답 — 실 Claude). 1건만: `make chat-agent ARGS=--once`
	$(DEV_ENV) python3 -m app.chat_agent $(ARGS)

# ===== Quarkify (선택적 탐색 가속 — gitignore 생성물, 게이트 아님) =====
# 코드 심볼·호출그래프 인덱스. make check 에 절대 미포함(부재 산출물의 빌드의존화 금지).
# 정책: 대형·고빈도 심볼은 인덱스 우선, 드문 리터럴은 grep. 상세 CLAUDE.md "## Quarkify".
quarkify-setup:   ## one-time: clone the pinned Quarkify tool (zero deps, no npm)
	@bash tools/quarkify/setup.sh
quarkify:         ## regenerate whole-src code topology → .quarkify/src (fast)
	@bash tools/quarkify/generate.sh
quarkify-check:   ## .quarkify/src 신선도 검사(비차단; stale면 make quarkify 안내). make check 미포함
	@bash harness/check-quarkify.sh --check

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
