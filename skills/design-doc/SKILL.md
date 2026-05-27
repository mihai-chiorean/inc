---
name: design-doc
description: |
  Scaffold a design doc with three mandatory diagram sections (user-flow + state-machine + data-flow) plus problem, goals/non-goals, implementation alternatives, failure modes, and open questions. Writes the doc to `decisions/NNNN-<slug>.md` by default; user can override the path. After scaffolding, the user iterates on content — this skill does not generate the diagrams or fill in the sections.

  This skill creates. Audit / hard-gate is the job of `plan-eng-review` (Week 3b, ships separately).
when_to_use: |
  Fires when the user says "design doc", "let me write a design doc", "scaffold a design doc for X", "/design-doc", or any time `/work-breakdown` recommends a design-doc gate (M+ classification). Also use proactively when an L or XL ask is about to start coding without a design doc on record.
argument-hint: '[slug]'
disable-model-invocation: true
version: 0
allowed-tools: Bash, Read, Edit, Write, Glob, Grep, AskUserQuestion
---

# /design-doc — scaffold a design doc

You scaffold a markdown design doc with all the required sections present (even if empty stubs). The user fills them in afterwards. The audit gate (Week 3b `plan-eng-review`) is what enforces that the sections are non-empty before code lands.

The template lives at `skills/design-doc/templates/design-doc.md.tmpl` in the inc repo (resolve via the symlink at `~/.claude/skills/design-doc/templates/design-doc.md.tmpl`).

---

## When to fire

- User says "design doc", "design document", "let me write a design", "scaffold a design doc", "/design-doc".
- `/work-breakdown` recommended a design-doc gate (M+ classification).
- User is about to start coding an L or XL piece of work with no design doc on record — proactively offer.
- Codex / specialist review surfaces a missing-design-doc concern.

Do **not** fire when:
- The user is updating an existing design doc — that's a regular edit.
- The work is S-sized and doesn't need a design doc.
- The user is asking you to write the *contents* of a doc from scratch — this skill scaffolds the shape, the user (or specialist agents) fills the contents.

---

## Procedure

### Step 1 — Gather metadata

Ask the user (use AskUserQuestion in one batch if possible, or infer from STATUS.md):

- **Title** — one-line. Will become the doc's H1.
- **Linear issue** — `MIT-XXX` for traceability. Default: from STATUS.md `linear_issue`. If missing, prompt.
- **Slug** — derived from title (lowercase, dashes). User can override.
- **Path** — see Step 2.

### Step 2 — Resolve the doc path

Default: `decisions/NNNN-<slug>.md` where `NNNN` is the next sequential 4-digit number. This is the **ADR pattern** (Architectural Decision Records).

```bash
# Resolve next number
ROOT="$(git rev-parse --show-toplevel)"
mkdir -p "$ROOT/decisions"
LAST_NUM="$(find "$ROOT/decisions" -maxdepth 1 -name '[0-9][0-9][0-9][0-9]-*.md' \
    | sed -E 's#.*/([0-9]{4})-.*#\1#' | sort -n | tail -1 || echo 0000)"
NEXT_NUM="$(printf '%04d' $((10#${LAST_NUM:-0000} + 1)))"
DOC_PATH="$ROOT/decisions/${NEXT_NUM}-${SLUG}.md"
```

Allow the user to override:
- `design-docs/<slug>.md` for non-temporally-ordered design docs
- `research/<slug>.md` only if explicitly a research note (we already use this for handoffs)

If the user-provided path already exists, **refuse to overwrite** — ask for a new slug or `--force` (explicit, surfaced).

### Step 3 — Scaffold via `design-doc-scaffold`

Steps 2-4 (path resolution, substitution, write) are all handled by the wrapper script:

```bash
design-doc-scaffold \
  --title "<title>" \
  --linear-issue "<MIT-XXX>" \
  --slug "<slug>"                # optional; derived from title if omitted
  # --path "<override>"          # optional; default is decisions/NNNN-<slug>.md
  # --force                      # optional; required to overwrite an existing file
```

The script lives at `skills/design-doc/bin/design-doc-scaffold` (symlinked to `~/.local/bin/design-doc-scaffold`). It handles:

- Resolving the next ADR-style number for `decisions/NNNN-<slug>.md`
- YAML-safe quoting of `title` / `linear_issue` / `author` (so pipes, ampersands, quotes, backslashes don't corrupt the frontmatter — see `design-doc-scaffold --help` for exit-code contract)
- Refusing to overwrite an existing file unless `--force` is passed (and being loud about it when it is)
- Rejecting newline characters in single-line fields

Exit codes: `0` success, `1` template/IO error, `2` bad args, `3` would overwrite without `--force`. The script prints the relative path of the created file on stdout.

**If `design-doc-scaffold` is not on `$PATH`:**

```bash
mkdir -p ~/.local/bin
ln -sf "$(git -C ~/workspace/inc rev-parse --show-toplevel)/skills/design-doc/bin/design-doc-scaffold" ~/.local/bin/design-doc-scaffold
```

### Step 4 — (handled by the script in Step 3)

### Step 5 — Surface a checklist

Print exactly what was created and what still needs filling in:

```
=== /design-doc ===
Created: decisions/NNNN-<slug>.md (link)

Required sections to fill before review:
  1. Problem — REPLACE the placeholder.
  2. Goals / Non-goals — REPLACE both lists.
  3. Implementation alternatives — at least 2 approaches with pros/cons.
  4. User flow diagram (ASCII) — happy path + ≥1 branch.
  5. State machine (ASCII) — if stateful; otherwise mark "Not applicable" with reason.
  6. Data flow diagram (ASCII) — all four paths (happy, nil, empty, upstream error).
  7. Failure modes table — every error has a name.
  8. Open questions — at least one per design (be honest about uncertainty).

Recommended next actions:
  → Spawn the relevant specialist (PM / tech-lead / plan-devex-review) to draft section <X>.
  → When all sections filled, change frontmatter status: draft → in-review.
  → Plan-eng-review (Week 3b, when it ships) audits the doc before any code lands.
```

### Step 6 — Update STATUS.md (if appropriate)

If the design doc is for the **active** work (matches `current_objective`), append to "Open items needing my attention":

```
- decisions/NNNN-<slug>.md — design doc draft; fill before coding
```

Otherwise (side-quest design doc), apply the same three-question test as `/work-breakdown` Step 7 — most design docs are part of the current thread, so Case A is the default.

### Step 7 — Fail loud (per CLAUDE.md Rule 6)

State explicitly what was NOT done:

- The file was created but **no sections are filled** — the doc is a shell, not a design.
- Diagrams are stubs; the user must replace them with real ASCII art.
- No audit ran; `plan-eng-review` is Week 3b and may not exist yet.

Surface these inline with the success message — do not bury them in a separate paragraph.

---

## Section reference (what each one is for)

| Section | Purpose | Mandatory? |
|---|---|---|
| Problem | What hurts today, who feels it. | Yes |
| Goals / Non-goals | Observable success + scope guardrails. | Yes |
| Implementation alternatives | ≥ 2 approaches with effort/risk/pros/cons. | Yes |
| User flow diagram (ASCII) | Happy path + branches. | Yes |
| State machine (ASCII) | States + transitions + invalid transitions. | Yes if any stateful object; explicit "N/A — why" otherwise |
| Data flow diagram (ASCII) | Four paths: happy, nil, empty, upstream error. | Yes |
| Failure modes table | Every error has a name + catcher + user surface + tested?. | Yes |
| Open questions | What the design doesn't yet answer + by-when. | Yes |
| Appendix | Anything else (links, raw notes, alternatives rejected). | Optional |

The three diagrams are the load-bearing additions from gstack `plan-ceo-review` Prime Directive #6. Their existence is the entire reason this skill ships.

---

## What `/design-doc` does NOT do

- **Fill in section content.** Section bodies are the user's (or specialist agents') job. The skill provides the shape.
- **Generate diagrams.** ASCII art is a human-judgment artifact. Auto-generated diagrams from code drift; we want intentional ones.
- **Audit.** `plan-eng-review` (Week 3b) checks that sections are non-empty + diagrams exist + failure-modes table is filled.
- **Linear document creation.** We use markdown in the repo for version-controlled history + diff visibility. Linear documents are good for shared review but lose history.

---

## Examples

### Example A — design doc for an M-sized feature

User: *"I'm about to start `/sitrep --all`. Let me write a design doc first."*

```
=== /design-doc ===
Title:       /sitrep --all for cross-project rollup
Linear:      MIT-345
Path:        decisions/0001-sitrep-all-cross-project-rollup.md
Created:     2026-05-11T18:23:00Z

Required sections to fill before review:
  1. Problem — REPLACE the placeholder.
  2. Goals / Non-goals — REPLACE both lists.
  ... (etc, 8 total)

NOT done (per Rule 6):
  • File created but no sections filled — shell only.
  • Diagrams are stubs.
  • plan-eng-review is Week 3b; not yet shipped.

Next action:
  → Fill section 1 (Problem) first; everything else flows from it.
```

### Example B — design doc rejecting a target path

User: *"Scaffold a design doc to `research/sitrep-all.md`."*

```
=== /design-doc ===
Refusing — file already exists at research/sitrep-all.md.

Options:
  (a) Pick a new slug: /design-doc with slug "sitrep-all-v2"
  (b) Force overwrite: /design-doc with --force (will be loud about it)
  (c) Edit the existing file directly (not via this skill)

Recommended: option (c) if the existing file is a handoff or research note;
option (a) if it's a stale design doc you want to supersede.
```

---

## Pointers

- **Template:** `skills/design-doc/templates/design-doc.md.tmpl`
- **CLAUDE.md rules:** Rule 5 (surface conflicts) + Rule 6 (fail loud) apply to design docs too — when alternatives in Section 3 conflict, name the conflict; when sections are stub-only, say so loudly.
- **Composition with `/work-breakdown`:** an M+ classification recommends a design-doc gate; this skill is what satisfies it.
- **Audit:** Week 3b `plan-eng-review` (lifted from gstack, stripped of plumbing). Until it ships, audit by inspection against this SKILL.md's section reference table.
