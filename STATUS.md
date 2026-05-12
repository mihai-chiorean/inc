---
status_version: 1
current_objective: "Rebrand claude-agents → inc. Phase 1 (text replacements) is this PR; Phase 2 (GitHub rename + local dir rename + symlink fixes + branch protection) happens at merge time."
active_branch: mit-363-rebrand-inc
active_pr: null
linear_issue: MIT-363
linear_team: MIT
linear_project: null
blocked_on_user: []
next_command: "Codex review the rebrand PR; then merge; then execute Phase 2 (gh repo rename + local mv + symlink fixes + branch protection); then begin Week 3b"
last_verified_state: 2026-05-12T22:00:00Z
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

Rebrand `claude-agents` → `inc`. The repo, the workspace dir, and the planned operational-state path-root (`~/.inc/projects/<slug>/` instead of `~/.claude-agents/...`) all switch. Aligns with the company-shape framing we adopted during the product-roster refactor (PM/TPM/tech-lead) — the agent setup is a small company; the repo is `inc`.

Week 3b (`plan-eng-review` lift) ships under the new name immediately after.

## What's next

1. Codex review the rebrand PR (mostly text replacements + path updates).
2. Merge.
3. Phase 2 — execute the live ops:
   - `gh repo rename inc`
   - `mv ~/workspace/claude-agents ~/workspace/inc`
   - `git remote set-url origin git@github.com:mihai-chiorean/inc.git`
   - Re-point all symlinks (`~/.claude/skills/*` and `~/.local/bin/{sitrep-linear,design-doc-scaffold}`)
   - Set branch protection on `main` (block force push + deletion; no PR-required; admin-overridable)
4. Verify: `sitrep-linear scope`, `design-doc-scaffold --help`, `/sitrep` end-to-end.
5. Begin Week 3b: `plan-eng-review` lift from gstack — strip plumbing per the scope list user approved (keep telemetry, knowledge-base path `~/.inc/projects/<slug>/`, restore points, and the Confidence Calibration sub-pattern).

## Open items needing my attention

- [decisions/0001-plan-eng-review-lift.md](decisions/0001-plan-eng-review-lift.md) — design-doc scaffold for Week 3b. All 8 sections are stubs; fill before starting Week 3b implementation.
- [MIT-345 — /sitrep --all for cross-project rollup](https://linear.app/mitzoku/issue/MIT-345/sitrep-all-for-cross-project-rollup) — side-quest from the /work-breakdown manual test. S-sized. Picks up after Week 3 ships if no higher-priority work appears.

_Live items in this section are normally populated by `/sitrep` from Linear/GitHub queries._

## Future work (not inbox)

- [research/gstack-borrow-2026-05-11.md](research/gstack-borrow-2026-05-11.md) — handoff doc. Reference for Week 3+ (`/design-doc`, `plan-eng-review`) and Week 4 (`/prioritize`).
- Project B (MIT-294–302) — fold gstack eval mechanics (touchfile diff selection + tier system + extended EvalResult schema) when picked up. Parallel track.
- **Label-based scoping for `/sitrep` (long-term direction).** v0 (MIT-362) uses Linear project names in `linear_scope`. Project-based misses orphan issues (no project assigned) and breaks if a project gets renamed or split. Long-term: every repo-relevant issue gets a label like `repo:inc` and `linear_scope` accepts a `labels:` key. Survives project moves and covers orphan/triage items. Defer until v0 friction is observed.

## Decisions log (recent)

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
