#!/usr/bin/env python3
"""/staff promote <agent-id> — flip an agent's scope to `org`.

Promotes an agent from project-scope to org-scope. The HR repo's
`agent.manifest.yaml` is regenerated and `install.sh --link` re-runs so
the agent becomes available at user scope (~/.claude/agents/<id>.md).

Idempotent: re-running on an already-org-scope agent is a no-op (exits 0,
prints "already org", does not touch the file or run install.sh).

Symmetric with /staff rif which demotes back to project scope.

Exit codes:
  0   promoted (or already org)
  2   agent not in manifest, HR repo not resolvable, etc.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply as apply_mod  # type: ignore

import yaml


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
SCOPE_LINE_RE = re.compile(r"^scope:\s*.*$", re.MULTILINE)
NAME_LINE_RE = re.compile(r"^name:\s*.*$", re.MULTILINE)


def read_scope_from_frontmatter(text: str) -> str:
    """Return current scope ('org' or 'project') from the agent .md text.

    Same fallback rule as generate-manifest.py: missing or unrecognised
    values normalise to 'project'."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("agent file has no frontmatter")
    fm_block = m.group(1)
    scope_match = SCOPE_LINE_RE.search(fm_block)
    if not scope_match:
        return "project"
    value = scope_match.group(0).split(":", 1)[1].strip().lower()
    return "org" if value == "org" else "project"


def set_scope_in_frontmatter(text: str, new_scope: str) -> str:
    """Set scope to `new_scope` in the agent .md text.

    Rules:
      - If an existing `scope:` line is present, replace its value in place.
      - Otherwise insert a new `scope: <value>` line directly after `name:`.
      - Never round-trip through yaml.safe_load — the agent frontmatter is
        permissive (unquoted multi-line descriptions) and the existing
        parsers tolerate that. We must preserve the original byte layout.
    """
    if new_scope not in {"org", "project"}:
        raise ValueError(f"invalid scope {new_scope!r} (must be 'org' or 'project')")

    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError("agent file has no frontmatter")
    fm_block = m.group(1)
    body = m.group(2)

    scope_match = SCOPE_LINE_RE.search(fm_block)
    if scope_match:
        new_fm = SCOPE_LINE_RE.sub(f"scope: {new_scope}", fm_block, count=1)
    else:
        name_match = NAME_LINE_RE.search(fm_block)
        if not name_match:
            raise ValueError("agent frontmatter missing required 'name:' line")
        insert_at = name_match.end()
        new_fm = fm_block[:insert_at] + f"\nscope: {new_scope}" + fm_block[insert_at:]

    return f"---\n{new_fm}\n---\n{body}"


def regenerate_manifest(hr_repo: Path) -> None:
    script = hr_repo / "scripts/generate-manifest.py"
    if not script.is_file():
        raise ValueError(f"generate-manifest.py not found at {script}")
    subprocess.run(
        [sys.executable, str(script)],
        cwd=hr_repo,
        check=True,
    )


def reinstall_org_agents(hr_repo: Path) -> None:
    install_sh = hr_repo / "install.sh"
    if not install_sh.is_file():
        raise ValueError(f"install.sh not found at {install_sh}")
    subprocess.run(
        ["bash", str(install_sh), "--link", "--no-cleanup"],
        cwd=hr_repo,
        check=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="promote an agent to org scope (installs at user scope via install.sh --link)",
    )
    parser.add_argument("agent", help="stable agent id (must exist in agent.manifest.yaml)")
    parser.add_argument("--hr-repo", help="HR repo path (overrides config + env)")
    parser.add_argument(
        "--project-root", default=".",
        help="project root used to read .claude/staff/config.yaml for hr_repo (default: cwd)",
    )
    parser.add_argument(
        "--skip-install", action="store_true",
        help="rewrite frontmatter and regenerate manifest, but skip install.sh --link "
             "(useful in tests and CI)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="report what would happen, write nothing",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).expanduser().resolve()

    try:
        hr_repo = apply_mod.resolve_hr_repo(project_root, args.hr_repo)
        if not (hr_repo / "agent.manifest.yaml").is_file():
            raise ValueError(f"not an HR repo (missing agent.manifest.yaml): {hr_repo}")
        manifest = apply_mod.load_manifest(hr_repo)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        canonical, entry = apply_mod.resolve_agent_id(manifest, args.agent)
    except ValueError as exc:
        print(f"error: agent-not-in-manifest: {exc}", file=sys.stderr)
        return 2

    agent_path = hr_repo / entry["file"]
    if not agent_path.is_file():
        print(f"error: manifest entry {canonical!r} points to missing file {agent_path}",
              file=sys.stderr)
        return 2

    text = agent_path.read_text(encoding="utf-8")
    try:
        current = read_scope_from_frontmatter(text)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if current == "org":
        print(f"{canonical}: already org (no changes)")
        return 0

    if args.dry_run:
        print(f"dry-run: would set scope: org in {agent_path.relative_to(hr_repo)}")
        print("dry-run: would regenerate agent.manifest.yaml")
        if not args.skip_install:
            print("dry-run: would re-run install.sh --link from HR repo")
        return 0

    try:
        new_text = set_scope_in_frontmatter(text, "org")
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    apply_mod.atomic_write(agent_path, new_text)
    print(f"{canonical}: scope project -> org ({agent_path.relative_to(hr_repo)})")

    try:
        regenerate_manifest(hr_repo)
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"error: failed to regenerate manifest: {exc}", file=sys.stderr)
        return 2

    if args.skip_install:
        print("skipped install.sh --link (--skip-install)")
        return 0

    try:
        reinstall_org_agents(hr_repo)
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"error: failed to re-run install.sh --link: {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
