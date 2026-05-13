# Changelog

## 2026-05-13 — /staff hardening: scope plumbing, matcher fixes, manifest hygiene

A cluster of /staff-skill improvements landed after the first real cross-project use surfaced silent failure modes.

### New /staff subcommands

- `/staff promote <id>` — flip an agent's frontmatter `scope: org`, regenerate `agent.manifest.yaml`, re-run `install.sh --link` so the agent appears at user scope. Idempotent. (MIT-377, PR #34.)
- `/staff rif <id>` — symmetric un-staff. Three modes:
  - `--project` (default in a project with a lockfile) drops the agent from the current project's lockfile and `.claude/agents/<id>.md`.
  - `--global` demotes back to `scope: project` and removes the user-scope symlink **only if it's a symlink whose target lives under the HR repo** — never deletes a real file at `~/.claude/agents/<id>.md`. Refuses without `--force` if any project lockfile (under `~/.inc/projects/*/lock.yaml` OR the current `--project-root`'s own lockfile) still references the agent. Exit code 8 on refusal.
  - `--everywhere` does both.
- `STAFF_PROJECTS_DIR` and `STAFF_USER_AGENTS_DIR` env vars are now honored by `rif` for test-isolation.

### /staff suggest matcher fixes

- **Regex hint scan extended to dependency manifests.** Previously `suggest` only scanned `CLAUDE.md` / `README.md` / `AGENTS.md` for regex matches. Now it also scans `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `requirements.txt`, `pyproject.toml`, `Pipfile{,.lock}`, `poetry.lock`, `uv.lock`, `setup.py`, `go.mod`, `go.sum`, `Cargo.toml`, `Cargo.lock`, `Gemfile{,.lock}`, `composer.json`, `pom.xml`, `build.gradle{,.kts}`. Fixes the real-world case where `ai-engineer`'s `(?i)\bopenai\b` regex failed to fire on a Node project that declared `"openai": "^4.x"` in `package.json` but never mentioned it in the README. Dep files get a 5 MiB byte cap vs 1 MiB for docs because lockfiles are routinely larger. (MIT-378, PR #33.)
- **Empty-summary guardrail.** When a meaningful fraction of agents have empty `description_summary` (≥30% or ≥10), `/staff suggest` now emits a loud-but-non-fatal stderr warning naming the degradation and the exact fix (`python3 scripts/generate-manifest.py --llm-summaries`). Silent in `--no-llm` mode. (MIT-378, PR #33.)

### Manifest hygiene

- **`description_summary` backfilled for all 55 agents** (PR #32). Before this, 54 of 55 had empty summaries; `/staff suggest`'s LLM matcher was running on 200-char truncations of raw descriptions for those agents. The MCP/OpenAI ai-engineer miss that started this cycle was the visible failure mode.
- **`scripts/generate-manifest.py` frontmatter parser hardened** (MIT-376, PR #31). Previously, adding any unrecognized YAML key (e.g. `scope:`) to an agent's frontmatter silently corrupted the previous field's value. The parser now emits a stderr warning with the source path and line number, distinguishes "treating as continuation of X" from "before any known field — line ignored", and scopes `DESCRIPTION_CONTENT_KEYS` (user/assistant/Context/commentary) suppression to inside `description:` only — a `user:` line appearing after `tools:` still warns. `scope` and `skills` are now part of `KNOWN_KEYS`.

### Filed follow-ups

- MIT-379 — evals harness for `/staff suggest` (regression battery with labelled project fixtures).
- MIT-380 — defensive check for JSON-wrapped LLM summaries (would have caught the 4-agent artifact regen issue at compute time, not at codex review time).

## 2026-05-08 — Roster refactor: studio → product-company shape

The project-management + product cluster was reshaped from a creative-studio frame to a product-company frame. Cleaner role boundaries for the LLM router; explicit anti-scope per agent so `/staff suggest` can route reliably; PM + tech-lead pairing pattern documented.

### Renames (with stable-ID aliases)

Existing project lockfiles continue to resolve via the `aliases:` mechanism in `agent.manifest.yaml`. No project action required.

- `sprint-prioritizer` → `product-manager` (product/) — expanded scope: roadmap, discovery synthesis, decision-rationale, ship/kill authority. Drops "6-day cycle" framing.
- `studio-producer` → `tpm` (project-management/) — narrowed to program readiness: cross-team dependencies, schedule, risk surfacing. Drops resource-allocation and process-optimization-for-its-own-sake language.
- `project-shipper` → `release-engineer` (project-management/) — narrowed to operational readiness from code-complete onward: rollout plan, rollback drill, launch monitoring. Drops GTM/marketing copy (lives in marketing agents).

### New agent

- `tech-lead` (engineering/) — owns the HOW for non-trivial features: design doc, implementation approach, sequencing, cross-component coherence. Pulls in domain specialists (backend-architect, frontend-developer, swift-backend, gpu-engineer, infra-reviewer, security-auditor, etc.) for depth on their slice. Pairs with `product-manager` on any non-trivial feature.

### Retired

- `studio-coach` (was `bonus/`) — motivational/affirmational language doesn't survive a single-engineer + agents setup. Useful sliver (multi-agent coordination) is covered by `tpm` plus the orchestrator's natural role. **No alias.** If a project lockfile pinned this, replace with `tpm` or omit.
- `workflow-optimizer` agent (was `testing/`) — overlapped with `tpm` (bottlenecks), `tool-evaluator` (tool integration), and `analytics-reporter` (metrics). The unique sliver — measuring how the agent ecosystem is serving the user — is now a **skill** at `skills/workflow-optimizer/SKILL.md`. **No alias on the agent.** If a project pinned this, switch to invoking the skill periodically instead.

### Tightened

- `experiment-tracker` (project-management/) — explicit anti-scope added: experiment-tracker recommends ship/kill via written readout; `product-manager` makes the final call. Drops "6-day" framing. Description now names the authority boundary.

### New skill

- `skills/workflow-optimizer/SKILL.md` — periodic ergonomics review of the agent roster. Distinct from `/staff audit` (project-side health) and `agent-eval-engineer` (output quality on graded tasks). This is the roster-side health pass. Invoked manually; produces a written report with named recommendations.

### New playbook

- `skills/staff/docs/role-pairings.md` — documents the PM + tech-lead pair (the canonical design unit), the tech-lead + specialists pattern, the TPM ↔ release-engineer code-complete handoff, and how experiment-tracker fits adjacent to all of them. Includes anti-pattern catalog.

### Rationale

The contains-studio fork the roster came from is shaped for a small creative agency producing apps in 6-day sprints. Real product companies have PM, TPM, EM, Tech Lead, Release Engineer as distinct roles with clean handoffs. The studio shape collapsed these into "studio-producer + sprint-prioritizer + project-shipper + studio-coach" with overlapping language that confused the `/staff suggest` LLM router (it would either pick several or none).

The refactor is constrained: net change is +1 agent (`tech-lead`), -2 retired (`studio-coach`, `workflow-optimizer` as agent — replaced by skill). 3 renames. 1 unchanged. Roster size: -1 net.

### Considered and deferred

Codex review surfaced 5 additional Series-B SaaS roles. Each was considered and deferred under the ≤2-new-agent constraint:

- `product-designer` — real gap; separate audit of `design/` cluster owed.
- `product-analyst` / `data-analyst` — partially covered by `analytics-reporter`; instrumentation/funnel work is a real gap but adjacent.
- `customer-success` — proactive customer-relationship side is uncovered.
- `sales-engineer` — out of scope for a personal repo.
- `compliance reviewer` (SOC2/privacy distinct from `security-auditor`) — real gap, separate audit.

The "what new agents do we need overall" question is a separate audit, owed but not done in this refactor.

### Migration

```bash
cd ~/workspace/inc
python3 scripts/generate-manifest.py    # picks up renames and new agent
./install.sh --link --skills-only        # symlinks new skill into ~/.claude/skills/
```

For projects that previously staffed `studio-coach` or `workflow-optimizer` (the agent): the next `staff status` run will report them as `MISSING` from the manifest. Replace with `tpm` (for studio-coach's coordination role) or invoke the new `/workflow-optimizer` skill periodically (for the agent-roster-ergonomics role).
