---
status_version: 1
current_objective: "Week 3a of the gstack-borrow initiative — build /design-doc skill that scaffolds a doc with three mandatory diagrams (user-flow + state-machine + data-flow). plan-eng-review (the auditor) ships as Week 3b."
active_branch: mit-347-design-doc
active_pr: null
linear_issue: MIT-347
linear_team: MIT
linear_project: https://linear.app/mitzoku/project/gstack-borrow-week-3-planning-discipline-bba4630036be
blocked_on_user: []
next_command: "Draft skills/design-doc/SKILL.md + a template file with all 8 required sections"
last_verified_state: 2026-05-11T00:00:00Z
links:
  initiative: https://linear.app/mitzoku/initiative/gstack-borrow-4e2936810b96
  project: https://linear.app/mitzoku/project/gstack-borrow-week-2-work-breakdown-e7a410fbafb8
  handoff: research/gstack-borrow-2026-05-11.md
---

# claude-agents status

## Current objective

Week 3a of the **gstack-borrow** initiative — `/design-doc` skill. Scaffolds a design doc with three mandatory diagram sections (user-flow + state-machine + data-flow) so the "did I include all the diagrams?" cognitive load goes to zero.

Per codex review of the shortlist: `/design-doc` creates, `plan-eng-review` audits. Two separate skills, two separate PRs. This is Week 3a (creator). Week 3b (auditor + hard gate) is the follow-up.

## What's next

1. Draft `skills/design-doc/SKILL.md` with the 8-section template + 3 mandatory diagram stubs.
2. Manual test: scaffold the design doc for the upcoming `plan-eng-review` lift (Week 3b). That doc then becomes Week 3b's input.
3. Codex review.
4. PR against `main`.
5. Move to Week 3b: `plan-eng-review` lift from gstack (strip plumbing, hard gate on missing diagrams).

## Open items needing my attention

- [decisions/0001-plan-eng-review-lift.md](decisions/0001-plan-eng-review-lift.md) — design-doc scaffold for Week 3b. All 8 sections are stubs; fill before starting Week 3b implementation.
- [MIT-345 — /sitrep --all for cross-project rollup](https://linear.app/mitzoku/issue/MIT-345/sitrep-all-for-cross-project-rollup) — side-quest from the /work-breakdown manual test. S-sized. Picks up after Week 3 ships if no higher-priority work appears.

_Live items in this section are normally populated by `/sitrep` from Linear/GitHub queries._

## Future work (not inbox)

- [research/gstack-borrow-2026-05-11.md](research/gstack-borrow-2026-05-11.md) — handoff doc. Reference for Week 3+ (`/design-doc`, `plan-eng-review`) and Week 4 (`/prioritize`).
- Project B (MIT-294–302) — fold gstack eval mechanics (touchfile diff selection + tier system + extended EvalResult schema) when picked up. Parallel track.

## Decisions log (recent)

- 2026-05-11 — Ran `/design-doc` manual test by scaffolding the Week 3b doc itself (`decisions/0001-plan-eng-review-lift.md`). 8 sections + 3 diagram stubs created cleanly via template substitution. Recursive setup: the design doc for plan-eng-review will eventually be audited BY plan-eng-review.
- 2026-05-11 — Established `decisions/` as the canonical location for design docs (ADR-numbered format `NNNN-<slug>.md`). `research/` reserved for research handoffs / external-source notes.
- 2026-05-11 — Evaluated the Forrest-Chang 12-rule CLAUDE.md template (karpathy-thread-derived). Cherry-picked 2 rules (Surface conflicts + Fail loud). Rejected 10: Simplicity-First contradicts boil-the-lake; token-budgets are unenforceable from CLAUDE.md; several others duplicate Claude Code defaults. MIT-346 captures the promotion + rationale.
- 2026-05-11 — Week 2 merged (PR #20, MIT-344). `/work-breakdown` skill shipped + CLAUDE.md rule 4 (invoke before non-trivial work). Manual test produced MIT-345.
- 2026-05-11 — Ran `/work-breakdown` manual test on the `/sitrep --all` idea. Classified S; created MIT-345. Applied Step-7 Case B (side quest). Confirms the skill produces useful Linear artifacts and the side-quest test fires correctly.
- 2026-05-11 — Week 1 merged (PR #19, MIT-343). Bootstrap loop shipped: STATUS.md schema v1 + thin CLAUDE.md + /sitrep v0 + sitrep-linear wrapper.
- 2026-05-11 — Per user feedback on PR #19: wrap CLI in a tool, don't bury CLI version handling in skill prose. Pattern: `skills/<skill>/bin/<wrapper>` symlinked to `~/.local/bin/`.
- 2026-05-11 — Adopted boil-the-lake the gstack way (full adoption, including feature scope). Folded into the Week 1 stance: build the complete useful version of `/sitrep`, not a "recent commits" stub. Recorded in handoff.
- 2026-05-11 — Codex review of gstack-borrow shortlist applied. Dropped `ETHOS.md`, `/codex` skill, `/retro`, `/triage`, and `/autoplan` as full coordinator port. Added `/work-breakdown` as the adoption bridge for Week 2.
- 2026-05-11 — `/sitrep` rolls in inbox state from day one (C and B are entangled per codex). No separate `/inbox` skill.
- 2026-05-11 — `STATUS.md` schema v1 defined. Lives at repo root; `/sitrep` is the read+write client.
