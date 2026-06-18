# LOOP_ENGINEERING — Autonomous Unattended Loop Operation (bible)

> **General concept document (bible).** For this repo's application (runner, env, make targets) → [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md).

## Definition
An autonomous execution loop that repeatedly invokes a single prompt headlessly, where each iteration **restores state from a small context → implements one task and passes the gate
→ records → commits locally**. One iteration = one atomic unit of work. Since each iteration commits,
**no matter when it stops, the loss is at most one iteration**.

## 1. Core Principles
| Principle | Why |
| --- | --- |
| **Fresh context per iteration** | Each iteration is a new process → no context bloat/summarization problem. Restore by re-reading only the Read Path. |
| **Iteration = one task + immediate commit** | Whenever a limit/crash hits, uncommitted loss is only one iteration. The next iteration picks up. |
| **offline gate = commit gate** | If the deterministic gate (lint+type+build+test) isn't green, no commit → broken code doesn't accumulate. No network needed. |
| **State on files** | Backlog, history, git history. Disk, not memory, is the source of truth. |
| **Least-privilege unattended execution** | Block push/network/destructive actions with allow/deny boundaries (`HARNESS_ENGINEERING §4`). |

## 2. One Loop Pass (loop-once)
```
restore state → recover leftovers (prior iteration's interrupted work) → select one task from backlog
  → implement + pass gate → record → commit locally → (pause) → repeat
```
- **Recover leftovers**: a dirty tree at start = leftover interrupted work from the prior iteration. If the gate is green, commit the recovery; if red, no edits + a stop signal.
- **Result classification**: structurally classify the iteration result as success/limit/failure (no free-text grep — avoids false misjudgment).
  limit→wait then retry, failure→consecutive-failure count, success→check whether a commit was created (HEAD diff) to track no-progress count.

## 3. Backlog Tagging — Marking Unattended Targets
Tag automation **on an axis separate** from status boxes:
- `auto` = locally, deterministically, offline-verifiable. **A one-line completion criterion is required** (prevents scope runaway).
- `manual` = human-perceived/content/balance/feel judgment → can't be verified unattended.
- `blocked` = accumulated failures or unmet preconditions.
- untagged = not an unattended target (safe default). The runner only consumes `auto*`; no arbitrary promotion.
> **A thin backlog is normal**: the more a repo has creative/perceptual work, the faster the `auto` backlog drains. Frequent no-progress
> exits are normal; for efficiency, **seed** `auto` items before running (regression backfill, codemod, lint/type debt, stale-doc cleanup).

## 4. Termination Conditions (backstops)
Backlog exhausted (DONE) · manual/red leftovers (STOP) · max iterations · N consecutive failures · N no-progress. **It stops when done** (0 extra tokens).

## 5. Application Limits
This loop suits **hygiene/regression/refactor/codemod/deterministic-bugfix**. Don't use it for creative/perceptual/content authoring —
the unattended gate can't verify those (those are `manual`, human QA).

## 6. Sibling Concepts (bibles)
- Parent harness: [`HARNESS_ENGINEERING.md`](HARNESS_ENGINEERING.md) · Parallel multi-engine: [`AGENTIC_ENGINEERING.md`](AGENTIC_ENGINEERING.md)
- Context restoration: [`CONTEXT_ENGINEERING.md`](CONTEXT_ENGINEERING.md) · Iteration prompt: [`PROMPT_ENGINEERING.md`](PROMPT_ENGINEERING.md)
- This repo's application: [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md)
