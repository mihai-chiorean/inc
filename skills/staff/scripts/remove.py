#!/usr/bin/env python3
"""/staff remove <id...> — drop agents from the staffed set.

Removes .claude/agents/<id>.md and the lockfile entry. Leaves
.claude/staff/overlays/<id>.md untouched (with a warning if present),
since overlays are project-owned content that may want to be preserved
or hand-removed by the user.

Errors:
  agent-not-currently-staffed    — id isn't in the lockfile (typo guard)
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply as apply_mod  # type: ignore

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description="remove agents from the staffed set")
    parser.add_argument("agents", nargs="+", help="stable agent IDs to remove")
    parser.add_argument("--project-root", default=".", help="project root (default: cwd)")
    parser.add_argument("--dry-run", action="store_true", help="report what would happen, write nothing")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"not a directory: {project_root}", file=sys.stderr)
        return 2

    paths = apply_mod.Paths.from_project(project_root, project_root)  # hr_repo unused for remove
    try:
        existing_lock = apply_mod.load_lockfile(paths.lock_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not paths.lock_path.exists():
        print(f"error: no lockfile at {paths.lock_path}; nothing to remove", file=sys.stderr)
        return 2

    staffed = dict(existing_lock.get("staffed") or {})
    not_staffed: list[str] = []
    to_remove: list[str] = []
    seen: set[str] = set()
    for raw in args.agents:
        if raw in seen:
            continue
        seen.add(raw)
        if raw not in staffed:
            not_staffed.append(raw)
        else:
            to_remove.append(raw)

    if not_staffed:
        print(
            f"error: agent-not-currently-staffed: {', '.join(sorted(not_staffed))}",
            file=sys.stderr,
        )
        return 7

    if not to_remove:
        print("error: no agents to remove", file=sys.stderr)
        return 2

    overlays_to_warn: list[Path] = []
    for aid in to_remove:
        overlay_path = paths.overlays_dir / f"{aid}.md"
        if overlay_path.exists():
            overlays_to_warn.append(overlay_path)

    if args.dry_run:
        print(f"dry-run: would remove {len(to_remove)} agents")
        for aid in to_remove:
            print(f"  · {aid}")
        for op in overlays_to_warn:
            print(f"  ! overlay preserved: {op.relative_to(project_root)} (hand-remove if no longer needed)")
        return 0

    # Carry forward hr_repo + hr_commit_pinned from existing lockfile (we don't
    # need to consult HR for a pure remove, and changing the pin would be
    # surprising).
    hr_commit = existing_lock.get("hr_commit_pinned", "0" * 40)
    hr_repo_str = existing_lock.get("hr_repo", "")

    # Delete agent files
    for aid in to_remove:
        out_path = paths.agents_dir / f"{aid}.md"
        if out_path.exists():
            out_path.unlink()
        del staffed[aid]

    # Re-write lockfile preserving hr_repo + hr_commit_pinned from before
    lock = {
        "schema_version": apply_mod.LOCKFILE_SCHEMA_VERSION,
        "hr_repo": hr_repo_str,
        "hr_commit_pinned": hr_commit,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generated_by": "/staff remove",
        "staffed": dict(sorted(staffed.items())),
    }
    out = yaml.safe_dump(lock, sort_keys=False, width=120, allow_unicode=True)
    apply_mod.atomic_write(paths.lock_path, out)

    print(f"removed {len(to_remove)} agents from {paths.agents_dir}")
    if overlays_to_warn:
        print(f"\n{len(overlays_to_warn)} overlay(s) preserved (project-owned, not auto-deleted):")
        for op in overlays_to_warn:
            print(f"  ! {op.relative_to(project_root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
