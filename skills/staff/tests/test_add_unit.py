#!/usr/bin/env python3
"""In-process unit tests for add.py that complement the subprocess-based
test_add_remove.py. These cover error-path branches that are awkward to
hit via subprocess (atomic_write failures, rollback)."""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "skills/staff/scripts"))
import add as add_mod  # type: ignore  # noqa: E402
import apply as apply_mod  # type: ignore  # noqa: E402


def make_minimal_hr(root: Path) -> Path:
    hr = root / "hr"
    hr.mkdir()
    (hr / "engineering").mkdir()
    (hr / "engineering" / "alpha.md").write_text(
        "---\nname: alpha\ndescription: Alpha agent\nmodel: sonnet\n---\n\nbody.\n",
    )
    manifest = {
        "schema_version": 1,
        "agents": {
            "alpha": {
                "file": "engineering/alpha.md",
                "category": "engineering",
                "description": "Alpha agent",
                "description_hash": "sha256:0",
                "body_hash": "sha256:0",
                "tags": ["alpha"],
                "project_hints": {"files": [], "regex": []},
                "conflicts": [],
                "introduced": "2026-01-01",
                "aliases": [],
            },
        },
    }
    (hr / "agent.manifest.yaml").write_text(yaml.safe_dump(manifest))
    # Initialize git so apply_mod functions don't fail
    import subprocess as sp
    env = {"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": "/usr/bin:/bin", "HOME": str(root)}
    sp.check_output(["git", "init", "-q", "-b", "main"], cwd=hr, env=env)
    sp.check_output(["git", "add", "-A"], cwd=hr, env=env)
    sp.check_output(["git", "commit", "-q", "-m", "init"], cwd=hr, env=env)
    return hr


class TestAddMain(unittest.TestCase):
    def test_project_not_a_directory_exits_2(self) -> None:
        bogus = "/tmp/definitely-does-not-exist-staff-test"
        with patch.object(sys, "argv",
                          ["add", "alpha", "--project-root", bogus, "--hr-repo", "/tmp"]):
            ret = add_mod.main()
        self.assertEqual(ret, 2)

    def test_no_hr_repo_specified_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "p"
            project.mkdir()
            with patch.dict("os.environ", {}, clear=False):
                # Clear all sources of HR config
                import os
                os.environ.pop("STAFF_HR_REPO", None)
                with patch.object(sys, "argv",
                                  ["add", "alpha", "--project-root", str(project)]):
                    ret = add_mod.main()
        self.assertEqual(ret, 2)

    def test_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_minimal_hr(root)
            project = root / "p"
            project.mkdir()
            with patch.object(sys, "argv", [
                "add", "alpha",
                "--project-root", str(project),
                "--hr-repo", str(hr),
                "--dry-run",
            ]):
                ret = add_mod.main()
            self.assertEqual(ret, 0)
            self.assertFalse((project / ".claude/agents/alpha.md").exists())

    def test_rollback_on_phase2_failure(self) -> None:
        """If atomic_write raises mid-phase-2, newly-created files roll back."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_minimal_hr(root)
            project = root / "p"
            project.mkdir()
            # Patch atomic_write to fail. We expect rollback + exit 5.
            with patch.object(apply_mod, "atomic_write",
                              side_effect=OSError("disk full")):
                with patch.object(sys, "argv", [
                    "add", "alpha",
                    "--project-root", str(project),
                    "--hr-repo", str(hr),
                ]):
                    ret = add_mod.main()
            self.assertEqual(ret, 5)
            self.assertFalse((project / ".claude/agents/alpha.md").exists())
            self.assertFalse((project / ".claude/staff/lock.yaml").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
