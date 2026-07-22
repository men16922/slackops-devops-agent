# AGENT_BRIEF — slackops-devops-agent
Last updated: 2026-07-23

> ▶ NEXT SESSION (**v2 AWSKRUG demo**): authority = `docs/NEXT_PLAN.md`.
>   `PRESENTATION.md`이 PPTX **19장**(신규 Slide 3) speaker note와 동기화됨. 인터컷 슬라이드용 데모 mp4 4종 제작 완료:
>   `docs/presentation/assets/videos/slide{7,11,12,16}-*.mp4`(각 8.6s·1920p, **입력→결과**; 결과=실 라이브 캡처, 입력 프레임=PIL 합성).
>   First action: **EC2 stop**(현재 running) + PR job `37d65bc9`(awaiting_approval) 정리 + **미커밋 번들 커밋**(`deploy/demo/*`, Makefile,
>   정책 TC, `LIVE/PRESENTATION.md`, `assets/`). PPT 영상 임베드는 사용자 직접.
>   Live infra 상태: monitor 정지(SSM), 데모 로그 재시딩됨, EC2 750 dirty(리셋해도 committed=750), **Chrome 확장 연결해제**(재캡처 시 재연결 필요).
>   Verification: `make check` **565 passed**(이전); 4개 mp4 <10s·1920p 확인.
>   남은 blocker: Slack terminal-state 잔류, PR prepare ~2분, monitor `diagnose 'api'` denied 스팸(정지시킴), 라이브 타이핑 실녹화는 macOS Space 이슈.
>   Guides: `docs/guide/kr/SLACK_NEW_GUIDE.md`, `docs/V2_INTRO.md`/`V2_TEST.md`.
> 1-minute compact entry point (≤60 lines). Standards in harness/CORE_MANDATES.md; work authority is NEXT_PLAN.md > docs/plans/.

## Read Path (session start/resume)
harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md → docs/STATUS.md → docs/NEXT_PLAN.md
→ (if needed) top of docs/PROGRESS_LOG.md → (if needed) docs/archive/

## Snapshot
- **What:** Slack natural-language command → Claude Code Headless on EC2 analyzes AWS/K8s/Terraform/GitHub context → ops automation.
  MVP = Read-Only analysis + PR creation.
- **Differentiator:** Not just a bot but a reference for "how to run an agent safely" — security (permissions + injection defense) + observability (OTel).
- **Behavior:** command routing + job queue + permission gate + sanitizer + claude_runner + allowlist
  (`run_for_command` single entry) + command_guard (PreToolUse argv schema = the execution boundary) + logs/diagnose/
  detect (fixed read adapters → isolate → assemble) + store/ (H0 single-table Job/Audit/Telemetry, Sqlite+DynamoDb)
  + telemetry + worker (claim→run→output-gate/complete, audit trajectory + capability drift gate) + tf-review
  (plan-isolated, no apply path) + pr (2-stage gate; execute gets a per-approval scoped write grant).
  **web/ dashboard (Next.js)** = jobs feed / detail (diff gate + Approve/Reject) / metrics; DynamoDB Local docker
  (8930) e2e verified; DDB_ENDPOINT toggles real DynamoDB (Vercel) (D7). Inference = subscription OAuth (D6).
  + **agent autonomous proposal (D9)** — mcp_server (propose_job) + agent_monitor; agent proposes → human approval via
  the existing output gate. JobSource.AGENT + Job.rationale. Runbook docs/runbooks/agent-mcp-demo.md.
  + **conversational producer (D10)** — natural-language chat over a DynamoDB conversation bus + chat_agent poller +
  web Chat. Agent inbound = 0 (poll-only) → works on Vercel. Real Claude e2e verified.
- **Verification:** 3-layer gate — `make check` (563 passed) + ruff + mypy (strict) + documentation budget.
  web/ is `next build` + `docker compose up` e2e green. **`make demo`** runs the full local stack (web+DB+chat_agent+worker) in one shot.
- **Current focus:** cloud deploy A–C verified (DynamoDB us-east-1 live, EC2 ping pong, then terminated). Logs/diagnose/detect use fixed read adapters → sanitizer isolation (generic AWS MCP retired). D17/P1/P2 fresh EC2 rehearsal verified role/credential/egress/audit boundaries plus deterministic scope deny before fetch and Worker audit; instance stopped. P3 is local/CI-only separate-account managed-MCP scaffolding, not an enabled AWS integration.

## Guardrails summary (details in CORE_MANDATES)
- Socket Mode only (no inbound port). IAM Instance Profile only (no Access Key).
- Only permission L0/1 active, L2 (Execute) disabled. No Production/deploy/IAM/DB changes.
- 4-layer injection defense: Sanitizer / Tool Allowlist / output gate / Template Prompt.
- EC2 runs on EventBridge schedule (never always-on).

## Slack commands (MVP)
- `/devops ping` — health check
- `/devops logs <service>` — CloudWatch query + analysis
- `/devops diagnose <service>` — CloudWatch + kubectl + git diff combined diagnosis
- `/devops tf-review` — terraform plan risk/cost/security review
- `/devops pr <description>` — branch → modify → test → PR (human-confirmation gate)

## Slash commands (work harness)
- `/sync` — at session start/resume, read only the Read Path and summarize (read-only)
- `/checkpoint` — on work-bundle completion, append PROGRESS_LOG + conditional updates (record-only)
- `/tidy-docs` — when docs bloat, split/compress/consolidate into archive (tidy-only)
