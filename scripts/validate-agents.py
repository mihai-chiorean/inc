#!/usr/bin/env python3
"""Validate agent .md and skill SKILL.md files against Anthropic's frontmatter spec.

Per MIT-413, this validator was rewritten to match Anthropic's published agent
and skill spec (see research/agent-skill-spec-ground-truth-MIT-410.md). Before,
KNOWN_KEYS conflated "what generate-manifest.py consumes" with "what the spec
allows" — the result was that spec-correct fields (`allowed-tools`, `effort`,
`disable-model-invocation`) tripped warnings while spec-incorrect ones (`tools`,
`color`) were silently accepted. This file is now spec-first.

Checks performed:
  - HARD: frontmatter parses with strict YAML (yaml.safe_load).
  - HARD: required keys present (`name`, `description`).
  - HARD (skills only): combined len(description) + len(when_to_use) ≤ 1536
    chars. This is Anthropic's documented router truncation cap.
  - WARN (agents): description ≤ 2000 chars. No documented spec cap, but the
    spirit is "tight"; 2000 is generous to allow MIT-415 gradual migration.
  - WARN: description contains XML tags (tracked separately under MIT-393).
  - WARN: non-spec frontmatter keys (e.g. `tools`, `color`, `skills`,
    `version`, `references`). For agents, see TODO below about MIT-412.
  - WARN: agent has `tools:` field — silently ignored by Claude Code, almost
    always means the author intended `allowed-tools:`. Will tighten to HARD
    after MIT-412 sweeps the existing 51 agents off this field.

Carve-out:
  - `scope:` on agents is an inc-repo extension consumed by install.sh's
    `is_org_agent` awk helper (filters which agents install at user scope
    by default). The validator accepts it without warning. See install.sh.

Exit codes:
  0 — no hard failures (warnings allowed)
  1 — at least one hard failure
  2 — script error (missing dir, etc.)

Usage:
  python3 scripts/validate-agents.py            # human-readable report
  python3 scripts/validate-agents.py --json     # machine-readable
  python3 scripts/validate-agents.py --quiet    # only print failures
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CATEGORIES = [
    "engineering", "product", "marketing", "testing", "writing",
    "design", "project-management", "studio-operations", "bonus",
]
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
XML_TAG_RE = re.compile(r"<[a-zA-Z/]")

# Per Anthropic sub-agents.md spec
# (https://code.claude.com/docs/en/sub-agents.md).
AGENT_SPEC_KEYS = {
    "name", "description", "model", "effort",
    "allowed-tools", "disallowed-tools",
    "user-invocable", "disable-model-invocation",
    "context", "agent", "hooks", "paths",
}

# Per Anthropic skills.md spec
# (https://code.claude.com/docs/en/skills.md → "Frontmatter reference").
SKILL_SPEC_KEYS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable",
    "allowed-tools", "disallowed-tools",
    "model", "effort", "context", "agent", "hooks", "paths", "shell",
}

# inc-repo extension. `scope:` on agents is consumed by install.sh's
# is_org_agent awk helper to decide which agents install at user scope
# by default (org vs project). Not in Anthropic's spec but load-bearing
# for our installer — keep as an explicit carve-out so the validator
# doesn't WARN on agents that legitimately use it.
INC_EXTENSION_KEYS = {"scope"}

# Agent description char budget. Anthropic doesn't publish a cap for agents
# (only skills are documented at 1,536 combined). 2000 is the inc-repo
# guideline — tight enough to keep routing context lean, generous enough
# that MIT-415 can rewrite the 52 over-spec descriptions gradually.
AGENT_DESCRIPTION_MAX_CHARS = 2000

# Skill description char budget. Anthropic's documented hard cap:
# `description` + `when_to_use` together are truncated at 1,536 chars in
# the skill listing (see https://code.claude.com/docs/en/skills.md). We
# treat exceeding this as a HARD failure because content past the cap is
# silently dropped from the router's view.
SKILL_DESCRIPTION_MAX_CHARS = 1536


# TODO(MIT-412): tighten the `tools/color/skills` non-spec-field check on
# agents from WARN to HARD once the existing 51 agents are swept off the
# (spec-incorrect) `tools` field. Today, hard-failing those would block
# every PR. Keep as WARN until that sweep merges, then flip the default
# here and let CI enforce.


def collect_agent_files() -> list[Path]:
    """Walk agent category dirs and return all *.md files (minus READMEs)."""
    files: list[Path] = []
    for cat in CATEGORIES:
        cat_dir = REPO_ROOT / cat
        if not cat_dir.is_dir():
            continue
        for p in sorted(cat_dir.glob("*.md")):
            if p.name == "README.md":
                continue
            files.append(p)
    return files


def collect_skill_files() -> list[Path]:
    """Walk skills/<name>/SKILL.md and return paths."""
    files: list[Path] = []
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.is_dir():
        return files
    for sub in sorted(skills_dir.iterdir()):
        if not sub.is_dir():
            continue
        skill_md = sub / "SKILL.md"
        if skill_md.is_file():
            files.append(skill_md)
    return files


def _parse_frontmatter(path: Path) -> tuple[dict | None, list[str], list[str]]:
    """Common frontmatter parse step. Returns (parsed, hard_errors, warnings)."""
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    hard: list[str] = []
    warn: list[str] = []
    if not m:
        hard.append("no frontmatter delimited by '---' lines")
        return None, hard, warn
    block = m.group(1)
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        msg = str(exc).splitlines()[0] if "\n" in str(exc) else str(exc)
        hard.append(f"strict YAML parse failed: {msg}")
        return None, hard, warn
    if not isinstance(parsed, dict):
        hard.append(
            f"frontmatter did not parse to a YAML mapping (got {type(parsed).__name__})"
        )
        return None, hard, warn
    return parsed, hard, warn


def validate_agent(path: Path) -> dict:
    """Check a single agent file. Returns hard_errors and warnings."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    parsed, hard, warn = _parse_frontmatter(path)
    if parsed is None:
        return {"kind": "agent", "file": rel, "hard_errors": hard, "warnings": warn}

    name = parsed.get("name")
    desc = parsed.get("description")
    if not isinstance(name, str) or not name.strip():
        hard.append("missing required 'name' field (or non-string / whitespace-only)")
    if not isinstance(desc, str) or not desc.strip():
        hard.append("missing required 'description' field (or non-string / whitespace-only)")
    else:
        if len(desc) > AGENT_DESCRIPTION_MAX_CHARS:
            warn.append(
                f"description is {len(desc)} chars (inc guideline: "
                f"≤{AGENT_DESCRIPTION_MAX_CHARS}); see MIT-415"
            )
        if XML_TAG_RE.search(desc):
            warn.append("description contains XML tags (Anthropic spec: none); see MIT-393")

    # Non-spec keys. Allow inc carve-outs (`scope`) silently. Everything
    # else is a WARN today (TODO above: tighten to HARD post-MIT-412).
    allowed = AGENT_SPEC_KEYS | INC_EXTENSION_KEYS
    unknown = sorted(k for k in parsed.keys() if k not in allowed)
    if unknown:
        warn.append(
            f"non-spec frontmatter keys {unknown!r} on agent — Anthropic's "
            "sub-agents.md does not list these. `tools` in particular is "
            "silently ignored by Claude Code; the spec field is "
            "`allowed-tools`. Tracked under MIT-412 (will HARD-fail after "
            "the sweep merges)."
        )

    return {"kind": "agent", "file": rel, "hard_errors": hard, "warnings": warn}


def validate_skill(path: Path) -> dict:
    """Check a single SKILL.md. Returns hard_errors and warnings."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    parsed, hard, warn = _parse_frontmatter(path)
    if parsed is None:
        return {"kind": "skill", "file": rel, "hard_errors": hard, "warnings": warn}

    name = parsed.get("name")
    desc = parsed.get("description")
    when_to_use = parsed.get("when_to_use", "")
    if not isinstance(name, str) or not name.strip():
        hard.append("missing required 'name' field (or non-string / whitespace-only)")
    if not isinstance(desc, str) or not desc.strip():
        hard.append("missing required 'description' field (or non-string / whitespace-only)")
    else:
        desc_len = len(desc)
        wtu_len = len(when_to_use) if isinstance(when_to_use, str) else 0
        combined = desc_len + wtu_len
        if combined > SKILL_DESCRIPTION_MAX_CHARS:
            hard.append(
                f"description + when_to_use is {combined} chars "
                f"({desc_len} + {wtu_len}); Anthropic spec caps this at "
                f"{SKILL_DESCRIPTION_MAX_CHARS} (router truncates above)."
            )
        if XML_TAG_RE.search(desc):
            warn.append("description contains XML tags (Anthropic spec: none); see MIT-393")

    # Non-spec keys on skills are WARN (we're more lenient than on agents —
    # skills less standardised in the repo, several use `version`/
    # `references`/`dependencies` for human bookkeeping).
    unknown = sorted(k for k in parsed.keys() if k not in SKILL_SPEC_KEYS)
    if unknown:
        warn.append(
            f"non-spec frontmatter keys {unknown!r} on skill — Anthropic's "
            "skills.md does not list these; they parse but are ignored by "
            "Claude Code's loader."
        )

    return {"kind": "skill", "file": rel, "hard_errors": hard, "warnings": warn}


def _summarise(results: list[dict], kind: str) -> tuple[int, int, int]:
    """Return (clean, warn_only, hard_fail) counts for a kind."""
    subset = [r for r in results if r["kind"] == kind]
    clean = sum(1 for r in subset if not r["hard_errors"] and not r["warnings"])
    warn_only = sum(1 for r in subset if r["warnings"] and not r["hard_errors"])
    hard = sum(1 for r in subset if r["hard_errors"])
    return clean, warn_only, hard


def _count_grandfathered(results: list[dict]) -> int:
    """How many agents trip the non-spec-fields warning today.
    Surfaced once at startup as an MIT-412 progress signal."""
    return sum(
        1 for r in results
        if r["kind"] == "agent"
        and any("non-spec frontmatter keys" in w for w in r["warnings"])
    )


def emit_text(results: list[dict], quiet: bool) -> None:
    if not quiet:
        agents = [r for r in results if r["kind"] == "agent"]
        skills = [r for r in results if r["kind"] == "skill"]
        print(f"Validating {len(agents)} agents and {len(skills)} skills...\n")
        for r in results:
            tag = "agent" if r["kind"] == "agent" else "skill"
            if r["hard_errors"]:
                print(f"  ✗ HARD  [{tag}] {r['file']}")
                for e in r["hard_errors"]:
                    print(f"          → {e}")
                for w in r["warnings"]:
                    print(f"          ⚠ {w}")
            elif r["warnings"]:
                print(f"  ⚠ WARN  [{tag}] {r['file']}")
                for w in r["warnings"]:
                    print(f"          ⚠ {w}")
            else:
                print(f"  ✓       [{tag}] {r['file']}")
        print()
    else:
        for r in results:
            if r["hard_errors"]:
                tag = "agent" if r["kind"] == "agent" else "skill"
                print(f"  ✗ HARD  [{tag}] {r['file']}")
                for e in r["hard_errors"]:
                    print(f"          → {e}")

    a_clean, a_warn, a_hard = _summarise(results, "agent")
    s_clean, s_warn, s_hard = _summarise(results, "skill")
    print(
        f"Summary: "
        f"Agents: {a_clean} clean, {a_warn} warn, {a_hard} hard-fail. "
        f"Skills: {s_clean} clean, {s_warn} warn, {s_hard} hard-fail."
    )

    grandfathered = _count_grandfathered(results)
    if grandfathered:
        print(
            f"\nNote: MIT-412 in progress — {grandfathered} agents currently "
            "carry non-spec frontmatter keys (e.g. `tools`, `color`, "
            "`skills`). These WARN today; once MIT-412's sweep merges this "
            "validator will be tightened to HARD-fail on those keys."
        )

    if a_hard or s_hard:
        print("\nHard failures block merge. Fix and re-run.", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog=(
            "Validates against Anthropic's published agent + skill spec "
            "(see research/agent-skill-spec-ground-truth-MIT-410.md). "
            "Skills HARD-fail if combined description + when_to_use > "
            f"{SKILL_DESCRIPTION_MAX_CHARS} chars (router cap). Agents WARN "
            f"if description > {AGENT_DESCRIPTION_MAX_CHARS} chars (inc "
            "guideline). Non-spec frontmatter keys WARN today; agent "
            "non-spec keys will be tightened to HARD after MIT-412."
        ),
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--quiet", action="store_true",
                        help="only print files with hard failures")
    args = parser.parse_args()

    agent_files = collect_agent_files()
    skill_files = collect_skill_files()
    if not agent_files and not skill_files:
        print("error: no agent or skill files found", file=sys.stderr)
        return 2

    results: list[dict] = []
    results.extend(validate_agent(p) for p in agent_files)
    results.extend(validate_skill(p) for p in skill_files)
    hard_count = sum(1 for r in results if r["hard_errors"])

    if args.json:
        a_clean, a_warn, a_hard = _summarise(results, "agent")
        s_clean, s_warn, s_hard = _summarise(results, "skill")
        print(json.dumps({
            "total": len(results),
            "hard_failures": hard_count,
            "warnings": sum(len(r["warnings"]) for r in results),
            "agents": {"clean": a_clean, "warn": a_warn, "hard": a_hard},
            "skills": {"clean": s_clean, "warn": s_warn, "hard": s_hard},
            "results": results,
        }, indent=2))
    else:
        emit_text(results, args.quiet)

    return 1 if hard_count else 0


if __name__ == "__main__":
    sys.exit(main())
