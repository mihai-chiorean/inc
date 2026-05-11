---
status_version: 1
current_objective: "Week 1 of the gstack-borrow initiative — ship the bootstrap loop (STATUS.md schema + thin CLAUDE.md + /sitrep v0)"
active_branch: mit-343-week1-bootstrap-loop
active_pr: "https://github.com/mihai-chiorean/claude-agents/pull/19"
linear_issue: MIT-343
linear_team: MIT
linear_project: https://linear.app/mitzoku/project/gstack-borrow-week-1-bootstrap-loop-edfc7c15d5d8
blocked_on_user: []
next_command: "Merge PR #19 once green; then begin Week 2 (/work-breakdown)"
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

1. Merge PR #19 once green.
2. Begin Week 2 (`/work-breakdown` — the adoption bridge for pain D). New branch, new Linear issue under the same initiative.
3. (Parallel) Resume Project B (MIT-294–302) with gstack eval mechanics folded in.

## Open items needing my attention

_None right now — `/sitrep` populates this section from live Linear/GitHub queries; static items belong in a future-work or backlog section._

## Future work (not inbox)

- [research/gstack-borrow-2026-05-11.md](research/gstack-borrow-2026-05-11.md) — handoff doc with the codex-revised shortlist. Reference for Week 2+.
- Project B (MIT-294–302) — fold gstack eval mechanics (touchfile diff selection + tier system + extended EvalResult schema) when picked up. Parallel track.

## Decisions log (recent)

- 2026-05-11 — Adopted boil-the-lake the gstack way (full adoption, including feature scope). Folded into the Week 1 stance: build the complete useful version of `/sitrep`, not a "recent commits" stub. Recorded in handoff.
- 2026-05-11 — Codex review of gstack-borrow shortlist applied. Dropped `ETHOS.md`, `/codex` skill, `/retro`, `/triage`, and `/autoplan` as full coordinator port. Added `/work-breakdown` as the adoption bridge for Week 2.
- 2026-05-11 — `/sitrep` rolls in inbox state from day one (C and B are entangled per codex). No separate `/inbox` skill.
- 2026-05-11 — `STATUS.md` schema v1 defined. Lives at repo root; `/sitrep` is the read+write client.
