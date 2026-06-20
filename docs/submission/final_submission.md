# Project overview
## General info
### Project Name
```
SlackOps — One Agent, Two Control Planes
```

### Elevator Pitch
```
One AI ops engineer, two control planes: Slack and a Vercel dashboard drive a least-privilege Claude agent over a shared DynamoDB queue — from read-only diagnosis to human-approved PRs, plus real-time alarm-to-proposal autonomy.
```

# Project detail
## Project Story
### About the project
Be sure to write what inspired you, what you learned, how you built your project, and the challenges you faced. Format your story in Markdown, with LaTeX support for math.


```
Inspiration

Teams want AI agents to operate infrastructure, but two concerns block adoption: over-privilege and prompt injection. Instead of building a "YOLO bot," we built a safe reference architecture — least privilege, defense-in-depth, and a human approval gate. The agent proposes and alerts; a human holds the boundary.

What it does

SlackOps turns Claude Code (Headless) into a remote DevOps engineer.

Two human control planes share a single DynamoDB job queue:
* Slack (Socket Mode) for on-call
* Next.js dashboard on Vercel for office workflows

Commands:
* /devops diagnose — root-cause analysis from real CloudWatch (via an agentic AWS API MCP, read-only)
* /devops logs — CloudWatch analysis
* /devops tf-review — Terraform risk/cost/security review (never apply)
* /devops pr — prepare code change + PR, human approval required before push

Event-driven autonomy (real-time): a real CloudWatch alarm fires an EventBridge rule that invokes a Lambda producer. The Lambda runs a deterministic detector and writes a PENDING proposal into the same DynamoDB queue — serverless, so detection fires even when the EC2 worker is stopped. A Slack ping + dashboard bell light up, a human reads the rationale and approves the diff, and only then does the worker (Claude) execute. A "done" notification with cost/tokens closes the loop.

How we built it

* DynamoDB single-table design (PK JOB#…, SK overloaded META / AUDIT#… / METRIC#…; GSIs for FEED/AUDIT/METRIC) — the table is the coordination + governance control plane, not just storage.
* EC2 worker running Claude Code Headless; AWS access via an agentic AWS API MCP with READ_OPERATIONS_ONLY.
* IAM Instance Profile (no static keys on EC2).
* Event-driven producer: EventBridge rule (CloudWatch "Alarm State Change") → Lambda, reusing the same detect()+propose logic as the resident agent.
* Next.js dashboard on Vercel reading the same DynamoDB table (TS contract mirrors the Python store).
* Four-layer prompt-injection defense: context sanitizer (untrusted-data isolation), tool allowlist, output approval gate, template prompts with validated input.

Every execution is audited and emits telemetry (latency / tokens / cost(USD) / tool-calls), with OpenTelemetry instrumentation.

Challenges we ran into

* Coordinating two interfaces safely required atomic DynamoDB job claiming + an optimistic-lock approval gate (duplicate approvals are rejected).
* Prompt injection is the real attack surface, so logs/diffs/alarm reasons are treated as untrusted input; the Lambda detector is deterministic so an alarm message can never inject a command.
* "What does a healthy deployed agent even detect?" We reframed: we are not a new monitor, but the triage/safe-response layer on top of signals you already have. Wiring the alarm path event-driven (a real alarm state-change wakes the agent) made the autonomy honest.

Accomplishments that we're proud of

* A least-privilege, injection-defended DevOps agent with a human approval gate.
* 316 automated tests passing (ruff + mypy strict green); zero real AWS/Claude calls in tests via dependency injection.
* Full event-driven loop verified live: CloudWatch ALARM → EventBridge → Lambda → DynamoDB → worker (Claude) → DONE → Slack, at ~$0.15 / run.
* A public Vercel dashboard reading the real production table.

What we learned

Safe AI autonomy is more about engineering controls than prompt engineering — verification gates, isolation boundaries, and human approval checkpoints matter more than a smarter prompt.

What's next

* Level 2 (Execute) with multi-party approval
* ADOT live numbers (CloudWatch EMF + X-Ray)
* IAM Access Analyzer / Security Hub governance categories
* L1 remediation PRs auto-drafted from findings (still human-gated)
```

* Built with
```
python, fastapi, slack, claude, amazon-dynamodb, next.js, vercel, ec2, amazon-cloudwatch, amazon-eventbridge, aws-lambda, aws-iam, opentelemetry, mcp
```

* "Try it out" links
```
https://slackops-devops-agent.vercel.app/
https://github.com/men16922/slackops-devops-agent
```

## Project Media
* Image gallery
```
docs/submission/architecture.png — architecture diagram
docs/submission/items.png — DynamoDB single-table (Job/Audit/Metric + per-run cost)
docs/submission/tables.png — DynamoDB table (Active, On-demand)
```

## Video demo link
```
TODO — YouTube (<3 min)
```

# Additional info
Unless noted, additional info is for judges and hackathon organizers and will not appear on your public project page.

## Upload a File
```
docs/submission/architecture.png
```

* Submitter Type
    -   individual

## Testing Instructions for the Judges (if applicable)
This question will not be shown publicly, only to Devpost and Judges.
```
Live dashboard: https://slackops-devops-agent.vercel.app/ — reads the real DynamoDB table (slackops-agent, us-east-1) and shows real diagnose Jobs, the approval gate (Output Gate diff + Approve/Reject), audit timeline, and per-run cost/token metrics.

The Slack agent runs on EC2, which is kept stopped between sessions to save cost. For a live Slack demo (/devops diagnose → real CloudWatch + write-denied), please request it and we will bring the instance up (~5 min). The 3-min video shows the full event-driven loop end to end.

Security boundary (visible in the demo): IAM Instance Profile (no stored keys), AWS API MCP READ_OPERATIONS_ONLY (write ops return "denied by security policy"), Socket Mode (no inbound port), 4-layer prompt-injection defense, permission L0/L1 only.
```

* Published Vercel/v0 Link
```
https://slackops-devops-agent.vercel.app/
```
* Vercel Team ID
```
team_Exh42D0O6q3f4xJA4j8lbv2P
```

* Which database did you use?
Regardless of track, all projects must use one of three designated Amazon Web Services databases (Amazon Aurora, Amazon Aurora DSQL, or Amazon DynamoDB) as the primary back end and deploy their front end on Vercel or v0.app. — Appears in project gallery
```
Amazon DynamoDB. Slack, the Vercel dashboard, the resident agent, and an event-driven Lambda are four producers that share one job queue: a DynamoDB conditional write gives atomic job claim + an optimistic-lock approval gate without a separate coordinator. A single-table design serves FEED/AUDIT/METRIC over GSIs plus detection config — the table is the coordination + governance control plane.
```

* Architecture diagram (required)
```
docs/submission/architecture.png
```

* Upload a screenshot proving your aws database usage
```
docs/submission/items.png
```

* URL(s) to your OPTIONAL content for Bonus Points
You must include language that says you created the piece of content for the purposes of entering this hackathon. When sharing on social media, use the hashtag #H0Hackathon.

```
TODO — article (dev.to / Medium / LinkedIn), published before Jun 30, includes "created for the #H0Hackathon".
```
