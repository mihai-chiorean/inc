# Skill catalog

A one-page reference of every skill in the `inc` repo. Read top-to-bottom for orientation; jump to any entry to find a fixed set of fields (purpose, when to fire, reads, writes, wrapper, composes-with, link to SKILL.md). This catalog has two parts: **workflow skills** (built and shipping — the ones that actually run the day-to-day procedure: orient, break down, design, review, ship) and **domain / reference skills** (advisory bodies of knowledge loaded by Claude Code when a topic matches, mostly Swift- and infra-flavored). For onboarding, pair this page with [getting-started/workflow.md](../getting-started/workflow.md) (day-in-the-life walkthrough) and [getting-started/bootstrap.md](../getting-started/bootstrap.md) (machine + per-project setup).

The workflow skills are listed first in the order they typically fire in a real session: orient (`/sitrep`), staff the project (`/staff`), break down the work (`/work-breakdown`), scaffold a design doc (`/design-doc`), audit it (`/plan-eng-review`), pressure-test (`/plan-ceo-review`, `/plan-devex-review`, `/office-hours`), and periodically tune the roster (`/workflow-optimizer`). Domain skills follow alphabetically — most are purely advisory (read SKILL.md + reference files, emit guidance). A handful — `/project-management`, `/commit-pr-etiquette`, `/linear`, `/docs-site` — directly drive external CLIs (Linear, gh, mkdocs) and can mutate state through them; their per-skill entries name that explicitly.

---

## Workflow skills (built and shipping)

### /sitrep
**One-line purpose:** Session bootstrap and operational landing page. Run at session start (or on demand) to surface "where you are, what's next, and what's blocked on you" for the current project. Reads STATUS.md, Linear (assigned-to-you), GitHub (PRs awaiting your review, your open PRs), and recent commits. Writes back updates to STATUS.md.
**When to fire:** Session start (per CLAUDE.md rule 1); user says "sitrep", "where am I", "what's the status", "what's next"; after resolving a blocker or finishing a PR.
**Reads:** `STATUS.md` at project root; Linear (issues assigned to user, optional flagged docs); GitHub (review-requested PRs, own open PRs, branch-specific PR); `git status` / `git log` / `git branch`.
**Writes:** `STATUS.md` — diff-update of YAML frontmatter (active branch / PR / Linear issue) and the four body sections (current objective, what's next, open items, decisions log).
**Wrapper:** `sitrep-linear` (`skills/sitrep/bin/sitrep-linear`, symlinked to `~/.local/bin/sitrep-linear`) — hides Linear CLI v1/v2 differences and team-key resolution.
**Composes with:** Read upstream of every other workflow skill (its STATUS.md is the contract); [`/work-breakdown`](../../skills/work-breakdown/SKILL.md) refers back to `/sitrep` Step 6's diff-update pattern.
**SKILL.md:** [skills/sitrep/SKILL.md](../../skills/sitrep/SKILL.md)

### /staff
**One-line purpose:** Per-project agent staffing for Claude Code. Use when a project needs a curated subset of agents from the HR repo (`inc`) instead of loading all user-scope agents, when re-syncing project-level `.claude/agents/` after the HR repo has been updated, when adding or removing an agent from a project, or when inspecting whether staffed agents are drifting from HR HEAD. Operates on `.claude/staff/` for state and `.claude/agents/` for generated agent files Claude Code loads.
**When to fire:** "staff this project" / "what agents should this project use"; after the HR repo (`inc`) gets updated; adding or removing an agent; checking for drift.
**Reads:** HR repo agent manifest; project's `CLAUDE.md` / `README` / `AGENTS.md` for hint matches; `.claude/staff/lock.yaml`; `.claude/staff/config.yaml`; `.claude/staff/overlays/<id>.md`; HR HEAD commit.
**Writes:** `.claude/agents/<id>.md` (generated agent files Claude Code loads); `.claude/staff/lock.yaml` (lockfile with HR commit + manifest hash); preserves project-owned overlays.
**Wrapper:** `staff` CLI (`skills/staff/bin/staff`, symlinked onto `$PATH`) with subcommands `suggest`, `apply`, `status`, `add`, `remove`, `audit`, `sync`.
**Composes with:** [`/workflow-optimizer`](../../skills/workflow-optimizer/SKILL.md) consumes `staff audit --json` for layers 2/3 of its roster report.
**SKILL.md:** [skills/staff/SKILL.md](../../skills/staff/SKILL.md)

### /work-breakdown
**One-line purpose:** Classify an idea by size (S/M/L/XL) and break it down into Linear artifacts at the right granularity — issue / project + issues / initiative + projects + issues / multi-repo coordination. Recommends specialist agents (PM, tech-lead, TPM) and planning gates (design-doc, plan-eng-review). Adoption bridge for the work-breakdown procedure that currently lives in user's head. Adapted from gstack's `/autoplan` but explicitly narrower: classification + Linear orchestration only.
**When to fire:** "let's build X" / "we should X" when X is non-trivial; "how do we break this down"; "this is going to be big"; ask visibly spans multiple files, areas, or repos.
**Reads:** Linear (existing initiatives, projects, issues for context); `STATUS.md` for current project context; user clarification on ambiguous scope.
**Writes:** Linear artifacts via the `linear` CLI — 1 issue (S), 1 project + N issues (M), 1 initiative + M projects + N issues (L), or initiative(s) + per-repo projects + coordination doc (XL). Recommends design-doc / plan-eng-review gates by classification.
**Wrapper:** none — invokes the `linear` CLI directly. (May extend `sitrep-linear` on the read side if needed.)
**Composes with:** [`/sitrep`](../../skills/sitrep/SKILL.md) (procedural counterpart — sitrep orients, work-breakdown plans); recommends [`/design-doc`](../../skills/design-doc/SKILL.md) gate at M+; recommends [`/plan-eng-review`](../../skills/plan-eng-review/SKILL.md) gate at M+ once design-doc exists; links to [`/linear`](../../skills/linear/SKILL.md) for CLI reference.
**SKILL.md:** [skills/work-breakdown/SKILL.md](../../skills/work-breakdown/SKILL.md)

### /design-doc
**One-line purpose:** Scaffold a design doc with three mandatory diagram sections (user-flow + state-machine + data-flow) plus problem, goals/non-goals, implementation alternatives, failure modes, and open questions. Writes the doc to `decisions/NNNN-<slug>.md` by default; user can override the path. After scaffolding, the user iterates on content — this skill does not generate the diagrams or fill in the sections. This skill creates; audit / hard-gate is the job of `plan-eng-review`.
**When to fire:** "design doc" / "let me write a design doc" / "scaffold a design doc for X" / "/design-doc"; any time `/work-breakdown` recommends a design-doc gate (M+ classification); proactively when an L or XL ask is about to start coding without a design doc on record.
**Reads:** `STATUS.md` for default Linear issue / context; the template at `skills/design-doc/templates/design-doc.md.tmpl`; existing `decisions/` directory to compute next ADR number.
**Writes:** `decisions/NNNN-<slug>.md` by default (or user-overridden path) — a fully-stubbed design doc with all required sections. Refuses to overwrite an existing file without `--force`.
**Wrapper:** `design-doc-scaffold` (`skills/design-doc/bin/design-doc-scaffold`, symlinked to `~/.local/bin/design-doc-scaffold`) — handles path resolution, template substitution, write.
**Composes with:** Satisfies the design-doc gate recommended by [`/work-breakdown`](../../skills/work-breakdown/SKILL.md); produces the input audited by [`/plan-eng-review`](../../skills/plan-eng-review/SKILL.md); shares the side-quest test with `/work-breakdown` Step 7.
**SKILL.md:** [skills/design-doc/SKILL.md](../../skills/design-doc/SKILL.md)

### /plan-eng-review
**One-line purpose:** Audit a design doc. Mechanical checks (8 required sections present, no REPLACE stubs, 3 diagrams non-stub, failure-modes table populated, open questions populated) plus a qualitative pass (architecture coherence, test coverage diagram, failure-mode critical-gap registry, stale-diagram audit, confidence calibration). On PASS, mutates the doc's frontmatter `status: draft → accepted` and writes telemetry + restore-point. Adapted from gstack's plan-eng-review.md (stripped of session-bootstrap plumbing, telemetry binary, outside-voice subagent, and gstack-specific filesystem layout).
**When to fire:** "audit this design doc" / "review this plan" / "is decisions/<file> ready" / "/plan-eng-review"; when `/work-breakdown` recommends the eng-review gate (M+ classification with design-doc completed); when a PR contains a new or substantially changed design doc.
**Reads:** The target design doc (`decisions/NNNN-<slug>.md` or override); referenced code files (for stale-diagram audit); `decisions/0001-plan-eng-review-lift.md` (spec for both layers).
**Writes:** On PASS — mutates the design doc's frontmatter (`status: draft → accepted`), writes telemetry, snapshots a restore point. On FAIL — no mutation; surfaces gap list.
**Wrapper:** `plan-eng-review-audit` (Python; `skills/plan-eng-review/bin/plan-eng-review-audit`, symlinked to `~/.local/bin/plan-eng-review-audit`) — handles all mechanical checks via `--mechanical-only`. Exit codes 0 (pass), 1 (missing file), 2 (frontmatter / illegal transition), 3 (mechanical fail).
**Composes with:** Hard-gates docs produced by [`/design-doc`](../../skills/design-doc/SKILL.md); fires when [`/work-breakdown`](../../skills/work-breakdown/SKILL.md) flags an M+ gate; the qualitative review reuses the side-quest test from `/work-breakdown` Step 7.
**SKILL.md:** [skills/plan-eng-review/SKILL.md](../../skills/plan-eng-review/SKILL.md)

### /plan-ceo-review
**One-line purpose:** Rigorous plan/strategy review via CEO cognitive patterns + Prime Directives + Implementation Alternatives protocol. Use when the user has a plan or strategy document to review, asks "review my plan" / "critique this strategy" / "is this a good approach", invokes `/plan-ceo-review`, or wants to pressure-test an architecture or roadmap decision before committing. Adapted from Garry Tan gstack plan-ceo-review (MIT).
**When to fire:** "review my plan" / "critique this strategy" / "is this a good approach" / "/plan-ceo-review"; pressure-testing an architecture or roadmap decision before commit.
**Reads:** The plan or strategy document supplied by the user; whatever surrounding context the user references.
**Writes:** Nothing — review-only. **HARD GATE:** no code changes, no implementation. Produces a written critique applying the nine Prime Directives and (per chosen mode) scope expansion / hold / reduction.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** Standalone, complementary to [`/plan-eng-review`](../../skills/plan-eng-review/SKILL.md) (eng-review is mechanical+qualitative on design docs; ceo-review is strategic on plans) and [`/plan-devex-review`](../../skills/plan-devex-review/SKILL.md) (DX-flavored variant of the same review pattern).
**SKILL.md:** [skills/plan-ceo-review/SKILL.md](../../skills/plan-ceo-review/SKILL.md)

### /plan-devex-review
**One-line purpose:** Rigorous developer-experience plan review. Persona mapping, competitive benchmarking, magical-moment design, friction mapping. Use when reviewing a plan that involves a developer-facing surface (API, CLI, SDK, library, framework, docs, platform), asking "review this API" / "how is the DX" / "would a developer like this", invoking `/plan-devex-review`, or assessing a product's developer experience against a persona. Adapted from Garry Tan gstack plan-devex-review (MIT).
**When to fire:** Plan involves a developer-facing surface (API, CLI, SDK, library, framework, docs, platform); "review this API" / "how is the DX" / "would a developer like this"; "/plan-devex-review".
**Reads:** The plan / API / CLI / SDK / docs surface under review; competitive references named by the user; named persona context.
**Writes:** Nothing — review-only. **HARD GATE:** no code changes. Produces an opinionated DX review with specific friction points, magical-moment proposals, and TTHW (time-to-hello-world) gaps mapped against a named persona.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** Sibling of [`/plan-ceo-review`](../../skills/plan-ceo-review/SKILL.md) — both pressure-test plans with different lenses; can run alongside [`/plan-eng-review`](../../skills/plan-eng-review/SKILL.md) on design docs that ship a developer-facing surface.
**SKILL.md:** [skills/plan-devex-review/SKILL.md](../../skills/plan-devex-review/SKILL.md)

### /office-hours
**One-line purpose:** Rigorous idea interrogation via Six Forcing Questions. Use when the user describes a new product/startup idea, asks "help me think through this" / "is this worth building" / "brainstorm this", wants to validate a concept before writing code, or invokes `/office-hours`. Produces a design doc; does NOT write code. Adapted from Garry Tan gstack office-hours (MIT).
**When to fire:** New product / startup idea described; "help me think through this" / "is this worth building" / "brainstorm this" / "/office-hours"; concept validation before any code.
**Reads:** The user's pitch / idea / problem statement; user answers to the Six Forcing Questions; whatever evidence the user can produce (real users, real behavior, real money).
**Writes:** A refined problem statement or design doc as output. **HARD GATE:** no code, no scaffolding, no implementation action. Mode-dependent (startup / intrapreneurship / side-project / pressure-test-existing-plan).
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** Upstream of [`/design-doc`](../../skills/design-doc/SKILL.md) (its output is a candidate design doc); complementary to [`/plan-ceo-review`](../../skills/plan-ceo-review/SKILL.md) (office-hours interrogates the problem; plan-ceo-review pressure-tests the solution).
**SKILL.md:** [skills/office-hours/SKILL.md](../../skills/office-hours/SKILL.md)

### /workflow-optimizer
**One-line purpose:** Periodic ergonomics review of the agent roster. Use when the user wants to assess whether the agent setup is serving them well, when `/workflow-optimizer` or "review my agent workflow" is invoked, when deciding which agents to retire / narrow / split / merge based on actual usage and friction, or before a major restructure of the roster (rename pass, scope refresh, etc.). Pairs with `/staff audit` (project-side health), agent-eval-engineer (output quality), and hiring-manager (roster shape decisions). Produces a written report with named recommendations; never auto-deletes anything.
**When to fire:** Quarterly cadence; after meaningful roster work (new agents, large rename pass, codex review of role boundaries); when something specific feels off; before pairing with `/hiring-manager` for a restructure.
**Reads:** HR repo `git log --since="3 months ago"` on agent dirs; `staff audit --json` (per-project staffing + aggregate usage + retirement candidates); user self-reflection prompts on handoff friction.
**Writes:** A markdown report at `~/workspace/inc/reports/workflow-review-<date>.md` — roster health summary, friction patterns, description-router signals, per-agent recommendations (retire / narrow / split / merge / leave-alone), open questions. Never auto-deletes agents.
**Wrapper:** none — pure procedural SKILL.md (consumes `staff audit --json`).
**Composes with:** [`/staff`](../../skills/staff/SKILL.md) (consumes `staff audit --json` for layers 2/3); explicitly distinct from project-side `/staff audit`, task-graded agent-eval-engineer, and roster-decision `/hiring-manager`.
**SKILL.md:** [skills/workflow-optimizer/SKILL.md](../../skills/workflow-optimizer/SKILL.md)

---

## Domain & reference skills

External-reference material loaded when a topic matches. Most are purely advisory: they read their own `SKILL.md` plus reference files, and emit guidance. A handful (`/project-management`, `/commit-pr-etiquette`, `/linear`, `/docs-site`) drive external CLIs and can mutate state through those — their per-skill entries call that out.

### /bay-value-hunter
**One-line purpose:** Bay Area residential real-estate underwriting playbook — San Francisco, Berkeley, Albany. Per-city profiles for permit sources, hazard patterns, and rent-control context. Produces buy targets, rehab ranges, ARV estimates, and pursue/monitor/pass verdicts — not pretty-home shopping.
**When to fire:** Evaluating a specific listing; hunting fixer-uppers / stale listings / estate or probate sales; ranking multiple candidates across cities; stress-testing a deal before making an offer; "/bay-value-hunter".
**Reads:** `SKILL.md` and listing data supplied by the user (MLS, photos, permits, neighborhood).
**Writes:** Nothing — advisory only. **HARD GATE:** no pretty-home commentary; every output produces an as-is value estimate, buy target, rehab scope, ARV range, and verdict (or names the missing data).
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** standalone.
**SKILL.md:** [skills/bay-value-hunter/SKILL.md](../../skills/bay-value-hunter/SKILL.md)

### /commit-pr-etiquette
**One-line purpose:** Commit and PR etiquette guidelines. Use when creating git commits, writing commit messages, creating or updating pull requests, writing PR descriptions, or reviewing code or PRs.
**When to fire:** Creating commits / PRs; writing commit messages or PR descriptions; reviewing code or PRs.
**Reads:** `SKILL.md` (small — a short rules list).
**Writes:** Nothing — advisory only. Calls out Claude Code footers (e.g. `Co-Authored-By: ...`) in commits and PR descriptions for removal.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** standalone; advisory layer for any skill that creates commits or PRs.
**SKILL.md:** [skills/commit-pr-etiquette/SKILL.md](../../skills/commit-pr-etiquette/SKILL.md)

### /database-driver-design
**One-line purpose:** Expert guidance on building Swift database client libraries. Use when developers mention building a database driver, wire protocol implementation, connection pooling design, state machines for protocol handling, NIO channel handlers for databases, backpressure in result streaming, or actor executor alignment with NIO.
**When to fire:** Building a Swift database driver; wire protocol implementation; connection pooling; NIO channel handlers for databases; backpressure in result streaming; actor executor alignment with NIO.
**Reads:** `SKILL.md` and external Swift docs / patterns derived from valkey-swift and postgres-nio.
**Writes:** Nothing — advisory only.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** [`/swift-nio`](../../skills/swift-nio/SKILL.md), [`/swift-concurrency`](../../skills/swift-concurrency/SKILL.md), [`/swift-library-design`](../../skills/swift-library-design/SKILL.md), [`/postgres`](../../skills/postgres/SKILL.md), [`/valkey`](../../skills/valkey/SKILL.md).
**SKILL.md:** [skills/database-driver-design/SKILL.md](../../skills/database-driver-design/SKILL.md)

### /docs-site
**One-line purpose:** MkDocs documentation server location and usage. Use when creating documentation, writing guides or technical docs, asked to put docs somewhere, referencing the docs server, or adding new doc pages.
**When to fire:** Creating documentation; writing guides / technical docs; "put docs somewhere"; referencing the docs server; adding new doc pages.
**Reads:** `SKILL.md` (server location, nav structure, conventions).
**Writes:** Nothing directly; the skill points authors at `~/workspace/docs-site/docs/` and the MkDocs config — actual writes are by the author into that path.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** standalone; referenced anywhere docs need a home.
**SKILL.md:** [skills/docs-site/SKILL.md](../../skills/docs-site/SKILL.md)

### /hummingbird
**One-line purpose:** Expert guidance on Hummingbird 2 web framework. Use when developers mention Hummingbird/HB/Hummingbird 2, Swift web/HTTP servers, server-side Swift routing or middleware, building REST APIs in Swift, RequestContext or ChildRequestContext, HummingbirdAuth, HummingbirdWebSocket, HummingbirdFluent or database integration, or ResponseGenerator / EditedResponse.
**When to fire:** Hummingbird 2 / Swift HTTP servers; server-side Swift routing or middleware; REST APIs in Swift; HummingbirdAuth / WebSocket / Fluent; ResponseGenerator.
**Reads:** `SKILL.md` and `references/` patterns.
**Writes:** Nothing — advisory only.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** [`/swift`](../../skills/swift/SKILL.md), [`/swift-nio`](../../skills/swift-nio/SKILL.md), [`/swift-concurrency`](../../skills/swift-concurrency/SKILL.md).
**SKILL.md:** [skills/hummingbird/SKILL.md](../../skills/hummingbird/SKILL.md)

### /linear
**One-line purpose:** Linear CLI for issue tracking and project management. Use when developers mention Linear issues or tickets, issue tracking, MIT team issues, closing/updating/triaging tickets, linking PRs to issues, issue states, Linear projects, milestones/cycles/initiatives/labels/documents, or agent sessions.
**When to fire:** Linear issues / tickets / MIT team work; closing, updating, or triaging tickets; linking PRs to issues; Linear projects / milestones / cycles / initiatives / labels / documents / agent sessions.
**Reads:** `SKILL.md` (full CLI reference); Linear via the `linear` CLI v2.0.0.
**Writes:** Linear state — issues / projects / comments / states — via the `linear` CLI when invoked by an upstream skill. The skill itself is a reference; concrete writes happen at the caller's direction.
**Wrapper:** `linear` CLI (third-party, `@schpet/linear-cli` v2.0.0, symlinked at `~/.local/bin/linear`).
**Composes with:** [`/work-breakdown`](../../skills/work-breakdown/SKILL.md) (writes), [`/sitrep`](../../skills/sitrep/SKILL.md) (reads, via `sitrep-linear`), [`/project-management`](../../skills/project-management/SKILL.md).
**SKILL.md:** [skills/linear/SKILL.md](../../skills/linear/SKILL.md)

### /postgres
**One-line purpose:** Expert guidance on using PostgreSQL with Swift. Use when developers mention PostgreSQL or Postgres in Swift, postgres-nio library, SQL queries in Swift, PostgreSQL connection pooling, prepared statements, type-safe database access, bulk loading or COPY FROM, or PostgresClient/PostgresConnection.
**When to fire:** postgres-nio; SQL queries in Swift; connection pooling; prepared statements; bulk loading / COPY FROM; PostgresClient / PostgresConnection.
**Reads:** `SKILL.md` and `references/postgres-patterns.md`.
**Writes:** Nothing — advisory only.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** [`/swift-nio`](../../skills/swift-nio/SKILL.md), [`/swift-concurrency`](../../skills/swift-concurrency/SKILL.md), [`/database-driver-design`](../../skills/database-driver-design/SKILL.md).
**SKILL.md:** [skills/postgres/SKILL.md](../../skills/postgres/SKILL.md)

### /project-management
**One-line purpose:** Project management workflows and practices. Use when developers mention planning work or sprints, prioritizing tasks or issues, tracking progress on a project, standup or status updates, breaking down work into issues, roadmap or milestone planning, workload/capacity, or what to work on next.
**When to fire:** Planning work / sprints; prioritizing tasks or issues; tracking progress; standup or status updates; breaking down into issues; roadmap / milestone planning; "what should I work on next".
**Reads:** `SKILL.md`; Linear via the `linear` CLI; GitHub via `gh`; git branch / commit history.
**Writes:** Linear issues (via the `linear` CLI) when invoked; no direct file mutation.
**Wrapper:** none — uses the `linear` CLI and `gh` directly.
**Composes with:** [`/linear`](../../skills/linear/SKILL.md) (full CLI reference), [`/work-breakdown`](../../skills/work-breakdown/SKILL.md) (the procedural counterpart for non-trivial planning).
**SKILL.md:** [skills/project-management/SKILL.md](../../skills/project-management/SKILL.md)

### /swift
**One-line purpose:** Expert guidance on Swift best practices, patterns, and implementation. Use when developers mention Swift configuration or environment variables, swift-log or logging patterns, OpenTelemetry/swift-otel, Swift Testing framework or @Test macro, Foundation avoidance or cross-platform Swift, platform-specific code organization, Span or memory safety patterns, non-copyable types (~Copyable), or API design patterns / access modifiers.
**When to fire:** Swift config / env vars; swift-log; swift-otel / OpenTelemetry; Swift Testing / `@Test`; Foundation avoidance; cross-platform Swift; Span / memory safety; non-copyable types; API design / access modifiers.
**Reads:** `SKILL.md` and topic-specific files under `references/`.
**Writes:** Nothing — advisory only.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** [`/swift-nio`](../../skills/swift-nio/SKILL.md), [`/swift-concurrency`](../../skills/swift-concurrency/SKILL.md), [`/swift-library-design`](../../skills/swift-library-design/SKILL.md), [`/hummingbird`](../../skills/hummingbird/SKILL.md), [`/postgres`](../../skills/postgres/SKILL.md), [`/valkey`](../../skills/valkey/SKILL.md).
**SKILL.md:** [skills/swift/SKILL.md](../../skills/swift/SKILL.md)

### /swift-concurrency
**One-line purpose:** Expert guidance on Swift Concurrency best practices, patterns, and implementation. Use when developers mention Swift Concurrency / async/await / actors / tasks, structured concurrency, Swift 6 migration, data races, async/await refactors, `@MainActor` / Sendable / actor isolation, concurrent code architecture, concurrency linter warnings, AsyncSequence / AsyncStream / task groups, or `nonisolated` / `@preconcurrency` / `@unchecked Sendable`.
**When to fire:** async/await / actors / tasks; structured concurrency; Swift 6 migration; data races; refactor closures → async/await; `@MainActor` / Sendable / actor isolation; AsyncSequence / AsyncStream / task groups.
**Reads:** `SKILL.md` and `references/`.
**Writes:** Nothing — advisory only.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** [`/swift`](../../skills/swift/SKILL.md), [`/swift-nio`](../../skills/swift-nio/SKILL.md), [`/swift-library-design`](../../skills/swift-library-design/SKILL.md), [`/database-driver-design`](../../skills/database-driver-design/SKILL.md).
**SKILL.md:** [skills/swift-concurrency/SKILL.md](../../skills/swift-concurrency/SKILL.md)

### /swift-library-design
**One-line purpose:** Expert guidance on Swift library and framework design. Use when developers mention designing a Swift library or framework, public API design patterns, protocol-oriented architecture or associated types, result builders or DSL design, performance optimization for libraries, `@inlinable` / `@usableFromInline`, noncopyable types for APIs, progressive disclosure, or ResponseGenerator / builder patterns.
**When to fire:** Designing a Swift library or framework; public API design; protocol-oriented architecture / associated types; result builders / DSLs; `@inlinable` / `@usableFromInline`; noncopyable types; progressive disclosure.
**Reads:** `SKILL.md` and `references/`.
**Writes:** Nothing — advisory only.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** [`/swift`](../../skills/swift/SKILL.md), [`/swift-concurrency`](../../skills/swift-concurrency/SKILL.md), [`/swift-nio`](../../skills/swift-nio/SKILL.md), [`/database-driver-design`](../../skills/database-driver-design/SKILL.md), [`/hummingbird`](../../skills/hummingbird/SKILL.md).
**SKILL.md:** [skills/swift-library-design/SKILL.md](../../skills/swift-library-design/SKILL.md)

### /swift-nio
**One-line purpose:** Expert guidance on SwiftNIO best practices, patterns, and implementation. Use when developers mention SwiftNIO/NIO/ByteBuffer/Channel/ChannelPipeline/ChannelHandler/EventLoop/NIOAsyncChannel/NIOFileSystem, EventLoopFuture / ServerBootstrap / DatagramBootstrap, TCP/UDP servers or clients, ByteToMessageDecoder or wire protocol codecs, binary protocol parsing/serialization, or blocking-the-event-loop issues.
**When to fire:** SwiftNIO / ByteBuffer / Channel / Pipeline / EventLoop / NIOAsyncChannel; ServerBootstrap / DatagramBootstrap; TCP/UDP server or client; ByteToMessageDecoder; binary protocol parsing; event-loop blocking.
**Reads:** `SKILL.md` and `references/`.
**Writes:** Nothing — advisory only.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** [`/swift-concurrency`](../../skills/swift-concurrency/SKILL.md), [`/swift-library-design`](../../skills/swift-library-design/SKILL.md), [`/database-driver-design`](../../skills/database-driver-design/SKILL.md), [`/postgres`](../../skills/postgres/SKILL.md), [`/valkey`](../../skills/valkey/SKILL.md), [`/hummingbird`](../../skills/hummingbird/SKILL.md).
**SKILL.md:** [skills/swift-nio/SKILL.md](../../skills/swift-nio/SKILL.md)

### /valkey
**One-line purpose:** Expert guidance on using Valkey and Redis with Swift. Use when developers mention Valkey or Redis in Swift, valkey-swift library, RESP protocol or RESP3, Redis cluster routing or hash slots, pub/sub or subscriptions, Redis transactions or MULTI/EXEC, or caching with Redis.
**When to fire:** Valkey / Redis in Swift; valkey-swift; RESP / RESP3; cluster routing / hash slots; pub/sub; MULTI/EXEC transactions; Redis caching.
**Reads:** `SKILL.md` and `references/valkey-patterns.md`.
**Writes:** Nothing — advisory only.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** [`/swift-nio`](../../skills/swift-nio/SKILL.md), [`/swift-concurrency`](../../skills/swift-concurrency/SKILL.md), [`/database-driver-design`](../../skills/database-driver-design/SKILL.md).
**SKILL.md:** [skills/valkey/SKILL.md](../../skills/valkey/SKILL.md)

### /wendy
**One-line purpose:** Expert guidance on building and deploying apps to WendyOS edge devices. Use when developers mention Wendy/WendyOS, the wendy CLI, wendy.json or entitlements, deploying apps to edge devices, remote debugging Swift on ARM64, NVIDIA Jetson or Raspberry Pi apps, or cross-compiling Swift for ARM64.
**When to fire:** Wendy / WendyOS; wendy CLI; wendy.json / entitlements; deploying to edge devices; remote-debugging Swift on ARM64; NVIDIA Jetson or Raspberry Pi apps; cross-compiling Swift for ARM64.
**Reads:** `SKILL.md` and `references/wendy.json.md`.
**Writes:** Nothing — advisory only. (User-side `wendy` CLI invocations mutate device state, not this skill.)
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** [`/wendy-contributing`](../../skills/wendy-contributing/SKILL.md) (sibling for OS-internals work); [`/swift`](../../skills/swift/SKILL.md), [`/swift-concurrency`](../../skills/swift-concurrency/SKILL.md) for app-side Swift work.
**SKILL.md:** [skills/wendy/SKILL.md](../../skills/wendy/SKILL.md)

### /wendy-contributing
**One-line purpose:** Expert guidance on contributing to WendyOS: Yocto builds, agent internals, E2E testing, and system architecture. Use when developers mention building WendyOS images, meta-wendyos layers or bitbake, wendy-agent development or internals, containerd or nerdctl on WendyOS, E2E tests for wendy-agent, Yocto recipes or bbappend files, mDNS/Avahi service configuration, or device identity / UUID generation.
**When to fire:** Building WendyOS images; meta-wendyos layers / bitbake; wendy-agent internals; containerd / nerdctl on WendyOS; E2E tests for wendy-agent; Yocto recipes / bbappend; mDNS / Avahi; device identity / UUID generation.
**Reads:** `SKILL.md`, `references/yocto-meta-layers.md`, `references/system-internals.md`, `references/raspberry-pi.md`.
**Writes:** Nothing — advisory only.
**Wrapper:** none — pure procedural SKILL.md.
**Composes with:** [`/wendy`](../../skills/wendy/SKILL.md) (sibling for app-deployment side); [`/swift`](../../skills/swift/SKILL.md) for Swift-side wendy-agent work.
**SKILL.md:** [skills/wendy-contributing/SKILL.md](../../skills/wendy-contributing/SKILL.md)

---

## See also

- [getting-started/workflow.md](../getting-started/workflow.md) — day-in-the-life walkthrough showing how the workflow skills compose in a real session.
- [getting-started/bootstrap.md](../getting-started/bootstrap.md) — machine + per-project setup (symlinks, `~/.local/bin` wrappers, `.claude/staff/` config).
