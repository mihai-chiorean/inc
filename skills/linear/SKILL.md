---
name: linear
description: 'Linear CLI for issue tracking and project management. Use when developers mention: (1) Linear issues or tickets, (2) issue tracking or task management, (3) MIT team issues, (4) closing, updating, or triaging tickets, (5) linking PRs to issues, (6) issue states (triage, backlog, started, completed), (7) Linear projects, (8) project create/update/delete, (9) milestones, cycles, initiatives, labels, documents, (10) agent sessions.'
---

# Linear CLI

## Overview

The Linear CLI (`linear` v2.0.0) provides command-line access to Linear issue tracking. Source: https://github.com/schpet/linear-cli

Installed via npm (global) at `~/.local/lib/node_modules/@schpet/linear-cli`, with the `linear` binary symlinked at `~/.local/bin/linear`. Requires Node.js ≥ 14 (currently 22.x from NodeSource).

To upgrade:

```bash
npm install -g @schpet/linear-cli@latest
linear --version
```

If `node`/`npm` are missing, install via `sudo apt-get install -y nodejs` (NodeSource 22.x repo is configured). The npm prefix is set to `~/.local` in `~/.npmrc` so globals land there.

## Authentication

Credentials are stored in the system keyring (Linux: libsecret) via `linear auth login`. For CI, bot accounts, or non-desktop sessions, set `LINEAR_API_KEY=lin_api_...` — it takes precedence over the keyring. Get a key from https://linear.app/settings/account/security.

```bash
linear auth login              # interactive; stores in keyring
linear auth login --plaintext  # stores in ~/.config/linear/credentials.toml instead
linear auth whoami             # show current user
linear auth list               # show all configured workspaces
linear auth default <slug>     # set default workspace
linear --workspace <slug> ...  # override default per-command
```

Priority order: `--api-key` flag → `LINEAR_API_KEY` env → `.linear.toml` project config → `--workspace` flag → default workspace from keyring.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `LINEAR_API_KEY` | API key; overrides keyring. Use for CI, bots, alternate identities. |
| `LINEAR_ISSUE_SORT` | Default sort for list commands (`priority` or `manual`). |
| `LINEAR_DEBUG=1` | Show full error details including stack traces. |
| `LINEAR_DOWNLOAD_IMAGES=false` | Disable automatic image download in `issue view`. |
| `LINEAR_HYPERLINK_FORMAT` | OSC-8 hyperlink format for image links in `issue view`. |

## Important Notes

- Always pass `--no-pager` when listing issues/projects in scripts to avoid hanging on the interactive pager.
- Many commands accept an optional `[issueId]` — if omitted, the CLI infers the issue from the current git branch name (or jj `Linear-issue` trailer).
- Default team for the workspace is **MIT (Mitzoku)** — not WDY. Use `linear team list` to confirm.
- **v2.0.0 breaking changes vs 1.x:** `issue list` was split into `issue mine` (personal queue) and `issue query` (cross-team/structured filtering); `list` is an alias for `mine` but deprecated. JSON output now preserves GraphQL field names and connection shape — if you were parsing 1.x JSON, adapt your parsers.

## Top-level commands

| Command | Purpose |
|---------|---------|
| `auth` | Manage Linear authentication (login, logout, list, default, token, whoami, migrate) |
| `issue`, `i` | Manage issues (create, update, view, mine, query, comment, attach, link, relation, agent-session, etc.) |
| `team`, `t` | Manage teams |
| `project`, `p` | Manage projects (create, update, delete, list, view) |
| `project-update`, `pu` | Manage project status updates |
| `cycle`, `cy` | Manage team cycles |
| `milestone`, `m` | Manage project milestones |
| `initiative`, `init` | Manage initiatives |
| `initiative-update`, `iu` | Manage initiative status updates |
| `label`, `l` | Manage issue labels |
| `document`, `docs`, `doc` | Manage Linear documents |
| `api` | Make raw GraphQL API requests |
| `schema` | Print the GraphQL schema to stdout |
| `config` | Interactively generate `.linear.toml` configuration |
| `completions` | Generate shell completions |

## Issue States

| State       | Description                    |
|-------------|--------------------------------|
| `triage`    | New issues needing triage      |
| `backlog`   | Prioritized but not started    |
| `unstarted` | Ready to start (Todo)          |
| `started`   | In Progress                    |
| `completed` | Done                           |
| `canceled`  | Canceled / Won't do            |

## Issues: `mine` vs `query`

**`issue mine`** — your personal work queue. Defaults to `unstarted` issues assigned to you on your default team.

```bash
linear issue mine --no-pager                          # default: your unstarted issues
linear issue mine --no-pager -s started -s unstarted  # multiple states
linear issue mine --no-pager --all-states             # all states
linear issue mine --no-pager --team MIT               # override default team
linear issue mine --no-pager --project "Project Name"
linear issue mine --no-pager --cycle active
linear issue mine --no-pager --milestone "MVP" --project "Project Name"  # milestone needs project
linear issue mine --no-pager --label "Bug" -l "P1"    # repeatable
linear issue mine --no-pager --project-label "Infra"  # label across all projects
linear issue mine --no-pager --created-after 2026-04-01
linear issue mine --no-pager --updated-after 2026-04-10
linear issue mine --no-pager --limit 10               # 0 = unlimited
```

`linear issue list` is still accepted as an alias for `mine` but deprecated — don't use it in new scripts.

**`issue query`** — structured filtering across teams, full-text search, `--json` output.

```bash
linear issue query --all-teams --no-pager                     # across workspace
linear issue query --team MIT --team ENG --no-pager           # multiple teams
linear issue query --search "login bug" --no-pager            # full-text
linear issue query --search "token" --search-comments --no-pager  # include comments
linear issue query --assignee mihai --no-pager                # by username
linear issue query -U --no-pager                              # unassigned only
linear issue query --team MIT --json                          # machine-readable
linear issue query --include-archived --team MIT --no-pager
```

All `mine` filters (`--label`, `--project`, `--cycle`, `--milestone`, `--project-label`, `--created-after`, `--updated-after`, `--limit`) also work on `query`. `--search` disables `--sort`.

## View / identify issues

```bash
linear issue view MIT-123 --no-pager       # markdown: title, state, priority, assignee, description, documents, attachments
linear issue view MIT-123 --web            # open in browser
linear issue view MIT-123 --app            # open in Linear desktop app

linear issue id                            # current branch → issue ID
linear issue title MIT-123                 # just the title
linear issue describe MIT-123              # title + Linear-issue trailer (for commits)
linear issue url MIT-123                   # just the URL
linear issue commits MIT-123               # all commits referencing issue (jj only)
```

## Create issues

```bash
linear issue create \
  --team MIT \
  -t "Issue title" \
  -d "Description (markdown)" \
  -a self \
  -p 2 \
  --estimate 3 \
  -l "Bug" \
  -s backlog \
  --project "Project Name" \
  --no-interactive

# Long description from a file
linear issue create --team MIT -t "Title" --description-file ./issue-body.md --no-interactive

# Create and immediately start (makes a git branch, sets state)
linear issue create --team MIT -t "Title" --start --no-interactive

# Sub-issue
linear issue create --team MIT -t "Sub-task" --parent MIT-42 --no-interactive
```

**Flags:** `-t` title, `-d` description (or `--description-file <path>` — preferred for markdown), `-a` assignee (`self`, username, or name), `-p` priority 1-4 (1=urgent), `--estimate` points, `-l` label (repeatable), `-s` state, `--project` name or slug (must already exist), `--parent` team-number code (e.g. `MIT-123`), `--milestone` name (requires `--project`), `--cycle` name/number/`active`, `--due-date YYYY-MM-DD`, `--start`, `--no-use-default-template`, `--no-interactive`.

## Update issues

```bash
linear issue update MIT-123 -s completed
linear issue update MIT-123 -s started
linear issue update MIT-123 -t "New title" -d "New description" -a self -p 1
linear issue update MIT-123 --project "Project Name" -l "Enhancement"
```

## Comments, attachments, links

```bash
linear issue comment add MIT-123 -m "Comment body in markdown"
linear issue comment list MIT-123
linear issue comment update <commentId> -m "Revised"
linear issue comment delete <commentId>
linear issue comment add MIT-123 -m "See screenshot" --attach /path/to/file.png

linear issue attach MIT-123 /path/to/file.png                    # attach file
linear issue link MIT-123 https://github.com/org/repo/pull/123   # link URL
linear issue link https://example.com --title "Design doc"       # infers issue from branch
```

## Issue relations, start, PR

```bash
linear issue relation --help               # dependency types: blocks, blocked-by, duplicate-of, related

linear issue start MIT-123                 # creates git branch, sets state to started
linear issue start MIT-123 -f main         # branch from specific ref
linear issue start MIT-123 --branch custom-name

linear issue pull-request MIT-123          # (alias: pr) makes GitHub PR with title/body preset
linear issue pr MIT-123 --draft --base main -t "Custom PR title" --web
```

## Agent sessions

Linear Agents (apps installed via OAuth with `actor=app`) get delegated issues and run sessions. The CLI can inspect those sessions:

```bash
linear issue agent-session list MIT-123     # sessions for an issue (infers from branch if omitted)
linear issue agent-session view <sessionId> # session details (activities, thoughts, etc.)
```

Setup for your own agent lives outside the CLI: Workspace settings → Applications → create app, enable webhooks with **Agent session events**, install via OAuth. Assigned issues fire `AgentSessionEvent`; the agent must emit a `thought` activity within 10 s. Agents don't consume a billable seat. For a simpler (billable) alternative, create a bot user and use its `LINEAR_API_KEY`.

## Delete issue

```bash
linear issue delete MIT-123
linear issue delete --bulk MIT-1 MIT-2 MIT-3
```

## Projects

```bash
# Create
linear project create \
  -t MIT \
  -n "Project name" \
  -d "Description (≤255 chars)" \
  -l @me \
  -s started \
  --start-date 2026-04-10 \
  --target-date 2026-06-10 \
  --json

# List / view / update / delete
linear project list --team MIT
linear project list --team MIT --status "In Progress"
linear project view PROJECT-ID-OR-SLUG
linear project update PROJECT-ID -n "New name" -s completed --target-date 2026-07-01
linear project delete PROJECT-ID           # moves to trash

# Status updates to the project timeline
linear project-update --help
```

**Create flags:** `-n` name (required), `-t` team (required, repeatable), `-d` description (≤255), `-l` lead (`@me`, username, email), `-s` status (planned, started, paused, completed, canceled, backlog), `--start-date`, `--target-date` (YYYY-MM-DD), `--initiative` (id/slug/name), `-j/--json`.

## Milestones, cycles, initiatives, labels, documents

```bash
linear milestone --help
linear cycle list --team MIT               # --json supported
linear cycle view <id>
linear initiative --help                   # list, view, create, archive, update, delete, add-project, remove-project
linear initiative-update --help            # timeline posts
linear label list --team MIT
linear label create --team MIT -n "Bug" --color "#ef4444"
linear label delete <id>
linear document list
linear document view <id>
linear document create -t "Title" -c "Content"
```

## Teams

```bash
linear team list
linear team id
linear team members MIT
linear team autolinks                      # configure GitHub autolinks
```

## Raw GraphQL

For anything the CLI doesn't expose:

```bash
linear schema | less                       # browse schema (SDL)
linear schema --json                       # JSON schema
linear api '{ viewer { id name } }'        # raw query
```

## JSON output

`--json` (or `-j`) is supported on `issue query`, `issue mine`, `issue create`, `project create`, `project list`, `cycle list`, and most commands where machine-readable output makes sense. In v2.0.0, JSON preserves GraphQL field names and connection shape (e.g. `{ "nodes": [...], "pageInfo": {...} }`) — if you have parsers from 1.x, they need updating.

## Workflows

### Start work on an issue

```bash
linear issue start MIT-123                 # branch + state=started
# ... commit work ...
linear issue pr MIT-123 --draft            # create linked PR
linear issue update MIT-123 -s completed   # after merge
```

### Triage new issues

```bash
linear issue query --team MIT --no-pager -s triage
linear issue update MIT-42 -s backlog -p 3
```

### Create a project + seed issues

```bash
linear project create -t MIT -n "Project name" -d "Short description" -l @me -s started --json

linear issue create --team MIT --project "Project name" --no-interactive \
  -a self -t "First task" --description-file ./task1.md
```

### Cross-reference issues with commits

```bash
linear issue query --team MIT --no-pager -s started -s unstarted
git log --oneline -30 --all
```

### Bot/agent queries

```bash
LINEAR_API_KEY=lin_api_bot_key linear issue mine --no-pager   # what's assigned to the bot
LINEAR_API_KEY=lin_api_bot_key linear issue agent-session list MIT-123
```
