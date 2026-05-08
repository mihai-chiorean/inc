#!/usr/bin/env python3
"""/staff add <id...> — add agents to the staffed set.

Thin wrapper over apply.py's logic that additionally rejects agents already
in the lockfile. Use /staff sync (when MIT-290 lands) or apply --agents
explicitly to refresh an existing entry.
"""

from __future__ import annotations

import argparse
import os
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

    # Load the lockfile first so we can fall back to its hr_repo if no override
    # is given (matches /staff status behavior).
    lock_path = project_root / ".claude/staff/lock.yaml"
    existing_lock: dict = {}
    lock_hr_repo: str | None = None
    if lock_path.exists():
        try:
            existing_lock = apply_mod.load_lockfile(lock_path)
            lock_hr_repo = existing_lock.get("hr_repo")
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    # Resolve HR repo with priority: --hr-repo > config > lockfile > env.
    # Note: this is one slot deeper than apply.py's resolve_hr_repo, which
    # has no lockfile fallback (apply has no committed prior state to fall
    # back on, so config|env is sufficient there).
    try:
        if args.hr_repo:
            hr_repo = apply_mod.parse_hr_repo_path(args.hr_repo)
        else:
            cfg = apply_mod.load_project_config(project_root)
            if cfg.get("hr_repo"):
                hr_repo = apply_mod.parse_hr_repo_path(str(cfg["hr_repo"]))
            elif lock_hr_repo:
                hr_repo = apply_mod.parse_hr_repo_path(lock_hr_repo)
            elif os.environ.get("STAFF_HR_REPO"):
                hr_repo = apply_mod.parse_hr_repo_path(os.environ["STAFF_HR_REPO"])
            else:
                raise ValueError(
                    "HR repo not specified — pass --hr-repo, set STAFF_HR_REPO, "
                    "or stage a lockfile via /staff apply first"
                )
        if not (hr_repo / "agent.manifest.yaml").is_file():
            raise ValueError(f"not an HR repo (missing agent.manifest.yaml): {hr_repo}")
        manifest = apply_mod.load_manifest(hr_repo)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    paths = apply_mod.Paths.from_project(project_root, hr_repo)
    existing_staffed = dict(existing_lock.get("staffed") or {})

    # Normalize existing staffed IDs through current manifest aliases so we
    # detect "already-staffed under the old name" collisions.
    existing_canonical: dict[str, str] = {}  # canonical_id -> lockfile_id
    for lock_id in existing_staffed:
        try:
            canonical, _ = apply_mod.resolve_agent_id(manifest, lock_id)
        except ValueError:
            # Lockfile entry no longer in manifest; status will flag it.
            existing_canonical[lock_id] = lock_id
        else:
            existing_canonical[canonical] = lock_id

    # Resolve requested IDs and check for already-staffed (under any name)
    resolved: list[tuple[str, dict]] = []
    seen: set[str] = set()
    already: list[str] = []
    try:
        for raw in args.agents:
            canonical, entry = apply_mod.resolve_agent_id(manifest, raw)
            if canonical in seen:
                continue
            seen.add(canonical)
            if canonical in existing_canonical:
                lock_name = existing_canonical[canonical]
                if lock_name == canonical:
                    already.append(canonical)
                else:
                    already.append(f"{canonical} (already staffed as alias {lock_name!r})")
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

    # Phase 2: write files. If any write fails, roll back files we just created
    # (only the ones that didn't exist before this add) so the project doesn't
    # end up with orphan files plus a stale lockfile.
    staffed = dict(existing_staffed)
    written_new: list[Path] = []
    try:
        for out_path, merged, canonical, lock_entry in pending:
            new_file = not out_path.exists()
            apply_mod.atomic_write(out_path, merged)
            if new_file:
                written_new.append(out_path)
            staffed[canonical] = lock_entry
        apply_mod.write_lockfile(paths, hr_commit, staffed)
    except Exception as exc:
        # Best-effort rollback: remove any new files we created. Files that
        # already existed are left alone (we could have overwritten them, but
        # that's vanishingly unlikely in an add — they'd be orphans).
        for p in written_new:
            try:
                p.unlink()
            except OSError:
                pass
        print(f"error: write failed during phase 2: {exc}", file=sys.stderr)
        return 5

    print(f"added {len(resolved)} agents at HR {hr_commit[:12]} → {paths.agents_dir}")
    print(f"lock: {paths.lock_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
