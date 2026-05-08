#!/usr/bin/env python3
"""Smoke tests for staff audit. Builds tiny fake HR + projects and checks
the report shape."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT = REPO_ROOT / "skills/staff/scripts/audit.py"


def make_fake_hr(root: Path) -> Path:
    hr = root / "hr"
    hr.mkdir()
    (hr / "engineering").mkdir()
    (hr / "engineering" / "alpha.md").write_text(
        "---\nname: alpha\ndescription: Use for go projects.\nmodel: sonnet\n---\n\nbody.\n",
    )
    manifest = {
        "schema_version": 1,
        "agents": {
            "alpha": {
                "file": "engineering/alpha.md",
                "category": "engineering",
                "description": "Use for go projects.",
                "description_summary": "Use for go projects.",
                "description_hash": "sha256:0",
                "body_hash": "sha256:0",
                "tags": ["alpha"],
                "project_hints": {
                    "files": ["go.mod"],
                    "regex": [],
                },
                "conflicts": [],
                "introduced": "2026-01-01",
                "aliases": [],
            },
        },
    }
    (hr / "agent.manifest.yaml").write_text(yaml.safe_dump(manifest))
    env = {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": "/usr/bin:/bin", "HOME": str(root)}
    subprocess.check_output(["git", "init", "-q", "-b", "main"], cwd=hr, env=env)
    subprocess.check_output(["git", "add", "-A"], cwd=hr, env=env)
    subprocess.check_output(["git", "commit", "-q", "-m", "init"], cwd=hr, env=env)
    return hr


def make_git_project(root: Path, name: str, with_go: bool = False) -> Path:
    p = root / name
    p.mkdir()
    (p / ".git").mkdir()
    if with_go:
        (p / "go.mod").write_text("module example.com/x\n")
    return p


def run_audit(*args: str, expect_exit: int | None = None) -> dict | None:
    cmd = [sys.executable, str(AUDIT), *args, "--no-llm", "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if expect_exit is not None and result.returncode != expect_exit:
        raise AssertionError(
            f"expected exit {expect_exit}, got {result.returncode}: {result.stderr}"
        )
    if result.stdout.strip():
        return json.loads(result.stdout)
    return None


class TestAudit(unittest.TestCase):
    def test_no_projects_in_workspace_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            empty_workspace = root / "ws"
            empty_workspace.mkdir()
            cmd = [
                sys.executable, str(AUDIT),
                "--hr-repo", str(hr),
                "--workspace", str(empty_workspace),
                "--no-llm",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("no git-rooted projects", result.stderr)

    def test_explicit_projects_unstaffed_with_match(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            ws = root / "ws"
            ws.mkdir()
            proj = make_git_project(ws, "myapp", with_go=True)
            payload = run_audit(
                "--hr-repo", str(hr),
                "--projects", str(proj),
                expect_exit=1,
            )
            assert payload is not None
            self.assertEqual(len(payload["projects"]), 1)
            self.assertEqual(payload["projects"][0]["name"], "myapp")
            self.assertFalse(payload["projects"][0]["has_lockfile"])
            self.assertEqual(payload["projects"][0]["suggested"], ["alpha"])
            self.assertEqual(payload["all_proposed"], ["alpha"])

    def test_retirement_candidates_computed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            ws = root / "ws"
            ws.mkdir()
            proj = make_git_project(ws, "myapp", with_go=True)
            scope = root / "user-scope"
            scope.mkdir()
            (scope / "engineering").mkdir()
            # alpha is wanted by myapp; foo + bar are not (and not in truly_global)
            (scope / "engineering" / "alpha.md").write_text("body")
            (scope / "engineering" / "foo.md").write_text("body")
            (scope / "engineering" / "bar.md").write_text("body")
            payload = run_audit(
                "--hr-repo", str(hr),
                "--projects", str(proj),
                "--user-scope-dir", str(scope),
                expect_exit=1,
            )
            assert payload is not None
            self.assertIn("foo", payload["retirement_candidates"])
            self.assertIn("bar", payload["retirement_candidates"])
            self.assertNotIn("alpha", payload["retirement_candidates"])

    def test_truly_global_excluded_from_retirement(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            ws = root / "ws"
            ws.mkdir()
            proj = make_git_project(ws, "myapp", with_go=True)
            scope = root / "user-scope"
            scope.mkdir()
            (scope / "engineering").mkdir()
            for global_id in ("hiring-manager", "blog-writer", "joker"):
                (scope / "engineering" / f"{global_id}.md").write_text("body")
            payload = run_audit(
                "--hr-repo", str(hr),
                "--projects", str(proj),
                "--user-scope-dir", str(scope),
            )
            assert payload is not None
            # Truly-global agents should not appear as retirement candidates
            for global_id in ("hiring-manager", "blog-writer", "joker"):
                self.assertNotIn(global_id, payload["retirement_candidates"])

    def test_staffed_project_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            ws = root / "ws"
            ws.mkdir()
            proj = make_git_project(ws, "myapp", with_go=True)
            (proj / ".claude/staff").mkdir(parents=True)
            (proj / ".claude/staff/lock.yaml").write_text("schema_version: 1\nstaffed: {}\n")
            payload = run_audit(
                "--hr-repo", str(hr),
                "--projects", str(proj),
            )
            assert payload is not None
            self.assertTrue(payload["projects"][0]["has_lockfile"])

    def test_clean_audit_exits_0(self) -> None:
        """Empty user-scope, no unstaffed projects → exit 0."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            ws = root / "ws"
            ws.mkdir()
            proj = make_git_project(ws, "myapp", with_go=True)
            (proj / ".claude/staff").mkdir(parents=True)
            (proj / ".claude/staff/lock.yaml").write_text("schema_version: 1\nstaffed: {alpha: {}}\n")
            scope = root / "empty-user-scope"
            scope.mkdir()
            cmd = [
                sys.executable, str(AUDIT),
                "--hr-repo", str(hr),
                "--projects", str(proj),
                "--user-scope-dir", str(scope),
                "--no-llm",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0,
                             f"expected 0, got {result.returncode}: {result.stderr}")


class TestAuditTextOutput(unittest.TestCase):
    """Cover the human-readable emit_text path with diverse inputs."""

    def test_text_output_covers_all_sections(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            ws = root / "ws"
            ws.mkdir()
            # One staffed (has lockfile), one unstaffed-with-match, one unstaffed-no-match,
            # and one user-scope retirement candidate.
            staffed_proj = make_git_project(ws, "alpha-app", with_go=True)
            (staffed_proj / ".claude/staff").mkdir(parents=True)
            (staffed_proj / ".claude/staff/lock.yaml").write_text("schema_version: 1\nstaffed: {}\n")

            unstaffed_match = make_git_project(ws, "beta-app", with_go=True)
            unstaffed_nomatch = make_git_project(ws, "gamma-app", with_go=False)

            scope = root / "user-scope"
            scope.mkdir()
            (scope / "engineering").mkdir()
            (scope / "engineering" / "alpha.md").write_text("body")
            (scope / "engineering" / "retire-me.md").write_text("body")

            cmd = [
                sys.executable, str(AUDIT),
                "--hr-repo", str(hr),
                "--projects", str(staffed_proj), str(unstaffed_match), str(unstaffed_nomatch),
                "--user-scope-dir", str(scope),
                "--no-llm",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            # All four sections should appear
            self.assertIn("STAFFED", result.stdout)
            self.assertIn("UNSTAFFED", result.stdout)
            self.assertIn("AGGREGATE", result.stdout)
            self.assertIn("RETIREMENT CANDIDATES", result.stdout)
            self.assertIn("alpha-app", result.stdout)
            self.assertIn("beta-app", result.stdout)
            self.assertIn("gamma-app", result.stdout)
            self.assertIn("retire-me", result.stdout)

    def test_text_output_clean_state(self) -> None:
        """No retirement candidates and no unstaffed projects -> clean message."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            ws = root / "ws"
            ws.mkdir()
            proj = make_git_project(ws, "alpha-app", with_go=True)
            (proj / ".claude/staff").mkdir(parents=True)
            (proj / ".claude/staff/lock.yaml").write_text("schema_version: 1\nstaffed: {}\n")
            empty_scope = root / "empty"
            empty_scope.mkdir()
            cmd = [
                sys.executable, str(AUDIT),
                "--hr-repo", str(hr),
                "--projects", str(proj),
                "--user-scope-dir", str(empty_scope),
                "--no-llm",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0)
            self.assertIn("none — every user-scope agent is wanted", result.stdout)


class TestAuditEdgeCases(unittest.TestCase):
    def test_no_hr_repo_set(self) -> None:
        """Missing both --hr-repo and STAFF_HR_REPO env exits 2 with clean message."""
        import os
        env = {k: v for k, v in os.environ.items() if k != "STAFF_HR_REPO"}
        with tempfile.TemporaryDirectory() as td:
            cmd = [sys.executable, str(AUDIT), "--projects", td, "--no-llm"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
            self.assertEqual(result.returncode, 1)
            self.assertIn("HR repo not specified", result.stderr)

    def test_invalid_hr_repo_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            empty_hr = Path(td) / "empty-hr"
            empty_hr.mkdir()
            with tempfile.TemporaryDirectory() as proj_td:
                cmd = [
                    sys.executable, str(AUDIT),
                    "--hr-repo", str(empty_hr),
                    "--projects", proj_td,
                    "--no-llm",
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 2)
                self.assertIn("not an HR repo", result.stderr)

    def test_nonexistent_explicit_project_path(self) -> None:
        """A --projects path that doesn't exist is recorded with error, exit 1."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            cmd = [
                sys.executable, str(AUDIT),
                "--hr-repo", str(hr),
                "--projects", "/tmp/staff-audit-nonexistent-path-xyz",
                "--no-llm",
                "--json",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertIn("error", result.stdout.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
