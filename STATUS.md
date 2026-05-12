---
status_version: 1
current_objective: "Week 3b — plan-eng-review skill lift. Design doc filled in this commit; next session builds SKILL.md + plan-eng-review-audit wrapper + telemetry/restore-point infrastructure. Manual test = recursively audit decisions/0001-plan-eng-review-lift.md."
active_branch: mit-348-plan-eng-review
active_pr: null
linear_issue: MIT-348
linear_team: MIT
linear_project: https://linear.app/mitzoku/project/gstack-borrow-week-3-planning-discipline-bba4630036be
blocked_on_user: []
next_command: "Build skills/plan-eng-review/SKILL.md + bin/plan-eng-review-audit per the design doc; recursive test by auditing decisions/0001-plan-eng-review-lift.md"
last_verified_state: 2026-05-12T22:30:00Z
linear_scope:
  - "gstack borrow — Week 1: bootstrap loop"
  - "gstack borrow — Week 2: /work-breakdown"
  - "gstack borrow — Week 3: planning discipline"
  - "gstack borrow — Week 4: /prioritize"
  - "gstack borrow — eval mechanics (parallel to Project B)"
  - "Per-project agent staffing skill"
  - "Agent roster eval framework"
links:
  initiative: https://linear.app/mitzoku/initiative/gstack-borrow-4e2936810b96
  project: null
  handoff: research/gstack-borrow-2026-05-11.md
---

# inc status

## Current objective

Week 3b of gstack-borrow — `plan-eng-review` skill lift. The auditor that hard-gates design docs against missing diagrams + REPLACE stubs + empty failure-modes tables, mutating `status: draft → accepted` on pass.

**Design doc filled in this commit** (`decisions/0001-plan-eng-review-lift.md`, 284 lines). Specifies: Approach B (hybrid Python wrapper + SKILL.md), telemetry to `~/.inc/projects/<slug>/telemetry.jsonl`, pre-mutation restore points, 11 named failure modes with exit codes, REPLACE-detection precision (parser, not regex).

Next session implements per that design.

## What's next

1. Build `skills/plan-eng-review/bin/plan-eng-review-audit` (Python wrapper, ~300 LOC). Mechanical checks per the failure-modes table; YAML frontmatter parse; section/diagram/table/list inspection; REPLACE-detection with backtick-span awareness; telemetry + restore-point write; exit-code contract 0/1/2/3.
2. Build `skills/plan-eng-review/SKILL.md` (procedural overlay for qualitative review).
3. Recursive manual test — audit `decisions/0001-plan-eng-review-lift.md` itself. Expected: PASS (doc is filled).
4. Codex review.
5. PR.

## Open items needing my attention

- [decisions/0001-plan-eng-review-lift.md](decisions/0001-plan-eng-review-lift.md) — design doc for Week 3b, **now filled in** (284 lines). Awaiting the auditor (Week 3b implementation) before status can move from `draft` to `accepted`.
- [MIT-345 — /sitrep --all for cross-project rollup](https://linear.app/mitzoku/issue/MIT-345/sitrep-all-for-cross-project-rollup) — side-quest from the /work-breakdown manual test. S-sized. Picks up after Week 3 ships if no higher-priority work appears.

_Live items in this section are normally populated by `/sitrep` from Linear/GitHub queries._

## Future work (not inbox)

- [research/gstack-borrow-2026-05-11.md](research/gstack-borrow-2026-05-11.md) — handoff doc. Reference for Week 3+ (`/design-doc`, `plan-eng-review`) and Week 4 (`/prioritize`).
- Project B (MIT-294–302) — fold gstack eval mechanics (touchfile diff selection + tier system + extended EvalResult schema) when picked up. Parallel track.
- **Label-based scoping for `/sitrep` (long-term direction).** v0 (MIT-362) uses Linear project names in `linear_scope`. Project-based misses orphan issues (no project assigned) and breaks if a project gets renamed or split. Long-term: every repo-relevant issue gets a label like `repo:inc` and `linear_scope` accepts a `labels:` key. Survives project moves and covers orphan/triage items. Defer until v0 friction is observed.

## Decisions log (recent)

- 2026-05-12 — Filled in design doc for Week 3b (`decisions/0001-plan-eng-review-lift.md`, 284 lines). Chose Approach B (hybrid wrapper + SKILL.md). Surfaced one design refinement while writing: REPLACE-detection needs a parser (not a regex), since this doc itself contains 8 meta-references to the literal token `REPLACE` in backtick-quoted prose. Captured as open question + updated failure-mode row.
- 2026-05-12 — Rebrand complete (MIT-363). Phase 1 PR #24 merged; Phase 2 (gh repo rename → inc, mv workspace dir, 25 symlinks repointed, branch protection on main) executed live. enforce_admins=false, allow_force_pushes=false, allow_deletions=false.

- 2026-05-12 — Rebrand: `claude-agents` → `inc`. Storage-path-root: `~/.inc/projects/<slug>/`. `agent.manifest.yaml` keeps `source_repo: claude-agents` as a stable logical identifier (backward compat with lab-control's lockfile; migrate separately if/when needed).
- 2026-05-12 — Revised Week 3b strip-list after pushback: KEEP telemetry (adapted to write `~/.inc/projects/<slug>/telemetry.jsonl`), KEEP the non-git knowledge-base pattern, KEEP restore points, lift the Confidence Calibration sub-pattern from gstack's Voice section. Strip the rest of Voice + Writing Style + Question Tuning + gstack-specific Outside Voice + review-log + telemetry binary.
- 2026-05-12 — Observed during `/sitrep`: inbox leaked transcribe.py / wendy / X-Y items across repos. Root cause: Linear has no "issue belongs to repo" link; one MIT team, many repos. Added `linear_scope` to STATUS.md schema v1.1 (backward-compat — empty/missing = current behavior). Long-term direction is label-based (see Future work).
- 2026-05-11 — Week 3a merged (PR #22, MIT-347). `/design-doc` skill + `design-doc-scaffold` wrapper + `decisions/` established as ADR location.
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
