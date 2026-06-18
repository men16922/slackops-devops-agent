# Engineering — 5 Agent-Operation Concepts (bible → interpretation)

This directory defines this repo's **AI agent operation harness** as 5 concepts. The structure is **bible → interpretation**:
- **bible** (`*_ENGINEERING.md`) = **general, portable** concept docs. Not tied to a specific repo (you can carry them to another project).
- **interpretation** (`interp/INTERPRETATION.md`) = an application doc that **maps those concepts to this repo's actual files, commands, and mechanisms**.

The bible holds "what/why"; the interpretation holds "how, in this repo".

## 5 Concepts
| Concept | Bible (general) |
| --- | --- |
| Harness (top-level operating system) | [HARNESS_ENGINEERING.md](HARNESS_ENGINEERING.md) |
| Autonomous unattended loop | [LOOP_ENGINEERING.md](LOOP_ENGINEERING.md) |
| Parallel multi-agent | [AGENTIC_ENGINEERING.md](AGENTIC_ENGINEERING.md) |
| Context/continuity | [CONTEXT_ENGINEERING.md](CONTEXT_ENGINEERING.md) |
| Prompt | [PROMPT_ENGINEERING.md](PROMPT_ENGINEERING.md) |

This repo's mapping: [interp/INTERPRETATION.md](interp/INTERPRETATION.md) (fill in the skeleton `/harness-init` generated).

## Read Order
1. **First grasping the concepts**: bible `HARNESS_ENGINEERING.md` (the full picture) → the bible for the concept you need.
2. **Actually running it in this repo**: `interp/INTERPRETATION.md` (runner, gate, file paths).
3. Unattended loop operation = `LOOP_ENGINEERING.md` + `scripts/overnight/run.sh`.
4. Docs/state/session continuity = `CONTEXT_ENGINEERING.md` + `/sync`·`/checkpoint` skills.

## Authority / Upstream Docs
- Doc operation rules, line budgets: `.claude/harness-config.json` (read by skills) + `CONTEXT_ENGINEERING.md`.
- Backlog/lane tags: `docs/NEXT_PLAN.md`.
