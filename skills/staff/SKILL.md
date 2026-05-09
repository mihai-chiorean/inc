---
name: staff
description: 'Per-project agent staffing for Claude Code. Use when: (1) a project needs a curated subset of agents from the HR repo (claude-agents) instead of loading all user-scope agents, (2) "staff this project" / "what agents should this project use" is asked, (3) re-syncing project-level .claude/agents/ after the HR repo has been updated, (4) adding or removing an agent from a project, (5) inspecting which agents are staffed and whether they''re drifting from HR HEAD. Operates on .claude/staff/ for state and .claude/agents/ for generated agent files Claude Code loads.'
---

# /staff — per-project agent staffing

Selects which agents from the canonical HR repo (`claude-agents`) are staffed in the current project. Replaces the "load every agent into every session" pattern with a curated per-project roster via Claude Code's native `.claude/agents/` scope.

## Operations

| Command | Status | Description |
|---|---|---|
| `/staff suggest` | **MIT-281 — implemented** | Propose a roster based on project hints. Read-only |
| `/staff apply` | **MIT-282 — implemented** | Copy chosen agents from HR into `.claude/agents/`, write lockfile |
| `/staff status` | **MIT-283 — implemented** | Show staffed/diff/overlay state vs HR HEAD |
| `/staff add <id>` | **MIT-284 — implemented** | Add an agent to the staffed set |
| `/staff remove <id>` | **MIT-284 — implemented** | Drop an agent |
| `/staff audit` | **MIT-287 — implemented** | Scan multiple projects, identify retirement candidates in `~/.claude/agents/` |
| `/staff sync` | MIT-290 (pending, v2) | Regenerate from HR HEAD; preserve overlays |

## /staff suggest

Reads the HR manifest, scans the project for hint matches (presence of specific files or regex patterns in `CLAUDE.md` / `README` / `AGENTS.md`), and prints a proposed roster. Read-only — never mutates project state.

**Recall over precision:** an agent matches if any of its declared hints fire. The user prunes the proposal with `/staff remove` before `/staff apply`.

### Invocation

```bash
# Default: scan cwd, infer HR repo from STAFF_HR_REPO env or .claude/staff/config.yaml
staff suggest

# Explicit project + HR repo
staff suggest \
    --project-root /home/mihai/workspace/wendy-cloud \
    --hr-repo /home/mihai/workspace/claude-agents

# JSON output (for piping to /staff apply later)
staff suggest --json
```

### HR repo discovery (priority order)

1. `--hr-repo PATH`
2. `.claude/staff/config.yaml` in project root, key `hr_repo:`
3. `STAFF_HR_REPO` environment variable

If none are set, the script exits with a clear error.

### Sample output (text)

```
project: /home/mihai/workspace/wendy-cloud
hr_repo: /home/mihai/workspace/claude-agents
manifest: 56 agents, 5 match

[engineering]
  go-engineer
    · file: go.mod → go.mod
  grpc-contracts
    · file: **/*.proto → api/svc.proto
  security-auditor
    · regex: '(?i)\bm[\s-]?tls\b' matched in CLAUDE.md ('mTLS')
  swift-backend
    · file: Package.swift → Package.swift
    · regex: '(?i)\bhummingbird\b' matched in CLAUDE.md ('Hummingbird')

Next:
  /staff apply        # install all 5 suggested agents
  /staff add <id>     # add an agent not in the suggestion
  /staff remove <id>  # drop one before apply
```

### When invoked from Claude Code

When the user types `/staff suggest`:

1. Run the script (above) and capture stdout.
2. Present the proposed roster to the user, formatted readably.
3. If the user confirms, chain into `/staff apply` (when MIT-282 lands) — for now, tell them the proposal is informational and `/staff apply` is not yet implemented.
4. If the user wants changes, accept "remove X" or "add Y" instructions and re-display.

## /staff apply

Installs agents from HR into the project's `.claude/agents/` and writes the lockfile. Generates merged files (HR base + optional overlay). Refuses to pin a dirty HR repo.

### Invocation

```bash
# From a previous suggest run (recommended — drift checks)
staff suggest --json > /tmp/staff.json
staff apply --from-suggest /tmp/staff.json

# Pipe directly
staff suggest --json \
  | staff apply --from-suggest -

# Explicit list (skips drift checks; intended for /staff add/remove)
staff apply --agents go-engineer swift-backend

# Dry run
staff apply --agents go-engineer --dry-run
```

### Drift refusal

When `--from-suggest` is used, apply compares the input's `hr_commit` and `manifest_hash` to the current HR repo. If either differs, apply refuses with exit code 3 and tells you to re-run `/staff suggest` (or pass `--force`). This prevents the case where you ran suggest, the HR repo got new commits, and apply silently pins agents to content you didn't see in the proposal.

### Dirty-HR refusal

If the HR repo has uncommitted changes (`git status --porcelain` non-empty), apply refuses with exit code 4. Pass `--allow-dirty-hr` to override (the pin still records HEAD; uncommitted content is what gets copied).

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 2 | Bad args, missing manifest, malformed config, unknown agent ID, etc. |
| 3 | HR drift (commit or manifest hash) — bypass with `--force` |
| 4 | Dirty HR — bypass with `--allow-dirty-hr` |
| 5 | One or more agents failed to apply (lockfile NOT written) |

### Idempotency

Re-running apply with the same input produces the same `.claude/agents/<id>.md` files. The lockfile's `staffed` map is unchanged; only `generated_at` (timestamp) updates. Useful for CI checks: a clean re-apply implies no drift.

### What apply does NOT do

- **Doesn't preserve hand-edits to `.claude/agents/<id>.md`** — those files are generated. Use overlays for project-specific context.
- **Doesn't touch overlay sources** under `.claude/staff/overlays/<id>.md`.
- **Doesn't remove agents from previous lockfile entries** that aren't in the current input. Use `/staff remove` for that.

## /staff status

Read-only inspection of staffed agents vs HR HEAD. Reports per-agent flags:

| Flag | Meaning |
|---|---|
| `OK` | Pin matches HR, generated file untouched, overlay (if any) fresh |
| `HR-DRIFT` | HR HEAD has different `body_hash` or `description_hash` than the pin |
| `MANUAL-EDIT` | `.claude/agents/<id>.md` was hand-edited (sha differs from `generated_hash_at_apply`) |
| `OVERLAY-EDITED` | Overlay source body differs from `overlay_hash_at_apply` |
| `OVERLAY-STALE` | Overlay `last_reviewed` is older than `stale_overlay_days` (default 90) |
| `MISSING` | Agent in lockfile but `.claude/agents/<id>.md` not on disk |
| `ORPHAN-FILE` | `.claude/agents/<id>.md` exists but isn't in the lockfile |
| `ALIAS-RENAMED` | Lockfile uses a stable id that's now an alias of a renamed agent |
| `ERROR` | Couldn't process this entry (see message) |

### Invocation

```bash
# Default: text output, exits 1 if any drift detected
staff status

# JSON output for hooks/tooling
staff status --json

# Override stale threshold
staff status --stale-overlay-days 30
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Everything clean — no drift, no orphans, no stale overlays |
| 1 | Drift detected (HR-DRIFT, MANUAL-EDIT, OVERLAY-EDITED, OVERLAY-STALE, MISSING, ALIAS-RENAMED, ORPHAN-FILE) |
| 2 | Invalid state or could not run — `ERROR` flag on any agent (malformed lockfile, missing required overlay frontmatter, alias collision, etc.) or missing lockfile/manifest |

Hooks should treat exit 1 as "syncable" (run `/staff sync` once MIT-290 lands) and exit 2 as "needs human repair." Don't conflate them.

### HR repo discovery

In priority order: `--hr-repo` flag → `.claude/staff/config.yaml` → lockfile's `hr_repo:` → `STAFF_HR_REPO`. Status falls back to the lockfile's recorded HR repo as a convenience — it's the only operation that can do so without staffing decisions.

## /staff add and /staff remove

Thin operations on the lockfile + `.claude/agents/`.

```bash
# Add one or more agents (idempotent for new IDs; rejects already-staffed)
staff add go-engineer swift-backend

# Remove (deletes the generated file; preserves overlays under .claude/staff/overlays/)
staff remove swift-backend

# Dry runs
staff add go-engineer --dry-run
staff remove go-engineer --dry-run
```

### add — exit codes

| Code | Meaning |
|---|---|
| 0 | Added |
| 2 | `agent-not-in-manifest` (unknown ID), no project, malformed config, etc. |
| 4 | Dirty HR (`--allow-dirty-hr` overrides) |
| 5 | One or more agents failed to compute (no files written) |
| 6 | `agent-already-staffed` — use `/staff sync` (when MIT-290 lands) to refresh |

### remove — exit codes

| Code | Meaning |
|---|---|
| 0 | Removed |
| 2 | No lockfile, malformed lockfile, etc. |
| 7 | `agent-not-currently-staffed` (typo guard) |

### Overlay handling on remove

`.claude/staff/overlays/<id>.md` is **never auto-deleted**. The overlay is project-owned content; if you genuinely don't want it anymore, delete it by hand. Remove warns when an overlay is being preserved so you don't forget.

## How matching works

For each agent in the manifest, the agent matches if at least one of:

- A **file** in `project_hints.files` exists at project root or matches as a glob (e.g., `**/*.proto`). Glob depth capped at 4 levels for performance.
- A **regex** in `project_hints.regex` matches anywhere in `CLAUDE.md`, `README.md`, `README.rst`, `README`, or `AGENTS.md` at project root.

Only the engineering and engineering-adjacent agents have hints curated in v1 (~14 agents). Marketing/design/writing/bonus agents don't match by file presence — they're added via `/staff add` based on user intent.

To add hints for an agent, edit its `project_hints:` block in `agent.manifest.yaml` directly. The generator script preserves hand-curated hints across re-runs.

## Manual

End-to-end setup, daily workflow, ASCII flow diagrams, troubleshooting: [`docs/manual.md`](docs/manual.md).

## Repo leakage policy

Whether `.claude/agents/` is committed or gitignored, what stays committed regardless, recommended `.gitignore` entries, migration in either direction: [`docs/leakage.md`](docs/leakage.md).

**TL;DR**: gitignore `.claude/agents/` (generated), commit `.claude/staff/` (lockfile + config + overlays). Override with `commit_generated_agents: true` in config when the project needs HR-independent reproducibility.

## Schemas

See [`docs/schemas.md`](docs/schemas.md) for the spec of:

- `agent.manifest.yaml` (HR repo root)
- `.claude/staff/lock.yaml` (project)
- overlay frontmatter (`.claude/staff/overlays/<id>.md`)
- merged file format (`.claude/agents/<id>.md`)

## Examples

See [`examples/`](examples/):

- `lock.example.yaml` — sample lockfile
- `overlay.example.md` — sample overlay
- `config.example.yaml` — sample project config

## Tests

```bash
python3 skills/staff/tests/test_suggest.py
```

Smoke tests for `/staff suggest`. Fixtures use temporary directories.

## Generating the manifest

```bash
python3 scripts/generate-manifest.py
```

Idempotent. Preserves hand-curated `tags`, `project_hints`, `conflicts`, and `aliases`. Re-run after adding, removing, or editing agent files in the HR repo. No-op runs leave the file byte-unchanged.
