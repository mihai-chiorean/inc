---
status_version: 1
current_objective: "Promote 2 rules to CLAUDE.md (Surface conflicts + Fail loud) — small detour before Week 3"
active_branch: mit-346-claudemd-rules
active_pr: null
linear_issue: MIT-346
linear_team: MIT
linear_project: null
blocked_on_user: []
next_command: "Open PR for MIT-346, merge, then begin Week 3 (/design-doc + plan-eng-review lift)"
last_verified_state: 2026-05-11T00:00:00Z
links:
  initiative: https://linear.app/mitzoku/initiative/gstack-borrow-4e2936810b96
  project: https://linear.app/mitzoku/project/gstack-borrow-week-2-work-breakdown-e7a410fbafb8
  handoff: research/gstack-borrow-2026-05-11.md
---

# claude-agents status

## Current objective

Small detour from the gstack-borrow week sequence: promote two CLAUDE.md rules (Surface conflicts + Fail loud) cherry-picked from the Forrest-Chang 12-rule template. Other 10 explicitly skipped per our "rules earn their place via observed failures" stance.

Week 2 (`/work-breakdown`) merged as [PR #20](https://github.com/mihai-chiorean/claude-agents/pull/20) earlier today. Week 3 is next once this small PR lands.

## What's next

1. Open PR for MIT-346 against `main`.
2. Merge.
3. Begin Week 3: `/design-doc` skill (creates, 3 mandatory diagrams) + `plan-eng-review` lift (audits, hard gate). Adopt informally on the next non-trivial plan; don't wait for Week 3 to formalize.

## Open items needing my attention

- [MIT-345 — /sitrep --all for cross-project rollup](https://linear.app/mitzoku/issue/MIT-345/sitrep-all-for-cross-project-rollup) — side-quest from the /work-breakdown manual test. S-sized. Picks up after Week 3 ships if no higher-priority work appears.

_Live items in this section are normally populated by `/sitrep` from Linear/GitHub queries._

## Future work (not inbox)

- [research/gstack-borrow-2026-05-11.md](research/gstack-borrow-2026-05-11.md) — handoff doc. Reference for Week 3+ (`/design-doc`, `plan-eng-review`) and Week 4 (`/prioritize`).
- Project B (MIT-294–302) — fold gstack eval mechanics (touchfile diff selection + tier system + extended EvalResult schema) when picked up. Parallel track.

## Decisions log (recent)

- 2026-05-11 — Evaluated the Forrest-Chang 12-rule CLAUDE.md template (karpathy-thread-derived). Cherry-picked 2 rules (Surface conflicts + Fail loud). Rejected 10: Simplicity-First contradicts boil-the-lake; token-budgets are unenforceable from CLAUDE.md; several others duplicate Claude Code defaults. MIT-346 captures the promotion + rationale.
- 2026-05-11 — Week 2 merged (PR #20, MIT-344). `/work-breakdown` skill shipped + CLAUDE.md rule 4 (invoke before non-trivial work). Manual test produced MIT-345.
- 2026-05-11 — Ran `/work-breakdown` manual test on the `/sitrep --all` idea. Classified S; created MIT-345. Applied Step-7 Case B (side quest). Confirms the skill produces useful Linear artifacts and the side-quest test fires correctly.
- 2026-05-11 — Week 1 merged (PR #19, MIT-343). Bootstrap loop shipped: STATUS.md schema v1 + thin CLAUDE.md + /sitrep v0 + sitrep-linear wrapper.
- 2026-05-11 — Per user feedback on PR #19: wrap CLI in a tool, don't bury CLI version handling in skill prose. Pattern: `skills/<skill>/bin/<wrapper>` symlinked to `~/.local/bin/`.
- 2026-05-11 — Adopted boil-the-lake the gstack way (full adoption, including feature scope). Folded into the Week 1 stance: build the complete useful version of `/sitrep`, not a "recent commits" stub. Recorded in handoff.
- 2026-05-11 — Codex review of gstack-borrow shortlist applied. Dropped `ETHOS.md`, `/codex` skill, `/retro`, `/triage`, and `/autoplan` as full coordinator port. Added `/work-breakdown` as the adoption bridge for Week 2.
- 2026-05-11 — `/sitrep` rolls in inbox state from day one (C and B are entangled per codex). No separate `/inbox` skill.
- 2026-05-11 — `STATUS.md` schema v1 defined. Lives at repo root; `/sitrep` is the read+write client.
