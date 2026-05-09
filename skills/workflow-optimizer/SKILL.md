---
name: workflow-optimizer
description: 'Periodic ergonomics review of the agent roster. Use when: (1) the user wants to assess whether the agent setup is serving them well, (2) "/workflow-optimizer" or "review my agent workflow" is invoked, (3) deciding which agents to retire / narrow / split / merge based on actual usage and friction, (4) before a major restructure of the roster (rename pass, scope refresh, etc.). Pairs with /staff audit (project-side health), agent-eval-engineer (output quality), and hiring-manager (roster shape decisions). Produces a written report with named recommendations; never auto-deletes anything.'
---

# /workflow-optimizer — agent-roster ergonomics review

Periodic ergonomics review of YOUR agent roster. Different from `/staff audit` (project-side health) and `/agent-eval-engineer` (output quality on graded tasks). This skill answers: **is the agent setup serving me well as a workflow?**

## What it does

Walks four layers of evidence and produces a written report:

1. **Recent agent edits** — what changed, when, why (from `git log` on the HR repo's agent files)
2. **Per-project staffing** — which agents each project actually pulled in (via `staff audit --json`)
3. **Aggregate usage** — which agents are wanted across projects vs. which are dead weight (the audit's retirement-candidates output)
4. **Self-reflection prompts** — handoff friction the user notices subjectively (asked, not measured)

Output is a markdown report at `~/workspace/claude-agents/reports/workflow-review-<date>.md` with:

- **Roster health summary** — N agents in HR, M actually staffed somewhere, K never wanted
- **Friction patterns** — handoffs that cost time, prompts the user keeps editing, agents that "almost work" but need rephrasing each time
- **Description-router signals** — agents whose `description` is too broad (over-fires) or too narrow (under-fires); inferred from staff audit and recent /staff suggest output
- **Recommendations** — per-agent: retire, narrow, split, merge, leave-alone — with one-line rationale
- **Open questions for the user** — the Mihai-shaped judgment calls the report can't make alone

## When to invoke

- Quarterly cadence ("first Monday of the quarter, run /workflow-optimizer")
- After any meaningful roster work (new agents added, large rename pass, codex review of role boundaries)
- When something specific feels off ("I keep editing go-engineer's prompt — is that a description issue, an example issue, or scope drift?")
- Before pairing with `/hiring-manager` for a roster restructure — workflow-optimizer surfaces the data; hiring-manager makes the call

## When NOT to invoke

- Project-side health: use `/staff audit` instead. workflow-optimizer is roster-side.
- Specific agent quality measurement on a known task: use `/agent-eval-engineer` instead. workflow-optimizer is broad ergonomics, not graded performance.
- Deciding whether to add or retire ONE agent: that's `/hiring-manager`. workflow-optimizer is the broader pass that informs hiring-manager.
- Mid-flight while doing real work: this is reflective, not operational.

## Procedure

When invoked, you walk these four layers in order. Don't skip steps; the report's value is in the cross-layer integration.

### Layer 1: Recent edits

```bash
cd $STAFF_HR_REPO   # or ~/workspace/claude-agents
git log --since="3 months ago" --oneline -- engineering/ product/ project-management/ \
    testing/ design/ marketing/ studio-operations/ writing/ bonus/ | head -40
```

For each change in the last quarter, note:
- What changed (rename / scope edit / new agent / retire)
- When
- The commit message (the WHY)

This gives you a sense of which parts of the roster are alive vs ossified.

### Layer 2: Per-project staffing

```bash
staff audit --json
```

Parse the JSON. For each project:
- Is it staffed? (`has_lockfile`)
- Which agents are pulled in?
- Compare to LAST audit if available (delta = signal of evolving needs)

For each agent across all projects:
- Total times wanted
- Distribution (one project? many? all?)

### Layer 3: Aggregate usage

From the same audit JSON:

- **`all_proposed`** = union of agents wanted somewhere → the actually-active roster
- **`retirement_candidates`** = `user_scope - all_proposed - truly_global` → dead weight
- Cross-reference with edit recency: a retirement candidate that was edited last week is suspicious (someone thought it was alive); one untouched for a year is genuinely dead

### Layer 4: Self-reflection (ask the user)

Surface 3-5 questions the data can't answer:

1. "Which agent did you most recently REPHRASE the prompt for? (signals scope-drift or description ambiguity)"
2. "Which handoff between agents costs you the most time? (PM → tech-lead? tech-lead → specialist?)"
3. "Which agent's output do you most often discard / redo manually? (signals output-quality issue, defer to agent-eval-engineer)"
4. "Are there problems you keep solving WITHOUT an agent that maybe should be one?"
5. "Are there agents you forgot existed when you should have invoked them? (signals routing failure or naming issue)"

Listen carefully to the answers. The aggregate-usage data is honest but lossy; subjective friction is precise but partial.

### Output: integrated report

```markdown
# Workflow review — <date>

## TL;DR
- N agents in roster
- M wanted across <P> projects
- K retirement candidates
- Top friction: <one-sentence summary>

## Roster health
[per-category breakdown with usage stats]

## Friction patterns
[2-4 named patterns with evidence and impact]

## Description-router signals
[over/under-firing agents with the suggest-output evidence]

## Recommendations
[per-agent: retire / narrow / split / merge / leave-alone with one-line rationale]

## Open questions for Mihai
[3-5 judgment calls the report can't make alone]
```

Save to `~/workspace/claude-agents/reports/workflow-review-<date>.md`.

## Pairing with adjacent agents/skills

- **`/staff audit`** — feeds layer 2/3 of this skill. Run it first.
- **`/hiring-manager`** — invoke AFTER workflow-optimizer when the recommendations include shape-changing actions (rename, split, merge, new agent). hiring-manager owns the codex-reviewed role-definition writing.
- **`/agent-eval-engineer`** — invoke when workflow-optimizer surfaces "agent X's output is poor" patterns. workflow-optimizer detects the symptom; agent-eval-engineer designs the harness to measure it.

## What this skill is NOT

- Not an automatic monitor. It runs when invoked, not continuously.
- Not a replacement for actually using `/hiring-manager` to write/edit role definitions. workflow-optimizer surfaces the data; hiring-manager does the writing.
- Not a pep talk. No motivational language. The output is dry, evidence-led, with named recommendations.
- Not a code review. Doesn't read the agent system prompts; reads metadata (descriptions, edit history, usage).

## Invocation

```bash
# Just the report; user invokes self-reflection prompts manually
/workflow-optimizer

# With explicit cadence (cron-able once /schedule integrates with this skill)
/workflow-optimizer --since 90d
```

When invoked from Claude Code (via the Skill tool):

1. Read `git log` in HR repo for recent edits
2. Run `staff audit --json` (must be on PATH — comes from the staff skill)
3. Read the JSON and aggregate
4. Ask the user the 3-5 reflection prompts via `AskUserQuestion`
5. Write the integrated report
6. Surface the report path and a one-sentence summary
