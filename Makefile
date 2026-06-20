# slackops-devops-agent — Makefile
# overnight 하네스 커밋 게이트 = `make check` (harness-config.gate). 오프라인·결정적 검증만.

.PHONY: check test lint typecheck check-doc-budget smoke-local demo mcp-server agent-monitor worker chat-agent
.PHONY: cloud-whoami cloud-iam cloud-ddb cloud-up cloud-deploy cloud-status cloud-console cloud-ssm cloud-schedule cloud-start cloud-stop cloud-down
.PHONY: cloud-lambda-deploy cloud-lambda-clean cloud-alarm cloud-alarm-clean

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
demo-incident: ## (로컬) mock 장애 신호 주입 → Tier1 규칙이 제안 적재. 신호 지정: `make demo-incident SIGNAL="..."`
	@echo "$${SIGNAL:-service=checkout-service ALB 504 error rate 23%, upstream gateway timeout, OOMKilled x2}" > /tmp/slackops-incident.txt
	@echo "demo-incident: 신호 주입 → $$(cat /tmp/slackops-incident.txt)"
	$(DEV_ENV) python3 -m app.agent_monitor --signals-file /tmp/slackops-incident.txt $(ARGS)
cloud-lambda-deploy: ## (클라우드) 이벤트 구동 producer 배포 — EventBridge rule + Lambda(CloudWatch ALARM→큐 제안). cloud-alarm 선행.
	@AWS_REGION=$${AWS_REGION:-us-east-1} bash deploy/lambda/deploy.sh
cloud-lambda-clean:  ## (클라우드) 이벤트 구동 producer 정리 — rule/Lambda/role 삭제.
	@AWS_REGION=$${AWS_REGION:-us-east-1} bash deploy/lambda/clean.sh
cloud-alarm:   ## (클라우드) 실 CloudWatch alarm 강제 ALARM → **EventBridge→Lambda** 실시간 제안(실 DynamoDB). cloud-lambda-deploy 선행.
	@bash scripts/cloud-alarm.sh
cloud-alarm-clean: ## (클라우드) 데모 alarm 삭제(비용 정리). 이벤트 경로는 cloud-lambda-clean.
	aws cloudwatch delete-alarms --alarm-names "$${ALARM_NAME:-slackops-demo-checkout-5xx}"

# ===== cloud 배포 라이프사이클 (실 AWS) — deploy/*.sh 래퍼. 실 자격증명 필요(aws sts get-caller-identity) =====
# 인프라 순서 고정: IAM → DynamoDB → EC2 (deploy-checklist.md [B]). EC2 인스턴스 ID 는 ID_FILE 에 기록 →
# 이후 cloud-status/console/ssm/stop/down 이 읽는다. 캡처 체크리스트: docs/test/0620-qa-test.md.
CLOUD_REGION  ?= us-east-1
ID_FILE       := deploy/.instance-id
AWSC          := AWS_REGION=$(CLOUD_REGION) AWS_DEFAULT_REGION=$(CLOUD_REGION) aws
# 저장된 인스턴스 ID 를 읽고 없으면 명확히 실패시키는 가드(파괴적 타깃에서 빈 인자 방지).
NEED_ID        = ID="$$(cat $(ID_FILE) 2>/dev/null)"; [ -n "$$ID" ] || { echo "no instance id — run 'make cloud-up' first"; exit 1; }

cloud-whoami:  ## 현재 AWS 자격증명/계정/리전 확인(배포 전 점검).
	@$(AWSC) sts get-caller-identity --output table && echo "region=$(CLOUD_REGION)"
cloud-iam:     ## (인프라 1/3) IAM role+instance-profile 생성. 멱등 아님 — 이미 있으면 EntityAlreadyExists(정상 스킵).
	@( cd deploy/iam && ./create-role.sh ) || echo "cloud-iam: 이미 존재할 수 있음(EntityAlreadyExists) — 계속 진행 가능"
cloud-ddb:     ## (인프라 2/3) DynamoDB 단일테이블(slackops-agent, PAY_PER_REQUEST, GSI1/2). 멱등(있으면 생략).
	( cd deploy/dynamodb && AWS_REGION=$(CLOUD_REGION) ./create-table.sh )
cloud-up:      ## (인프라 3/3) EC2 기동(t3.medium·인바운드0·systemd 4개) → ID 기록 + running 대기. INSTANCE_TYPE 오버라이드 가능.
	@INSTANCE_ID="$$( cd deploy/ec2 && AWS_REGION=$(CLOUD_REGION) ./launch-instance.sh )"; \
	  echo "$$INSTANCE_ID" > $(ID_FILE); \
	  echo "launched: $$INSTANCE_ID → $(ID_FILE)"; echo "waiting instance-running..."; \
	  $(AWSC) ec2 wait instance-running --instance-ids "$$INSTANCE_ID"; \
	  echo "running. 부팅/설치 로그: make cloud-console (수 분 후), 접속: make cloud-ssm"
cloud-deploy: cloud-iam cloud-ddb cloud-up   ## 인프라 전체 한 번에(IAM→DDB→EC2). 멱등 부분만 안전 재실행.
cloud-status:  ## EC2 상태/타입/AZ 출력.
	@$(NEED_ID); $(AWSC) ec2 describe-instances --instance-ids "$$ID" \
	  --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name,Type:InstanceType,AZ:Placement.AvailabilityZone}' --output table
cloud-console: ## EC2 시리얼 콘솔 출력 마지막 40줄(부팅/cloud-init/설치 디버그).
	@$(NEED_ID); $(AWSC) ec2 get-console-output --instance-id "$$ID" --query Output --output text | tail -40
cloud-ssm:     ## SSM Session Manager 접속(인바운드0 유지 — SSH 대신). 안에서 `systemctl status` 로 4개 유닛 확인.
	@$(NEED_ID); $(AWSC) ssm start-session --target "$$ID"
cloud-schedule: ## EventBridge stop/start 스케줄(평일 09–19 Asia/Seoul) 생성 — 상시 가동 금지 불변.
	@$(NEED_ID); ( cd deploy/eventbridge && AWS_REGION=$(CLOUD_REGION) ./create-schedules.sh "$$ID" )
cloud-start:   ## 중지된 EC2 재가동.
	@$(NEED_ID); $(AWSC) ec2 start-instances --instance-ids "$$ID"
cloud-stop:    ## EC2 stop(캡처 후 비용 절약). DynamoDB/Vercel 은 유지(idle ~$0).
	@$(NEED_ID); $(AWSC) ec2 stop-instances --instance-ids "$$ID"
cloud-down:    ## EC2 terminate(완전 삭제) + ID 파일 제거. (DynamoDB/IAM 정리는 deploy-checklist 부록2)
	@$(NEED_ID); $(AWSC) ec2 terminate-instances --instance-ids "$$ID" && rm -f $(ID_FILE) && echo "terminated + $(ID_FILE) 제거"
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
