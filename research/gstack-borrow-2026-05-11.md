# gstack borrow / side quest — handoff

**Status (2026-05-11):** discovery + 4 sub-agent deep-reads complete + codex review complete. Shortlist revised per codex. **Next session: begin Week 1 build (revised plan below).**

**Source:** https://github.com/garrytan/gstack — Garry Tan's Claude Code setup, 23 skills, MIT-licensed.

---

## Goal

Lift specific concepts from gstack into our agent-driven setup. **Not a port.** Our agent spine stays.

## Posture

**(b) study-and-lift** — read gstack as a concept library; surface narrow imports. Agent system stays the spine.

---

## Why gstack uses skills (answered)

Per the Epsilla "Why YC's Garry Tan Abandoned Omni-Bots for gstack" article:

- gstack's framing: **cognitive specialization beats generic.** Same insight as ours.
- gstack implements via skills (procedures the orchestrator runs).
- We implement via agents (subagents with separate context).
- **Both work.** Different tradeoffs.

What we're missing isn't agents — it's the **playbook layer that composes specialists into procedures**. Skills go on top of our agent spine.

---

## Pain ranking (user-stated, walked through)

1. **C — Session bootstrap** (worst) — Claude opens with no orientation; manual sitrep dance every session.
2. **D — Work breakdown** — multi-step procedure (idea → plan → initiative → projects → PR-issues) lives in user's head, not codified.
3. **B — Cross-project state** — Linear-as-inbox isn't lived; issues stay open; design docs / PRs vanish; user goes through tmux tabs.
4. **A — Procedural work** (diagrams, tests, codex × 3) — last because encoding procedures on top of unclean state is ceremony.

---

## C data (session bootstrap, manual dance)

1. SSH → tmux attach → move to project tab (named differently than project — friction)
2. Open `claude` in lab-control dir
3. Ask *"what's the status of the project and what's next?"*
4. Claude has to go to Linear + read docs to know latest
5. Throughout: manual asks to update docs + handoff doc
6. Manual asks to "delegate to the expert"
7. Manual asks to run integration tests "even manually"
8. Sometimes: describe → design → codex feedback

**Gap:** Claude opens unoriented. User is the orchestrator firing off bootstrap commands every session.

**`lab-control/CLAUDE.md`** is a 1-line pointer to `agent-brief.md`. `claude-agents/CLAUDE.md` doesn't exist.

## D data (Linear work breakdown)

Works when triggered, but trigger is manual:

1. Idea originates anywhere
2. Claude or an agent creates issue
3. **If large/multi-repo**: claude → plan → initiative → projects → eng team creates own issues
4. Sub-agents/experts scope, debate, codex feedback, break down
5. Issues are **per-PR**

**Pain:** procedure in user's head, not codified. Trigger condition ("I feel the idea is pretty large") is manual judgment.

## B data (cross-project state)

Manual moves:
- Goes through tmux tabs and asks per-tab
- Knows he *should* go to Linear; doesn't
- Issues stay open / don't get closed
- Some issues become obsolete (need periodic cleanup)
- Projects forgotten, PRs forgotten, design docs forgotten

User-articulated wants:
- Agents should assign Linear tasks back to him for things needing review (design docs especially), with link
- Periodic prioritization mode (rank in-flight vs backlog)
- Both "now" (what needs my attention) and "later" (resuming forgotten work)

**Gap:** Linear-as-inbox isn't lived. Agents produce review-worthy artifacts but don't push them into user's queue.

## A data (procedural)

Listed implicitly through C/D walkthroughs:
- Diagrams: user-flow + state-machine + data-flow on every design doc
- Test coverage
- Codex code review × 3 rounds
- Update docs + handoff doc throughout session

These are the recurring procedures user runs by hand. Encoding them is gstack's bread and butter.

---

## Boil-the-lake stance — UPDATED 2026-05-11

**Previous stance:** adopt for procedure/discipline, NOT for feature scope.

**Current stance (user confirmed 2026-05-11):** **adopt boil-the-lake the gstack way — fully.** "Warming up to it."

What this means in practice:
- Default to **complete** when implementing. AI compresses implementation cost 10-100×; the delta between 80% and 100% is usually seconds, not days.
- Stop reflexively choosing the minimal-viable approach to "save scope." Choose the right approach.
- Still surface taste decisions to the user. Still respect User Sovereignty (AI recommends, human decides).
- "Add later in our plan" — fold the principle into ETHOS.md (Week 4) so it becomes the standing posture, not a one-off.

**This shifts the engineering preferences encoded in our forthcoming CLAUDE.md:** lean toward complete-and-named over minimal-and-deferred. Boil the lake on procedures AND on features.

---

## gstack concepts on the table

### ETHOS.md (4 principles)
- **Boil the Lake** — completeness is cheap; default to complete. (**ADOPT FULLY** — see stance update above.)
- **Search Before Building** — three knowledge layers. (Weak fit; we compose primitives.)
- **User Sovereignty** — *"AI recommends, humans decide. The one rule that overrides all others."* (**Adopt verbatim.**)
- **Build for Yourself** — specificity beats hypothetical generality. (**Adopt verbatim.**)

### CLAUDE.md (auto-loaded constitution)
gstack instructs Claude on session start:
- *"When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill."*
- Pre-merge testing requirements named explicitly
- Long-running task handling

**Adopt the pattern.** Our version: *"When the user's request matches a specialist agent, route to it. When in doubt, route to the specialist."* Plus codex-review-before-merge, 80% coverage gate, Linear conventions.

---

## Deep-read findings (4 parallel delegations, 2026-05-11)

### `/autoplan` (general-purpose deep-read)

**What it does:** orchestrator that reads four review skill files (`plan-ceo-review`, `plan-design-review`, `plan-eng-review`, `plan-devex-review`) from disk and executes them sequentially with auto-decisions. Phase 0 captures a restore-point of the plan file; Phases 1-3.5 run the review gears in fixed order CEO → Design → Eng → DX (each conditional on detected scope); Phase 4 is the final human approval gate.

**Cognitive gears invoked:** four **review** gears in fixed order. NOT the CEO/EM/QA/RE quartet from the Epsilla article — that quartet is the broader gstack roster; autoplan invokes only the planning subset.

**Artifacts produced:**
- Restore-point file at `~/.gstack/projects/$SLUG/${BRANCH}-autoplan-restore-${DATETIME}.md`
- In-place plan-file mutations: Decision Audit Trail table, consensus tables, Failure Modes Registry, "NOT in scope", "What already exists", ASCII architecture diagram, Dream State delta
- Test plan artifact for `/qa` to consume
- JSONL review logs for `/ship`'s dashboard

**Worth lifting (3):**
1. **6 Decision Principles + Classification triad** — every decision is *Mechanical* (auto-silent), *Taste* (auto-decide but surface at final gate), or *User Challenge* (NEVER auto-decided — when both reviewers agree the user's direction should change, default stays the user's). The User Challenge framing — "the models must make the case for change, not the other way around" — is gold.
2. **Restore point + decision audit trail pattern** — snapshot the plan to disk before mutating; incrementally write decisions into a `## Decision Audit Trail` table.
3. **Pre-Gate Verification checklist** — explicit per-phase output checkboxes with bounded retry (max 2 attempts) before opening the final gate.

**Doesn't translate (2):**
1. "Skills-as-text invoked inline" — autoplan literally `Read`s SKILL.md files and executes them in the parent context with a skip list. We have actual sub-agents (PM, tech-lead, TPM, RE) with separate contexts. **Right adaptation:** a coordinator agent that fires sub-agents sequentially with phase-transition payloads.
2. `~/.gstack/projects/$SLUG/` filesystem state store — we use Linear. Artifacts go to Linear issues/documents, not local JSONL.

### `/plan-*-review` family (general-purpose deep-read)

**Status of our local copies:** we already have `plan-ceo-review` (164 lines vs gstack's 2107) and `plan-devex-review` (211 vs 2028) at `/home/mihai/.claude/skills/`. We do NOT have `plan-eng-review` or `plan-design-review`.

**Each review skill — distinct lens:**
- **`plan-ceo-review`** — strategic/scope review. 4 modes (SCOPE EXPANSION / SELECTIVE / HOLD / REDUCTION). 9 Prime Directives including #6 *"Diagrams are mandatory"*. Implementation Alternatives protocol (2-3 approaches). Dream State diagram.
- **`plan-eng-review`** — engineering manager review. **Diagram-heavy.** Step 3 builds ASCII coverage diagram with star ratings (★★★/★★/★) and `[→E2E]` / `[→EVAL]` tags. Failure-modes registry per new codepath. "NOT in scope" / "What already exists" / Worktree parallelization strategy. Stale Diagram Audit ("List every ASCII diagram in files this plan touches. Still accurate?").
- **`plan-design-review`** — designer review. 7 passes. Interaction State Coverage table (FEATURE × {LOADING, EMPTY, ERROR, SUCCESS, PARTIAL}). AI Slop blacklist. Mostly visual-designer oriented; **selective lift only.**
- **`plan-devex-review`** — DX review. 8 passes. TTHW (Time To Hello World) metric. Persona/empathy/benchmark/magical-moment Step-0 investigation.

**The 3-diagram requirement IS already encoded** in our local `plan-ceo-review` Prime Directive #6 (user-flow / state-machine / data-flow). The *enforcement machinery* (Stale Diagram Audit, coverage diagram, failure-mode registry) lives in `plan-eng-review` which we don't have.

**Per-skill verdict:**
- `plan-ceo-review` — keep. Worth re-syncing to pick up "Completeness is cheap / Boil the Lake" framing and Dream State diagram.
- `plan-eng-review` — **lift it.** Single highest-value addition. Coverage diagram + failure-mode registry + Stale Diagram Audit. Pairs with our tech-lead agent.
- `plan-design-review` — selective lift. Take the state-coverage table and unresolved-decisions table; **don't** take marketing/landing/typography rules.
- `plan-devex-review` — keep. Re-sync to pick up `dx-hall-of-fame.md` reference + 0A-0G Step-0 investigation.

**Concrete enforcement move:** make the 3-diagram requirement a **hard gate** in `plan-eng-review`: if the plan lacks any of {user-flow, state-machine, data-flow} ASCII diagram, `status = issues_open`, `critical_gap += 1`. TPM/release-engineer refuse to advance until produced.

### gstack evals approach (general-purpose deep-read)

**What it evaluates:** agent/skill *behavior*, not code correctness. Two tiers:
- `bun test` (free, <2s) — skill validation, doc quality
- `bun run test:evals` (paid, ~$4 max) — splits into **LLM-judge tests** (grade artifacts on numeric rubrics) and **skill E2E tests** (invoke skills via `claude -p`, then judge resulting files with a second LLM call)

**Diff-based selection:** `test/helpers/touchfiles.ts` maps each test to file globs. `scripts/eval-select.ts` runs `git diff --name-only base..HEAD` then runs only tests whose touchfiles intersect. `GLOBAL_TOUCHFILES` (like `session-runner.ts`) forces all-run when touched. `EVALS_ALL=1` overrides.

**Tier system:** `E2E_TIERS: 'gate' | 'periodic'`. Gate runs every PR (`evals.yml`). Periodic runs Monday 06:00 UTC cron only (`evals-periodic.yml`). **Not a hard merge block** — CI uses `if: always()` and posts a PR comment, no required-status rule. Gate is **social** more than mechanical.

**Judge architecture:**
- Cheap rubric judge: **Haiku** (~$0.04 per run) for high-volume gate
- Skill-output judge: **Sonnet** for periodic deep evals
- Persisted `EvalResult` schema: `{schema_version, version, branch, git_sha, timestamp, tests: [{passed, duration_ms, cost_usd, transcript, model}]}` under `~/.gstack/projects/<slug>/evals/` with auto-compare to previous run

**Skill matrix (orthogonal to test:evals):**
| Skill | Purpose | When |
|---|---|---|
| `/benchmark` | Browser perf (TTFB/FCP/LCP, bundle, regression vs baseline) | per-PR perf |
| `/canary` | Post-deploy production watcher; screenshot diff every 60s | post-ship |
| `/qa` | Test web app, **fix bugs**, atomic commits, re-verify | dev loop |
| `/qa-only` | Same surface, **report only**, `baseline.json` snapshot | audit |

**Liftable for Project B (MIT-294-302):**
1. **Touchfile-driven diff selection** (~150 LOC in Python). Single highest-value idea — makes paid evals affordable per-PR.
2. **Two-tier `gate` vs `periodic` classification.** Maps onto our routing-accuracy (gate) vs conflict-detection (periodic if expensive).
3. **Persisted result schema with auto-compare** — drop-in for Codex-as-judge.
4. **Rubric-based judge with numeric threshold** (≥4/5). Matches our routing-accuracy and conflict-detection patterns.
5. **Cheap model for gate, expensive for periodic.** Codex slots into gate cheaply.
6. **Local-then-CI gate with stated cost ceiling** in docs. "$4/run max" is a forcing function.

**Don't lift:** bun harness, `claude -p` invocation harness (we have subagents), `/benchmark`/`/canary` (no UI), `/qa`/`/qa-only` (web-test specific), make-pdf/browse/xterm integrations.

### Role-comparison (hiring-manager)

Full doc at `/home/mihai/workspace/claude-agents/research/gstack-role-comparison.md`. Summary:

**1:1 mappings:**
- `/plan-eng-review` ↔ tech-lead — cleanest match
- `/plan-ceo-review` ↔ product-manager — overlap on prioritization, diverge on scope-expansion framing
- `/qa` ↔ test-writer-fixer — close
- `/ship` ↔ release-engineer — close but different scale

**No agent equivalent:** `/plan-design-review`, `/plan-devex-review`, `/retro`, `/autoplan` — these are skills, not roles.

**Granularity:** ours is sharper on **execution** (PM → TL → TPM → RE + specialists). gstack is sharper on **planning** (4 review gears vs our 2). Neither uniformly better.

**Procedural (skills) vs structural (agents) switch:**
- Skills win for reflexive moves: codex review, PR review.
- Agents win for deep multi-step moves with conflicting heuristics: security audit, infra review.

**Head-to-heads:**
- `/cso` is broader than our `security-auditor` — our specialization is deliberate, not a gap.
- `/codex` skill standardizes a procedure we do ad-hoc — **procedure gap**, worth lifting as a skill.
- design-* skills are out of scope (no visual designer).

**Proposal:** extend `tech-lead.md` with a named DX-review lens rather than create a `devex-reviewer` agent. **Do not** add visual-designer, ceo-reviewer, or qa-engineer agents — those are skill-shaped, not role-shaped.

**Bigger conclusion:** **lift skills, not agents.** gstack's transferable contribution is the planning pipeline, not the role decomposition.

---

## Codex review (2026-05-11) — revisions applied below

Codex pressure-tested the consolidated shortlist. Verdict summary:

- **Sequencing:** Week 1 was constitution-heavy. Better: thin CLAUDE.md (3 rules only) + `/sitrep v0` + a canonical session-state file. Defer the full constitution.
- **`/inbox` is secretly tier-1.** C and B are entangled — *"Claude opens unoriented"* is partly *"Claude doesn't know what needs the user's attention."* If `/sitrep` excludes assigned Linear review items, open PRs, and pending design-doc reviews, it becomes a status summary instead of an operational landing page.
- **`plan-eng-review` is tier-1 for the next non-trivial plan.** Not globally tier-1, but: shipping the first gstack-borrow changes without the very planning discipline we're adopting is silly.
- **Overbuilt:** `ETHOS.md` (defer until rules survive contact), `/retro` (indulgent for solo eng), `/triage` (overlaps `/inbox`), `/autoplan` (start with `/work-breakdown`, add coordinator after one real use), `/codex` skill (premature before CLAUDE.md rule is shown insufficient), `3.5a + 3.5b` overlap (let `/design-doc` *create*, `plan-eng-review` *audit* — don't enforce diagrams in two places).
- **Missing: an adoption bridge.** "Use this on the next plan" was hand-wavy. Add `/work-breakdown` for D. Also missing: a persistent session-state contract (file + fields) that `/sitrep` reads and updates.
- **Boil-the-lake:** mostly cosmetic for the shortlist. Risk: makes `/autoplan` literally interpreted dangerous (it would pull in CEO/design/DX/audit-trails/restore-points before the loop is proven). Cheaper for `/sitrep` (build the complete useful version, including inbox state, not "recent commits"). **Don't let boil-the-lake justify shipping all Week 4 reflection tools.**
- **Project B integration risks:** EvalResult schema too thin for `/staff` (needs precision/recall/F1, expected/suggested IDs, FP/FN, strategy, labels-file version, judge metadata). Numeric ≥4/5 is for *qualitative* judge calls (conflict-detection rationale) — routing accuracy stays *deterministic*. Touchfiles must trigger on manifest/schemas/labels/agent-frontmatter changes. Conflict-detection should be **gate** (not periodic) when conflicts/aliases/tags/descriptions change; periodic only for broad drift sweeps.

## Revised lift shortlist (post-codex)

| Tier | Lift | Fixes | What it is |
|---|---|---|---|
| **1.1** | **Thin** `CLAUDE.md` (3 rules only) | C | session-start rule (run/offer `/sitrep`), routing rule (request matches specialist → route), Linear-as-inbox rule. **Defer** full constitution, coverage gate, codex discipline. |
| **1.2** | `/sitrep v0` skill | C, B | Current project, **active Linear issues assigned to user**, **review-needed items (PRs, design docs)**, blocked-on-user, next action, last verified state. Reads + writes canonical session-state file. |
| **1.3** | Canonical session-state contract | C | `STATUS.md` (or `decisions/`) per-project with fields: current objective, active branch/PR, blocked-on-user, next command, last verified state. `/sitrep` is the read+write client. |
| **2.4** | `/work-breakdown` skill (adoption bridge) | D | Decides: small task / project-sized / initiative-sized / multi-repo. Creates/updates Linear issues, projects, initiative. Calls PM/TL/TPM only at thresholds. Attaches design-doc + eng-review gates before coding. |
| **2.5** | `/inbox` rolled into `/sitrep` | B, D | Per codex: don't ship `/inbox` separately. Make `/sitrep v0` cover assigned-to-me + open PRs + design docs for review from day one. |
| **3.5a** | `/design-doc` skill (creates) | A | Scaffolds doc with 3 mandatory diagram sections (user-flow + state-machine + data-flow). |
| **3.5b** | `plan-eng-review` skill (audits) | A | Lifted from gstack, stripped of plumbing. Coverage diagram + failure-mode registry + Stale Diagram Audit. **Hard gate** on missing diagrams. Adopt for the next non-trivial plan immediately — don't wait for Week 3. |
| **4.6** | `/prioritize` skill | B later | Ranks in-flight vs backlog. Solo-engineer-shaped (not bundled with `/retro` or `/triage`). |
| **B-eval** | Touchfile diff selection + tiers + extended EvalResult schema | Project B | Schema includes precision/recall/F1, expected/suggested, FP/FN, strategy, labels version, judge metadata. Touchfiles cover manifest/schemas/labels/frontmatter. Conflict-detection is gate when conflicts/aliases/tags/descriptions change. |

### Dropped from shortlist (per codex)

- `ETHOS.md` as a Week 4 deliverable. Three operational rules go in CLAUDE.md. Write ETHOS.md later **if** the rules survive contact.
- `/codex` skill (as a named workflow). Premature. Try the CLAUDE.md rule first; promote to a skill only if ignored.
- `/retro` and `/triage`. `/retro` is indulgent for a single engineer; `/triage` overlaps `/inbox`. `/prioritize` is the only one kept.
- `/autoplan` as a full coordinator port. Replaced by `/work-breakdown` (the adoption bridge). Add PM → tech-lead → TPM orchestration only after one real use shows the seams.

---

## What NOT to lift

- Full skill-replacement of agents (we keep agents as spine)
- gstack's bun/test infrastructure (we have Python + coverage.py)
- `/cso`, `/freeze`, `/guard` safety skills (overkill for personal repo)
- `/benchmark`, `/canary`, `/qa`, `/qa-only` (web-specific)
- design-* skills wholesale (cherry-pick state-coverage table only)
- `~/.gstack/projects/$SLUG/` filesystem state store (we use Linear)
- `claude -p` E2E harness (we have subagents)

---

## Revised sequence to ship (post-codex)

1. **Week 1 — bootstrap loop.** Thin CLAUDE.md (3 rules) + `/sitrep v0` (with inbox rolled in) + canonical `STATUS.md`/`decisions/` contract. **Goal:** session starts oriented, no manual sitrep dance. Fixes C and the operational part of B.
2. **Week 2 — work breakdown.** `/work-breakdown` skill (the adoption bridge for D). Creates/updates Linear at the right granularity. Use it on the next non-trivial idea.
3. **Week 3 — planning discipline.** `/design-doc` (creates, 3 diagrams scaffolded) + `plan-eng-review` (audits, hard gate). Adopt for the next plan, not just shelved as available. Fixes A.
4. **Week 4 — sweep.** `/prioritize` only. Defer `ETHOS.md`, `/retro`, `/triage`, `/codex` skill — revisit if pain persists.
5. **Project B parallel track.** Fold gstack mechanics (touchfile selection, gate/periodic tiers, persisted results) into MIT-294-302 with the extended EvalResult schema. Routing accuracy stays deterministic; judge rubrics scoped to qualitative cases.

---

## Delegations + review completed (2026-05-11)

1. ✅ general-purpose — `/autoplan` skill deep-read
2. ✅ general-purpose — `/plan-*-review` family deep-read
3. ✅ general-purpose — gstack evals approach deep-read
4. ✅ hiring-manager — role-comparison (separate doc at `research/gstack-role-comparison.md`)
5. ✅ codex review of consolidated shortlist — revisions applied above. Per-PR codex review during build phase as usual.

---

## Open research still owed (deferred)

- Garry Tan "tokenizing maximization" talk — couldn't find with exact phrase. May be paraphrased from Karpathy "haven't typed code since December" or related. Defer until a specific source surfaces.

---

## Status: handoff updated 2026-05-11 (post-codex)

**Next session — begin Week 1 build (revised):**

1. Read this file first. Skim `research/gstack-role-comparison.md` for role context.
2. **Build Week 1 in order:**
   - **Step 1: Define the canonical session-state contract.** Pick a name (`STATUS.md` at project root is the front-runner). Fields: `current_objective`, `active_branch`, `active_pr`, `blocked_on_user`, `next_command`, `last_verified_state`, `links` (Linear issues, PRs, design docs needing review). Write a 1-page schema doc.
   - **Step 2: Draft thin CLAUDE.md** at `/home/mihai/workspace/claude-agents/CLAUDE.md`. THREE rules only: (a) on session start, run or offer `/sitrep`; (b) when request matches a specialist agent, route to it; (c) Linear-as-inbox — assigned-to-user items + open PRs + pending design-doc reviews are the queue. **Defer** full constitution, coverage gate language, codex × 3, ETHOS philosophy.
   - **Step 3: Build `/sitrep v0`.** Reads `STATUS.md` + Linear (`linear issue mine`, open PRs with `gh pr list`, pending review docs from Linear documents) + last commits. Surfaces operational landing page: "you are here, next command is X, blocked on you: [...]". Writes back updates to `STATUS.md` at end of session.
3. **Create Linear initiative** "gstack borrow" on MIT team. Projects: Week 1 (bootstrap loop), Week 2 (work breakdown), Week 3 (planning discipline), Week 4 (prioritize), Project B parallel (eval mechanics).
4. **Per-PR:** codex review × 3 rounds per house workflow.
5. **Use `plan-eng-review` discipline on the next non-trivial plan** (don't wait for Week 3 to formalize). Even informally — 3 diagrams + failure-modes + Stale Diagram Audit on whatever lands next.
6. **Boil-the-lake stance reminder:** apply to procedural completeness (wire each skill into session start + Linear + next plan), NOT to expanding feature scope of any one skill. Don't let it justify `/autoplan` as a full coordinator port in Week 2.
