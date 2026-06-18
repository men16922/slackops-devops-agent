# PROMPT_ENGINEERING — Agent/LLM Prompt Design (bible)

> **General concept document (bible).** For this repo's application (iteration prompts, narrative prompts) → [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md).

## Definition
The engineering of **constraining and steering agent/LLM behavior via prompts**. There are usually two layers —
① **harness prompts** (the fixed procedure the agent runs every iteration) ② **runtime/domain prompts** (the requests a product feature makes to the LLM).

## 1. Harness Iteration Prompt
Encode the fixed procedure the unattended loop runs each iteration as a prompt:
- Standard procedure: restore state → recover leftovers → select one task → implement + gate → record → commit.
- Per-engine branching: even for the same procedure, split the prompt to match engine capabilities (skill calls available or not, sandbox or not).
- **Don't leave boundaries to the prompt alone — promote whatever you can to deterministic gates** (Feedback Ladder, `HARNESS_ENGINEERING §2`).
  Prompt-based prohibition is a last resort (only for what the sandbox can't block). Explicitly forbid fabricate (passing the gate with fake artifacts).

## 2. Runtime/Domain Prompts — Reliability Patterns
| Pattern | Content |
| --- | --- |
| **Structured output** | Have it return a schema (JSON etc.) rather than free text, and encode the limits (length, item count, allowed keys). |
| **Model division of labor** | Separating generation (free text, large model) from structuring (parsing, small model) is more stable. |
| **repair → fallback** | On parse failure, retry repair once → on repeated failure, **deterministic fallback** (user-visible/safe behavior). |
| **context selection** | Don't inject the whole knowledge base; only relevant snippets + rollup summary (avoids context bloat, cost, drift). |

## 3. Tone/Register Rules Are a feel Domain
Things like prose tone, register, and repetition suppression are a **human-judgment (feel)** domain and can't be locked into an unattended gate. Keep the rules
documented (e.g., per-scene register, no repetition) but leave the final call to human QA. Repetition is often a real problem, so
suppress it with prompt guidance + an immediate-context window.

## 4. Sibling Concepts (bibles)
- Parent harness: [`HARNESS_ENGINEERING.md`](HARNESS_ENGINEERING.md) · Loop: [`LOOP_ENGINEERING.md`](LOOP_ENGINEERING.md)
- Multi-agent: [`AGENTIC_ENGINEERING.md`](AGENTIC_ENGINEERING.md) · Context: [`CONTEXT_ENGINEERING.md`](CONTEXT_ENGINEERING.md)
- This repo's application: [`interp/INTERPRETATION.md`](interp/INTERPRETATION.md)
