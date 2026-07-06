# VERIFICATION_ENGINEERING — What Proves a Commit Is Good (Bible)

> **General Conceptual Document (Bible).** Not bound to a specific repository. For this repository's application (gate, critic, manual boundary) see → [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md).

## Definition
A verification strategy that splits "is this change actually good?" into **three layers by what kind of judgment each requires** — mechanical, semantic, and creative — so that the unattended loop can keep everything a machine or a read-only reviewer can decide, and surface to a human **only** what genuinely needs human judgment. One-line principle: **Automate every check that does not need taste; reserve the human queue for the checks that do.**

This is the organizing axis behind `HARNESS_ENGINEERING §3`'s L1–L5 layers: L1–L3 are *mechanical*, L4 is *semantic*, L5/`[manual]` is *creative*. This bible names the three judgment classes, states what each can and cannot catch, and defines how they compose into the loop's keep/revert decision.

## 1. The Three Layers
| Layer | Who judges | Mechanism | Catches | Cannot catch |
| --- | --- | --- | --- | --- |
| **Mechanical** | Deterministic machine | Offline commit gate (lint + typecheck + build + test), re-run **externally** after each commit | Compile/type errors, failing tests, lint/format, forbidden patterns, contract-test breaks | Anything no test exercises; "passes but wrong"; scope creep; weakened tests |
| **Semantic** | Read-only LLM (critic) | Independent review of the committed diff, no edits | Regressions behind a green gate, scope-creep beyond the task, test subversion (deleted/skipped/loosened), dead-code masking | Subjective quality; aesthetic/balance/UX feel; whether the *idea* is right |
| **Creative** | Human | `[manual]` backlog tag + morning review (`/overnight-report`) | Taste, game balance, UX/visual feel, product/judgment calls, strategy | (nothing automatable — this is the residue by design) |

The layers are a **filter cascade**: mechanical is cheapest and runs always; semantic runs on top (opt-in, risk-gated); creative is the human residue. Each layer removes work the next would otherwise have to do — the goal is to shrink the human queue to only what is irreducibly human.

## 2. Composition in the Loop (keep / revert)
The runner composes the two automatable layers into a single keep-or-revert decision per commit:
```
agent commits  →  external re-gate (mechanical)
                    ├─ RED  → phantom-success: revert, count as failure
                    └─ GREEN → critic (semantic, if enabled)
                                 ├─ FAIL → revert, count as failure
                                 └─ PASS → commit verified, kept
```
- **Mechanical is a hard gate, not a soft signal.** An agent reporting success (`is_error:false`) is *not* proof; the gate is re-run externally at the new commit. A RED here is a **phantom-success** → reverted.
- **Semantic is fail-closed on clear evidence, fail-open on doubt.** The critic reverts only on concrete evidence of a failure mode; an unparseable/uncertain verdict defaults to PASS (the gate already passed — a parse glitch must not discard good work).
- **Creative never blocks the loop.** Work needing taste is *not* in the `[auto]` backlog at all; it is tagged `[manual]` and routed to a human, never gated automatically.

## 3. Per-Project Specialization
Every project tunes all three layers; this is what makes the harness fit a specific codebase:
| Layer | Specialization point | Example |
| --- | --- | --- |
| Mechanical | `gate` command (`harness-config.json`) | `make check` vs `npm test && npm run typecheck` |
| Semantic | `scripts/overnight/CRITIC_PROMPT.md` (per-repo override) + `OVERNIGHT_CRITIC=auto\|1` | "Balance constants must not change without a `[manual]` flag"; "API response contract is invariant" |
| Creative | `[manual]` criteria + morning-review focus (`INTERPRETATION`) | "Any change touching difficulty curves needs human playtest" |

Default semantic critic is generic (regression/scope/subversion/masking). The leverage is **domain invariants**: encode the project-specific "green but wrong" failure modes a generic reviewer would miss into a per-repo `CRITIC_PROMPT.md` (copy `CRITIC_PROMPT.example.md` to activate). Start `OVERNIGHT_CRITIC=auto` (risk-gated, near-zero cost on hygiene commits) and escalate to `1` for high-stakes repos.

## 4. Principles
- **Push work down the cascade.** If a "green but wrong" failure recurs, first try to make it *mechanical* (a regression test) — a deterministic gate beats a probabilistic critic. Only encode it in the critic if no test can express it. Only leave it `[manual]` if no machine and no read-only reviewer can decide it. (Mirrors `HARNESS_ENGINEERING §2`'s feedback ladder.)
- **Thin `[auto]` backlog is a signal, not a bug.** In aesthetic/subjective projects the creative residue dominates; the `[auto]` queue depletes fast and the loop stops with no progress. That is correct — do not lower the bar to manufacture `[auto]` work.
- **Semantic verification is conservative by contract.** A wrongly-reverted good commit costs an iteration and erodes trust. The critic defaults to PASS; it earns a FAIL only with concrete diff evidence.
- **Name what fails where.** Each layer must make its verdict legible (gate log, `critic-N.log`, review checklist) so a human can see *which* layer rejected and why.

## 5. Non-Goals (Scope Boundary)
These belong to the **host/operator**, not the verification layers or this plugin — recorded here so they are not re-proposed as harness features:
- **Loop kickoff** (cron / CI / GitHub Actions) — the runner is unattended *once started*; scheduling the start is a host concern. Cloud runners also conflict with the local least-privilege model (network/push are blocked by design — `HARNESS_ENGINEERING §4`).
- **External reporting** (Slack / Notion / dashboards) — failure notification is host transport (`notify.sh`); progress lives in repo docs.
- **Automated push** — the loop commits locally only; promotion is a human decision after morning review.
- **Goal/deadline routing ("what not to do today")** — a planning concern above the loop, not a verification layer.

## 6. Sister Concepts (Bibles)
- Parent Harness: [`HARNESS_ENGINEERING.md`](HARNESS_ENGINEERING.md) · Autonomous Loop: [`LOOP_ENGINEERING.md`](LOOP_ENGINEERING.md)
- Multi-Agent: [`AGENTIC_ENGINEERING.md`](AGENTIC_ENGINEERING.md) · Context Restoration: [`CONTEXT_ENGINEERING.md`](CONTEXT_ENGINEERING.md) · Prompt Layer: [`PROMPT_ENGINEERING.md`](PROMPT_ENGINEERING.md)
- This Repo Application: [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md)
