# claude-agents — operating rules

This file is auto-loaded by Claude Code at session start. It is **deliberately thin**: three operational rules only. Other discipline (codex-review-before-merge, coverage gates, ETHOS philosophy) lives elsewhere and gets promoted into this file only if its absence costs real time.

The current scope is informed by the gstack-borrow Week 1 review — see `research/gstack-borrow-2026-05-11.md`.

---

## Rule 1 — Session bootstrap

On session start, **run or offer `/sitrep`** before doing other work. `/sitrep` reads `STATUS.md` + Linear + open PRs and surfaces "where you are, what's next, what's blocked on you." If the user's first message is an explicit task that bypasses bootstrap, do the task — but still surface a one-line orientation ("on branch X for MIT-Y; next was Z") from `STATUS.md` if it's present.

When work concludes, update `STATUS.md` (active branch, active PR, next command, last_verified_state). The schema lives at `skills/sitrep/docs/status-schema.md`.

## Rule 2 — Specialist routing

When the user's request matches a specialist agent's domain, **route to it via the Agent tool**. Do not redo work specialists exist to handle. When in doubt, route. The roster is the `agent.manifest.yaml` at the repo root, surfaced per-project by the `/staff` skill.

Specialists own depth. Skills own procedure. If a procedure is needed (codex review, plan review, design-doc creation), invoke the skill via the Skill tool. If a domain is needed (Swift backend, GPU, security audit), spawn the agent.

## Rule 3 — Linear-as-inbox

Linear is the queue and the history. The **inbox** is anything assigned to the user, any open PR awaiting their review, and any design doc flagged for review. `/sitrep` surfaces all three. Agents that produce review-worthy artifacts should create or update Linear items assigned back to the user (with a link), not leave them in chat or as wandering files.

When the user asks "what's on my plate" or "what needs my attention," go to Linear (via `linear issue mine`) and open PRs (via `gh pr list --search 'review-requested:@me'`), not to a chat-history reconstruction.

---

## Defer (not in this CLAUDE.md, yet)

The following are explicitly NOT enforced by this CLAUDE.md. Promote them only if their absence is observed to cost time:

- Codex review × 3 rounds per PR (currently done by convention; not a CLAUDE.md rule yet).
- 80% test coverage gate (project-specific; lives in `Makefile` for repos that need it).
- Boil-the-lake stance (procedural completeness vs feature scope — see handoff for the nuanced version).
- ETHOS.md cultural principles.

These may be promoted in a later week of the gstack-borrow initiative if they prove load-bearing.

## Pointers

- **Session-state contract:** `STATUS.md` at this repo's root. Schema at `skills/sitrep/docs/status-schema.md`.
- **Agent roster:** `agent.manifest.yaml` (top-level). Per-project staffing: `/staff` skill.
- **Active initiative:** gstack-borrow ([Linear](https://linear.app/mitzoku/initiative/gstack-borrow-4e2936810b96)). Handoff at `research/gstack-borrow-2026-05-11.md`.
