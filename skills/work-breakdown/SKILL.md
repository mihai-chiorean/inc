---
name: work-breakdown
description: |
  Classify an idea by size (S/M/L/XL) and break it down into Linear artifacts at the right granularity — issue / project + issues / initiative + projects + issues / multi-repo coordination. Recommends specialist agents (PM, tech-lead, TPM) and planning gates (design-doc, plan-eng-review). Adoption bridge for the work-breakdown procedure that currently lives in user's head.

  Adapted from gstack's /autoplan but explicitly narrower: classification + Linear orchestration only. PM → tech-lead → TPM full coordinator orchestration is deferred until one real use shows the seams.
when_to_use: |
  Fires when the user says "let's build X" / "we should X" and X is non-trivial (more than a one-line fix), "how do we break this down", "this is going to be big", or any time the ask visibly spans multiple files, areas, or repos. When in doubt, fire — classifying as S still produces a useful single issue.
argument-hint: '[one-line idea description]'
disable-model-invocation: true
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

- User is **planning or queuing work**, not asking for immediate implementation. The phrasing signals deliberation: "let's build", "we should", "I want to start on", "how do we break this down", "where do we start", "this is going to be big."
- User describes scope spanning more than 3 paragraphs.
- The ask visibly spans multiple files, areas, or repos.
- User mentions multiple deliverables, multiple repos, or "phases."

**Do NOT fire** when:
- The user is asking you to do the work right now ("fix this", "implement X", "ship it", "go", "just do it").
- The ask is clearly a single change with no breakdown needed (typo fix, dependency bump, single function refactor).
- The user has already broken the work down themselves and is asking for execution.

When the signal is ambiguous (e.g. "let's add Y" where Y could be one PR or three), **ask one clarifying question** before firing: "Is this one PR or should we break it down?" — fire only if they signal multi-PR.

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

**Propose a default size with a one-line justification.** Then ask the user to confirm or override. Do not make the user classify from scratch — you have read the ask, you have a hypothesis.

Apply the tie-breakers below to your hypothesis. Output looks like:

> I think this is **M** — touches the `/sitrep` skill plus its wrapper, no other repos, no schema change. Two or three PRs. Confirm, or pick: **S** / **L** / **XL**.

If the user pushes back ("just create an issue"), do that. User Sovereignty applies — recommend, don't decide.

### Tie-breakers (apply to your hypothesis)

Bump up one size if **any** of these is true and not already accounted for:

- **Multi-repo dependency.** Touches > 1 repo with order-sensitive changes. (A trivial dependency bump across two repos is still M, not XL.)
- **Public API / schema change.** Adds or alters a public surface (CLI flag, library API, DB schema, on-disk schema, gRPC proto).
- **Data migration or backcompat.** Existing data needs to be migrated, or older clients must keep working.
- **Security / privacy risk.** Touches auth, secrets, sensitive paths, or new external network surface.
- **Production rollout / rollback.** Needs phased rollout, feature flag, or named rollback path.
- **Ambiguity / discovery scope.** Significant unknowns mean part of the work is *figuring out what the work is*. Often pushes M → L.
- **Multiple specialists needed.** Engineering + product + cross-team coordination required.
- **External deadline or dependency.** Coordination cost adds a size band.

Tie-breakers that do **not** bump size by themselves:
- Number of PRs alone (5 small PRs in one area is M, not L).
- Multi-repo alone (a dependency bump or version bump in two repos is M).
- "Feels big" without a concrete tie-breaker.

---

## Procedure

### Step 1 — Restate the ask

In one sentence, restate the user's idea back to them. This is the **premise check**. If the user disagrees with your restatement, you have not understood the ask; do not proceed until you do.

### Step 2 — Classify (propose, then confirm)

State your hypothesis size + one-line justification + which tie-breakers (if any) apply. Then offer the four options with AskUserQuestion, marking your proposed size as recommended. Capture the user's choice.

If S, jump to Step 5.

### Step 3 — Initiative / project naming

For M+ work, propose a **name** and **one-line description** for the parent artifact (initiative for L/XL, project for M). Names should:
- Be specific enough to read in a Linear list six weeks from now.
- Match the user's existing naming pattern. Examples in this workspace: `gstack borrow`, `Per-project agent staffing skill`, `agent eval framework`.
- Avoid generic words like "improvements" or "enhancements" — they make the artifact invisible in search.

Confirm with the user before creating.

### Step 4 — Specialist recommendations

For M+ work, recommend which specialist agents should weigh in **before** issues get created. Recommendation, not auto-routing.

| Specialist | Call when (sharp criteria) |
|---|---|
| **product-manager** | The user's *intended end-user* is a **non-developer human** AND the change affects what they see or do. (NOT for dev-tool / internal-CLI / engineering-only work — those use plan-devex-review instead.) |
| **plan-devex-review** (skill) | Developer-facing surface — CLI flag, library API, SDK, framework, skill, dev tool. Most of our work falls here. |
| **tech-lead** | Architecture decision with **named tradeoffs** (two or more credible approaches), performance bet, or cross-cutting refactor. Not "M means call tech-lead." |
| **tpm** (technical-product-manager) | Cross-team or cross-repo coordination. Always for XL. |

Volume rule of thumb:
- **S:** none.
- **M:** zero or one (whichever lens dominates; often `plan-devex-review` alone for skill work, often none for refactors).
- **L:** one or two (the named-tradeoff lens + the end-user lens).
- **XL:** TPM always, plus the L set.

Tell the user **which specialists you'd call and why**. Let them choose. If you're recommending none, say so explicitly — silent zero feels like an omission.

### Step 5 — Create Linear artifacts

Use the `linear` CLI directly for creates (commands are stable; no need for a wrapper at v0). Reads still go through `sitrep-linear`.

**Preflight (do this once, before any create):**

```bash
# 0a. Linear CLI is installed and authed
linear --version >/dev/null || { echo "install @schpet/linear-cli"; exit 1; }
linear auth whoami >/dev/null 2>&1 || { echo "run: linear auth login"; exit 1; }

# 0b. Resolve the team key (same resolution order as sitrep-linear)
TEAM_KEY="$(sitrep-linear team-key)"
# Or, when sitrep-linear is not installed, derive manually from STATUS.md:
#   TEAM_KEY="$(awk '/^---$/{n++;next} n==1 && /^linear_team:/{print $2; exit}' STATUS.md | tr -d '"')"
[[ -n "$TEAM_KEY" ]] || { echo "cannot resolve team key — set linear_team in STATUS.md"; exit 1; }
```

For each create command, **capture the created artifact's URL** for the summary in Step 8. `--json` makes this reliable.

**S — single issue:**

```bash
# Write the body to a real file (not <(...) — Linear CLI is picky about heredocs).
ISSUE_BODY="$(mktemp)"; cat > "$ISSUE_BODY" <<'BODY'
<markdown body>
BODY

ISSUE_URL="$(linear issue create \
  --team "$TEAM_KEY" \
  -t "<one-line title>" \
  --description-file "$ISSUE_BODY" \
  -a self \
  -p <priority 1-4, default 3> \
  -s backlog \
  --no-interactive 2>&1 | grep -oE 'https://linear.app/[^[:space:]]+' | head -1)"
rm -f "$ISSUE_BODY"
echo "Issue: $ISSUE_URL"
```

If a project context already exists (from `STATUS.md` or just-created), add `--project "<project name>"` to the issue create.

**M — project + issues:**

```bash
# 1. Project. --initiative is optional; pass only if M is under an existing initiative.
INITIATIVE_NAME=""   # set to "" if standalone, else e.g. "gstack borrow"
PROJECT_JSON="$(linear project create \
  --team "$TEAM_KEY" \
  -n "<name>" \
  -d "<one-line description, ≤ 255 chars>" \
  ${INITIATIVE_NAME:+--initiative "$INITIATIVE_NAME"} \
  -l @me \
  -s planned \
  --target-date <YYYY-MM-DD> \
  --json)"
PROJECT_URL="$(printf '%s' "$PROJECT_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["url"])')"
PROJECT_NAME="$(printf '%s' "$PROJECT_JSON" | python3 -c 'import sys,json; print(json.load(sys.stdin)["name"])')"
echo "Project: $PROJECT_URL"

# 2. Issues under it (one per anticipated PR). Capture each URL.
for title in "issue-1 title" "issue-2 title" "issue-3 title"; do
    body_file="$(mktemp)"; printf '<body for %s>\n' "$title" > "$body_file"
    url="$(linear issue create \
        --team "$TEAM_KEY" \
        --project "$PROJECT_NAME" \
        -t "$title" \
        --description-file "$body_file" \
        -a self -p 3 -s backlog \
        --no-interactive 2>&1 | grep -oE 'https://linear.app/[^[:space:]]+' | head -1)"
    rm -f "$body_file"
    echo "Issue: $url"
done
```

**L — initiative + projects + issues:**

```bash
# 1. Initiative
INIT_OUT="$(linear initiative create \
  -n "<name>" \
  -d "<≤ 255 chars>" \
  -o @me \
  -s active \
  --target-date <YYYY-MM-DD> 2>&1)"
INIT_URL="$(printf '%s' "$INIT_OUT" | grep -oE 'https://linear.app/[^[:space:]]+' | head -1)"
INIT_NAME="<name>"   # same string you just passed to -n
echo "Initiative: $INIT_URL"

# 2. Projects per phase or per area (typically 3-6) — see M-shape, with --initiative "$INIT_NAME"
# 3. Issues per project (one per PR) — see M-shape
```

**XL — same as L plus:**

- Create a coordination doc:
  - Linear document via `linear document create -t "<name> coordination" --content-file <path>`, **OR**
  - `research/<name>-coordination.md` in the lead repo (preferred when version-controlled history matters).
- The doc must name:
  - Every repo touched.
  - The order of changes (which repo lands first, which depends on which).
  - The rollback path if any repo fails mid-rollout.
- Reference the coordination doc URL from every initiative/project description.

### Step 6 — Gates

For M+, **state explicitly** what gates the work must pass before any code lands:

- **M:** "/design-doc recommended. Plan-eng-review on the first non-trivial PR."
- **L:** "/design-doc required. Plan-eng-review on every M+ PR within."
- **XL:** "/design-doc required for the coordination doc. Plan-eng-review per repo. Cross-repo sequence written before any code lands."

(`/design-doc` and `plan-eng-review` are Week 3 deliverables. Until they exist, gate verbally — say what would be checked.)

### Step 7 — Update STATUS.md

Two cases, decide before editing:

**Case A — new active focus.** The ask becomes the project's main thread. Replace these fields:
- `current_objective` → new initiative/project's one-liner
- `linear_issue` → first issue created (if S/M) or the initiative's top-level tracker
- `linear_project` → new project URL
- `next_command` → first thing to do (often "kick off design-doc for X")
- Append a dated entry to "Decisions log (recent)".

**Case B — side quest.** Do NOT replace `current_objective`. Instead:
- Append the new artifact's URL to "Open items needing my attention" with a one-line context.
- Append a dated entry to "Decisions log (recent)".
- Leave `active_branch`, `active_pr`, `current_objective`, and `next_command` untouched.

**Test for side quest** (apply all three):
1. Is the new ask **unrelated** to `current_objective`? (Or only loosely related — follow-up, cleanup, parallel track.)
2. Is the user **not** asking you to switch to it right now? (No phrasing like "let's pivot" or "drop the current thing.")
3. Would changing `next_command` for the active branch be **wrong** because it'd lose the current thread?

If all three are yes → side quest, Case B. Else → Case A.

Use the diff-update pattern from `skills/sitrep/SKILL.md` Step 6 — preserve other fields.

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
