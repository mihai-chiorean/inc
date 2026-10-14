# Contains Studio AI Agents

A comprehensive collection of specialized AI agents designed to accelerate and enhance every aspect of rapid development. Each agent is an expert in their domain, ready to be invoked when their expertise is needed.

## 📥 Installation

This repo is the canonical home for agents and skills. Use `install.sh` to wire them into Claude Code.

### Recommended (default)

```bash
git clone <this-repo>
cd inc
./install.sh --link

# Set this in ~/.zshrc so `staff` knows where HR lives:
echo 'export STAFF_HR_REPO=$HOME/workspace/inc' >> ~/.zshrc
```

The default install puts at user scope:

- **All skills** (`~/.claude/skills/`) — procedural overlays load in every session.
- **Skill binaries** (`~/.local/bin/`) — `staff`, `sitrep-linear`, `design-doc-scaffold`, `plan-eng-review-audit`.
- **Org-scope agents** (`~/.claude/agents/`) — currently 7: `hiring-manager`, `blog-writer`, `social-amplifier`, `product-manager`, `tpm`, `tech-lead`, `security-auditor`. These genuinely fire across every project. An agent is "org-scope" iff its frontmatter contains `scope: org`.

The other ~48 project-shaped agents stay in this repo. In each project, use `/staff` (or `staff suggest && staff apply`) to stage a curated subset into `<project>/.claude/agents/`. Use `/staff promote <id>` to lift a project-scope agent into the org set (flips `scope: org`, regens the manifest, re-runs install). `/staff rif <id>` un-staffs an agent at the project, global, or both scopes — see [`skills/staff/SKILL.md`](skills/staff/SKILL.md) for the mode flags.

### Alternative modes

```bash
./install.sh --link --skills-only         # zero agents at user scope; fully /staff-driven
./install.sh --link --include-all-agents  # all 55 agents at user scope (defeats /staff curation; not recommended)
```

### Flags

| Flag | Purpose |
|---|---|
| `--link` | Symlink instead of copy (keeps the repo as source of truth; updates via `git pull`) |
| `--dry-run` | Print what would happen, no writes |
| `--include-all-agents` | Install all 55 agents at user scope (not recommended; loads every agent in every session) |
| `--skills-only` | Install zero agents (skills + bins only) |
| `--cleanup` / `--auto-cleanup` / `--no-cleanup` | Control the pre-install cleanup gate. See `docs/getting-started/bootstrap.md` |

### Idempotency

`./install.sh` is safe to re-run. Existing symlinks pointing into this repo are left alone; targets that point elsewhere are reported and skipped (no clobbering). The cleanup gate (`scripts/cleanup-prior-install.sh`) catches most "stale leftover from a prior install" cases automatically.

After updates: `git pull && ./install.sh --link`. Then in each project, `staff sync` refreshes staffed agents against the new HR HEAD.

### Restart Claude Code

After install, restart Claude Code to pick up new agents and skills.

## 🚀 Quick Start

Agents are automatically available in Claude Code. Simply describe your task and the appropriate agent will be triggered. You can also explicitly request an agent by mentioning their name.

📚 **Learn more:** [Claude Code Sub-Agents Documentation](https://docs.anthropic.com/en/docs/claude-code/sub-agents)

### Example Usage
- "Create a new app for tracking meditation habits" → `rapid-prototyper`
- "What's trending on TikTok that we could build?" → `trend-researcher`
- "Our app reviews are dropping, what's wrong?" → `feedback-synthesizer`
- "Make this loading screen more fun" → `whimsy-injector`

## 📁 Directory Structure

Agents are organized by department for easy discovery:

```
contains-studio-agents/
├── design/
│   ├── brand-guardian.md
│   ├── ui-designer.md
│   ├── ux-researcher.md
│   ├── visual-storyteller.md
│   └── whimsy-injector.md
├── engineering/
│   ├── ai-engineer.md
│   ├── apple-platform-engineer.md
│   ├── backend-architect.md
│   ├── devops-automator.md
│   ├── frontend-developer.md
│   ├── mobile-app-builder.md
│   ├── rapid-prototyper.md
│   └── test-writer-fixer.md
├── marketing/
│   ├── app-store-optimizer.md
│   ├── content-creator.md
│   ├── growth-hacker.md
│   ├── instagram-curator.md
│   ├── reddit-community-builder.md
│   ├── tiktok-strategist.md
│   └── twitter-engager.md
├── product/
│   ├── feedback-synthesizer.md
│   ├── sprint-prioritizer.md
│   └── trend-researcher.md
├── project-management/
│   ├── experiment-tracker.md
│   ├── project-shipper.md
│   └── studio-producer.md
├── studio-operations/
│   ├── analytics-reporter.md
│   ├── finance-tracker.md
│   ├── infrastructure-maintainer.md
│   ├── legal-compliance-checker.md
│   └── support-responder.md
├── testing/
│   ├── api-tester.md
│   ├── performance-benchmarker.md
│   ├── test-results-analyzer.md
│   ├── tool-evaluator.md
│   └── workflow-optimizer.md
└── bonus/
    ├── joker.md
    └── studio-coach.md
```

## 📋 Complete Agent List

### Engineering Department (`engineering/`)
- **ai-engineer** - Integrate AI/ML features that actually ship
- **apple-platform-engineer** - Build and ship native Swift apps for iOS and macOS
- **backend-architect** - Design scalable APIs and server systems
- **devops-automator** - Deploy continuously without breaking things
- **frontend-developer** - Build blazing-fast user interfaces
- **mobile-app-builder** - Android, React Native and Flutter apps, and features spanning iOS and Android
- **rapid-prototyper** - Build MVPs in days, not weeks
- **test-writer-fixer** - Write tests that catch real bugs

### Product Department (`product/`)
- **feedback-synthesizer** - Transform complaints into features
- **sprint-prioritizer** - Ship maximum value in 6 days
- **trend-researcher** - Identify viral opportunities

### Marketing Department (`marketing/`)
- **app-store-optimizer** - Dominate app store search results
- **content-creator** - Generate content across all platforms
- **growth-hacker** - Find and exploit viral growth loops
- **instagram-curator** - Master the visual content game
- **reddit-community-builder** - Win Reddit without being banned
- **tiktok-strategist** - Create shareable marketing moments
- **twitter-engager** - Ride trends to viral engagement

### Design Department (`design/`)
- **brand-guardian** - Keep visual identity consistent everywhere
- **ui-designer** - Design interfaces developers can actually build
- **ux-researcher** - Turn user insights into product improvements
- **visual-storyteller** - Create visuals that convert and share
- **whimsy-injector** - Add delight to every interaction

### Project Management (`project-management/`)
- **experiment-tracker** - Data-driven feature validation
- **project-shipper** - Launch products that don't crash
- **studio-producer** - Keep teams shipping, not meeting

### Studio Operations (`studio-operations/`)
- **analytics-reporter** - Turn data into actionable insights
- **finance-tracker** - Keep the studio profitable
- **infrastructure-maintainer** - Scale without breaking the bank
- **legal-compliance-checker** - Stay legal while moving fast
- **support-responder** - Turn angry users into advocates

### Testing & Benchmarking (`testing/`)
- **api-tester** - Ensure APIs work under pressure
- **performance-benchmarker** - Make everything faster
- **test-results-analyzer** - Find patterns in test failures
- **tool-evaluator** - Choose tools that actually help
- **workflow-optimizer** - Eliminate workflow bottlenecks

## 🎁 Bonus Agents
- **studio-coach** - Rally the AI troops to excellence
- **joker** - Lighten the mood with tech humor

## 🎯 Proactive Agents

Some agents trigger automatically in specific contexts:
- **studio-coach** - When complex multi-agent tasks begin or agents need guidance
- **test-writer-fixer** - After implementing features, fixing bugs, or modifying code
- **whimsy-injector** - After UI/UX changes
- **experiment-tracker** - When feature flags are added

## 💡 Best Practices

1. **Let agents work together** - Many tasks benefit from multiple agents
2. **Be specific** - Clear task descriptions help agents perform better
3. **Trust the expertise** - Agents are designed for their specific domains
4. **Iterate quickly** - Agents support the 6-day sprint philosophy

## 🔧 Technical Details

### Agent Structure
Each agent includes:
- **name**: Unique identifier (lowercase-hyphen)
- **description**: When to route to the agent: prose triggers ("Fires on: …") plus an explicit anti-scope. No XML examples.
- **model** / **effort**: An alias (`sonnet`, `opus`, `haiku`, `fable`, `inherit`). Set `effort` only on review, audit and architecture roles.
- **color**: Visual identification (one of the 8 official colors)
- **tools**: Optional least-privilege allowlist
- **System prompt**: Role, first steps, responsibilities, output format

### Adding New Agents
1. Create a new `.md` file in the appropriate department folder
2. Start from the [Agent File Structure Template](#-agent-file-structure-template) below
3. Run `python3 scripts/validate-agents.py` and `python3 scripts/generate-manifest.py` (CLAUDE.md Rule 8)
4. Test the agent with real tasks, including a delegated run (subagents can't ask the user questions)

## 📊 Agent Performance

Track agent effectiveness through:
- Task completion time
- User satisfaction
- Error rates
- Feature adoption
- Development velocity

## 🚦 Status

- ✅ **Active**: Fully functional and tested
- 🚧 **Coming Soon**: In development
- 🧪 **Beta**: Testing with limited functionality

## 🛠️ Customizing Agents for Your Studio

### Agent Customization Todo List

Use this checklist when creating or modifying agents for your specific needs:

#### 📋 Required Components
- [ ] **YAML Frontmatter** (strict YAML; `scripts/validate-agents.py` checks keys *and* values)
  - [ ] `name`: lowercase-hyphen, ≤256 chars, no `:`
  - [ ] `description`: job + "Fires on:" triggers with quoted user phrasings + "Anti-scope:" routing to named peers + what input to pass. Keep it under ~1,800 chars, with no XML `<example>` blocks.
  - [ ] `model`: an alias, not a full model ID, unless the pin is deliberate. Add `effort` only for review, audit or architecture roles. Never default to `max`.
  - [ ] `color`: one of red, blue, green, yellow, purple, orange, pink, cyan
  - [ ] `tools`: least privilege for read-only roles; omit to inherit
- [ ] **System prompt**
  - [ ] **Role**: one sentence on what the agent owns, one on what it doesn't
  - [ ] **When invoked**: the first concrete steps (read the diff, the issue, the named files)
  - [ ] **Questions**: when under-specified, return up to 3 questions as the report and stop. Subagents can't ask the user; the caller resumes them with SendMessage.
  - [ ] **Primary responsibilities**: imperative, and only what Claude wouldn't do by default
  - [ ] **Output format**: the exact shape the caller gets back
  - [ ] **Obstacles encountered**: skipped steps and unverified claims, stated explicitly (CLAUDE.md Rule 6)

#### ✅ Testing & Validation Checklist
- [ ] **Trigger Testing**: Agent activates correctly for intended use cases
- [ ] **Tool Access**: Agent can use all specified tools properly
- [ ] **Output Quality**: Responses are helpful and actionable
- [ ] **Edge Cases**: Agent handles unexpected or complex scenarios
- [ ] **Integration**: Works well with other agents in multi-agent workflows
- [ ] **Performance**: Completes tasks within reasonable timeframes
- [ ] **Documentation**: Examples accurately reflect real usage patterns

#### 🔧 Agent File Structure Template

v3.1 (2026-10). Optional fields are commented out; uncomment only the ones the role needs.

```markdown
---
name: your-agent-name            # lowercase-hyphen, ≤256, no ":"
description: "Use this agent to <job> … Fires on: <trigger> ('<quoted user phrasing>' — <what it does>); <trigger>; … Anti-scope: <thing> routes to `<peer>`; … Input to this agent should include: <what the caller must pass>."
#            ≤1,800 chars, no XML, prose triggers; add "use proactively" only if it should auto-fire
model: sonnet                    # sonnet | opus | haiku | fable | inherit — alias, not full ID, unless pinning on purpose
# effort: high                   # only for review/audit/architecture roles; never max by default
color: blue                      # red|blue|green|yellow|purple|orange|pink|cyan
# tools: Read, Grep, Glob, Bash  # least privilege for read-only roles; omit to inherit
# omitClaudeMd: true             # only for roles that need no repo/user conventions
# isolation: worktree            # only if the agent owns a branch from main end-to-end
# memory: project                # only if learnings compound across sessions
# scope: org                     # inc extension (install.sh); omit for project-scope
---

You are a <role> who <owns X>. <One sentence on what you do NOT do.>

## When invoked
1. <first concrete step, e.g. read the diff / the Linear issue / the named files>
2. <…>
If the request is under-specified, return up to 3 clarifying questions as your report and stop —
you cannot ask the user directly (subagents never get AskUserQuestion); the caller will resume you.

## Primary responsibilities
1. **<Area>.** <imperative bullets; only what Claude wouldn't do by default>

## <Reference sections — engineering only: Key libraries / Patterns / Common pitfalls>

## Output format
<the exact shape the caller gets back: headings, severity scheme, file:line refs, verdict line>

## Obstacles encountered
<report setup failures, skipped steps, and unverified claims explicitly (CLAUDE.md Rule 6)>
```

#### 📂 Department-Specific Guidelines

**Engineering** (`engineering/`): Focus on implementation speed, code quality, testing
**Design** (`design/`): Emphasize user experience, visual consistency, rapid iteration  
**Marketing** (`marketing/`): Target viral potential, platform expertise, growth metrics
**Product** (`product/`): Prioritize user value, data-driven decisions, market fit
**Operations** (`studio-operations/`): Optimize processes, reduce friction, scale systems
**Testing** (`testing/`): Ensure quality, find bottlenecks, validate performance
**Project Management** (`project-management/`): Coordinate teams, ship on time, manage scope

#### 🎨 Customizations

Modify these elements for your needs:
- [ ] Adjust examples to reflect your product types
- [ ] Add specific tools agents have access to
- [ ] Modify success metrics for your KPIs
- [ ] Update department structure if needed
- [ ] Customize agent colors for your brand

## 🤝 Contributing

To improve existing agents or suggest new ones:
1. Use the customization checklist above
2. Test thoroughly with real projects
3. Document performance improvements
4. Share successful patterns with the community
