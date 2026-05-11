---
status_version: 1
current_objective: "Week 1 of the gstack-borrow initiative — ship the bootstrap loop (STATUS.md schema + thin CLAUDE.md + /sitrep v0)"
active_branch: mit-343-week1-bootstrap-loop
active_pr: null
linear_issue: MIT-343
linear_project: https://linear.app/mitzoku/project/gstack-borrow-week-1-bootstrap-loop-edfc7c15d5d8
blocked_on_user: []
next_command: "Build /sitrep v0 skill (after CLAUDE.md lands)"
last_verified_state: 2026-05-11T00:00:00Z
links:
  initiative: https://linear.app/mitzoku/initiative/gstack-borrow-4e2936810b96
  project: https://linear.app/mitzoku/project/gstack-borrow-week-1-bootstrap-loop-edfc7c15d5d8
  handoff: research/gstack-borrow-2026-05-11.md
---

# claude-agents status

## Current objective

Week 1 of the **gstack-borrow** initiative: build the bootstrap loop so Claude opens oriented every session. Fixes pain bucket C (session bootstrap) and the operational part of B (cross-project state).

Three artifacts ship in one PR:
1. `STATUS.md` schema + this instance (the canonical session-state contract).
2. Thin `CLAUDE.md` at repo root — three rules only.
3. `/sitrep v0` skill — read+write client of STATUS.md.

## What's next

1. Land thin CLAUDE.md (3 rules: session-start, routing, Linear-as-inbox).
2. Build `/sitrep v0` skill — reads STATUS.md, `linear issue mine`, `gh pr list`, recent commits; writes back updates.
3. Manual test `/sitrep` in this repo end-to-end.
4. Codex review (1 round).
5. PR against `main`.

## Open items needing my attention

- [research/gstack-borrow-2026-05-11.md](research/gstack-borrow-2026-05-11.md) — handoff doc with codex-revised shortlist. Read before starting Week 2 (`/work-breakdown`).
- Outstanding Project B work (MIT-294–302) — fold gstack eval mechanics (touchfile diff selection + tier system + extended EvalResult schema) when picked up.

## Decisions log (recent)

- 2026-05-11 — Adopted boil-the-lake the gstack way (full adoption, including feature scope). Folded into the Week 1 stance: build the complete useful version of `/sitrep`, not a "recent commits" stub. Recorded in handoff.
- 2026-05-11 — Codex review of gstack-borrow shortlist applied. Dropped `ETHOS.md`, `/codex` skill, `/retro`, `/triage`, and `/autoplan` as full coordinator port. Added `/work-breakdown` as the adoption bridge for Week 2.
- 2026-05-11 — `/sitrep` rolls in inbox state from day one (C and B are entangled per codex). No separate `/inbox` skill.
- 2026-05-11 — `STATUS.md` schema v1 defined. Lives at repo root; `/sitrep` is the read+write client.
