#!/usr/bin/env python3
"""staff audit — scan multiple projects, aggregate suggested rosters, and
identify HR agents that no project actually wants (retirement candidates).

The migration use case: you have ~58 agents installed user-scope at
~/.claude/agents/, and you want to know which ones to retire from global
because every project that needs them will staff them locally via
/staff suggest+apply. This script gives you the data.

Beyond migration, useful as an ongoing audit: which projects haven't
been staffed yet? Which agents are everywhere? Which are nowhere?

Inputs:
  --projects PATH    repeatable; explicit project root(s) to scan
  --workspace DIR    scan DIR/* for git-rooted project candidates
                     (default: $HOME/workspace if no --projects)
  --hr-repo PATH     HR repo (else STAFF_HR_REPO env)
  --no-llm           skip the LLM in suggest (faster, slightly less precise)
  --json             emit machine-readable JSON instead of text

Outputs (text mode):
  Per-project summary: staffed yet?, suggested roster, command to apply
  Aggregate: agents proposed somewhere
  Retirement candidates: agents in ~/.claude/agents/ that NO project wants
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SUGGEST = Path(__file__).resolve().parent / "suggest.py"


@dataclass
class ProjectAudit:
    path: Path
    name: str
    is_git_repo: bool
    has_lockfile: bool
    suggested: list[str] = field(default_factory=list)
    error: str | None = None


def is_git_root(p: Path) -> bool:
    return (p / ".git").exists() or (p / ".git").is_file()


def discover_projects(workspace: Path) -> list[Path]:
    if not workspace.is_dir():
        return []
    out: list[Path] = []
    for child in sorted(workspace.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        if is_git_root(child):
            out.append(child)
    return out


def list_user_scope_agents(scope_dir: Path) -> set[str]:
    """Read ~/.claude/agents/ recursively and return the set of agent ids
    (filename stem)."""
    if not scope_dir.is_dir():
        return set()
    out: set[str] = set()
    for p in scope_dir.rglob("*.md"):
        if p.name == "README.md":
            continue
        out.add(p.stem)
    return out


def run_suggest(project: Path, hr_repo: Path, no_llm: bool) -> tuple[list[str], str | None]:
    cmd = [
        sys.executable, str(SUGGEST),
        "--project-root", str(project),
        "--hr-repo", str(hr_repo),
        "--json",
    ]
    if no_llm:
        cmd.append("--no-llm")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return [], result.stderr.strip().splitlines()[0] if result.stderr else f"exit {result.returncode}"
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return [], f"non-JSON output: {exc}"
    return [s["id"] for s in payload.get("suggested", [])], None


def audit_project(project: Path, hr_repo: Path, no_llm: bool) -> ProjectAudit:
    audit = ProjectAudit(
        path=project, name=project.name,
        is_git_repo=is_git_root(project),
        has_lockfile=(project / ".claude/staff/lock.yaml").exists(),
    )
    suggested, err = run_suggest(project, hr_repo, no_llm)
    audit.suggested = suggested
    audit.error = err
    return audit


def emit_text(audits: list[ProjectAudit], retirement: list[str], all_proposed: set[str],
              user_scope: set[str], hr_repo: Path) -> None:
    print(f"hr_repo: {hr_repo}")
    print(f"user_scope: {len(user_scope)} agents in ~/.claude/agents/")
    print(f"projects scanned: {len(audits)}\n")

    staffed = [a for a in audits if a.has_lockfile]
    unstaffed = [a for a in audits if not a.has_lockfile and a.error is None]
    failed = [a for a in audits if a.error is not None]

    if staffed:
        print(f"[STAFFED ({len(staffed)})] — already have .claude/staff/lock.yaml")
        for a in staffed:
            ids = ", ".join(a.suggested) if a.suggested else "(suggest returned empty)"
            print(f"  {a.name:<40} suggested: {ids}")
        print()

    if unstaffed:
        print(f"[UNSTAFFED ({len(unstaffed)})] — candidates for `staff apply`")
        for a in unstaffed:
            ids = ", ".join(a.suggested) if a.suggested else "(no agents matched)"
            print(f"  {a.name}")
            print(f"    suggested: {ids}")
            if a.suggested:
                print(f"    cd {a.path} && staff suggest --json | staff apply --from-suggest -")
            print()

    if failed:
        print(f"[FAILED ({len(failed)})] — suggest errored")
        for a in failed:
            print(f"  {a.name:<40} error: {a.error}")
        print()

    print(f"[AGGREGATE] proposed across all projects: {len(all_proposed)}")
    if all_proposed:
        print(f"  {', '.join(sorted(all_proposed))}")
    print()

    if retirement:
        print(f"[RETIREMENT CANDIDATES ({len(retirement)})] — in ~/.claude/agents/ but no project staffs them")
        print("  These are safe to consider removing from global once all your projects are staffed.")
        print(f"  {', '.join(retirement)}")
        print()
        print("  Manual prune (review first; this script never deletes):")
        print("    for a in", " ".join(retirement[:5]) + (" …" if len(retirement) > 5 else ""), "; do")
        print("      find ~/.claude/agents -name \"$a.md\" -delete")
        print("    done")
    else:
        print("[RETIREMENT CANDIDATES] none — every user-scope agent is wanted by at least one project.")


def emit_json(audits: list[ProjectAudit], retirement: list[str], all_proposed: set[str],
              user_scope: set[str], hr_repo: Path) -> str:
    return json.dumps({
        "schema_version": 1,
        "hr_repo": str(hr_repo),
        "user_scope_count": len(user_scope),
        "projects": [
            {
                "name": a.name,
                "path": str(a.path),
                "is_git_repo": a.is_git_repo,
                "has_lockfile": a.has_lockfile,
                "suggested": a.suggested,
                "error": a.error,
            }
            for a in audits
        ],
        "all_proposed": sorted(all_proposed),
        "retirement_candidates": retirement,
    }, indent=2)


def resolve_hr_repo(override: str | None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    env = os.environ.get("STAFF_HR_REPO")
    if env:
        return Path(env).expanduser().resolve()
    raise SystemExit(
        "HR repo not specified — pass --hr-repo or set STAFF_HR_REPO"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="audit projects vs HR roster")
    parser.add_argument("--projects", nargs="+", default=[],
                        help="explicit project root(s) to scan; takes one or more paths")
    parser.add_argument("--workspace",
                        help="scan DIR/* for git-rooted projects (default: $HOME/workspace)")
    parser.add_argument("--hr-repo", help="HR repo (else STAFF_HR_REPO)")
    parser.add_argument("--user-scope-dir", default=str(Path.home() / ".claude/agents"),
                        help="path to user-scope agents dir (default: ~/.claude/agents)")
    parser.add_argument("--no-llm", action="store_true", help="run suggest in deterministic mode")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    args = parser.parse_args()

    hr_repo = resolve_hr_repo(args.hr_repo)
    if not (hr_repo / "agent.manifest.yaml").is_file():
        print(f"error: not an HR repo (missing agent.manifest.yaml): {hr_repo}", file=sys.stderr)
        return 2

    if args.projects:
        project_roots = [Path(p).expanduser().resolve() for p in args.projects]
    else:
        workspace = Path(args.workspace).expanduser().resolve() if args.workspace else Path.home() / "workspace"
        project_roots = discover_projects(workspace)
        if not project_roots:
            print(f"error: no git-rooted projects found in {workspace}", file=sys.stderr)
            print("hint: pass --projects PATH (repeatable) to specify them explicitly.", file=sys.stderr)
            return 2

    user_scope = list_user_scope_agents(Path(args.user_scope_dir).expanduser())

    audits: list[ProjectAudit] = []
    for project in project_roots:
        if not project.is_dir():
            audits.append(ProjectAudit(
                path=project, name=project.name, is_git_repo=False,
                has_lockfile=False, error="not a directory",
            ))
            continue
        audits.append(audit_project(project, hr_repo, args.no_llm))

    all_proposed: set[str] = set()
    for a in audits:
        all_proposed.update(a.suggested)

    # Retirement candidates: in user_scope but never proposed
    # Excludes truly-global agents (hardcoded list — kept short and obvious)
    truly_global = {
        "hiring-manager", "agent-eval-engineer", "blog-writer",
        "joker", "studio-coach", "studio-producer",
    }
    retirement = sorted(user_scope - all_proposed - truly_global)

    if args.json:
        print(emit_json(audits, retirement, all_proposed, user_scope, hr_repo))
    else:
        emit_text(audits, retirement, all_proposed, user_scope, hr_repo)

    # Exit 1 if any retirement candidates or unstaffed projects (informational)
    has_unstaffed = any(not a.has_lockfile and a.error is None for a in audits)
    return 1 if (retirement or has_unstaffed) else 0


if __name__ == "__main__":
    sys.exit(main())
