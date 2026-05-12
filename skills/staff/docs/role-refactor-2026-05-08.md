# Role Refactor: Studio Shape -> Product-Company Shape

**Status:** Phase 1 design (draft, awaiting Mihai sign-off).
**Date:** 2026-05-08.
**Scope:** `product/sprint-prioritizer`, `project-management/*`, `bonus/studio-coach`, `testing/workflow-optimizer`. Nothing else in the roster is touched.

## 1. Problem statement

The current project-management + product cluster was inherited from the contains-studio (creative-agency) frame. Four agents — `sprint-prioritizer`, `studio-producer`, `project-shipper`, `studio-coach` — and one orphan (`workflow-optimizer`) all carry overlapping language around "6-day cycles," "coordination," "process optimization," and "team health." When `/staff suggest` reads these descriptions to recommend a roster, it cannot reliably distinguish them, so it either picks several of them (bloat) or none of them (gap). A real product company doesn't have "studio producers"; it has PMs, TPMs, EMs, Tech Leads, and Release Engineers, and each one has a clean handoff to the others.

This refactor reshapes the cluster around that taxonomy without inflating the roster (constraint: ≤2 net-new agents).

## 2. Verdict per agent

| Agent | Verdict | One-line rationale |
|---|---|---|
| `sprint-prioritizer` | **Rename + expand** -> `product-manager` | Already owns prioritization/RICE/roadmap; lift "6-day cycle" framing, add discovery + decision-rationale framing. Stable ID changes; alias preserves lockfiles. |
| `studio-producer` | **Rename + narrow** -> `tpm` (Technical Program Manager) | Keep cross-team coordination, dependencies, risk surfacing, schedule. Remove "resource allocation" (-> EM) and "process optimization for its own sake" (-> retire). |
| `project-shipper` | **Rename + narrow** -> `release-engineer` | Already 70% release-process-shaped. Remove the GTM/marketing copy (that lives in `growth-hacker` and `app-store-optimizer`), keep release branches, rollouts, rollbacks, launch readiness, post-launch monitoring. |
| `experiment-tracker` | **Keep + tighten** | Real specialty (A/B tests, feature flags, statistical significance). Already scope-clarified vs `agent-eval-engineer`. Tighten authority: this agent *recommends* ship/kill via written readout; `product-manager` *decides*. Strip any current language implying it owns the final call. |
| `studio-coach` | **Retire** | Pure motivation/affirmation language. Doesn't survive contact with a single-engineer + agents setup. The useful sliver — "coordinating *agents* during multi-agent work" — is not what its description actually says, and what it says ("rallying," "championship coach," "psychological safety") is studio-cosplay, not a working contract. Cleaner to retire than to surgery. |
| `workflow-optimizer` | **Retire** | Overlaps TPM's bottleneck-detection AND `tool-evaluator`'s tool-integration analysis. The remaining slice ("human-AI handoff testing") is a research question, not a recurring role. |
| **NEW** `tech-lead` | **Add** | Owns the *feature-level* technical direction: writes design docs, picks implementation approach, sequences work, owns execution quality. Pulls in domain specialists (backend-architect, infra-reviewer, security-auditor, frontend-developer, gpu-engineer) for depth on their slice. PM's pair on any non-trivial feature. |
| **NEW** `eng-manager` | **Defer / open question** | Capacity, hiring, team-health. In a one-engineer + agents setup the "team health" half of EM is null. The "capacity allocation" half overlaps TPM. Recommend NOT adding in this refactor. See §6 Open Question 1. |

Net change: **+1 new agent** (`tech-lead`), **-2 retired** (`studio-coach`, `workflow-optimizer`), **3 renames** (`sprint-prioritizer` -> `product-manager`, `studio-producer` -> `tpm`, `project-shipper` -> `release-engineer`), **1 unchanged** (`experiment-tracker`). Roster size: -1 net.

## 3. Proposed roster after refactor

| Stable ID | Category | One-line scope |
|---|---|---|
| `product-manager` | product | Owns the WHY *and the decision*: roadmap, prioritization (RICE/Kano/JTBD), customer-discovery synthesis, definition-of-done from user value, final ship/kill calls. Pairs with `tech-lead` on feature framing. Treats research/discovery agents (`customer-interviewer`, `feedback-synthesizer`, `market-validator`, `idea-evaluator`, `trend-researcher`, `competitive-intel`) as inputs PM commissions and integrates — not as decision-makers. |
| `tech-lead` | engineering | Owns the HOW *for a feature*: writes the feature design doc, picks the implementation approach, sequences the work, owns technical execution quality. Pulls in domain specialists (`backend-architect`, `infra-reviewer`, `security-auditor`, `frontend-developer`, `gpu-engineer`, etc.) for deep review on their slice. Not language-specific. |
| `tpm` | project-management | Owns **program readiness** (pre-code-complete): cross-team dependency mapping, milestone/schedule tracking, cross-functional risk surfacing. Doesn't decide what to build or how. Hands off to `release-engineer` once a feature is code-complete. |
| `release-engineer` | project-management | Owns **operational readiness** (at ship time): release plan, code freeze, rollout strategy, gates, rollback drill, launch-day monitoring, incident-channel coordination. Picks up where `tpm` leaves off. |
| `experiment-tracker` | project-management | Owns **the evidence**: A/B test design, feature-flag instrumentation, statistical analysis, written readouts and recommendations. *Does not* make ship/kill decisions — that authority belongs to `product-manager`. |

Supporting product agents (unchanged): `customer-interviewer`, `market-validator`, `feedback-synthesizer`, `idea-evaluator`, `trend-researcher`, `competitive-intel`.

## 4. Aliases (stable-ID rename map)

These go into `agent.manifest.yaml` under each new entry's `aliases:` field, hand-edited before `generate-manifest.py` runs. Once added, they stay forever (per schema doc, lockfiles depend on them).

```yaml
product-manager:
  aliases: [sprint-prioritizer]
tpm:
  aliases: [studio-producer]
release-engineer:
  aliases: [project-shipper]
```

Retirements (`studio-coach`, `workflow-optimizer`): no alias needed — their entries are deleted from the manifest. Existing lockfiles that pinned them will fail to resolve on next `/staff sync`, which is the correct signal ("this agent went away; pick a replacement"). A `CHANGELOG` migration note will document this.

`experiment-tracker` and `tech-lead`: no aliases (one is unchanged; the other is brand-new).

## 5. PM + Tech Lead pairing pattern — where does it live?

Three options considered:

1. **In each agent's description.** Pro: the LLM router sees it. Con: duplicated text, drifts.
2. **In a separate playbook doc** (`skills/staff/docs/role-pairings.md`). Pro: single source of truth. Con: invisible to `/staff suggest`.
3. **One sentence in the description of both PM and TL, plus the playbook doc for the longer version.** Pro: router gets the signal, humans get the detail. Con: minor duplication.

**Recommendation: option 3.** Each of `product-manager` and `tech-lead` carries one sentence in its description: *"For non-trivial features, pairs with `tech-lead` (frames implementation) / `product-manager` (frames user value)."* The longer pairing playbook lives at `skills/staff/docs/role-pairings.md` and gets cross-linked from both agent files in their body sections. TPM and release-engineer don't get pairing language because they don't pair-by-default — they coordinate across many features.

## 6. Anti-scope statements (per role)

These go into each agent's description as a "NOT for" line. They exist for the LLM router, not for humans.

- **`product-manager` is NOT `tpm`** — PM decides what to build and why; TPM tracks when it ships and what's blocking it. PM does not run dependency maps; TPM does not run user-research synthesis.
- **`product-manager` is NOT `idea-evaluator`** — PM operates on a committed roadmap; idea-evaluator scores raw inbound ideas before they reach the roadmap.
- **`product-manager` is NOT `experiment-tracker`** — PM makes the ship/kill decision; experiment-tracker provides the readout and recommendation. PM owns the call; experiment-tracker owns the evidence.
- **`tech-lead` is NOT `backend-architect`** — TL writes the feature-level design doc, sequences the work, and owns execution quality across the whole feature; backend-architect goes deep on a specific API/DB/service slice when TL pulls them in. TL is the generalist; backend-architect is the specialist.
- **`tech-lead` is NOT `eng-manager`** — TL owns technical approach; EM (if added later) would own people, capacity, growth. TL does not run 1:1s or hiring decisions.
- **`tech-lead` is NOT `infra-reviewer`** — TL reviews application architecture and feature design; infra-reviewer reviews GCP/Terraform plans specifically. TL pulls infra-reviewer in when the feature touches infrastructure; doesn't replace them.
- **`tech-lead` is NOT a domain specialist** — TL does not replace `frontend-developer`, `gpu-engineer`, `security-auditor`, `swift-backend`, `vision-engineer`, etc. TL owns the *shape* of the feature; specialists own the *depth* of their domain.
- **`tpm` is NOT `product-manager`** — TPM tracks the schedule of decisions PM has already made. TPM does not change priorities; TPM surfaces when priorities can no longer be met and asks PM to re-prioritize.
- **`tpm` is NOT `release-engineer`** — TPM owns *program* readiness up to code-complete (deps, dates, cross-team risk). Release-engineer owns *operational* readiness from code-complete through rollout. The handoff is explicit, not overlapping.
- **`release-engineer` is NOT `devops-automator`** — release-engineer owns the *process* of shipping a specific release (rollout strategy, freeze, hotfix, rollback drill); devops-automator builds the underlying CI/CD and infrastructure plumbing.
- **`release-engineer` is NOT `growth-hacker` / `app-store-optimizer`** — release-engineer owns engineering-side launch readiness; GTM/positioning copy lives in marketing agents.
- **`experiment-tracker` is NOT `agent-eval-engineer`** — already documented. Experiments = real users + feature flags. Evals = judge-graded agent quality.
- **`experiment-tracker` is NOT `product-manager`** — experiment-tracker recommends; PM decides. The readout names a winner; PM signs the ship-or-kill.

## 7. Open questions for Mihai

1. **Is `eng-manager` worth adding for a single-engineer setup?** My recommendation is no for this refactor. The "team health / 1:1s / hiring" half of EM has no surface area when the team is one human and a roster of agents. The "capacity allocation across people" half belongs to TPM here. If Mihai disagrees, EM gets added in phase 2 with explicit scope: "agent-roster capacity decisions, hiring-manager *invocations*, project-level allocation." That makes it a dispatcher in front of `hiring-manager` + `tpm`, which is probably too thin to justify.
2. **Does retiring `studio-coach` lose anything real?** I don't think so — its useful sliver is *agent coordination during multi-agent work*, but in practice when multiple agents are running, the orchestrator does that, and `tpm` covers the cross-thread tracking explicitly. If Mihai wants to keep a thin "agent-coordinator" alive, propose: 1-paragraph description, model: sonnet, explicitly scoped to "I sequence multi-agent runs and surface conflicts between their outputs," and drop everything that mentions motivation, championship sports, or `🏆`. Otherwise, retire.
3. **Does retiring `workflow-optimizer` lose anything real?** Possibly — the "measure how long human-AI handoffs take" angle is genuinely useful for tuning the agent skills themselves. Suggest: fold the measurement angle into `tool-evaluator`'s description (one example block) rather than keep a whole agent.
4. **Should `tech-lead` be in `engineering/` or `project-management/`?** I put it in engineering because that's where its work artifacts land (design docs, ADRs, code-shape decisions). PM goes in `product/` for the same reason.
5. **Does `tpm` belong in `project-management/` or get its own home?** Keeping the folder makes sense; the folder name is fine even if its contents are now product-company-shaped instead of studio-shaped.

## 7b. Series-B roles considered and rejected (for now)

Codex review flagged five additional roles a real Series-B SaaS company would have. Each was considered and rejected for *this* refactor under the ≤2-new-agent constraint, with notes on whether they're real future gaps or already covered:

- **`product-designer` / `ux-designer`** — genuine gap, but deferred. The design folder already has `ui-designer`, `ux-researcher`, `whimsy-injector`, and `brand-guardian`. Recommend a separate audit of the design cluster rather than smuggling a sixth design role into a project-management refactor. Marked as a real follow-up.
- **`product-analyst` / `data-analyst`** — partially covered by `analytics-reporter` (studio-operations). Real gap on instrumentation/metric-taxonomy/funnel work, but it's adjacent to this refactor, not part of it.
- **`customer-success` / `solutions-consultant`** — `feedback-synthesizer` covers the inbound signal side; the proactive customer-relationship side is a real gap, but adding it now turns a 5-role product cluster into 7+ roles and breaks the constraint.
- **`sales-engineer` / `solutions-architect`** — out of scope; this is a single-engineer personal repo, not a B2B SaaS company. Mark as "if this repo ever gets used by a real B2B founder, revisit."
- **`security/compliance reviewer`** — already exists as `security-auditor` (engineering); SOC2/privacy/compliance specifically is uncovered. Real gap, but again, separate audit.

Decision: this refactor stays focused on the studio→product-company *re-shape* of existing agents. The "what new agents do we need overall" question is a separate audit, owed but not done here.

## 8. Migration / changelog plan (for phase 2)

A single `CHANGELOG.md` entry under "2026-05-08 — Roster refactor: studio -> product-company shape," covering:

- 3 renames (with stable-ID alias entries listed)
- 2 retirements (with "if your project lockfile pinned X, replace with Y" guidance: `studio-coach` -> nothing or `tpm`; `workflow-optimizer` -> `tool-evaluator` or `tpm` depending on use case)
- 1 new agent (`tech-lead`)
- 1 new playbook doc (`skills/staff/docs/role-pairings.md`)

## 9. Phase 2 work items (deferred, gated on sign-off)

1. Write `engineering/tech-lead.md` (new agent, codex-reviewed across 3 lenses).
2. Rewrite `product/sprint-prioritizer.md` -> `product/product-manager.md` (rename file, narrow scope, drop "6-day" framing, add anti-scope lines, add pairing line).
3. Rewrite `project-management/studio-producer.md` -> `project-management/tpm.md` (narrow scope, drop resource-allocation language, drop process-optimization language, add anti-scope lines).
4. Rewrite `project-management/project-shipper.md` -> `project-management/release-engineer.md` (drop GTM/marketing language, sharpen release-process language, add anti-scope lines).
5. Delete `bonus/studio-coach.md` and `testing/workflow-optimizer.md`.
6. Hand-edit `agent.manifest.yaml` to add `aliases:` entries before regenerating.
7. Run `python3 scripts/generate-manifest.py` (or whatever the current entrypoint is).
8. Run `~/workspace/inc/install.sh --link` to refresh symlinks.
9. Write `skills/staff/docs/role-pairings.md` (PM+TL playbook).
10. Add `CHANGELOG` entry.

Word count: ~1,750 (post codex round 1; up from ~1,450 to absorb sharper authority boundaries and the "considered and rejected" section).
