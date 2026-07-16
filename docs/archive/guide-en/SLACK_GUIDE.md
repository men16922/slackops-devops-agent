# SLACK_GUIDE — Slack DevOps Agent Operations Guide

> **Target Audience:** The operator **deploying and running** the agent backend (EC2).
> Web dashboard guide is in [DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md), manual verification pending items are in [QA_TEST.md](QA_TEST.md), and AWS infrastructure steps & current status are in `docs/runbooks/deploy-checklist.md` (authoritative).

---

## 0. Overview / Security Principles (Read First)
Slack natural language command → Claude Code Headless on EC2 processes via safety gates, analyzing/automating with AWS/K8s/Terraform/GitHub context. MVP = **Read-Only Analysis + PR Creation**.

- **EC2 runtime never uses AWS Access Keys** — relies entirely on IAM Instance Profile (`deploy/ec2/user-data.sh`).
- **Socket Mode only** — inbound port 0 (no public endpoints). Agent only performs outbound polling.
- **Do not commit tokens/keys to git/code** — operational tokens SSM SecureString is the source of truth.
- **Permission Gates** — Only Level 0 (observe) and Level 1 (prepare/PR) are active. Level 2 (execute)/prod/IAM/DB changes are **immutably banned**.
- **4 Layers of Injection Defense** — Sanitizer (untrusted isolation) / Tool Allowlist / Output Gate (human approval for diffs) / Template Prompt.

---

## 1. Slack Commands (MVP)
After inviting the app to your channel (`/invite @slackops-devops-agent`):

| Command | Behavior | Level |
| --- | --- | --- |
| `/devops ping` | Health check → `pong` | L0 |
| `/devops logs <service>` | CloudWatch query + analysis (AWS API MCP) | L0 |
| `/devops diagnose <service>` | Comprehensive diagnosis using CloudWatch + kubectl + git diff | L0 |
| `/devops tf-review` | Risk/cost/security review of terraform plan (no apply path) | L1 |
| `/devops pr <description>` | Branch → modify → test → PR (**requires human approval for diff**) | L1 |

> Level 0 (`diagnose`/`logs`) executes immediately. Level 1 (`pr`) posts the diff to Slack first, and pushes/creates PR **only after human approval**.

---

## 2. Secrets — What and Where
| Secret | Usage | Storage | Issuance |
| --- | --- | --- | --- |
| `SLACK_BOT_TOKEN` (`xoxb-…`) | Slack Bot | **SSM** `/slackops/SLACK_BOT_TOKEN` | Slack App → OAuth |
| `SLACK_APP_TOKEN` (`xapp-…`) | Socket Mode | **SSM** `/slackops/SLACK_APP_TOKEN` | Slack App → App-Level Token |
| `CLAUDE_CODE_OAUTH_TOKEN` (`sk-ant-oat…`) | Claude inference (subscription) | **SSM** `/slackops/CLAUDE_CODE_OAUTH_TOKEN` | `claude setup-token` |
| AWS Credentials (EC2 runtime) | AWS/DynamoDB access | **None** — IAM Instance Profile | `deploy/iam/create-role.sh` |

### 2.1 Slack Tokens (SSM)
After creating the Slack App (Socket Mode):
```sh
aws ssm put-parameter --name /slackops/SLACK_BOT_TOKEN --type SecureString --value 'xoxb-...'
aws ssm put-parameter --name /slackops/SLACK_APP_TOKEN --type SecureString --value 'xapp-...'
```
EC2 boots and automatically loads these into `/etc/slackops-devops-agent.env` (root 600) via `user-data.sh`.

### 2.2 Claude Subscription Token (SSM)
Attribute inference costs to the **subscription account** (separated from AWS credits). Do not put `ANTHROPIC_API_KEY` on EC2 (prevents API billing paths).
```sh
claude setup-token                                  # Subscription login → prints sk-ant-oat...
aws ssm put-parameter --name /slackops/CLAUDE_CODE_OAUTH_TOKEN --type SecureString --value 'sk-ant-oat...'
```
- Upon expiration/auth failure: re-generate → update SSM → `sudo systemctl restart slackops-devops-agent`.

---

## 3. Deployment Steps (Summary)
Refer to **`docs/runbooks/deploy-checklist.md` (authoritative)** for execution order, current status, and validation checkboxes. Summary:

1. Slack App creation + SSM tokens (§2.1·§2.2)
2. `deploy/iam/create-role.sh` — IAM Role + Instance Profile (**strict ordering**: needs Profile access to DynamoDB/SSM at boot)
3. `deploy/dynamodb/create-table.sh` — DynamoDB single-table (on-demand)
4. `deploy/ec2/launch-instance.sh` — Boot EC2 (user-data sets up toolchain + registers 3 systemd services: slack app, worker, chat-agent)
5. `deploy/eventbridge/create-schedules.sh <instance-id>` — stop/start schedules (do not run continuously)
6. `/devops ping` → `pong` e2e verification

> ⚠️ Cloning private repo: user-data's `git clone` has no authentication → Choose one of: **public repo transition** (simplest for demo), SSM PAT, or deploy keys.

---

## 4. e2e Verification — `/devops ping`
Connect via **SSM Session Manager** instead of SSH (maintaining inbound port 0): `aws ssm start-session --target "$INSTANCE_ID"`.
```sh
systemctl status slackops-devops-agent slackops-devops-agent-worker slackops-devops-agent-chat-agent  # 3 active services
curl 127.0.0.1:8080/health        # {"status":"ok"}
```
In Slack, `/devops ping` → `:white_check_mark: pong … on ip-…ec2.internal` confirms cloud round-trip success.

| Symptom | Diagnosis |
| --- | --- |
| `/devops ping` no response | `journalctl -u slackops-devops-agent -n 50` — Socket connection/token loading failed? Check SSM name and decryption permission. |
| Service boot failed | Private repo clone auth issue — check console output using `get-console-output`. |
| DynamoDB AccessDenied | Instance Profile policy + check table name and region matching. |
| SSM decryption failed | KMS default key permissions + `ssm:GetParameter` + `--with-decryption`. |
| Cannot access EC2 | Inbound 0 is normal — connect via SSM Session Manager instead of SSH. |

---

## 5. Cost Saving / Cleanup
Do not run continuously. Stopping immediately after demos/captures is highly recommended (c7i.large 24h ≈ $2.16, weekdays 10h ≈ $0.9 — see `deploy-checklist.md` Appendix 2).
```sh
aws ec2 stop-instances      --instance-ids "$INSTANCE_ID"   # Stop during evaluation, start when needed
aws ec2 terminate-instances --instance-ids "$INSTANCE_ID"   # Terminate completely
aws dynamodb delete-table   --table-name slackops-agent     # Delete table (almost $0 if idle anyway)
```
- Claude inference cost is not billed to AWS (charged to subscription token) → not in AWS invoice.
- During evaluation (post-submission): EC2 stopped, DynamoDB/Vercel kept active (idle cost ~$0, keeping dashboard link alive).
