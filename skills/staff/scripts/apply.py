#!/usr/bin/env python3
"""/staff apply — install staffed agents from HR into .claude/agents/.

Inputs (one of, mutually exclusive):
  --from-suggest <path>    Read schema_version=1 JSON from file (or `-` for stdin)
  --agents <id1> <id2>     Explicit list of stable agent IDs

For each ID:
  1. Resolve the entry in agent.manifest.yaml (handles aliases).
  2. Read the HR base file.
  3. Read .claude/staff/overlays/<id>.md if it exists; parse frontmatter.
  4. Build the merged file (HR body + overlay markers + overlay body).
  5. Write .claude/agents/<id>.md.
  6. Update .claude/staff/lock.yaml with all the at-pin hashes.

Refuses if:
  - HR repo has uncommitted changes (`git status --porcelain` non-empty).
  - Suggest JSON's hr_commit != current HR HEAD (use --force to override).
  - An ID isn't in the manifest (or in any manifest entry's aliases).

Hand edits to .claude/agents/<id>.md are NOT preserved — overwritten.
agent.local.md (if it ever lives in .claude/agents/ — it shouldn't, but
guard anyway) is never touched.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_DEFAULTS = {
    "lock_path": ".claude/staff/lock.yaml",
    "agents_dir": ".claude/agents",
    "overlays_dir": ".claude/staff/overlays",
}
LOCKFILE_SCHEMA_VERSION = 1
SUGGEST_SCHEMA_VERSION_SUPPORTED = 1
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
OVERLAY_BEGIN = "<!-- BEGIN STAFF OVERLAY -->"
OVERLAY_END = "<!-- END STAFF OVERLAY -->"


# ---------- shared helpers (kept local to the script for portability) ----------


def canonicalize_for_hash(s: str) -> str:
    return s.strip()


def sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(canonicalize_for_hash(s).encode("utf-8")).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def split_agent_file(text: str) -> tuple[str, str, dict]:
    """Returns (raw_frontmatter_block, body, parsed_frontmatter).

    Frontmatter must parse with strict YAML — this is the post-MIT-392
    invariant enforced by scripts/validate-agents.py and the CI gate.
    Using strict YAML here (rather than the previous permissive
    line-by-line parser) means the description string we hash matches
    what generate-manifest.py records in agent.manifest.yaml, which is
    what status.py compares against. MIT-411 was the spurious HR-DRIFT
    caused by the parser mismatch between apply (permissive: captured
    surrounding quotes and literal `\\n` chars) and generate-manifest
    (strict: real YAML-decoded value)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("agent file has no frontmatter")
    fm_block = m.group(1)
    body = m.group(2)
    try:
        fm = yaml.safe_load(fm_block)
    except yaml.YAMLError as exc:
        raise ValueError(
            f"agent frontmatter failed strict YAML parse: {exc}. "
            "Run `python3 scripts/validate-agents.py` on the HR repo."
        ) from exc
    if not isinstance(fm, dict):
        raise ValueError(
            f"agent frontmatter did not parse to a YAML mapping "
            f"(got {type(fm).__name__})"
        )
    # Coerce scalar values to strings (model/color/etc may come back as
    # native YAML types). description/name are always strings in practice
    # but defensive-cast for consistency.
    fm = {k: str(v) if not isinstance(v, str) else v for k, v in fm.items()}
    return fm_block, body, fm


def parse_overlay(text: str) -> tuple[dict, str]:
    """Overlay frontmatter is real YAML (no embedded ': ' weirdness)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("overlay file has no frontmatter")
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"overlay frontmatter is not valid YAML: {exc}") from exc
    if not isinstance(fm, dict):
        raise ValueError("overlay frontmatter must be a mapping")
    body = m.group(2)
    return fm, body


# ---------- HR / project I/O ----------


@dataclass
class Paths:
    project_root: Path
    hr_repo: Path
    lock_path: Path
    agents_dir: Path
    overlays_dir: Path

    @classmethod
    def from_project(cls, project_root: Path, hr_repo: Path) -> "Paths":
        return cls(
            project_root=project_root,
            hr_repo=hr_repo,
            lock_path=project_root / REPO_DEFAULTS["lock_path"],
            agents_dir=project_root / REPO_DEFAULTS["agents_dir"],
            overlays_dir=project_root / REPO_DEFAULTS["overlays_dir"],
        )


def load_project_config(project_root: Path) -> dict:
    cfg = project_root / ".claude/staff/config.yaml"
    if not cfg.exists():
        return {}
    try:
        data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"project config at {cfg} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"project config at {cfg} must be a YAML mapping")
    return data


def parse_hr_repo_path(value: str) -> Path:
    from urllib.parse import unquote, urlparse
    parsed = urlparse(value)
    if parsed.scheme == "file":
        path = unquote(parsed.path)
    elif parsed.scheme:
        raise ValueError(
            f"unsupported hr_repo scheme: {parsed.scheme!r} (only file:// and plain paths supported)"
        )
    else:
        path = value
    return Path(path).expanduser().resolve()


def resolve_hr_repo(project_root: Path, override: str | None) -> Path:
    cfg = load_project_config(project_root)
    if override:
        return parse_hr_repo_path(override)
    if cfg.get("hr_repo"):
        return parse_hr_repo_path(str(cfg["hr_repo"]))
    env = os.environ.get("STAFF_HR_REPO")
    if env:
        return parse_hr_repo_path(env)
    raise ValueError(
        "HR repo not specified — pass --hr-repo, set STAFF_HR_REPO, or write hr_repo: in .claude/staff/config.yaml"
    )


def hr_head_sha(hr_repo: Path) -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=hr_repo, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise ValueError(f"HR repo at {hr_repo} is not a git repo or git unavailable: {exc}") from exc
    return out.decode().strip()


def hr_is_clean(hr_repo: Path) -> bool:
    try:
        out = subprocess.check_output(["git", "status", "--porcelain"], cwd=hr_repo, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
    return out.decode().strip() == ""


def load_manifest(hr_repo: Path) -> dict:
    p = hr_repo / "agent.manifest.yaml"
    if not p.exists():
        raise ValueError(f"manifest not found at {p}")
    try:
        m = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"manifest at {p} is not valid YAML: {exc}") from exc
    if not isinstance(m, dict) or not isinstance(m.get("agents"), dict):
        raise ValueError(f"manifest at {p} missing valid 'agents' mapping")
    # Validate alias uniqueness: each alias must map to exactly one canonical ID
    alias_owners: dict[str, str] = {}
    for canonical_id, entry in m["agents"].items():
        for alias in entry.get("aliases") or []:
            if alias in m["agents"]:
                raise ValueError(
                    f"manifest invalid: alias {alias!r} of {canonical_id!r} collides with a canonical agent id"
                )
            prior = alias_owners.get(alias)
            if prior is not None:
                raise ValueError(
                    f"manifest invalid: alias {alias!r} is claimed by both {prior!r} and {canonical_id!r}"
                )
            alias_owners[alias] = canonical_id
    return m


def manifest_hash(hr_repo: Path) -> str:
    return sha256_bytes((hr_repo / "agent.manifest.yaml").read_bytes())


def load_lockfile(lock_path: Path) -> dict:
    if not lock_path.exists():
        return {"schema_version": LOCKFILE_SCHEMA_VERSION, "staffed": {}}
    try:
        data = yaml.safe_load(lock_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"lockfile at {lock_path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"lockfile at {lock_path} must be a YAML mapping")
    sv = data.get("schema_version")
    if sv is not None and sv != LOCKFILE_SCHEMA_VERSION:
        raise ValueError(
            f"lockfile at {lock_path} schema_version={sv} is not supported by this apply "
            f"(expected {LOCKFILE_SCHEMA_VERSION})"
        )
    if "staffed" not in data or not isinstance(data["staffed"], dict):
        data["staffed"] = {}
    return data


def atomic_write(path: Path, content: str) -> None:
    """Write content to path durably: write to a same-dir temp file, fsync,
    then os.replace. Resilient to crashes leaving truncated/missing files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


# ---------- ID resolution ----------


def resolve_agent_id(manifest: dict, raw_id: str) -> tuple[str, dict]:
    """Resolve a possibly-aliased ID to its canonical entry. Raises ValueError if unknown."""
    agents = manifest["agents"]
    if raw_id in agents:
        return raw_id, agents[raw_id]
    for canonical_id, entry in agents.items():
        if raw_id in (entry.get("aliases") or []):
            return canonical_id, entry
    raise ValueError(f"agent id {raw_id!r} not found in manifest (and no entry lists it as an alias)")


# ---------- merge generation ----------


def build_merged(hr_body: str, hr_frontmatter_block: str, overlay_path: Path | None,
                 agent_id: str) -> tuple[str, dict | None]:
    """Return (merged_text, overlay_meta_or_None).

    overlay_meta is a dict with keys 'last_reviewed', 'overlay_hash_at_apply',
    or None if no overlay applied."""
    base = f"---\n{hr_frontmatter_block}\n---\n{hr_body.rstrip()}\n"
    if overlay_path is None or not overlay_path.exists():
        return base, None

    overlay_text = overlay_path.read_text(encoding="utf-8")
    fm, body = parse_overlay(overlay_text)
    if fm.get("agent_id") and fm["agent_id"] != agent_id:
        raise ValueError(
            f"overlay {overlay_path} has agent_id={fm['agent_id']!r} but is being applied to {agent_id!r}"
        )
    last_reviewed = fm.get("last_reviewed")
    if last_reviewed is None:
        raise ValueError(f"overlay {overlay_path} missing required 'last_reviewed' frontmatter")
    last_reviewed_str = str(last_reviewed)

    overlay_block = (
        f"\n{OVERLAY_BEGIN}\n"
        f"<!-- agent_id: {agent_id} -->\n"
        f"<!-- overlay_source: {REPO_DEFAULTS['overlays_dir']}/{agent_id}.md -->\n"
        f"<!-- overlay_last_reviewed: {last_reviewed_str} -->\n"
        f"<!-- DO NOT EDIT THIS FILE -- edit the overlay source and run /staff apply -->\n\n"
        f"{body.strip()}\n"
        f"\n{OVERLAY_END}\n"
    )
    merged = base + overlay_block
    meta = {
        "last_reviewed": last_reviewed_str,
        "overlay_hash_at_apply": sha256(body),
    }
    return merged, meta


# ---------- input parsing ----------


def parse_input(args: argparse.Namespace) -> tuple[list[str], dict | None]:
    """Returns (agent_ids, suggest_metadata_or_None).

    suggest_metadata carries hr_commit and manifest_hash from the suggest JSON
    so apply can detect drift."""
    if args.agents:
        return list(args.agents), None
    if args.from_suggest:
        if args.from_suggest == "-":
            text = sys.stdin.read()
        else:
            text = Path(args.from_suggest).read_text(encoding="utf-8")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"input is not valid JSON: {exc}") from exc
        version = payload.get("schema_version")
        if version != SUGGEST_SCHEMA_VERSION_SUPPORTED:
            raise ValueError(
                f"unsupported suggest schema_version {version!r}; "
                f"this apply expects schema_version={SUGGEST_SCHEMA_VERSION_SUPPORTED}"
            )
        # v1 contract: hr_commit and manifest_hash are required for drift safety.
        # If either is missing, the payload is malformed and apply must reject it.
        if not payload.get("hr_commit"):
            raise ValueError(
                "suggest payload missing required 'hr_commit'; cannot drift-check. "
                "Re-run /staff suggest from a git-tracked HR repo."
            )
        if not payload.get("manifest_hash"):
            raise ValueError(
                "suggest payload missing required 'manifest_hash'; cannot drift-check. "
                "Re-run /staff suggest with the current script."
            )
        suggested = payload.get("suggested") or []
        ids = [s["id"] for s in suggested if "id" in s]
        meta = {
            "hr_commit": payload["hr_commit"],
            "manifest_hash": payload["manifest_hash"],
            "hr_repo": payload.get("hr_repo"),
        }
        return ids, meta
    raise ValueError("specify either --agents or --from-suggest")


# ---------- apply ----------


def compute_agent(paths: Paths, agent_id: str, hr_commit: str,
                  manifest_entry: dict) -> tuple[Path, str, dict]:
    """Compute (without writing) the merged content + lock entry for one agent.

    Returns (output_path, merged_content, lock_entry). Raises ValueError on
    any input problem so the caller can abort before writing anything."""
    src = paths.hr_repo / manifest_entry["file"]
    if not src.is_file():
        raise ValueError(f"manifest entry {agent_id!r} points to missing file {src}")

    text = src.read_text(encoding="utf-8")
    fm_block, body, fm = split_agent_file(text)
    description = fm.get("description", "")
    if not description.strip():
        raise ValueError(f"HR agent {agent_id!r} has empty description in {src}")

    overlay_path = paths.overlays_dir / f"{agent_id}.md"
    merged, overlay_meta = build_merged(body, fm_block, overlay_path, agent_id)

    out_path = paths.agents_dir / f"{agent_id}.md"
    entry: dict = {
        "pinned_at": hr_commit,
        "file": manifest_entry["file"],
        "description_hash_at_pin": sha256(description),
        "body_hash_at_pin": sha256(body),
        "generated_hash_at_apply": sha256(merged),
        "overlay": overlay_meta is not None,
    }
    if overlay_meta is not None:
        entry["overlay_path"] = str(overlay_path.relative_to(paths.project_root))
        entry["overlay_hash_at_apply"] = overlay_meta["overlay_hash_at_apply"]
        entry["overlay_last_reviewed"] = overlay_meta["last_reviewed"]
    return out_path, merged, entry


def write_lockfile(paths: Paths, hr_commit: str, staffed: dict) -> None:
    lock = {
        "schema_version": LOCKFILE_SCHEMA_VERSION,
        "hr_repo": f"file://{paths.hr_repo}",
        "hr_commit_pinned": hr_commit,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generated_by": "/staff apply",
        "staffed": dict(sorted(staffed.items())),
    }
    out = yaml.safe_dump(lock, sort_keys=False, width=120, allow_unicode=True)
    atomic_write(paths.lock_path, out)


def main() -> int:
    parser = argparse.ArgumentParser(description="install staffed agents from HR into .claude/agents/")
    parser.add_argument("--project-root", default=".", help="project root (default: cwd)")
    parser.add_argument("--hr-repo", help="HR repo path (overrides config + env)")
    parser.add_argument("--from-suggest", help="path to suggest JSON, or '-' for stdin")
    parser.add_argument("--agents", nargs="+", help="explicit list of agent IDs")
    parser.add_argument("--force", action="store_true",
                        help="proceed despite suggest-vs-HR drift (hr_commit, manifest_hash, or hr_repo mismatch)")
    parser.add_argument("--dry-run", action="store_true", help="report what would happen, write nothing")
    parser.add_argument("--allow-dirty-hr", action="store_true",
                        help="apply even though HR has uncommitted changes (still records HEAD as pin)")
    args = parser.parse_args()

    if args.from_suggest and args.agents:
        print("error: --from-suggest and --agents are mutually exclusive", file=sys.stderr)
        return 2

    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"not a directory: {project_root}", file=sys.stderr)
        return 2

    try:
        hr_repo = resolve_hr_repo(project_root, args.hr_repo)
        if not (hr_repo / "agent.manifest.yaml").is_file():
            raise ValueError(f"not an HR repo (missing agent.manifest.yaml): {hr_repo}")
        manifest = load_manifest(hr_repo)
        agent_ids, suggest_meta = parse_input(args)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not agent_ids:
        print("error: no agents to apply (input was empty)", file=sys.stderr)
        return 2

    # Drift checks against suggest metadata
    if suggest_meta is not None:
        try:
            current_head = hr_head_sha(hr_repo)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if suggest_meta["hr_commit"] != current_head and not args.force:
            print(
                f"error: HR repo has moved since /staff suggest was run\n"
                f"  suggested at: {suggest_meta['hr_commit']}\n"
                f"  HR HEAD now : {current_head}\n"
                f"Re-run /staff suggest, or pass --force to apply against current HEAD anyway.",
                file=sys.stderr,
            )
            return 3
        current_mh = manifest_hash(hr_repo)
        if suggest_meta["manifest_hash"] != current_mh and not args.force:
            print(
                f"error: manifest has changed since /staff suggest was run\n"
                f"  suggested manifest: {suggest_meta['manifest_hash']}\n"
                f"  current manifest  : {current_mh}\n"
                f"Re-run /staff suggest, or pass --force to apply anyway.",
                file=sys.stderr,
            )
            return 3
        # Optional: warn if hr_repo path in payload differs from the resolved HR repo.
        suggest_hr_repo = suggest_meta.get("hr_repo")
        if suggest_hr_repo and Path(suggest_hr_repo).resolve() != hr_repo and not args.force:
            print(
                f"error: HR repo path differs from /staff suggest payload\n"
                f"  suggested HR: {suggest_hr_repo}\n"
                f"  resolved HR : {hr_repo}\n"
                f"Re-run /staff suggest against the same HR repo, or pass --force.",
                file=sys.stderr,
            )
            return 3

    # Refuse to pin a dirty HR
    if not hr_is_clean(hr_repo) and not args.allow_dirty_hr:
        print(
            f"error: HR repo at {hr_repo} has uncommitted changes\n"
            f"Commit or stash them, or pass --allow-dirty-hr (records HEAD as the pin).",
            file=sys.stderr,
        )
        return 4

    try:
        hr_commit = hr_head_sha(hr_repo)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    paths = Paths.from_project(project_root, hr_repo)

    # Resolve all IDs first; fail loud before writing anything
    resolved: list[tuple[str, dict]] = []
    seen: set[str] = set()
    try:
        for raw in agent_ids:
            canonical, entry = resolve_agent_id(manifest, raw)
            if canonical in seen:
                continue
            seen.add(canonical)
            resolved.append((canonical, entry))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"dry-run: would apply {len(resolved)} agents at HR {hr_commit[:12]}")
        for canonical, _ in resolved:
            print(f"  · {canonical}")
        return 0

    # Load existing lockfile so unstaged agents are preserved
    try:
        existing_lock = load_lockfile(paths.lock_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    # Phase 1: compute everything. No writes yet — atomic at the boundary.
    pending: list[tuple[Path, str, str, dict]] = []  # (path, content, agent_id, lock_entry)
    failures: list[str] = []
    for canonical, entry in resolved:
        try:
            out_path, merged, lock_entry = compute_agent(paths, canonical, hr_commit, entry)
        except ValueError as exc:
            failures.append(f"{canonical}: {exc}")
            continue
        pending.append((out_path, merged, canonical, lock_entry))

    if failures:
        for f in failures:
            print(f"error: {f}", file=sys.stderr)
        print(
            f"\n{len(failures)} agent(s) failed to apply. "
            f"No files written; lockfile unchanged.",
            file=sys.stderr,
        )
        return 5

    # Phase 2: write everything atomically. Files first (each via temp+rename),
    # then lockfile. If a file write fails, lockfile is still not advanced.
    staffed = dict(existing_lock.get("staffed") or {})
    for out_path, merged, canonical, lock_entry in pending:
        atomic_write(out_path, merged)
        staffed[canonical] = lock_entry

    write_lockfile(paths, hr_commit, staffed)
    print(f"applied {len(resolved)} agents at HR {hr_commit[:12]} → {paths.agents_dir}")
    print(f"lock: {paths.lock_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
