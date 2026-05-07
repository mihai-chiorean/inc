#!/usr/bin/env python3
"""/staff add <id...> — add agents to the staffed set.

Thin wrapper over apply.py's logic that additionally rejects agents already
in the lockfile. Use /staff sync (when MIT-290 lands) or apply --agents
explicitly to refresh an existing entry.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Reuse apply's primitives. They're in the same directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply as apply_mod  # type: ignore

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description="add agents to the staffed set")
    parser.add_argument("agents", nargs="+", help="stable agent IDs to add")
    parser.add_argument("--project-root", default=".", help="project root (default: cwd)")
    parser.add_argument("--hr-repo", help="HR repo path (overrides config + env)")
    parser.add_argument("--allow-dirty-hr", action="store_true",
                        help="apply even though HR has uncommitted changes")
    parser.add_argument("--dry-run", action="store_true", help="report what would happen, write nothing")
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    if not project_root.is_dir():
        print(f"not a directory: {project_root}", file=sys.stderr)
        return 2

    try:
        hr_repo = apply_mod.resolve_hr_repo(project_root, args.hr_repo)
        if not (hr_repo / "agent.manifest.yaml").is_file():
            raise ValueError(f"not an HR repo (missing agent.manifest.yaml): {hr_repo}")
        manifest = apply_mod.load_manifest(hr_repo)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    paths = apply_mod.Paths.from_project(project_root, hr_repo)
    try:
        existing_lock = apply_mod.load_lockfile(paths.lock_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    existing_staffed = dict(existing_lock.get("staffed") or {})

    # Resolve and check for already-staffed
    resolved: list[tuple[str, dict]] = []
    seen: set[str] = set()
    already: list[str] = []
    try:
        for raw in args.agents:
            canonical, entry = apply_mod.resolve_agent_id(manifest, raw)
            if canonical in seen:
                continue
            seen.add(canonical)
            if canonical in existing_staffed:
                already.append(canonical)
                continue
            resolved.append((canonical, entry))
    except ValueError as exc:
        print(f"error: agent-not-in-manifest: {exc}", file=sys.stderr)
        return 2

    if already:
        print(
            f"error: agent-already-staffed: {', '.join(sorted(already))}\n"
            f"Use `/staff sync` (or apply --agents <id> --force) to refresh an existing entry.",
            file=sys.stderr,
        )
        return 6

    if not resolved:
        print("error: no agents to add", file=sys.stderr)
        return 2

    # Refuse dirty HR like apply does
    if not apply_mod.hr_is_clean(hr_repo) and not args.allow_dirty_hr:
        print(
            f"error: HR repo at {hr_repo} has uncommitted changes\n"
            f"Commit or stash them, or pass --allow-dirty-hr (records HEAD as the pin).",
            file=sys.stderr,
        )
        return 4

    try:
        hr_commit = apply_mod.hr_head_sha(hr_repo)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"dry-run: would add {len(resolved)} agents at HR {hr_commit[:12]}")
        for canonical, _ in resolved:
            print(f"  · {canonical}")
        return 0

    # Phase 1: compute everything (atomic boundary)
    pending: list[tuple[Path, str, str, dict]] = []
    failures: list[str] = []
    for canonical, entry in resolved:
        try:
            out_path, merged, lock_entry = apply_mod.compute_agent(paths, canonical, hr_commit, entry)
        except ValueError as exc:
            failures.append(f"{canonical}: {exc}")
            continue
        pending.append((out_path, merged, canonical, lock_entry))

    if failures:
        for f in failures:
            print(f"error: {f}", file=sys.stderr)
        print(f"\n{len(failures)} agent(s) failed to add. No files written.", file=sys.stderr)
        return 5

    # Phase 2: write
    staffed = dict(existing_staffed)
    for out_path, merged, canonical, lock_entry in pending:
        apply_mod.atomic_write(out_path, merged)
        staffed[canonical] = lock_entry

    apply_mod.write_lockfile(paths, hr_commit, staffed)
    print(f"added {len(resolved)} agents at HR {hr_commit[:12]} → {paths.agents_dir}")
    print(f"lock: {paths.lock_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
