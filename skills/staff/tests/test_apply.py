#!/usr/bin/env python3
"""Smoke tests for skills/staff/scripts/apply.py.

These build a fake HR repo as a real git repo (so we can test commit-pinning
and dirty-state checks), run apply against a temp project, and assert on the
generated files and lockfile.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "skills/staff/scripts/apply.py"
SUGGEST_SCRIPT = REPO_ROOT / "skills/staff/scripts/suggest.py"


def expect(condition: bool, msg: str) -> None:
    if not condition:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


def git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(
        ["git"] + args,
        cwd=cwd,
        stderr=subprocess.DEVNULL,
        env={"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
             "PATH": "/usr/bin:/bin", "HOME": str(cwd)},
    ).decode().strip()


def make_fake_hr(root: Path) -> Path:
    """Build a small fake HR repo with two agents."""
    hr = root / "hr"
    hr.mkdir()
    (hr / "engineering").mkdir()
    (hr / "engineering" / "alpha.md").write_text(
        "---\nname: alpha\ndescription: Alpha agent for tests\nmodel: sonnet\n---\n\n"
        "You are the alpha agent.\n",
        encoding="utf-8",
    )
    (hr / "engineering" / "beta.md").write_text(
        "---\nname: beta\ndescription: Beta agent for tests\nmodel: sonnet\n---\n\n"
        "You are the beta agent.\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "generated_by": "test",
        "source_repo": "fake",
        "agents": {
            "alpha": {
                "file": "engineering/alpha.md",
                "category": "engineering",
                "description": "Alpha agent for tests",
                "description_hash": "sha256:placeholder",
                "body_hash": "sha256:placeholder",
                "tags": ["alpha"],
                "project_hints": {"files": [], "regex": []},
                "conflicts": [],
                "introduced": "2026-01-01",
                "aliases": ["alfa"],  # alias for testing resolution
            },
            "beta": {
                "file": "engineering/beta.md",
                "category": "engineering",
                "description": "Beta agent for tests",
                "description_hash": "sha256:placeholder",
                "body_hash": "sha256:placeholder",
                "tags": ["beta"],
                "project_hints": {"files": [], "regex": []},
                "conflicts": [],
                "introduced": "2026-01-01",
                "aliases": [],
            },
        },
    }
    (hr / "agent.manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")
    git(["init", "-q", "-b", "main"], cwd=hr)
    git(["add", "-A"], cwd=hr)
    git(["commit", "-q", "-m", "initial"], cwd=hr)
    return hr


def run_apply(project: Path, hr: Path, agent_ids: list[str] | None = None,
              from_suggest_json: str | None = None,
              extra_args: list[str] | None = None,
              expect_exit: int = 0) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT), "--project-root", str(project), "--hr-repo", str(hr)]
    stdin = None
    if agent_ids is not None:
        cmd.extend(["--agents"] + agent_ids)
    if from_suggest_json is not None:
        cmd.extend(["--from-suggest", "-"])
        stdin = from_suggest_json
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, input=stdin, check=False)
    if result.returncode != expect_exit:
        print(f"FAIL: expected exit {expect_exit}, got {result.returncode}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)
    return result


def test_apply_explicit_list_writes_files_and_lock(root: Path) -> None:
    print("test_apply_explicit_list_writes_files_and_lock")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, agent_ids=["alpha", "beta"])
    expect((project / ".claude/agents/alpha.md").is_file(), "alpha.md generated")
    expect((project / ".claude/agents/beta.md").is_file(), "beta.md generated")
    expect((project / ".claude/staff/lock.yaml").is_file(), "lock.yaml written")
    lock = yaml.safe_load((project / ".claude/staff/lock.yaml").read_text())
    expect(lock["schema_version"] == 1, "lockfile schema_version 1")
    expect(set(lock["staffed"].keys()) == {"alpha", "beta"}, "lockfile staffed has both agents")
    for aid in ("alpha", "beta"):
        e = lock["staffed"][aid]
        expect(e["pinned_at"] == git(["rev-parse", "HEAD"], cwd=hr), f"{aid} pinned_at == HR HEAD")
        expect(e["description_hash_at_pin"].startswith("sha256:"), f"{aid} description_hash_at_pin set")
        expect(e["body_hash_at_pin"].startswith("sha256:"), f"{aid} body_hash_at_pin set")
        expect(e["generated_hash_at_apply"].startswith("sha256:"), f"{aid} generated_hash_at_apply set")
        expect(e["overlay"] is False, f"{aid} overlay false (no overlay file)")


def test_apply_is_idempotent(root: Path) -> None:
    print("test_apply_is_idempotent")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, agent_ids=["alpha"])
    first_lock = (project / ".claude/staff/lock.yaml").read_text()
    first_alpha = (project / ".claude/agents/alpha.md").read_text()
    run_apply(project, hr, agent_ids=["alpha"])
    second_alpha = (project / ".claude/agents/alpha.md").read_text()
    expect(first_alpha == second_alpha, "alpha.md identical after second apply")
    # Lock generated_at differs by timestamp; staffed entries should match.
    second_lock = yaml.safe_load((project / ".claude/staff/lock.yaml").read_text())
    first_parsed = yaml.safe_load(first_lock)
    expect(first_parsed["staffed"] == second_lock["staffed"], "staffed map unchanged on re-apply")


def test_apply_with_overlay(root: Path) -> None:
    print("test_apply_with_overlay")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    overlays = project / ".claude/staff/overlays"
    overlays.mkdir(parents=True)
    (overlays / "alpha.md").write_text(
        "---\nagent_id: alpha\nlast_reviewed: 2026-05-07\n---\n\n## Project Context\n\nUse port 9999.\n",
        encoding="utf-8",
    )
    run_apply(project, hr, agent_ids=["alpha"])
    merged = (project / ".claude/agents/alpha.md").read_text()
    expect("BEGIN STAFF OVERLAY" in merged, "merged file has overlay BEGIN marker")
    expect("END STAFF OVERLAY" in merged, "merged file has overlay END marker")
    expect("Use port 9999" in merged, "overlay body present in merged file")
    expect("overlay_last_reviewed: 2026-05-07" in merged, "merged file embeds last_reviewed")
    lock = yaml.safe_load((project / ".claude/staff/lock.yaml").read_text())
    e = lock["staffed"]["alpha"]
    expect(e["overlay"] is True, "lockfile says overlay=true")
    expect(e["overlay_last_reviewed"] == "2026-05-07", "lockfile mirrors last_reviewed")
    expect(e["overlay_hash_at_apply"].startswith("sha256:"), "overlay_hash_at_apply set")


def test_alias_resolves(root: Path) -> None:
    print("test_alias_resolves")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    # Apply by alias 'alfa' — should resolve to 'alpha'
    run_apply(project, hr, agent_ids=["alfa"])
    expect((project / ".claude/agents/alpha.md").is_file(),
           "alias 'alfa' resolves to canonical 'alpha'")
    expect(not (project / ".claude/agents/alfa.md").exists(),
           "no alfa.md is written under the alias name")


def test_unknown_id_fails(root: Path) -> None:
    print("test_unknown_id_fails")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    res = run_apply(project, hr, agent_ids=["does-not-exist"], expect_exit=2)
    expect("not found" in res.stderr.lower() or "manifest" in res.stderr.lower(),
           "stderr mentions missing agent")


def test_dirty_hr_is_refused(root: Path) -> None:
    print("test_dirty_hr_is_refused")
    hr = make_fake_hr(root)
    # Make HR dirty
    (hr / "engineering" / "alpha.md").write_text("dirty\n")
    project = root / "proj"
    project.mkdir()
    res = run_apply(project, hr, agent_ids=["alpha"], expect_exit=4)
    expect("uncommitted" in res.stderr.lower() or "dirty" in res.stderr.lower(),
           "stderr mentions dirty HR")


def test_dirty_hr_with_allow_flag(root: Path) -> None:
    print("test_dirty_hr_with_allow_flag")
    hr = make_fake_hr(root)
    (hr / "engineering" / "alpha.md").write_text(
        "---\nname: alpha\ndescription: Alpha agent for tests (dirty)\nmodel: sonnet\n---\n\nDirty body.\n"
    )
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, agent_ids=["alpha"], extra_args=["--allow-dirty-hr"])
    merged = (project / ".claude/agents/alpha.md").read_text()
    expect("Dirty body" in merged, "applied the dirty content under --allow-dirty-hr")


def test_suggest_to_apply_pipeline(root: Path) -> None:
    """End-to-end: suggest --json | apply --from-suggest -, against the real HR repo.

    Uses the real inc repo at REPO_ROOT and a project with a Go file."""
    print("test_suggest_to_apply_pipeline")
    project = root / "proj-pipeline"
    project.mkdir()
    (project / "go.mod").write_text("module example.com/x\n", encoding="utf-8")
    suggest = subprocess.run(
        [sys.executable, str(SUGGEST_SCRIPT),
         "--project-root", str(project),
         "--hr-repo", str(REPO_ROOT),
         "--json"],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(suggest.stdout)
    expect(any(p["id"] == "go-engineer" for p in payload["suggested"]),
           "suggest finds go-engineer for go.mod project")
    # Pass --allow-dirty-hr because this test runs against the real inc
    # repo, which often has uncommitted changes when this test executes. The
    # dedicated dirty-HR test (test_dirty_hr_is_refused) covers the refusal path.
    apply = subprocess.run(
        [sys.executable, str(SCRIPT),
         "--project-root", str(project),
         "--hr-repo", str(REPO_ROOT),
         "--from-suggest", "-",
         "--allow-dirty-hr",
         "--force"],  # also bypass the manifest_hash drift check
        input=suggest.stdout, capture_output=True, text=True, check=False,
    )
    expect(apply.returncode == 0, f"apply succeeds (got {apply.returncode}; stderr={apply.stderr})")
    expect((project / ".claude/agents/go-engineer.md").is_file(),
           "go-engineer.md installed by apply")


def test_suggest_drift_blocks_apply(root: Path) -> None:
    print("test_suggest_drift_blocks_apply")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    # Hand-craft a suggest payload with a fake hr_commit
    payload = {
        "schema_version": 1,
        "project_root": str(project),
        "hr_repo": str(hr),
        "hr_commit": "0" * 40,  # not the actual HR HEAD
        "manifest_hash": "sha256:" + "0" * 64,
        "manifest_count": 2,
        "suggested": [{"id": "alpha", "category": "engineering", "matches": [], "reasons": []}],
    }
    res = run_apply(project, hr, from_suggest_json=json.dumps(payload), expect_exit=3)
    expect("hr_commit" in res.stderr.lower() or "moved" in res.stderr.lower() or "drift" in res.stderr.lower()
           or "hr repo has moved" in res.stderr.lower(),
           "stderr mentions HR drift")


def test_unsupported_suggest_schema_version(root: Path) -> None:
    print("test_unsupported_suggest_schema_version")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    payload = {"schema_version": 99, "suggested": [{"id": "alpha"}]}
    res = run_apply(project, hr, from_suggest_json=json.dumps(payload), expect_exit=2)
    expect("schema_version" in res.stderr or "schema version" in res.stderr.lower(),
           "stderr mentions schema version mismatch")


def test_partial_failure_no_lockfile_change(root: Path) -> None:
    print("test_partial_failure_no_lockfile_change")
    hr = make_fake_hr(root)
    # Break HR by removing alpha.md after manifest already references it
    (hr / "engineering" / "alpha.md").unlink()
    git(["add", "-A"], cwd=hr)
    git(["commit", "-q", "-m", "remove alpha"], cwd=hr)
    project = root / "proj"
    project.mkdir()
    res = run_apply(project, hr, agent_ids=["alpha", "beta"], expect_exit=5)
    expect("missing file" in res.stderr.lower() or "alpha" in res.stderr.lower(),
           "stderr names the failed agent")
    expect(not (project / ".claude/staff/lock.yaml").exists(),
           "lockfile not written on partial failure")


def test_partial_failure_no_agent_files_written(root: Path) -> None:
    """Atomicity: if any requested agent fails, NO agent file is left written."""
    print("test_partial_failure_no_agent_files_written")
    hr = make_fake_hr(root)
    (hr / "engineering" / "alpha.md").unlink()
    git(["add", "-A"], cwd=hr)
    git(["commit", "-q", "-m", "remove alpha"], cwd=hr)
    project = root / "proj"
    project.mkdir()
    # beta is healthy, alpha is missing — old (non-atomic) code would write
    # beta.md before alpha failed.
    run_apply(project, hr, agent_ids=["beta", "alpha"], expect_exit=5)
    expect(not (project / ".claude/agents/beta.md").exists(),
           "beta.md NOT written even though it would have succeeded (atomicity)")
    expect(not (project / ".claude/agents/alpha.md").exists(),
           "alpha.md not written")


def test_lockfile_with_unsupported_schema_version(root: Path) -> None:
    print("test_lockfile_with_unsupported_schema_version")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    lock = project / ".claude/staff/lock.yaml"
    lock.parent.mkdir(parents=True)
    lock.write_text("schema_version: 99\nstaffed: {}\n")
    res = run_apply(project, hr, agent_ids=["alpha"], expect_exit=2)
    expect("schema_version" in res.stderr or "schema version" in res.stderr.lower(),
           "stderr mentions unsupported lockfile schema_version")


def test_manifest_with_alias_collision_rejected(root: Path) -> None:
    print("test_manifest_with_alias_collision_rejected")
    hr = make_fake_hr(root)
    # Edit manifest to add a colliding alias (alias 'alpha' on beta — collides with canonical)
    m = yaml.safe_load((hr / "agent.manifest.yaml").read_text())
    m["agents"]["beta"]["aliases"] = ["alpha"]
    (hr / "agent.manifest.yaml").write_text(yaml.safe_dump(m))
    git(["add", "-A"], cwd=hr)
    git(["commit", "-q", "-m", "broken alias"], cwd=hr)
    project = root / "proj"
    project.mkdir()
    res = run_apply(project, hr, agent_ids=["alpha"], expect_exit=2)
    expect("alias" in res.stderr.lower() and ("collid" in res.stderr.lower() or "canonical" in res.stderr.lower()),
           "stderr names the alias collision")


def test_drift_payload_missing_manifest_hash_rejected(root: Path) -> None:
    print("test_drift_payload_missing_manifest_hash_rejected")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    payload = {
        "schema_version": 1,
        "hr_commit": git(["rev-parse", "HEAD"], cwd=hr),
        # manifest_hash deliberately missing
        "suggested": [{"id": "alpha"}],
    }
    res = run_apply(project, hr, from_suggest_json=json.dumps(payload), expect_exit=2)
    expect("manifest_hash" in res.stderr.lower(),
           "stderr names the missing required field")


def test_dry_run_writes_nothing(root: Path) -> None:
    print("test_dry_run_writes_nothing")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    run_apply(project, hr, agent_ids=["alpha"], extra_args=["--dry-run"])
    expect(not (project / ".claude/agents/alpha.md").exists(), "no agent file written on --dry-run")
    expect(not (project / ".claude/staff/lock.yaml").exists(), "no lockfile written on --dry-run")


def main() -> int:
    if not SCRIPT.exists():
        print(f"script not found: {SCRIPT}", file=sys.stderr)
        return 1

    tests = [
        test_apply_explicit_list_writes_files_and_lock,
        test_apply_is_idempotent,
        test_apply_with_overlay,
        test_alias_resolves,
        test_unknown_id_fails,
        test_dirty_hr_is_refused,
        test_dirty_hr_with_allow_flag,
        test_suggest_to_apply_pipeline,
        test_suggest_drift_blocks_apply,
        test_unsupported_suggest_schema_version,
        test_partial_failure_no_lockfile_change,
        test_partial_failure_no_agent_files_written,
        test_dry_run_writes_nothing,
        test_lockfile_with_unsupported_schema_version,
        test_manifest_with_alias_collision_rejected,
        test_drift_payload_missing_manifest_hash_rejected,
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
