---
doc_version: 1
title: "plan-eng-review skill lift (audits design docs)"
linear_issue: "MIT-348"
status: draft
created: "2026-05-12T06:00:49Z"
authors:
  - "Mihai Chiorean"
---

# plan-eng-review skill lift (audits design docs)

> **Status:** draft &middot; **Linear:** MIT-348 &middot; **Created:** 2026-05-12T06:00:49Z
>
> This doc is in draft. All sections must be filled before requesting review (see Week 3b `plan-eng-review` when it lands; until then audit by inspection against this template).

---

## 1. Problem

<!--
What is broken / missing / costly today? Make the pain concrete. One paragraph
or a short list. If the reader can't tell what the cost of doing nothing is,
this section is incomplete.
-->

REPLACE: state the problem in 2-5 sentences. Be specific about what hurts and who feels it.

## 2. Goals / Non-goals

### Goals
- REPLACE: what success looks like, in observable terms.
- REPLACE: another observable success criterion.

### Non-goals
- REPLACE: explicit thing this design will NOT do. Naming non-goals prevents scope creep later.
- REPLACE: another non-goal.

### Verification
How will we know the goals are met? Acceptance criteria, manual tests, automated tests, observed metrics, or a specific user-visible outcome. The failure-modes table (section 7) covers what's tested for bad inputs; this covers happy-path validation.

- REPLACE: how we'll verify goal 1 (e.g., manual test on X / automated test in Y / metric Z reaches threshold N).
- REPLACE: how we'll verify goal 2.

## 3. Implementation alternatives

At least **two** distinct approaches. Three is better for non-trivial work. (Pattern from gstack `plan-ceo-review` Step 0C-bis.)

### Approach A — REPLACE name
- **Summary:** 1-2 sentences.
- **Effort:** S / M / L / XL
- **Risk:** Low / Med / High
- **Pros:** REPLACE
- **Cons:** REPLACE
- **Reuses:** existing code / patterns leveraged.

### Approach B — REPLACE name (meaningfully different from A)
- **Summary:**
- **Effort:**
- **Risk:**
- **Pros:**
- **Cons:**
- **Reuses:**

### (Optional) Approach C
- ...

**Recommendation:** Approach REPLACE because REPLACE-one-line-reason.

## 4. User flow diagram (mandatory)

ASCII diagram of the user-visible flow. Happy path + at least one branch.

```text
REPLACE — example shape:

  [USER] starts X
     ↓
  [SYSTEM] does Y  ← (or branches to Z if condition C)
     ↓
  [USER] sees outcome W
```

## 5. State machine (mandatory if any stateful object)

If this design introduces a stateful object (process, session, record, request), diagram its states + transitions + invalid transitions explicitly. Mark this section "Not applicable — no stateful objects" only after confirming there really aren't any (most non-trivial features have at least one).

```text
REPLACE — example shape:

   ┌─────────┐  start   ┌──────────┐  succeed   ┌──────────┐
   │  init   │ ───────→ │  running │ ─────────→ │ complete │
   └─────────┘          └──────────┘            └──────────┘
                              │ fail
                              ↓
                        ┌──────────┐
                        │  failed  │
                        └──────────┘

   Invalid transitions: init → complete (must run first; enforced by ...)
```

## 6. Data flow diagram (mandatory)

Per gstack `plan-ceo-review` Prime Directive #3: **every** data flow has four paths. **Repeat the block below for each distinct source/sink pair in the design.** If there's truly only one data flow, state that explicitly so a reader doesn't wonder if you forgot the others.

### Flow A — REPLACE name (e.g., "user input → STATUS.md write")

```text
REPLACE — example shape:

  Happy path:
     [source] → validate → transform → [sink]

  Nil input:
     [source: null] → ??? → [behavior?]

  Empty / zero-length input:
     [source: []] → ??? → [behavior?]

  Upstream error:
     [source: error] → ??? → [behavior?]
```

For each non-happy path, state what catches it and what the user sees.

### Flow B — REPLACE name (or remove this block if only one flow)

Repeat the structure above.

## 7. Failure modes

Per gstack `plan-ceo-review` Prime Directive #2: every error has a name.

| Failure | Triggered by | Caught by | User sees | Tested? |
|---|---|---|---|---|
| REPLACE — `SpecificExceptionName` | REPLACE | REPLACE | REPLACE | yes / no / planned |
| ... | | | | |

Add as many rows as needed. **Silent failures are a critical defect.** If a failure can happen without anyone noticing, it must be either eliminated or made loud (per CLAUDE.md Rule 6).

## 8. Open questions

- REPLACE: a question the design does not yet answer, with a date by which it must be answered.
- REPLACE: another open question.

When all open questions are resolved, change `status: draft` to `status: in-review` in the frontmatter and trigger the audit (Week 3b `plan-eng-review` skill, when it ships).

---

## Appendix (optional)

Anything else that doesn't belong in sections 1-8 — links to prior art, raw notes, alternatives considered and rejected with reasons, performance estimates, security considerations beyond the failure-modes table, etc.
