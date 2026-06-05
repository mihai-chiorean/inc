---
status_version: 1
current_objective: "Started Project B — Agent roster eval framework (MIT-294–302 + folded gstack-eval issues MIT-438/439/440). First issue MIT-294 (routing dataset schema + interactive labeling tool) in progress. The spec-conformance initiative (MIT-410→437) is fully merged."
active_branch: mit-294-routing-dataset-schema-labeling-tool
active_pr: null
linear_issue: MIT-294
linear_team: MIT
linear_project: "Agent roster eval framework"
blocked_on_user: []
next_command: "Finish + PR MIT-294 (evals/routing/ schema + label.py). Then MIT-295 (hand-label 30 prompts using the tool) → MIT-296 (judge) → MIT-297 (runner) → MIT-438 (EvalResult schema) → MIT-439 (touchfile selection) → MIT-298 (conflict detection) → MIT-299 (reports) → MIT-440 (gate/periodic CI)."
last_verified_state: 2026-06-05T20:00:00Z
linear_scope:
  # NOTE: these MUST be exact Linear project names (sitrep-linear filters on them).
  # Verify against `linear project list` before editing — invented strings get silently excluded.
  - "Agent roster eval framework"
  - "Per-project agent staffing skill"
  - "gstack borrow — workflow & onboarding docs"
  - "gstack borrow — eval mechanics (parallel to Project B)"
  - "gstack borrow — Week 1: bootstrap loop"
  - "gstack borrow — Week 2: /work-breakdown"
  - "gstack borrow — Week 3: planning discipline"
  - "gstack borrow — Week 4: /prioritize"
links:
  initiative: https://linear.app/mitzoku/initiative/gstack-borrow-4e2936810b96
  project: null
  handoff: research/gstack-borrow-2026-05-11.md
---

# inc status

## Current objective

Agent/skill spec-conformance + canonicalization initiative (MIT-410→437). Grounded in the MIT-410 research artifact (Anthropic agent/skill spec ground truth). Validator + frontmatter rewritten to match the spec (MIT-412/413/414), ~57 agents rewritten to canonical v3 shape (MIT-415), now in per-field refinement (allowed-tools sweep, Output Format / Obstacles sections, aspirational-closing trim + prompt-shaping) plus new skills (/cso).

**Session of 2026-06-05: cleared the open-PR queue.** All 5 open PRs reviewed (one general-purpose review agent each) and merged to main — see decisions log for the order and the rebase mechanics.

## What's next

**Project B is started.** MIT-294 (routing dataset schema + labeling tool) in progress on `mit-294-routing-dataset-schema-labeling-tool` — `evals/routing/{dataset.yaml,label.py,test_label.py,README.md}`. Sequence:

1. **MIT-294** (in progress) — `evals/routing/dataset.yaml` schema + `label.py` incremental labeling tool. PR pending.
2. MIT-295 — hand-label 30 routing prompts using the tool (20 clear / 7 adversarial / 3 NONE).
3. MIT-296 (judge config) → MIT-297 (eval runner) → **MIT-438** (extended EvalResult schema, foundational) → **MIT-439** (touchfile diff selection) → MIT-298 (conflict detection) → MIT-299 (reports) → **MIT-440** (gate/periodic CI).

Side backlog (not Project B): MIT-374 (non-symlink skill-dir conflict detection), MIT-345 (/sitrep --all). The 5-PR review nits were fixed in PR #55, not deferred.

## Open items needing my attention

- MIT-294 PR (pending) — review + merge once opened.
- Backlog: rest of Project B (MIT-295–302, MIT-438/439/440), MIT-374, MIT-345.

_Live items in this section are normally populated by `/sitrep` from Linear/GitHub queries._

## Future work (not inbox)

- [research/gstack-borrow-2026-05-11.md](research/gstack-borrow-2026-05-11.md) — handoff doc. Reference for Week 3+ (`/design-doc`, `plan-eng-review`) and Week 4 (`/prioritize`).
- Project B gstack-eval mechanics — now tracked as issues: [MIT-438](https://linear.app/mitzoku/issue/MIT-438) (extended EvalResult schema + persistence + auto-compare), [MIT-439](https://linear.app/mitzoku/issue/MIT-439) (touchfile diff selection), [MIT-440](https://linear.app/mitzoku/issue/MIT-440) (gate/periodic tiers + CI). Sequenced after the core runner; see "What's next".
- **Workflow & onboarding docs** ([project](https://linear.app/mitzoku/project/gstack-borrow-workflow-and-onboarding-docs-074488a4d805)) — three issues queued for after Week 3b ships: MIT-364 (workflow walkthrough), MIT-365 (project bootstrap), MIT-366 (skill catalog). Audience: future-me 6-months-out + outside reader getting-started. Lives in `docs/` (probably `docs/getting-started/{workflow,bootstrap}.md` + `docs/reference/skills.md`). Specialist: plan-devex-review will review the developer-experience side.
- **Label-based scoping for `/sitrep` (long-term direction).** v0 (MIT-362) uses Linear project names in `linear_scope`. Project-based misses orphan issues (no project assigned) and breaks if a project gets renamed or split. Long-term: every repo-relevant issue gets a label like `repo:inc` and `linear_scope` accepts a `labels:` key. Survives project moves and covers orphan/triage items. Defer until v0 friction is observed.

## Decisions log (recent)

- 2026-06-05 — **Started Project B (Agent roster eval framework).** Created 3 issues folding the gstack eval mechanics into the project: MIT-438 (extended EvalResult schema — precision/recall/F1, expected/suggested IDs, FP/FN, judge metadata, persisted + auto-compare), MIT-439 (touchfile-driven diff selection), MIT-440 (gate/periodic tiers + CI), each cross-linked to the core issues (MIT-297/298/299) and assigned to me. Granularity chosen: 3 new issues over augmenting existing ones (user call). Began MIT-294 (routing dataset schema + interactive labeling tool) — built `evals/routing/{dataset.yaml,label.py,README.md,test_label.py}` via a general-purpose agent against a detailed spec. Note: the natural owner (agent-eval-engineer) is an HR-repo definition not spawnable in this session's subagent set, so used general-purpose. `linear_scope` fix (PR #56) was required first — #54 had broken it with invented project names, silently gutting the inbox.
- 2026-06-05 — **Cleared the 5-PR open queue.** Reviewed all five in parallel (one general-purpose review agent each) — all APPROVE / APPROVE-WITH-NITS, no blocking content issues. Merge order **#49 → #53 → #51 → #50 → #52**: #49 (skill portability, scripts/skills) and #53 (/cso skill) are independent; #53 needed a rebase (branch was 52 commits behind main). The trio #50/#51/#52 overlap heavily (all edit `infra-reviewer`/`feedback-synthesizer`/`test-results-analyzer`/`legal-compliance-checker` + others; #50 & #52 regen the manifest) so they could NOT merge in parallel — serialized with a rebase between each. Only real conflict was `agent.manifest.yaml` on #52 (#50 vs #52 body_hash collision); resolved by regenerating the manifest from the merged `.md` tree rather than hand-merging the derived file. `.md` files auto-merged cleanly (frontmatter/body regions disjoint). Validator 0 hard-fail + manifest zero-drift + 10/10 staff test files green at each step and on final main. Base-branch ruleset required `--admin` to merge each PR (CI was green; enforce_admins=false).
- 2026-06-05 — **Incident + CLAUDE.md Rule 2 amendment.** A review agent ran `git checkout` in the *main* working tree (not an isolated worktree), leaving it on a detached HEAD and silently reverting in-flight STATUS.md/CLAUDE.md edits twice. Added a caution to Rule 2: fan-out review/inspection agents must read diffs (`gh pr diff`) or use isolated worktrees, never switch branches in place. Same commit makes roster delegation the *default* (no need for the user to ask) and notes parallel fan-out.
- 2026-05-12 — **gstack-borrow initiative complete.** All four weeks merged today: Week 3b (PR #25, /plan-eng-review + audit wrapper, recursive v0 test passed), workflow + onboarding docs (PR #26, MIT-364/365/366), Week 4 (PR #27, /prioritize). Plus the rebrand to `inc` (PR #24 + Phase-2 live ops). Six PRs merged, six skills shipped total. 24 skills now in the catalog. Pipeline composes end-to-end: /sitrep → /work-breakdown → /design-doc → /plan-eng-review → code → /prioritize → repeat.
- 2026-05-12 — Applied `/work-breakdown` to the "document the workflow" ask. Classified M. Created Linear project "gstack borrow — workflow & onboarding docs" + 3 issues (MIT-364/365/366). Sequenced AFTER Week 3b ships per user preference — Week 3b finishing means the docs can describe a complete skill set + use the recursive plan-eng-review-audits-its-own-doc story as a worked example. Audience: future-me 6-months-out + outside getting-started reader.
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
