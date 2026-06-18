# AGENTIC_ENGINEERING — Parallel Multi-Agent Operation (bible)

> **General concept document (bible).** For this repo's application (3 engines, worktree, make) → [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md).

## Definition
The engineering of **organizing multiple headless agents by role, isolation, and gates** so they collaborate without conflict. A single agent
doesn't do everything. An orchestrator decomposes and assigns work, and specialized agents execute each in their own domain.

## 1. Block Conflicts by "Structure"
Concurrent-write conflicts are blocked by **isolation**, not willpower. Keep three axes from overlapping:
1. **Work-tree isolation** — a different worktree+branch per agent → they can't touch the same file at once.
2. **Lane separation** — an agent-suffix tag on backlog tasks → two agents don't pick the same item.
3. **Domain partitioning** — per-agent directory ownership → merge conflicts are virtually nonexistent.
4. **Shared-doc convention** — docs all three touch are append-only + merge=union, or toggle only one's own lane line.

## 2. Role Specialization (Builder ≠ Reviewer ≠ Researcher ≠ QA)
| Role | Responsibility |
| --- | --- |
| Orchestrator | Decompose work, assign lanes, integrate results, resolve conflicts, final approval |
| Builder | Implement, refactor, write tests, pass gate |
| Reviewer | Read-only audit of git diff (bugs/edges/missing tests/drift). **No code edits** |
| Researcher | Investigate, analyze docs, draft (image/content) generation |
| QA | E2E, browser, screenshot verification |
The number of roles isn't free (token + coordination cost). For a small repo, having the Builder also serve as Orchestrator is reasonable.

## 3. Creator ≠ Reviewer (Core Loop)
Separate the creating agent from the reviewing agent to reduce **self-confirmation bias**:
```
Builder creates → integrate → Reviewer read-only audit → feed findings back to backlog → Builder fixes
```
The reviewer fixes neither code nor backlog directly — only produces findings. The orchestrator reflects them into the backlog.

## 4. Deterministic vs Non-deterministic Lanes Have Different Gates
- **Deterministic (code)**: gate green → auto-commit. Safe.
- **Non-deterministic (image/content/feel)**: the same input differs each time and it's a "feel" call, so it can't be locked into a gate
  → auto-commit only via an **integrity gate** (it exists / it's spec-conformant), and leave aesthetic/narrative quality to **human review**. No fabricating missing assets.

## 5. Reasoning Sandwich
Planning = high reasoning, implementation = medium reasoning, verification = high reasoning. Using the top model at every stage is wasteful. Match the model tier per stage.

## 6. Sibling Concepts (bibles)
- Parent harness: [`HARNESS_ENGINEERING.md`](HARNESS_ENGINEERING.md) · Single loop: [`LOOP_ENGINEERING.md`](LOOP_ENGINEERING.md)
- Context: [`CONTEXT_ENGINEERING.md`](CONTEXT_ENGINEERING.md) · Prompt: [`PROMPT_ENGINEERING.md`](PROMPT_ENGINEERING.md)
- This repo's application: [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md)
