# slackops-devops-agent — Makefile
# overnight 하네스 커밋 게이트 = `make check` (harness-config.gate). 오프라인·결정적 검증만.

.PHONY: check test lint typecheck smoke-local

check: test lint typecheck   ## 커밋 게이트 3계층 (pytest + ruff + mypy)

test:        ## pytest 전체
	python3 -m pytest tests/ -q
lint:        ## ruff
	python3 -m ruff check src tests
typecheck:   ## mypy (strict)
	python3 -m mypy src
smoke-local: ## 빠른 스모크(overnight-seed 용) — pytest 전체(현재 ~2s)
	python3 -m pytest tests/ -q

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
