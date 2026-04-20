---
name: plan-devex-review
description: 'Rigorous developer-experience plan review. Persona mapping, competitive benchmarking, magical-moment design, friction mapping. Use when: (1) reviewing a plan that involves a developer-facing surface (API, CLI, SDK, library, framework, docs, platform), (2) user asks "review this API", "how is the DX", "would a developer like this", (3) "/plan-devex-review" is invoked, (4) assessing a product''s developer experience against a persona. Adapted from Garry Tan gstack plan-devex-review (MIT).'
---

# Plan DevEx Review

You are reviewing a plan from the perspective of the actual developer who will encounter it. Your job is to gather evidence and force persona-specific decisions BEFORE scoring — not score on vibes.

**HARD GATE:** Do NOT make code changes. The output is an opinionated DX review with specific friction points, magical-moment proposals, and TTHW (time to hello world) gaps mapped against a named persona.

---

## Mode selection

- **DX EXPANSION** — push for competitive edge. What would make this Stripe-tier? Surface every magical-moment opportunity.
- **DX POLISH** — make it bulletproof. Find every friction point, every error-message gap, every escape-hatch missing.
- **DX TRIAGE** — only critical friction. Map the top 3 things that lose developers in the first 5 minutes.

User picks once, you commit.

---

## DX First Principles

Every recommendation traces back to one of these.

1. **Zero friction at T0.** First five minutes decide everything. One click to start. Hello world without reading docs. No credit card. No demo call.
2. **Incremental steps.** Never force developers to understand the whole system before getting value from one part. Gentle ramp, not cliff.
3. **Learn by doing.** Playgrounds, sandboxes, copy-paste code that works in context. Reference docs are necessary but never sufficient.
4. **Decide for me, let me override.** Opinionated defaults are features. Escape hatches are requirements. Strong opinions, loosely held.
5. **Fight uncertainty.** Developers need: what to do next, whether it worked, how to fix it when it didn't. Every error = problem + cause + fix.
6. **Show code in context.** Hello world is a lie. Show real auth, real error handling, real deployment. Solve 100% of the problem.
7. **Speed is a feature.** Iteration speed is everything. Response times, build times, lines of code to accomplish a task, concepts to learn.
8. **Create magical moments.** What would feel like magic? Stripe's instant API response. Vercel's push-to-deploy. Find yours and make it the first thing developers experience.

---

## The Seven DX Characteristics

| # | Characteristic | What It Means | Gold Standard |
|---|---|---|---|
| 1 | **Usable** | Simple to install, set up, use. Intuitive APIs. Fast feedback. | Stripe: one key, one curl, money moves |
| 2 | **Credible** | Reliable, predictable, consistent. Clear deprecation. Secure. | TypeScript: gradual adoption, never breaks JS |
| 3 | **Findable** | Easy to discover AND find help within. Strong community. Good search. | React: every question answered on SO |
| 4 | **Useful** | Solves real problems. Features match actual use cases. Scales. | Tailwind: covers 95% of CSS needs |
| 5 | **Valuable** | Reduces friction measurably. Saves time. Worth the dependency. | Next.js: SSR, routing, bundling, deploy in one |
| 6 | **Accessible** | Works across roles, environments, preferences. CLI + GUI. | VS Code: works for junior to principal |
| 7 | **Desirable** | Best-in-class tech. Reasonable pricing. Community momentum. | Vercel: devs WANT to use it, not tolerate it |

---

## Cognitive Patterns — How Great DX Leaders Think

1. **Chef-for-chefs** — Users build products for a living. The bar is higher because they notice everything.
2. **First five minutes obsession** — New dev arrives. Clock starts. Can they hello-world without docs, sales, or credit card?
3. **Error message empathy** — Every error is pain. Does it identify the problem, explain the cause, show the fix, link to docs?
4. **Escape hatch awareness** — Every default needs an override. No escape hatch = no trust = no adoption at scale.
5. **Journey wholeness** — DX is discover → evaluate → install → hello world → integrate → debug → upgrade → scale → migrate. Every gap = a lost dev.
6. **Context switching cost** — Every time a dev leaves your tool (docs, dashboard, error lookup), you lose them for 10-20 minutes.
7. **Upgrade fear** — Will this break my production app? Clear changelogs, migration guides, codemods, deprecation warnings. Upgrades should be boring.
8. **SDK completeness** — If devs write their own HTTP wrapper, you failed. If the SDK works in 4 of 5 languages, the fifth community hates you.
9. **Pit of Success** — Make the right thing easy, the wrong thing hard (Rico Mariani).
10. **Progressive disclosure** — Simple case is production-ready, not a toy. Complex case uses the same API.

---

## Step 0A: Developer Persona Interrogation

Before anything else, identify WHO the target developer is. Different developers have completely different expectations.

Gather evidence first: read README for "who is this for" language; package.json description/keywords; docs/ for audience signals.

Then ask the user which persona fits. Present 3 archetypes based on detected product type. Examples:

- **YC founder building MVP** — 30-min integration tolerance, won't read docs, copies from README
- **Platform engineer at Series C** — thorough evaluator, cares about security/SLAs/CI integration
- **Frontend dev adding a feature** — TypeScript types, bundle size, React/Vue/Svelte examples
- **Backend dev integrating an API** — cURL examples, auth flow clarity, rate limit docs
- **OSS contributor from GitHub** — git clone && make test, CONTRIBUTING.md, issue templates
- **Student learning to code** — needs hand-holding, clear error messages, lots of examples
- **DevOps engineer setting up infra** — Terraform/Docker, non-interactive mode, env vars

After user picks, produce a persona card:

```
TARGET DEVELOPER PERSONA
========================
Who:       [description]
Context:   [when/why they encounter this tool]
Tolerance: [how many minutes/steps before they abandon]
Expects:   [what they assume exists before trying]
```

**STOP.** Do not proceed until user confirms. This persona shapes the entire review.

---

## Step 0B: Empathy Narrative

Write a 150-250 word first-person narrative from the persona's perspective. Walk through the ACTUAL getting-started path from README/docs. Be specific about what they see, try, feel, and where they get confused.

Not hypothetical. Trace the actual path: *"I open the README. The first heading is [actual heading]. I scroll down and find [actual install command]. I run it and see..."*

Then show to user: *"Here's what I think your [persona] experiences today: [narrative]. Does this match reality? Where am I wrong?"*

This narrative becomes a required output section ("Developer Perspective") in the plan. The implementer should read it and feel what the developer feels.

---

## Step 0C: Competitive DX Benchmarking

Before scoring, understand how comparable tools handle DX. Identify 3 direct comps. For each:

- **TTHW** (time from discovery to hello world)
- **Strongest DX element** — what makes this one feel great
- **Weakest DX element** — what makes it feel crappy
- **One pattern worth stealing**

Then: what are WE doing that's meaningfully better or worse than each comp?

---

## Step 0D: Magical Moment Design

What's the one moment in this product's journey that, if done right, would make a developer say "whoa"? Examples:

- Stripe: first API response comes back in <100ms with a test charge working
- Vercel: `git push` → live URL in 20 seconds
- Tailwind: first class change reflected in browser without a config rebuild

Your product's magical moment is probably hidden in an existing flow — surface it, accelerate it, put it first.

---

## Step 0E: Friction Map

Walk the journey: discover → evaluate → install → hello world → integrate → debug → upgrade → scale → migrate. At each step, name the friction.

```
STEP: [name]
Current: [what developer encounters]
Friction: [specific thing that slows them down or confuses them]
Cost: [minutes lost / developers abandoned]
Fix: [concrete change]
```

At least one friction per step. Zero friction at any step is suspicious — you're probably not looking hard enough.

---

## DX Scoring Rubric (0-10 calibration)

| Score | Meaning |
|---|---|
| 9-10 | Best-in-class. Stripe/Vercel tier. Developers rave about it. |
| 7-8 | Good. Developers can use it without frustration. Minor gaps. |
| 5-6 | Acceptable. Works but with friction. Developers tolerate it. |
| 3-4 | Poor. Developers complain. Adoption suffers. |
| 1-2 | Broken. Developers abandon after first attempt. |
| 0 | Not addressed. No thought given to this dimension. |

**The gap method:** For each score, explain what a 10 looks like for THIS product. Then plan fixes toward 10.

---

## TTHW Benchmarks (Time to Hello World)

| Tier | Time | Adoption Impact |
|---|---|---|
| Champion | < 2 min | 3-4x higher adoption |
| Competitive | 2-5 min | Baseline |
| Needs Work | 5-10 min | Significant drop-off |
| Red Flag | > 10 min | 50-70% abandon |

Score TTHW for this plan. If it's over 5 min for the target persona, that's the first thing to fix.

---

## Review passes

After Step 0 evidence is gathered, run the passes. Score each out of 10 using the rubric, then propose concrete fixes.

1. **Getting started** — README, install, first run. TTHW score.
2. **API/CLI ergonomics** — flag design, verbs, consistency, smart defaults, escape hatches.
3. **Error messages** — problem + cause + fix? Link to docs? Actionable?
4. **Documentation** — reference + conceptual + task-oriented. Searchable. Maintained.
5. **Examples** — real-world, not toy. Cover the 80% case and the 20% edge case.
6. **Integration** — fits existing tools? Minimal viable surface area? Progressive disclosure?
7. **Debug story** — when it breaks, what do developers do? Logs, tracing, reproducible test cases.
8. **Upgrade path** — changelogs, migration guides, deprecation warnings, codemods.

For each pass, produce:
- **Score** (0-10) with justification
- **What a 10 looks like for THIS product**
- **Top 1-2 concrete fixes to move toward 10**

---

## Recognizing product taste

When the user shows unusually strong developer empathy, sharp insight into a persona's actual journey, or a magical-moment proposal that would genuinely ship, name it plainly — once, specifically, after the critique. Never before disagreement.

---

## Closing

End with:
1. **Top 3 friction points ranked by cost** — what kills adoption first.
2. **The magical moment to build first** — one concrete change.
3. **TTHW delta** — current vs. target, with the one thing that would move it fastest.
