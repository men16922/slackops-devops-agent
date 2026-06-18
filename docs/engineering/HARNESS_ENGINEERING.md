# HARNESS_ENGINEERING — Safe Agent Operation Scaffolding (bible)

> **General concept document (bible).** Not tied to a specific repo. For this repo's application (interpretation) → [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md).

## Definition
An operating system that, instead of letting an AI agent write code freely, embeds **knowledge, constraints, verification, state recording, and a review loop into the repo**
so the agent runs safely on repeat. One-line principle: **Humans steer. Agents execute.**
Humans set the direction, boundaries, and exceptions; agents repeat implementation, verification, fixing, and recording within them.

## 1. Maturity Ladder (L0→L4)
| Level | Definition |
| --- | --- |
| L0 Ad-hoc | Human approval every time; rules/state exist only in the chat window |
| L1 Basic Harness | Agent instruction file + lint/test gate + worktree/branch isolation + documented plan |
| L2 Automated Feedback | Gate script + independent reviewer + automatic retry on failure + checkpoint saving |
| L3 Multi-Agent | coder/reviewer/gardener role separation + risk-based approval + parallel worktrees + periodic entropy scan |
| L4 Self-Evolving | Failure-trace analysis + self-improving harness PRs + human intervention only on exceptions |
For most projects, **L2→L3** is a realistic goal. Self-diagnose your level and invest only in the gap of the next single step.

## 2. Feedback Ladder — Repeated Feedback Is Promoted to a Stronger System
| Repetition | What to encode |
| --- | --- |
| Once | Review note |
| Twice | Doc |
| 3×+ | Script / linter / test (deterministic gate) |
| Safety violation | hard gate (block) |
Key: when the same point recurs, lock it into a **deterministic gate**, not prose.

## 3. Verification Layers — Deterministic First, Probabilistic on Top
| Layer | Trigger | What it catches |
| --- | --- | --- |
| L1 | File change | Forbidden patterns, file size, secret, conflict marker |
| L2 | Turn end | lint, format, typecheck, architecture/dependency rules |
| L3 | Before completion | unit, integration, contract tests |
| L4 | After L3 | LLM/Codex read-only review (bugs, edges, drift) |
| L5 | PR/merge | Full CI, E2E, human approval |
Get L1-L3 (deterministic) in place first, and layer L4 (probabilistic review) on top. You can bundle them into a single gate command or
split them into scripts — all that matters is that **what gets caught where** is clear.

## 4. Tier-based Boundary Security — Boundaries, Not Per-Command Approval
| Tier | Action |
| --- | --- |
| 1 Always allowed | read, grep, glob, git status/diff |
| 2 Allowed within repo | Editing src/tests/docs/scripts + enumerated safe commands + local commit |
| 3 Conditional (block/human) | push, network, destructive commands, secret, prod, dependency install |
Tier 3 requires a plan before execution (what, why, impact, recovery, command). Unattended environments **physically block** Tier 3.

## 5. Adoption Principles
- **Repository as SoT**: rules/state live in the repo, not chat/memory. Plans too live in the repo (no scratch paths).
- **Agent Legibility First**: keep entry points small, core docs short, details in links. Enforce prohibitions with tests/scripts.
- **Constraints Create Speed**: stating "what not to do" reduces guessing/drift, which actually makes things faster.
- **Progressive Deletability**: attach a **removal condition** to every rule/gate (e.g., remove after 3 months no violation, when CI does the same check, or on architecture mismatch).
- **Agent-friendly errors**: gate failures carry the 4 elements *what / where / why forbidden / how to fix* so the agent can self-correct.
- **Measured Adoption**: don't accept external tools / harness prompts as prescribed. **Measure the effect, derive a conditional policy**,
  and attach a **removal condition**. (Vendor "X-FIRST / avoid Y" prompt → after measurement, qualify it like "only at large/high-frequency, authority is
  the original.") Optional accelerators are **not gated** (no making them required build dependencies).

## 6. Triple State Storage
git history (change history) + structured ledger (task/event ledger) + natural language (status/progress/handoff docs).
Disk, not memory, is the source of truth → restore via fresh context per iteration.

## 7. Sibling Concepts (bibles)
- Autonomous loop: [`LOOP_ENGINEERING.md`](LOOP_ENGINEERING.md) · Multi-agent: [`AGENTIC_ENGINEERING.md`](AGENTIC_ENGINEERING.md)
- Context: [`CONTEXT_ENGINEERING.md`](CONTEXT_ENGINEERING.md) · Prompt: [`PROMPT_ENGINEERING.md`](PROMPT_ENGINEERING.md)
- This repo's application: [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md)
