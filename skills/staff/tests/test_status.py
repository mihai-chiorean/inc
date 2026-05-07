#!/usr/bin/env python3
"""Smoke tests for skills/staff/scripts/status.py.

Each test sets up a fake HR git repo, runs /staff apply to populate the
project, then optionally mutates state (HR-side or project-side) and runs
/staff status to verify the right flags are detected."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import yaml


def _sha256(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.strip().encode("utf-8")).hexdigest()


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def _build_manifest_for_fake_hr(hr: Path) -> dict:
    """Mirror what scripts/generate-manifest.py would produce, but for an
    arbitrary repo root (the script hardcodes the real repo's path)."""
    agents: dict[str, dict] = {}
    for cat_dir in sorted(hr.iterdir()):
        if not cat_dir.is_dir():
            continue
        for p in sorted(cat_dir.glob("*.md")):
            text = p.read_text(encoding="utf-8")
            m = _FRONTMATTER_RE.match(text)
            assert m, f"{p} has no frontmatter"
            fm_block, body = m.group(1), m.group(2)
            # permissive parse of name + description
            name = None
            desc = None
            current = None
            for line in fm_block.splitlines():
                key_match = re.match(r"^(name|description|model|color|tools):\s?(.*)$", line)
                if key_match:
                    current = key_match.group(1)
                    if current == "name":
                        name = key_match.group(2).strip()
                    elif current == "description":
                        desc = key_match.group(2)
            assert name and desc, f"{p} missing name or description"
            agents[name] = {
                "file": str(p.relative_to(hr).as_posix()),
                "category": cat_dir.name,
                "description": desc,
                "description_hash": _sha256(desc),
                "body_hash": _sha256(body),
                "tags": [name],
                "project_hints": {"files": [], "regex": []},
                "conflicts": [],
                "introduced": "2026-01-01",
                "aliases": [],
            }
    return {
        "schema_version": 1,
        "generated_by": "test_status.py:_build_manifest_for_fake_hr",
        "source_repo": "fake-hr",
        "agents": dict(sorted(agents.items())),
    }

REPO_ROOT = Path(__file__).resolve().parents[3]
STATUS = REPO_ROOT / "skills/staff/scripts/status.py"
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
    (hr / "engineering" / "alpha.md").write_text(
        "---\nname: alpha\ndescription: Alpha agent v1\nmodel: sonnet\n---\n\nYou are alpha v1.\n",
    )
    (hr / "engineering" / "beta.md").write_text(
        "---\nname: beta\ndescription: Beta agent\nmodel: sonnet\n---\n\nYou are beta.\n",
    )
    # Compute the manifest inline (the real generator hardcodes the repo path)
    manifest = _build_manifest_for_fake_hr(hr)
    (hr / "agent.manifest.yaml").write_text(yaml.safe_dump(manifest))
    git(["init", "-q", "-b", "main"], cwd=hr)
    git(["add", "-A"], cwd=hr)
    git(["commit", "-q", "-m", "initial"], cwd=hr)
    return hr


def regenerate_and_commit_hr(hr: Path, message: str) -> None:
    manifest = _build_manifest_for_fake_hr(hr)
    (hr / "agent.manifest.yaml").write_text(yaml.safe_dump(manifest))
    if git(["status", "--porcelain"], cwd=hr):
        git(["add", "-A"], cwd=hr)
        git(["commit", "-q", "-m", message], cwd=hr)


def apply_agents(project: Path, hr: Path, ids: list[str]) -> None:
    subprocess.check_call(
        [sys.executable, str(APPLY),
         "--project-root", str(project),
         "--hr-repo", str(hr),
         "--agents", *ids],
    )


def run_status(project: Path, hr: Path | None = None,
               extra_args: list[str] | None = None,
               expect_exit: int | None = None) -> dict:
    cmd = [sys.executable, str(STATUS), "--project-root", str(project), "--json"]
    if hr is not None:
        cmd.extend(["--hr-repo", str(hr)])
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if expect_exit is not None and result.returncode != expect_exit:
        print(f"FAIL: expected status exit {expect_exit}, got {result.returncode}")
        print(f"stdout: {result.stdout}\nstderr: {result.stderr}")
        sys.exit(1)
    if not result.stdout.strip():
        return {"_returncode": result.returncode, "_stderr": result.stderr}
    payload = json.loads(result.stdout)
    payload["_returncode"] = result.returncode
    payload["_stderr"] = result.stderr
    return payload


def find_status(payload: dict, agent_id: str) -> dict | None:
    for s in payload.get("staffed", []):
        if s["id"] == agent_id:
            return s
    return None


def test_clean_status_after_apply(root: Path) -> None:
    print("test_clean_status_after_apply")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    apply_agents(project, hr, ["alpha", "beta"])
    s = run_status(project, hr=hr, expect_exit=0)
    expect(len(s["staffed"]) == 2, "two agents in status")
    expect(all(a["ok"] for a in s["staffed"]), "both agents OK")
    expect(s["orphan_files"] == [], "no orphans")


def test_hr_drift_detected(root: Path) -> None:
    print("test_hr_drift_detected")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    apply_agents(project, hr, ["alpha"])
    # Mutate HR alpha body, regenerate manifest, commit
    (hr / "engineering" / "alpha.md").write_text(
        "---\nname: alpha\ndescription: Alpha agent v1\nmodel: sonnet\n---\n\nYou are alpha v2 (updated).\n",
    )
    regenerate_and_commit_hr(hr, "alpha v2")
    s = run_status(project, hr=hr, expect_exit=1)
    a = find_status(s, "alpha")
    expect(a is not None, "alpha in status")
    expect("HR-DRIFT" in a["flags"], "HR-DRIFT detected after HR body change")


def test_manual_edit_detected(root: Path) -> None:
    print("test_manual_edit_detected")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    apply_agents(project, hr, ["alpha"])
    # Hand-edit the merged file
    p = project / ".claude/agents/alpha.md"
    p.write_text(p.read_text() + "\nA hand-written tweak.\n")
    s = run_status(project, hr=hr, expect_exit=1)
    a = find_status(s, "alpha")
    expect("MANUAL-EDIT" in a["flags"], "MANUAL-EDIT detected on hand-edited generated file")


def test_missing_generated_file(root: Path) -> None:
    print("test_missing_generated_file")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    apply_agents(project, hr, ["alpha"])
    (project / ".claude/agents/alpha.md").unlink()
    s = run_status(project, hr=hr, expect_exit=1)
    a = find_status(s, "alpha")
    expect("MISSING" in a["flags"], "MISSING detected when generated file deleted")


def test_orphan_file_detected(root: Path) -> None:
    print("test_orphan_file_detected")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    apply_agents(project, hr, ["alpha"])
    # Drop a stray .md into .claude/agents/ that isn't in the lockfile
    (project / ".claude/agents/foreign.md").write_text(
        "---\nname: foreign\ndescription: from another HR\n---\n\nbody\n",
    )
    s = run_status(project, hr=hr, expect_exit=1)
    expect("foreign" in s["orphan_files"], "orphan file flagged")


def test_overlay_edited_detected(root: Path) -> None:
    print("test_overlay_edited_detected")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    overlays = project / ".claude/staff/overlays"
    overlays.mkdir(parents=True)
    overlay_path = overlays / "alpha.md"
    overlay_path.write_text(
        "---\nagent_id: alpha\nlast_reviewed: 2026-05-07\n---\n\n## Project\n\nOriginal note.\n",
    )
    apply_agents(project, hr, ["alpha"])
    # Edit overlay body without re-applying
    overlay_path.write_text(
        "---\nagent_id: alpha\nlast_reviewed: 2026-05-07\n---\n\n## Project\n\nEdited note.\n",
    )
    s = run_status(project, hr=hr, expect_exit=1)
    a = find_status(s, "alpha")
    expect("OVERLAY-EDITED" in a["flags"], "OVERLAY-EDITED detected on body change without re-apply")


def test_overlay_stale_detected(root: Path) -> None:
    print("test_overlay_stale_detected")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    overlays = project / ".claude/staff/overlays"
    overlays.mkdir(parents=True)
    old = (date.today() - timedelta(days=200)).isoformat()
    (overlays / "alpha.md").write_text(
        f"---\nagent_id: alpha\nlast_reviewed: {old}\n---\n\n## Project\n\nNote.\n",
    )
    apply_agents(project, hr, ["alpha"])
    s = run_status(project, hr=hr, expect_exit=1)
    a = find_status(s, "alpha")
    expect("OVERLAY-STALE" in a["flags"], "OVERLAY-STALE detected for >90d-old last_reviewed")


def test_alias_renamed_detected(root: Path) -> None:
    print("test_alias_renamed_detected")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    apply_agents(project, hr, ["alpha"])
    # Lockfile has 'alpha' as canonical. Now rename: in HR, alpha's id becomes 'gamma'
    # with 'alpha' moved to aliases.
    manifest = yaml.safe_load((hr / "agent.manifest.yaml").read_text())
    manifest["agents"]["gamma"] = {**manifest["agents"]["alpha"], "aliases": ["alpha"]}
    del manifest["agents"]["alpha"]
    (hr / "agent.manifest.yaml").write_text(yaml.safe_dump(manifest))
    git(["add", "-A"], cwd=hr)
    git(["commit", "-q", "-m", "rename alpha->gamma"], cwd=hr)
    s = run_status(project, hr=hr, expect_exit=1)
    a = find_status(s, "alpha")
    expect("ALIAS-RENAMED" in a["flags"], "ALIAS-RENAMED detected when canonical id changed")
    expect(a["canonical_id"] == "gamma", "canonical_id resolves to new name")


def test_no_lockfile_exits_2(root: Path) -> None:
    print("test_no_lockfile_exits_2")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    res = run_status(project, hr=hr, expect_exit=2)
    expect("lockfile" in res["_stderr"].lower(), "stderr mentions missing lockfile")


def test_text_output_lists_clean_and_dirty(root: Path) -> None:
    print("test_text_output_lists_clean_and_dirty")
    hr = make_fake_hr(root)
    project = root / "proj"
    project.mkdir()
    apply_agents(project, hr, ["alpha", "beta"])
    # Make beta dirty via manual edit
    (project / ".claude/agents/beta.md").write_text("hand edit\n")
    cmd = [sys.executable, str(STATUS), "--project-root", str(project), "--hr-repo", str(hr)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    expect(result.returncode == 1, "exit 1 with drift")
    expect("OK" in result.stdout, "text output has OK section")
    expect("NEEDS ATTENTION" in result.stdout, "text output has NEEDS ATTENTION section")
    expect("alpha" in result.stdout and "beta" in result.stdout, "both agents listed")
    expect("MANUAL-EDIT" in result.stdout, "MANUAL-EDIT flag visible in text output")


def main() -> int:
    if not STATUS.exists():
        print(f"script not found: {STATUS}", file=sys.stderr)
        return 1
    tests = [
        test_clean_status_after_apply,
        test_hr_drift_detected,
        test_manual_edit_detected,
        test_missing_generated_file,
        test_orphan_file_detected,
        test_overlay_edited_detected,
        test_overlay_stale_detected,
        test_alias_renamed_detected,
        test_no_lockfile_exits_2,
        test_text_output_lists_clean_and_dirty,
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
