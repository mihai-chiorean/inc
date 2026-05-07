#!/usr/bin/env python3
"""Smoke tests for /staff add and /staff remove."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
ADD = REPO_ROOT / "skills/staff/scripts/add.py"
REMOVE = REPO_ROOT / "skills/staff/scripts/remove.py"
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
    hr = root / "hr"
    hr.mkdir()
    (hr / "engineering").mkdir()
    for name in ("alpha", "beta", "gamma"):
        (hr / "engineering" / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: {name.title()} agent\nmodel: sonnet\n---\n\nYou are {name}.\n",
        )
    manifest = {
        "schema_version": 1,
        "agents": {
            name: {
                "file": f"engineering/{name}.md",
                "category": "engineering",
                "description": f"{name.title()} agent",
                "description_hash": "sha256:0",  # placeholder; not consumed by add/remove tests
                "body_hash": "sha256:0",
                "tags": [name],
                "project_hints": {"files": [], "regex": []},
                "conflicts": [],
                "introduced": "2026-01-01",
                "aliases": [],
            } for name in ("alpha", "beta", "gamma")
        },
    }
    (hr / "agent.manifest.yaml").write_text(yaml.safe_dump(manifest))
    git(["init", "-q", "-b", "main"], cwd=hr)
    git(["add", "-A"], cwd=hr)
    git(["commit", "-q", "-m", "initial"], cwd=hr)
    return hr


def run_apply(project: Path, hr: Path, ids: list[str]) -> None:
    subprocess.check_call(
        [sys.executable, str(APPLY),
         "--project-root", str(project),
         "--hr-repo", str(hr),
         "--agents", *ids],
    )


def run_add(project: Path, hr: Path, ids: list[str], extra: list[str] | None = None,
            expect_exit: int = 0) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(ADD), *ids,
           "--project-root", str(project), "--hr-repo", str(hr)]
    if extra:
        cmd.extend(extra)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != expect_exit:
        print(f"FAIL: expected exit {expect_exit}, got {result.returncode}")
        print(f"stdout: {result.stdout}\nstderr: {result.stderr}")
        sys.exit(1)
    return result


def run_remove(project: Path, ids: list[str], extra: list[str] | None = None,
               expect_exit: int = 0) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(REMOVE), *ids, "--project-root", str(project)]
    if extra:
        cmd.extend(extra)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != expect_exit:
        print(f"FAIL: expected exit {expect_exit}, got {result.returncode}")
        print(f"stdout: {result.stdout}\nstderr: {result.stderr}")
        sys.exit(1)
    return result


def lockfile_ids(project: Path) -> set[str]:
    lock = yaml.safe_load((project / ".claude/staff/lock.yaml").read_text())
    return set((lock.get("staffed") or {}).keys())


# ===== add =====

def test_add_to_existing_lockfile(root: Path) -> None:
    print("test_add_to_existing_lockfile")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, ["alpha"])
    run_add(project, hr, ["beta"])
    expect(lockfile_ids(project) == {"alpha", "beta"}, "both alpha and beta in lockfile")
    expect((project / ".claude/agents/beta.md").is_file(), "beta.md written")
    expect((project / ".claude/agents/alpha.md").is_file(), "alpha.md preserved")


def test_add_already_staffed_rejects(root: Path) -> None:
    print("test_add_already_staffed_rejects")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, ["alpha"])
    res = run_add(project, hr, ["alpha"], expect_exit=6)
    expect("agent-already-staffed" in res.stderr, "stderr names the error class")
    expect("alpha" in res.stderr, "stderr names the conflicting agent")


def test_add_unknown_id_rejects(root: Path) -> None:
    print("test_add_unknown_id_rejects")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    res = run_add(project, hr, ["does-not-exist"], expect_exit=2)
    expect("agent-not-in-manifest" in res.stderr, "stderr names the error class")


def test_add_to_empty_project(root: Path) -> None:
    """First add into a project with no prior lockfile."""
    print("test_add_to_empty_project")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_add(project, hr, ["alpha", "beta"])
    expect(lockfile_ids(project) == {"alpha", "beta"}, "both staffed from empty start")


def test_add_dry_run_writes_nothing(root: Path) -> None:
    print("test_add_dry_run_writes_nothing")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, ["alpha"])
    run_add(project, hr, ["beta"], extra=["--dry-run"])
    expect(not (project / ".claude/agents/beta.md").exists(), "no beta.md on dry-run")
    expect(lockfile_ids(project) == {"alpha"}, "lockfile unchanged on dry-run")


# ===== remove =====

def test_remove_one_agent(root: Path) -> None:
    print("test_remove_one_agent")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, ["alpha", "beta"])
    run_remove(project, ["alpha"])
    expect(lockfile_ids(project) == {"beta"}, "alpha gone from lockfile, beta remains")
    expect(not (project / ".claude/agents/alpha.md").exists(), "alpha.md deleted")
    expect((project / ".claude/agents/beta.md").is_file(), "beta.md preserved")


def test_remove_not_staffed_rejects(root: Path) -> None:
    print("test_remove_not_staffed_rejects")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, ["alpha"])
    res = run_remove(project, ["beta"], expect_exit=7)
    expect("agent-not-currently-staffed" in res.stderr, "stderr names the error class")


def test_remove_no_lockfile_exits_2(root: Path) -> None:
    print("test_remove_no_lockfile_exits_2")
    project = root / "proj"
    project.mkdir()
    res = run_remove(project, ["alpha"], expect_exit=2)
    expect("lockfile" in res.stderr.lower(), "stderr mentions missing lockfile")


def test_remove_preserves_overlay(root: Path) -> None:
    print("test_remove_preserves_overlay")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    overlays = project / ".claude/staff/overlays"
    overlays.mkdir(parents=True)
    overlay_path = overlays / "alpha.md"
    overlay_path.write_text(
        "---\nagent_id: alpha\nlast_reviewed: 2026-05-07\n---\n\n## Project\n\nKeep this.\n",
    )
    run_apply(project, hr, ["alpha"])
    res = run_remove(project, ["alpha"])
    expect(overlay_path.exists(), "overlay file still on disk after remove")
    expect("overlay preserved" in res.stdout.lower() or "overlay" in res.stdout.lower(),
           "stdout warns about preserved overlay")


def test_remove_dry_run_writes_nothing(root: Path) -> None:
    print("test_remove_dry_run_writes_nothing")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, ["alpha", "beta"])
    run_remove(project, ["alpha"], extra=["--dry-run"])
    expect((project / ".claude/agents/alpha.md").exists(), "dry-run did not delete the file")
    expect(lockfile_ids(project) == {"alpha", "beta"}, "dry-run did not modify lockfile")


# ===== integration =====

def test_add_then_remove_round_trip(root: Path) -> None:
    print("test_add_then_remove_round_trip")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, ["alpha"])
    run_add(project, hr, ["beta", "gamma"])
    expect(lockfile_ids(project) == {"alpha", "beta", "gamma"}, "all three staffed after add")
    run_remove(project, ["beta"])
    expect(lockfile_ids(project) == {"alpha", "gamma"}, "beta removed; alpha and gamma remain")


def main() -> int:
    if not ADD.exists() or not REMOVE.exists():
        print(f"scripts not found", file=sys.stderr)
        return 1
    tests = [
        test_add_to_existing_lockfile,
        test_add_already_staffed_rejects,
        test_add_unknown_id_rejects,
        test_add_to_empty_project,
        test_add_dry_run_writes_nothing,
        test_remove_one_agent,
        test_remove_not_staffed_rejects,
        test_remove_no_lockfile_exits_2,
        test_remove_preserves_overlay,
        test_remove_dry_run_writes_nothing,
        test_add_then_remove_round_trip,
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
