# gstack "cognitive gears" vs our agent roster

**Date:** 2026-05-11
**Source:** https://github.com/garrytan/gstack (MIT-licensed)
**Local roster:** `/home/mihai/workspace/claude-agents/{product,project-management,engineering}/`

## 1. Role-to-agent mapping

gstack encodes specialization as *skills* the orchestrator invokes. The skills that act as "roles" cluster around the planning gauntlet (`/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/plan-devex-review`), the build/ship pipeline (`/qa`, `/review`, `/ship`, `/document-release`), and the standing modes (`/cso`, `/codex`, `/retro`, `/learn`).

| gstack role-skill | Closest agent of ours | Fit |
|---|---|---|
| `/plan-ceo-review` ("founder-mode … 10-star product, challenge premises") | `product/product-manager.md` | Strong on prioritization/scope-call; weaker on "dream big / scope-expansion" framing. PM is a *committed roadmap* role; CEO-review is upstream of that. |
| `/plan-eng-review` ("eng manager-mode … lock in architecture, edge cases, coverage") | `engineering/tech-lead.md` | Direct 1:1. Both are "review the design doc before code starts." |
| `/plan-design-review` + `/design-review` (visual/UX critique) | *no agent* | Gap. We have no `visual-designer` or `ux-reviewer`. |
| `/plan-devex-review` (APIs, CLIs, SDK ergonomics) | partially `engineering/tech-lead.md`, partially `engineering/go-engineer.md` (CLI ergonomics) | No dedicated DX-reviewer; coverage is incidental. |
| `/qa` (systematic QA, find-and-fix bugs) | `engineering/test-writer-fixer.md` | Close. test-writer-fixer is more unit/integration; gstack `/qa` is more E2E + bug iteration. |
| `/review` (pre-landing PR review) | `engineering/tech-lead.md` reviewing seams + `engineering/infra-reviewer.md` for IaC | Distributed across multiple agents; no single "PR review" gate. |
| `/ship` (merge, version, changelog, push, PR) | `project-management/release-engineer.md` | Close on rollout/rollback; gstack's `/ship` is lighter-weight (a single PR) where ours is launch-scale. |
| `/cso` (security audit, OWASP, STRIDE, supply chain) | `engineering/security-auditor.md` | Strong fit; see §4. |
| `/codex` (codex CLI wrapper) | invoked via Bash, no agent | See §4. |
| `/retro` (weekly retrospective) | *no agent* | Gap. `experiment-tracker` is per-experiment, not weekly. |
| `/learn` (cross-session learnings) | *no agent / handled by handoff docs* | Procedural gap, not a role gap. |
| `/autoplan` (pipelines the four `/plan-*-review` skills) | *no equivalent orchestrator* | Procedural gap. |

Our extras with no gstack equivalent: every domain specialist (`gpu-engineer`, `vision-engineer`, `embedded-linux`, `swift-backend`, `grpc-contracts`, `db-migration`, `ai-engineer`, `mobile-app-builder`, etc.). gstack has no concept of "this person is the GPU expert"; it expects the generalist plus the right skill-mode to cover it.

## 2. Granularity: which is sharper?

**Ours is more granular on the *execution* axis; gstack is more granular on the *planning* axis.**

We split execution along domains (GPU vs embedded vs Swift backend) and along the program lifecycle (PM frames WHY → TL frames HOW → TPM tracks WHEN → release-engineer rolls out). gstack collapses all of this into a generalist that switches "modes." See `product-manager.md` line 6 — "Pairs with `tech-lead` on any non-trivial feature through code-complete" — that handoff is structural; gstack's equivalent is a procedural sequence within one context.

gstack splits planning four ways (CEO / eng / design / devex) where we have effectively *two* gears (PM, TL). That is the sharper move for design and DX, which our roster genuinely under-covers.

**Verdict:** their planning taxonomy is sharper; our execution taxonomy is sharper. Neither is uniformly better. The right move is to copy planning gears as skills on top of our agent spine — already on the lift shortlist in `research/gstack-borrow-2026-05-11.md`.

## 3. Procedural switch vs structural switch

- **Skill = procedural switch.** Same context, instructions reshape behavior. Cheap to invoke, cheap to compose (`/autoplan` chains four). Cost: context-window pollution; previous mode bleeds into the next.
- **Agent = structural switch.** Fresh context, fresh tool allowlist, fresh persona. Clean separation. Cost: handoff friction (artifacts must be written down, not held in working memory) and per-invocation overhead.

For *reflexive* moves (codex review, PR review, ship) procedural wins on latency. For *deep, multi-step* moves with conflicting heuristics (security audit, infra review, design doc authorship) structural wins because the agent can't "forget it was supposed to be paranoid." Our roster bets correctly on structural for the expensive moves and should add procedural for the reflexive ones.

## 4. Concrete head-to-heads

**`/cso` vs `security-auditor`:** gstack's `/cso` is broader — secrets archaeology, dependency supply chain, CI/CD security, LLM/AI security, skill supply-chain scanning, OWASP, STRIDE, daily vs comprehensive modes. Ours (`engineering/security-auditor.md`) is sharper on mTLS / PKI / GCP / X.509 because those are real workloads in this lab. Not a gap — a deliberate specialization. We should *not* broaden security-auditor to match `/cso`; we should consider an *additional* `supply-chain-auditor` only if/when we add untrusted dependencies.

**`/codex` skill vs Bash-invoked codex:** gstack's `/codex` codifies three modes (review / challenge / consult) with session continuity. We use `codex exec` ad-hoc and inconsistently. This is a *procedure* gap, not a role gap. A `/codex` skill on top of our agents would standardize the three-rounds review pattern this hiring-manager already does informally.

**design-* skills:** gstack has `/plan-design-review`, `/design-review`, `/design-consultation`, `/design-html`, `/design-shotgun`. We have *zero* visual-design coverage. Honest read: this is genuinely outside scope for a robotics/CV lab. Web/UX polish is not a recurring workload here. **Not a gap to fill.**

## 5. Opinionated proposal

Two changes, in priority order:

1. **Add a `devex-reviewer` agent** (or fold the lens into `tech-lead`). We ship CLIs (`go-engineer` owns `lab-control`) and gRPC contracts. gstack's `/plan-devex-review` ("developer personas, magical moments, friction tracing") is a lens we currently do not apply. Lowest-cost option: extend `tech-lead.md` with a named "DX review mode" rather than a new agent — overlap with TL is >60%.

2. **Do NOT add a `visual-designer`, `ceo-reviewer`, or `qa-engineer` agent.** Visual design is out of scope. CEO-review is a planning *gear*, not a role — implement as a skill. `/qa` overlaps `test-writer-fixer` by >60% — extend, do not split.

**Verdict:** gstack's role taxonomy is not better than ours; it solves a different problem (one generalist with mode-switches vs. a roster of specialists). The genuinely transferable insight is the *planning gauntlet as a procedural pipeline* (`/autoplan`), not the role decomposition. Lift skills, not agents.
