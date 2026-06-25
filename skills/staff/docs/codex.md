# Codex CLI support (`staff codex`)

`inc` is the single source of truth for agents and skills. Claude Code consumes
the `.md` agents directly. **Codex CLI** (0.142+) consumes a generated
projection of the same set. `staff codex` is that generator — it never edits the
source `.md`; it emits Codex-format artifacts from them.

## What maps to what

| Claude Code | Codex CLI (0.142+) | Fidelity |
|---|---|---|
| sub-agent `.md` (YAML frontmatter + MD body) | subagent **TOML** in `~/.codex/agents/<name>.toml` (user) or `<proj>/.codex/agents/<name>.toml` (project) | near 1:1 — see field mapping |
| `SKILL.md` skill | `SKILL.md` skill in `$CODEX_HOME/skills/<name>/` | clean 1:1 (same open spec) |
| `CLAUDE.md` | `AGENTS.md` | clean 1:1 (write per project) |
| `~/.claude/agents` vs `.claude/agents` | `~/.codex/agents` vs `.codex/agents` | clean 1:1 (two-tier) |

### Agent field mapping (`.md` → subagent `.toml`)

| `.md` frontmatter / body | `.toml` key | note |
|---|---|---|
| `name` | `name` | also becomes the spawnable `agent_type` |
| `description` | `description` | **selection guidance, not an auto-route trigger** (see below) |
| markdown body | `developer_instructions` | the system prompt, as a TOML multiline string |
| `model` (`opus`/`sonnet`/`haiku`) | `model_reasoning_effort` (`high`/`medium`/`low`) | `model` itself is dropped — Codex inherits its own model (gpt-5.x); we translate the *intent* |
| `color`, `scope` | — | dropped; scope is expressed by *location* (user vs project dir) |

## The one behavioural difference (v1 scope)

On Codex, **subagents are explicit-spawn**. The `description` disambiguates
*which* agent to spawn once you've asked for delegation; it is **not** scanned to
auto-delegate the way Claude Code's Task tool routes by description. Verbatim
from Codex's `spawn_agent` tool: *"Do not spawn sub-agents unless the user
explicitly asks for sub-agents, delegation, or parallel agent work."*

So a converted roster gives you **isolated-context + parallel** delegation on
request (`spawn_agent` / `spawn_agents_on_csv`), but not Claude's automatic
description-based routing. The thing that *does* auto-trigger by description on
Codex is **Skills** — which is why skills port 1:1 and matter more there. v1
emits subagents only; companion routing-skills are a possible v2.

## Usage

```sh
# User/org scope: emit `scope: org` agents + mirror skills into ~/.codex
staff codex --user --skills

# Or fold it into install (opt-in):
./install.sh --link --codex

# Project scope: emit a staffed project's roster into <proj>/.codex/agents
staff codex --project /path/to/project
```

### Automatic regeneration

A staff-managed project can opt in by adding to `.claude/staff/config.yaml`:

```yaml
emit_codex: true
```

Then `staff apply` and `staff sync` regenerate `.codex/agents/*.toml` (with
per-project overlays stitched in, same as the `.claude/agents/*.md`) every time
they run. The hook is best-effort — it never fails apply/sync.

## Caveats

- **Restart Codex** to pick up newly written subagents/skills (same as Claude's
  disk-edit caveat).
- `model_reasoning_effort` is a heuristic translation of the model tier, not the
  same model. Tune per agent in the source `.md` if needed (it round-trips).
- Generated `.toml` / `.codex/agents/` are build artifacts — treat them like
  `.claude/agents/` (regenerate, don't hand-edit).
