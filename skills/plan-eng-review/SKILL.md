---
name: plan-eng-review
description: |
  Audit a design doc. Mechanical checks (8 required sections present, no REPLACE stubs, 3 diagrams non-stub, failure-modes table populated, open questions populated) plus a qualitative pass (architecture coherence, test coverage diagram, failure-mode critical-gap registry, stale-diagram audit, confidence calibration). On PASS, mutates the doc's frontmatter `status: draft → accepted` and writes telemetry + restore-point.

  Use when the user says "audit this design doc", "is decisions/<file> ready", "review this plan", "/plan-eng-review", or when `/work-breakdown` recommends the eng-review gate (M+ classification with design-doc completed).

  Adapted from gstack's plan-eng-review.md (1634 lines) — stripped of its session-bootstrap plumbing, telemetry binary, outside-voice subagent, and gstack-specific filesystem layout. Kept: the audit logic, Confidence Calibration, Stale Diagram Audit, failure-modes registry. Mechanical checks delegated to `plan-eng-review-audit` wrapper.
version: 0
allowed-tools: Bash, Read, Edit, Glob, Grep, AskUserQuestion
---

# /plan-eng-review — audit a design doc

You are the **qualitative review layer** for design docs. The mechanical checks (sections present, REPLACE-stub detection, diagram non-emptiness, frontmatter validity, status transitions) are delegated to `plan-eng-review-audit` — a Python wrapper symlinked to `~/.local/bin/plan-eng-review-audit` from `skills/plan-eng-review/bin/`. Run that first; if it FAILs, surface the gaps and stop. If it PASSes mechanically, do the qualitative review below; if THAT passes too, commit the audit (mutates frontmatter, writes telemetry, snapshots a restore point).

The spec for both layers is in `decisions/0001-plan-eng-review-lift.md`.

---

## When to fire

- User says "audit this design doc", "review this plan", "is decisions/<file> ready", or invokes `/plan-eng-review` directly.
- `/work-breakdown` recommended an eng-review gate (M+ classification with a design doc already created).
- A PR contains a new or substantially changed design doc and the user wants to gate-check it before merging.

**Do NOT** fire when:
- The doc isn't a design doc (e.g. research handoff in `research/`, README, blog draft). The audit's section-shape assumptions only apply to docs scaffolded by `/design-doc`.
- The user is editing the design doc and asking for inline feedback — that's regular review, not the audit gate.

---

## Procedure

### Step 1 — Locate the doc

The user passes a path: `decisions/NNNN-<slug>.md` (or absolute / repo-relative). Resolve it. If missing, stop with a clear message and stop.

### Step 2 — Run the mechanical audit (no mutation)

```bash
plan-eng-review-audit --mechanical-only <doc-path>
```

Exit codes:
- `0` → mechanical PASS. Proceed to Step 3 (qualitative review).
- `1` → file not found. Stop; tell the user.
- `2` → frontmatter malformed OR illegal status transition. Stop; surface the wrapper's error verbatim.
- `3` → mechanical FAIL. The wrapper printed a gap list. Surface the gaps to the user, **do not proceed to qualitative review** (the doc isn't structurally ready). Recommend they fix the gaps and re-run.

If you got exit 3, the typical fix loop is:
1. Read the gap list.
2. Open the doc.
3. Replace stubs with real content / add missing sections / add failure-modes table rows / add open-questions list items.
4. Re-run `plan-eng-review-audit --mechanical-only`.
5. Iterate until exit 0.

### Step 3 — Qualitative review (the actual judgment)

Mechanical checks tell you the doc has the right **shape**. The qualitative review tells you whether the **content holds up**. Adapted from gstack's plan-eng-review, six lenses:

#### 3.1 — Scope challenge (gstack Step 0)

Read sections 1 (Problem) and 2 (Goals / Non-goals / Verification). Ask:

- Is the **premise** correct? If the Problem statement is wrong about what's broken, no amount of well-designed solution helps.
- Is the scope **right-sized**? Goals fit the stated problem, non-goals are honestly named (not just "things we forgot"), verification has a concrete observable success.
- Does the doc avoid both **scope creep** (goals that wandered beyond the problem) and **under-scoping** (goals that don't actually solve the problem)?

Flag any of the above.

#### 3.2 — Architecture review

Read section 3 (Implementation alternatives) and the diagrams in sections 4-6. Ask:

- Does the chosen approach actually solve the goals? Could any of the rejected alternatives have worked?
- Are the **named tradeoffs** real, or generic ("pros: simple; cons: less powerful")? Tradeoffs that don't predict outcomes are decoration.
- Does the user-flow diagram cover at least one non-happy branch? Linear flows mean unstated assumptions.
- Does the state machine name **invalid transitions** explicitly, not just legal ones? (gstack Prime Directive: every state has a "what prevents bad transitions" mechanism.)
- Does the data-flow diagram cover all four paths (happy, nil, empty, upstream error)? If one is missing or trivially handled, that's a future bug.

#### 3.3 — Test review (gstack Section 3)

Read section 2's Verification subsection + section 7's `Tested?` column. Ask:

- Does the verification plan have **observable success criteria**? "Manual test passes" without specifics is not a plan.
- Do the failure modes named in section 7 have plausible test paths? An untested critical failure mode is a critical gap.
- Look for the **coverage diagram pattern** if the doc references code: code paths + user flows with ★ ratings + `[→E2E]` / `[→EVAL]` markers (lifted from gstack). For pure docs/skills work where there are no traditional tests, this section can say "N/A — manual verification only" but should still name what gets verified.

#### 3.4 — Failure-mode critical-gap registry

Read section 7. For each row, ask:

- **Triggered by** — is the trigger concrete? "Bad input" doesn't count; "frontmatter `status: superseded`" does.
- **Caught by** — does something actually catch it? "Code reviewer would notice" is hope, not catch.
- **User sees** — does the user see a specific message OR a silent state change? Per CLAUDE.md Rule 6, silent failures are a critical defect.
- **Tested?** — `yes`, `no`, or `planned` with a planned-by-when. Empty cells are gaps.

Count rows where the answer to any of the above is unclear — those are **critical gaps**. ≥ 1 critical gap → qualitative FAIL.

#### 3.5 — Stale-diagram audit (gstack)

If the design doc references existing code files (e.g. mentions `skills/sitrep/bin/sitrep-linear`), grep those files for ASCII diagrams. Each diagram found is a potential staleness risk. For each:

- Does the diagram still match the file's current behavior?
- If the design doc proposes changes to that file, does the diagram need updating as part of this work?

This is qualitative — Claude reads, compares, flags. Stale diagrams are worse than no diagrams.

#### 3.6 — Confidence calibration (Rule 6 / gstack Voice)

For each qualitative finding above, state confidence explicitly:
- **High** — verified by reading the doc + the code it references.
- **Medium** — inferred from the doc but the code wasn't checked.
- **Low** — the doc was unclear or the section was sparse; this is a guess.

A "high-confidence pass" with no checking is worse than a "medium-confidence pass with named uncertainty."

### Step 4 — Report

Print a structured report. Use exactly these section labels:

```
=== /plan-eng-review ===
Doc: <path>
Mechanical: PASS  (plan-eng-review-audit --mechanical-only)
Qualitative:
  3.1 Scope challenge:        <PASS | gaps>
  3.2 Architecture:           <PASS | gaps>
  3.3 Tests:                  <PASS | gaps>
  3.4 Failure-mode registry:  <PASS | N critical gaps>
  3.5 Stale-diagram audit:    <PASS | gaps | N/A — no code refs>
  3.6 Confidence calibration: <overall confidence + uncertainty list>

Verdict: <READY TO ACCEPT | NEEDS WORK>
```

If `READY TO ACCEPT`, proceed to Step 5. If `NEEDS WORK`, list the gaps with section pointers and stop — user must address before re-audit.

### Step 5 — Commit the audit (mutate doc + telemetry + restore)

Ask the user: "Mechanical and qualitative checks pass. Want me to commit the audit? This will:
- Mutate frontmatter `status: <current>` → `status: accepted` in `<doc>`.
- Write a JSONL telemetry line to `~/.inc/projects/<slug>/telemetry.jsonl`.
- Snapshot the doc (pre-mutation) to `~/.inc/projects/<slug>/restore/<datetime>-<basename>`.

Confirm to proceed."

On `yes`:

```bash
plan-eng-review-audit <doc-path>
```

(no `--mechanical-only` flag this time → wrapper performs the mutation + restore + telemetry).

Print the wrapper's output verbatim. The `accepted` status is now persistent; coding may begin.

On `no`: leave the doc untouched. Tell the user the audit found no blockers but they've chosen not to commit.

### Step 6 — Update STATUS.md

If the audited design doc is for the active work (matches `current_objective` or the active branch's Linear issue), append a decisions-log entry:

```
- YYYY-MM-DD — `decisions/NNNN-<slug>.md` audited (plan-eng-review). Status: accepted. Restore: ~/.inc/projects/<slug>/restore/<dt>-<basename>.
```

If it's a side-quest audit, just note it in "Open items" with status: accepted, no objective change. Apply the three-question side-quest test from `/work-breakdown` Step 7.

---

## Output examples

### Example A — clean PASS

```
=== /plan-eng-review ===
Doc: decisions/0001-plan-eng-review-lift.md
Mechanical: PASS

Qualitative:
  3.1 Scope challenge:        PASS — premise is sharp; non-goals honestly bounded
  3.2 Architecture:           PASS — three alternatives compared with named tradeoffs;
                                    user-flow + state-machine + data-flow all present
                                    with non-happy paths
  3.3 Tests:                  PASS — verification subsection has 3 observable criteria;
                                    11 failure modes all marked tested? with rationale
  3.4 Failure-mode registry:  PASS — no critical gaps; silent-failure audit confirms
                                    none
  3.5 Stale-diagram audit:    N/A — doc references skills/plan-eng-review/* which
                                    doesn't exist yet (this is the audit FOR that work)
  3.6 Confidence calibration: HIGH — verified against the SKILL.md + wrapper source

Verdict: READY TO ACCEPT

Commit the audit? (mutates frontmatter, writes telemetry, snapshots restore point)
```

### Example B — mechanical FAIL

```
plan-eng-review-audit --mechanical-only decisions/0042-foo.md

FAIL: 4 gaps
- ReplaceTokenPresent: section 1 contains stub REPLACE at line(s) 21
- ReplaceTokenPresent: section 7 contains stub REPLACE at line(s) 142
- DiagramStubOnly: section 5 diagram is still a stub
- OpenQuestionsEmpty: section 8 has no list items

This is structural — the doc isn't shape-ready. Fill the stubs, fill the diagram, add at least one open question (be honest about uncertainty). Re-run when ready.
```

### Example C — qualitative FAIL with mechanical PASS

```
=== /plan-eng-review ===
Doc: decisions/0042-foo.md
Mechanical: PASS

Qualitative:
  3.1 Scope challenge:        PASS
  3.2 Architecture:           GAP — user-flow diagram is a single happy-path line; no branches.
                              The state machine names 3 states but no invalid transitions.
  3.3 Tests:                  GAP — verification says "manual test"; no observable criteria.
  3.4 Failure-mode registry:  2 critical gaps:
                                row 3: "Caught by reviewer" — that's hope, not catch
                                row 7: "Tested? — TBD" with no by-when
  3.5 Stale-diagram audit:    PASS — no code refs
  3.6 Confidence calibration: MEDIUM — flagged-gap rows are HIGH confidence; rest MEDIUM.

Verdict: NEEDS WORK — 4 qualitative gaps. Address sections 3.2, 3.3, 3.4 above. Re-audit when ready.
```

---

## What `/plan-eng-review` does NOT do (yet)

- **Audit non-design-docs.** Won't audit blog drafts, READMEs, research handoffs. Section-shape assumptions are specific to `/design-doc` scaffolds.
- **Re-audit on save.** Manual invocation only.
- **Block PRs.** v0 is solo-engineer audit-discipline. PR-blocking via CI requires `--mechanical-only` mode (which IS provided in the wrapper) but wiring is future work.
- **Fix the doc.** The audit reports gaps; the user fixes. The skill doesn't auto-rewrite sections.
- **Outside-voice subagent.** gstack's pattern of running `codex exec` for an independent second opinion is deferred — we already do codex review separately on PRs.

---

## Pointers

- **Spec:** `decisions/0001-plan-eng-review-lift.md` — design doc for THIS skill. Recursive: this skill audits that doc.
- **Wrapper:** `skills/plan-eng-review/bin/plan-eng-review-audit` (symlinked to `~/.local/bin/plan-eng-review-audit`).
- **CLAUDE.md rules in play:** Rule 5 (Surface conflicts — qualitative gaps must be surfaced, not blended), Rule 6 (Fail loud — explicit confidence calibration, no "looks right" without checking).
- **Composes with:** `/design-doc` (creates), `/work-breakdown` (recommends as M+ gate).
- **Storage layer:** `~/.inc/projects/<slug>/` — established in this PR; later skills can also write here (telemetry, restore points).
