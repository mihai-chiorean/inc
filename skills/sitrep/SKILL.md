---
name: sitrep
description: |
  Session bootstrap and operational landing page. Run at session start (or on demand) to surface "where you are, what's next, and what's blocked on you" for the current project. Reads STATUS.md, Linear (assigned-to-you), GitHub (PRs awaiting your review, your open PRs), and recent commits. Writes back updates to STATUS.md.

  Use when the user says "sitrep", "where am I", "what's the status", "what's next", or any session-start orientation request. Also use proactively at session start per CLAUDE.md rule 1.
version: 0
allowed-tools: Bash, Read, Edit, Write, Glob, Grep
---

# /sitrep — operational landing page

You are the read+write client for `STATUS.md`. Your job is to surface a single one-page answer to "where am I right now and what do I do next" — using `STATUS.md` as the persistent contract.

The schema is documented at `skills/sitrep/docs/status-schema.md` in the claude-agents repo. Read it once if you have not — it specifies the fields you read and write.

---

## When to fire

- Session start (per CLAUDE.md rule 1 in any repo that has a CLAUDE.md referencing this skill).
- User says "sitrep", "where am I", "what's the status", "what's next on this project".
- After resolving a blocker or finishing a PR — to refresh "what's next" before the next move.

If the user's first message is an explicit task that bypasses bootstrap, **still** surface a one-line orientation from `STATUS.md` if it exists, then proceed with the task.

---

## Procedure

### Step 1 — Detect project root

Find the project root by walking up from the current working directory looking for:
1. A `STATUS.md` file (preferred — the explicit contract).
2. A `.git` directory (fallback — git root).

```bash
git rev-parse --show-toplevel
```

If neither exists, this is not a `/sitrep` context. Tell the user and stop.

### Step 2 — Read STATUS.md

Read `STATUS.md` at the project root.

**If missing or malformed (no YAML frontmatter):** offer to bootstrap it. Use the schema doc as the template. Seed defaults from:
- `active_branch` ← `git branch --show-current`
- `linear_issue` ← parse from branch name (e.g. `mit-343-…` → `MIT-343`)
- Other fields ← prompt or leave null
Once written, continue with Step 3.

**If present:** parse the YAML frontmatter and the four markdown body sections (`## Current objective`, `## What's next`, `## Open items needing my attention`, `## Decisions log (recent)`).

### Step 3 — Gather live state in parallel

Run these in a single batch (multiple `Bash` tool calls in one message). All Linear queries go through the **`sitrep-linear` wrapper** (`skills/sitrep/bin/sitrep-linear`, symlinked to `~/.local/bin/sitrep-linear`) — it hides Linear CLI v1/v2 differences and team-key resolution so this SKILL.md doesn't have to. See [`bin/sitrep-linear --help`](bin/sitrep-linear) for the contract.

```bash
# 1. Current branch + uncommitted state
git status --short && git branch --show-current

# 2. Recent commits on the branch
git log --oneline -10

# 3. Linear issues assigned to me (wrapper resolves team key + CLI version)
sitrep-linear inbox

# 4. PRs awaiting user's review
gh pr list --search 'review-requested:@me state:open' --json number,title,author,url,headRepository --limit 20

# 5. User's own open PRs (workspace-wide)
gh pr list --author @me --state open --json number,title,url,headRefName,statusCheckRollup --limit 20

# 6. Branch-specific PR (to reconcile STATUS.md's `active_pr`)
gh pr list --author @me --state open --head "$(git branch --show-current)" --json number,url --limit 1

# 7. (Optional) Linear documents flagged for review
sitrep-linear docs | head -30
```

**If `sitrep-linear` is not on `$PATH`:** the wrapper lives at `skills/sitrep/bin/sitrep-linear` in the claude-agents repo. Symlink it onto `$PATH`:

```bash
ln -sf "$(git -C ~/workspace/claude-agents rev-parse --show-toplevel)/skills/sitrep/bin/sitrep-linear" ~/.local/bin/sitrep-linear
```

If the wrapper fails entirely (Linear CLI missing, no auth), fall back to surfacing what you have and noting the gap in the output's footer.

**Failure handling:**
- `gh` not authed or no GitHub remote → skip GitHub queries silently; note in output.
- `linear` not authed → tell the user once; continue with what you have.
- Network failure → use cached STATUS.md only; mark `last_verified_state` as stale in output.

### Step 4 — Reconcile

Compare STATUS.md frontmatter against live state:

| STATUS.md says | Live state | Action |
|---|---|---|
| `active_branch: X` | git branch is X | Confirm. |
| `active_branch: X` | git branch is Y | Flag in output: "STATUS.md is stale — on branch Y, STATUS says X." |
| `linear_issue: MIT-N` | Linear shows MIT-N completed | Flag: "MIT-N is done. Time to advance `next_command`?" |
| `active_pr: null` | Step 3 query #6 (`gh pr list --author @me --head <branch>`) finds one | Flag: "PR opened since last sitrep — update STATUS.md." Derive `active_pr` from that query's first result. |
| `active_pr: #N` | Step 3 query #6 finds nothing for current branch | Flag: "STATUS.md `active_pr` is stale or wrong branch." |
| `blocked_on_user` non-empty | Each item still relevant? | Ask user; clear resolved items. |

### Step 5 — Surface the landing page

Output format (use exactly these section labels; the user has learned to scan them):

```
=== sitrep: <repo name> ===
Branch:    <active_branch>  →  <linear_issue> [<state>]
PR:        <active_pr or "none">
Objective: <one sentence from current_objective>

▎ NEXT
  → <next_command>

▎ BLOCKED ON YOU (<N>)
  • <item>  (since <date>, <link>)
  • ...
  (or "▎ BLOCKED ON YOU — clear")

▎ INBOX (<N> issues, <M> PRs for review)
  • <MIT-XXX> [P<n>] <title>
  • ...
  • PR #<n> <title> (author: @<who>)
  • ...

▎ YOUR OPEN PRS (<N>)
  • PR #<n> <title>  [<CI status>]
  • ...

▎ RECENT DECISIONS
  • <YYYY-MM-DD> — <decision>
  • ... (up to 5)

Last verified: <timestamp>  [stale | just now | <duration> ago]
```

**Truncation rules:** if Inbox has > 8 issues, show top 5 by priority + "(N more)". If user has > 5 open PRs, show 5 most recently updated + "(N more)".

### Step 6 — Write back

After surfacing the landing page, **prompt the user**:

> "Want me to update STATUS.md? Refreshing: `last_verified_state` → now, `active_branch`/`active_pr` → live state, plus any new decisions or blockers you mention."

Accept yes/no. If yes:
- Diff-update the YAML frontmatter (do NOT rewrite — preserve fields you didn't touch).
- Update `last_verified_state` to ISO-8601 now.
- Update `active_branch`, `active_pr` from live state.
- If the user dictated a new `next_command` or decision, append it.
- Use the `Edit` tool with exact-string replacement to update.

If the user mentions a new blocker in conversation ("waiting on you to review the manifest change"), offer to add it to `blocked_on_user`.

---

## What `/sitrep v0` does NOT do (yet)

- **Cross-project sweep.** v0 is single-project. The pain B (cross-project state via tmux tabs) is bigger and gets a `/work-breakdown`-adjacent treatment later if needed.
- **Automatic agent dispatch.** v0 surfaces the inbox; it does not auto-route review items to specialist agents.
- **Notifications.** No push, no email. The user runs `/sitrep` when they want.
- **CI status enrichment beyond `gh pr list --json statusCheckRollup`.** No flake analysis, no log digging.

These are deferred to v1+ based on whether v0 is actually used.

---

## Examples

**Example A — clean state, mid-project**

```
=== sitrep: claude-agents ===
Branch:    mit-343-week1-bootstrap-loop  →  MIT-343 [started]
PR:        none
Objective: Week 1 of gstack-borrow — ship the bootstrap loop

▎ NEXT
  → Build /sitrep v0 skill (after CLAUDE.md lands)

▎ BLOCKED ON YOU — clear

▎ INBOX (2 issues, 0 PRs for review)
  • MIT-302 [P3] manifest regen automation
  • MIT-291 [P2] eval framework foundations

▎ YOUR OPEN PRS (0)

▎ RECENT DECISIONS
  • 2026-05-11 — Codex review applied; dropped ETHOS + /codex skill
  • 2026-05-11 — Boil-the-lake fully adopted
  • 2026-05-11 — STATUS.md schema v1 defined

Last verified: 2026-05-11T18:00:00Z  (just now)
```

**Example B — STATUS.md missing**

```
No STATUS.md found at repo root.

I can bootstrap one. Current state I can see:
  • git branch: mit-343-week1-bootstrap-loop
  • inferred Linear issue: MIT-343
  • git remote: github.com/mihai-chiorean/claude-agents

What's the current_objective for this project? (one sentence)
```

**Example C — stale frontmatter**

```
=== sitrep: claude-agents ===
⚠ STATUS.md is stale.
  • active_branch says "mit-340-...", but git is on "mit-343-week1-...".
  • last_verified_state is 6 days ago.

I'll refresh after I show you the current picture.

[... rest of landing page ...]
```

---

## Notes for future versions

- **Cross-project rollup** (`/sitrep --all`): scan ~/workspace/* for STATUS.md files and surface the union. Pain B fix.
- **Pre-fetch Linear documents flagged with `review:` label** rather than dumping all docs. Requires Linear-side convention.
- **Persist a tiny cache** of last `gh`/`linear` results so a second `/sitrep` within N seconds doesn't re-hit the network.
- **Trigger heuristic**: if `last_verified_state` is more than 24h old at session start, fire automatically without asking.

These are not in v0.
