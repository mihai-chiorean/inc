# Project bootstrap

The "I just got a new machine, here's how to set up `inc`" guide.

Two audiences:

1. **Future-me** reinstalling on a new device.
2. **Outside reader** evaluating the repo before forking, lifting, or just reading for ideas.

Sections A → B → C run in order. Section D is for the outside reader and is independent of the others.

Sibling guides:

- [`workflow.md`](workflow.md) — day-in-the-life walkthrough (MIT-364).
- [`../reference/skills.md`](../reference/skills.md) — one-page skill catalog (MIT-366).

---

## A — Machine setup

This sets up `inc` as the **HR repo** for your machine: the single source of truth for agents and skills that other projects pull from.

### A.0 Existing install? Clean up first

Skip if you're on a truly fresh machine (no prior `claude-agents` checkout, no other `~/.claude/skills/` setup). Otherwise read this section before running `install.sh`.

**What "prior install" means.** Most likely:

- You had `claude-agents` (the pre-rebrand name) cloned at `~/workspace/claude-agents`. That clone got renamed to `inc`, but `~/.claude/skills/` still has symlinks pointing at the old path (now broken).
- You ran `./install.sh` without `--link` at some point, so `~/.claude/agents/` contains COPIES of agent .md files instead of symlinks — those copies are stale.
- An older Claude Code skill bootstrap left files in `~/.claude/skills/` that don't belong to inc.

**The cleanup script handles the first two cases directly.** It's at `scripts/cleanup-prior-install.sh` in this repo (run from the clone — not symlinked anywhere, by design). Safe-by-default: read-only `inventory` mode by default, moves `~/.claude/agents/` to a timestamped backup rather than `rm`-ing it.

For the third case — unrelated Claude Code skills already installed by other tools — the script **does not actively clean them**. It leaves unrelated symlinks alone (with a stderr WARN if any are broken). If an unrelated skill happens to share a name with one inc would install, `install.sh --link` will report it as `SKIPPED` and refuse to clobber. You'd manually inspect and resolve those.

**Two ways to use it.**

**(1) Standalone — preview, then commit:**

```bash
cd ~/workspace/inc

# Read-only inspection. Shows what would be cleaned. No changes.
./scripts/cleanup-prior-install.sh inventory

# When ready, run the cleanup. Prompts for confirmation.
./scripts/cleanup-prior-install.sh clean

# Or fully non-interactive (CI / re-runs):
./scripts/cleanup-prior-install.sh clean --yes

# Or preview without committing:
./scripts/cleanup-prior-install.sh clean --yes --dry-run
```

The script exits `0` on success / nothing-to-clean, `1` if you decline the prompt, `2` for bad arguments or refuses (e.g. `~/workspace/claude-agents/` still exists — finish the rebrand mv first).

**(2) Let `install.sh` handle it for you.** Skip the standalone step — `install.sh` runs the same inventory at startup and prompts:

```bash
cd ~/workspace/inc
./install.sh --link

# … if leftovers detected, you'll see:
# Clean up these leftovers before installing? [y/N/show]
```

Answer:
- `y` / `yes` → runs the cleanup, then proceeds with install.
- `show` → re-prints the inventory, asks again.
- `n` / `no` / Enter (default) → proceeds anyway. `install.sh` will refuse to clobber any conflicting target and report `SKIPPED` items at the end with instructions.

For non-interactive scenarios (CI, headless re-install), pass `--auto-cleanup`. To skip the check entirely (you know the machine is clean), pass `--no-cleanup`.

**Safety guarantees.** The cleanup:

- Only removes symlinks under `~/.claude/skills/` or `~/.local/bin/` whose target matches `*workspace/claude-agents*` (old-name leftovers), OR symlinks that are broken AND point at the current inc workspace (install will recreate them).
- **Leaves unrelated broken symlinks alone** with a stderr WARN line listing them. If you have a custom skill symlinked into `~/.claude/skills/` whose target moved temporarily, the script will not touch it.
- Moves `~/.claude/agents/` to `~/.claude/agents.bak-pre-inc-<UTC-timestamp>/` rather than deleting. Restore from the backup later if anything is missing.
- Refuses to run if `~/workspace/claude-agents/` still exists — finish `mv ~/workspace/claude-agents ~/workspace/inc` first (the script reminds you).

**Portability.** Shebang is `#!/bin/bash`; works on macOS (`/bin/bash` is bash 3.2) and Linux. **Do NOT invoke as `zsh scripts/cleanup-prior-install.sh`** — zsh's `case`-pattern semantics differ from POSIX and the script will silently misclassify. Use `./scripts/cleanup-prior-install.sh` (shebang resolves to bash) or `bash scripts/cleanup-prior-install.sh`.

### A.1 Prerequisites

| Tool | Why | Install check |
|---|---|---|
| [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) | Where the skills and agents run | `claude --version` |
| [`codex` CLI](https://github.com/openai/codex) | `staff suggest` defaults to LLM-based matching with `STAFF_LLM=codex`. Also used for per-PR codex review × N rounds. Without it, fall back to `staff suggest --no-llm` (regex-only) | `codex --version` |
| [`gh`](https://cli.github.com/) | Used by `/sitrep` for PR queries; needed for `gh auth login` and PR creation | `gh --version` |
| [`linear` CLI](https://github.com/schpet/linear-cli) v1.x or v2.x | Used by `sitrep-linear` for the inbox; needed for issue creation in `/work-breakdown` | `linear --version` |
| `git`, `bash` (≥4), `python3` (≥3.9), `perl` | Used by `install.sh`, `staff`, and `sitrep-linear` | usually preinstalled |

The `sitrep-linear` wrapper transparently handles both linear CLI v1.x (which uses `issue list`) and v2.x (which uses `issue mine`). Either is fine.

### A.2 Clone and install

```bash
git clone https://github.com/mihai-chiorean/inc.git ~/workspace/inc
cd ~/workspace/inc
./install.sh --link
```

The flag:

- `--link` symlinks instead of copying, so `git pull` in this repo updates everything else in place.

**What gets installed by default:**

- **All skills** (25 dirs) → `~/.claude/skills/` (loaded in every session — these are procedural overlays, you want them everywhere).
- **Skill binaries** → `~/.local/bin/` (`staff`, `sitrep-linear`, `design-doc-scaffold`, `plan-eng-review-audit`).
- **A small set of org-scope agents** (currently 7: `hiring-manager`, `blog-writer`, `social-amplifier`, `product-manager`, `tpm`, `tech-lead`, `security-auditor`) → `~/.claude/agents/` at user scope. These are the agents that genuinely fire across every project. The other ~48 stay in this repo until you stage them per-project via `/staff`.

An agent is "org-scope" iff its frontmatter contains `scope: org`. Add or remove the tag to change the default set; `install.sh` reads each agent's `.md` directly.

**Alternative modes:**

- `./install.sh --link --include-all-agents` — installs all 55 agents at user scope. **Not recommended:** loads every agent in every session, defeating the per-project `/staff` curation. Use only if you genuinely want every specialist available globally.
- `./install.sh --link --skills-only` — installs zero agents (skills + bins only). For fully-`/staff`-curated setups.

Expected output (default mode):

```
Installing org-scope agents + all skills to /home/<you>/.claude/agents and /home/<you>/.claude/skills (mode: link)
Project-shaped agents stay in this repo; use /staff in projects to stage them per-repo.

Summary: 7 org agents + 25 skill dirs + 4 bins processed (37 linked, 0 copied, 0 already in place, 0 skipped)
Done.
```

(Skill / agent / bin counts drift as the repo grows. The interesting line is the trailing summary — non-zero `SKIPPED` means an existing non-symlink target is in the way; the installer refuses to clobber and exits 2. See A.0 for the cleanup procedure when that happens.)

### A.3 Make the skill binaries reachable

`install.sh` symlinks each skill's `bin/` executables into `~/.local/bin/`. If that directory is not on your `PATH`, the wrappers (`staff`, `sitrep-linear`, `design-doc-scaffold`, `plan-eng-review-audit`) won't resolve.

```bash
# Check
echo "$PATH" | tr ':' '\n' | grep -q "$HOME/.local/bin" \
  && echo "ok" \
  || echo "MISSING — add to your shell rc"

# Add to ~/.zshrc or ~/.bashrc if missing
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Confirm the wrappers resolve:

```bash
$ command -v staff sitrep-linear design-doc-scaffold
/home/<you>/.local/bin/staff
/home/<you>/.local/bin/sitrep-linear
/home/<you>/.local/bin/design-doc-scaffold
```

### A.4 Tell `staff` where HR lives

The `staff` skill discovers the HR repo (this clone of `inc`) in priority order:

1. `--hr-repo PATH` flag (per-invocation)
2. `.claude/staff/config.yaml` `hr_repo:` (per-project)
3. `STAFF_HR_REPO` env var (machine-wide)

Set the env var so you don't have to think about it again:

```bash
echo 'export STAFF_HR_REPO=$HOME/workspace/inc' >> ~/.zshrc
source ~/.zshrc
```

### A.5 Populate agent description summaries (first-run only)

`/staff suggest` uses an LLM to pick agents for a project. To keep that match accurate, it reads a 2–4 sentence `description_summary` per agent from `agent.manifest.yaml` rather than the full description. **A fresh clone has those summaries populated** (committed to the repo), but if you ever add a new agent or modify an existing one's description, regenerate:

```bash
cd ~/workspace/inc
python3 scripts/generate-manifest.py --llm-summaries
```

This uses the codex CLI (configurable via `STAFF_LLM`) to (re)compute the summary for any agent whose description has changed or which has no summary yet. ~7s per agent. Existing summaries are preserved unchanged.

`/staff suggest` will warn loudly on stderr if it sees a degraded manifest (≥30% or ≥10 agents with empty summaries) and tell you to run this. Loud but non-fatal — it'll proceed with degraded recall.

### A.6 Verify the symlink farm

```bash
ls -la ~/.claude/skills/ | head -10
ls -la ~/.local/bin/ | grep -E '(staff|sitrep-linear|design-doc-scaffold|plan-eng-review-audit)'
```

Expected: every entry in `~/.claude/skills/` is a symlink pointing into `~/workspace/inc/skills/`, and every wrapper in `~/.local/bin/` points into a skill's `bin/` directory. If any entry is a real file (not a symlink), the installer skipped it — investigate by hand and re-run.

### A.7 Authenticate `gh` and `linear`

```bash
gh auth login          # interactive: pick GitHub.com, HTTPS, browser auth
linear auth login      # interactive: opens browser to https://linear.app/oauth/...
```

Verify:

```bash
$ gh auth status
github.com
  ✓ Logged in to github.com account <you>
  ...

$ linear auth whoami
<you> @ <workspace>
```

If you're on a headless box where the browser auth flow won't work, `linear auth login --plaintext` stores credentials in `~/.config/linear/credentials.toml` instead of the system keyring. For CI / bot accounts, set `LINEAR_API_KEY=lin_api_...` from <https://linear.app/settings/account/security> — it takes precedence over the keyring.

### A.8 Restart Claude Code

Skills are loaded once per session. If Claude Code was already running, exit and relaunch so it picks up the new `~/.claude/skills/`.

---

## B — Per-project setup

This is what you do **inside each repo you want to use with `inc`**.

The flow is: pick a roster of agents → install them locally → write a `STATUS.md` so `/sitrep` has something to read → scope the Linear inbox down to this repo's work.

### B.1 Suggest a roster

```bash
cd ~/workspace/<your-project>
staff suggest
```

`staff suggest` is read-only. By default it uses an LLM (defaults to `STAFF_LLM=codex`, configurable to `claude` or a local provider) to match project hints — file presence, regex matches in `CLAUDE.md`/`README.md`/`AGENTS.md`, **regex matches in dependency manifests** (`package.json`, `requirements.txt`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Gemfile`, `pom.xml`, etc.), and surface signals — against the HR manifest. Pass `--no-llm` to force deterministic regex-only matching (faster, no codex dependency, less accurate on novel repos).

Sample output:

```
project: /home/<you>/workspace/wendy-cloud
hr_repo: /home/<you>/workspace/inc
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

Next:
  /staff apply        # install all 5 suggested agents
  /staff add <id>     # add an agent not in the suggestion
  /staff remove <id>  # drop one before apply
```

**Recall over precision.** The matcher fires on any hint; prune what you don't want before applying. Marketing, design, writing, and bonus agents have no file hints — add them by hand if you want them (e.g. `staff add joker`).

### B.2 Apply the roster

Pipe the JSON output through `staff apply` so drift checks fire (commit hash and manifest hash are pinned at suggest time and re-verified at apply time):

```bash
staff suggest --json | staff apply --from-suggest -
```

Or pass agents explicitly (skips drift checks; useful for incremental adds):

```bash
staff apply --agents go-engineer security-auditor
```

Expected effect:

- `.claude/agents/<id>.md` created for each agent (this is what Claude Code loads).
- `.claude/staff/lock.yaml` written with pinned content hashes per agent (records `hr_repo` URI so subsequent `staff sync` / `staff status` knows where the canonical source lives).

`staff apply` refuses if the HR repo has uncommitted changes (exit 4) or if the HR commit has moved since `staff suggest` ran (exit 3). Override with `--allow-dirty-hr` or `--force` respectively — both surface what they're bypassing.

Sanity-check:

```bash
$ staff status
all 5 agents OK against HR HEAD (abc1234)
```

### B.3 Bootstrap `STATUS.md`

`STATUS.md` is the **per-project session-state contract** that `/sitrep` reads and updates. It lives at the repo root. The full schema is at [`skills/sitrep/docs/status-schema.md`](../../skills/sitrep/docs/status-schema.md).

Easiest path: run `/sitrep` and let it offer to bootstrap. The skill detects a missing or malformed `STATUS.md` and walks you through creating one, seeding defaults from `git branch --show-current` and the branch's Linear issue prefix.

If you'd rather write it by hand:

```yaml
---
status_version: 1
current_objective: "<one sentence — the why behind active_branch>"
active_branch: null
active_pr: null
linear_issue: null
linear_team: MIT                      # Linear team key; sitrep-linear can derive from linear_issue otherwise
linear_project: null
linear_scope:                         # see B.4
  - "<exact Linear project name>"
blocked_on_user: []
next_command: "<one sentence imperative>"
last_verified_state: "1970-01-01T00:00:00Z"
links:
  initiative: null
  project: null
  handoff: null
---

# <project name> status

## Current objective
<paragraph or bullets — the why>

## What's next
1. <ordered next steps>

## Open items needing my attention
- <empty until /sitrep populates from Linear/GitHub>

## Decisions log (recent)
- YYYY-MM-DD — <decision>
```

The four `##` body sections are required. `/sitrep` populates **Open items needing my attention** automatically from Linear (assigned-to-you) and GitHub (PRs awaiting your review).

### B.4 Set `linear_scope`

Linear has no inherent "this issue belongs to this repo" link — one team, many repos. Without scoping, `sitrep-linear inbox` returns every issue assigned to you across every repo on the team. `linear_scope` is the filter:

```yaml
linear_scope:
  - "gstack borrow — Week 1: bootstrap loop"
  - "Per-project agent staffing skill"
  - "agent eval framework"
```

**Match rule.** Exact string match on the project name as Linear shows it. List the Linear projects that count as this repo's work. Order doesn't matter.

**Caveats** (from the [schema doc](../../skills/sitrep/docs/status-schema.md#scoping-linear_scope)):

- Issues without a Linear project are **not surfaced** by `sitrep-linear inbox` when `linear_scope` is set. Triage and orphan issues are silently dropped — you only see them if you go to Linear directly. Put new issues in a project (any project in `linear_scope`) for them to show up.
- Missing or empty field falls back to all-team behavior. Useful as an escape hatch but easy to forget — the wrapper prints a stderr warning if `linear_scope` is present but parses to zero items.
- If some project names are typos, you'll see a partial inbox plus a stderr warning listing the failed names. Run `sitrep-linear scope` against `linear project list` to compare.

The long-term direction is label-based scoping (a `repo:<slug>` label on every relevant issue). Not built yet — see the schema doc for the deferred design.

### B.5 First `/sitrep`

```
/sitrep
```

Confirms three things:

1. `STATUS.md` parses cleanly (no warnings about malformed frontmatter).
2. `sitrep-linear` resolves the team key from `linear_team` or `linear_issue`.
3. The Inbox section shows only this-repo issues (matches your `linear_scope`).

Sample output:

```
=== sitrep: <project> ===
Branch:    main  →  none
PR:        none
Objective: <your current_objective>

▎ NEXT
  → <your next_command>

▎ BLOCKED ON YOU — clear

▎ INBOX (2 issues, 0 PRs for review)
  • MIT-XXX [P2] <title>
  • MIT-YYY [P3] <title>

▎ YOUR OPEN PRS (0)

Last verified: <iso-timestamp>  (just now)
```

If Inbox shows issues from other repos, your `linear_scope` is wrong (typo, missing entry, or you genuinely haven't moved the orphan issues into projects). Run `sitrep-linear scope` to see what's parsed.

### B.6 (Optional) Scaffold a design doc for the first non-trivial work

If the next piece of work is M-or-larger (multi-file, has architectural choice, touches more than one repo), scaffold a design doc:

```
/design-doc
```

or directly:

```bash
design-doc-scaffold \
  --title "<one-line>" \
  --linear-issue MIT-XXX
```

This writes `decisions/NNNN-<slug>.md` with three mandatory diagram sections (user-flow / state-machine / data-flow), failure-modes table, implementation alternatives, and open questions. You then fill it in; `plan-eng-review` audits it before code lands.

**Don't fire `/design-doc` for S-sized work.** The skill itself surfaces this — it's a scaffolding tool, not a ceremony tax.

---

## C — Verification

A 90-second check that the per-project setup actually works end-to-end. Run from inside the project's repo root.

### C.1 `sitrep-linear scope` returns the configured projects

```bash
$ sitrep-linear scope
gstack borrow — Week 1: bootstrap loop
Per-project agent staffing skill
agent eval framework
```

Exit code 0 with one project per line. Exit 1 means `STATUS.md` is missing the field (unscoped — silent fallback). Exit 2 means the field is present but yielded zero items (likely malformed YAML).

### C.2 `sitrep-linear inbox` returns only this-repo issues

```bash
$ sitrep-linear inbox
◌ ID         Title                                        Project              Status
  MIT-XXX    <title>                                      <project>            Backlog
  MIT-YYY    <title>                                      <project>            Started
```

Cross-check: every row's `Project` column should be a name from your `linear_scope`. If it isn't, the scope is too broad or the project name doesn't match exactly.

### C.3 `design-doc-scaffold --help` shows usage

```bash
$ design-doc-scaffold --help
usage: design-doc-scaffold [-h] --title TITLE [--linear-issue LINEAR_ISSUE]
                           [--slug SLUG] [--path PATH] [--author AUTHOR]
                           [--force] [--template TEMPLATE]

Scaffold a design doc from the /design-doc template.
...
```

Confirms `~/.local/bin/` is on `PATH` and the skill's wrapper resolved. If you get `command not found`, re-run section A.3.

### C.4 `staff status` reports clean

```bash
$ staff status
all <N> agents OK against HR HEAD (<sha>)
```

Exit 0 means staffed agents match the HR pin and have no manual edits or stale overlays. Exit 1 means drift (run `staff sync`). Exit 2 means a malformed lockfile or alias collision — needs hand repair.

### C.5 `~/.inc/projects/<slug>/` is created on first use

The `plan-eng-review` skill (Week 3b — currently in build) and any future telemetry-emitting skill writes under `~/.inc/projects/<slug>/`. The directory is created on first write; it's not pre-provisioned by `install.sh`.

```bash
$ ls ~/.inc/projects/ 2>/dev/null || echo "(empty — not yet used)"
```

Both are normal states for a fresh install.

---

## D — For an outside reader

If you found this repo because you're evaluating Claude Code patterns, this section is for you. It's honest about what `inc` is and isn't.

### D.1 What `inc` is

A personal **operations layout** for one engineer running multiple repos through Claude Code. It bundles:

- **A roster of \~55 agents** organized by department (engineering, product, design, marketing, project-management, studio-operations, testing, bonus). Many came from [Contains Studio's agents repo](https://github.com/contains-studio/agents); the lab-specific ones (`go-engineer`, `swift-backend`, `gpu-engineer`, `embedded-linux`, `wendy-*`, `grpc-contracts`, `db-migration`, etc.) are bespoke to a robotics/CV lab the author runs.
- **A set of skills** that codify recurring procedures: session bootstrap (`/sitrep`), per-project agent staffing (`/staff`), work breakdown (`/work-breakdown`), design-doc scaffolding (`/design-doc`), engineering plan review (`/plan-eng-review`), and a handful of domain-specific guidance skills (Swift NIO, Hummingbird, Postgres, Valkey, etc.).
- **An installer (`install.sh`)** that wires both into `~/.claude/` via symlinks, plus skill binaries onto `~/.local/bin/`.
- **An opinion** about how the two should compose: agents are structural switches (separate context, separate persona — `/staff` curates a small subset per project to keep the router's view tight). Skills are procedural switches (same context, reshapes behavior — invoked on demand or auto-fired by `CLAUDE.md` rules).

### D.2 What `inc` is not

- **Not a framework.** It is one engineer's working setup checked into a public repo. The directory names, the team key `MIT`, the file paths (`~/workspace/inc`, `~/.inc/projects/`), and the Linear conventions are all hard-coded to one workflow. If you fork it, you'll be editing all of those.
- **Not a product.** No support, no roadmap commitments, no API stability. Issues are tracked in a private Linear workspace; the GitHub issues tab may or may not be used.
- **Not language-agnostic.** The engineering specialist roster leans Swift / Go / Python / embedded Linux because that's what the author ships. If you write Rust or JavaScript, the agent set will feel sparse — you'll want to add your own.
- **Not a battle-tested skill catalog.** Several skills are days-old, written under the [gstack-borrow](../../research/gstack-borrow-2026-05-11.md) initiative and verified against exactly one consumer. The fail-loud rule in [`CLAUDE.md`](../../CLAUDE.md) is there because silent skips have been observed.

### D.3 Hard prerequisites

| Required | Why |
|---|---|
| Claude Code CLI | Skills and agents are Claude Code primitives. None of this runs without it. |
| `gh` CLI, authed | `/sitrep` queries open PRs and review-requested PRs. `/work-breakdown` uses it for PR linkage. |
| `linear` CLI v1.x or v2.x, authed | The wrapper handles both. `/sitrep`, `/work-breakdown`, and most coordination skills assume Linear is the queue. |
| `bash` ≥ 4, `python3` ≥ 3.9, `perl` | `install.sh` is bash. `staff` is Python. `sitrep-linear` uses Perl for ANSI stripping. |

The Linear dependency is the most opinionated. If you don't use Linear, most of the planning/coordination skills (`/sitrep`, `/work-breakdown`, much of `/staff`) will need adaptation — the agent roster itself is independent and works fine without Linear.

### D.4 What to fork vs. what to read for ideas

**Worth forking as-is**, if your workflow looks similar:

- **`install.sh`.** Idempotent symlink installer with `--link / --dry-run / --skills-only / --include-all-agents`. Default mode installs skills + bins + org-scope agents. Generic and reusable.
- **`/staff` skill** (`skills/staff/`). The per-project agent staffing pattern — lockfile, drift detection, overlays, sync — is the load-bearing piece if you're trying to avoid the "load every agent into every session" failure mode.
- **`/sitrep` + `STATUS.md` schema** (`skills/sitrep/`). The session-bootstrap contract is the lift from gstack that's paid off the most. The schema is at `skills/sitrep/docs/status-schema.md`; the wrapper script `bin/sitrep-linear` hides the Linear CLI v1/v2 mess.
- **`/design-doc` template** (`skills/design-doc/templates/design-doc.md.tmpl`). Three-diagram + failure-modes + alternatives. Forkable on its own without the rest of `inc`.

**Worth reading, not forking**:

- The agent files themselves (e.g. `engineering/swift-backend.md`). These are tuned to one lab's workloads. Read for the *structure* of a good system prompt and the YAML-frontmatter conventions; write your own with your own examples.
- [`CLAUDE.md`](../../CLAUDE.md). It's eight rules, each backed by a specific observed failure mode in this repo. Borrow rules whose failure modes match yours; don't copy the whole file wholesale — every rule that doesn't earn its place becomes noise the model learns to skip.
- [`research/gstack-borrow-2026-05-11.md`](../../research/gstack-borrow-2026-05-11.md). The handoff doc for the gstack-borrow initiative. Walks through *why* each lifted concept was picked and what was deliberately dropped. Useful as a worked example of evaluating an external system before adopting it.

**Best ignored**:

- The Linear conventions (team key `MIT`, project-naming patterns). They reflect one workspace.
- The lab-specific specialist agents (`wendy-*`, `gpu-engineer`, `embedded-linux`). Useful only if you run similar workloads.
- The `~/.inc/projects/<slug>/` paths. The choice of `~/.inc` over `~/.config/inc` was preference, not principle.

### D.5 MIT-licensed gstack credit

Several skills are adapted from [Garry Tan's gstack](https://github.com/garrytan/gstack) (MIT-licensed). Specifically:

| Our skill | gstack source | Adaptation |
|---|---|---|
| [`/plan-ceo-review`](../../skills/plan-ceo-review/) | gstack `/plan-ceo-review` | Stripped to ~164 lines from ~2,100. Kept: Prime Directives, Implementation Alternatives protocol, Dream State diagram. Dropped: most of the gstack-specific plumbing. |
| [`/plan-devex-review`](../../skills/plan-devex-review/) | gstack `/plan-devex-review` | Stripped to ~211 lines from ~2,028. Kept: TTHW metric, persona/empathy/benchmark/magical-moment investigation. |
| [`/plan-eng-review`](../../skills/plan-eng-review/) | gstack `/plan-eng-review` | Lifted under [MIT-348](../../decisions/0001-plan-eng-review-lift.md). Kept: coverage diagram, failure-mode registry, Stale Diagram Audit, three-diagram hard gate. Adapted: telemetry writes to `~/.inc/projects/<slug>/telemetry.jsonl` instead of `~/.gstack/projects/<slug>/`. |
| [`/office-hours`](../../skills/office-hours/) | gstack `/office-hours` | Lifted closer to verbatim. Six Forcing Questions for early-stage idea interrogation. |
| [`/work-breakdown`](../../skills/work-breakdown/) | gstack `/autoplan` (concept) | Deliberately narrower. Just classification + Linear orchestration. The full PM → tech-lead → TPM coordinator that gstack's `/autoplan` runs was deferred until one real use shows the seams. |

The role-mapping analysis is at [`research/gstack-role-comparison.md`](../../research/gstack-role-comparison.md). The conclusion: gstack's transferable contribution is the **planning gauntlet as a procedural pipeline**, not the role decomposition. Lift skills, not agents.

Credit: Garry Tan / gstack contributors, [MIT license](https://github.com/garrytan/gstack/blob/main/LICENSE). Adapted files note their gstack origin in the SKILL.md or in the design-doc that landed them. (The `inc` repo itself does not currently ship a `LICENSE` file — it's a personal-ops repo, not a redistributable framework. If you fork it, add your own.)

### D.6 If you want to try it on a throwaway project

The minimum-viable trial:

```bash
git clone https://github.com/mihai-chiorean/inc.git /tmp/inc
cd /tmp/inc && ./install.sh --link --dry-run
```

`--dry-run` prints what `install.sh` would do without writing anything. Read the output, decide if you want the symlinks in your `~/.claude/skills/`, then re-run without `--dry-run`.

If you decide it's not for you, the skills are symlinks — remove **only the ones pointing into your inc clone**:

```bash
find ~/.claude/skills -maxdepth 1 -type l -lname "$HOME/workspace/inc/skills/*" -delete
find ~/.local/bin     -maxdepth 1 -type l -lname "$HOME/workspace/inc/skills/*" -delete
```

Do **not** `rm ~/.claude/skills/*` — that wipes every Claude Code skill on the machine (Anthropic-shipped, plugin-shipped, your other repos), not just the inc ones. The installer creates symlinks into `~/.claude/skills/` by skill name, so this targeted command only removes the ones originating from this clone. Plus the 7 org-scope agents at `~/.claude/agents/` (if you ran the default install) — same `find -lname` pattern handles those: `find ~/.claude/agents -type l -lname "$HOME/workspace/inc/*" -delete`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `install.sh` exits 2 with "SKIP" lines | Real files (not symlinks) at target paths | Inspect each path under `~/.claude/skills/` or `~/.claude/agents/`; remove or rename, re-run |
| `staff: command not found` | `~/.local/bin` not on `PATH` | Section A.3 |
| `staff suggest` says "cannot resolve HR repo" | `STAFF_HR_REPO` not set, no config, no flag | Section A.4 |
| `staff apply` exits 3 | HR repo got new commits between `suggest` and `apply` | Re-run `staff suggest --json` |
| `staff apply` exits 4 | HR repo has uncommitted changes | Commit them, or pass `--allow-dirty-hr` |
| `sitrep-linear: cannot resolve team key` | No `.linear.toml`, no `$LINEAR_TEAM`, no `STATUS.md` | Add `linear_team: <key>` to `STATUS.md` frontmatter |
| `/sitrep` Inbox leaks issues from other repos | `linear_scope` missing or has typos | `sitrep-linear scope` to see what's parsed; cross-check with `linear project list` |
| Linear CLI not authed in CI | Keyring unavailable | Set `LINEAR_API_KEY=lin_api_...` from <https://linear.app/settings/account/security> |

---

## What this guide does not cover

- **Day-to-day workflow.** See [`workflow.md`](workflow.md) — what a typical session looks like once setup is done.
- **Skill reference.** See [`../reference/skills.md`](../reference/skills.md) — one-page catalog of every skill and what fires it.
- **Agent authoring.** See the top-level [`README.md`](../../README.md) section "Customizing Agents for Your Studio" for the YAML frontmatter contract and the system-prompt checklist.
- **Updating after `git pull`.** Re-run `./install.sh --link` (idempotent) and `staff sync` in each project (per-agent diff + accept).
