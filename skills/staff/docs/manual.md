# `/staff` — user manual

> Per-project agent staffing for Claude Code. This repo is the **HR repo** — the canonical source of agent definitions. Each project pulls its own staffed roster of HR agents into `.claude/agents/` instead of dumping all 56 agents globally and bloating every Claude Code session.

This manual is the practical companion to [`schemas.md`](schemas.md) (the file-format spec). If you want to know what fields exist, read schemas. If you want to know how to use the thing, read this.

---

## Mental model

```
HR repo                                Project (e.g. lab-control)
─────────────                          ─────────────────────────────
agent.manifest.yaml  ──┐               .claude/
  agents/              │                 agents/             ← what Claude Code loads
    go-engineer        │                   go-engineer.md    (generated; HR base + overlay)
    swift-backend      │                   security-auditor.md
    security-auditor   │                 staff/              ← user-owned state
    ...                │                   config.yaml       (HR repo path, etc.)
                       │                   lock.yaml         (pinned hashes)
                       │                   overlays/         (project-specific context)
                       │                     go-engineer.md  (~/lab-control idioms)
                       └── /staff suggest → /staff apply ────┘
```

Three operations move data:

- **`/staff suggest`** reads HR + your project, proposes a roster.
- **`/staff apply`** copies HR agents into the project, merges any overlays, writes the lockfile.
- **`/staff status`** compares the project against HR HEAD, reports drift or invalid state.

Two minor operations:

- **`/staff add <ids…>`** — staff additional agents.
- **`/staff remove <ids…>`** — drop agents from the staffed set.

---

## Setup

### One-time per machine

```bash
# Clone HR
git clone git@github.com:mihai-chiorean/inc.git ~/workspace/inc
cd ~/workspace/inc

# Install skills, org-scope agents, and the staff CLI on PATH.
# (Use --skills-only if you want zero user-scope agents.)
./install.sh --link

# Tell `staff` where HR lives
echo 'export STAFF_HR_REPO=$HOME/workspace/inc' >> ~/.zshrc
source ~/.zshrc
```

The agent.manifest.yaml that ships in the repo already has per-agent `description_summary` populated. If you ever add a new agent or edit an existing one's description, regenerate the summary so `/staff suggest`'s LLM matcher has a clean signal to route on:

```bash
python3 scripts/generate-manifest.py --llm-summaries
```

`/staff suggest` will warn on stderr if it sees a degraded manifest (≥30% or ≥10 agents with empty `description_summary`) and tell you to run this. Loud but non-fatal — recall is degraded until you fix it.

The script symlinks every skill into `~/.claude/skills/` and every skill's `bin/` entries into `~/.local/bin/`. Verify:

```bash
staff help
which staff
```

### One-time per project

```bash
cd ~/workspace/your-project

# 1. See what staff thinks the project needs
staff suggest

# 2. Install the proposed roster
staff suggest --json | staff apply --from-suggest -

# 3. (optional) Write a project-specific overlay for one agent
mkdir -p .claude/staff/overlays
$EDITOR .claude/staff/overlays/<agent-id>.md   # see overlay format below
staff apply --agents <agent-id>                # re-apply to merge overlay
```

That's it. Open Claude Code in the project; the staffed agents load from `.claude/agents/`.

---

## Daily workflow (user flow)

```
                ┌────────────────────────┐
                │  cd <project>          │
                └────────┬───────────────┘
                         │
                         ▼
                ┌────────────────────────┐
                │  staff status          │
                │  (read-only check)     │
                └────────┬───────────────┘
                         │
              ┌──────────┼───────────────┬───────────────────┐
        exit 0│      exit 1│        exit 2│              orphan-file
              ▼           ▼               ▼                    ▼
      "OK, get to    HR-DRIFT or         ERROR (corrupt   .claude/agents/<id>.md
       work."        OVERLAY-EDITED      lockfile,        exists but lockfile
                     or OVERLAY-STALE    alias collision, doesn't claim it
                                          missing field)
                          │                      │                  │
                          ▼                      ▼                  ▼
                   git -C $STAFF_HR_REPO    fix manually:    staff remove <id>
                   pull && cd back          repair lockfile  (or staff add it
                                            or rerun apply   officially)
                          │
                          ▼
                   staff apply \
                     --agents <ids>     ← pull HR updates for the drifting agents
                     --force              (or use /staff sync for per-agent diff + accept)
                          │
                          ▼
                   staff status          ← back to clean
                          │
                          ▼
                       resume work
```

Practical tips:

- **Status is your dashboard.** Run it whenever you cd into a project. Exit codes are designed for hooks: `0` clean, `1` drift, `2` invalid state.
- **Overlays don't auto-flow.** Editing `.claude/staff/overlays/<id>.md` doesn't update `.claude/agents/<id>.md` — you have to re-apply. Status will flag this as `OVERLAY-EDITED`.
- **HR pulls are user-initiated.** `git pull` on the HR repo doesn't touch your projects. `staff status` shows the drift; `staff apply` (or eventually `staff sync`) brings the project up to date.

---

## Overlays — what they're for

The HR `swift-backend.md` is generic. The version that loads in your Wendy cloud-services project should also know:

- mTLS via ALB header forwarding (X-Client-Cert)
- Hummingbird 2 + postgres-nio with the pool config in Sources/CloudServices/Database/PoolConfig.swift
- Never use Foundation in the auth path (per ADR-014)

That's project-specific knowledge that doesn't belong in HR. It goes in an overlay:

```markdown
---
agent_id: swift-backend
last_reviewed: 2026-05-08
notes: Wendy cloud-services
---

## Project Context

mTLS via ALB header forwarding (X-Client-Cert). The ALB terminates TLS and
forwards the cert in the header; backend re-validates the chain in
Sources/CloudServices/Auth/HeaderCertExtractor.swift. Never trust the header
without re-validation; ingress restriction is the only thing keeping this safe
(ADR-014).

Database access: postgres-nio with the pool config in
Sources/CloudServices/Database/PoolConfig.swift. Prepared statements for hot
paths.

Never use Foundation in the auth path (ADR-014).
```

`staff apply --agents swift-backend` merges this into `.claude/agents/swift-backend.md` between BEGIN/END STAFF OVERLAY marker comments. The HR base flows through cleanly on every re-apply; the overlay is preserved.

`last_reviewed` is required. `staff status` flags overlays older than `stale_overlay_days` (default 90) as `OVERLAY-STALE`.

---

## How matching works (data flow)

```
                              ┌──────────────────────────────────┐
                              │ HR: agent.manifest.yaml          │
                              │  ├ id, file, hashes              │
                              │  ├ description (full)            │
                              │  ├ description_summary (LLM)     │
                              │  ├ tags                          │
                              │  └ project_hints                 │
                              │     ├ files: [go.mod, *.proto]   │
                              │     └ regex: [\bcobra\b, …]      │
                              └──────────────┬───────────────────┘
                                             │
        ┌──────────────────┐                 │
        │ Project doc files│                 │
        │  CLAUDE.md       │                 │
        │  README.md       │                 │
        │  AGENTS.md       │                 │
        │ ───────────────  │                 │
        │ Dep manifests:   │                 │
        │  package.json    │                 │
        │  requirements.txt│                 │
        │  pyproject.toml  │                 │
        │  go.mod, go.sum  │                 │
        │  Cargo.toml/lock │                 │
        │  Gemfile, pom.xml│                 │
        │  …               │                 │
        └────────┬─────────┘                 │
                 │                           │
                 │  ┌──────────────────────┐ │
                 └─▶│ Deterministic match  │◀┘
                    │  (file presence +    │
                    │   regex on docs and  │
                    │   dep manifests)     │
                    └──────────┬───────────┘
                               │
                               │ "concrete signals"
                               ▼
                    ┌──────────────────────┐
                    │ Build LLM prompt     │
                    │  · doc excerpts      │      ┌────────────────────────┐
                    │  · concrete signals  │      │ STAFF_LLM env var      │
                    │  · roster summaries  │      │  codex   (default)     │
                    └──────────┬───────────┘      │  claude                │
                               │                  │  local  (HTTP)         │
                               ▼                  └────────┬───────────────┘
                    ┌──────────────────────┐               │
                    │ LLMProvider.call()   │◀──────────────┘
                    │  with json_schema    │
                    └──────────┬───────────┘
                               │
                               │ {suggested: [{id, reason}, …]}
                               ▼
                    ┌──────────────────────┐
                    │ Merge LLM proposals  │
                    │ with deterministic   │
                    │ signals; emit JSON   │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ staff apply          │
                    │  --from-suggest -    │
                    └──────────────────────┘
```

The LLM is the primary matcher; the deterministic regex/file hints are passed in as **input grounding** so the model has concrete observations to anchor its reasoning. You can disable the LLM with `--no-llm` (deterministic-only), useful for offline/CI runs.

`STAFF_LLM=codex` is the default. `STAFF_LLM=claude` swaps the CLI. `STAFF_LLM=local STAFF_LLM_URL=http://beelink:11434/v1 STAFF_LLM_MODEL=qwen2.5-coder:14b` uses a local LLM via the OpenAI-compatible HTTP API — works with ollama, vLLM, llama.cpp server.

---

## How apply works (data flow)

```
                  ┌────────────────────────────┐
                  │ staff suggest --json       │
                  │  → schema_version          │
                  │    hr_commit               │
                  │    manifest_hash           │
                  │    suggested[].id          │
                  └─────────────┬──────────────┘
                                │
                                ▼
                  ┌────────────────────────────┐
                  │ staff apply --from-suggest │
                  └─────────────┬──────────────┘
                                │
                                ▼
                  ┌────────────────────────────┐    drift?      exit 3
                  │ Validate vs HR             │──────────────▶ "re-run suggest"
                  │  · hr_commit == HEAD?      │                (--force overrides)
                  │  · manifest_hash matches?  │
                  │  · HR clean?               │    dirty?      exit 4
                  └─────────────┬──────────────┘──────────────▶ (--allow-dirty-hr)
                                │
                                ▼
                  ┌────────────────────────────┐
                  │ Phase 1: COMPUTE all       │
                  │  for each agent id:        │
                  │    resolve canonical       │
                  │    read HR base file       │
                  │    read overlay if exists  │    any failure?  exit 5
                  │    build merged content    │──────────────▶ "no files written"
                  │    compute lock entry      │
                  └─────────────┬──────────────┘
                                │
                                │ (atomic boundary — all-or-nothing)
                                │
                                ▼
                  ┌────────────────────────────┐
                  │ Phase 2: WRITE all         │
                  │  for each (path, content): │
                  │    atomic_write()          │    write fails?
                  │  write lockfile last       │──────────────▶ rollback new files,
                  └─────────────┬──────────────┘                exit 5
                                │
                                ▼
                       .claude/agents/<id>.md  (one per agent)
                       .claude/staff/lock.yaml (single source of truth)
```

Two-phase apply means: if any agent fails to compute, **no files are written**. If a file write fails partway through phase 2, **rollback runs** — newly-created files are removed; the lockfile is not advanced. Worst case is detectable as `ORPHAN-FILE` in `staff status`, never `MISSING`.

---

## How sync fits

```
HR moves forward                                     project still pinned
git -C $STAFF_HR_REPO pull
                  │
                  ▼
          staff status     ← shows HR-DRIFT for affected agents
                  │
                  ▼
          staff sync       ← for each drifting agent:
                                show diff (HR HEAD body vs pinned body)
                                prompt: take HR / skip
                                regenerate merged file from HR + existing overlay
                                bump lockfile pin
                                          │
                                          ▼
                                  back to clean
```

Until `staff sync` ships, the equivalent is `staff apply --agents <id> --force` per agent. Less ergonomic but functional.

---

## Exit codes (for hooks)

| Tool | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---|---|---|---|---|---|---|---|
| `suggest` | OK | — | bad input / missing manifest | — | — | — | — | — |
| `apply` | OK | — | bad args | drift vs suggest | dirty HR | one or more agents failed | — | — |
| `status` | clean | drift detected | invalid state | — | — | — | — | — |
| `add` | OK | — | unknown id / bad input | — | dirty HR | one or more failed | already-staffed | — |
| `remove` | OK | — | no lockfile / bad input | — | — | — | — | not-currently-staffed |
| `promote` | OK / already-org | — | bad input / agent not in manifest | — | — | — | — | — |
| `rif` | OK / no-op | — | bad input / agent not in manifest | — | — | — | — | — |

`rif --global` additionally exits `8` when project lockfiles still reference the agent (override with `--force` after rif-ing those projects).

The split between `1` (drift, syncable) and `2` (invalid, needs human) on `status` matters most for automation: SessionStart hooks can react to `1` by suggesting sync; `2` should always page the user.

---

## HR repo discovery (precedence)

Each subcommand resolves the HR repo path differently because their needs differ:

```
suggest:   --hr-repo  >  config.yaml  >  STAFF_HR_REPO
apply:     --hr-repo  >  config.yaml  >  STAFF_HR_REPO
add:       --hr-repo  >  config.yaml  >  lockfile.hr_repo  >  STAFF_HR_REPO
status:    --hr-repo  >  config.yaml  >  lockfile.hr_repo  >  STAFF_HR_REPO
remove:    (doesn't need HR; uses lockfile only)
```

`add` and `status` fall back to the lockfile because by the time you're running them, a previous `apply` has already recorded which HR was used.

If you pass `--hr-repo` explicitly, **a malformed config is silently bypassed** — you told staff to use the override, so it does. If config is the source of truth and is broken, you get exit 2 with a clear message.

---

## Common scenarios

### "I just cloned a project, what do I run?"

```bash
cd <project>
staff suggest                                # see proposed roster
staff suggest --json | staff apply --from-suggest -
```

If you've never run staff before on this machine, set `STAFF_HR_REPO` first.

### "HR has updated. Bring my project up to date."

```bash
cd ~/workspace/inc && git pull   # update HR
cd ~/workspace/<project>
staff status                                # see HR-DRIFT flags
staff apply --agents <id1> <id2> --force    # re-pin specific agents
# (or use staff sync for per-agent diff + accept)
```

### "I want to write a project-specific overlay for go-engineer"

```bash
cd <project>
mkdir -p .claude/staff/overlays
$EDITOR .claude/staff/overlays/go-engineer.md
# (frontmatter + body — see Overlays section above)
staff apply --agents go-engineer            # merge overlay into .claude/agents/go-engineer.md
staff status                                # confirm clean
```

### "I'm offline / on a flight. Can I still suggest?"

```bash
staff suggest --no-llm                      # deterministic regex/file hints only
```

You'll get the deterministic-only proposal. Expect lower recall (no semantic match) but it works.

### "Tell me what's installed without going to GitHub"

```bash
cd <project>
staff status                    # human-readable
staff status --json             # machine-parseable
```

### "I want to use a local LLM"

```bash
export STAFF_LLM=local
export STAFF_LLM_URL=http://beelink:11434/v1   # ollama on the lab box
export STAFF_LLM_MODEL=qwen2.5-coder:14b
staff suggest                                # uses local LLM
```

`STAFF_LLM_API_KEY` is optional (some local servers require it).

### "Move an agent between org and project scope"

`scope: org` agents get installed at user scope by `install.sh` and load in every Claude Code session. `scope: project` agents stay in the HR repo and are pulled in per-project via `/staff apply`. `/staff promote` and `/staff rif` move an agent across that boundary without manual frontmatter editing.

```bash
# Promote: flip scope: org in the agent's frontmatter, regenerate
# agent.manifest.yaml, re-run install.sh --link so the agent appears
# at ~/.claude/agents/<id>.md. Idempotent.
staff promote tech-lead

# rif --project (default in a project with a lockfile): drop the agent
# from this project only. Idempotent — exit 0 if not staffed.
cd <project>
staff rif go-engineer

# rif --global: demote scope: project, remove the user-scope symlink
# at ~/.claude/agents/<id>.md if and only if it's a symlink pointing
# into the HR repo. Refuses without --force if the agent is still
# referenced by any project lockfile under ~/.inc/projects/*/lock.yaml
# OR the current --project-root's own lockfile.
staff rif blog-writer --global
staff rif blog-writer --global --force      # override the safety gate

# Both at once
staff rif blog-writer --everywhere
```

Safety summary:

- `promote` never asks for confirmation — it's a strict superset (the agent is loaded everywhere it was before, plus globally).
- `rif --global` refuses if the agent is still referenced by any project lockfile. The `--force` override exists for the case where you've already run `/staff rif --project` in each consumer.
- `rif --global` will not delete a real file at `~/.claude/agents/<id>.md` — only its own symlinks. A user-edited copy is preserved with a warning so you can decide what to do with it.

For tests, override the project-lockfile scan root with `STAFF_PROJECTS_DIR` and the user-scope agents dir with `STAFF_USER_AGENTS_DIR`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `HR repo not specified` | Nothing set in `--hr-repo`, config, lockfile, or env | Set `STAFF_HR_REPO` once in your shell init |
| `error: LLM call failed: codex CLI not found on PATH` | `codex` binary missing | `npm install -g @openai/codex` (or `--no-llm`) |
| `error: HR repo has uncommitted changes` | HR has dirty working tree | `cd $STAFF_HR_REPO && git stash` (or `--allow-dirty-hr`) |
| `error: HR repo has moved since /staff suggest was run` | suggest's `hr_commit` ≠ current HR HEAD | re-run suggest, or `--force` |
| `agent.manifest.yaml schema_version=99 not supported` | Lockfile or manifest from a future version | Don't downgrade the staff CLI mid-flight |
| `OVERLAY-EDITED` shows after editing an overlay | overlay body changed without re-apply | `staff apply --agents <id>` |
| `OVERLAY-STALE` shows | `last_reviewed` > 90 days old | review the overlay, bump the date, re-apply |
| `MANUAL-EDIT` on `.claude/agents/<id>.md` | someone hand-edited the generated file | edit the overlay instead, then re-apply |
| `ORPHAN-FILE` | `.md` in `.claude/agents/` not in lockfile | `staff remove <id>` (drops it) or `staff add <id>` (claims it) |

---

## What this isn't

- **Not a package manager.** No semver, no version pinning beyond HR commits.
- **Not a three-way merge.** `staff sync` regenerates from HR HEAD; manual edits to merged files are detected as drift and surfaced before being overwritten.
- **Not multi-source HR.** One HR repo per project, period.
- **Not auto-renaming.** If an agent's stable ID changes upstream, an operator must hand-add the old ID to `aliases:` in the manifest before regen.

---

## Reference

- `schemas.md` — exact YAML/markdown shapes for manifest, lockfile, overlay, merged file
- `SKILL.md` — usage in Claude Code via `/staff <subcommand>`
- `examples/` — sample lockfile, overlay, project config
- Source: [github.com/mihai-chiorean/inc](https://github.com/mihai-chiorean/inc)
- Linear: [Per-project agent staffing skill project](https://linear.app/mitzoku/project/per-project-agent-staffing-skill-b7691b903726)
