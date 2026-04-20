---
name: project-management
description: 'Project management workflows and practices. Use when developers mention: (1) planning work or sprints, (2) prioritizing tasks or issues, (3) tracking progress on a project, (4) standup or status updates, (5) breaking down work into issues, (6) roadmap or milestone planning, (7) workload or capacity, (8) what to work on next.'
---

# Project Management

## Tools

- **Linear CLI** (`linear`): Primary issue tracker. See the `linear` skill for full CLI reference.
- **GitHub CLI** (`gh`): PR and code review management.
- **Git**: Branch and commit history.

## Workflows

### Planning Work

When asked to plan or break down work:

1. Understand the goal — ask clarifying questions if the scope is ambiguous.
2. Break it into discrete, actionable issues — each should be completable in a day or less.
3. Create issues in Linear with appropriate metadata:
   ```bash
   linear issue create --team WDY -t "Issue title" -d "Description" \
     --priority 2 -s backlog --project "Project Name" --no-interactive
   ```
4. Set parent/child relationships for larger epics:
   ```bash
   linear issue create --team WDY -t "Subtask" -p WDY-100 --no-interactive
   ```

### Picking What to Work on Next

When asked "what should I work on next" or similar:

1. Check issues in priority order:
   ```bash
   LINEAR_ISSUE_SORT=priority linear issue list --team WDY --no-pager -s unstarted -s started -a self
   ```
2. If nothing assigned, check unassigned:
   ```bash
   LINEAR_ISSUE_SORT=priority linear issue list --team WDY --no-pager -s unstarted -U
   ```
3. Recommend the highest-priority unblocked issue.

### Status Update / Standup

When asked for a status update:

1. Show in-progress issues:
   ```bash
   LINEAR_ISSUE_SORT=priority linear issue list --team WDY --no-pager -s started -a self
   ```
2. Show recently completed:
   ```bash
   LINEAR_ISSUE_SORT=priority linear issue list --team WDY --no-pager -s completed -a self
   ```
3. Show open PRs:
   ```bash
   gh pr list --author @me
   ```
4. Summarize: what was done, what's in progress, what's blocked.

### Tracking Progress on a Project

1. List project issues by state:
   ```bash
   linear project list --team WDY
   linear project view PROJECT-ID
   ```
2. Cross-reference with issue states to gauge completion.

### Closing Completed Work

When wrapping up or tidying issues:

1. List started/unstarted issues:
   ```bash
   LINEAR_ISSUE_SORT=priority linear issue list --team WDY --no-pager -s started -s unstarted
   ```
2. Cross-reference with merged PRs:
   ```bash
   gh pr list --state merged --limit 20
   ```
3. Close issues whose work has been merged:
   ```bash
   linear issue update WDY-123 -s completed
   ```

### Triaging New Issues

1. Review triage queue:
   ```bash
   LINEAR_ISSUE_SORT=priority linear issue list --team WDY --no-pager -s triage -A
   ```
2. For each issue, decide: prioritize (move to backlog/unstarted with a priority) or reject (cancel).
   ```bash
   linear issue update WDY-42 -s backlog --priority 3
   linear issue update WDY-43 -s canceled
   ```

## Principles

- Keep issues small and focused — one concern per issue.
- Use priority levels consistently: 1=urgent, 2=high, 3=medium, 4=low.
- Link PRs to issues so closing a PR can close the issue.
- Don't let "started" issues pile up — if something is stalled, move it back to backlog or unstarted.
