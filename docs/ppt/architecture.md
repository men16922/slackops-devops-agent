# Architecture diagram (source)

> Submission diagram source. Render the Mermaid block to PNG at [mermaid.live](https://mermaid.live)
> (or `mmdc -i architecture.md -o architecture.png`) → save as `docs/images/architecture.png`.
> ASCII fallback below. Reflects the safe-autonomy loop (F1–F5) on one DynamoDB single-table.

## Mermaid

```mermaid
flowchart TB
  subgraph CP["Control planes (dual)"]
    SL["💬 Slack — Socket Mode<br/>no inbound port"]
    WEB["🖥️ Web dashboard — Next.js / Vercel<br/>🔔 bell · Detections menu · approval gate"]
  end

  subgraph DDB["🗄️ DynamoDB single-table — slackops-agent"]
    Q["Job queue<br/>conditional write = atomic claim + optimistic-lock approval"]
    G["GSI2: FEED / AUDIT / METRIC"]
    CFG["CONFIG#detections (toggles)"]
  end

  subgraph EC2["⚙️ EC2 agent — IAM Instance Profile (no stored keys) · systemd"]
    MON["agent_monitor (resident --loop)"]
    NOTIF["proposal notifier (thread in slack app)"]
    WK["worker (claim → execute)"]
    CA["chat_agent (streaming)"]
    CC["🤖 Claude Code Headless<br/>+ AWS API MCP (READ_OPERATIONS_ONLY)"]
  end

  SL <-->|propose / results| Q
  WEB <-->|poll / approve| Q
  WEB -->|toggle| CFG
  CFG -->|enabled+scheduled| MON
  MON -->|detect signal / scan → propose| Q
  CA -->|chat → propose| Q
  Q -->|new agent proposal| NOTIF -->|ping| SL
  Q -->|claim pending/approved| WK --> CC
  CC -->|read-only| AWS["☁️ AWS: CloudWatch · Config · Access Analyzer · SSM"]
  WK -.->|L1 pr: diff → human approve → push| GH["🐙 GitHub PR<br/>branch protection"]

  classDef gate fill:#1a2030,stroke:#3fb950,color:#e6e9ef;
  class Q,WEB gate;
```

## ASCII fallback

```
        ┌──────────────── Dual control plane ────────────────┐
        │  💬 Slack (Socket Mode, no inbound)   🖥️ Web/Vercel │
        │        ▲    │                          ▲   │        │
        └────────┼────┼──────────────────────────┼───┼────────┘
   Slack ping ── │    │ propose/results   poll/approve  │ toggle
        ┌────────┴────▼──────────────────────────▼───▼────────┐
        │   🗄️ DynamoDB single-table  (slackops-agent)         │
        │   queue: conditional write = atomic claim +          │
        │          optimistic-lock approval  ·  no coordinator │
        │   GSI2: FEED/AUDIT/METRIC   ·   CONFIG#detections     │
        └───▲────────────────▲───────────────────┬─────────────┘
   propose  │  enabled+sched  │ claim pending/approved
        ┌───┴────────────────┴───────────────────▼─────────────┐
        │ ⚙️ EC2 (IAM Instance Profile, systemd)                │
        │ agent_monitor → propose   notifier → Slack ping       │
        │ chat_agent → propose      worker → execute            │
        │ 🤖 Claude Code Headless + AWS API MCP (read-only) ─────┼──► ☁️ CloudWatch/Config/
        │ worker ─ L1 pr: diff→approve→push ─► 🐙 GitHub PR      │     AccessAnalyzer/SSM
        └──────────────────────────────────────────────────────┘
```

## Safety invariants (annotate on the diagram)
- **Socket Mode** = no inbound port / public endpoint.
- **IAM Instance Profile** = zero stored access keys; AWS MCP `READ_OPERATIONS_ONLY` → writes denied.
- **Permission L0/L1 only**; L2(Execute)/prod/IAM/DB = forbidden invariant.
- **Output gate**: L1 (pr) stops at `awaiting_approval` → human approves diff → push/PR (branch protection blocks auto-merge).
- **Injection defense (4-layer)**: untrusted-data isolation · tool allowlist · output gate · template prompt.

## The loop (highlight in the deck)
`monitor/chat detect → propose (queue) → 🔔 Slack ping + dashboard bell → human reads rationale → approval gate → worker executes → telemetry` — all over **one** DynamoDB table.
