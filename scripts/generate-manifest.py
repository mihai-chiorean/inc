#!/usr/bin/env python3
"""Generate agent.manifest.yaml from agent .md files in this HR repo.

Idempotent: re-run whenever agent files change. Preserves hand-curated fields
(tags, project_hints, conflicts, aliases, introduced) and per-agent
description_summary across runs.

Use --llm-summaries to (re-)compute summaries for agents that don't have one
yet, or whose description has changed (description_hash mismatch). Without
that flag, summaries are preserved as-is and never updated. Calls go through
skills/staff/scripts/_llm.py (provider selected by STAFF_LLM env var).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone  # used only by git_first_commit_date

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "agent.manifest.yaml"

# Allow importing skills/staff/scripts/_llm.py
sys.path.insert(0, str(REPO_ROOT / "skills/staff/scripts"))
import _llm  # type: ignore  # noqa: E402

SUMMARY_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
}

SUMMARY_SYSTEM = (
    "You write tight, factual one-paragraph summaries of Claude Code subagent definitions. "
    "Each summary is 2-4 sentences. Capture: when to use the agent, what it specialises in, "
    "and any explicit anti-scope. Avoid marketing language. Do not mention the agent's name "
    "in the summary (it's already keyed by id). Output ONLY the JSON object."
)

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
REQUIRED_KEYS = {"name", "description"}


def parse_frontmatter_strict(raw: str, source: str = "<frontmatter>") -> dict:
    """Parse agent frontmatter with strict YAML.

    Per MIT-392, every agent's frontmatter must be valid YAML — that's
    what Claude Code's loader (and `/staff suggest`'s router) actually
    consumes. The permissive parser this replaced existed to tolerate
    multi-line unquoted descriptions with embedded `: ` sequences; those
    are now swept into double-quoted single-line form so strict YAML works.

    `scripts/validate-agents.py` is the supporting check; it's also called
    out as a pre-push gate in CLAUDE.md Rule 8.
    """
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(
            f"{source}: strict YAML parse failed — {exc}\n"
            "Run `python3 scripts/validate-agents.py` for the full report."
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            f"{source}: frontmatter did not parse to a YAML mapping "
            f"(got {type(parsed).__name__})"
        )
    for required in REQUIRED_KEYS:
        val = parsed.get(required)
        if not val or not str(val).strip():
            raise ValueError(f"{source}: frontmatter missing required {required!r} field")
    # Coerce all values to strings (model/color/tools/scope sometimes come
    # back as YAML scalars of varying types). The manifest writer expects
    # strings; preserving the YAML-native type would break downstream code.
    out = {k: str(v) if not isinstance(v, str) else v for k, v in parsed.items()}
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
    frontmatter = parse_frontmatter_strict(m.group(1), source=str(path))
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

    desc_hash = sha256(description)
    # Carry forward summary if description hasn't changed; otherwise blank
    # so the LLM pass (if requested) re-summarises.
    prev_summary = prev.get("description_summary") or ""
    prev_desc_hash = prev.get("description_hash") or ""
    summary = prev_summary if prev_desc_hash == desc_hash else ""

    # Read `scope` from frontmatter; default to "project". The org set is
    # what install.sh installs at user scope by default; the rest go to
    # per-project .claude/agents/ via /staff. See docs/getting-started/
    # bootstrap.md and MIT-375.
    scope_raw = frontmatter.get("scope", "project")
    scope = scope_raw.strip().lower() if isinstance(scope_raw, str) else "project"
    if scope not in {"project", "org"}:
        scope = "project"

    entry = {
        "file": rel,
        "category": category,
        "scope": scope,
        "description": description,
        "description_summary": summary,
        "description_hash": desc_hash,
        "body_hash": sha256(body),
        "tags": prev.get("tags") or derive_tags(name, category),
        "project_hints": prev.get("project_hints") or {"files": [], "regex": []},
        "conflicts": prev.get("conflicts") or [],
        "introduced": prev.get("introduced") or git_first_commit_date(path),
        "aliases": prev.get("aliases") or [],
    }
    return name, entry


def summarise_agent(name: str, description: str, provider: _llm.LLMProvider) -> str:
    """Call the LLM to produce a description_summary for one agent."""
    prompt = (
        f"Agent id: {name}\n\n"
        f"Description (from frontmatter):\n{description}\n\n"
        "Write a 2-4 sentence factual summary that a router could use to decide whether "
        "to send a project's task to this agent. Output the JSON object."
    )
    payload = _llm.call_with_json(
        provider, prompt, SUMMARY_SCHEMA, system=SUMMARY_SYSTEM, timeout_sec=120,
    )
    summary = (payload.get("summary") or "").strip()
    if not summary:
        raise _llm.LLMError(f"empty summary for {name!r}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate agent.manifest.yaml")
    parser.add_argument(
        "--llm-summaries", action="store_true",
        help="Compute description_summary for any agent whose description has changed "
             "or which has no summary yet. Calls the LLM provider configured via STAFF_LLM.",
    )
    parser.add_argument(
        "--summarise-only", metavar="ID", action="append", default=[],
        help="When used with --llm-summaries, only summarise these agent ids "
             "(repeatable). Useful for incremental top-ups.",
    )
    args = parser.parse_args()

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

    if args.llm_summaries:
        try:
            provider = _llm.get_provider()
        except _llm.LLMError as exc:
            print(f"error: cannot resolve LLM provider: {exc}", file=sys.stderr)
            return 2
        target_ids = (
            sorted(set(args.summarise_only)) if args.summarise_only
            else [aid for aid, e in agents.items() if not e["description_summary"]]
        )
        if target_ids:
            print(f"computing description_summary via {provider.name} for {len(target_ids)} agents", file=sys.stderr)
        for aid in target_ids:
            if aid not in agents:
                print(f"warning: --summarise-only {aid!r} not in manifest, skipping", file=sys.stderr)
                continue
            try:
                summary = summarise_agent(aid, agents[aid]["description"], provider)
            except _llm.LLMError as exc:
                print(f"error: failed to summarise {aid}: {exc}", file=sys.stderr)
                return 3
            agents[aid]["description_summary"] = summary
            print(f"  ✓ {aid} ({len(summary)} chars)", file=sys.stderr)

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
