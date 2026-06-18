# CONTEXT_ENGINEERING — Context Budget, State Restoration, Session Continuity (bible)

> **General concept document (bible).** For this repo's application (read-path, /sync, entry points) → [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md).

## Definition
The engineering of letting an agent **restore the correct work context with minimal tokens** and letting the next session seamlessly
pick up even when a session is cut off. **Disk, not memory, is the source of truth.**

## 1. Read Path & Context Budget
Don't bulk-read all docs at session start; read **only the entry points** (short → detailed order):
1. Compressed entry point (1-minute context) → 2. Current status → 3. Next tasks (rolling plan) → 4. Latest incremental log.
- Details (design/rules/scenarios/dated plan/archive) are **on-demand** — open them only when actually changing them.
- Put a **line budget** on entry-point docs (e.g., entry point ≤60, status/plan ≤120). Split overflow into cleanup/archive.
- Key: the entry point is **a map, not a manual that contains everything**. Details are reached via links.

## 2. Knowledge Pyramid
| Layer | Nature |
| --- | --- |
| L0 | Entry points always read at session start |
| L1 | Core docs referenced on demand (design, rules, plan) |
| L2 | Per-task detail (dated plan, design-doc, structured task list) |
| L3 | Generated/referenced/large docs (review, report, trace, archive) — not in the default context |

## 3. Triple State Storage
| Layer | Medium | Question it answers |
| --- | --- | --- |
| Change history | git history | What was changed |
| Structured state | machine-readable ledger (task/event ledger) | How the loop ran |
| Natural-language state | current status/progress/handoff docs | Why · what next |
The three are complementary. None fully replaces the others.

## 4. Session Continuity (Resume Pointer) — plan-only/unfinished handoff
When a session ends plan-only or unfinished and the next session must pick up:
1. **A single "next session" pointer at the top of the entry point** = in-repo plan path + first concrete action.
2. Promote that task to **authoritative active focus** → **align** the entry-point/status/plan docs (don't leave it as just a header note).
3. The state-restoration procedure surfaces this pointer **first** → the next session picks up seamlessly. Update/clear it once picked up.
- **Forbidden**: don't record a tool-generated out-of-session scratch path (random name, machine-local) as the authoritative pointer — the next session can't find it.

## 5. Preventing Entry-Point Divergence
Keep multiple agent entry points (per-tool instruction files) as **one shared body + the rest as links**. Copy-pasting the same content
soon causes them to drift apart (divergence). Unify entry points as thin wrappers and let one place own the detail.

## 6. Structure Index Is Conditional
A structure index (symbol/call-graph folder map / LSP / ctags etc.) can substitute for grep but isn't a cure-all.
The lever isn't shell latency but *round trips × per-turn tokens*. **When it pays**: large module + high-frequency symbol.
**When it loses**: rare literals / small files — grep is cheaper. Don't accept an "index-first" prescription without measurement.
**structure-before-body**: for large files, don't read end-to-end; narrow to members via the index first. **But index ≠ authority** — confirm the body in the original.

## 7. Sibling Concepts (bibles)
- Parent harness: [`HARNESS_ENGINEERING.md`](HARNESS_ENGINEERING.md) · Loop: [`LOOP_ENGINEERING.md`](LOOP_ENGINEERING.md)
- Multi-agent: [`AGENTIC_ENGINEERING.md`](AGENTIC_ENGINEERING.md) · Prompt: [`PROMPT_ENGINEERING.md`](PROMPT_ENGINEERING.md)
- This repo's application: [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md)
