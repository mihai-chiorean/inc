---
name: work-breakdown
description: |
  Classify an idea by size (S/M/L/XL) and break it down into Linear artifacts at the right granularity — issue / project + issues / initiative + projects + issues / multi-repo coordination. Recommends specialist agents (PM, tech-lead, TPM) and planning gates (design-doc, plan-eng-review). Adoption bridge for the work-breakdown procedure that currently lives in user's head.

  Use when the user says "let's build X" / "we should X" and X is non-trivial (more than a one-line fix), "how do we break this down", "this is going to be big", or any time the ask visibly spans multiple files, areas, or repos. When in doubt, fire — classifying as S still produces a useful single issue.

  Adapted from gstack's /autoplan but explicitly narrower: classification + Linear orchestration only. PM → tech-lead → TPM full coordinator orchestration is deferred until one real use shows the seams.
version: 0
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, AskUserQuestion
---

# /work-breakdown — classify and break down

You are the procedural counterpart to `/sitrep`. Where `/sitrep` orients ("where am I"), `/work-breakdown` plans ("how do we split this up so it ships").

The goal is **not** to do the work. The goal is to:
1. Classify the ask (S / M / L / XL).
2. Produce the right Linear artifacts.
3. Recommend who to bring in next (specialist agents) and what gates to satisfy (design-doc, plan-eng-review).

Linear artifacts go through the `linear` CLI (extend `skills/sitrep/bin/sitrep-linear` if read-side wrapping is needed; writes are well-defined enough to invoke directly per the linear skill).

---

## When to fire

Trigger heuristics (this is the skill's `description` field at the top — Claude Code matches it):

- User says "let's build X", "we should X", "I want to X" and X is more than a one-line fix.
- User says "how do we break this down", "where do we start", "this is going to be big."
- User describes scope spanning **more than 3 paragraphs**.
- The ask **visibly spans multiple files, areas, or repos**.
- User mentions multiple deliverables, multiple repos, or "phases."

**When in doubt, fire.** Classifying as S still produces a single useful issue; the cost of mis-firing on a small ask is low. The cost of NOT firing on a large ask is the procedure stays in the user's head — which is the pain we're fixing.

---

## Classification

Four sizes. Each maps to a specific Linear shape and a specific minimum gate set.

| Size | Scope | Linear shape | Time horizon | Required gates |
|---|---|---|---|---|
| **S** | Single PR, single concern, ≤ 1 day | 1 issue | Hours–1 day | None |
| **M** | Multiple PRs in one area, single coherent feature | 1 project + N issues (1 per PR) | 1–2 weeks | Design-doc recommended |
| **L** | Multiple projects, cross-cutting | 1 initiative + M projects + N issues per project | 1–2 months | Design-doc **required** + plan-eng-review **required** |
| **XL** | Multi-repo or multiple initiatives | 1 initiative (or 2) + projects per repo + coordination doc | Months+ | All L gates + cross-repo coordination doc |

### How to choose

Ask up front, do not guess. The user almost always has a better intuition than you about scope. Present the four options with brief consequences (use AskUserQuestion):

> What size is this work?
> - **S** — one PR, one issue. (Bug fix, small feature, refactor.)
> - **M** — project with several PRs in one area. (New skill, new endpoint, new module.)
> - **L** — initiative with multiple projects. Cross-cutting. (Like the gstack-borrow initiative itself.)
> - **XL** — multi-repo or multi-initiative. (Touches lab-control + claude-agents + cloud, or several big initiatives.)

If the user pushes back ("just create an issue"), do that. User Sovereignty applies — recommend, don't decide.

### Tie-breakers

If the user says "I'm not sure," ask which of these apply:
- Does it touch more than one repo? → at least M, probably L or XL.
- Will there be more than 5 PRs? → at least M, probably L.
- Is the user-facing surface new? → at least M; add PM to the recommended specialists.
- Does it cross more than one of {backend, frontend, infra, embedded}? → at least M; add tech-lead.
- Are multiple people likely to coordinate? → at least L; add TPM.
- Is there a known deadline or external dependency? → bump up one size for safety.

---

## Procedure

### Step 1 — Restate the ask

In one sentence, restate the user's idea back to them. This is the **premise check**. If the user disagrees with your restatement, you have not understood the ask; do not proceed until you do.

### Step 2 — Classify

Use AskUserQuestion (one question, single-select) with the four options above. Capture the choice.

If S, jump to Step 5.

### Step 3 — Initiative / project naming

For M+ work, propose a **name** and **one-line description** for the parent artifact (initiative for L/XL, project for M). Names should:
- Be specific enough to read in a Linear list six weeks from now.
- Match the user's existing naming pattern. Examples in this workspace: `gstack borrow`, `Per-project agent staffing skill`, `agent eval framework`.
- Avoid generic words like "improvements" or "enhancements" — they make the artifact invisible in search.

Confirm with the user before creating.

### Step 4 — Specialist recommendations

For M+ work, recommend which specialist agents should weigh in **before** issues get created. This is a recommendation, not auto-routing.

| Specialist | Call when |
|---|---|
| **product-manager** | New user-facing surface, business-model question, feature priority unclear, or success-metric not yet defined. |
| **tech-lead** | Architecture decision, performance bet, cross-cutting refactor, or M+ engineering scope. |
| **tpm** (technical-product-manager) | Cross-team / cross-repo coordination. Always for XL. |

For S work, no specialists called. For M, usually one (whichever lens dominates). For L, usually both PM + tech-lead. For XL, all three.

Tell the user **which specialists you'd call and why**. Let them choose.

### Step 5 — Create Linear artifacts

Use the `linear` CLI directly for creates (commands are stable; no need for a wrapper at v0). Reads still go through `sitrep-linear` per the established pattern.

**S — single issue:**

```bash
linear issue create \
  --team "$TEAM_KEY" \
  -t "<one-line title>" \
  --description-file <(echo "<body in markdown>") \
  -a self \
  -p <priority 1-4, default 3> \
  -s backlog \
  --no-interactive
```

If the user has an active project context (from `STATUS.md` or just-created via this skill), pass `--project "<project name>"`.

**M — project + issues:**

```bash
# 1. Create the project
linear project create \
  --team "$TEAM_KEY" \
  -n "<name>" \
  -d "<one-line description, ≤ 255 chars>" \
  --initiative "<initiative name>" \   # if M is under an existing initiative
  -l @me \
  -s planned \
  --target-date <YYYY-MM-DD> \
  --json

# 2. Create issues under it (one per anticipated PR)
linear issue create \
  --team "$TEAM_KEY" \
  --project "<project name>" \
  -t "<issue title>" \
  --description-file <path> \
  -a self -p <p> -s backlog \
  --no-interactive
```

**L — initiative + projects + issues:**

```bash
# 1. Initiative
linear initiative create \
  -n "<name>" \
  -d "<≤ 255 chars>" \
  -o @me \
  -s active \
  --target-date <YYYY-MM-DD>

# 2. Projects per phase or per area (typically 3-6)
# 3. Issues per project (one per PR)
```

**XL — same as L plus:**

- Create a coordination doc (a Linear document or a `research/<name>-coordination.md` in the lead repo) that:
  - Lists every repo touched
  - Names the order of changes (which repo lands first, which depends on which)
  - Names the rollback path if any repo fails mid-rollout
- Reference the coordination doc from every initiative/project description.

### Step 6 — Gates

For M+, **state explicitly** what gates the work must pass before any code lands:

- **M:** "/design-doc recommended. Plan-eng-review on the first non-trivial PR."
- **L:** "/design-doc required. Plan-eng-review on every M+ PR within."
- **XL:** "/design-doc required for the coordination doc. Plan-eng-review per repo. Cross-repo sequence written before any code lands."

(`/design-doc` and `plan-eng-review` are Week 3 deliverables. Until they exist, gate verbally — say what would be checked.)

### Step 7 — Update STATUS.md

If the ask is the new active focus for the project, update STATUS.md:
- `current_objective` → new initiative/project's one-liner
- `linear_issue` → first issue created (if S/M) or the initiative's top-level tracker
- `linear_project` → new project URL
- `next_command` → first thing to do (often "kick off design-doc for X")

Use the diff-update pattern from `skills/sitrep/SKILL.md` Step 6 — preserve other fields.

If the ask is **side-quest-shaped** (e.g., a Week 2 user files a Week 1 follow-up), DO NOT replace `current_objective`. Just add to "Open items" or note it in Decisions log.

### Step 8 — Summary output

Print a structured summary the user can act on:

```
=== /work-breakdown ===
Ask:    <restated one-liner>
Size:   <S/M/L/XL>  —  <one-line justification>

Linear created:
  • <type> — <title>  →  <URL>
  • ...

Specialists to call (your choice):
  • <agent>  —  <why>
  • ...

Gates required before code lands:
  • <gate>
  • ...

Next command suggestion:
  → <e.g. "Run /design-doc on the initiative">
```

---

## What `/work-breakdown` does NOT do (yet)

- **Auto-call specialists.** v0 recommends; user decides who to spawn. The full PM → tech-lead → TPM coordinator chain is deferred to a later week (per codex review — "too big as a first move").
- **Run `/design-doc` automatically.** Recommended via gate text only. The skill itself ships in Week 3.
- **Run `plan-eng-review` automatically.** Same — Week 3 deliverable.
- **Estimate effort or time.** The user is the expert on their own velocity.
- **Auto-classify via LLM heuristics.** Asking the user is faster and more accurate at this scope.
- **Track work after it starts.** That's `/sitrep`'s job (read state) and the user's own discipline (close issues, link PRs).

---

## Examples

### Example A — S-sized

User: *"add `--all` to /sitrep so I can roll up all my projects at once."*

```
=== /work-breakdown ===
Ask:    Add --all flag to /sitrep for cross-project rollup.
Size:   S  —  Single skill enhancement, one PR, no new abstractions.

Linear created:
  • Issue — Add /sitrep --all for cross-project rollup  →  MIT-???

Specialists to call: none.

Gates required: none.

Next command suggestion:
  → linear issue start MIT-???
```

### Example B — M-sized

User: *"build a /retro skill that runs at end of sprint and writes Linear cleanup actions."*

Restate; ask size; user says M (multiple PRs: skill core, codex review wiring, cleanup actions).

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

### Example C — L-sized

User: *"replace the Linear-CLI v1 dependency across all our skills with a unified internal Linear client."*

Restate; ask size; user says L (touches sitrep, work-breakdown, future retro/prioritize, and any other skill that shells out to linear; needs initiative because >3 projects of work).

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

---

## Pointers

- **Linear conventions:** see `~/.claude/skills/linear/SKILL.md` for the full CLI reference.
- **STATUS.md schema:** `skills/sitrep/docs/status-schema.md`.
- **Roster of specialists:** `agent.manifest.yaml` (top-level); use the `Agent` tool to spawn.
- **Active initiative:** the gstack-borrow initiative spawned this skill — its handoff at `research/gstack-borrow-2026-05-11.md` shows L-sized breakdown in practice.
