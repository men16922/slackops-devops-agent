# DevPost Submission — H0 Hackathon ("Hack the Zero Stack with Vercel v0 + AWS Databases")

> 채우는 법: 공개 항목은 영어로 작성했고, **사용자 입력 필요** 표시된 곳(링크/Team ID/파일/국가)만
> 직접 채우면 된다. 길이 제한 항목은 글자수를 맞춰 두었다.

---

## General info

### Project name  (≤60자)
```
SlackOps — One Agent, Two Control Planes
```

### Elevator pitch  (≤200자)
```
One AI ops engineer, two control planes: Slack and a Vercel dashboard drive a least-privilege Claude agent over a shared DynamoDB queue — from read-only diagnosis to human-approved PRs.
```

---

## Project Story — About the project

## Inspiration
Teams increasingly want to let an AI agent *operate* their infrastructure, not just suggest code. But two
fears block it: **over-privilege** (an agent with prod write access) and **prompt injection** (a poisoned
log line or diff hijacking the agent). We wanted to show the opposite of a YOLO bot — a reference design for
running an ops agent *safely*: least privilege, injection defense in depth, and full observability, reachable
from both the office (a web dashboard) and on-call (Slack).

## What it does
SlackOps turns Claude Code (Headless) into a remote operations engineer with **two control planes that share
one DynamoDB job queue**:
- **Slack** (Socket Mode, no inbound port) for on-call / mobile.
- A **Vercel + Next.js dashboard** for the office — both enqueue jobs to the same single-table DynamoDB.

A single EC2 worker polls the queue and runs read-only ops commands:
- `/devops logs <service>` — CloudWatch query + analysis
- `/devops diagnose <service>` — CloudWatch + kubectl + git diff combined diagnosis
- `/devops tf-review` — `terraform plan` risk / cost / security review (never `apply`)
- `/devops pr <desc>` — branch → edit → test → PR, **held at a human-approval gate** before push

Every action is least-privilege (IAM Instance Profile, no static keys), passes a **4-layer injection defense**,
and is fully instrumented (DynamoDB audit + metric records, optional OpenTelemetry spans).

## How we built it
- **Shared state in DynamoDB single-table** (`slackops-agent`): Job / Audit / Metric items under one table
  with GSI1 (status feed) + GSI2 (daily feed). `claim` is an atomic optimistic-lock `UpdateItem`
  (`ConditionExpression`), so two interfaces never double-run a job.
- **Permission engine** — Levels 0 (observe) and 1 (prepare/PR) active; Level 2 (execute) disabled.
  Production / deploy / IAM / DB changes are forbidden invariants.
- **4-layer prompt-injection defense**: (1) Context Sanitizer wraps all untrusted text (logs, diffs, plans)
  in `<untrusted_data>` tags with tag-forgery neutralization; (2) per-command tool allowlist
  (`--allowedTools`); (3) **output gate** — PR writes publish a diff for human approval before push tools
  are even available; (4) template prompts — Slack input is never inserted directly (regex/length-validated).
- **EC2 worker** polls → claims → runs Claude Code Headless → writes back audit + metrics; EventBridge
  schedules start/stop so the instance isn't always on.
- **Observability**: every Claude invocation flows through one entry point that emits duration / tokens / cost
  to a TelemetryStore (DynamoDB) and, when configured, OpenTelemetry spans → ADOT Collector.
- **Frontend**: Next.js on Vercel, server actions reading/writing the same DynamoDB via AWS SDK for JS v3.

## Challenges we ran into
- **Two writers, one truth.** A single-writer SQLite queue can't back two interfaces — DynamoDB single-table
  with conditional-write claims was the design that made "two control planes, one agent" actually correct.
- **Injection is the real attack surface.** Logs and diffs are attacker-influenced; we had to make tag forgery
  (`</untrusted_data>` smuggling) and argv flag injection (a service name like `-A`) structurally impossible,
  not just filtered.
- **Letting an agent write code without letting it merge.** The PR flow is split prepare→approve→execute:
  push / `gh pr create` tools are removed from the allowlist until a human approves the diff.

## Accomplishments that we're proud of
- A working **least-privilege + injection-defended + fully-instrumented** agent backend, verified by a
  **229-test suite (1 skipped), all green under `pytest` + `ruff` + `mypy --strict`** — with zero real AWS,
  Claude, or subprocess calls in tests (everything dependency-injected).
- **One single-table DynamoDB design** serving jobs, audit, and metrics, with Sqlite mirror + moto-verified
  equivalence.
- A self-improving **autonomous overnight loop** that built most of this backend unattended — fresh context
  per iteration, one atomic task → 3-layer test gate → local commit, so a crash/limit loses at most one task.

## What we learned
Safe agent autonomy is an *engineering* problem, not a prompt problem: the leverage is in **verification gates,
isolation boundaries, and human-approval choke points**, not in a cleverer system prompt. Designing for "where
do we stop the agent" turned out to matter more than "what can the agent do."

## What's next for SlackOps
- Level 2 (Execute) behind stricter multi-party approval.
- Richer dashboard: live job feed, cost/latency charts from the metric store.
- More ops commands (k8s rollout review, cost anomaly triage) reusing the same gate + sanitizer.

---

## Built with
`Python 3.11` · `FastAPI` · `Slack Bolt (Socket Mode)` · `Claude Code (Headless)` · **`Amazon DynamoDB`** ·
`Next.js` · **`Vercel`** · `boto3` · `AWS SDK for JavaScript v3` · `OpenTelemetry` / `AWS Distro for OpenTelemetry (ADOT)` ·
`Amazon EC2` · `AWS IAM (Instance Profile)` · `Amazon EventBridge` · `Amazon CloudWatch` · `pytest` · `moto` · `mypy` · `ruff`

---

## Additional info (judges/organizers)

### App Status
**Newly created during the Submission Period.** Backend (permission engine, sanitizer, allowlist,
claude_runner, DynamoDB store layer, worker, telemetry/OTel, tf-review & PR output gate) was built and
verified (229 tests green) during the submission window; frontend deployed to Vercel + DynamoDB provisioned
during the same period.

### Track
**Track 2 — B2B.**

### Database (required)
**Amazon DynamoDB** — single-table (`slackops-agent`): Job + Audit + Metric items, GSI1 (status feed) /
GSI2 (daily feed), atomic conditional-write claim.

### Testing Instructions for the Judges
```sh
git clone <repo> && cd "SlackOps DevOps Agent"
python3 -m pip install -e ".[dev]"
python3 -m pytest tests/ -q          # → 229 passed, 1 skipped
python3 -m ruff check src tests      # → clean
python3 -m mypy src                  # → 0 errors (strict)
```
Tests use injected mocks + `moto` — no real AWS/Slack/Claude calls. The live demo (Slack `/devops ping`
→ EC2 → pong, and the Vercel dashboard reading DynamoDB) is shown in the 3-minute video.

### Published Vercel / v0 Link
**[사용자 입력 필요]** `https://...`  ← v0/Next.js 대시보드 배포 후 채우기

### Vercel Team ID
**[사용자 입력 필요]** `team_xxxxx`

### Architecture diagram (required, file)
**[사용자 입력 필요 — 파일 업로드]** 아래 구조로 작성(png/pdf):
```
Slack (Socket Mode) ─┐
Vercel Next.js ──────┴─→ Amazon DynamoDB (single-table: Job/Audit/Metric, GSI1/GSI2)
                          ▲ poll(GSI)/write-back
            EC2 Agent Worker — Claude Code Headless
            (Permission L0/L1 · Sanitizer · Tool Allowlist · Output Gate · OTel→ADOT)
            IAM Instance Profile (no static keys) · EventBridge start/stop
```

### Screenshot proving AWS database usage (required, file)
**[사용자 입력 필요 — 파일 업로드]** AWS Console 의 DynamoDB `slackops-agent` 테이블(항목/GSI 보이게) 캡처.

### Submitter Type / Country of Residence / Organization
**[사용자 입력 필요]** DevPost 폼에서 직접 선택.

### Optional bonus content (URL)
**[선택]** #H0Hackathon 아티클 — 게시 시 "created for the purposes of entering this hackathon" 문구 포함.
