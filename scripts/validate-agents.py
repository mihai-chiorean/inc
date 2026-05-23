#!/usr/bin/env python3
"""Validate all agent .md files against Claude Code's frontmatter spec.

Three checks:
  - HARD: frontmatter parses with strict YAML (yaml.safe_load). The repo's
    invariant after MIT-392; any failure here blocks merge.
  - WARN: description ≤ 1024 chars (per Anthropic spec). Tracked by MIT-393.
  - WARN: description contains no XML tags (<, per Anthropic spec). MIT-393.

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

DESCRIPTION_MAX_CHARS = 1024
XML_TAG_RE = re.compile(r"<[a-zA-Z/]")


def collect_agent_files() -> list[Path]:
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


def validate_one(path: Path) -> dict:
    """Check a single agent file. Returns a dict with hard_errors and warnings."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {
            "file": rel,
            "hard_errors": ["no frontmatter delimited by '---' lines"],
            "warnings": [],
        }
    block = m.group(1)
    hard: list[str] = []
    warn: list[str] = []
    parsed: dict | None = None
    try:
        parsed = yaml.safe_load(block)
        if not isinstance(parsed, dict):
            hard.append(f"frontmatter did not parse to a YAML mapping (got {type(parsed).__name__})")
            parsed = None
    except yaml.YAMLError as exc:
        # Compact the YAML error to a single line for the report.
        msg = str(exc).splitlines()[0] if "\n" in str(exc) else str(exc)
        hard.append(f"strict YAML parse failed: {msg}")

    if parsed is not None:
        name = parsed.get("name")
        desc = parsed.get("description")
        if not name:
            hard.append("missing required 'name' field")
        if not desc:
            hard.append("missing required 'description' field")
        else:
            if len(desc) > DESCRIPTION_MAX_CHARS:
                warn.append(
                    f"description is {len(desc)} chars (Anthropic spec: ≤{DESCRIPTION_MAX_CHARS}); "
                    "see MIT-393"
                )
            if XML_TAG_RE.search(desc):
                warn.append(
                    "description contains XML tags (Anthropic spec: none); see MIT-393"
                )

    return {"file": rel, "hard_errors": hard, "warnings": warn}


def emit_text(results: list[dict], quiet: bool) -> None:
    hard_count = sum(len(r["hard_errors"]) for r in results)
    warn_count = sum(len(r["warnings"]) for r in results)
    hard_files = sum(1 for r in results if r["hard_errors"])
    warn_files = sum(1 for r in results if r["warnings"] and not r["hard_errors"])
    clean_files = sum(1 for r in results if not r["hard_errors"] and not r["warnings"])

    if not quiet:
        print(f"Validating {len(results)} agent files...\n")
        for r in results:
            if r["hard_errors"]:
                print(f"  ✗ HARD  {r['file']}")
                for e in r["hard_errors"]:
                    print(f"          → {e}")
                for w in r["warnings"]:
                    print(f"          ⚠ {w}")
            elif r["warnings"]:
                print(f"  ⚠ WARN  {r['file']}")
                for w in r["warnings"]:
                    print(f"          ⚠ {w}")
            else:
                print(f"  ✓       {r['file']}")
        print()
    else:
        for r in results:
            if r["hard_errors"]:
                print(f"  ✗ HARD  {r['file']}")
                for e in r["hard_errors"]:
                    print(f"          → {e}")

    print(f"Summary: {clean_files} clean, {warn_files} warn-only, {hard_files} hard-fail "
          f"({hard_count} errors, {warn_count} warnings).")
    if hard_files:
        print("\nHard failures block merge. Fix and re-run.", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--quiet", action="store_true",
                        help="only print files with hard failures")
    args = parser.parse_args()

    files = collect_agent_files()
    if not files:
        print("error: no agent files found", file=sys.stderr)
        return 2
    results = [validate_one(p) for p in files]
    hard_count = sum(1 for r in results if r["hard_errors"])

    if args.json:
        print(json.dumps({
            "total": len(results),
            "hard_failures": hard_count,
            "warnings": sum(len(r["warnings"]) for r in results),
            "results": results,
        }, indent=2))
    else:
        emit_text(results, args.quiet)

    return 1 if hard_count else 0


if __name__ == "__main__":
    sys.exit(main())
