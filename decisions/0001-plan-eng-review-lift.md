---
doc_version: 1
title: "plan-eng-review skill lift (audits design docs)"
linear_issue: "MIT-348"
status: accepted
created: "2026-05-12T06:00:49Z"
authors:
  - "Mihai Chiorean"
---

# plan-eng-review skill lift (audits design docs)

> **Status:** draft &middot; **Linear:** MIT-348 &middot; **Created:** 2026-05-12T06:00:49Z
>
> Recursive setup: this doc will be audited by the very skill it designs. Until the skill ships, audit by inspection against the section reference in `skills/design-doc/SKILL.md`.

---

## 1. Problem

`/design-doc` (Week 3a) scaffolds an 8-section design doc with three mandatory diagram stubs. **There's no enforcement.** A scaffolded doc with all sections marked `REPLACE` is structurally identical to a filled-in one — both have 8 H2 headers, both have three fenced code blocks. The first time we ship a feature whose "design doc" is a forest of stubs, the gate is meaningless and the 3-diagram requirement (gstack `plan-ceo-review` Prime Directive #6, the load-bearing thing we explicitly adopted) is theater.

Pain bucket A (procedural discipline) only converts to actual discipline when the procedure produces a binary "are we ready to code" answer. Today, the only answer is "looks filled in to a human who skimmed it once."

## 2. Goals / Non-goals

### Goals
- A design doc with `REPLACE` stubs in any required section **fails audit** with a specific gap list (section + reason).
- All three mandatory diagrams (user-flow, state-machine-if-applicable, data-flow with all 4 paths) must be present and non-stub to pass.
- The failure-modes table cannot be empty (at least one named failure mode is the floor).
- On pass: frontmatter `status: draft` → `status: accepted` (mutated in place). On fail: no mutation; gap list printed; non-zero exit.
- Per-audit telemetry written to `~/.inc/projects/<slug>/telemetry.jsonl`. Auditable trail of when audits ran, what gaps existed, and when they were resolved.
- Pre-mutation restore point saved to `~/.inc/projects/<slug>/restore/<datetime>-<doc-basename>.md` so the user can roll back a bad audit-acceptance.

### Non-goals
- Re-implementing gstack's full plumbing (their telemetry binary, JSONL `review-log`, outside-voice subagent harness, `~/.gstack/projects/` restore format).
- AST-level coverage analysis. The audit reads what the doc *claims* about test coverage and failure modes; it does NOT ground-truth those claims against actual tests or code.
- Auto-running on every commit. v0 is manual invocation only.
- Re-implementing gstack's per-skill Voice section beyond the Confidence Calibration sub-pattern (folded into the audit output format).

### Verification
- **Acceptance test:** audit *this doc* before fully filling it → must FAIL with gap list. Fill the remaining sections → re-audit → must PASS with `status: draft → accepted` mutation.
- **Telemetry test:** `cat ~/.inc/projects/inc/telemetry.jsonl` after the above shows two events (one failed audit, one passed audit) with the gap list on the first.
- **Restore-point test:** the pre-acceptance restore point exists at `~/.inc/projects/inc/restore/<datetime>-0001-plan-eng-review-lift.md` and is byte-identical to the doc state immediately before the `draft → accepted` mutation.

## 3. Implementation alternatives

### Approach A — Procedural-only SKILL.md (no wrapper script)
- **Summary:** Claude reads the design doc, runs the audit procedurally in-context, writes findings + (on pass) mutates frontmatter via the Edit tool.
- **Effort:** S
- **Risk:** Med
- **Pros:** Quick to ship; no Python wrapper to maintain; matches `/sitrep v0` pattern (pure SKILL.md, no scripts).
- **Cons:** Audit consistency depends on Claude reasoning; the gate isn't programmatically enforceable (e.g. by CI later); deterministic checks (REPLACE-token presence, frontmatter validity, diagram code-block non-emptiness) get redone every invocation.
- **Reuses:** existing `/sitrep` and `/work-breakdown` procedural patterns.

### Approach B — Hybrid: Python wrapper for deterministic checks + SKILL.md for qualitative review
- **Summary:** `skills/plan-eng-review/bin/plan-eng-review-audit` (Python) does the mechanical checks (frontmatter parses; all 8 H2 sections present; no `REPLACE` tokens in body; diagram blocks non-stub; failure-modes table has ≥1 named entry; open questions ≥1) and writes telemetry + restore-point. SKILL.md adds the qualitative pass (does the state-machine cover invalid transitions? is each failure mode actually catchable? is the verification plan executable?) and the user-facing report.
- **Effort:** M
- **Risk:** Low
- **Pros:** Mechanical checks are deterministic, fast, CI-able (we get the option to gate PRs later for free); qualitative checks where judgment is needed; matches the established pattern (`sitrep-linear`+SKILL.md, `design-doc-scaffold`+SKILL.md).
- **Cons:** More moving parts; need exit-code contract for the wrapper; wrapper duplicates some logic that the SKILL.md procedure also expresses.
- **Reuses:** `design-doc-scaffold`'s YAML-parse pattern, file-on-disk semantics, exit-code conventions.

### Approach C — Pure Python wrapper (no SKILL.md)
- **Summary:** All checks programmatic. Output is a JSON or text report. No Claude in the loop.
- **Effort:** S
- **Risk:** Med
- **Pros:** Fully deterministic; trivial to wire into CI; cheap to run.
- **Cons:** Loses the entire qualitative-review value (the actual point of `plan-eng-review`). A design doc with all 8 sections filled but full of incoherent contradictions would pass.
- **Reuses:** `design-doc-scaffold` template parsing.

**Recommendation:** **Approach B.** Mechanical gates programmatically, qualitative gates procedurally. The wrapper's `exit 0` is *necessary but not sufficient* for acceptance; the SKILL.md procedure provides the sufficiency. Maps cleanly to the established repo pattern (every recent skill = SKILL.md + bin/wrapper).

## 4. User flow diagram (mandatory)

```text
[user] runs:  /plan-eng-review decisions/NNNN-foo.md
                │
                ▼
        ┌─────────────────────────────────────────────┐
        │   plan-eng-review-audit  (Python wrapper)   │
        │   - parse frontmatter                       │
        │   - check 8 sections present                │
        │   - check no REPLACE tokens in body         │
        │   - check 3 diagram blocks non-stub         │
        │   - check failure-modes table >= 1 row      │
        │   - check open-questions >= 1 item          │
        └─────────────────────────────────────────────┘
                │
        ┌───────┴────────┐
        ▼                ▼
   mechanical          mechanical
     PASS                FAIL
        │                │
        ▼                ▼
   ┌────────────┐    ┌──────────────────────────┐
   │ SKILL.md   │    │ print gap list + status: │
   │ qualitative│    │ issues_open  → exit 3    │
   │ review     │    │ NO mutation              │
   └────────────┘    └──────────────────────────┘
        │                  (user fixes + re-runs)
   ┌────┴────┐
   ▼         ▼
 PASS      FAIL (qualitative)
   │         │
   ▼         ▼
 mutate    print qualitative gaps;
 status:   exit 3; no mutation
 draft →
 accepted
   │
   ▼
 write telemetry entry
   │
   ▼
 write restore point (pre-mutation snapshot)
   │
   ▼
 exit 0  →  doc is now "accepted"; coding may begin
```

## 5. State machine (mandatory if any stateful object)

The design doc's frontmatter `status` field is the stateful object the auditor manipulates.

```text
                        ┌─────────────┐
        scaffolded ────→│   draft     │
                        └──────┬──────┘
                               │ user requests audit
                               ▼
                        ┌─────────────┐
                        │  in-review  │
                        └──────┬──────┘
                               │ audit runs
                  ┌────────────┼────────────┐
                  │            │            │
              PASS │       FAIL │     ERROR │  (parse/IO)
                  ▼            ▼            ▼
            ┌──────────┐ ┌──────────────┐ ┌────────┐
            │ accepted │ │ issues_open  │ │ error  │
            └──────────┘ └──────┬───────┘ └────────┘
                  │             │  (user updates doc)
                  │             │
                  │             ▼
                  │      back to in-review on next audit
                  │
                  │ later: new design replaces
                  ▼
            ┌─────────────┐
            │ superseded  │
            └─────────────┘

Invalid transitions (prevented by wrapper):
  - draft → accepted directly (must go through in-review/audit)
  - issues_open → accepted directly (must re-audit and pass)
  - accepted → draft / in-review (use superseded instead; this is a different doc)
  - any → error (error is only emitted, never targeted)
```

The wrapper enforces these by reading the *current* status and only allowing legal next-states. Any illegal write is refused with a clear error and exit code 2.

## 6. Data flow diagram (mandatory)

### Flow A — design doc → audit report + (on pass) mutated doc

```text
Happy path:
  [doc path]
    → read
    → parse frontmatter (YAML)
    → mechanical checks (8 sections, REPLACE count, diagram-block non-emptiness)
    → qualitative review (SKILL.md procedure)
    → snapshot doc to ~/.inc/projects/<slug>/restore/<dt>-<basename>.md
    → mutate frontmatter status: in-review → accepted
    → write ~/.inc/projects/<slug>/telemetry.jsonl event {status: pass, gaps: []}
    → exit 0

Nil input (no path argument):
  [argv empty]
    → wrapper prints usage
    → exit 2 (bad args; same convention as design-doc-scaffold)

Empty input (path exists but file is 0 bytes):
  [empty file]
    → frontmatter parse fails (no `---` block)
    → status: error
    → write telemetry event {status: error, reason: empty_file}
    → exit 2

Upstream error (filesystem unwritable, ~/.inc not creatable):
  [doc path readable, but telemetry path not writable]
    → audit runs normally
    → mutation succeeds
    → telemetry write fails → log warning to stderr
    → exit 0 (audit succeeded; telemetry is best-effort)

  Trade-off: audit success takes precedence over telemetry. The alternative
  (fail audit when telemetry can't write) would couple the artifact's
  acceptance to a logging concern, which is wrong.
```

### Flow B — telemetry jsonl read-side (consumed by /sitrep + future /retro)

```text
Happy path:
  [/sitrep --telemetry or similar reader]
    → tail ~/.inc/projects/<slug>/telemetry.jsonl
    → parse each line as JSON
    → surface recent audit history

Nil input:
  [no jsonl file yet — never run]
    → reader gracefully returns "no audits recorded"

Empty input:
  [jsonl file exists but 0 bytes]
    → reader returns "no audits recorded"

Upstream error:
  [permission denied / disk full]
    → reader logs warning and continues without telemetry context
```

This flow doesn't ship in Week 3b — it's documented here so the telemetry format is designed for a future reader. The format: one JSON object per line, with fields `{ts, repo, skill: "plan-eng-review", event: "audit", doc, status, gaps, duration_ms}`.

## 7. Failure modes

| Failure | Triggered by | Caught by | User sees | Tested? |
|---|---|---|---|---|
| `DocNotFound` | path doesn't exist | wrapper `Path.exists()` check | `plan-eng-review-audit: doc not found at <path>` + exit 1 | yes (manual) |
| `FrontmatterMalformed` | invalid YAML in `---` block | wrapper `yaml.safe_load` exception | `plan-eng-review-audit: frontmatter parse error at line N: <error>` + exit 2 | yes (manual, with crafted invalid doc) |
| `MissingSection` | required H2 absent | wrapper section-presence check | gap list entry: `Section "<title>" missing` + exit 3 | yes (manual, against scaffolded-but-not-filled doc) |
| `ReplaceTokenPresent` | `REPLACE` appears in body **as actual stub content**, NOT as meta-reference in backtick-quoted prose | wrapper regex scan with detection rule (see open question 5) | gap list entry per section: `REPLACE token in section <N>` + exit 3 | yes (manual, against scaffolded doc) |
| `DiagramStubOnly` | diagram code block contains only stub content (`REPLACE` or empty) | wrapper diagram-content check | gap list entry: `Diagram <N> is still a stub` + exit 3 | yes (manual) |
| `FailureModesEmpty` | section 7 has 0 data rows in the table | wrapper table-parser check | gap list entry: `Failure modes table has no entries` + exit 3 | yes (manual) |
| `OpenQuestionsEmpty` | section 8 has 0 list items | wrapper section-content check | gap list entry: `Open questions section is empty` + exit 3 | yes (manual) |
| `IllegalStatusTransition` | trying to accept a doc with frontmatter status: superseded or already accepted | wrapper status-machine check | `cannot transition <X> → accepted; create a new design doc instead` + exit 2 | yes (manual) |
| `TelemetryWriteFailed` | `~/.inc/projects/...` unwritable | wrapper try/except around append | stderr warning: `telemetry write failed: <reason>`; audit continues + exit 0 | no (defer until storage layer exists) |
| `RestoreWriteFailed` | restore dir unwritable | wrapper try/except | stderr warning; audit continues + exit 0 | no (defer) |
| `QualitativeGap` (judgment) | SKILL.md procedure finds e.g. an unreachable state in the state-machine, or a data-flow path that contradicts the failure-modes table | SKILL.md output | the qualitative gap list is appended below the mechanical pass; user must address before re-audit | no (procedural; not unit-testable) |

**Silent failures audit:** none. Every mechanical check has a named exit code. Every qualitative gap surfaces in the report. Telemetry/restore-write failures emit stderr warnings; they never silently swallow.

## 8. Open questions

- **Restore-point retention.** Keep last N restore points per doc? Time-based GC (older than X days)? Per-doc or per-`~/.inc/projects/<slug>/`? Proposed: keep last 30 per doc; deletion is a separate `/inc-cleanup` skill someday. (S-sized future work; defer.)
- **Status: superseded mechanics.** When a new design doc replaces an old one, who flips the old doc's status to `superseded`? Manual? A `/design-doc supersede <old> <new>` subcommand? Proposed: v0 = manual edit; revisit if it becomes painful.
- **Auto-fire on save.** Should `/plan-eng-review` fire automatically when a design doc is saved (e.g. via a Claude Code hook)? Proposed: no in v0; manual only. Auto-fire risks running audit on every keystroke during writing.
- **Slug resolution at write time.** The wrapper writes to `~/.inc/projects/<slug>/`. Slug = `git rev-parse --show-toplevel | xargs basename` per the prior conversation. What if the doc is being audited from outside a git repo? Proposed: fall back to a single `~/.inc/projects/_orphan/` directory with a stderr warning; resolves to the user explicitly later if they want.
- **REPLACE-token detection precision.** This very doc mentions the literal token `REPLACE` 8 times — all as meta-references in backtick-quoted prose discussing how the template works. A naive `grep REPLACE` would false-positive on this doc itself. Proposed detection rule: flag `REPLACE` only when it appears (a) outside backtick-spans, AND (b) in section-content position — meaning either at the start of a line as the entire bullet/paragraph (`REPLACE: state the problem in 2-5 sentences`), or inside a fenced code block as that block's primary content. Backtick-quoted `\`REPLACE\`` and prose like "tokens marked REPLACE" do NOT trigger. The wrapper's regex needs a small parser, not a one-liner.

When all open questions are resolved (or explicitly deferred with rationale), change `status: draft` to `status: in-review` in the frontmatter and run the audit.

---

## Appendix — strip list from gstack's plan-eng-review.md (1634 lines)

**Keep (the actual review logic, ~250 lines worth):**
- Step 0: Scope Challenge
- Section 1 — Architecture review
- Section 2 — Code quality review
- Section 3 — Test review + E2E Test Decision Matrix + REGRESSION RULE
- Section 4 — Performance review
- "NOT in scope" / "What already exists" sections
- Diagrams subsection — the Stale Diagram Audit
- Failure modes
- Worktree parallelization strategy
- Confidence Calibration (from the Voice section — composes with CLAUDE.md Rule 6)

**Strip (gstack-specific infrastructure):**
- Preamble + AskUserQuestion Format + Artifacts Sync (gstack session bootstrap; we have `/sitrep`)
- Model-Specific Behavioral Patch (claude)
- Voice (full) + Writing Style + Question Tuning
- gstack's Telemetry binary (`gstack-telemetry-log`); we write our own JSONL directly
- Plan Status Footer
- Outside Voice (`codex exec` integration); we already do codex review separately
- `gstack-review-log` JSONL persistence; we replace with `~/.inc/projects/<slug>/telemetry.jsonl`
- Restore-point in gstack's `~/.gstack/...` path; we replace with `~/.inc/projects/<slug>/restore/`
- Test Plan Artifact at `~/.gstack/...`; folded into our Verification subsection per Week 3a codex revision
- Cross-references to `/canary`, `/qa`, `/ship`, `gbrain`
- Operational Self-Improvement + Retrospective Learning + Prior Learnings DB reads

Net: lift ~15% of gstack's file as the structural pattern; build our own infrastructure for telemetry + restore points sitting on `~/.inc/projects/<slug>/`.
