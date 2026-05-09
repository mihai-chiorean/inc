#!/usr/bin/env python3
"""Smoke tests for staff sync.

Builds a fake HR git repo with two agents, applies, then advances HR (or
renames, or removes) and verifies sync handles each case correctly.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SYNC = REPO_ROOT / "skills/staff/scripts/sync.py"
APPLY = REPO_ROOT / "skills/staff/scripts/apply.py"


def git(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(
        ["git"] + args, cwd=cwd, stderr=subprocess.DEVNULL,
        env={"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
             "PATH": "/usr/bin:/bin", "HOME": str(cwd)},
    ).decode().strip()


def make_fake_hr(root: Path) -> Path:
    """Build a fake HR repo with alpha + beta agents."""
    hr = root / "hr"
    hr.mkdir()
    (hr / "engineering").mkdir()
    (hr / "engineering" / "alpha.md").write_text(
        "---\nname: alpha\ndescription: Alpha v1\nmodel: sonnet\n---\n\nAlpha body v1.\n",
    )
    (hr / "engineering" / "beta.md").write_text(
        "---\nname: beta\ndescription: Beta v1\nmodel: sonnet\n---\n\nBeta body v1.\n",
    )
    write_manifest(hr)
    git(["init", "-q", "-b", "main"], cwd=hr)
    git(["add", "-A"], cwd=hr)
    git(["commit", "-q", "-m", "initial"], cwd=hr)
    return hr


def write_manifest(hr: Path, alpha_alias: list[str] | None = None,
                   include_beta: bool = True) -> None:
    """Reconstruct the manifest from the current alpha/beta files."""
    import hashlib

    def sha256(s: str) -> str:
        return "sha256:" + hashlib.sha256(s.strip().encode("utf-8")).hexdigest()

    def parse(path: Path) -> tuple[str, str, str]:
        text = path.read_text()
        # crude frontmatter split
        parts = text.split("---", 2)
        fm = parts[1]
        body = parts[2]
        name = ""
        desc = ""
        for line in fm.strip().splitlines():
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("description:"):
                desc = line.split(":", 1)[1].strip()
        return name, desc, body

    agents: dict = {}
    for fpath in (hr / "engineering").glob("*.md"):
        name, desc, body = parse(fpath)
        agents[name] = {
            "file": f"engineering/{fpath.name}",
            "category": "engineering",
            "description": desc,
            "description_summary": desc,
            "description_hash": sha256(desc),
            "body_hash": sha256(body),
            "tags": [name],
            "project_hints": {"files": [], "regex": []},
            "conflicts": [],
            "introduced": "2026-01-01",
            "aliases": [],
        }
    if alpha_alias is not None and "alpha" in agents:
        agents["alpha"]["aliases"] = alpha_alias
    if not include_beta and "beta" in agents:
        del agents["beta"]
    manifest = {"schema_version": 1, "agents": agents}
    (hr / "agent.manifest.yaml").write_text(yaml.safe_dump(manifest))


def apply_agents(project: Path, hr: Path, ids: list[str]) -> None:
    subprocess.check_call(
        [sys.executable, str(APPLY),
         "--project-root", str(project),
         "--hr-repo", str(hr),
         "--agents", *ids],
        env={**os.environ},
    )


def run_sync(project: Path, hr: Path | None = None,
             extra: list[str] | None = None,
             expect_exit: int | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SYNC),
           "--project-root", str(project)]
    if hr is not None:
        cmd.extend(["--hr-repo", str(hr)])
    if extra:
        cmd.extend(extra)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if expect_exit is not None and result.returncode != expect_exit:
        raise AssertionError(
            f"expected exit {expect_exit}, got {result.returncode}: stderr={result.stderr}"
        )
    return result


def lockfile_keys(project: Path) -> set[str]:
    lock = yaml.safe_load((project / ".claude/staff/lock.yaml").read_text())
    return set((lock.get("staffed") or {}).keys())


def lockfile_pinned_at(project: Path, agent_id: str) -> str:
    lock = yaml.safe_load((project / ".claude/staff/lock.yaml").read_text())
    return lock["staffed"][agent_id].get("pinned_at", "")


class TestSync(unittest.TestCase):
    def test_no_changes_exits_0(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            apply_agents(project, hr, ["alpha", "beta"])
            r = run_sync(project, hr=hr, extra=["--yes"], expect_exit=0)
            self.assertIn("up to date", r.stdout)

    def test_hr_drift_accepts_with_yes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            apply_agents(project, hr, ["alpha"])
            old_pin = lockfile_pinned_at(project, "alpha")

            # Mutate alpha and commit
            (hr / "engineering" / "alpha.md").write_text(
                "---\nname: alpha\ndescription: Alpha v2\nmodel: sonnet\n---\n\nAlpha body v2 (updated).\n",
            )
            write_manifest(hr)
            git(["add", "-A"], cwd=hr)
            git(["commit", "-q", "-m", "alpha v2"], cwd=hr)

            r = run_sync(project, hr=hr, extra=["--yes"], expect_exit=0)
            new_pin = lockfile_pinned_at(project, "alpha")
            self.assertNotEqual(old_pin, new_pin, "pin should advance after sync")
            # Generated file should reflect new content
            content = (project / ".claude/agents/alpha.md").read_text()
            self.assertIn("v2", content)

    def test_hr_drift_dry_run_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            apply_agents(project, hr, ["alpha"])
            old_pin = lockfile_pinned_at(project, "alpha")
            old_content = (project / ".claude/agents/alpha.md").read_text()

            (hr / "engineering" / "alpha.md").write_text(
                "---\nname: alpha\ndescription: Alpha v2\nmodel: sonnet\n---\n\nAlpha body v2.\n",
            )
            write_manifest(hr)
            git(["add", "-A"], cwd=hr)
            git(["commit", "-q", "-m", "alpha v2"], cwd=hr)

            run_sync(project, hr=hr, extra=["--yes", "--dry-run"], expect_exit=0)
            self.assertEqual(lockfile_pinned_at(project, "alpha"), old_pin,
                             "dry-run should not advance the pin")
            self.assertEqual((project / ".claude/agents/alpha.md").read_text(), old_content,
                             "dry-run should not modify generated file")

    def test_alias_rename_migrates_lockfile_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            apply_agents(project, hr, ["alpha"])

            # Rename alpha -> aleph in HR with alpha as alias
            old_path = hr / "engineering" / "alpha.md"
            new_path = hr / "engineering" / "aleph.md"
            old_content = old_path.read_text().replace("name: alpha", "name: aleph")
            new_path.write_text(old_content)
            old_path.unlink()
            # Rebuild manifest with aleph as the canonical id, alpha as alias
            import hashlib
            def sha256(s: str) -> str:
                return "sha256:" + hashlib.sha256(s.strip().encode("utf-8")).hexdigest()
            text = new_path.read_text()
            parts = text.split("---", 2)
            body = parts[2]
            beta_path = hr / "engineering" / "beta.md"
            beta_text = beta_path.read_text()
            beta_body = beta_text.split("---", 2)[2]
            manifest = {
                "schema_version": 1,
                "agents": {
                    "aleph": {
                        "file": "engineering/aleph.md",
                        "category": "engineering",
                        "description": "Alpha v1",
                        "description_summary": "Alpha v1",
                        "description_hash": sha256("Alpha v1"),
                        "body_hash": sha256(body),
                        "tags": ["aleph"],
                        "project_hints": {"files": [], "regex": []},
                        "conflicts": [],
                        "introduced": "2026-01-01",
                        "aliases": ["alpha"],
                    },
                    "beta": {
                        "file": "engineering/beta.md",
                        "category": "engineering",
                        "description": "Beta v1",
                        "description_summary": "Beta v1",
                        "description_hash": sha256("Beta v1"),
                        "body_hash": sha256(beta_body),
                        "tags": ["beta"],
                        "project_hints": {"files": [], "regex": []},
                        "conflicts": [],
                        "introduced": "2026-01-01",
                        "aliases": [],
                    },
                },
            }
            (hr / "agent.manifest.yaml").write_text(yaml.safe_dump(manifest))
            git(["add", "-A"], cwd=hr)
            git(["commit", "-q", "-m", "rename alpha->aleph"], cwd=hr)

            run_sync(project, hr=hr, extra=["--yes"], expect_exit=0)
            keys = lockfile_keys(project)
            self.assertIn("aleph", keys, "lockfile key should migrate to canonical id")
            self.assertNotIn("alpha", keys, "old alias key should be dropped")
            self.assertTrue((project / ".claude/agents/aleph.md").is_file(),
                            "new generated file should exist")
            self.assertFalse((project / ".claude/agents/alpha.md").exists(),
                             "old generated file should be removed")

    def test_missing_agent_removes_from_lockfile_with_yes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            apply_agents(project, hr, ["alpha", "beta"])

            # Remove beta from HR entirely
            (hr / "engineering" / "beta.md").unlink()
            write_manifest(hr, include_beta=False)
            git(["add", "-A"], cwd=hr)
            git(["commit", "-q", "-m", "retire beta"], cwd=hr)

            run_sync(project, hr=hr, extra=["--yes"], expect_exit=0)
            keys = lockfile_keys(project)
            self.assertNotIn("beta", keys, "removed agent dropped from lockfile")
            self.assertIn("alpha", keys, "still-present agent stays")
            self.assertFalse((project / ".claude/agents/beta.md").exists(),
                             "removed agent's generated file deleted")

    def test_overlay_preserved_during_sync(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            overlays = project / ".claude/staff/overlays"
            overlays.mkdir(parents=True)
            (overlays / "alpha.md").write_text(
                "---\nagent_id: alpha\nlast_reviewed: 2026-05-09\n---\n\n## Project\n\nMy notes.\n",
            )
            apply_agents(project, hr, ["alpha"])

            # Mutate HR
            (hr / "engineering" / "alpha.md").write_text(
                "---\nname: alpha\ndescription: Alpha v2\nmodel: sonnet\n---\n\nNew alpha body.\n",
            )
            write_manifest(hr)
            git(["add", "-A"], cwd=hr)
            git(["commit", "-q", "-m", "alpha v2"], cwd=hr)

            run_sync(project, hr=hr, extra=["--yes"], expect_exit=0)
            # Overlay file untouched
            self.assertTrue((overlays / "alpha.md").is_file(), "overlay source preserved")
            # Generated file has both new HR content AND the overlay
            content = (project / ".claude/agents/alpha.md").read_text()
            self.assertIn("New alpha body", content, "HR content updated")
            self.assertIn("My notes", content, "overlay merged in")
            self.assertIn("BEGIN STAFF OVERLAY", content, "overlay markers present")

    def test_no_lockfile_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            project.mkdir()
            r = run_sync(project, hr=None, expect_exit=2)
            self.assertIn("lockfile", r.stderr.lower())

    def test_subset_via_agents_flag(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            apply_agents(project, hr, ["alpha", "beta"])
            old_alpha_pin = lockfile_pinned_at(project, "alpha")
            old_beta_pin = lockfile_pinned_at(project, "beta")

            # Mutate BOTH alpha and beta in HR
            (hr / "engineering" / "alpha.md").write_text(
                "---\nname: alpha\ndescription: Alpha v2\nmodel: sonnet\n---\n\nAlpha v2.\n",
            )
            (hr / "engineering" / "beta.md").write_text(
                "---\nname: beta\ndescription: Beta v2\nmodel: sonnet\n---\n\nBeta v2.\n",
            )
            write_manifest(hr)
            git(["add", "-A"], cwd=hr)
            git(["commit", "-q", "-m", "v2 both"], cwd=hr)

            # Sync only alpha
            run_sync(project, hr=hr, extra=["--yes", "--agents", "alpha"], expect_exit=0)
            self.assertNotEqual(lockfile_pinned_at(project, "alpha"), old_alpha_pin,
                                "alpha pin advanced")
            self.assertEqual(lockfile_pinned_at(project, "beta"), old_beta_pin,
                             "beta pin unchanged (not in --agents)")


class TestSyncInteractive(unittest.TestCase):
    """Cover the interactive prompt paths (default, accept, skip, remove)."""

    def _setup(self, root: Path) -> tuple[Path, Path]:
        hr = make_fake_hr(root)
        project = root / "proj"
        project.mkdir()
        apply_agents(project, hr, ["alpha"])
        # Mutate HR so there's something to sync
        (hr / "engineering" / "alpha.md").write_text(
            "---\nname: alpha\ndescription: Alpha v2\nmodel: sonnet\n---\n\nUpdated body.\n",
        )
        write_manifest(hr)
        git(["add", "-A"], cwd=hr)
        git(["commit", "-q", "-m", "v2"], cwd=hr)
        return project, hr

    def test_interactive_accept_default(self) -> None:
        """Default response (empty input) on HR-DRIFT should accept."""
        with tempfile.TemporaryDirectory() as td:
            project, hr = self._setup(Path(td))
            old_pin = lockfile_pinned_at(project, "alpha")
            cmd = [sys.executable, str(SYNC),
                   "--project-root", str(project),
                   "--hr-repo", str(hr)]
            result = subprocess.run(cmd, input="\n", capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0,
                             f"sync should exit 0 on default-accept; stderr={result.stderr}")
            self.assertNotEqual(lockfile_pinned_at(project, "alpha"), old_pin,
                                "default-accept should advance the pin")

    def test_interactive_skip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project, hr = self._setup(Path(td))
            old_pin = lockfile_pinned_at(project, "alpha")
            cmd = [sys.executable, str(SYNC),
                   "--project-root", str(project),
                   "--hr-repo", str(hr)]
            result = subprocess.run(cmd, input="n\n", capture_output=True, text=True, check=False)
            # Exit 1 = informational (one declined)
            self.assertEqual(result.returncode, 1,
                             f"declining one change should exit 1; stderr={result.stderr}")
            self.assertEqual(lockfile_pinned_at(project, "alpha"), old_pin,
                             "skip should leave the pin unchanged")


class TestSyncDirtyHr(unittest.TestCase):
    def test_dirty_hr_refused_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            apply_agents(project, hr, ["alpha"])
            # Make HR dirty (uncommitted change)
            (hr / "engineering" / "alpha.md").write_text("dirty\n")
            r = run_sync(project, hr=hr, extra=["--yes"], expect_exit=2)
            self.assertIn("uncommitted changes", r.stderr)


class TestSyncManualEditWarn(unittest.TestCase):
    def test_manual_edit_default_skip(self) -> None:
        """If the merged file has been hand-edited, the default prompt response
        is 'skip' (preserve the edit)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            apply_agents(project, hr, ["alpha"])
            # Hand-edit the generated file
            generated = project / ".claude/agents/alpha.md"
            generated.write_text(generated.read_text() + "\n# manual addendum\n")
            # Mutate HR too so there's an HR-DRIFT in addition to MANUAL-EDIT
            (hr / "engineering" / "alpha.md").write_text(
                "---\nname: alpha\ndescription: Alpha v2\nmodel: sonnet\n---\n\nv2 body.\n",
            )
            write_manifest(hr)
            git(["add", "-A"], cwd=hr)
            git(["commit", "-q", "-m", "v2"], cwd=hr)
            cmd = [sys.executable, str(SYNC),
                   "--project-root", str(project),
                   "--hr-repo", str(hr)]
            result = subprocess.run(cmd, input="\n", capture_output=True, text=True, check=False)
            # Default-skip should leave file with manual edit intact and exit 1 (declined)
            self.assertEqual(result.returncode, 1)
            self.assertIn("manual addendum", generated.read_text(),
                          "manual edit preserved when prompt defaults to skip")


class TestSyncAliasWithOverlay(unittest.TestCase):
    """Codex round-2: alias rename + overlay must rewrite the overlay's
    agent_id frontmatter to match the new canonical id, otherwise
    compute_agent rejects it."""

    def test_alias_rename_preserves_overlay_with_rewritten_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            overlays = project / ".claude/staff/overlays"
            overlays.mkdir(parents=True)
            (overlays / "alpha.md").write_text(
                "---\nagent_id: alpha\nlast_reviewed: 2026-05-09\n---\n\n## Project\n\nAlpha context.\n",
            )
            apply_agents(project, hr, ["alpha"])

            # Rename alpha → aleph upstream
            (hr / "engineering" / "alpha.md").rename(hr / "engineering" / "aleph.md")
            new_path = hr / "engineering" / "aleph.md"
            new_path.write_text(
                new_path.read_text().replace("name: alpha", "name: aleph"),
            )
            import hashlib
            def sha256(s: str) -> str:
                return "sha256:" + hashlib.sha256(s.strip().encode("utf-8")).hexdigest()
            text = new_path.read_text()
            body = text.split("---", 2)[2]
            beta_text = (hr / "engineering" / "beta.md").read_text()
            beta_body = beta_text.split("---", 2)[2]
            manifest = {
                "schema_version": 1,
                "agents": {
                    "aleph": {
                        "file": "engineering/aleph.md",
                        "category": "engineering",
                        "description": "Alpha v1",
                        "description_summary": "Alpha v1",
                        "description_hash": sha256("Alpha v1"),
                        "body_hash": sha256(body),
                        "tags": ["aleph"],
                        "project_hints": {"files": [], "regex": []},
                        "conflicts": [],
                        "introduced": "2026-01-01",
                        "aliases": ["alpha"],
                    },
                    "beta": {
                        "file": "engineering/beta.md",
                        "category": "engineering",
                        "description": "Beta v1",
                        "description_summary": "Beta v1",
                        "description_hash": sha256("Beta v1"),
                        "body_hash": sha256(beta_body),
                        "tags": ["beta"],
                        "project_hints": {"files": [], "regex": []},
                        "conflicts": [],
                        "introduced": "2026-01-01",
                        "aliases": [],
                    },
                },
            }
            (hr / "agent.manifest.yaml").write_text(yaml.safe_dump(manifest))
            git(["add", "-A"], cwd=hr)
            git(["commit", "-q", "-m", "rename"], cwd=hr)

            run_sync(project, hr=hr, extra=["--yes"], expect_exit=0)
            # New overlay path with rewritten agent_id
            new_overlay = overlays / "aleph.md"
            self.assertTrue(new_overlay.is_file(), "overlay migrated to new canonical name")
            self.assertFalse((overlays / "alpha.md").exists(),
                             "old overlay path removed")
            content = new_overlay.read_text()
            self.assertIn("agent_id: aleph", content,
                          "overlay frontmatter agent_id rewritten to canonical")
            self.assertIn("Alpha context", content,
                          "overlay body preserved verbatim")
            # Generated file has both new HR content AND the migrated overlay
            generated = (project / ".claude/agents/aleph.md").read_text()
            self.assertIn("Alpha context", generated,
                          "overlay merged into renamed generated file")

    def test_overlay_collision_aborts_safely(self) -> None:
        """If both old and new overlay paths exist, sync must abort with a
        named error rather than silently dropping the old one."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            overlays = project / ".claude/staff/overlays"
            overlays.mkdir(parents=True)
            # Create alpha overlay AND a stray aleph overlay
            (overlays / "alpha.md").write_text(
                "---\nagent_id: alpha\nlast_reviewed: 2026-05-09\n---\n\nold notes\n",
            )
            (overlays / "aleph.md").write_text(
                "---\nagent_id: aleph\nlast_reviewed: 2026-05-09\n---\n\nstray notes\n",
            )
            apply_agents(project, hr, ["alpha"])

            # Rename alpha → aleph upstream
            (hr / "engineering" / "alpha.md").rename(hr / "engineering" / "aleph.md")
            new_path = hr / "engineering" / "aleph.md"
            new_path.write_text(
                new_path.read_text().replace("name: alpha", "name: aleph"),
            )
            import hashlib
            def sha256(s: str) -> str:
                return "sha256:" + hashlib.sha256(s.strip().encode("utf-8")).hexdigest()
            text = new_path.read_text()
            body = text.split("---", 2)[2]
            manifest = yaml.safe_load((hr / "agent.manifest.yaml").read_text())
            manifest["agents"]["aleph"] = {
                "file": "engineering/aleph.md",
                "category": "engineering",
                "description": "Alpha v1",
                "description_summary": "Alpha v1",
                "description_hash": sha256("Alpha v1"),
                "body_hash": sha256(body),
                "tags": ["aleph"],
                "project_hints": {"files": [], "regex": []},
                "conflicts": [],
                "introduced": "2026-01-01",
                "aliases": ["alpha"],
            }
            del manifest["agents"]["alpha"]
            (hr / "agent.manifest.yaml").write_text(yaml.safe_dump(manifest))
            git(["add", "-A"], cwd=hr)
            git(["commit", "-q", "-m", "rename"], cwd=hr)

            r = run_sync(project, hr=hr, extra=["--yes"], expect_exit=5)
            self.assertIn("overlay collision", r.stderr.lower())
            # Both overlays still present (no destructive action taken)
            self.assertTrue((overlays / "alpha.md").exists(),
                            "old overlay preserved on abort")
            self.assertTrue((overlays / "aleph.md").exists(),
                            "new overlay preserved on abort")


class TestSyncAgentsTypos(unittest.TestCase):
    """Codex round-2: --agents with all-unknown ids should exit 2 (loud),
    not 0 (silent success)."""

    def test_all_unknown_ids_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            apply_agents(project, hr, ["alpha"])
            r = run_sync(project, hr=hr,
                         extra=["--yes", "--agents", "nonexistent", "alsobogus"],
                         expect_exit=2)
            self.assertIn("none of the requested agents", r.stderr)


class TestSyncMissingDefaultSkip(unittest.TestCase):
    """Codex round-2: MISSING default should be skip (destructive action
    requires explicit y), not remove."""

    def test_missing_default_skip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            apply_agents(project, hr, ["alpha", "beta"])
            # Retire beta upstream
            (hr / "engineering" / "beta.md").unlink()
            write_manifest(hr, include_beta=False)
            git(["add", "-A"], cwd=hr)
            git(["commit", "-q", "-m", "retire beta"], cwd=hr)
            # Default response (empty input) on the MISSING prompt: skip
            cmd = [sys.executable, str(SYNC),
                   "--project-root", str(project),
                   "--hr-repo", str(hr)]
            result = subprocess.run(cmd, input="\n", capture_output=True, text=True, check=False)
            # Default-skip on the only change → all declined → exit 1
            self.assertEqual(result.returncode, 1,
                             f"default-skip on MISSING should exit 1; stderr={result.stderr}")
            # beta still in lockfile (default declined the removal)
            self.assertIn("beta", lockfile_keys(project),
                          "default-skip preserves the lockfile entry")


class TestSyncDryRunNoPrompts(unittest.TestCase):
    """Codex round-2: --dry-run should not require interactive input."""

    def test_dry_run_no_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            hr = make_fake_hr(root)
            project = root / "proj"
            project.mkdir()
            apply_agents(project, hr, ["alpha"])
            (hr / "engineering" / "alpha.md").write_text(
                "---\nname: alpha\ndescription: Alpha v2\nmodel: sonnet\n---\n\nv2 body.\n",
            )
            write_manifest(hr)
            git(["add", "-A"], cwd=hr)
            git(["commit", "-q", "-m", "v2"], cwd=hr)
            # Dry-run should complete without input. Use stdin=DEVNULL to confirm.
            cmd = [sys.executable, str(SYNC),
                   "--project-root", str(project),
                   "--hr-repo", str(hr), "--dry-run"]
            result = subprocess.run(cmd, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, check=False, timeout=10)
            self.assertEqual(result.returncode, 0)
            self.assertIn("dry-run default", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
