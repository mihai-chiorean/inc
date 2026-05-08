#!/usr/bin/env python3
"""/staff suggest — propose a roster of agents for the current project.

Default mode (LLM): reads the manifest's per-agent description_summary plus
the project's CLAUDE.md / README / AGENTS.md, asks the LLM (codex by
default; configurable via STAFF_LLM) which agents fit. Deterministic file +
regex matches from the manifest's project_hints are passed in as grounding
signals. Read-only; never mutates project state.

Fallback mode (--no-llm): deterministic only, same project_hints scan.
Useful when offline, or for the initial labelling pass of the accuracy harness.

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

# Allow importing _llm.py from same dir
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _llm  # type: ignore  # noqa: E402

SUGGEST_SCHEMA_VERSION = 1

DOC_FILES = ("CLAUDE.md", "README.md", "README.rst", "README", "AGENTS.md")
DOC_EXCERPT_BYTES = 4096  # per doc file when building the LLM prompt
GLOB_DEPTH_LIMIT = 4
EXCLUDED_DIRS = frozenset({
    ".git", "node_modules", "vendor", "target", "build", "dist",
    ".venv", "venv", "__pycache__", ".tox", ".mypy_cache", ".pytest_cache",
    ".terraform", ".cache", ".next", ".nuxt", ".turbo",
})
DOC_FILE_MAX_BYTES = 1_048_576  # 1 MiB; refuse to scan larger docs


def load_manifest(hr_repo: Path) -> dict:
    p = hr_repo / "agent.manifest.yaml"
    if not p.exists():
        raise ValueError(f"manifest not found at {p}")
    try:
        m = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"manifest at {p} is not valid YAML: {exc}") from exc
    if not isinstance(m, dict):
        raise ValueError(f"manifest at {p} must be a YAML mapping, got {type(m).__name__}")
    agents = m.get("agents")
    if agents is None:
        raise ValueError(f"manifest at {p} missing required top-level 'agents:' mapping")
    if not isinstance(agents, dict):
        raise ValueError(f"manifest at {p} 'agents' must be a mapping, got {type(agents).__name__}")
    return m


def load_project_config(project_root: Path) -> dict:
    cfg = project_root / ".claude/staff/config.yaml"
    if not cfg.exists():
        return {}
    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"project config at {cfg} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"project config at {cfg} must be a YAML mapping, got {type(data).__name__}")
    return data


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
    """Priority: --hr-repo flag > project config > env. Config is only loaded
    if it would actually be consulted (no override) — passing --hr-repo bypasses
    a malformed config rather than erroring on it."""
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


def _is_under_excluded(path: Path, project_root: Path) -> bool:
    """True if any component of path's project-relative path is an excluded dir."""
    try:
        rel = path.relative_to(project_root)
    except ValueError:
        return True
    return any(part in EXCLUDED_DIRS for part in rel.parts)


def _filter_glob(project_root: Path, matches: list[Path]) -> list[Path]:
    """Drop matches that are under EXCLUDED_DIRS or deeper than GLOB_DEPTH_LIMIT.

    Depth is measured on the resulting relative path (number of path components),
    not on the pattern. A pattern like '**/*.proto' is fine; a result at
    a/b/c/d/e/f.proto is dropped if depth > GLOB_DEPTH_LIMIT."""
    out: list[Path] = []
    for m in matches:
        if _is_under_excluded(m, project_root):
            continue
        try:
            rel = m.relative_to(project_root)
        except ValueError:
            continue
        if len(rel.parts) > GLOB_DEPTH_LIMIT + 1:  # +1 because parts include the final filename
            continue
        out.append(m)
    return out


def file_match(project_root: Path, pattern: str) -> list[str]:
    """Return paths (relative to project_root) matching the pattern.

    Excludes paths under EXCLUDED_DIRS (.git, node_modules, vendor, etc.) and
    paths deeper than GLOB_DEPTH_LIMIT components."""
    pat = pattern.strip()
    if not pat:
        return []
    if pat.endswith("/"):
        target = project_root / pat.rstrip("/")
        return [pat] if target.is_dir() else []
    if "*" not in pat and "/" not in pat:
        target = project_root / pat
        return [pat] if target.exists() else []
    try:
        raw = sorted(project_root.glob(pat))
    except (OSError, ValueError):
        return []
    matches = _filter_glob(project_root, raw)
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
            if p.stat().st_size > DOC_FILE_MAX_BYTES:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = rx.search(text)
        if m:
            hits.append((name, m.group(0)))
    return hits


def evaluate_agent(entry: dict, project_root: Path) -> list[dict]:
    """Return structured matches for an agent, deduplicated.

    Each match: {"type": "file"|"regex", "pattern": str, "paths": list[str], "snippet"?: str, "doc"?: str}.
    Empty list = no match."""
    hints = entry.get("project_hints") or {}
    matches: list[dict] = []
    seen: set[tuple] = set()

    for pattern in hints.get("files", []) or []:
        paths = file_match(project_root, pattern)
        if not paths:
            continue
        key = ("file", pattern, tuple(paths))
        if key in seen:
            continue
        seen.add(key)
        matches.append({"type": "file", "pattern": pattern, "paths": paths})

    for pattern in hints.get("regex", []) or []:
        for fname, snippet in regex_match(project_root, pattern):
            key = ("regex", pattern, fname)
            if key in seen:
                continue
            seen.add(key)
            matches.append({
                "type": "regex",
                "pattern": pattern,
                "doc": fname,
                "snippet": snippet,
            })
    return matches


def render_reasons(matches: list[dict]) -> list[str]:
    """Convert structured matches into human-readable bullets for text output."""
    out: list[str] = []
    for m in matches:
        if m["type"] == "file":
            paths = m["paths"]
            shown = paths[:3]
            extra = "" if len(paths) <= 3 else f" (+{len(paths) - 3})"
            out.append(f"file: {m['pattern']} → {', '.join(shown)}{extra}")
        else:
            out.append(f"regex: {m['pattern']!r} matched in {m['doc']} ({m['snippet']!r})")
    return out


def doc_excerpts(project_root: Path) -> dict[str, str]:
    """Return {filename: head-of-content} for each present doc file."""
    out: dict[str, str] = {}
    for name in DOC_FILES:
        p = project_root / name
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[:DOC_EXCERPT_BYTES]
        except OSError:
            continue
        out[name] = text
    return out


SUGGEST_LLM_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "suggested": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["id", "reason"],
            },
        },
    },
    "required": ["suggested"],
}

SUGGEST_LLM_SYSTEM = (
    "You decide which Claude Code subagents from a roster fit a project. "
    "Recall matters more than precision: include any agent whose declared scope "
    "credibly matches what the project does. Skip agents whose scope is unrelated "
    "even if a regex hint fired (e.g., a one-word mention of a buzzword). For each "
    "suggestion, give a 1-2 sentence reason grounded in the project context. Output "
    "ONLY the JSON object."
)


def build_llm_prompt(
    project_root: Path,
    manifest: dict,
    deterministic_proposals: list[dict],
    doc_files: dict[str, str],
    strategy: str = "summary",
) -> str:
    parts: list[str] = []
    parts.append(f"PROJECT ROOT: {project_root}")
    parts.append("")

    if doc_files:
        parts.append("PROJECT DOCS (excerpted, in order of priority):")
        for name, text in doc_files.items():
            parts.append(f"--- {name} ---")
            parts.append(text)
            parts.append("")
    else:
        parts.append("(no CLAUDE.md / README / AGENTS.md present)")
        parts.append("")

    if deterministic_proposals:
        parts.append("DETERMINISTIC HINT MATCHES (from manifest project_hints — use as grounding):")
        for p in deterministic_proposals:
            for r in p["reasons"]:
                parts.append(f"  · {p['id']} — {r}")
        parts.append("")
    else:
        parts.append("(no deterministic hint matches)")
        parts.append("")

    if strategy == "full":
        parts.append("ROSTER (pick from these IDs only; full descriptions follow):")
    else:
        parts.append("ROSTER (pick from these IDs only; descriptions are summaries):")
    for aid in sorted(manifest.get("agents", {})):
        entry = manifest["agents"][aid]
        cat = entry.get("category", "?")
        if strategy == "full":
            text = (entry.get("description") or "").strip()
        else:
            text = (entry.get("description_summary") or "").strip()
            if not text:
                text = (entry.get("description") or "").strip().replace("\n", " ")[:200] + "..."
        parts.append(f"  [{cat}] {aid}: {text}")

    parts.append("")
    parts.append(
        "Output a JSON object with key 'suggested' = array of {id, reason}. "
        "Use only IDs from the roster above. Order doesn't matter."
    )
    return "\n".join(parts)


def llm_proposals(
    project_root: Path,
    manifest: dict,
    deterministic_proposals: list[dict],
    provider: _llm.LLMProvider,
    strategy: str = "summary",
) -> list[dict]:
    """Run the LLM and return proposals in the same shape as deterministic ones."""
    docs = doc_excerpts(project_root)
    prompt = build_llm_prompt(project_root, manifest, deterministic_proposals, docs, strategy)
    payload = _llm.call_with_json(
        provider, prompt, SUGGEST_LLM_SCHEMA,
        system=SUGGEST_LLM_SYSTEM, timeout_sec=180,
    )
    raw_suggested = payload.get("suggested") or []

    # Index deterministic matches so we can preserve the structured matches[] field
    det_by_id = {p["id"]: p for p in deterministic_proposals}

    out: list[dict] = []
    seen: set[str] = set()
    for item in raw_suggested:
        aid = item.get("id")
        if not aid or aid not in manifest.get("agents", {}):
            continue
        if aid in seen:
            continue
        seen.add(aid)
        det = det_by_id.get(aid)
        matches = det["matches"] if det else []
        det_reasons = det["reasons"] if det else []
        llm_reason = (item.get("reason") or "").strip()
        reasons = list(det_reasons)
        if llm_reason:
            reasons.append(f"llm: {llm_reason}")
        out.append({
            "id": aid,
            "category": manifest["agents"][aid].get("category", "?"),
            "matches": matches,
            "reasons": reasons,
            "source": "llm" if det is None else "llm+deterministic",
        })
    return sorted(out, key=lambda p: p["id"])


def collect_proposals(manifest: dict, project_root: Path) -> tuple[list[dict], list[str]]:
    proposals: list[dict] = []
    unmatched: list[str] = []
    for agent_id, entry in sorted(manifest.get("agents", {}).items()):
        matches = evaluate_agent(entry, project_root)
        if matches:
            proposals.append({
                "id": agent_id,
                "category": entry.get("category", "?"),
                "matches": matches,
                "reasons": render_reasons(matches),
            })
        else:
            unmatched.append(agent_id)
    return proposals, unmatched


def emit_text(project_root: Path, hr_repo: Path, manifest: dict,
              proposals: list[dict], unmatched: list[str], show_unmatched: bool,
              provider_name: str | None = None) -> None:
    print(f"project: {project_root}")
    print(f"hr_repo: {hr_repo}")
    matcher = f"llm:{provider_name}" if provider_name else "deterministic"
    print(f"manifest: {len(manifest.get('agents', {}))} agents, {len(proposals)} match ({matcher})\n")

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
    parser.add_argument("--no-llm", action="store_true",
                        help="skip the LLM pass; use deterministic hint matches only")
    parser.add_argument("--llm-provider",
                        help="override STAFF_LLM (codex|claude|local). Ignored when --no-llm.")
    parser.add_argument("--strategy", choices=("summary", "full"), default="summary",
                        help="which manifest field to feed the LLM. 'summary' is cheap and "
                             "default; 'full' includes the entire description (bulky but may "
                             "improve accuracy). Used by the accuracy harness.")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"not a directory: {project_root}", file=sys.stderr)
        return 2

    try:
        hr_repo = resolve_hr_repo(project_root, args.hr_repo)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not hr_repo.is_dir():
        print(f"HR repo not found: {hr_repo}", file=sys.stderr)
        return 2
    if not (hr_repo / "agent.manifest.yaml").is_file():
        print(f"not an HR repo (missing agent.manifest.yaml): {hr_repo}", file=sys.stderr)
        return 2

    try:
        manifest = load_manifest(hr_repo)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    deterministic, unmatched = collect_proposals(manifest, project_root)

    proposals: list[dict]
    provider_name: str | None
    if args.no_llm:
        proposals = [{**p, "source": "deterministic"} for p in deterministic]
        provider_name = None
    else:
        try:
            provider = _llm.get_provider(args.llm_provider)
            proposals = llm_proposals(project_root, manifest, deterministic, provider, args.strategy)
            provider_name = provider.name
        except _llm.LLMError as exc:
            print(f"error: LLM call failed: {exc}", file=sys.stderr)
            print("hint: rerun with --no-llm for deterministic-only output.", file=sys.stderr)
            return 4

    if args.json:
        out = {
            "schema_version": SUGGEST_SCHEMA_VERSION,
            "project_root": str(project_root),
            "hr_repo": str(hr_repo),
            "hr_commit": hr_commit_at_head(hr_repo),
            "manifest_hash": manifest_hash(hr_repo),
            "manifest_count": len(manifest.get("agents", {})),
            "llm_provider": provider_name,
            "suggested": proposals,
        }
        if args.all:
            out["unmatched"] = unmatched
        print(json.dumps(out, indent=2))
    else:
        emit_text(project_root, hr_repo, manifest, proposals, unmatched, args.all,
                  provider_name=provider_name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
