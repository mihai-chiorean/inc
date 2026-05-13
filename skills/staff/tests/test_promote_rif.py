#!/usr/bin/env python3
"""Smoke tests for /staff promote and /staff rif (MIT-377).

Uses a temporary HR repo fixture with a tiny manifest (no LLM, no real
install) so we can exercise the frontmatter rewrite, manifest regen, and
project-lockfile scan without touching the user's real ~/.claude or
~/.inc directories.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PROMOTE = REPO_ROOT / "skills/staff/scripts/promote.py"
RIF = REPO_ROOT / "skills/staff/scripts/rif.py"
APPLY = REPO_ROOT / "skills/staff/scripts/apply.py"


def expect(condition: bool, msg: str) -> None:
    if not condition:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


def git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(
        ["git"] + args, cwd=cwd, stderr=subprocess.DEVNULL,
        env={"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
             "PATH": "/usr/bin:/bin", "HOME": str(cwd)},
    ).decode().strip()


def make_fake_hr(root: Path) -> Path:
    """Create a minimal HR-shaped repo with a generate-manifest.py
    and install.sh that exercise the same surface the real ones do."""
    hr = root / "hr"
    hr.mkdir()
    (hr / "engineering").mkdir()
    (hr / "scripts").mkdir()
    (hr / "skills" / "staff" / "scripts").mkdir(parents=True)

    # Two agents: alpha (project), beta (org).
    (hr / "engineering" / "alpha.md").write_text(
        "---\n"
        "name: alpha\n"
        "model: sonnet\n"
        "description: Alpha agent\n"
        "---\n\n"
        "You are alpha.\n",
    )
    (hr / "engineering" / "beta.md").write_text(
        "---\n"
        "name: beta\n"
        "scope: org\n"
        "model: sonnet\n"
        "description: Beta agent\n"
        "---\n\n"
        "You are beta.\n",
    )

    # Copy the real generate-manifest.py over so we exercise it. It depends
    # on skills/staff/scripts/_llm.py being importable.
    real_genmf = REPO_ROOT / "scripts" / "generate-manifest.py"
    (hr / "scripts" / "generate-manifest.py").write_text(real_genmf.read_text())
    real_llm = REPO_ROOT / "skills" / "staff" / "scripts" / "_llm.py"
    (hr / "skills" / "staff" / "scripts" / "_llm.py").write_text(real_llm.read_text())

    # A no-op install.sh — promote re-runs install.sh --link, but for tests
    # we only need to confirm the call happens (or use --skip-install).
    (hr / "install.sh").write_text(
        "#!/bin/bash\n"
        "echo \"fake install.sh called with: $*\"\n"
        "exit 0\n",
    )
    os.chmod(hr / "install.sh", 0o755)

    git(["init", "-q", "-b", "main"], cwd=hr)
    git(["add", "-A"], cwd=hr)
    git(["commit", "-q", "-m", "initial"], cwd=hr)

    # First manifest generation (without LLM summaries — defaults to empty).
    # Commit it so the HR repo is clean (apply/promote/rif refuse a dirty HR
    # by default).
    subprocess.check_call(
        [sys.executable, str(hr / "scripts/generate-manifest.py")],
        cwd=hr,
    )
    git(["add", "-A"], cwd=hr)
    git(["commit", "-q", "-m", "manifest"], cwd=hr)
    return hr


def read_scope(agent_md: Path) -> str:
    text = agent_md.read_text(encoding="utf-8")
    # Same parse as promote.read_scope_from_frontmatter
    import re
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return "(no frontmatter)"
    block = m.group(1)
    for line in block.splitlines():
        if line.startswith("scope:"):
            return line.split(":", 1)[1].strip()
    return "project"


def manifest_scope(hr: Path, agent_id: str) -> str:
    data = yaml.safe_load((hr / "agent.manifest.yaml").read_text())
    return data["agents"][agent_id]["scope"]


def run_promote(hr: Path, agent: str, extra: list[str] | None = None,
                expect_exit: int = 0) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(PROMOTE), agent, "--hr-repo", str(hr)]
    if extra:
        cmd.extend(extra)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != expect_exit:
        print(f"FAIL: expected exit {expect_exit}, got {result.returncode}")
        print(f"stdout: {result.stdout}\nstderr: {result.stderr}")
        sys.exit(1)
    return result


def run_rif(hr: Path, agent: str, extra: list[str] | None = None,
            expect_exit: int = 0, env: dict | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(RIF), agent, "--hr-repo", str(hr)]
    if extra:
        cmd.extend(extra)
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=full_env)
    if result.returncode != expect_exit:
        print(f"FAIL: expected exit {expect_exit}, got {result.returncode}")
        print(f"stdout: {result.stdout}\nstderr: {result.stderr}")
        sys.exit(1)
    return result


def run_apply(project: Path, hr: Path, ids: list[str]) -> None:
    subprocess.check_call(
        [sys.executable, str(APPLY),
         "--project-root", str(project),
         "--hr-repo", str(hr),
         "--agents", *ids],
    )


# ===== promote =====

def test_promote_adds_scope_line(root: Path) -> None:
    print("test_promote_adds_scope_line")
    hr = make_fake_hr(root)
    expect(manifest_scope(hr, "alpha") == "project", "alpha starts as project scope")
    run_promote(hr, "alpha", extra=["--skip-install"])
    expect(read_scope(hr / "engineering/alpha.md") == "org", "alpha.md frontmatter now scope: org")
    expect(manifest_scope(hr, "alpha") == "org", "manifest now records alpha as org")


def test_promote_already_org_is_noop(root: Path) -> None:
    print("test_promote_already_org_is_noop")
    hr = make_fake_hr(root)
    pre = (hr / "engineering/beta.md").read_text()
    res = run_promote(hr, "beta", extra=["--skip-install"])
    expect("already org" in res.stdout.lower(), "stdout says 'already org'")
    expect((hr / "engineering/beta.md").read_text() == pre, "beta.md byte-unchanged")


def test_promote_unknown_id_exits_2(root: Path) -> None:
    print("test_promote_unknown_id_exits_2")
    hr = make_fake_hr(root)
    res = run_promote(hr, "does-not-exist", expect_exit=2)
    expect("agent-not-in-manifest" in res.stderr, "stderr names the error class")


def test_promote_inserts_after_name_line(root: Path) -> None:
    """When scope is absent, the new line lands right after `name:` to keep
    the frontmatter visually stable for human review."""
    print("test_promote_inserts_after_name_line")
    hr = make_fake_hr(root)
    run_promote(hr, "alpha", extra=["--skip-install"])
    lines = (hr / "engineering/alpha.md").read_text().splitlines()
    name_idx = next(i for i, ln in enumerate(lines) if ln.startswith("name:"))
    expect(lines[name_idx + 1].startswith("scope:"),
           "scope: line is immediately after name: line")


def test_promote_dry_run_writes_nothing(root: Path) -> None:
    print("test_promote_dry_run_writes_nothing")
    hr = make_fake_hr(root)
    before = (hr / "engineering/alpha.md").read_text()
    before_mf = (hr / "agent.manifest.yaml").read_text()
    run_promote(hr, "alpha", extra=["--skip-install", "--dry-run"])
    expect((hr / "engineering/alpha.md").read_text() == before, "agent file unchanged")
    expect((hr / "agent.manifest.yaml").read_text() == before_mf, "manifest unchanged")


# ===== rif =====

def test_rif_global_demotes(root: Path) -> None:
    print("test_rif_global_demotes")
    hr = make_fake_hr(root)
    # Use an isolated user-agents dir so we don't touch ~/.claude
    user_agents = root / "user_agents"
    user_agents.mkdir()
    res = run_rif(
        hr, "beta", extra=["--global"],
        env={"STAFF_USER_AGENTS_DIR": str(user_agents),
             "STAFF_PROJECTS_DIR": str(root / "no-such-projects")},
    )
    expect(read_scope(hr / "engineering/beta.md") == "project",
           "beta.md frontmatter is now scope: project")
    expect(manifest_scope(hr, "beta") == "project",
           "manifest now records beta as project")


def test_rif_global_refuses_when_in_use(root: Path) -> None:
    """rif --global without --force should refuse if any project lockfile
    under STAFF_PROJECTS_DIR references the agent."""
    print("test_rif_global_refuses_when_in_use")
    hr = make_fake_hr(root)
    projects_dir = root / "inc-projects"
    projects_dir.mkdir()
    proj_a = projects_dir / "proj-a"
    (proj_a / ".claude/staff").mkdir(parents=True)
    (proj_a / ".claude/staff/lock.yaml").write_text(
        "schema_version: 1\n"
        "hr_repo: file://" + str(hr) + "\n"
        "hr_commit_pinned: 0000000000000000000000000000000000000000\n"
        "staffed:\n"
        "  beta:\n"
        "    pinned_at: 0000000000000000000000000000000000000000\n"
        "    file: engineering/beta.md\n",
    )
    res = run_rif(
        hr, "beta", extra=["--global"], expect_exit=8,
        env={"STAFF_PROJECTS_DIR": str(projects_dir),
             "STAFF_USER_AGENTS_DIR": str(root / "user_agents")},
    )
    expect("still referenced" in res.stderr.lower() or "referenced" in res.stderr.lower(),
           "stderr explains the refusal")
    expect(manifest_scope(hr, "beta") == "org", "beta unchanged in manifest")


def test_rif_global_refuses_via_current_project_root(root: Path) -> None:
    """rif --global also counts the current --project-root's own lockfile,
    not just projects under STAFF_PROJECTS_DIR. Otherwise an unindexed
    project could rif --global an agent it still uses."""
    print("test_rif_global_refuses_via_current_project_root")
    hr = make_fake_hr(root)
    # STAFF_PROJECTS_DIR is empty — the indexed-projects scan finds nothing.
    empty_projects = root / "empty-projects"
    empty_projects.mkdir()
    # The current project is not under STAFF_PROJECTS_DIR but staffs beta.
    here = root / "current-project"
    (here / ".claude/staff").mkdir(parents=True)
    (here / ".claude/staff/lock.yaml").write_text(
        "schema_version: 1\n"
        "hr_repo: file://" + str(hr) + "\n"
        "hr_commit_pinned: 0000000000000000000000000000000000000000\n"
        "staffed:\n"
        "  beta:\n"
        "    pinned_at: 0000000000000000000000000000000000000000\n"
        "    file: engineering/beta.md\n",
    )
    res = run_rif(
        hr, "beta", extra=["--global", "--project-root", str(here)],
        expect_exit=8,
        env={"STAFF_PROJECTS_DIR": str(empty_projects),
             "STAFF_USER_AGENTS_DIR": str(root / "user_agents")},
    )
    expect("referenced" in res.stderr.lower(),
           "stderr explains the refusal (current project counted)")
    expect(manifest_scope(hr, "beta") == "org", "beta unchanged in manifest")


def test_rif_global_force_overrides(root: Path) -> None:
    print("test_rif_global_force_overrides")
    hr = make_fake_hr(root)
    projects_dir = root / "inc-projects"
    projects_dir.mkdir()
    proj_a = projects_dir / "proj-a"
    (proj_a / ".claude/staff").mkdir(parents=True)
    (proj_a / ".claude/staff/lock.yaml").write_text(
        "schema_version: 1\n"
        "hr_repo: file://" + str(hr) + "\n"
        "hr_commit_pinned: 0000000000000000000000000000000000000000\n"
        "staffed:\n"
        "  beta:\n"
        "    pinned_at: 0000000000000000000000000000000000000000\n"
        "    file: engineering/beta.md\n",
    )
    run_rif(
        hr, "beta", extra=["--global", "--force"],
        env={"STAFF_PROJECTS_DIR": str(projects_dir),
             "STAFF_USER_AGENTS_DIR": str(root / "user_agents")},
    )
    expect(manifest_scope(hr, "beta") == "project", "--force demotes anyway")


def test_rif_global_already_project_is_noop(root: Path) -> None:
    print("test_rif_global_already_project_is_noop")
    hr = make_fake_hr(root)
    user_agents = root / "user_agents"
    user_agents.mkdir()
    pre = (hr / "engineering/alpha.md").read_text()
    res = run_rif(
        hr, "alpha", extra=["--global"],
        env={"STAFF_PROJECTS_DIR": str(root / "no-such"),
             "STAFF_USER_AGENTS_DIR": str(user_agents)},
    )
    expect(
        "not at global scope" in res.stdout.lower() or "no-op" in res.stdout.lower(),
        "stdout indicates no-op",
    )
    expect((hr / "engineering/alpha.md").read_text() == pre, "alpha.md byte-unchanged")


def test_rif_global_deletes_symlink_into_hr(root: Path) -> None:
    """If ~/.claude/agents/<id>.md is a symlink into the HR repo, rif --global
    should delete it. If it's a real file, rif --global should leave it."""
    print("test_rif_global_deletes_symlink_into_hr")
    hr = make_fake_hr(root)
    user_agents = root / "user_agents"
    user_agents.mkdir()
    # Simulate install.sh --link having symlinked beta in.
    link = user_agents / "beta.md"
    link.symlink_to(hr / "engineering/beta.md")
    expect(link.is_symlink(), "fixture symlink created")

    run_rif(
        hr, "beta", extra=["--global"],
        env={"STAFF_PROJECTS_DIR": str(root / "no-such"),
             "STAFF_USER_AGENTS_DIR": str(user_agents)},
    )
    expect(not link.exists() and not link.is_symlink(),
           "symlink was deleted")


def test_rif_global_preserves_real_file(root: Path) -> None:
    """If ~/.claude/agents/<id>.md is a real file (not our symlink), we never
    delete it — even on rif --global. The frontmatter is still demoted."""
    print("test_rif_global_preserves_real_file")
    hr = make_fake_hr(root)
    user_agents = root / "user_agents"
    user_agents.mkdir()
    real = user_agents / "beta.md"
    real.write_text("user-edited copy\n")
    expect(real.is_file() and not real.is_symlink(), "fixture real file created")

    res = run_rif(
        hr, "beta", extra=["--global"],
        env={"STAFF_PROJECTS_DIR": str(root / "no-such"),
             "STAFF_USER_AGENTS_DIR": str(user_agents)},
    )
    expect(real.exists() and real.read_text() == "user-edited copy\n",
           "hand-edited copy preserved")
    expect("refusing to delete" in res.stderr.lower()
           or "refusing" in res.stderr.lower()
           or "hand-edited" in res.stderr.lower(),
           "stderr warns we left it alone")


def test_rif_project_drops_lockfile_entry(root: Path) -> None:
    print("test_rif_project_drops_lockfile_entry")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, ["alpha"])
    lock_path = project / ".claude/staff/lock.yaml"
    expect("alpha" in (yaml.safe_load(lock_path.read_text()).get("staffed") or {}),
           "alpha staffed before rif")
    run_rif(hr, "alpha", extra=["--project", "--project-root", str(project)])
    after = yaml.safe_load(lock_path.read_text()).get("staffed") or {}
    expect("alpha" not in after, "alpha gone from lockfile")
    expect(not (project / ".claude/agents/alpha.md").exists(), "alpha.md deleted")


def test_rif_project_idempotent(root: Path) -> None:
    """rif --project on an agent that isn't staffed should exit 0 quietly
    (unlike /staff remove, which is more strict)."""
    print("test_rif_project_idempotent")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, ["alpha"])
    # 'beta' is in the manifest but not staffed in this project
    res = run_rif(hr, "beta", extra=["--project", "--project-root", str(project)])
    expect("not installed in this project" in res.stdout.lower() or "no-op" in res.stdout.lower(),
           "stdout signals idempotent no-op")


def test_rif_no_lockfile_project_is_noop(root: Path) -> None:
    """rif --project in a directory with no lockfile is also a no-op."""
    print("test_rif_no_lockfile_project_is_noop")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    res = run_rif(hr, "alpha", extra=["--project", "--project-root", str(project)])
    expect("nothing to remove" in res.stdout.lower() or "no lockfile" in res.stdout.lower(),
           "stdout signals nothing to do")


# ===== integration =====

def test_promote_then_rif_round_trip(root: Path) -> None:
    print("test_promote_then_rif_round_trip")
    hr = make_fake_hr(root)
    user_agents = root / "user_agents"
    user_agents.mkdir()

    run_promote(hr, "alpha", extra=["--skip-install"])
    expect(manifest_scope(hr, "alpha") == "org", "alpha promoted to org")

    run_rif(
        hr, "alpha", extra=["--global"],
        env={"STAFF_PROJECTS_DIR": str(root / "no-such"),
             "STAFF_USER_AGENTS_DIR": str(user_agents)},
    )
    expect(manifest_scope(hr, "alpha") == "project", "alpha demoted back to project")


# ===== runner =====

def main() -> int:
    if not PROMOTE.exists() or not RIF.exists():
        print("scripts not found", file=sys.stderr)
        return 1
    tests = [
        test_promote_adds_scope_line,
        test_promote_already_org_is_noop,
        test_promote_unknown_id_exits_2,
        test_promote_inserts_after_name_line,
        test_promote_dry_run_writes_nothing,
        test_rif_global_demotes,
        test_rif_global_refuses_when_in_use,
        test_rif_global_refuses_via_current_project_root,
        test_rif_global_force_overrides,
        test_rif_global_already_project_is_noop,
        test_rif_global_deletes_symlink_into_hr,
        test_rif_global_preserves_real_file,
        test_rif_project_drops_lockfile_entry,
        test_rif_project_idempotent,
        test_rif_no_lockfile_project_is_noop,
        test_promote_then_rif_round_trip,
    ]
    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            try:
                fn(Path(d))
            except SystemExit:
                raise
            except Exception as exc:
                print(f"FAIL: {fn.__name__}: {exc!r}")
                return 1
    print(f"\n{len(tests)}/{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
