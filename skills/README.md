# Skills

Each skill lives in its own directory under this `skills/` tree. Per the inc convention (which mirrors Anthropic's published "Complete Guide to Building Skills for Claude"), a skill is **a folder-based distribution unit**, not just a single file.

## Required structure

```
skills/<skill-name>/
└── SKILL.md           # required — frontmatter + body
```

## Optional structure (Anthropic spec)

The Anthropic skills guide specifies three optional subdirectories. Adopt whichever fit your skill's shape:

```
skills/<skill-name>/
├── SKILL.md           # required
├── scripts/           # executables the skill can run
│   ├── foo.py
│   └── bar.sh
├── references/        # supporting documentation the skill consumes
│   ├── examples.md
│   └── schema.yaml
└── assets/            # static files the skill ships with
    ├── template.md
    └── logo.svg
```

- **`scripts/`** — Python/shell/etc. that the skill invokes via `Bash` tool calls. Examples in our repo: `skills/staff/scripts/` (Python orchestration), `skills/sitrep/bin/sitrep-linear` (shell wrapper). Sometimes also published into `bin/` if you want them on `$PATH` after install.
- **`references/`** — Markdown / YAML / JSON the skill consumes for its own context. Examples: `skills/staff/docs/manual.md`, `skills/staff/docs/schemas.md`.
- **`assets/`** — Static content the skill produces or templates from. Examples: design tokens, prompt templates, boilerplate files.

## Portability

Skills should be self-contained per Anthropic's open standard for skill distribution. Avoid in `SKILL.md`:

- ❌ Absolute paths outside the skill directory (e.g., `/home/mihai/workspace/inc/...`).
- ❌ Hardcoded machine-specific paths (e.g., `~/specific-user-only-dir/`).
- ❌ Dynamic context (`` !`command` ``) referencing non-portable commands without fallback.
- ✅ Relative paths from `SKILL.md` (e.g., `scripts/foo.py`).
- ✅ Environment-variable-aware paths (e.g., `$HOME/.inc/...`).
- ✅ Commands available on most POSIX systems, plus optional fallbacks.

The validator at `scripts/validate-agents.py --check-portability` can flag common issues; see its `--help`.

## Frontmatter

See `scripts/validate-agents.py` for the spec-allowed frontmatter keys (`SKILL_SPEC_KEYS`). The MIT-413 validator enforces these per Anthropic's published `skills.md` reference.

Key fields:

- **`name`** (optional) — defaults to the directory name.
- **`description`** (recommended) — what the skill does + when to use it. Combined with `when_to_use`, capped at 1,536 chars.
- **`when_to_use`** (optional) — trigger phrases ("Fires when user says X / mentions Y"). Frees `description` to be a tight one-liner.
- **`argument-hint`** (optional) — autocomplete hint for arg-taking skills, e.g., `[slug]` or `[duration] [command]`.
- **`disable-model-invocation: true`** (recommended for side-effect skills) — prevents Claude from auto-firing the skill. Use on anything that writes state, creates tickets, or has irreversible effects (`/staff apply`, `/work-breakdown`, `/design-doc`, etc.).
- **`allowed-tools` / `disallowed-tools`** — restrict the skill's tool access.
- **`background`** (optional) — run a forked skill in the background.
- **`license`**, **`compatibility`** (optional, open Agent Skills spec) — license name; environment requirements (≤500 chars).
- **`metadata`** (optional) — free-form map for anything Claude Code doesn't read itself: `version`, `deprecation-notice`, `references`, and so on. For example:
  ```yaml
  metadata:
    version: "0"
    references:
      - postgres-patterns.md
  ```

Top-level `version:` / `deprecation-notice:` (accepted under MIT-437) are **not** in Claude Code's skills table and are silently ignored; the validator WARNs and asks you to move them under `metadata:`. The loader doesn't read `references:` either: link reference files from the SKILL.md body ("See references/x.md") so Claude actually opens them.

## Distribution (advanced)

Anthropic shipped org-wide skill deployment in Dec 2025 (admins push skills across workspaces with centralized updates). We don't currently use this — single-user repo — but `metadata.version` / `metadata.deprecation-notice` future-proof if we ever do.

For one-off sharing, package a skill folder as a zip via `make zip-skill SKILL=<name>` (see top-level `Makefile`). Recipient unzips into their `~/.claude/skills/` and the skill is available.

## Authoring a new skill

1. Create the directory: `mkdir skills/<my-skill>`
2. Write `SKILL.md` with the required frontmatter.
3. Add `scripts/`, `references/`, `assets/` subdirs as needed.
4. Run `python3 scripts/validate-agents.py` to verify it passes.
5. Symlink-installed by `install.sh --link` automatically on next run.

For broader guidance see:
- Anthropic's published guide: https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf
- `docs/getting-started/workflow.md` §6 "Validators for agent + manifest changes"
