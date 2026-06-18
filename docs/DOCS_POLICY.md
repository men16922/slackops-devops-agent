# DOCS_POLICY — slackops-devops-agent
Last updated: 2026-06-17

> Doc operating rules (context budget). Full standards in harness/CORE_MANDATES.md.
> Skills and budgets: the **overnight-harness plugin** + `.claude/harness-config.json` (budgets) are the single source.

## Context Budget (lifeline)
| Doc | Budget | Contents |
| --- | --- | --- |
| `AGENT_BRIEF.md` | ≤ 60 lines | 1-minute compressed context, snapshot, current focus, guardrails |
| `STATUS.md` | ≤ 120 lines | current implementation state, verification baseline, active focus, open risks |
| `NEXT_PLAN.md` | ≤ 120 lines | **open work only** (not completed history) |
| `PROGRESS_LOG.md` | ≤ 120 lines | latest 3–5 increments. When over, split into docs/archive/progress-YYYY-MM.md |

Rules: no bulk-read of the whole `docs/` (Read Path only). Compress completed checklists into `COMPLETED_SUMMARY.md` + link.
Record irreversible choices in `DECISIONS.md` (Decision/Reason/Impact). No guessing — if absent, say "not in docs".

## Read Path (session start/resume)
```
harness/CONTEXT_BRIDGE.md → docs/AGENT_BRIEF.md → docs/STATUS.md → docs/NEXT_PLAN.md
→ (if needed) top of docs/PROGRESS_LOG.md → (if needed) docs/archive/
```
Authority order: `NEXT_PLAN.md` > `docs/plans/` (historical). Immutable standard = `harness/CORE_MANDATES.md`.

## skill boundaries (provided by overnight-harness plugin — no overlap)
| skill | when | what it does |
| --- | --- | --- |
| `/sync` | session start/resume | read only the current docs per the Read Path and give a 5–10 line summary. **Read only.** |
| `/checkpoint` | work bundle done | collect changes → append to PROGRESS_LOG → conditionally update STATUS/BRIEF/NEXT → record milestone/decision. **Record only.** Commit only on request. |
| `/tidy-docs` | over budget / duplication | split PROGRESS_LOG into monthly archive, compress completed items, merge/retire duplicates. **Tidy only.** Deletion is a last resort, approve before destroying. |
| `/overnight-report` | morning review | report runner state, iterations, commits, re-measured gate, residual backlog. **Read + verify only.** |
| `/overnight-seed` | before unattended run | judge whether `[auto]` backlog is sufficient, survey candidates, record only approved items into plan. **Record only.** |

Boundary principle: **/sync reads only, /checkpoint records only, /tidy-docs tidies only.** None does another's job.

## PROGRESS_LOG entry format
```text
## YYYY-MM-DD — <one-line title>
- Status:
- Changed:
- Verified:   # only verification actually run. If not run, "unverified".
- Blockers:
- Next:
```
