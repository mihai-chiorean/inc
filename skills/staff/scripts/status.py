#!/usr/bin/env python3
"""/staff status — show staffed/diff/overlay state vs HR HEAD.

Read-only. Reports per-agent state:

  OK              clean: pin matches HR HEAD, generated file untouched, overlay fresh
  HR-DRIFT        HR HEAD has different body_hash or description_hash than the pin
  MANUAL-EDIT     .claude/agents/<id>.md was hand-edited (sha differs from generated_hash_at_apply)
  OVERLAY-EDITED  overlay source body differs from overlay_hash_at_apply
  OVERLAY-STALE   overlay last_reviewed is older than stale_overlay_days (default 90)
  MISSING         agent in lockfile but .claude/agents/<id>.md not on disk
  ORPHAN-FILE     .claude/agents/<id>.md exists but isn't in the lockfile
  ALIAS-RENAMED   lockfile uses a stable id that's now an alias of a renamed agent
  ERROR           couldn't process this entry (see message)

Exit codes:
  0   everything clean
  1   drift / warnings detected (informational)
  2   error (couldn't read lockfile, manifest, etc.)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import yaml

DEFAULT_STALE_OVERLAY_DAYS = 90
LOCKFILE_SCHEMA_VERSION = 1
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
KNOWN_AGENT_KEYS = {"name", "description", "model", "color", "tools"}
KEY_LINE_RE = re.compile(r"^([a-zA-Z_][a-zA-Z0-9_-]*):\s?(.*)$")


# ---------- shared helpers (kept local to script) ----------


def canonicalize_for_hash(s: str) -> str:
    return s.strip()


def sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(canonicalize_for_hash(s).encode("utf-8")).hexdigest()


def parse_agent_frontmatter_permissive(raw: str) -> dict:
    out: dict[str, str] = {}
    current_key: str | None = None
    for line in raw.splitlines():
        m = KEY_LINE_RE.match(line)
        if m and m.group(1) in KNOWN_AGENT_KEYS:
            current_key = m.group(1)
            out[current_key] = m.group(2)
        elif current_key is not None:
            out[current_key] += "\n" + line
    return out


def split_agent_file(text: str) -> tuple[str, str, dict]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("agent file has no frontmatter")
    return m.group(1), m.group(2), parse_agent_frontmatter_permissive(m.group(1))


def parse_overlay(text: str) -> tuple[dict, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("overlay file has no frontmatter")
    fm = yaml.safe_load(m.group(1)) or {}
    if not isinstance(fm, dict):
        raise ValueError("overlay frontmatter must be a mapping")
    return fm, m.group(2)


# ---------- HR / project I/O ----------


def parse_hr_repo_path(value: str) -> Path:
    parsed = urlparse(value)
    if parsed.scheme == "file":
        path = unquote(parsed.path)
    elif parsed.scheme:
        raise ValueError(f"unsupported hr_repo scheme: {parsed.scheme!r}")
    else:
        path = value
    return Path(path).expanduser().resolve()


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


def resolve_hr_repo(project_root: Path, override: str | None, lock_hr_repo: str | None) -> Path:
    cfg = load_project_config(project_root)
    if override:
        return parse_hr_repo_path(override)
    if cfg.get("hr_repo"):
        return parse_hr_repo_path(str(cfg["hr_repo"]))
    if lock_hr_repo:
        return parse_hr_repo_path(lock_hr_repo)
    env = os.environ.get("STAFF_HR_REPO")
    if env:
        return parse_hr_repo_path(env)
    raise ValueError(
        "HR repo not specified — pass --hr-repo, set STAFF_HR_REPO, or write hr_repo: in .claude/staff/config.yaml"
    )


def load_manifest(hr_repo: Path) -> dict:
    p = hr_repo / "agent.manifest.yaml"
    if not p.exists():
        raise ValueError(f"manifest not found at {p}")
    try:
        m = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"manifest at {p} is not valid YAML: {exc}") from exc
    if not isinstance(m, dict) or not isinstance(m.get("agents"), dict):
        raise ValueError(f"manifest at {p} missing 'agents'")
    return m


def load_lockfile(lock_path: Path) -> dict:
    if not lock_path.exists():
        raise ValueError(f"no lockfile at {lock_path}; run /staff apply first")
    try:
        data = yaml.safe_load(lock_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"lockfile at {lock_path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"lockfile at {lock_path} must be a YAML mapping")
    sv = data.get("schema_version")
    if sv is not None and sv != LOCKFILE_SCHEMA_VERSION:
        raise ValueError(
            f"lockfile schema_version={sv} not supported (expected {LOCKFILE_SCHEMA_VERSION})"
        )
    if not isinstance(data.get("staffed"), dict):
        data["staffed"] = {}
    return data


# ---------- per-agent status ----------


@dataclass
class AgentStatus:
    id: str
    canonical_id: str | None  # None if id no longer in manifest
    flags: list[str] = field(default_factory=list)
    detail: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.flags

    def add(self, flag: str, detail: str | None = None) -> None:
        self.flags.append(flag)
        if detail:
            self.detail.append(detail)


def evaluate_staffed_entry(
    agent_id: str,
    lock_entry: dict,
    manifest: dict,
    project_root: Path,
    agents_dir: Path,
    overlays_dir: Path,
    stale_overlay_days: int,
    today: date,
) -> AgentStatus:
    status = AgentStatus(id=agent_id, canonical_id=None)

    # 1. Resolve in manifest (may have been renamed via aliases)
    agents = manifest["agents"]
    canonical_id = agent_id if agent_id in agents else None
    if canonical_id is None:
        for c, e in agents.items():
            if agent_id in (e.get("aliases") or []):
                canonical_id = c
                status.add("ALIAS-RENAMED", f"lockfile id {agent_id!r} is now an alias of {c!r}")
                break
    if canonical_id is None:
        status.add("ERROR", f"agent {agent_id!r} not in manifest (and no aliases match)")
        return status
    status.canonical_id = canonical_id
    manifest_entry = agents[canonical_id]

    # 2. HR drift: compare body and description hashes
    if manifest_entry.get("body_hash") != lock_entry.get("body_hash_at_pin"):
        status.add(
            "HR-DRIFT",
            f"body_hash diverged: pin={short(lock_entry.get('body_hash_at_pin'))}, "
            f"HR HEAD={short(manifest_entry.get('body_hash'))}",
        )
    if manifest_entry.get("description_hash") != lock_entry.get("description_hash_at_pin"):
        status.add(
            "HR-DRIFT",
            f"description_hash diverged: pin={short(lock_entry.get('description_hash_at_pin'))}, "
            f"HR HEAD={short(manifest_entry.get('description_hash'))}",
        )

    # 3. Generated file: missing or hand-edited?
    generated_path = agents_dir / f"{agent_id}.md"
    if not generated_path.is_file():
        status.add("MISSING", f"{generated_path.relative_to(project_root)} not on disk")
    else:
        actual_gen_hash = sha256(generated_path.read_text(encoding="utf-8"))
        expected_gen_hash = lock_entry.get("generated_hash_at_apply")
        if expected_gen_hash and actual_gen_hash != expected_gen_hash:
            status.add(
                "MANUAL-EDIT",
                f"{generated_path.relative_to(project_root)} hash {short(actual_gen_hash)} "
                f"!= apply-time {short(expected_gen_hash)}",
            )

    # 4. Overlay: edited or stale?
    if lock_entry.get("overlay"):
        overlay_path = overlays_dir / f"{agent_id}.md"
        if not overlay_path.is_file():
            status.add("ERROR", f"lockfile says overlay=true but {overlay_path.relative_to(project_root)} missing")
        else:
            try:
                fm, body = parse_overlay(overlay_path.read_text(encoding="utf-8"))
            except (ValueError, yaml.YAMLError) as exc:
                status.add("ERROR", f"overlay parse failed: {exc}")
            else:
                actual_overlay_hash = sha256(body)
                expected_overlay_hash = lock_entry.get("overlay_hash_at_apply")
                if expected_overlay_hash and actual_overlay_hash != expected_overlay_hash:
                    status.add(
                        "OVERLAY-EDITED",
                        f"overlay body hash {short(actual_overlay_hash)} != apply-time "
                        f"{short(expected_overlay_hash)}",
                    )
                last_reviewed = fm.get("last_reviewed")
                if last_reviewed:
                    try:
                        lr_date = (
                            last_reviewed
                            if isinstance(last_reviewed, date)
                            else date.fromisoformat(str(last_reviewed))
                        )
                        age = (today - lr_date).days
                        if age > stale_overlay_days:
                            status.add(
                                "OVERLAY-STALE",
                                f"last_reviewed {lr_date.isoformat()} is {age}d old "
                                f"(threshold {stale_overlay_days}d)",
                            )
                    except (ValueError, TypeError):
                        status.add("ERROR", f"overlay last_reviewed not a valid date: {last_reviewed!r}")

    return status


def short(h: str | None) -> str:
    if not h:
        return "<missing>"
    if h.startswith("sha256:"):
        return h[7:19]
    return h[:12]


def find_orphans(staffed: dict, agents_dir: Path) -> list[str]:
    if not agents_dir.is_dir():
        return []
    orphans: list[str] = []
    for p in sorted(agents_dir.glob("*.md")):
        if p.stem not in staffed:
            orphans.append(p.stem)
    return orphans


# ---------- output ----------


def emit_text(
    project_root: Path,
    hr_repo: Path,
    lock: dict,
    statuses: list[AgentStatus],
    orphans: list[str],
) -> None:
    print(f"project: {project_root}")
    print(f"hr_repo: {hr_repo}")
    print(f"hr_commit_pinned: {short(lock.get('hr_commit_pinned'))}")
    print(f"staffed: {len(statuses)} agents, orphan files: {len(orphans)}\n")

    if not statuses and not orphans:
        print("(no agents staffed)")
        return

    n_clean = sum(1 for s in statuses if s.ok)
    n_dirty = len(statuses) - n_clean

    if n_clean:
        print(f"OK ({n_clean}):")
        for s in statuses:
            if s.ok:
                print(f"  {s.id}")
        print()

    if n_dirty:
        print(f"NEEDS ATTENTION ({n_dirty}):")
        for s in statuses:
            if not s.ok:
                tags = " ".join(f"[{f}]" for f in dedup(s.flags))
                print(f"  {s.id}  {tags}")
                for d in s.detail:
                    print(f"    · {d}")
        print()

    if orphans:
        print(f"ORPHAN-FILE ({len(orphans)}):")
        for o in orphans:
            print(f"  {o}  (in .claude/agents/ but not in lockfile — staff or remove)")
        print()

    print("Next:")
    if n_dirty or orphans:
        print("  /staff sync         # pull HR updates (when MIT-290 lands)")
        print("  /staff apply --agents <id>...   # re-apply specific agents")
    else:
        print("  All staffed agents match HR HEAD; nothing to do.")


def emit_json(
    project_root: Path,
    hr_repo: Path,
    lock: dict,
    statuses: list[AgentStatus],
    orphans: list[str],
) -> str:
    payload = {
        "schema_version": 1,
        "project_root": str(project_root),
        "hr_repo": str(hr_repo),
        "hr_commit_pinned": lock.get("hr_commit_pinned"),
        "staffed": [
            {
                "id": s.id,
                "canonical_id": s.canonical_id,
                "ok": s.ok,
                "flags": dedup(s.flags),
                "detail": s.detail,
            }
            for s in statuses
        ],
        "orphan_files": orphans,
    }
    return json.dumps(payload, indent=2)


def dedup(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


# ---------- main ----------


def main() -> int:
    parser = argparse.ArgumentParser(description="show staffed/drift/overlay state")
    parser.add_argument("--project-root", default=".", help="project root (default: cwd)")
    parser.add_argument("--hr-repo", help="HR repo path override")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--stale-overlay-days", type=int, default=None,
                        help=f"override stale-overlay threshold (default: {DEFAULT_STALE_OVERLAY_DAYS} or config value)")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"not a directory: {project_root}", file=sys.stderr)
        return 2

    lock_path = project_root / ".claude/staff/lock.yaml"
    try:
        lock = load_lockfile(lock_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        cfg = load_project_config(project_root)
        hr_repo = resolve_hr_repo(project_root, args.hr_repo, lock.get("hr_repo"))
        if not (hr_repo / "agent.manifest.yaml").is_file():
            raise ValueError(f"not an HR repo (missing agent.manifest.yaml): {hr_repo}")
        manifest = load_manifest(hr_repo)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    stale_days = (
        args.stale_overlay_days
        if args.stale_overlay_days is not None
        else cfg.get("stale_overlay_days", DEFAULT_STALE_OVERLAY_DAYS)
    )

    agents_dir = project_root / ".claude/agents"
    overlays_dir = project_root / ".claude/staff/overlays"

    today = datetime.now().date()
    statuses: list[AgentStatus] = []
    for aid, entry in sorted((lock.get("staffed") or {}).items()):
        if not isinstance(entry, dict):
            statuses.append(AgentStatus(id=aid, canonical_id=None, flags=["ERROR"],
                                        detail=[f"lockfile entry for {aid} is not a mapping"]))
            continue
        statuses.append(
            evaluate_staffed_entry(
                aid, entry, manifest, project_root, agents_dir, overlays_dir, stale_days, today
            )
        )
    orphans = find_orphans(lock.get("staffed") or {}, agents_dir)

    if args.json:
        print(emit_json(project_root, hr_repo, lock, statuses, orphans))
    else:
        emit_text(project_root, hr_repo, lock, statuses, orphans)

    has_drift = any(not s.ok for s in statuses) or bool(orphans)
    return 1 if has_drift else 0


if __name__ == "__main__":
    sys.exit(main())
