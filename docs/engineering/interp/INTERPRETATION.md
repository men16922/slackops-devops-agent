# Engineering Interpretation — slackops-devops-agent

This document **maps the `docs/engineering/*_ENGINEERING.md` bibles (general concepts)** to **this repo's actual files, commands, and mechanisms**.
Bible = "what/why" (portable), this doc = "how, in this repo". (Absorbs the content of the old `docs/LOOP_ENGINEERING.md`.)
The repo's invariant standards are in `harness/CORE_MANDATES.md`, and the handoff is in `harness/CONTEXT_BRIDGE.md`.

## HARNESS — Maturity/Verification/Permissions (bible `HARNESS_ENGINEERING.md`)
- gate (verification): `make check` = `pytest tests/ -q` + `ruff check src tests` + `mypy src` (strict).
  If not all green, no commit → prevents broken/low-quality code from accumulating (lowers morning human-review cost). baseline 229 passed, 1 skipped.
- Permission boundary: `scripts/overnight/overnight-settings.json` (`--settings` isolation applied — interactive settings unchanged).
  allow=gate targets (make/python3/some git), deny=`aws`·`git push`·`curl`/`wget`·`rm -rf`·`sudo`·Web*·github MCP.
- Maturity: at the stage where the local [auto] backlog is drained — the remainder is [manual] (AWS/Slack/UI). Next investment = real e2e / observability capture.

## LOOP — Unattended Loop (bible `LOOP_ENGINEERING.md`)
- Runner: `scripts/overnight/run.sh` (single engine claude). Each iteration runs `claude -p PROMPT --settings overnight-settings.json`.
  env: `GATE_CMD`(=make check)/`MAX_ITER`(50)/`ITER_TIMEOUT`(3600s)/`LIMIT_WAIT`(1800s)/`PAUSE`(30s)/
  `MAX_CONSEC_FAIL`(3)/`MAX_NO_PROGRESS`(2)/`KEEP_ITER_LOGS`(30)/`--once`.
- Result classification: if the last object of `--output-format json` has `is_error==false` → success (ignore a 'rate limit'
  mention in a successful iteration's text), otherwise check the limit text → limit (wait, retry), else failure. On success, compare HEAD before/after to judge
  no_progress (block empty iterations / repeated Blocker).
- Iteration prompt: `scripts/overnight/PROMPT.md` — ①sync ②recover leftovers (dirty+green=`[recovered]` commit,
  red=no edits+STOP) ③top one `[auto]` (Blocker twice→`[blocked]`, drained→DONE) ④implement+gate ⑤checkpoint ⑥local commit.
- Backlog tags: `[auto]`/`[manual]`/`[blocked]` in `docs/NEXT_PLAN.md`. Top→bottom, one at a time, removed on completion.
- **Quality-review iteration pattern**: after an implementation milestone, a read-only review-style `[auto]` (security/type/simplification lens, no code edits)
  → feed findings back as `[auto]` → the next iteration fixes them. Forms a quality loop while keeping the 1-iteration=1-task invariant.
- skills: `/overnight-harness:{sync,checkpoint,tidy-docs,overnight-report,overnight-seed}` (provided by the plugin).

## AGENTIC — Multi-Agent (bible `AGENTIC_ENGINEERING.md`)
- Currently single engine (claude). When introducing multi, map lane/domain partitioning, worktree isolation, and builder≠reviewer here.

## CONTEXT — Context/Doc Discipline (bible `CONTEXT_ENGINEERING.md`)
- Read Path: `harness/CONTEXT_BRIDGE.md` → `docs/AGENT_BRIEF.md` → `docs/STATUS.md` → `docs/NEXT_PLAN.md`
  → (if needed) top of `docs/PROGRESS_LOG.md` → (if needed) `docs/archive/`. No bulk-read of all of docs/.
- Line budget: brief ≤60 · status/plan/log ≤120 (`.claude/harness-config.json` budgets). Operation rules in `docs/DOCS_POLICY.md`.
- State on files: `NEXT_PLAN` (backlog) · `PROGRESS_LOG` (history) · git history are the source of truth (not memory).
- archive: `docs/archive/progress-YYYY-MM.md` (`/tidy-docs` splits PROGRESS_LOG overflow by month).

## PROMPT — Prompt Layer (bible `PROMPT_ENGINEERING.md`)
- Harness prompt: `scripts/overnight/PROMPT.md` (+ repo invariant sections: CORE_MANDATES/aws→mock/lazy import/Korean).
- Runtime/domain prompt: `src/app/sanitizer.py` (wrap_untrusted + build_prompt template) — no direct passing of Slack
  input · logs/diff isolated in `<untrusted_data>` (part of the 4-layer injection defense).

## Limits / Known Behavior (old LOOP_ENGINEERING §5)
- Mac sleep: `caffeinate` is required, power connection recommended. Per-iteration loss: if a limit hits mid-iteration, only the in-progress iteration is
  uncommitted-lost (committed up to the prior one; next iteration restores via `/sync` — PROMPT step 2 [recovered] automation, red is human-reviewed).
