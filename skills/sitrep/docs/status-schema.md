# `STATUS.md` schema (v1)

The canonical session-state contract. Each project that uses `/sitrep` keeps a `STATUS.md` at the repo root. It is the **single source of truth** for "where is this project, right now."

`/sitrep` is the read+write client. Humans may edit it by hand; the format is markdown so it stays diffable.

---

## Why this exists

Pain C (session bootstrap) was: Claude opens unoriented every session. The user re-runs the same sitrep dance — "what's the status, what's next, what's blocking me." Without a written contract, every session rebuilds context from `linear`, `gh`, `git log`, and tribal memory.

`STATUS.md` is the persistent state that survives across sessions. It is **operational**, not reflective — what command to run next, who is blocked, what needs review.

## File layout

```markdown
---
status_version: 1
current_objective: "<one sentence>"
active_branch: "<git branch name or null>"
active_pr: "<#NN or URL or null>"
linear_issue: "<MIT-XXX or null>"
linear_project: "<URL or null>"
blocked_on_user: []      # list of objects (see below)
next_command: "<one sentence imperative>"
last_verified_state: "<ISO-8601 timestamp>"
links:
  initiative: "<URL or null>"
  project: "<URL or null>"
  handoff: "<repo-relative path or null>"
---

# <project name> status

## Current objective
<paragraph or bullets — the why behind active_branch>

## What's next
1. <ordered next steps>
2. ...

## Open items needing my attention
- <link> — <one-line context>
- ...

## Decisions log (recent)
- YYYY-MM-DD — <decision>
```

## Field reference

### Frontmatter (structured fields — machine-readable)

| Field | Type | Required | Meaning |
|---|---|---|---|
| `status_version` | int | yes | Schema version. v1 today. Bump when schema changes. |
| `current_objective` | string | yes | One sentence. Drop into `/sitrep` output verbatim. |
| `active_branch` | string\|null | yes | Current working branch. `null` if on main with nothing in flight. |
| `active_pr` | string\|null | yes | PR number or URL. `null` if no PR open. |
| `linear_issue` | string\|null | yes | Issue ID (e.g. `MIT-343`) the active work corresponds to. |
| `linear_project` | string\|null | no | Linear project URL if the work is under one. |
| `blocked_on_user` | list | yes | Things waiting on the human. Can be empty `[]`. Each item: `{item: string, since: ISO-date, link: URL\|null}`. |
| `next_command` | string | yes | One sentence imperative. The thing to do next in this project. |
| `last_verified_state` | ISO-8601 | yes | When `/sitrep` last ran end-to-end successfully. Stale value = trust the body sections less. |
| `links.initiative` | URL\|null | no | Linear initiative URL. |
| `links.project` | URL\|null | no | Same as `linear_project`. Duplicated for human convenience. |
| `links.handoff` | path\|null | no | Repo-relative path to a handoff/research doc if one exists. |

### Body sections (narrative — human-readable)

| Section | Required | Meaning |
|---|---|---|
| `## Current objective` | yes | Paragraph or bullets. The *why*, not just the *what*. |
| `## What's next` | yes | Ordered list of upcoming steps. The first item should match `next_command`. |
| `## Open items needing my attention` | yes | Items pulled from Linear (assigned-to-user), GitHub (PRs awaiting your review), Linear documents (design docs flagged for review). Can be empty. |
| `## Decisions log (recent)` | no | Last 5–10 dated decisions. Acts as a lightweight ADR trail when the project doesn't have a real `decisions/` directory. |

## When fields get updated

- `current_objective`, `links` — at project kickoff and when scope shifts.
- `active_branch`, `active_pr`, `linear_issue` — when starting/finishing a piece of work.
- `blocked_on_user` — when an agent or sub-agent produces something needing human review, OR when the user resolves a blocker.
- `next_command` — at the end of every `/sitrep` invocation (so the next session knows where to pick up).
- `last_verified_state` — set automatically by `/sitrep` when it finishes a full read pass.
- Body sections — updated by `/sitrep` (or by hand) whenever state changes.

## What this is NOT

- **Not a full ADR system.** Decisions log is a lightweight tail. Real architectural decisions belong in `decisions/` if the project warrants one.
- **Not a Linear replacement.** Linear is the queue + history. `STATUS.md` is the *operational landing page* — the one-page answer to "where am I and what do I do next."
- **Not a CHANGELOG.** Recent decisions, not recent commits.
- **Not version-controlled state for CI.** It is a developer-facing file, edited by humans + `/sitrep`. Don't gate merges on its content.

## Parsing rules (for `/sitrep`)

1. The frontmatter is delimited by `---` lines. Parse it as YAML.
2. If frontmatter is missing or malformed, treat the file as un-initialized — `/sitrep` should offer to write a fresh one.
3. Body sections are detected by `## ` headings with the exact text from the table above. Extra sections are preserved on write.
4. On write, `/sitrep` should diff-update fields rather than rewriting the whole file — preserves human edits and trailing notes.
5. `blocked_on_user` items survive `/sitrep` writes unless explicitly cleared by the user via prompt.

## Versioning

`status_version: 1`. If the schema changes:
- Bump `status_version`.
- Document the migration in this file.
- `/sitrep` should detect lower versions and offer an in-place migration.
