---
status_version: 1
current_objective: "Week 2 of the gstack-borrow initiative — build /work-breakdown skill as the adoption bridge for pain D (work-breakdown procedure lives in head, not codified)"
active_branch: mit-344-week2-work-breakdown
active_pr: null
linear_issue: MIT-344
linear_team: MIT
linear_project: https://linear.app/mitzoku/project/gstack-borrow-week-2-work-breakdown-e7a410fbafb8
blocked_on_user: []
next_command: "Draft /work-breakdown SKILL.md with S/M/L/XL classification + specialist routing thresholds"
last_verified_state: 2026-05-11T00:00:00Z
links:
  initiative: https://linear.app/mitzoku/initiative/gstack-borrow-4e2936810b96
  project: https://linear.app/mitzoku/project/gstack-borrow-week-2-work-breakdown-e7a410fbafb8
  handoff: research/gstack-borrow-2026-05-11.md
---

# claude-agents status

## Current objective

Week 2 of the **gstack-borrow** initiative: build the `/work-breakdown` skill — the adoption bridge for pain D (multi-step work-breakdown procedure lives in user's head, not codified).

Per codex review: this is narrower than `/autoplan`. Just the breakdown decision + Linear orchestration. PM → tech-lead → TPM full coordinator orchestration is deferred until one real use shows the seams.

## What's next

1. Draft `skills/work-breakdown/SKILL.md` with explicit S/M/L/XL classification thresholds + specialist-routing rules.
2. Manual test on one real small idea end-to-end (`/sitrep --all` cross-project rollup is the leading candidate).
3. Codex review.
4. PR against `main`.

## Open items needing my attention

_Populated by `/sitrep` from live Linear/GitHub queries._

## Future work (not inbox)

- [research/gstack-borrow-2026-05-11.md](research/gstack-borrow-2026-05-11.md) — handoff doc. Reference for Week 3+ (`/design-doc`, `plan-eng-review`) and Week 4 (`/prioritize`).
- Project B (MIT-294–302) — fold gstack eval mechanics (touchfile diff selection + tier system + extended EvalResult schema) when picked up. Parallel track.

## Decisions log (recent)

- 2026-05-11 — Week 1 merged (PR #19, MIT-343). Bootstrap loop shipped: STATUS.md schema v1 + thin CLAUDE.md + /sitrep v0 + sitrep-linear wrapper.
- 2026-05-11 — Per user feedback on PR #19: wrap CLI in a tool, don't bury CLI version handling in skill prose. Pattern: `skills/<skill>/bin/<wrapper>` symlinked to `~/.local/bin/`.
- 2026-05-11 — Adopted boil-the-lake the gstack way (full adoption, including feature scope). Folded into the Week 1 stance: build the complete useful version of `/sitrep`, not a "recent commits" stub. Recorded in handoff.
- 2026-05-11 — Codex review of gstack-borrow shortlist applied. Dropped `ETHOS.md`, `/codex` skill, `/retro`, `/triage`, and `/autoplan` as full coordinator port. Added `/work-breakdown` as the adoption bridge for Week 2.
- 2026-05-11 — `/sitrep` rolls in inbox state from day one (C and B are entangled per codex). No separate `/inbox` skill.
- 2026-05-11 — `STATUS.md` schema v1 defined. Lives at repo root; `/sitrep` is the read+write client.
