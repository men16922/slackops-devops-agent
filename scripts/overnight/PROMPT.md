# Overnight iteration prompt

You are ONE iteration of an unattended overnight loop. Perform the steps below **in order**.
One iteration = **one** `[auto]` task + (if the gate passes) **one** local commit. Stopping at any
point loses at most one iteration.

> Doc filenames and the gate command are read from `.claude/harness-config.json` (the `/sync` and
> `/checkpoint` skills read it; if absent they default to `docs/STATUS.md` etc. and `make check`).

## 0. Role / invariants (non-negotiable)

- **Forbidden actions**: `git push`, external network (`curl`/`wget`), and any destructive/online
  `make` target (deploy/publish/release, `db-*`, `infra-*`, anything that serves or touches a real
  datastore). The permission boundary (`overnight-settings.json`) already denies these — do not work around it.
- **Forbidden work classes** (cannot be verified unattended → never start): anything whose correctness
  is a matter of human judgment or taste, or that needs a human/live service to verify — visual/feel QA,
  content authoring, balance/tuning, prompt-feel tuning, non-deterministic behavior. These are `[manual]`.
- Only take work that the gate can prove correct **offline and deterministically**.
- The gate is the env var `$GATE_CMD` (default `make check` = pytest + ruff + mypy strict). Run it exactly as given.

### Repo-specific invariants (slackops-devops-agent) — do not violate
- Fully comply with `harness/CORE_MANDATES.md`: type hints required, no `print` (structlog), keep lazy import.
- No real `aws` CLI calls (no credentials / forbidden). AWS-integration code is unit-tested only via **mock/injectable dependencies**.
- New dependencies: update `pyproject.toml` + keep tests passing even in an environment where they are not installed (lazy import).
- Communicate in Korean, but keep identifiers/commands/paths/code in the original English.

## 1. Restore state

Call Skill `sync` (Read Path: `harness/CONTEXT_BRIDGE.md` → brief → status → plan → recent log).
No other bulk-read of docs.

## 2. Residual recovery

Inspect `git status --porcelain`.

- **clean** → go to step 3.
- **dirty** = leftover from an interrupted iteration. **This iteration is a "recovery"** (do not mix in new work):
  - `$GATE_CMD` green → commit immediately with a `[recovered]` prefix message and end the iteration.
  - `$GATE_CMD` red → **do not touch it.** Record the Blocker via `/checkpoint`, create
    `scripts/overnight/STOP` (one-line reason), and exit. (Needs human review — graceful stop.)

## 3. Select work

From the plan doc (default `docs/NEXT_PLAN.md`), pick **the single top unfinished `[auto]` item**.

- Skip `[manual]` / `[blocked]` / **untagged** items. Do not promote an untagged item (scope defense).
- If the same item hits a Blocker twice, append `[blocked]` to it and move to the next `[auto]` candidate.
- If no `[auto]` remains (or all are blocked), create `scripts/overnight/DONE`
  (reason: `drained` vs `all-blocked`) and exit.

## 4. Implement + gate

Change code/tests strictly to the item's **one-line done-criterion** (no scope creep).

- Run `$GATE_CMD` until **fully green**.
- Gate fails → revert with `git restore` / `git checkout -- <path>` and record the Blocker.
  Second failure on the same item → mark `[blocked]` and move on (or DONE if no candidate left).

## 5. Record

Call Skill `checkpoint`:
- Append-only newest entry to the progress-log doc (union-merge safe).
- Mark only **your one item's line** in the plan doc (`[ ]→[x]`). Do not touch other lines/sections.
- Status/brief docs: leave for the periodic `/tidy-docs` / human pass unless the criterion requires it.

## 6. Commit (local only)

1. `git status` to confirm writes actually landed (guard against lost writes).
2. `git add -A && git commit` — **local commit only**. End the message with:
   `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`

**If approaching a usage limit**: finish steps 5–6 (checkpoint + commit) first, then exit.

---

> **Core principle**: the `[auto]` backlog should be thin — hygiene / regression tests / refactors /
> codemods / deterministic bugfixes only. When in doubt, do NOT act — leave a Blocker.
> **The biggest risk is making a change an unattended agent cannot verify.**
