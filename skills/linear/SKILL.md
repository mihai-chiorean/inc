---
name: linear
description: 'Linear CLI for issue tracking and project management. Use when developers mention: (1) Linear issues or tickets, (2) issue tracking or task management, (3) MIT team issues, (4) closing, updating, or triaging tickets, (5) linking PRs to issues, (6) issue states (triage, backlog, started, completed), (7) Linear projects, (8) project create/update/delete, (9) milestones, cycles, initiatives, labels, documents.'
---

# Linear CLI

## Overview

The Linear CLI (`linear` v1.11.1) provides command-line access to Linear issue tracking, installed at `/usr/local/bin/linear`. Source: https://github.com/schpet/linear-cli

To upgrade: download the latest x86_64 linux binary from the releases page, extract, and replace `/usr/local/bin/linear`. Mihai owns the binary so no sudo required:

```bash
cd /tmp
curl -sL -o linear-latest.tar.xz https://github.com/schpet/linear-cli/releases/download/vX.Y.Z/linear-x86_64-unknown-linux-gnu.tar.xz
tar -xf linear-latest.tar.xz
cp linear-x86_64-unknown-linux-gnu/linear /usr/local/bin/linear
chmod +x /usr/local/bin/linear
linear --version
```

**v2.0.0 is a breaking release** (restructured JSON output, split `issue mine` and `issue query`). Stay on 1.x unless ready to update workflows.

## Important Notes

- Always pass `--no-pager` when listing issues or projects to avoid hanging on the interactive pager.
- `LINEAR_ISSUE_SORT=priority` must be set (or use `--sort priority`) for `issue list` commands — they error without it.
- Many commands accept an optional `[issueId]` — if omitted, the CLI infers the issue from the current git branch name.
- Default team for the workspace is **MIT (Mitzoku)** — not WDY. Use `linear team list` to confirm.

## Top-level commands (v1.11.1)

| Command | Purpose |
|---------|---------|
| `auth` | Manage Linear authentication |
| `issue`, `i` | Manage issues (create, update, view, list, comment, attach, relation, etc.) |
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

## Issues

```bash
# List active issues (default: unstarted only)
LINEAR_ISSUE_SORT=priority linear issue list --team MIT --no-pager

# Filter by state(s) — repeatable
LINEAR_ISSUE_SORT=priority linear issue list --team MIT --no-pager -s started -s unstarted

# All states including completed/canceled
LINEAR_ISSUE_SORT=priority linear issue list --team MIT --no-pager --all-states

# Filter by assignee (username, NOT 'self' for list — that only works for create)
LINEAR_ISSUE_SORT=priority linear issue list --team MIT --no-pager --assignee mihai

# All assignees / unassigned only
LINEAR_ISSUE_SORT=priority linear issue list --team MIT --no-pager -A
LINEAR_ISSUE_SORT=priority linear issue list --team MIT --no-pager -U

# Filter by project, cycle, milestone
LINEAR_ISSUE_SORT=priority linear issue list --team MIT --no-pager --project "Project Name"
LINEAR_ISSUE_SORT=priority linear issue list --team MIT --no-pager --cycle active
LINEAR_ISSUE_SORT=priority linear issue list --team MIT --no-pager --project "Project" --milestone "Milestone Name"

# Limit results (default 50, 0 = unlimited)
LINEAR_ISSUE_SORT=priority linear issue list --team MIT --no-pager --limit 10

# View issue details
linear issue view MIT-123 --no-pager

# Get issue ID from current git branch
linear issue id

# Get issue title
linear issue title MIT-123

# Get title + Linear-issue trailer (for commit messages)
linear issue describe MIT-123

# Get issue URL
linear issue url MIT-123

# Show all commits referencing an issue (jj only)
linear issue commits MIT-123
```

### Create Issues

```bash
linear issue create \
  --team MIT \
  -t "Issue title" \
  -d "Description (markdown supported)" \
  -a self \
  --priority 2 \
  --estimate 3 \
  -l "Bug" \
  -s backlog \
  --project "Project Name" \
  --no-interactive

# Create and immediately start working
linear issue create --team MIT -t "Title" --start --no-interactive
```

**Flags:** `-t` title, `-d` description, `-a` assignee (`self` or username), `--priority` 1-4 (1=urgent), `--estimate` points, `-l` label (repeatable), `-s` state, `--project` name (must already exist), `-p` parent issue (team-number code, e.g. `MIT-123`), `--due-date YYYY-MM-DD`, `--start`, `--no-interactive`.

### Update Issues

```bash
# Update state
linear issue update MIT-123 -s completed
linear issue update MIT-123 -s started

# Update other fields
linear issue update MIT-123 -t "New title" -d "New description" -a self --priority 1
linear issue update MIT-123 --project "Project Name" -l "Enhancement"
```

### Comments

```bash
linear issue comment MIT-123 -m "Comment body in markdown"
```

### Attach files

```bash
linear issue attach MIT-123 /path/to/file.png
```

### Issue relations (dependencies, blocking)

```bash
linear issue relation --help    # see available relation types
```

### Start Working on an Issue

```bash
# Creates a git branch and sets issue to "In Progress"
linear issue start MIT-123

# Start from a specific ref
linear issue start MIT-123 -f main
```

### Create PR Linked to Issue

```bash
# Creates a GitHub PR with issue details pre-filled
linear issue pr MIT-123

# With options
linear issue pr MIT-123 --draft --base main -t "Custom PR title" --web
```

### Delete Issue

```bash
linear issue delete MIT-123
```

## Projects

### Create

```bash
linear project create \
  -t MIT \
  -n "Project name" \
  -d "Description (255 char max)" \
  -l @me \
  -s started \
  --start-date 2026-04-10 \
  --target-date 2026-06-10 \
  --json
```

**Flags:** `-n` name (required), `-t` team (required, repeatable for multi-team), `-d` description (≤255 chars), `-l` lead (`@me`, username, or email), `-s` status (planned, started, paused, completed, canceled, backlog), `--start-date YYYY-MM-DD`, `--target-date YYYY-MM-DD`, `--initiative` (ID, slug, or name), `-j` JSON output.

### List / View / Update / Delete

```bash
# List
linear project list --team MIT
linear project list --team MIT --status "In Progress"

# View
linear project view PROJECT-ID-OR-SLUG

# Update
linear project update PROJECT-ID -n "New name" -s completed --target-date 2026-07-01

# Delete (moves to trash)
linear project delete PROJECT-ID
```

### Project status updates

```bash
linear project-update --help    # post status updates to a project's timeline
```

## Milestones, Cycles, Initiatives, Labels, Documents

```bash
linear milestone --help
linear cycle --help
linear initiative --help
linear label --help
linear document --help
```

These exist in 1.11.1 — check `--help` for current syntax before using.

## Teams

```bash
linear team list
linear team id
linear team members MIT
linear team autolinks   # Configure GitHub autolinks for team prefix
```

## Raw GraphQL

For anything the CLI doesn't expose:

```bash
linear schema | less    # browse the GraphQL schema
linear api '{ viewer { id name } }'    # raw query
```

## Workflows

### Start Work on an Issue

```bash
linear issue start MIT-123        # creates branch, sets state to started
# ... do work, commit ...
linear issue pr MIT-123 --draft   # create PR linked to issue
linear issue update MIT-123 -s completed  # close when merged
```

### Triage New Issues

```bash
LINEAR_ISSUE_SORT=priority linear issue list --team MIT --no-pager -s triage
# Review each, then move to backlog or unstarted:
linear issue update MIT-42 -s backlog --priority 3
```

### Create a project + populate with issues

```bash
# 1. Create the project
linear project create -t MIT -n "Project name" -d "Short description" -l @me -s started --json

# 2. Create issues attached to it (project must exist first)
linear issue create --team MIT --project "Project name" --no-interactive \
  -a self -t "First task" -d "Description"
```

### Cross-reference Issues with Commits

```bash
LINEAR_ISSUE_SORT=priority linear issue list --team MIT --no-pager -s started -s unstarted
git log --oneline -30 --all
```
