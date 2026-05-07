#!/usr/bin/env python3
"""/staff suggest — propose a roster of agents for the current project.

Reads the HR manifest, scans the project for hint matches (presence of
specific files or regex patterns in CLAUDE.md / README), and prints a
proposed roster. Read-only; never mutates project state.

Recall over precision: an agent matches if any of its hints fire. The user
prunes the proposal with /staff remove before /staff apply.

HR repo discovery (in priority order):
  1. --hr-repo argument
  2. .claude/staff/config.yaml in project root, key `hr_repo:`
  3. $STAFF_HR_REPO env var
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml

SUGGEST_SCHEMA_VERSION = 1

DOC_FILES = ("CLAUDE.md", "README.md", "README.rst", "README", "AGENTS.md")
GLOB_DEPTH_LIMIT = 4


def load_manifest(hr_repo: Path) -> dict:
    p = hr_repo / "agent.manifest.yaml"
    if not p.exists():
        sys.exit(f"manifest not found at {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def load_project_config(project_root: Path) -> dict:
    cfg = project_root / ".claude/staff/config.yaml"
    if cfg.exists():
        return yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    return {}


def parse_hr_repo_path(value: str) -> Path:
    """Parse an hr_repo value which may be a plain path or a file:// URL.

    Uses urllib so spaces and percent-encoded chars round-trip correctly."""
    parsed = urlparse(value)
    if parsed.scheme == "file":
        path = unquote(parsed.path)
    elif parsed.scheme:
        raise ValueError(f"unsupported hr_repo scheme: {parsed.scheme!r} (only file:// and plain paths are supported)")
    else:
        path = value
    return Path(path).expanduser().resolve()


def resolve_hr_repo(project_root: Path, override: str | None) -> Path:
    if override:
        return parse_hr_repo_path(override)
    cfg = load_project_config(project_root)
    if cfg.get("hr_repo"):
        return parse_hr_repo_path(str(cfg["hr_repo"]))
    env = os.environ.get("STAFF_HR_REPO")
    if env:
        return parse_hr_repo_path(env)
    sys.exit(
        "HR repo not specified.\n"
        "  --hr-repo PATH                   pass explicitly\n"
        "  STAFF_HR_REPO=PATH               set in env\n"
        "  .claude/staff/config.yaml        set hr_repo: in the project"
    )


def hr_commit_at_head(hr_repo: Path) -> str | None:
    """Best-effort full SHA of HR HEAD. Returns None if not a git repo."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=hr_repo,
            stderr=subprocess.DEVNULL,
        )
        return out.decode().strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def manifest_hash(hr_repo: Path) -> str:
    p = hr_repo / "agent.manifest.yaml"
    return "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()


def file_match(project_root: Path, pattern: str) -> list[str]:
    """Return paths (relative to project_root) matching the pattern."""
    pat = pattern.strip()
    if not pat:
        return []
    if pat.endswith("/"):
        target = project_root / pat.rstrip("/")
        return [pat] if target.is_dir() else []
    if "*" not in pat and "/" not in pat:
        target = project_root / pat
        return [pat] if target.exists() else []
    if "**" in pat:
        depth = pat.count("/")
        if depth > GLOB_DEPTH_LIMIT:
            return []
        matches = sorted(project_root.glob(pat))
    else:
        matches = sorted(project_root.glob(pat))
    return [str(m.relative_to(project_root)) for m in matches if m.exists()]


def regex_match(project_root: Path, pattern: str) -> list[tuple[str, str]]:
    """Return (filename, snippet) for each doc file the regex matches."""
    try:
        rx = re.compile(pattern)
    except re.error as exc:
        print(f"warning: invalid regex {pattern!r}: {exc}", file=sys.stderr)
        return []
    hits: list[tuple[str, str]] = []
    for name in DOC_FILES:
        p = project_root / name
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = rx.search(text)
        if m:
            hits.append((name, m.group(0)))
    return hits


def evaluate_agent(entry: dict, project_root: Path) -> list[str]:
    hints = entry.get("project_hints") or {}
    reasons: list[str] = []
    for pattern in hints.get("files", []) or []:
        matches = file_match(project_root, pattern)
        if matches:
            shown = matches[:3]
            extra = "" if len(matches) <= 3 else f" (+{len(matches) - 3})"
            reasons.append(f"file: {pattern} → {', '.join(shown)}{extra}")
    for pattern in hints.get("regex", []) or []:
        for fname, snippet in regex_match(project_root, pattern):
            reasons.append(f"regex: {pattern!r} matched in {fname} ({snippet!r})")
    return reasons


def collect_proposals(manifest: dict, project_root: Path) -> tuple[list[dict], list[str]]:
    proposals: list[dict] = []
    unmatched: list[str] = []
    for agent_id, entry in sorted(manifest.get("agents", {}).items()):
        reasons = evaluate_agent(entry, project_root)
        if reasons:
            proposals.append({
                "id": agent_id,
                "category": entry.get("category", "?"),
                "reasons": reasons,
            })
        else:
            unmatched.append(agent_id)
    return proposals, unmatched


def emit_text(project_root: Path, hr_repo: Path, manifest: dict,
              proposals: list[dict], unmatched: list[str], show_unmatched: bool) -> None:
    print(f"project: {project_root}")
    print(f"hr_repo: {hr_repo}")
    print(f"manifest: {len(manifest.get('agents', {}))} agents, {len(proposals)} match\n")

    if not proposals:
        print("No agents matched any project hints.")
        print("  Add manually:           /staff add <id>")
        print("  Curate hints in HR:     edit project_hints in agent.manifest.yaml")
        return

    by_cat: dict[str, list[dict]] = {}
    for p in proposals:
        by_cat.setdefault(p["category"], []).append(p)
    for cat in sorted(by_cat):
        print(f"[{cat}]")
        for p in by_cat[cat]:
            print(f"  {p['id']}")
            for r in p["reasons"]:
                print(f"    · {r}")
        print()

    if show_unmatched and unmatched:
        print(f"[unmatched ({len(unmatched)})]")
        for uid in unmatched:
            print(f"  {uid}")
        print()

    print("Next:")
    print(f"  /staff apply        # install all {len(proposals)} suggested agents")
    print("  /staff add <id>     # add an agent not in the suggestion")
    print("  /staff remove <id>  # drop one before apply")


def main() -> int:
    parser = argparse.ArgumentParser(description="propose a staffing roster for a project")
    parser.add_argument("--project-root", default=".", help="project root (default: cwd)")
    parser.add_argument("--hr-repo", help="HR repo path (overrides config + env)")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--all", action="store_true", help="include unmatched agents in output")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"not a directory: {project_root}", file=sys.stderr)
        return 2

    try:
        hr_repo = resolve_hr_repo(project_root, args.hr_repo)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not hr_repo.is_dir():
        print(f"HR repo not found: {hr_repo}", file=sys.stderr)
        return 2
    if not (hr_repo / "agent.manifest.yaml").is_file():
        print(f"not an HR repo (missing agent.manifest.yaml): {hr_repo}", file=sys.stderr)
        return 2

    manifest = load_manifest(hr_repo)
    proposals, unmatched = collect_proposals(manifest, project_root)

    if args.json:
        out = {
            "schema_version": SUGGEST_SCHEMA_VERSION,
            "project_root": str(project_root),
            "hr_repo": str(hr_repo),
            "hr_commit": hr_commit_at_head(hr_repo),
            "manifest_hash": manifest_hash(hr_repo),
            "manifest_count": len(manifest.get("agents", {})),
            "suggested": proposals,
        }
        if args.all:
            out["unmatched"] = unmatched
        print(json.dumps(out, indent=2))
    else:
        emit_text(project_root, hr_repo, manifest, proposals, unmatched, args.all)

    return 0


if __name__ == "__main__":
    sys.exit(main())
