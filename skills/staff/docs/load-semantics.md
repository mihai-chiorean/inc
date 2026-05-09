# Claude Code agent load semantics

> Verified 2026-05-09 against Claude Code 2.1.x. The findings here drove the design decisions in `/staff` — specifically the choice to put the project's staffed agents in `.claude/agents/<id>.md` rather than try to override user-scope from elsewhere, and the choice to gitignore generated agents by default while committing the lockfile.

This doc answers: when Claude Code starts a session in a project, **which agent .md files load, in what order, and what happens when names collide?**

---

## Sources

1. **[Official Claude Code Subagents docs](https://code.claude.com/docs/en/sub-agents)** — the priority table.
2. **Empirical test** — `claude agents` from inside a test project that intentionally has a name collision with the user-scope.

---

## The priority table (from official docs)

Subagent definitions are loaded from these locations, in priority order (highest first):

| Priority | Location                       | Scope                         | How it gets there |
|---------:|--------------------------------|-------------------------------|-------------------|
| 1        | Managed settings               | Org-wide                      | Deployed via managed settings |
| 2        | `--agents` CLI flag            | Current session only          | JSON passed at `claude` launch |
| 3        | `.claude/agents/`              | Current project (cwd)         | Per-repo; walked up from cwd |
| 4        | `~/.claude/agents/`            | All your projects (user)      | Hand-placed or symlinked |
| 5        | Plugin's `agents/` directory   | Where the plugin is enabled   | Installed via `/plugin` |

When multiple subagents share the **same name**, the higher-priority location wins; the lower-priority versions are **shadowed** but still listed (with a label) in `claude agents`.

---

## What "shadowed" actually looks like

Empirically confirmed by creating a project with `.claude/agents/test-collision.md` and a user-scope `~/.claude/agents/test-collision.md` simultaneously, then running `claude agents`:

```
46 active agents

User agents:
  agent-eval-engineer · opus
  ...
  (shadowed by project) test-collision · inherit
  test-writer-fixer · sonnet
  ...

Project agents (current directory):
  test-collision · inherit (the project version, in use)
```

The user-scope `test-collision` is **explicitly labeled `(shadowed by project)`**. The project-scope version is the one Claude actually uses. The label means Claude knows about the user version but won't dispatch to it.

This matters for `/staff`: when a project staffs an agent that already exists in user-scope under the same id, the project version wins cleanly. No silent merging, no random precedence.

---

## What composes vs. what shadows

- **Different-name agents from different scopes COMPOSE.** All load. A user-scope `go-engineer` and a project-scope `swift-backend` are both available. Total in `claude agents` = (project agents) + (user agents not shadowed) + (plugins not shadowed).
- **Same-name agents from different scopes SHADOW.** Only the highest-priority one is dispatched. The others are listed-but-inactive.

Practical implication: the "`/staff` puts ONLY the staffed subset in `.claude/agents/`, leaves user-scope alone" pattern works exactly as intended. The user-scope set continues to load (composition); the project subset takes priority on any naming collision (shadow). Pruning user-scope down to truly-global agents (per `staff audit`'s retirement-candidates output) is what shrinks the routing prompt — staffing alone doesn't.

---

## Walked-up project discovery

Quoting the docs: *"Project subagents are discovered by walking up from the current working directory."*

Concrete: if you `cd ~/workspace/lab-control/cmd/lab` and start Claude Code, it walks `cmd/lab/` → `cmd/` → `lab-control/` and uses the first `.claude/agents/` it finds. If lab-control has `.claude/agents/`, those agents load. If you'd been one level up at `~/workspace/`, no project agents would load (no `.claude/agents/` at that level).

This means a parent repo's `.claude/agents/` doesn't affect a sub-repo's session unless the sub-repo lacks its own `.claude/agents/` — first-found-wins on the walk.

`--add-dir` does NOT add additional project agent dirs. From the docs: *"Directories added with `--add-dir` grant file access only and are not scanned for subagents."* If you want extra agents in a session, use `--agents` (priority 2) instead.

---

## CLI flag and managed settings (priority 1 and 2)

These are higher-priority than project, but in practice neither shows up in normal use:

- **Managed settings** (priority 1) — corporate deployment via `/en/settings`. Not relevant for a personal repo.
- **`--agents` flag** (priority 2) — pass JSON at `claude` launch:

```bash
claude --agents '{"reviewer": {"description": "Code reviewer", "prompt": "You are a senior code reviewer."}}'
```

Useful for ad-hoc ephemeral agents or scripted invocations. They override anything in `.claude/agents/` for that session only and aren't saved to disk.

---

## Plugin-scoped agents (priority 5, lowest)

Plugin agents come from packages installed via `/plugin`. They appear in `claude agents` alongside everything else. Because they're lowest priority, ANY same-named agent in user-scope or project-scope shadows them. Plugins also have **restrictions** that other scopes don't: plugin subagents cannot use `hooks`, `mcpServers`, or `permissionMode` frontmatter fields — those are silently ignored when loading from a plugin. If you need those, copy the agent file out of the plugin into `.claude/agents/` or `~/.claude/agents/`.

---

## What this means for `/staff`

1. **`.claude/agents/<id>.md` (priority 3) wins over `~/.claude/agents/<id>.md` (priority 4).** Shadowing is the mechanism that lets a project use a tweaked or differently-overlaid version of an agent without fighting user-scope.

2. **Different-name agents compose.** Putting only 5 agents in `.claude/agents/` does NOT remove the 56 from user-scope. If you want the lean roster, you have to prune user-scope. `staff audit` is what tells you which to retire.

3. **The router sees BOTH project and user agents (minus same-name shadows).** When the LLM router decides where to dispatch, it sees the union. So `staff suggest`'s job — picking which agents go in `.claude/agents/` — only narrows the project's shadow set, not the union the router considers.

4. **`--agents` CLI is highest practical priority.** `staff` doesn't use this today (we use the disk-based `.claude/agents/` directory). Future: a hook or wrapper could use `--agents` to inject extra agents per-session without writing to disk.

5. **Plugin agents are weakest.** If we ever package `/staff` and friends as a plugin (vs. the current symlink-via-`install.sh` approach), be aware the contained agents would lose to anything in user-scope. For skills this is probably fine; for agents we'd have to think about it.

---

## What's NOT verified (gaps)

- **Subdirectory layout under `.claude/agents/`** — the official docs don't say whether subdirs are walked. The current convention is to put all agents flat at the directory root with the stable id as the filename. `/staff` follows this. If subdirs are walked recursively, it's a free benefit; if not, the flat convention works either way.
- **Performance impact of large user-scope sets** — anecdotally the routing prompt gets bloated past ~50 agents but no measurement.
- **`maxTurns`, `effort`, and other recent frontmatter fields** at different scopes — assume they apply at whatever scope wins precedence; not directly tested.

---

## Reference cmd

```bash
claude agents                 # list active agents (with shadowed-by labels)
claude agents --setting-sources project,user   # restrict which scopes load
```

Useful for verifying what the current session actually has access to, especially after a `/staff apply` or after editing `~/.claude/agents/`.
