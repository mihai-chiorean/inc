# Project repo leakage policy

> Decision: `.claude/agents/` (the **generated** agent files) is **gitignored by default**. `.claude/staff/` (the user-owned source of truth: lockfile, config, overlays) is **committed by default**. Override via `commit_generated_agents: true` in `.claude/staff/config.yaml` when the project actively wants generated agents in the repo.

This file documents the tradeoff, the default, and what to do at the edges.

---

## What gets committed by default

```
<project>/
  .claude/
    agents/                  ← gitignored (generated; rebuilt by `staff apply`)
      go-engineer.md
      security-auditor.md
    staff/
      lock.yaml              ← COMMITTED (pinned hashes — reviewable in PRs)
      config.yaml            ← COMMITTED (HR repo path, stale-overlay threshold)
      overlays/              ← COMMITTED unless individual overlays opt out
        go-engineer.md       ← COMMITTED
```

The lockfile committed means project staffing is **reviewable**: when you bump an HR pin, the diff in `lock.yaml` shows exactly which agents and which commits moved. This is the same reason `package-lock.json`, `Cargo.lock`, `Package.resolved` are committed in their respective ecosystems.

The generated `.claude/agents/<id>.md` files are **build artifacts**: HR base + overlay merged with marker comments. They're regenerable from `lock.yaml` + the HR repo + `.claude/staff/overlays/`. Committing them adds churn (large file diffs on every HR pin bump) without reproducibility benefit when HR is reachable.

---

## When to flip the default

Set `commit_generated_agents: true` in `.claude/staff/config.yaml` when **any** of these apply:

1. **The project repo lives somewhere HR doesn't.** A vendor handoff, a published demo, an air-gapped lab. Whoever opens the repo needs the agent files immediately, without cloning the HR repo first.
2. **You want to pin Claude Code behavior verifiably.** With generated files committed, the exact prompt Claude Code will see is in the repo and reviewable. Without commit, you trust `staff apply` to reproduce it.
3. **You're publishing the repo as a reference.** The generated agents make the project's intent transparent to readers.

In all three cases, the tradeoff is: every HR pin bump produces a noisy diff (~3 KB per agent × N agents staffed). Acceptable if your review process is set up for it.

---

## What never gets committed regardless

Overlays are committed by default and merged verbatim into the generated agent files. They are the **primary leakage surface** — anything you write in an overlay is in the project repo and (depending on the project repo's visibility) potentially public. Discipline list:

- **Secrets.** Passwords, API keys, tokens, OAuth client secrets, signing keys. Use environment variables or a secret manager and reference them by name in the overlay (`see $DB_PASSWORD env var`), never the value.
- **Hostnames and URLs.** Internal hostnames, staging/prod URLs, customer-tenant subdomains, internal-only DNS names. These leak topology, scale, and tenancy.
- **Customer / tenant identifiers.** "This overlay was written for Acme Corp's deployment" or "tenant_id 47291 has the legacy auth path" — never in overlays.
- **Internal repo / org names.** "See gnarly-vendor/legacy-auth for the original implementation" leaks org structure and prior-art relationships.
- **Incident details.** Post-mortem references with date, scope, or affected customer — overlays are not the right home.
- **Architecture notes that aren't already public.** If the org's threat model isn't published, don't bake "we use mTLS this way for legal reasons" into an overlay.
- **Auth flow specifics that an attacker would value.** "To trigger admin mode, set the X-Admin header to Y" is a vulnerability disclosure, not a context note.
- **Out-of-tree paths.** Overlays that reference `/Users/mihai/private-notes/...` are useless to anyone else and signal local layout.
- **"Temporary" debugging notes.** Anything you'd be embarrassed to find in `git log -p` six months later. The "temporary" framing decays fast.

`staff apply` does NOT enforce any of this — it merges overlay content verbatim. Discipline is on the user.

### `config.yaml` is a leakage surface too

`.claude/staff/config.yaml` is committed by default. Its `hr_repo:` value is a path. That path can leak:

- Your organization's name (`/home/work/acme-corp/agents/`)
- Internal repo names (`git@gh.internal.example/private-agents.git`)
- Your username and local filesystem layout
- The fact that you have a private HR repo at all (vs. using a public one)

If the project repo is public, prefer the `STAFF_HR_REPO` env var (set per-machine) over baking an absolute private path into the committed config. The config schema accepts both; the env var wins when both are set.

### Generated agents leak HR base content

If you flip `commit_generated_agents: true`, the generated `.claude/agents/<id>.md` files contain HR's base prompts merged with your overlays. **Only do this when the HR-derived content is allowed to leave HR.** A private HR repo's prompts may contain internal policy, security posture, tool conventions, or anti-scope rationale that's not meant to leave the HR fence. Public repo + private HR + committed generated agents = an unintended HR exfiltration channel.

### Git history is a leakage surface

`.gitignore` and `git rm --cached` only stop **future** tracking. They do not remove history. If sensitive overlay content (or a leaky `config.yaml`) was ever committed:

- **For real secrets**: assume compromise. Rotate the credential immediately. Adding `.gitignore` after the fact does not invalidate the leaked secret.
- **For non-secret-but-still-sensitive content**: consider `git filter-repo` (or BFG) to rewrite history, then force-push and notify any clones to re-clone. This is disruptive; weigh against just letting history stay if the project is private and the content is moderately sensitive.
- **Default position**: write overlays as if they will be public from day one. The history-rewrite path is for accidents, not design.

---

## What `staff status` flags

`staff status` does not check for leaky overlays. That would require a domain-aware classifier (regex on "password" / "api_key" / "secret" produces too many false positives, and misses the real-world cases like "the staging URL is gnarly-vendor.com" which is also leaky in some contexts).

If you want a pre-commit lint, write a project-level hook that scans `.claude/staff/overlays/*.md` for your specific patterns and runs on `git commit`.

---

## Recommended `.gitignore` entries

Two modes, depending on `commit_generated_agents`:

### Default mode (recommended): generated agents gitignored

```gitignore
# Generated by /staff apply — rebuilt from .claude/staff/lock.yaml and overlays.
.claude/agents/
```

That single line covers everything under `.claude/agents/` — both the merged agent files and any temp files staff produces. No need for a separate `.tmp.*` rule.

### Commit-generated mode (opt-in): generated agents committed, temp files still ignored

```gitignore
# Temp files /staff apply creates during atomic write; never commit these.
.claude/agents/.tmp.*
```

`.claude/agents/<id>.md` itself stays tracked.

### What stays committed in either mode

```
.claude/staff/lock.yaml          ← source of truth; review pins in PRs
.claude/staff/config.yaml        ← project config (mind the leakage warnings above)
.claude/staff/overlays/          ← overlay sources; mind the leakage discipline list
```

---

## Migration: opting in to commit generated agents

If you flip `commit_generated_agents: true` partway through a project's life:

1. Update `.claude/staff/config.yaml`: `commit_generated_agents: true`
2. Remove `.claude/agents/` from `.gitignore`
3. Run `staff apply --agents <ids>` (or wait for `/staff sync`) to regenerate cleanly
4. `git add .claude/agents/ && git commit`

Going the other direction (committed → gitignored) is just adding `.claude/agents/` back to `.gitignore` and `git rm --cached -r .claude/agents/`.

---

## Why a separate decision from `.claude/staff/`

The lockfile + overlays + config are **specifications**: "this project staffs these agents at these HR commits, with these project-specific notes." They are small (one `agent.lock` file, a handful of short overlay files) and auditable.

The generated `.claude/agents/<id>.md` files are **outputs**: the spec applied. They're large and re-derive cleanly. Treating them like build artifacts (gitignored, regeneratable) is consistent with how every other build system handles outputs vs. inputs.

---

## Why config is committed but lockfile changes go through review

`config.yaml` records the HR repo path and per-project preferences. It changes rarely (initial setup + occasional preference changes). Committing it makes `staff` work on a fresh clone without re-configuration.

`lock.yaml` records pinned HR commits and hashes. It changes whenever you bump HR. The diff is small and reviewable, which makes "we updated HR pins" a meaningful PR rather than a silent shift.

Together: a teammate clones the project, runs `staff apply` (no flags needed; config is read), and gets the same agent set you have. With generated files gitignored, the artifacts get freshly built locally. With generated files committed (opt-in), nothing needs to run at all.
