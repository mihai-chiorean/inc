# Workflow — a day in the life of `inc`

> Audience: future-me, six months out, returning cold. Secondary: an outside reader who just cloned the repo and wants to understand the shape before they touch anything.
>
> This doc is the **narrative**. For the per-skill reference, see the [skill catalog](../reference/skills.md). For first-machine setup, see the [bootstrap guide](./bootstrap.md).

The shortest possible summary: every session starts with `/sitrep`, every non-trivial idea goes through `/work-breakdown`, M-sized work *recommends* a design doc audited by `/plan-eng-review` (L+ *requires* both), every PR is one Linear issue, and `STATUS.md` is the contract that survives between sessions. The rest of this document is why those moves exist in that order, and what each one actually does for you on a Tuesday morning.

---

## 1. The mental model

`inc` is a private engineering company. The vocabulary is deliberate.

- **HR / roster.** [`agent.manifest.yaml`](../../agent.manifest.yaml) at the repo root is the canonical list of every specialist agent. The `inc` repo *is* the HR department — agents are version-controlled here, then staffed per-project into `.claude/agents/` by the [`/staff`](../../skills/staff/SKILL.md) skill so each project loads only the people it actually needs.
- **Specialists own depth.** A specialist agent is a sub-agent with its own context window and a sharp domain — `tech-lead` for architecture-with-named-tradeoffs, `product-manager` for end-user-facing scope calls, `tpm` for cross-team coordination, plus the long tail (`swift-concurrency`, `database-driver-design`, `security-auditor`, etc.). They are *roles*. You spawn them via the Agent tool.
- **Skills own procedure.** A skill is a procedural overlay — a markdown file with a trigger and a series of steps that the orchestrator (Claude Code in the parent session) executes. `/sitrep`, `/work-breakdown`, `/design-doc`, `/plan-eng-review` are skills. They are *playbooks*. You invoke them via the Skill tool.
- **The split is load-bearing.** When you need a domain (Swift backend, security review, a Hummingbird endpoint), you route to a specialist. When you need a procedure (orient at session start, classify the size of new work, audit a design doc), you fire a skill. The split is restated verbatim in [CLAUDE.md Rule 2](../../CLAUDE.md): *"Specialists own depth. Skills own procedure."*

### Why this exists vs. a generic AI dev setup

The generic AI dev setup is one big agent with one big prompt and one big context window. You ask it to do everything. It does most of it adequately and a few things badly, and you spend half your day re-orienting it.

`inc` started from a specific pain bucket — see [research/gstack-borrow-2026-05-11.md](../../research/gstack-borrow-2026-05-11.md) for the long version. The headline:

1. Pain C — every session opened with Claude completely unoriented; manual sitrep dance.
2. Pain D — multi-step "idea → initiative → projects → PR-issues" lived in the user's head, not codified.
3. Pain B — Linear-as-inbox wasn't actually lived; design docs and PRs vanished into tmux tabs.
4. Pain A — the procedural moves (3 diagrams per design doc, codex review ×N, test coverage) were ad-hoc.

The gstack-borrow initiative is what's fixing those, in that order. The current state of the world (Week 3b complete) is: there is a session bootstrap (`/sitrep`), a work-breakdown procedure (`/work-breakdown`), and a planning gate (`/design-doc` + `/plan-eng-review`). Week 4 (`/prioritize`) and the deferred items (ETHOS.md, `/retro`, `/codex` as a skill) are next.

The setup is **deliberately built for one engineer**. The vocabulary borrows from engineering-org metaphors (HR, specialists, TPM) because the procedure is org-shaped, not because there is a team. Singular subject, plural roster.

### How the layers compose, in one sentence each

- [CLAUDE.md](../../CLAUDE.md) — six operating rules. Auto-loaded at session start. Every rule has earned its place by closing a failure mode.
- [STATUS.md](../../STATUS.md) — the session-state contract. Per-project, at repo root. Read+written by `/sitrep`.
- Skills (`skills/<name>/SKILL.md`) — procedures, loaded by Claude Code when their trigger matches.
- Agents (`agent.manifest.yaml` → `.claude/agents/`) — specialists, staffed per-project by `/staff`.
- `decisions/NNNN-<slug>.md` — design docs (ADR-numbered).
- `~/.inc/projects/<slug>/` — per-project telemetry + restore points (see §6).

> **Next action:** open [CLAUDE.md](../../CLAUDE.md) and read the eight rules end-to-end. They are short on purpose. Everything that follows in this doc is a worked example of those rules in action.

---

## 2. Session start — `/sitrep`

You open Claude Code in `~/workspace/inc` (or any project that has a `STATUS.md`). The first thing that should happen is `/sitrep`. CLAUDE.md Rule 1 makes this explicit: *"On session start, run or offer `/sitrep` before doing other work."*

### What it actually does

[`/sitrep`](../../skills/sitrep/SKILL.md) is the read+write client for `STATUS.md`. It does five things in one pass, in parallel where it can:

1. **Reads `STATUS.md`** — both the YAML frontmatter (machine-readable: `active_branch`, `linear_issue`, `next_command`, `last_verified_state`, etc.) and the four narrative body sections (`## Current objective`, `## What's next`, `## Open items needing my attention`, `## Decisions log (recent)`). The schema lives at [`skills/sitrep/docs/status-schema.md`](../../skills/sitrep/docs/status-schema.md).
2. **Gathers live state** — git branch + uncommitted changes, recent commits, Linear issues assigned to you (scoped by `linear_scope` — see §6), GitHub PRs awaiting your review, your own open PRs, and the PR (if any) for the current branch. All Linear reads go through the `sitrep-linear` wrapper which hides Linear CLI v1/v2 differences and team-key resolution.
3. **Reconciles** — compares `STATUS.md` frontmatter against live state. If the branch on disk disagrees with `active_branch`, that's surfaced. If a PR was opened since the last sitrep, that's surfaced. If `linear_issue` is marked complete in Linear, that's surfaced.
4. **Surfaces the landing page** — a fixed-format output (see below) you've learned to scan in three seconds.
5. **Prompts to write back** — `last_verified_state` → now, `active_branch`/`active_pr` → live state, any new decisions or blockers you dictate. Diff-update, not rewrite, so human edits and trailing notes are preserved.

### The landing page

The output uses exactly these labels — they're stable so you can scan them by shape:

```
=== sitrep: inc ===
Branch:    mit-348-plan-eng-review  →  MIT-348 [started]
PR:        none
Objective: Week 3b — plan-eng-review skill lift

▎ NEXT
  → Build skills/plan-eng-review/SKILL.md + bin/plan-eng-review-audit per the design doc;
    recursive test by auditing decisions/0001-plan-eng-review-lift.md

▎ BLOCKED ON YOU — clear

▎ INBOX (2 issues, 0 PRs for review)
  • MIT-345 [P3] /sitrep --all for cross-project rollup
  • MIT-364 [P3] Workflow overview doc — day-in-the-life walkthrough

▎ YOUR OPEN PRS (0)

▎ RECENT DECISIONS
  • 2026-05-12 — Filled in design doc for Week 3b (0001-plan-eng-review-lift.md, 284 lines)
  • 2026-05-12 — Rebrand complete: claude-agents → inc
  • 2026-05-12 — Revised Week 3b strip-list after pushback

Last verified: 2026-05-12T22:30:00Z  (just now)
```

The reason this is the landing page and not a status report: it's **operational**. The next move is on screen. The inbox is what's blocking *you*, not a global todo. "Blocked on you" is a separate section so it can't hide.

### What it does NOT do (v0)

- No cross-project rollup. `/sitrep --all` is queued as MIT-345.
- No automatic specialist dispatch. It surfaces review items; it doesn't route them.
- No notifications. You run `/sitrep` when you want it.
- No CI flake analysis. It reports `statusCheckRollup` and stops.

These are deferred to v1+ if v0 friction warrants. See [skills/sitrep/SKILL.md](../../skills/sitrep/SKILL.md#what-sitrep-v0-does-not-do-yet) for the full list.

### When STATUS.md is missing

`/sitrep` offers to bootstrap one. It can seed `active_branch` from `git branch --show-current`, `linear_issue` from the branch name (`mit-348-...` → `MIT-348`), and prompts for `current_objective`. The result is a valid v1 status file you can iterate on. See [bootstrap guide](./bootstrap.md) for the full per-project setup.

> **Next action:** run `/sitrep` now. If there's no `STATUS.md` in this project, let it bootstrap one. The contract only works if it exists.

---

## 3. New idea — `/work-breakdown`

You've sitrepped. You're oriented. Now an idea lands — either yours, or something a specialist surfaced, or a Linear issue you just remembered. It's bigger than a one-line fix.

CLAUDE.md Rule 4: *"When the user plans or queues new work that is more than a one-line fix — phrases like 'let's build', 'we should ship', 'I want to start on', 'how do we break this down' — invoke `/work-breakdown` before writing code."*

The trigger is **planning intent**, not size alone. If you've already classified the work and are asking for immediate execution ("just implement X"), `/work-breakdown` does not fire. If you're unsure, the rule says ask one clarifying question: *"Is this one PR or should we break it down?"*

### What [`/work-breakdown`](../../skills/work-breakdown/SKILL.md) does

Three things:

1. **Classifies** the ask: S / M / L / XL.
2. **Creates Linear artifacts** at the right granularity.
3. **Recommends** specialist agents to bring in and planning gates to satisfy.

It does *not* do the work. It does not auto-route to specialists. It does not estimate effort. It does not track the work once it starts (that's `/sitrep`'s job).

### The four sizes

| Size | Scope | Linear shape | Required gates |
|---|---|---|---|
| **S** | Single PR, single concern, ≤ 1 day | 1 issue | None |
| **M** | Multiple PRs in one area, single coherent feature | 1 project + N issues (one per PR) | Design-doc recommended |
| **L** | Multiple projects, cross-cutting | 1 initiative + M projects + N issues | Design-doc **required** + plan-eng-review **required** |
| **XL** | Multi-repo or multiple initiatives | L set + cross-repo coordination doc | All L gates + coordination doc |

The skill *proposes* a default size with one-line justification, then asks you to confirm or override. It applies a fixed set of tie-breakers (multi-repo dependency, public API/schema change, data migration, security risk, production rollout, ambiguity scope, multiple specialists, external deadline). Number of PRs alone and "feels big" are explicitly **not** tie-breakers.

### When to call PM vs. tech-lead vs. plan-devex-review

The volume rule of thumb:

- **S:** none.
- **M:** zero or one. Usually `plan-devex-review` alone for skill work, often none for refactors.
- **L:** one or two — the named-tradeoff lens (`tech-lead`) plus the end-user lens (`product-manager` or `plan-devex-review`).
- **XL:** `tpm` always, plus the L set.

The sharp criteria for each (paraphrased from the skill):

- **`product-manager`** — the intended end-user is a **non-developer human** AND the change affects what they see or do. NOT for dev-tool / internal-CLI / engineering-only work.
- **[`/plan-devex-review`](../../skills/plan-devex-review/SKILL.md)** (skill, not agent) — developer-facing surface. CLI flag, library API, SDK, framework, skill, dev tool. Most of `inc`'s own work falls here.
- **`tech-lead`** — architecture decision with **named tradeoffs** (two or more credible approaches), performance bet, or cross-cutting refactor. Not "M means call tech-lead."
- **`tpm`** — cross-team or cross-repo coordination. Always for XL.

The recommendation is **explicit**. If zero specialists are recommended, the skill says so out loud — silent zero feels like an omission.

### Worked example: the four size paths

Real examples from this repo's recent history.

#### S — "add `--all` to /sitrep so I can roll up all projects"

This is MIT-345. One skill, one flag, no new abstractions. The skill output:

```
=== /work-breakdown ===
Ask:    Add --all flag to /sitrep for cross-project rollup.
Size:   S  —  Single skill enhancement, one PR, no new abstractions.

Linear created:
  • Issue — Add /sitrep --all for cross-project rollup  →  MIT-345

Specialists to call: none.
Gates required: none.

Next command suggestion:
  → linear issue start MIT-345
```

#### M — "build a /retro skill that runs at end of sprint"

Three PRs in one area: skill core, cleanup-action templates, codex review wiring.

```
=== /work-breakdown ===
Ask:    Build /retro skill — end-of-sprint reflection that produces Linear cleanup actions.
Size:   M  —  Project with ~3 PRs (skill core, cleanup-action templates, codex review wiring).

Linear created:
  • Project   — /retro skill  →  <URL>
  • Issue 1   — /retro v0 skill (core procedure + AskUserQuestion flow)
  • Issue 2   — Linear cleanup action templates
  • Issue 3   — Wire codex review into /retro output

Specialists to call (your choice):
  • product-manager  —  the "what makes a retro useful" question
  • tech-lead        —  cleanup-action persistence design

Gates required:
  • /design-doc recommended (multiple PRs touching similar surface).
  • plan-eng-review on first PR.

Next command suggestion:
  → Spawn product-manager on Issue 1 ("what makes a retro useful")
```

#### L — "replace Linear-CLI v1 dependency across all our skills with a unified internal client"

Cross-cutting; affects every skill that touches Linear. Initiative-shaped because more than three projects of work.

```
=== /work-breakdown ===
Ask:    Replace Linear v1 CLI dependency with a unified internal client.
Size:   L  —  Cross-cutting; affects every skill that touches Linear; initiative-shaped.

Linear created:
  • Initiative — Unified Linear client across skills  →  <URL>
  • Project 1  — Client library + manifest contract
  • Project 2  — Migrate /sitrep + /work-breakdown
  • Project 3  — Migrate future skills (retro, prioritize, design-doc)
  (Issues per project to be created via /work-breakdown on each.)

Specialists to call (your choice):
  • tech-lead        —  client API design + manifest contract
  • product-manager  —  is this worth doing now vs deferring?

Gates required:
  • /design-doc required.
  • plan-eng-review on every M+ PR.

Next command suggestion:
  → Spawn product-manager to challenge: is this the highest-leverage L right now?
```

#### XL — multi-repo coordination

The gstack-borrow initiative itself was the worked XL example, except it was decomposed before `/work-breakdown` existed. The shape is the same as L plus:

- A coordination doc (Linear document, or `research/<name>-coordination.md` in the lead repo).
- The doc names every repo touched, the order of changes (which repo lands first, what depends on what), and the rollback path.
- `tpm` is mandatory.

### After-the-fact: side quest vs. new focus

After creating artifacts, `/work-breakdown` updates `STATUS.md`. Two cases:

- **Case A — new active focus.** The ask becomes the project's main thread. `current_objective`, `linear_issue`, `linear_project`, `next_command` all get replaced. A dated entry lands in the decisions log.
- **Case B — side quest.** The new ask doesn't replace the current thread. The artifact lands in "Open items needing my attention"; `current_objective` and friends stay put.

The skill applies a three-question test: (1) is the new ask unrelated to `current_objective`? (2) Is the user *not* asking to switch right now? (3) Would changing `next_command` lose the current thread? If all three are yes → side quest.

MIT-345 (the `/sitrep --all` ask above) is the canonical side quest example — it was Case B, surfaced during a `/work-breakdown` manual test, parked in Open Items, current objective (Week 2 ship) untouched.

> **Next action:** the next time you say "let's build X" out loud or in chat, fire `/work-breakdown`. Even if X turns out to be S, the skill produces a useful single issue and the side-quest test fires correctly. When the signal is ambiguous (planning intent vs. immediate execution), ask one clarifying question first ("is this one PR or should we break it down?") per CLAUDE.md Rule 4 — do NOT default to firing on every implementation request.

---

## 4. Design-doc discipline — `/design-doc` + `plan-eng-review`

`/work-breakdown` told you you need a design doc (or recommended one for M, or required one for L/XL). This is where Pain A — the procedural moves — gets enforced.

The split is deliberate: **one skill creates, one skill audits.** Don't blend them.

### Why the discipline exists at all

The 3-diagram requirement (user-flow + state-machine + data-flow) is lifted from gstack's `plan-ceo-review` Prime Directive #6. It's the load-bearing thing we explicitly adopted. The reason it's load-bearing: design docs without diagrams are forests of bullets that all look coherent. Diagrams force you to commit to actual paths — and to name the non-happy ones.

Without an audit gate, every required section can be a `REPLACE` stub and the doc is structurally identical to a filled one. *"Looks filled in to a human who skimmed it once"* is the failure mode. `plan-eng-review` is what turns that into a binary yes/no.

### When to create a design doc

[`/design-doc`](../../skills/design-doc/SKILL.md) fires when:

- You say "design doc" / "let me write a design doc" / "scaffold a design doc for X".
- `/work-breakdown` recommended a design-doc gate (M+ classification).
- You're about to start coding an L or XL piece of work with no design doc on record (proactive offer).
- Codex or a specialist review surfaces a missing-design-doc concern.

It does **not** fire when you're updating an existing design doc (that's a regular edit) or asking for the *contents* of a doc from scratch (this skill scaffolds the shape; you or a specialist fill the contents).

### The 8-section template

Every doc scaffolded by `/design-doc` lands at `decisions/NNNN-<slug>.md` (the ADR-numbered pattern, sequential 4-digit prefix, slug derived from the title). The next number is computed by the `design-doc-scaffold` wrapper; the wrapper refuses to overwrite an existing file without `--force`.

The eight required sections:

| # | Section | Purpose | Mandatory? |
|---|---|---|---|
| 1 | Problem | What hurts today, who feels it. | Yes |
| 2 | Goals / Non-goals | Observable success + scope guardrails. Includes a Verification subsection. | Yes |
| 3 | Implementation alternatives | ≥ 2 approaches with effort/risk/pros/cons. | Yes |
| 4 | User flow diagram (ASCII) | Happy path + ≥ 1 branch. | Yes |
| 5 | State machine (ASCII) | States + transitions + invalid transitions. | Yes if any stateful object; explicit "N/A — why" otherwise |
| 6 | Data flow diagram (ASCII) | Four paths: happy, nil, empty, upstream error. | Yes |
| 7 | Failure modes table | Every error has a name + trigger + catcher + user surface + tested?. | Yes |
| 8 | Open questions | What the design doesn't yet answer + by-when. | Yes |
| (9) | Appendix | Anything else (links, raw notes, rejected alternatives). | Optional |

### The three mandatory diagrams

The diagrams are the load-bearing additions, and they each have a specific job:

- **User flow** — must include the happy path **and at least one branch**. A linear flow means unstated assumptions.
- **State machine** — must name the **invalid transitions** explicitly, not just the legal ones. Every state has a "what prevents bad transitions" mechanism. If the design has no stateful object, say so with a reason.
- **Data flow** — must cover all four paths: **happy, nil, empty, upstream error**. A missing path is a future bug.

The diagrams are ASCII art. They are intentionally not auto-generated — auto-generated diagrams drift; intentional ones don't.

### Fail loud — what `/design-doc` does NOT do

Per CLAUDE.md Rule 6, the skill surfaces what was skipped:

- The file was created but **no sections are filled** — the doc is a shell, not a design.
- Diagrams are stubs; you must replace them with real ASCII art.
- No audit ran; that's `plan-eng-review`'s job.

These caveats appear *inline with the success message*, not in a separate paragraph.

### The audit gate — [`/plan-eng-review`](../../skills/plan-eng-review/SKILL.md)

After you fill the doc, the audit runs in two layers.

#### Mechanical layer (deterministic, Python wrapper)

`plan-eng-review-audit --mechanical-only <doc-path>` does the checks that can be programmed:

- Frontmatter parses as YAML.
- All 8 H2 sections are present with the expected titles.
- No `REPLACE` tokens appear as actual stub content (the parser distinguishes backtick-quoted prose mentioning the token from real stubs).
- All three diagram code blocks contain non-stub content.
- Failure-modes table has ≥ 1 data row.
- Open questions has ≥ 1 list item.
- Status transition is legal (`draft → accepted`, `in-review → accepted`, `issues_open → accepted`; refuses `accepted → accepted`, `superseded → *`, etc.).

Exit codes: `0` PASS, `1` IO error, `2` malformed frontmatter / illegal transition, `3` mechanical FAIL with gap list.

#### Qualitative layer (judgment, SKILL.md procedure)

Six lenses, each lifted from gstack's plan-eng-review:

1. **Scope challenge** — is the Problem premise correct? Is the scope right-sized? Are non-goals honestly named or just "things we forgot"?
2. **Architecture review** — does the chosen approach actually solve the goals? Are the named tradeoffs real or generic? Does the user-flow cover at least one non-happy branch? Does the state-machine name invalid transitions? Does the data-flow cover all four paths?
3. **Test review** — does Verification have observable success criteria? Do the failure modes named in section 7 have plausible test paths?
4. **Failure-mode critical-gap registry** — for each row in section 7: is the trigger concrete? Does something actually catch it? Does the user see a specific message OR a silent state change (silent = critical defect per Rule 6)? Is `Tested?` resolved? ≥ 1 critical gap → qualitative FAIL.
5. **Stale-diagram audit** — if the doc references existing code files, grep them for ASCII diagrams and check whether they still match current behavior.
6. **Confidence calibration** — every qualitative finding states confidence (High = verified against code; Medium = inferred from doc only; Low = guess). A "high-confidence pass with no checking" is worse than a "medium-confidence pass with named uncertainty."

#### Commit the audit

On both PASS, the skill asks before mutating. On `yes`, `plan-eng-review-audit <doc-path>` (no flag) runs the full pipeline:

1. Writes a pre-mutation snapshot to `~/.inc/projects/<slug>/restore/<datetime>-<basename>.md`. **This is required**; if the restore write fails, the audit aborts with exit 1 and the doc is not mutated. Acceptance without rollback is unsafe.
2. Mutates frontmatter `status: <current> → status: accepted`.
3. Appends a JSONL telemetry event to `~/.inc/projects/<slug>/telemetry.jsonl` (best-effort; stderr warning on failure, audit still PASSes).

The `accepted` status is now persistent. Coding may begin.

### The recursive example

[`decisions/0001-plan-eng-review-lift.md`](../../decisions/0001-plan-eng-review-lift.md) is the canonical filled-in example to point at. It's the design doc for the `plan-eng-review` skill itself — and it was audited by that same skill on its first run (the recursive setup). The doc has all 8 sections, all 3 diagrams, an 11-row failure-modes table with named exit codes, and an explicit Verification subsection with observable criteria. Read it once; it's the shape every other design doc in `decisions/` should look like.

### What `plan-eng-review` does NOT do

- Audit non-design-docs (READMEs, research handoffs, blog drafts).
- Re-audit on save (manual invocation only).
- Block PRs (v0 is solo-engineer discipline; the `--mechanical-only` mode is CI-shaped but not wired).
- Fix the doc (reports gaps; the user fixes them).
- Run an "outside voice" subagent (gstack has one; we already do codex review separately on PRs).

> **Next action:** the next time `/work-breakdown` recommends a design-doc gate, run `/design-doc` immediately — don't wait for "later." Fill it. Then audit it with `/plan-eng-review`. If the audit fails, the gap list is the to-do list.

---

## 5. Coding the work

You have an accepted design doc. Now the actual code.

> **Note:** this section assumes the ticket is implementation-shaped. For investigation, spike, audit, or "figure out X" tickets, the deliverable is a markdown report attached to the Linear issue — see §6's "Ticket shape: implementation vs investigation" subsection.

The conventions here are *not* in CLAUDE.md yet — they're stated explicitly in the [Defer](../../CLAUDE.md#defer-not-in-this-claudemd-yet) section: codex review × N rounds and the coverage gate live by convention, not by rule. They get promoted into CLAUDE.md only if their absence costs real time. They haven't yet, so they don't.

That said, the actual lived convention this repo has settled on:

### Branch convention — `mit-NNN-slug`

One branch per Linear issue. Format: `mit-<issue-number>-<short-slug>`. Examples from the last sprint:

- `mit-343-week1-bootstrap-loop`
- `mit-344-work-breakdown`
- `mit-347-design-doc`
- `mit-348-plan-eng-review`

The Linear number prefix is load-bearing — `/sitrep` parses it out of `git branch --show-current` to infer `linear_issue` when bootstrapping a STATUS.md. The slug is for humans; keep it short and recognizable.

### One issue per PR

Every PR closes exactly one Linear issue. This is the unit. If a piece of work needs more than one PR, it's M+ and `/work-breakdown` should have created multiple issues under a project. If you find yourself wanting to land two issues in one PR, the issues were probably wrong-sized — back to `/work-breakdown`.

PR title and description follow the [commit-pr-etiquette](../../skills/commit-pr-etiquette/SKILL.md) skill. The recent merged PRs show the shape: `Week 3b of gstack-borrow: /plan-eng-review skill (audits design docs) (#25)`, `Week 2 of gstack-borrow: /work-breakdown skill (adoption bridge for pain D) (#20)`. Phrase = `<week or scope>: <skill> (<one-line>)`.

### Codex review × N rounds before merge

The convention is iterative codex review. Specifically:

1. Open the PR.
2. Run codex review on the diff.
3. Address the feedback (substantively — Rule 5: pick or push back, don't blend).
4. Re-run codex on the updated diff.
5. Repeat until codex returns a clean pass *or* you've explicitly logged why a flagged item is being deferred.

Recent PRs show this pattern in their commit history — `b34f256` is *"Address codex review on load-semantics doc"*, `a2d70df` is *"Address codex round-2 on /staff sync"*. Two-to-three rounds is typical; one round is suspicious unless the diff is trivial.

The reason this isn't in CLAUDE.md yet: it's a convention that hasn't been broken visibly enough to need a rule. The day someone (you, future-me) ships a PR without codex review and it bites, this rule gets promoted.

### Conflict surfacing during review

When codex disagrees with your own analysis, CLAUDE.md Rule 5 fires. Don't blend; pick one explicitly:

1. State both positions in one sentence each.
2. Pick one — usually the more recent, the more tested, or the one matching explicit user preference.
3. Flag the other as a follow-up — Linear issue, `decisions/` entry, or at minimum a line in the next commit message.

For codex specifically: if you disagree, say so in the PR thread with a reason, and then move on. If you agree, fix and re-push. Don't half-fix.

### STATUS.md updates as you go

`STATUS.md` is the operational landing page, not a journal. Update it when state actually changes:

- When you start work on a new issue → `active_branch`, `linear_issue`, `current_objective`, `next_command`.
- When you open a PR → `active_pr`.
- When something needs your attention → append to "Open items needing my attention."
- When a decision lands → append to "Decisions log (recent)" with the date.
- At the end of any `/sitrep` invocation → `last_verified_state` to now.

The skill diff-updates the YAML frontmatter; it does not rewrite the file. Body sections are preserved verbatim unless you ask `/sitrep` to update them.

Don't update STATUS.md for trivia ("ran the tests," "committed a docstring fix"). The decisions log is the recent-decisions log, not the recent-commits log.

### Merge → next issue

On merge:

1. `gh pr merge` (squash is the default).
2. `git switch main && git pull`.
3. Run `/sitrep`. The reconcile step will notice that `active_pr` no longer exists for the now-deleted branch and offer to clear it. The previous `linear_issue` should now show as completed in Linear; the inbox should advance.
4. Pick the next issue. If it's already in `STATUS.md` (via a `/work-breakdown` plan), start a new branch from main. If it's a side quest from the inbox, decide first whether it's a side quest or a new active focus (the three-question test from §3).

> **Next action:** before opening your next PR, re-read [CLAUDE.md Rule 6](../../CLAUDE.md#rule-6--fail-loud). The PR description should not claim "tests pass" if any were skipped; should not claim "works" if you didn't verify the edge case; should name what was skipped, deferred, or stubbed. The PRs that fail codex review hardest are the ones with quiet half-completions.

---

## 6. Cross-cutting conventions

The four things above (sitrep, work-breakdown, design-doc, coding) are the day's spine. The conventions below cut across all of them.

### Validators for agent + manifest changes

Touched an agent .md file, the manifest, or any file under the category directories (`engineering/`, `product/`, etc.)? Run the two local checks before pushing — CLAUDE.md Rule 8 makes this expected:

```bash
python3 scripts/validate-agents.py    # strict YAML + spec checks per MIT-392
python3 scripts/generate-manifest.py  # regen + commit if anything changed
```

**What `validate-agents.py` checks:**

- **HARD**: every agent's frontmatter parses with strict YAML (`yaml.safe_load`). Failing means Claude Code's loader will degrade silently — descriptions get truncated at the first parse failure, examples disappear from routing, no error surfaces anywhere. Exit non-zero.
- **WARN**: description is ≤ 1024 chars (Anthropic spec). 52 agents currently violate; MIT-393 tracks the rewrite.
- **WARN**: description contains no XML tags (Anthropic spec). Same cohort; same ticket.

Hard failures block the push (CI rejects them). Warnings count and report but exit 0 — they're the Tier 2 progress meter.

**Iteration loop while editing an agent:**

```bash
# Edit engineering/foo-agent.md ...
python3 scripts/validate-agents.py     # quick check; fix any HARD before continuing
python3 scripts/generate-manifest.py   # may need --llm-summaries if description changed
git diff agent.manifest.yaml           # confirm only the agent you touched changed
```

If `validate-agents.py` shows a hard failure, the most common cause is an unquoted `description:` that contains a literal `: ` (e.g., an `<example>` block with `Context: ...` or `user: "..."`). The fix is to use a double-quoted single-line description with `\n` escapes, matching the pattern landed in MIT-392. The fully-broken file from `vision-engineer` is a worked example in the MIT-392 PR history.

**CI runs the same checks** via `.github/workflows/validate.yml`, plus the staff skill test suite. Hard failures block merge. The CI gate is a safety net; the local pre-push run is the discipline that keeps the gate green most of the time.

### Ticket shape: implementation vs investigation

Not every Linear ticket is implementation work. A meaningful share — spikes, audits, design explorations, "figure out X" tickets, research questions — wants a markdown report as the deliverable, not a code PR. CLAUDE.md Rule 7 makes this explicit; this section is the longer "how."

**Classify before branching.** When you pick up a ticket, ask: is the ask code, or is the ask understanding (an answer or a recommendation)? Read the ticket body first — don't classify off the title alone. Apply the classifier *before* asking the user; only ask if reading the body left the shape genuinely ambiguous.

- **Implementation-shaped:** "add X", "fix Y", "ship Z", "refactor W to do U", "migrate from A to B." Output is a PR closing the issue.
- **Investigation-shaped:** "figure out", "audit", "diagnose", "triage", "root-cause", "assess", "inventory", "map", "survey", "spike", "research", "explore", "what would it take to", "compare options for", "evaluate whether to." Output is a markdown report attached to the issue.

**Mixed-shape gotchas:**

- *Audit-then-fix.* "Audit X and fix what you find" is genuinely two tickets — the audit is investigation-shaped, the fixes are implementation-shaped. Default behavior: produce the audit report, then surface the proposed fixes as separate tickets (or as a list at the bottom of the report) and let the user decide which to implement. Don't bundle.
- *Refactor with discovery.* Some refactors need a discovery pass before the actual code change — "refactor the certificate flow" might start with a map of who calls what. If the discovery is non-trivial, do the discovery as a short report inline in the PR description (not a separate Linear attachment) and proceed with the code. The ticket is still implementation-shaped; the discovery is plumbing, not the deliverable.

If, after reading the body, a ticket is still ambiguous, ask one clarifying question before branching: "report-shaped or PR-shaped?" Cheap, and avoids both the wasted-PR failure mode (investigation work becomes a code-shaped PR) and the wasted-report failure mode (implementation work stalls because someone wrote prose instead of code).

**Investigation flow:**

1. **Write the report to a working file.** Convention: `~/.inc/projects/<slug>/reports/<MIT-NNN>-<slug>.md` (the same `~/.inc/projects/<slug>/` namespace used for non-git operational state). The path is local; the Linear attachment is the long-term artifact.
2. **Cover what a reviewer needs:**
   - **Question.** What the ticket actually asked. Quote the ticket if it helps.
   - **Method.** What you read, who you talked to, what you ran. So the reviewer can sanity-check the path to the conclusion.
   - **Findings.** The substantive answer. State positions, don't hedge ("X is the right call because…" beats "we could consider X or Y or Z").
   - **Recommendations.** What should happen next. If implementation work falls out, name it as a separate ticket — don't blur into a PR from the investigation ticket.
   - **Unknowns / next-action options.** What you didn't answer and why. The "this needs more research" or "this needs a decision from you" surfaces here.
3. **Attach to the Linear issue.** `linear issue attach MIT-NNN <path-to-md>`. The CLI will upload the file and surface it on the issue.
4. **Optionally add a comment** summarizing the headline findings: `linear issue comment add MIT-NNN -m "..."`. The inbox view shows the comment preview; pure-attachment-only issues look empty in the queue.
5. **Move the issue forward.** Close it if the answer is final, or leave it open with the next action named in a comment if it kicks off implementation work (which should become a separate ticket — see "One issue per PR" above).

**Override path.** If the user explicitly asks for code from an investigation ticket ("implement what you found", "turn this into a PR"), do that instead. The default is "report"; the override is "code". The reverse — implementation ticket becoming a report — is rarer and almost always means the ticket was misclassified upstream; in that case, push back rather than silently switching.

**Why this rule exists.** The reflexive `ticket → branch → PR` pattern is the default agent behavior because it's the default code-assistant pattern. Without an explicit convention, every investigation ticket would silently become a PR — with branch overhead, conflict-resolution risk, and a code-review-shaped review for something that wasn't code. The artifact-attached-to-Linear pattern keeps research findings searchable in the same place as implementation history, and keeps the inbox semantics ("this issue's deliverable lives here") consistent across shapes.

### Linear-as-inbox

Linear is the queue and the history. CLAUDE.md Rule 3 makes this explicit: *"The inbox is anything assigned to the user, any open PR awaiting their review, and any design doc flagged for review. `/sitrep` surfaces all three."*

The discipline:

- **Agents that produce review-worthy artifacts create or update Linear items assigned back to the user, with a link.** Not chat messages, not wandering files. If `tech-lead` produces a design review and you need to act on it, the artifact is a Linear issue or a comment on an existing one — searchable, scoped, surfaceable by `/sitrep`.
- **When you ask "what's on my plate," go to Linear.** Not to a chat-history reconstruction. The CLI for this is `sitrep-linear inbox` (the wrapper at `skills/sitrep/bin/sitrep-linear`) plus `gh pr list --search 'review-requested:@me'`.
- **Issues stay open until closed.** If an issue is obsolete, close it with a reason — don't leave it as a noise generator in the inbox. Periodic cleanup is a future `/prioritize` (Week 4) responsibility.

The long-term direction (deferred) is label-based scoping — every repo-relevant issue gets a `repo:inc` label and `linear_scope` accepts a `labels:` key. The v0 friction with project-based scoping (orphan issues, project renames) hasn't shown up yet, so the label move is parked.

### `linear_scope` per repo

Linear has no inherent "this issue belongs to this repo" link — one MIT team, many repos. Without scoping, `/sitrep`'s inbox would leak issues from `wendy`, `transcribe.py`, `lab-control`, etc. into every project's view.

`linear_scope` in `STATUS.md` is the bridge — a list of Linear project **names** (exact match) that count as this repo's work:

```yaml
linear_scope:
  - "gstack borrow — Week 1: bootstrap loop"
  - "gstack borrow — Week 2: /work-breakdown"
  - "gstack borrow — Week 3: planning discipline"
  - "Per-project agent staffing skill"
  - "Agent roster eval framework"
```

`sitrep-linear inbox` filters the team-wide inbox down to issues in these projects. Empty list or missing field = no filtering (backward compat). The match rule is exact-string; YAML comments on items are stripped from bare scalars but preserved in quoted strings. Block scalars and multi-line values are not supported. See the [STATUS schema](../../skills/sitrep/docs/status-schema.md#scoping-linear_scope) for the full contract.

Failure modes are explicit and loud (per Rule 6):

- `linear_scope` field present but parses to zero items (malformed YAML, empty list) → fallback to all-team behavior with a stderr warning. A typo on the field-name level cannot silently reintroduce cross-repo leakage.
- Some — but not all — listed projects fail to query (typo on a project name) → partial results plus a stderr warning naming the failed projects.
- **Every** listed project query fails → exit 3 with the failed-project list. No fallback — the inbox would be wrong, so the wrapper refuses rather than misleading you.

### `~/.inc/projects/<slug>/` for telemetry + restore points

Storage layer for per-project state that doesn't belong in git. Slug = `git rev-parse --show-toplevel | xargs basename` (for `inc`, slug = `inc`). Layout:

```
~/.inc/projects/<slug>/
├── telemetry.jsonl                          # one event per line (audit runs, etc.)
└── restore/
    ├── 2026-05-12T22-30-00-0001-plan-eng-review-lift.md
    └── ...
```

What writes here today:

- **`plan-eng-review`** writes a pre-mutation snapshot of any design doc it's about to accept, then appends a telemetry JSONL line `{ts, repo, skill, event, doc, status, gaps, duration_ms}`.

What may write here later: `/sitrep` (cached recent state), `/retro` (sprint-retro telemetry), `/prioritize` (priority-rank telemetry). The schema is intentionally append-only and loosely typed so future skills can extend it without coordination.

If the doc is being audited from outside a git repo, the slug falls back to `_orphan` with a stderr warning. (Future work: explicit slug resolution from the user.)

Telemetry writes are **best-effort** — a write failure emits a stderr warning, but the audit (or whatever operation was running) still PASSes. Restore-point writes are **required** — a restore write failure fails the audit. Acceptance without a rollback path is the failure mode we explicitly refuse.

### The eight CLAUDE.md rules

Restated here as a single block, because they cut across every section above. The full text and rationale live in [CLAUDE.md](../../CLAUDE.md):

1. **Session bootstrap.** On session start, run or offer `/sitrep` before doing other work. Update `STATUS.md` when work concludes.
2. **Specialist routing.** When the user's request matches a specialist agent's domain, route to it via the Agent tool. Specialists own depth, skills own procedure.
3. **Linear-as-inbox.** Linear is the queue and the history. Inbox = assigned issues + open PRs + design docs flagged for review. `/sitrep` surfaces all three.
4. **Break down non-trivial work before doing it.** Planning intent ("let's build", "we should ship") triggers `/work-breakdown`. Immediate-execution intent does not.
5. **Surface conflicts, don't average them.** When two parts of the system disagree, pick one explicitly and say why. State both positions, pick one, flag the other as a follow-up. Distinguish material from cosmetic disagreement.
6. **Fail loud.** "Completed" is wrong if anything was silently skipped. "Tests pass" is wrong if any were skipped/xfail'd. "Works" is wrong if you didn't verify the edge case. Caveats go in the same sentence as the success claim, not buried in a paragraph.
7. **Investigation tickets ship markdown reports, not PRs.** Research/spike/audit/"figure out X" tickets produce a markdown report attached to the Linear issue, not a code PR. Override only when the user explicitly asks for code. If shape is ambiguous, ask one clarifying question before branching.
8. **Run the validators before pushing agent or manifest changes.** `python3 scripts/validate-agents.py` (strict YAML + spec) and `python3 scripts/generate-manifest.py` (regen + commit) before any push that touches agent .md files or the manifest. CI runs the same checks and blocks merge on hard-fail.

Every rule has earned its place by closing a failure mode observed in this repo. Rules 5 and 6 came in via PR #21, after codex caught silent-skip behavior twice in Week 1. Rule 7 closed the reflexive `ticket → branch → PR` failure mode. Rule 8 is the most recent — closes the silent-degradation failure mode where 52 of 57 agents had invalid YAML and Claude Code's loader truncated their descriptions without surfacing an error (MIT-392). Rules that have *not* yet earned a place: codex review × 3 (convention, not rule), 80% coverage gate (Makefile-level, not constitution-level), boil-the-lake stance (handoff doc), ETHOS principles (deferred).

The discipline of CLAUDE.md is to keep it short. Eight rules is the current ceiling. Anything new needs to displace something old, or close a failure mode no existing rule covers.

> **Next action:** if you've just read this end-to-end, run `/sitrep` to land back in the loop, then keep going from there. Six months from now this doc should still make sense — if it doesn't, the workflow has drifted and the doc needs an update, not the other way around.

---

## Pointers

- **Operating rules:** [CLAUDE.md](../../CLAUDE.md)
- **Session-state contract:** [STATUS.md](../../STATUS.md), schema at [skills/sitrep/docs/status-schema.md](../../skills/sitrep/docs/status-schema.md)
- **Skill catalog (one-page reference):** [skill catalog](../reference/skills.md)
- **Machine + per-project setup:** [bootstrap guide](./bootstrap.md)
- **Worked design-doc example:** [decisions/0001-plan-eng-review-lift.md](../../decisions/0001-plan-eng-review-lift.md)
- **Why `inc` exists in this shape (historical):** [research/gstack-borrow-2026-05-11.md](../../research/gstack-borrow-2026-05-11.md)
- **Agent roster:** [agent.manifest.yaml](../../agent.manifest.yaml), staffed per-project by [`/staff`](../../skills/staff/SKILL.md)
