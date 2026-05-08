#!/usr/bin/env python3
"""Generate agent.manifest.yaml from agent .md files in this HR repo.

Idempotent: re-run whenever agent files change. Preserves hand-curated fields
(tags, project_hints, conflicts, aliases, introduced) by reading the existing
manifest and merging.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone  # used only by git_first_commit_date

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "agent.manifest.yaml"

CATEGORIES = [
    "engineering",
    "product",
    "marketing",
    "testing",
    "writing",
    "design",
    "project-management",
    "studio-operations",
    "bonus",
]

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
KNOWN_KEYS = {"name", "description", "model", "color", "tools"}
KEY_LINE_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s?(.*)$")


def parse_frontmatter_permissive(raw: str) -> dict:
    """Parse the agent frontmatter without choking on unquoted descriptions
    that contain embedded ': ' sequences (e.g., 'Examples:\\n<example>\\nContext: foo').

    Returns dict with at least 'name' and 'description'; fails loudly otherwise."""
    out: dict[str, str] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        m = KEY_LINE_RE.match(line)
        if m and m.group(1) in KNOWN_KEYS:
            current_key = m.group(1)
            out[current_key] = m.group(2)
        elif current_key is not None:
            out[current_key] += "\n" + line
    if "name" not in out or not out["name"].strip():
        raise ValueError("frontmatter missing required 'name' field")
    if "description" not in out or not out["description"].strip():
        raise ValueError("frontmatter missing required 'description' field")
    return out


def canonicalize_for_hash(s: str) -> str:
    """Single canonical form for hashing description and body strings: strip
    leading and trailing whitespace, leave internal content unchanged."""
    return s.strip()


def parse_agent_file(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{path}: no frontmatter found")
    frontmatter = parse_frontmatter_permissive(m.group(1))
    body = m.group(2)
    return frontmatter, body


def sha256(s: str) -> str:
    """Hash a string after canonicalization (strip leading + trailing whitespace)."""
    return "sha256:" + hashlib.sha256(canonicalize_for_hash(s).encode("utf-8")).hexdigest()


def derive_tags(name: str, category: str) -> list[str]:
    parts = [p for p in name.split("-") if p]
    seen = set(parts)
    if category not in seen:
        parts.append(category)
    return sorted(set(parts))


def git_first_commit_date(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT)
    try:
        out = subprocess.check_output(
            ["git", "log", "--diff-filter=A", "--follow", "--format=%cI", "--", str(rel)],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if out:
            first = out.splitlines()[-1]
            return first[:10]
    except subprocess.CalledProcessError:
        pass
    return datetime.now(timezone.utc).date().isoformat()


def load_existing_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {"agents": {}}
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) or {"agents": {}}


def collect_agent_files() -> list[Path]:
    files = []
    for cat in CATEGORIES:
        cat_dir = REPO_ROOT / cat
        if not cat_dir.is_dir():
            continue
        for p in sorted(cat_dir.glob("*.md")):
            if p.name == "README.md":
                continue
            files.append(p)
    return files


def build_entry(path: Path, existing: dict) -> tuple[str, dict]:
    frontmatter, body = parse_agent_file(path)
    name = frontmatter["name"].strip()
    description = frontmatter["description"]
    rel = path.relative_to(REPO_ROOT).as_posix()
    category = path.parent.name

    prev = existing.get(name, {})

    entry = {
        "file": rel,
        "category": category,
        "description": description,
        "description_hash": sha256(description),
        "body_hash": sha256(body),
        "tags": prev.get("tags") or derive_tags(name, category),
        "project_hints": prev.get("project_hints") or {"files": [], "regex": []},
        "conflicts": prev.get("conflicts") or [],
        "introduced": prev.get("introduced") or git_first_commit_date(path),
        "aliases": prev.get("aliases") or [],
    }
    return name, entry


def main() -> int:
    existing = load_existing_manifest().get("agents") or {}
    files = collect_agent_files()
    if not files:
        print("no agent files found", file=sys.stderr)
        return 1

    agents: dict[str, dict] = {}
    failures: list[str] = []
    for path in files:
        try:
            name, entry = build_entry(path, existing)
        except ValueError as exc:
            failures.append(f"{path}: {exc}")
            continue
        if name in agents:
            failures.append(f"{path}: duplicate stable id '{name}'")
            continue
        agents[name] = entry

    if failures:
        for f in failures:
            print(f"error: {f}", file=sys.stderr)
        print(f"\n{len(failures)} agent file(s) failed to parse — refusing to write a partial manifest.",
              file=sys.stderr)
        return 2

    seen_ids = set(agents.keys())
    for old_id, old_entry in existing.items():
        if old_id in seen_ids:
            continue
        for new_id, new_entry in agents.items():
            if old_id in (new_entry.get("aliases") or []):
                break
        else:
            print(f"warning: agent '{old_id}' was in manifest but not found on disk; "
                  "if renamed, add the old id to the new entry's aliases:", file=sys.stderr)

    manifest = {
        "schema_version": 1,
        "generated_by": "scripts/generate-manifest.py",
        "source_repo": "claude-agents",
        "agents": dict(sorted(agents.items())),
    }

    out = yaml.safe_dump(manifest, sort_keys=False, width=120, allow_unicode=True)
    if MANIFEST_PATH.exists() and MANIFEST_PATH.read_text(encoding="utf-8") == out:
        print(f"{MANIFEST_PATH} unchanged ({len(agents)} agents)")
        return 0
    MANIFEST_PATH.write_text(out, encoding="utf-8")
    print(f"wrote {MANIFEST_PATH} ({len(agents)} agents)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
