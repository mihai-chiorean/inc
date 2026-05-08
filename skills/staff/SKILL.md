---
name: staff
description: 'Per-project agent staffing for Claude Code. Use when: (1) a project needs a curated subset of agents from the HR repo (claude-agents) instead of loading all user-scope agents, (2) "staff this project" / "what agents should this project use" is asked, (3) re-syncing project-level .claude/agents/ after the HR repo has been updated, (4) adding or removing an agent from a project, (5) inspecting which agents are staffed and whether they''re drifting from HR HEAD. Operates on .claude/staff/ for state and .claude/agents/ for generated agent files Claude Code loads.'
---

# /staff — per-project agent staffing

> **Status (MIT-280):** schemas + manifest + examples landed. Operations (`suggest`, `apply`, `add`, `remove`, `status`, `sync`) are tracked under MIT-281…MIT-290 and not yet implemented. This SKILL.md is a stub; once the operations exist it will be filled in with usage instructions.

## What this skill does

Selects which agents from the canonical HR repo (`claude-agents`) are staffed in the current project. Manages:

- `.claude/agents/<id>.md` — generated, what Claude Code loads
- `.claude/staff/lock.yaml` — pinned HR commits per agent
- `.claude/staff/config.yaml` — project-local config (HR repo path, stale-overlay threshold, commit policy)
- `.claude/staff/overlays/<id>.md` — project-specific context appended to agents

## Why

Claude Code loads every `.md` file in `~/.claude/agents/` into every session. A 58-agent user-scope roster bloats the routing prompt and causes mis-routes. Per-project staffing via Claude Code's native `.claude/agents/` scope replaces that with the agents the project actually needs.

## Schemas

See `docs/schemas.md` for the full spec of:

- `agent.manifest.yaml` (HR repo root)
- `.claude/staff/lock.yaml` (project)
- overlay frontmatter (`.claude/staff/overlays/<id>.md`)
- merged file format (`.claude/agents/<id>.md`)

## Examples

See `examples/`:

- `lock.example.yaml` — sample lockfile
- `overlay.example.md` — sample overlay
- `config.example.yaml` — sample project config

## Generating the manifest

```bash
python3 scripts/generate-manifest.py
```

Idempotent. Preserves hand-curated `tags`, `project_hints`, `conflicts`, and `aliases`. Run after adding, removing, or editing agent files in the HR repo.
