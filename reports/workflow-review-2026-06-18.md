# Workflow review — 2026-06-18

Author: triggered by the Ziggy workspace consolidation session. /staff applied for the first time today; this report is the post-application ergonomics snapshot.

## TL;DR

- **HR repo: 59 agents** (after today's `llm-inference-engineer` addition).
- **Per-project staffing: ~1 project actually staffed** out of ~7+ scanned. Today's `~/workspace/ziggy/` is the first project with a `.claude/staff/lock.yaml` lockfile across the workspaces I audited. **Every other project shows `has_lockfile: false`.**
- **Friction pattern: /staff is suggested but not applied.** The audit's "suggested" lists across 5+ projects are healthy (6-12 matches each), but nothing converts those suggestions into lockfiles. This is the load-bearing signal.
- **Roster activity is concentrated in the last 3 months.** 24 commits to agent dirs since 2026-03; 4 commits in 2026-06. The roster is alive — but its consumers aren't (yet) using it via `/staff`.

## Roster health

### Recent HR edits (Layer 1 — 24 commits since 2026-03)

Themes:

1. **Canonical v3 shape sweep (MIT-415)** — 3 batches of rewrites covering engineering / product / design / marketing / ops / testing / bonus. Mass refactor toward consistency. Aspirational closings trimmed (commit `7f6e0ec` from `test-writer-fixer`). Indicates active discipline around description-as-router; rewrites were per-batch with codex review per batch.
2. **Strict YAML + validator gate (MIT-392)** — `a505a00 Strict YAML across all 57 agents + validator + CI gate`. Tightens the loader-tolerance ratchet. Coupled with manifest regen.
3. **Allowed-tools + output-format additions (MIT-431/432/433)** — three commits adding execution-shape fields to 15-21 agents at a time. Stewarding agent reliability beyond just description quality.
4. **Vision split (MIT-391)** — `cd828f7 Split vision-engineer into 3 lanes: vision / video-pipeline / video-analytics`. The kind of scope-drift correction this skill is designed to surface; it happened upstream via hiring-manager.
5. **Model bumps** — `d963df6 go-engineer: switch model from sonnet to opus`. Suggests ongoing per-agent capability calibration.
6. **Roster shape change** — `ef8bdd9 Roster refactor: studio shape -> product-company shape`. Significant structural change Q2.

**What's NOT in the log:** no retirements in the last 3 months. The roster grows; it doesn't shrink. (`MIT-377` adds `/staff promote` + `/staff rif` for retirement, but neither has been used yet on org-scope agents per the commit history.)

### Per-project staffing (Layer 2 — partial; full audit times out)

Audit ran via `staff audit --json` but **timed out at 60s** — each project incurs a `codex-cli` LLM call for hint matching, so 12+ projects × ~5-10s/each puts the full pass beyond a comfortable interactive budget. The partial data I extracted:

| Project | has_lockfile | suggested (count) | lock_staffed |
|---|---|---|---|
| DNSClient | false | 6 | 0 |
| TensorRT-LLM | false | 11 | 0 |
| clip-labeler | false | 7 | 0 |
| containerd-registry | false | 9 | 0 |
| deepstream-swift-detector | false | 12 | 0 |
| **ziggy (today)** | **true** | 12 → **10 after pruning** | **10** |

**Headline:** ~7+ workspaces scanned, exactly **1** has a lockfile. That's a major adoption gap.

### Aggregate usage (Layer 3 — partial)

Full retirement-candidate computation requires the complete audit. From the partial data, two soft signals:

- `performance-benchmarker` was suggested by 3 of the 5 scanned non-Ziggy projects (containerd-registry, deepstream-swift-detector, plus DNSClient). Its description over-fires on the keyword `benchmark`, but the actual scope (Web Vitals, mobile frame rates, React DevTools) is wrong for most of these projects. **Strong rot candidate** — matches the hiring-manager audit findings on Ziggy specifically.
- `frontend-developer` similarly over-fires (suggested for deepstream-swift-detector — a Jetson detector with no frontend).

The complete retirement-candidate list requires re-running the audit with a longer timeout OR a `--no-llm` fast mode that the current `staff audit` doesn't appear to support.

## Friction patterns

Four patterns surfaced during today's Ziggy consolidation session:

### 1. `/staff suggest --json` produces a DIFFERENT set than the text form

`staff suggest` (text) listed 12 agents including `go-engineer` and `tech-lead`. `staff suggest --json` piped to `staff apply --from-suggest` installed 12 agents but with `frontend-developer` and `gpu-engineer` swapped in instead. The discrepancy is invisible to a workflow that trusts the text suggest output as the source of truth.

**Root cause unclear.** Worth a bug investigation. Possibly the JSON includes lower-confidence matches the text view filters out, or the LLM call gives different output across invocations.

### 2. `/staff suggest`'s LLM step is interactive-hostile

Every project gets a `codex-cli` call. For a quick "what should I staff?" question, this latency (~10s per project) is fine. For `staff audit` across the workspace (12+ projects), it's 1-2 minutes — past the interactive comfort threshold and into "run it overnight or in a background tab" territory.

**Recommendation:** add a `--cached` or `--no-llm` mode to `staff audit` that only does hint-matching (not LLM reasoning), so the ergonomic-review use-case is sub-10-second.

### 3. Description-router gap: no agent owns the LLM-serving stack

Today's hiring-manager audit identified `llm-inference-engineer` as a real coverage gap (llama.cpp / GGUF quant / KV-cache tuning / systemd-managed inference). Was filled in this session — but the gap survived for the entire run-up to Ziggy production. **Surfacing this earlier could have happened if `/workflow-optimizer` had been run quarterly.**

### 4. Over-firing agents in suggest output

`api-tester` and `performance-benchmarker` matched on Ziggy via LLM reasoning that was over-broad. The hiring-manager rejection rationale was concrete (no REST surface for the former; Web Vitals scope for the latter). **The suggest LLM prompt may need an explicit "what this agent does NOT cover" injection** to prevent these.

## Description-router signals

| Agent | Signal | Evidence |
|---|---|---|
| `performance-benchmarker` | **Over-fires** broadly | Suggested for 3+ unrelated projects; declared scope is Web Vitals/mobile, not LLM perf |
| `frontend-developer` | **Over-fires** on backend/embedded projects | Suggested for deepstream-swift-detector (Jetson detector) |
| `api-tester` | **Over-fires** on anything HTTP-shaped | Suggested for Ziggy where the eval harness covers test needs |
| `go-engineer` | **Plausibly correct but under-utilized** | Owns lab-control but isn't in the lab-control workspace's lockfile (because lab-control doesn't have one) |
| `llm-inference-engineer` (NEW) | **Untested in router** | Just added; will need a quarter of suggest results to gauge if its keywords route correctly |

## Recommendations

| Agent / change | Action | Rationale |
|---|---|---|
| `performance-benchmarker` | **Narrow OR split** | Scope is mobile/Web Vitals. Either rename to make that explicit (`web-vitals-engineer`?) or split a new `llm-perf-engineer` for the actual GPU/serving perf work |
| `frontend-developer` | **Narrow** description | Filter on actual frontend markers (React, Vue, package.json frontend deps) — currently matches on too-generic terms |
| `api-tester` | **Narrow** description | Currently fires on any HTTP service. Should require REST contract / OpenAPI / Pact-shaped work |
| `/staff audit --no-llm` | **Build** | Sub-10-second cached pass for ergonomic reviews; LLM pass becomes opt-in |
| `/staff suggest` text-vs-JSON divergence | **Investigate** | Today's session was bitten by this. Likely a bug worth filing |
| Staff lab-control + nano-bot workspaces | **One-time apply** | Both are active workspaces with no lockfile; expected suggested rosters are well-defined |
| Quarterly `/workflow-optimizer` | **Calendar it** | Today's pass found 4 actionable patterns. Next pass 2026-09-18 |

## Open questions for Mihai (Layer 4 — TODO when convenient)

These are the reflection prompts the data can't answer. Pick them up when you have 10 minutes:

1. **Which agent did you most recently rephrase the prompt for?** (Signals scope-drift or description ambiguity. Today's session never had to rephrase, but the consolidation work was unusual — meta-work, not domain work.)
2. **Which handoff between agents cost you the most time recently?** Specifically: PM → tech-lead handoffs, tech-lead → specialist handoffs, codex-review-to-merge. Any one you'd flag?
3. **Which agent's output do you most often discard / redo manually?** (Discard rate is the strongest output-quality signal. If anyone, candidates would be agent-eval-engineer's reports — they're long.)
4. **Are there problems you keep solving WITHOUT an agent that maybe should be one?** Today's session surfaced one: the Ziggy workspace consolidation itself was meta-orchestration work without a clear specialist. `staffing-orchestrator` or similar?
5. **Are there agents you forgot existed when you should have invoked them?** Routing-failure signal. Cross-check against the 59-agent manifest.

Answer in line in this file (or tell me and I'll patch in your responses).

## Next pass

Calendar 2026-09-18 for the next quarterly review, OR fire on-demand if you observe any of:

- Three or more rephrases of the same agent prompt
- A specialist's recommendation getting overridden manually twice in a row
- A new gap surfacing via hiring-manager (today's `llm-inference-engineer` was the trigger for this pass)
- Roster grows by 5+ agents (we're at 59; next checkpoint 64)
