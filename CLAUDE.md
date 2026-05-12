# claude-agents — operating rules

This file is auto-loaded by Claude Code at session start. It is **deliberately minimal**: every rule has earned its place by closing a failure mode observed in this repo. Other discipline (codex-review-before-merge, coverage gates, ETHOS philosophy) lives elsewhere and gets promoted into this file only if its absence costs real time.

The current scope is informed by the gstack-borrow review — see `research/gstack-borrow-2026-05-11.md`.

---

## Rule 1 — Session bootstrap

On session start, **run or offer `/sitrep`** before doing other work. `/sitrep` reads `STATUS.md` + Linear + open PRs and surfaces "where you are, what's next, what's blocked on you." If the user's first message is an explicit task that bypasses bootstrap, do the task — but still surface a one-line orientation ("on branch X for MIT-Y; next was Z") from `STATUS.md` if it's present.

When work concludes, update `STATUS.md` (active branch, active PR, next command, last_verified_state). The schema lives at `skills/sitrep/docs/status-schema.md`.

## Rule 2 — Specialist routing

When the user's request matches a specialist agent's domain, **route to it via the Agent tool**. Do not redo work specialists exist to handle. When in doubt, route. The roster is the `agent.manifest.yaml` at the repo root, surfaced per-project by the `/staff` skill.

Specialists own depth. Skills own procedure. If a procedure is needed (codex review, plan review, design-doc creation), invoke the skill via the Skill tool. If a domain is needed (Swift backend, GPU, security audit), spawn the agent.

## Rule 3 — Linear-as-inbox

Linear is the queue and the history. The **inbox** is anything assigned to the user, any open PR awaiting their review, and any design doc flagged for review. `/sitrep` surfaces all three. Agents that produce review-worthy artifacts should create or update Linear items assigned back to the user (with a link), not leave them in chat or as wandering files.

When the user asks "what's on my plate" or "what needs my attention," go to Linear (via `sitrep-linear inbox`) and open PRs (via `gh pr list --search 'review-requested:@me'`), not to a chat-history reconstruction.

## Rule 4 — Break down non-trivial work before doing it

When the user **plans or queues new work** that is more than a one-line fix — phrases like "let's build", "we should ship", "I want to start on", "how do we break this down" — **invoke `/work-breakdown`** before writing code. The skill classifies size (S/M/L/XL), creates the right Linear artifacts (issue / project + issues / initiative + projects), recommends specialist agents to bring in, and names the required planning gates.

Do **not** invoke when the user is asking for immediate execution of an already-scoped change ("fix this", "implement X now", "just do it"). The trigger is *planning intent*, not size alone.

If unsure whether to fire, ask one clarifying question: "is this one PR or should we break it down?"

## Rule 5 — Surface conflicts, don't average them

When two parts of the system disagree — two existing code patterns, two specialist agents (PM vs tech-lead), codex feedback vs your own analysis, a doc vs the code — **pick one explicitly and say why**. Do not blend them. Average behavior that satisfies both is the worst behavior: the conflict stays hidden and the codebase grows incoherent.

The right move when two patterns contradict:
1. State both positions in one sentence each.
2. Pick one (usually: more recent, more tested, or matches the explicit user preference if there is one).
3. Flag the other as a follow-up — a Linear issue, a `decisions/` entry, or at minimum a line in the next commit message.

When **specialists** disagree (PM says X, tech-lead says Y), surface the disagreement to the user; do not silently pick one. User Sovereignty applies — AI surfaces, human decides.

## Rule 6 — Fail loud

Default to surfacing uncertainty, not hiding it. Specifically:

- **"Completed"** is wrong if anything was silently skipped, deferred, or stubbed. Name what was skipped and why.
- **"Tests pass"** is wrong if any tests were skipped, xfail'd, or removed. Report the skip count.
- **"Works"** is wrong if you did not verify the edge case the user asked about. Name the verified path and the unverified one.
- **"Migration ran"** is wrong if records hit constraint violations and were silently dropped. Always report a count.

When you cannot verify something worked, **say so explicitly in the same sentence as the claim of success**. Burying caveats in a long paragraph is functionally the same as silent failure — the user reads "done" and moves on.

This rule has teeth because codex review caught silent-skip behavior twice during Week 1 of the gstack-borrow initiative. Promoting it from "we happen to catch this" to "expected default."

---

## Defer (not in this CLAUDE.md, yet)

The following are explicitly NOT enforced by this CLAUDE.md. Promote them only if their absence is observed to cost time:

- Codex review × 3 rounds per PR (currently done by convention; not a CLAUDE.md rule yet).
- 80% test coverage gate (project-specific; lives in `Makefile` for repos that need it).
- Boil-the-lake stance (procedural completeness vs feature scope — see handoff for the nuanced version).
- ETHOS.md cultural principles.

These may be promoted in a later week of the gstack-borrow initiative if they prove load-bearing.

## Pointers

- **Session-state contract:** `STATUS.md` at this repo's root. Schema at `skills/sitrep/docs/status-schema.md`.
- **Agent roster:** `agent.manifest.yaml` (top-level). Per-project staffing: `/staff` skill.
- **Active initiative:** gstack-borrow ([Linear](https://linear.app/mitzoku/initiative/gstack-borrow-4e2936810b96)). Handoff at `research/gstack-borrow-2026-05-11.md`.
