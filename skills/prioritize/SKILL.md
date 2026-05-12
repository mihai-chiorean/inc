---
name: prioritize
description: |
  Rank in-flight work + backlog items and surface the top 3 to do next, with rationale. Reads STATUS.md + `sitrep-linear inbox`; asks the user about effort/impact/blockers/deadlines for high-signal items; emits an ordered list. Single-project, single-pass — each invocation is from scratch (no persistent priority cache).

  Use when the user says "what should I work on next", "/prioritize", "rank the inbox", "what's most important", or any version of "I have too many things, help me pick." Also use at sprint-equivalent transitions (e.g. an initiative wraps and you need to choose the next thread).

  Last of the gstack-borrow week-skills. `/retro` and `/triage` were explicitly dropped (indulgent or overlapping); `/prioritize` is the single Week-4 deliverable.
version: 0
allowed-tools: Bash, Read, Edit, AskUserQuestion
---

# /prioritize — rank work, surface the top 3

You are the prioritization decision-aide. Read what's in flight, read the backlog, ask the user enough to score, output a defensible order. The user picks; you don't decide.

This skill is **procedural-only** (no wrapper). It consumes `sitrep-linear inbox` (Week 1) + STATUS.md (Week 1 schema) + the user's judgment on effort/impact/blockers/deadlines (Week 2 vocabulary).

---

## When to fire

- "What should I work on next?" / "/prioritize" / "rank the inbox" / "what's most important right now"
- After a PR merges, especially the last PR of an initiative — natural decision point.
- After a `/sitrep` shows a large inbox (≥ 6 items) and the user says "this is a lot."
- User feels stuck or context-switching between too many threads.

**Do NOT fire** when:
- The user is mid-task and asks an implementation question. Don't derail.
- The inbox is trivially small (≤ 2 items) — no ranking needed, just tell them to pick.
- The user already has a clear active focus per STATUS.md `current_objective` and isn't asking to switch.

---

## Procedure

### Step 1 — Gather state

```bash
# Active focus + blocked items
sed -n '/^---$/,/^---$/p' STATUS.md      # frontmatter, for current_objective + blocked_on_user
sitrep-linear inbox                       # scoped Linear inbox (backlog + in-progress)
# Also: open PRs you're authoring
gh pr list --author @me --state open --json number,title,headRefName,url --limit 20
```

State the gathered shape in one line:
> *"You have 1 active focus (current_objective), 0 blocked-on-you, N inbox issues (X in-progress + Y backlog), M open PRs."*

If `current_objective` and `next_command` are already specific and the inbox isn't overwhelming, the prioritization may be already-done — say so and ask whether the user wants to re-rank anyway.

### Step 2 — Identify the candidate set

Not every backlog item needs scoring. Filter to:

- All in-progress items (Linear state: started, or marked active via STATUS.md `linear_issue` matching).
- All P1 + P2 backlog items.
- Top 5 P3 backlog items by recency (most recently updated first).
- Anything explicitly blocked-on-user from STATUS.md.

Drop everything else from the prioritization pass. State the cut-off so the user can override if they want a P3 considered.

### Step 3 — Score each candidate

For each candidate, the user has up to 4 inputs:

| Input | What you ask | How it scores |
|---|---|---|
| **Effort** | "S/M/L/XL?" (reuse `/work-breakdown` taxonomy: S=1 day, M=1-2 weeks, L=1-2 months, XL=months+) | Divisor — smaller effort scores higher |
| **Impact** | "One line: what does this unlock? Who benefits? What's the cost of not doing it?" | Qualitative; high-impact items get a 2-3× multiplier |
| **Blocker** | "Does this block other work? Is this blocked by something else?" | Items that unblock get a multiplier; items that are themselves blocked get deprioritized until the blocker resolves |
| **Deadline** | "External deadline? (date or 'no')" | Date-pressure multiplier — within 7 days = 2×, 14 days = 1.5×, >30 days or no deadline = 1× |

**How to ask:** in batches via AskUserQuestion when the candidate set is small (≤ 4). For larger sets, ask only about the top-priority ambiguous items and infer the rest from Linear state + recency. **Never** ask 16 questions in a row.

**Heuristic shortcuts:**
- P1 with a deadline this week → top of list, no questioning needed.
- Stale P3 with no recent updates (> 30 days) → either retire or surface to user. Default: bottom of list with a "consider closing" suggestion.
- An item that blocks ≥ 2 other items → bump up regardless of priority.

### Step 4 — Score

Score = `priority_weight × impact_multiplier × deadline_multiplier × blocker_multiplier / effort_units`

- `priority_weight`: P1=8, P2=4, P3=2, P4=1 (or unscored=2).
- `impact_multiplier`: high=3, medium=2, low=1 (your read; user can override).
- `deadline_multiplier`: within 7 days=2, 14 days=1.5, otherwise=1.
- `blocker_multiplier`: unblocks 2+ items=1.5, blocks me=0.5 (deprioritize until resolved), else=1.
- `effort_units`: S=1, M=4, L=12, XL=40.

The exact numbers aren't sacred — what matters is the relative ordering. **State your scoring inline** so the user can challenge a specific item if your read of impact/blocker is wrong.

### Step 5 — Surface the ranked list

Print in this format:

```
=== /prioritize ===
Active focus: <current_objective from STATUS.md>
Candidate set: <N> items (<X> in-flight, <Y> backlog)

▎ TOP 3 — do these next, in this order

1. MIT-XXX — <title>  [P<n>, <effort>, <state>]
   Why first: <one-line rationale: impact + deadline + blocker math>
   Effort: <S/M/L/XL>  Impact: <high/med/low>  Deadline: <date or none>

2. MIT-YYY — <title>  [P<n>, <effort>, <state>]
   Why second: ...

3. MIT-ZZZ — <title>  [P<n>, <effort>, <state>]
   Why third: ...

▎ ALSO RECOMMENDED (in order)

4. MIT-AAA — <title>  (brief rationale)
5. MIT-BBB — <title>  (brief rationale)
...

▎ CONSIDER CLOSING / DEPRIORITIZING

- MIT-CCC — last updated 45 days ago, no blocker, no deadline. Either close as obsolete or schedule.
- MIT-DDD — blocked by MIT-EEE which is itself stale. Address the blocker first.

▎ BLOCKED ON YOU

- <items from STATUS.md blocked_on_user — call out separately, these need a human decision not a rerank>

Next command suggestion:
  → Start MIT-XXX (top of list)
```

### Step 6 — Confirm and (optionally) update STATUS.md

Ask: "Pick the top item? I can update STATUS.md `next_command` to 'Start MIT-XXX'."

On yes:
- Update STATUS.md frontmatter: `next_command` → "Start MIT-XXX — <title>"
- Append a decisions-log entry: `YYYY-MM-DD — Ran /prioritize; picked MIT-XXX as next. Top 3 was [list].`
- Apply the standard side-quest test from `/work-breakdown` Step 7 — if MIT-XXX is unrelated to `current_objective`, treat as Case B (don't replace current_objective; add to Open items).

On no: leave STATUS.md untouched. The ranking is advisory.

---

## What `/prioritize` does NOT do (yet)

- **Cross-project rollup.** v0 is single-project (uses `linear_scope`). The cross-project case is the `/sitrep --all` future work (MIT-345).
- **Persistent priority cache.** Each run starts from scratch — by design. Caching priorities means stale priorities; the user's intuition shifts session-to-session.
- **Auto-rerank.** Manual invocation only. No hooks, no scheduled runs.
- **Effort/impact estimation.** The user provides these. Asking the LLM to estimate "impact" without context produces marketing fluff.
- **Closing items automatically.** The "consider closing" section is a recommendation; the user runs `linear issue update <id> -s canceled` themselves.

---

## Examples

### Example A — clean inbox, light prioritization

```
=== /prioritize ===
Active focus: Week 4 of gstack-borrow — /prioritize skill
Candidate set: 4 items (1 in-flight, 3 backlog)

▎ TOP 3 — do these next, in this order

1. MIT-367 — /prioritize skill   [P3, S, in-flight]
   Why first: active focus per STATUS.md current_objective; you're already on the branch.
   Effort: S  Impact: med  Deadline: none

2. MIT-345 — /sitrep --all cross-project rollup   [P3, S, backlog]
   Why second: S-sized, unblocks a real pain (cross-project state via tmux tabs), no deadline.
   Effort: S  Impact: med  Deadline: none

3. MIT-294 — Routing dataset schema + interactive labeling tool   [P3, M, backlog]
   Why third: Project B foundations; longer-running so getting started early matters.
   Effort: M  Impact: high (eval framework foundation)  Deadline: none

▎ ALSO RECOMMENDED

4. MIT-295 — Hand-label 30 routing prompts  (depends on MIT-294; sequencing)

▎ CONSIDER CLOSING / DEPRIORITIZING

(none; inbox is clean post-Week-3b)

▎ BLOCKED ON YOU — clear

Next command suggestion:
  → Stay on MIT-367 (already active; finish it)
```

### Example B — overwhelmed inbox

```
=== /prioritize ===
Active focus: <none clear — current_objective hasn't been updated since the rebrand>
Candidate set: 9 items (2 in-flight, 7 backlog)

⚠ Two things in-flight at once is the failure mode this skill exists for. Picking ONE.

▎ TOP 3 — do these next, in this order
...

▎ CONSIDER CLOSING / DEPRIORITIZING

- MIT-120 — "60-day content plan" (last updated 30 days ago, no blocker, no deadline). Either close or schedule a session.

Next command suggestion:
  → Drop MIT-XXX (your second in-flight), focus on MIT-YYY. Update STATUS.md to reflect single active focus.
```

---

## Pointers

- **Reads:** STATUS.md, `sitrep-linear inbox`, `gh pr list`. Optionally `git status` for uncommitted-in-flight signal.
- **Writes:** STATUS.md (only on user confirmation; `next_command` + decisions log).
- **Composes with:** [`/sitrep`](../sitrep/SKILL.md) (the orient skill — `/prioritize` is the "now decide" follow-up), [`/work-breakdown`](../work-breakdown/SKILL.md) (the S/M/L/XL taxonomy this reuses for Effort).
- **Reuses:** the side-quest test from `/work-breakdown` Step 7 when deciding whether to update `current_objective`.
- **CLAUDE.md rules:** Rule 5 (Surface conflicts — if two items are tied, name the tradeoff; don't auto-pick), Rule 6 (Fail loud — state the scoring inline so the user can challenge).
