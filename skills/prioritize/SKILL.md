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
- After the **last** PR of an initiative merges AND `STATUS.md.next_command` is no longer specific (i.e. you genuinely need to pick a new thread). Do NOT fire after every PR merge — most merges have a clear next step already.
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

Filter rules (additive — every check below contributes; deduplicate at the end):

- All in-progress items (Linear state: started, or marked active via STATUS.md `linear_issue` matching).
- All P1 + P2 backlog items.
- All **open PRs you authored** — these belong in the prioritization. A PR with a stalled CI or a stale review-requested is often the highest-value next-action, not a new task.
- Anything explicitly blocked-on-user from STATUS.md.
- Top 5 P3 backlog items by recency (most recently updated first). **And** ask the user: "Any P3 you want included that I might have filtered out? — e.g. one with an external deadline, customer blocker, or PR dependency I can't see from Linear alone." This ask is the only way deadline/blocker info enters the filter for stale P3s, since the wrapper doesn't have visibility there.

State the cut-off explicitly so the user can override. Recency is a weak proxy — name it as such and offer the override.

### Step 3 — Score each candidate

For each candidate, the user has up to 4 inputs:

| Input | What you ask | How it scores |
|---|---|---|
| **Effort** | "S/M/L/XL?" (reuse `/work-breakdown` taxonomy: S=1 day, M=1-2 weeks, L=1-2 months, XL=months+) | Divisor — smaller effort scores higher |
| **Impact** | "One line: what does this unlock? Who benefits? What's the cost of not doing it?" | Qualitative; high-impact items get a 2-3× multiplier |
| **Blocker** | "Does this block other work? Is this blocked by something else?" | Items that unblock get a multiplier; items that are themselves blocked get deprioritized until the blocker resolves |
| **Deadline** | "External deadline? (date or 'no')" | Date-pressure multiplier — within 7 days = 2×, 14 days = 1.5×, >30 days or no deadline = 1× |

**Question budget — hard cap of 8 questions per `/prioritize` invocation.** Concrete rules:

- For each candidate, ask at most ONE consolidated question (effort + impact + blocker + deadline combined in a single AskUserQuestion with structured response, OR 4 quick free-form lines).
- If the candidate set is ≤ 4, ask each.
- If the candidate set is 5-8, ask only items where Linear state is ambiguous (P1/P2, or in-progress for > 14 days, or "important?" by your read). Infer the rest from Linear + recency.
- If > 8, ask only the top 4 by priority + recency; surface the remaining tail with `(inferred — confirm if wrong)` tags in Step 5.
- A user's "stop asking" reply ends the question pass — score the rest from defaults.

**Default inferences** (when not asking):
- Effort: M for backlog items with no recent activity; S for in-flight items.
- Impact: medium.
- Blocker: none unless STATUS.md `blocked_on_user` or Linear comments say otherwise.
- Deadline: none unless the issue title or description names a date.

**Heuristic shortcuts** (override scoring entirely):
- **P1 with a deadline within 7 days** → guaranteed top of list. Skip scoring; surface as "tier 1 (urgent)".
- **Item that blocks ≥ 2 other items** → guaranteed top 3 regardless of priority. Skip scoring; surface as "tier 1 (unblocks others)".
- **Stale P3 (> 30 days updated)** with no blocker / no deadline → bottom with a "consider closing" suggestion.

### Step 4 — Score, in tiers

**Tier-first, then score within tier.** This prevents the degenerate "P1 XL loses to P3 S" inversion that a multiplicative formula creates when effort spread is wide.

**Hard tiers (auto-placed; no scoring):**
- **Tier 1 (urgent)** — P1 with deadline ≤ 7 days, OR blocks ≥ 2 other items, OR blocked-on-user from STATUS.md. Order within tier by deadline-proximity then priority.
- **Tier 4 (deprioritize / consider closing)** — stale P3 (> 30 days no update) with no blocker, no deadline.

**Soft tiers (score within tier):**
- **Tier 2 (high priority)** — P1 + P2 not already in Tier 1.
- **Tier 3 (normal)** — P3 + in-flight items not already escalated.

**Within-tier score** = `impact_multiplier × deadline_multiplier × blocker_multiplier / effort_units`
- `impact_multiplier`: high=3, medium=2, low=1.
- `deadline_multiplier`: ≤7d=2, ≤14d=1.5, ≤30d=1.2, otherwise=1.
- `blocker_multiplier`: unblocks=1.5, blocked-by=0.5, else=1.
- `effort_units`: S=1, M=2, L=3, XL=4. **Gentle spread** — effort is a tiebreaker, not a dominant axis. (Codex round-1 fix: original 1/4/12/40 spread inverted priorities.)

**State your scoring inline** in Step 5 output so the user can challenge a specific item if your read of impact/blocker is wrong. Per CLAUDE.md Rule 6 (fail loud): tag each item's confidence as `(confirmed)` if the user provided the inputs or `(inferred)` if you defaulted.

### Step 5 — Surface the ranked list

Print in this format:

```
=== /prioritize ===
Active focus: <current_objective from STATUS.md>
Candidate set: <N> items (<X> in-flight, <Y> backlog, <Z> open PRs)
Questions asked: <K> of 8 budget

▎ TIER 1 (urgent — auto-placed, no scoring)

1. MIT-XXX — <title>  [P<n>, <effort>, <state>]  (confirmed | inferred)
   Why tier 1: deadline 2026-05-15 (3 days) / unblocks MIT-AAA + MIT-BBB / blocked-on-user since X
   Effort: <S/M/L/XL>  Impact: <high/med/low>

▎ TIER 2 (high priority — P1/P2)

2. MIT-YYY — <title>  [P<n>, <effort>, <state>]  (confirmed | inferred)
   Why second: <score = 3.0; impact high, no deadline pressure, S effort>

▎ TIER 3 (normal)

3. PR #N — <title>  [in-review, S]  (confirmed)
   Why third: open PR with stale review-requested; closing the loop unblocks merge.

(If two items tie in score, list them as `2a / 2b` and surface the tradeoff per CLAUDE.md Rule 5 — do NOT pick one.)

▎ TIER 4 (consider closing / deprioritize)

- MIT-CCC — last updated 45 days ago, no blocker, no deadline. Close as obsolete or schedule a session.

▎ BLOCKED ON YOU

- <items from STATUS.md blocked_on_user — needs a human decision, not a rerank>

Next command suggestion:
  → Start MIT-XXX (top of tier 1)
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
- **Mutate Linear.** No auto-close, no auto-priority change, no auto-state-transition, no auto-assignee change. The "consider closing" section is a recommendation; the user runs `linear issue update <id> -s canceled` themselves. The ONLY mutation is to STATUS.md `next_command` + decisions log, and only on explicit user confirmation.
- **Auto-pick between ties.** When two items score within 10% of each other, surface them as a tie with the tradeoff named per CLAUDE.md Rule 5 — do NOT silently pick.

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
