#!/usr/bin/env python3
"""/staff rif <agent-id> [--project|--global|--everywhere] — un-staff an agent.

The symmetric counterpart of /staff promote. Three modes:

  --project (default when run in a project with a lockfile)
      Drop the agent from <project>/.claude/agents/<id>.md and the
      project lockfile's staffed: map. Idempotent — exit 0 if the agent
      isn't currently staffed in the project.

  --global
      Demote the agent from org scope: rewrite frontmatter to
      scope: project, regenerate agent.manifest.yaml, and remove the
      ~/.claude/agents/<id>.md user-scope entry IF it's a symlink into
      this HR repo. Refuses by default if any project lockfile references
      the agent (override with --force).

  --everywhere
      Do both: project-side removal plus global demotion.

Safety guards (per MIT-377):
  - --global without --force refuses if any project lockfile under
    ~/.inc/projects/*/lock.yaml references the agent. Override path can
    be set via STAFF_PROJECTS_DIR env var (for tests).
  - We only delete ~/.claude/agents/<id>.md when it's a symlink whose
    resolved target lives under the HR repo. A real file (e.g., a
    hand-edited copy) is preserved and a warning is printed.

Exit codes:
  0   removed (or already absent at the requested scope)
  2   agent not in manifest, bad args, HR repo not resolvable, etc.
  8   refused: --global would orphan a project that still references the
      agent (re-run with --force after staff-rif'ing those projects)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply as apply_mod  # type: ignore
import promote as promote_mod  # type: ignore

import yaml


PROJECTS_DIR_ENV = "STAFF_PROJECTS_DIR"
DEFAULT_PROJECTS_DIR = Path.home() / ".inc" / "projects"
USER_AGENTS_DIR_ENV = "STAFF_USER_AGENTS_DIR"
DEFAULT_USER_AGENTS_DIR = Path.home() / ".claude" / "agents"


def projects_dir() -> Path:
    env = os.environ.get(PROJECTS_DIR_ENV)
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_PROJECTS_DIR


def user_agents_dir() -> Path:
    env = os.environ.get(USER_AGENTS_DIR_ENV)
    if env:
        return Path(env).expanduser().resolve()
    return DEFAULT_USER_AGENTS_DIR


def _lockfile_references(lock_path: Path, needles: set[str]) -> bool:
    """True if the lockfile at lock_path lists any of `needles` under staffed:."""
    try:
        data = yaml.safe_load(lock_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return False
    staffed = data.get("staffed") if isinstance(data, dict) else None
    if not isinstance(staffed, dict):
        return False
    return bool(needles & set(staffed.keys()))


def find_projects_referencing(
    agent_id: str, aliases: list[str], extra_project_root: Path | None = None,
) -> list[Path]:
    """Best-effort scan for any project lockfile whose staffed: map contains
    the given agent id (or any of its aliases). Returns lockfile paths.

    Scans ~/.inc/projects/*/lock.yaml and */.claude/staff/lock.yaml under
    the projects_dir() root. If extra_project_root is provided, its
    .claude/staff/lock.yaml is also checked — this covers the case where
    the caller is standing in a project that isn't indexed under
    ~/.inc/projects/ but is itself a consumer of the agent."""
    pdir = projects_dir()
    candidates: list[Path] = []
    if pdir.is_dir():
        candidates.extend(sorted(pdir.glob("*/lock.yaml")))
        candidates.extend(sorted(pdir.glob("*/.claude/staff/lock.yaml")))
    if extra_project_root is not None:
        extra = extra_project_root / ".claude/staff/lock.yaml"
        if extra.is_file() and extra not in candidates:
            candidates.append(extra)
    needles = {agent_id, *aliases}
    return [p for p in candidates if _lockfile_references(p, needles)]


def find_user_scope_path(agent_id: str) -> Path | None:
    """Locate ~/.claude/agents/<id>.md (or under a category subdir).

    install.sh installs into ~/.claude/agents/<category>/<id>.md, so we
    look at both the flat path and the recursive case. Returns None if
    nothing matches."""
    udir = user_agents_dir()
    if not udir.is_dir():
        return None
    flat = udir / f"{agent_id}.md"
    if flat.exists() or flat.is_symlink():
        return flat
    # install.sh categorises agents under <category>/<id>.md
    for candidate in udir.rglob(f"{agent_id}.md"):
        if candidate.name == "README.md":
            continue
        return candidate
    return None


def is_symlink_into(path: Path, root: Path) -> bool:
    """True if `path` is a symlink whose resolved target is under `root`.

    We never delete a non-symlink at ~/.claude/agents/<id>.md — that
    would mean clobbering a user-edited file. We also refuse to delete
    a symlink pointing outside this HR repo."""
    if not path.is_symlink():
        return False
    try:
        target = path.resolve(strict=False)
        root_resolved = root.resolve(strict=False)
    except OSError:
        return False
    try:
        target.relative_to(root_resolved)
    except ValueError:
        return False
    return True


def remove_user_scope_entry(agent_id: str, hr_repo: Path) -> tuple[bool, str]:
    """Remove the user-scope symlink for `agent_id` if and only if it's a
    symlink whose target resolves under `hr_repo`.

    Returns (removed, message). `removed` is True if we deleted the entry,
    False if it didn't exist or we declined to touch it."""
    user_path = find_user_scope_path(agent_id)
    if user_path is None:
        return False, f"no user-scope entry for {agent_id}"
    if not user_path.exists() and not user_path.is_symlink():
        return False, f"no user-scope entry for {agent_id}"
    if not is_symlink_into(user_path, hr_repo):
        return False, (
            f"refusing to delete {user_path} — not a symlink into {hr_repo}. "
            "It looks like a hand-edited copy; remove it by hand if you really "
            "want it gone."
        )
    try:
        user_path.unlink()
    except OSError as exc:
        return False, f"failed to delete {user_path}: {exc}"
    return True, f"removed user-scope symlink {user_path}"


def run_project_rif(agent: str, project_root: Path) -> int:
    """Project-side removal: idempotent. If the agent isn't in the project
    lockfile we exit 0 with an informational message — unlike /staff
    remove, /staff rif --project is intended to be safe to run repeatedly."""
    lock_path = project_root / ".claude/staff/lock.yaml"
    if not lock_path.exists():
        print(f"no lockfile at {lock_path}; nothing to remove (project-side)")
        return 0
    try:
        lock = apply_mod.load_lockfile(lock_path)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    staffed = dict(lock.get("staffed") or {})
    # Try to resolve through aliases if the manifest is reachable.
    canonical = agent
    hr_repo_str = lock.get("hr_repo", "")
    if hr_repo_str:
        try:
            hr_repo = apply_mod.parse_hr_repo_path(hr_repo_str)
            if (hr_repo / "agent.manifest.yaml").is_file():
                manifest = apply_mod.load_manifest(hr_repo)
                try:
                    canonical, _ = apply_mod.resolve_agent_id(manifest, agent)
                except ValueError:
                    pass
        except (ValueError, yaml.YAMLError):
            pass

    if canonical not in staffed and agent not in staffed:
        print(f"{agent}: not installed in this project (no-op)")
        return 0

    # Delegate to remove.py — re-running its CLI keeps the lockfile-write
    # logic in one place.
    remove_script = Path(__file__).resolve().parent / "remove.py"
    result = subprocess.run(
        [sys.executable, str(remove_script), agent,
         "--project-root", str(project_root)],
        check=False,
    )
    return result.returncode


def run_global_rif(agent: str, hr_repo: Path, project_root: Path | None,
                   force: bool, dry_run: bool) -> int:
    """Global demote: scope: project in frontmatter + regen manifest +
    remove user-scope symlink (if owned by this HR repo). Refuses without
    --force if any project lockfile under ~/.inc/projects/ still references
    the agent."""
    try:
        manifest = apply_mod.load_manifest(hr_repo)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        canonical, entry = apply_mod.resolve_agent_id(manifest, agent)
    except ValueError as exc:
        print(f"error: agent-not-in-manifest: {exc}", file=sys.stderr)
        return 2

    aliases = list(entry.get("aliases") or [])
    if not force:
        referencing = find_projects_referencing(
            canonical, aliases, extra_project_root=project_root,
        )
        if referencing:
            print(
                f"error: refusing to demote {canonical} — still referenced by "
                f"{len(referencing)} project lockfile(s):",
                file=sys.stderr,
            )
            for p in referencing:
                print(f"  · {p}", file=sys.stderr)
            print(
                "Run /staff rif --project in each, or re-run with --force.",
                file=sys.stderr,
            )
            return 8

    agent_path = hr_repo / entry["file"]
    if not agent_path.is_file():
        print(f"error: manifest entry {canonical!r} points to missing file {agent_path}",
              file=sys.stderr)
        return 2

    text = agent_path.read_text(encoding="utf-8")
    try:
        current = promote_mod.read_scope_from_frontmatter(text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    user_path = find_user_scope_path(canonical)
    user_owned_symlink = (
        user_path is not None and is_symlink_into(user_path, hr_repo)
    )

    if current == "project" and not user_owned_symlink:
        if user_path is not None:
            print(
                f"{canonical}: already project scope; user-scope entry at "
                f"{user_path} is not ours — leaving it alone."
            )
        else:
            print(f"{canonical}: not at global scope (no-op)")
        return 0

    if dry_run:
        if current == "org":
            print(f"dry-run: would set scope: project in {agent_path.relative_to(hr_repo)}")
            print("dry-run: would regenerate agent.manifest.yaml")
        if user_owned_symlink:
            print(f"dry-run: would remove user-scope symlink {user_path}")
        return 0

    if current == "org":
        try:
            new_text = promote_mod.set_scope_in_frontmatter(text, "project")
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        apply_mod.atomic_write(agent_path, new_text)
        print(f"{canonical}: scope org -> project ({agent_path.relative_to(hr_repo)})")
        try:
            promote_mod.regenerate_manifest(hr_repo)
        except (subprocess.CalledProcessError, ValueError) as exc:
            print(f"error: failed to regenerate manifest: {exc}", file=sys.stderr)
            return 2

    if user_path is not None:
        removed, msg = remove_user_scope_entry(canonical, hr_repo)
        if removed:
            print(msg)
        else:
            # Either we declined (non-symlink) or it wasn't there. Print as
            # a warning if it still exists but isn't ours.
            if user_path.exists() and not is_symlink_into(user_path, hr_repo):
                print(f"warning: {msg}", file=sys.stderr)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="un-staff an agent at project, global, or both scopes",
    )
    parser.add_argument("agent", help="stable agent id")
    scope_group = parser.add_mutually_exclusive_group()
    scope_group.add_argument(
        "--project", dest="scope", action="store_const", const="project",
        help="remove from current project only (default if a project lockfile is present)",
    )
    scope_group.add_argument(
        "--global", dest="scope", action="store_const", const="global",
        help="demote from org scope in the HR repo + drop user-scope symlink",
    )
    scope_group.add_argument(
        "--everywhere", dest="scope", action="store_const", const="everywhere",
        help="both --project and --global",
    )
    parser.add_argument("--project-root", default=".", help="project root (default: cwd)")
    parser.add_argument("--hr-repo", help="HR repo path (overrides config + env)")
    parser.add_argument(
        "--force", action="store_true",
        help="for --global: proceed even if other project lockfiles reference the agent",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report what would happen, write nothing",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()

    # Decide the scope if the user didn't pass one. Default to --project if
    # we're in a project with a lockfile; otherwise default to --global.
    scope = args.scope
    if scope is None:
        if (project_root / ".claude/staff/lock.yaml").exists():
            scope = "project"
        else:
            scope = "global"

    rc = 0

    if scope in {"project", "everywhere"}:
        rc_p = run_project_rif(args.agent, project_root)
        if rc_p != 0:
            return rc_p
        rc = max(rc, rc_p)

    if scope in {"global", "everywhere"}:
        try:
            hr_repo = apply_mod.resolve_hr_repo(project_root, args.hr_repo)
            if not (hr_repo / "agent.manifest.yaml").is_file():
                raise ValueError(f"not an HR repo (missing agent.manifest.yaml): {hr_repo}")
        except (ValueError, yaml.YAMLError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        rc_g = run_global_rif(
            args.agent, hr_repo, project_root=project_root,
            force=args.force, dry_run=args.dry_run,
        )
        if rc_g != 0:
            return rc_g
        rc = max(rc, rc_g)

    return rc


if __name__ == "__main__":
    sys.exit(main())
