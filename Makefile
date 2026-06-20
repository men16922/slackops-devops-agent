# slackops-devops-agent — Makefile
# overnight 하네스 커밋 게이트 = `make check` (harness-config.gate). 오프라인·결정적 검증만.

.PHONY: check test lint typecheck check-doc-budget smoke-local demo mcp-server agent-monitor worker chat-agent

check: test lint typecheck check-doc-budget   ## 커밋 게이트 (pytest + ruff + mypy + doc-budget)

check-doc-budget: ## entry-doc line caps (context budget — mirrors harness-config budgets)
	@bash harness/check-doc-budget.sh

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

install:       ## 로컬 파이썬 의존성 설치(slack-bolt/fastapi/boto3/… + dev). Slack 앱 실행 전 1회.
	python3 -m pip install -e '.[dev]'
demo:          ## 로컬 데모 풀스택 한 번에 — web+DB(docker) + chat_agent/worker poller (Ctrl-C 정리). 토큰 필요.
	@bash scripts/demo.sh
demo-all:      ## demo + Slack 앱(app.main) 함께 — .env 의 SLACK 토큰 필요(Ctrl-C 전체 종료).
	@WITH_SLACK=1 bash scripts/demo.sh
mcp-server:    ## propose_job MCP 서버(stdio) — 보통 claude --mcp-config 가 자동 기동(수동 점검용)
	$(DEV_ENV) python3 -m app.mcp_server
agent-monitor: ## 에이전트 모니터 1회(Tier1 시뮬레이터). 실제는 `make agent-monitor ARGS=--real`
	$(DEV_ENV) python3 -m app.agent_monitor $(ARGS)
demo-incident: ## mock 장애 신호 주입 → Tier1 규칙이 제안 적재. 신호 지정: `make demo-incident SIGNAL="..."`
	@echo "$${SIGNAL:-service=checkout-service ALB 504 error rate 23%, upstream gateway timeout, OOMKilled x2}" > /tmp/slackops-incident.txt
	@echo "demo-incident: 신호 주입 → $$(cat /tmp/slackops-incident.txt)"
	$(DEV_ENV) python3 -m app.agent_monitor --signals-file /tmp/slackops-incident.txt $(ARGS)
worker:        ## 공유 큐 폴링 worker(승인된 job 실행 — 실 Claude). 1건만: `make worker ARGS=--once`
	$(DEV_ENV) python3 -m app.worker $(ARGS)
chat-agent:    ## 대화 버스 폴링 에이전트(Claude 스트리밍 응답 — 실 Claude). 1건만: `make chat-agent ARGS=--once`
	$(DEV_ENV) python3 -m app.chat_agent $(ARGS)
slack:         ## Slack 앱(app.main) 로컬 기동 — .env 자동 로드(토큰). 먼저 web 스택(make demo/docker) 띄워두기.
	$(DEV_ENV) bash -c 'set -a; [ -f .env ] && . ./.env; set +a; exec python3 -m app.main'

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
