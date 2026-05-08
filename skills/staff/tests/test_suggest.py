#!/usr/bin/env python3
"""Smoke tests for skills/staff/scripts/suggest.py.

Run: python3 skills/staff/tests/test_suggest.py
Exits 0 on success, 1 on any failure.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "skills/staff/scripts/suggest.py"
HR_REPO = REPO_ROOT


def run_suggest(project_root: Path, json_output: bool = True, extra_args: list[str] | None = None) -> dict | str:
    # Tests default to --no-llm: this is the deterministic path, what we want
    # to assert behavior on. LLM-mode tests pass extra_args=["--llm-provider", ...] explicitly.
    cmd = [sys.executable, str(SCRIPT), "--project-root", str(project_root), "--hr-repo", str(HR_REPO), "--no-llm"]
    if json_output:
        cmd.append("--json")
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"suggest exited {result.returncode}: {result.stderr}")
    return json.loads(result.stdout) if json_output else result.stdout


def expect(condition: bool, msg: str) -> None:
    if not condition:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


def test_empty_project_no_matches(tmp: Path) -> None:
    print("test_empty_project_no_matches")
    out = run_suggest(tmp)
    expect(isinstance(out["suggested"], list), "suggested is a list")
    expect(len(out["suggested"]) == 0, "empty project matches no agents")


def test_go_project_matches_go_engineer(tmp: Path) -> None:
    print("test_go_project_matches_go_engineer")
    (tmp / "go.mod").write_text("module example.com/foo\n\ngo 1.22\n")
    out = run_suggest(tmp)
    ids = {p["id"] for p in out["suggested"]}
    expect("go-engineer" in ids, "go.mod triggers go-engineer")


def test_swift_project_matches_swift_backend(tmp: Path) -> None:
    print("test_swift_project_matches_swift_backend")
    (tmp / "Package.swift").write_text("// swift-tools-version: 5.9\n")
    (tmp / "README.md").write_text("Built on Hummingbird and postgres-nio.\n")
    out = run_suggest(tmp)
    ids = {p["id"] for p in out["suggested"]}
    expect("swift-backend" in ids, "Package.swift + Hummingbird match swift-backend")
    sb = next(p for p in out["suggested"] if p["id"] == "swift-backend")
    expect(any("Package.swift" in r for r in sb["reasons"]), "reason mentions Package.swift")
    expect(any("hummingbird" in r.lower() for r in sb["reasons"]), "reason mentions hummingbird")


def test_proto_files_match_grpc_contracts(tmp: Path) -> None:
    print("test_proto_files_match_grpc_contracts")
    (tmp / "api").mkdir()
    (tmp / "api/foo.proto").write_text('syntax = "proto3";\n')
    out = run_suggest(tmp)
    ids = {p["id"] for p in out["suggested"]}
    expect("grpc-contracts" in ids, "*.proto file matches grpc-contracts")


def test_regex_only_match_in_claude_md(tmp: Path) -> None:
    print("test_regex_only_match_in_claude_md")
    (tmp / "CLAUDE.md").write_text("# Project\n\nWe use CUDA and TensorRT for inference.\n")
    out = run_suggest(tmp)
    ids = {p["id"] for p in out["suggested"]}
    expect("gpu-engineer" in ids, "CUDA mention matches gpu-engineer via regex only")


def test_unrelated_text_does_not_match(tmp: Path) -> None:
    print("test_unrelated_text_does_not_match")
    (tmp / "README.md").write_text("# A meditation app for cats.\n")
    out = run_suggest(tmp)
    ids = {p["id"] for p in out["suggested"]}
    expect("go-engineer" not in ids, "no go.mod, no go regex → no go-engineer")
    expect("swift-backend" not in ids, "no swift signal → no swift-backend")


def test_all_flag_includes_unmatched(tmp: Path) -> None:
    print("test_all_flag_includes_unmatched")
    out = run_suggest(tmp, extra_args=["--all"])
    expect("unmatched" in out, "--all surfaces unmatched list")
    expect(len(out["unmatched"]) > 0, "unmatched is non-empty for empty project")


def test_directory_hint_matches(tmp: Path) -> None:
    print("test_directory_hint_matches")
    (tmp / "migrations").mkdir()
    (tmp / "migrations" / "0001_init.sql").write_text("create table x ();\n")
    out = run_suggest(tmp)
    ids = {p["id"] for p in out["suggested"]}
    expect("db-migration" in ids, "migrations/ directory triggers db-migration")


def test_shallow_glob_matches(tmp: Path) -> None:
    print("test_shallow_glob_matches")
    (tmp / "kas").mkdir()
    (tmp / "kas" / "jetson.yml").write_text("header: { version: '14' }\n")
    out = run_suggest(tmp)
    ids = {p["id"] for p in out["suggested"]}
    expect("embedded-linux" in ids, "kas/*.yml triggers embedded-linux")


def test_no_doc_files_no_regex_match(tmp: Path) -> None:
    print("test_no_doc_files_no_regex_match")
    # No CLAUDE.md, no README, but has a .cu file (gpu-engineer regex+files both fire)
    out = run_suggest(tmp)
    expect(len(out["suggested"]) == 0, "no doc files and no source files → no matches")


def test_json_schema_includes_versioning(tmp: Path) -> None:
    print("test_json_schema_includes_versioning")
    out = run_suggest(tmp)
    expect("schema_version" in out, "JSON has schema_version")
    expect(out["schema_version"] == 1, "schema_version == 1 for v1")
    expect("manifest_hash" in out, "JSON has manifest_hash")
    expect(out["manifest_hash"].startswith("sha256:"), "manifest_hash is sha256:")
    expect("hr_commit" in out, "JSON has hr_commit (may be null if HR is not a git repo)")
    expect("hr_repo" in out and "project_root" in out, "JSON has hr_repo + project_root")


def test_invalid_hr_repo_url_scheme(tmp: Path) -> None:
    print("test_invalid_hr_repo_url_scheme")
    cmd = [
        sys.executable, str(SCRIPT),
        "--project-root", str(tmp),
        "--hr-repo", "https://example.com/agents",
        "--no-llm", "--json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    expect(result.returncode != 0, "non-file:// HR URL exits non-zero")
    expect("scheme" in result.stderr.lower() or "unsupported" in result.stderr.lower(),
           "stderr names the scheme issue")


def test_file_url_with_spaces(tmp: Path) -> None:
    print("test_file_url_with_spaces")
    # The HR repo path contains no spaces in our setup, but the file:// form should still work.
    file_url = f"file://{HR_REPO}"
    cmd = [
        sys.executable, str(SCRIPT),
        "--project-root", str(tmp),
        "--hr-repo", file_url,
        "--no-llm", "--json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    expect(result.returncode == 0, "file:// URL is accepted")
    out = json.loads(result.stdout)
    expect(out["hr_repo"] == str(HR_REPO), "file:// URL resolves to plain path")


def test_deterministic_ordering(tmp: Path) -> None:
    print("test_deterministic_ordering")
    (tmp / "go.mod").write_text("module a\n")
    (tmp / "Package.swift").write_text("// swift-tools-version: 5.9\n")
    out_a = run_suggest(tmp)
    out_b = run_suggest(tmp)
    ids_a = [p["id"] for p in out_a["suggested"]]
    ids_b = [p["id"] for p in out_b["suggested"]]
    expect(ids_a == ids_b, "two runs produce identical ordering")
    expect(ids_a == sorted(ids_a), "agents emitted in sorted order by id")


def test_excluded_dirs_skip_globs(tmp: Path) -> None:
    print("test_excluded_dirs_skip_globs")
    # Put a .proto inside .git — should be ignored
    (tmp / ".git").mkdir()
    (tmp / ".git" / "hooks.proto").write_text('syntax = "proto3";\n')
    (tmp / "node_modules").mkdir()
    (tmp / "node_modules" / "deep.proto").write_text('syntax = "proto3";\n')
    out = run_suggest(tmp)
    ids = {p["id"] for p in out["suggested"]}
    expect("grpc-contracts" not in ids, "*.proto in .git/node_modules ignored")


def test_glob_depth_cap(tmp: Path) -> None:
    print("test_glob_depth_cap")
    # Build a path 6 levels deep with a .proto leaf — should be excluded
    deep = tmp / "a" / "b" / "c" / "d" / "e" / "f"
    deep.mkdir(parents=True)
    (deep / "leaf.proto").write_text('syntax = "proto3";\n')
    out = run_suggest(tmp)
    ids = {p["id"] for p in out["suggested"]}
    expect("grpc-contracts" not in ids, "deeply nested *.proto excluded by depth cap")


def test_directory_hint_with_slash_path(tmp: Path) -> None:
    print("test_directory_hint_with_slash_path")
    (tmp / ".github").mkdir()
    (tmp / ".github" / "workflows").mkdir()
    out = run_suggest(tmp)
    ids = {p["id"] for p in out["suggested"]}
    expect("devops-automator" in ids, ".github/workflows directory triggers devops-automator")


def test_match_json_field_structure(tmp: Path) -> None:
    print("test_match_json_field_structure")
    (tmp / "go.mod").write_text("module x\n")
    (tmp / "CLAUDE.md").write_text("This project uses Cobra.\n")
    out = run_suggest(tmp)
    go = next((p for p in out["suggested"] if p["id"] == "go-engineer"), None)
    expect(go is not None, "go-engineer in proposals")
    expect("matches" in go, "proposal has matches[] structured field")
    expect(isinstance(go["matches"], list) and len(go["matches"]) >= 1, "matches has entries")
    file_matches = [m for m in go["matches"] if m["type"] == "file"]
    regex_matches = [m for m in go["matches"] if m["type"] == "regex"]
    expect(len(file_matches) >= 1, "go.mod produces a file match")
    expect("paths" in file_matches[0], "file match has 'paths'")
    expect(len(regex_matches) >= 1, "Cobra mention produces a regex match")
    expect("snippet" in regex_matches[0], "regex match has 'snippet'")
    expect("doc" in regex_matches[0], "regex match has 'doc' (which doc file matched)")


def test_malformed_project_config(tmp: Path) -> None:
    print("test_malformed_project_config")
    (tmp / ".claude" / "staff").mkdir(parents=True)
    (tmp / ".claude/staff/config.yaml").write_text(": not valid yaml :::\n")
    # Don't pass --hr-repo here: config is consulted only when there's no override,
    # so this is the path where the malformed config actually matters.
    cmd = [
        sys.executable, str(SCRIPT),
        "--project-root", str(tmp),
        "--no-llm", "--json",
    ]
    env = {**os.environ}
    env.pop("STAFF_HR_REPO", None)  # ensure we hit the config path, not env
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    expect(result.returncode == 2, "malformed project config exits 2 when consulted")
    expect("config" in result.stderr.lower() or "yaml" in result.stderr.lower(),
           "stderr mentions config/yaml")
    expect("Traceback" not in result.stderr, "no python traceback leaks")


def test_malformed_config_ignored_when_overridden(tmp: Path) -> None:
    """If --hr-repo is passed, a malformed config is NOT consulted, so it
    should be silently bypassed. Override wins."""
    print("test_malformed_config_ignored_when_overridden")
    (tmp / ".claude" / "staff").mkdir(parents=True)
    (tmp / ".claude/staff/config.yaml").write_text(": not valid yaml :::\n")
    cmd = [
        sys.executable, str(SCRIPT),
        "--project-root", str(tmp),
        "--hr-repo", str(HR_REPO),
        "--no-llm", "--json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    expect(result.returncode == 0, "override bypasses config validation")


def test_malformed_manifest_shape(tmp: Path) -> None:
    print("test_malformed_manifest_shape")
    fake_hr = tmp / "fake-hr"
    fake_hr.mkdir()
    # Missing 'agents' key entirely
    (fake_hr / "agent.manifest.yaml").write_text("schema_version: 1\n")
    cmd = [sys.executable, str(SCRIPT), "--project-root", str(tmp), "--hr-repo", str(fake_hr), "--no-llm", "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    expect(result.returncode == 2, "manifest missing 'agents' exits 2")
    expect("agents" in result.stderr.lower(), "stderr mentions missing agents key")
    expect("Traceback" not in result.stderr, "no python traceback leaks")


def test_missing_manifest(tmp: Path) -> None:
    print("test_missing_manifest")
    fake_hr = tmp / "empty-hr"
    fake_hr.mkdir()
    cmd = [sys.executable, str(SCRIPT), "--project-root", str(tmp), "--hr-repo", str(fake_hr), "--no-llm", "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    expect(result.returncode == 2, "missing manifest exits 2")
    expect("manifest" in result.stderr.lower(), "stderr mentions missing manifest")


def test_invalid_regex_in_manifest_does_not_crash(tmp: Path) -> None:
    """Ensure a malformed regex in a custom manifest doesn't crash the script."""
    print("test_invalid_regex_in_manifest_does_not_crash")
    # Build a tiny custom HR repo with one bad-regex agent
    fake_hr = tmp / "fake-hr"
    fake_hr.mkdir()
    fake_manifest = {
        "schema_version": 1,
        "agents": {
            "broken-agent": {
                "file": "x.md",
                "category": "engineering",
                "description": "x",
                "description_hash": "sha256:0",
                "body_hash": "sha256:0",
                "tags": ["x"],
                "project_hints": {"files": [], "regex": ["[unterminated"]},
                "conflicts": [],
                "introduced": "2026-01-01",
                "aliases": [],
            }
        },
    }
    import yaml as _yaml
    (fake_hr / "agent.manifest.yaml").write_text(_yaml.safe_dump(fake_manifest))
    project = tmp / "proj"
    project.mkdir()
    (project / "README.md").write_text("anything\n")
    cmd = [
        sys.executable, str(SCRIPT),
        "--project-root", str(project),
        "--hr-repo", str(fake_hr),
        "--no-llm", "--json",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    expect(result.returncode == 0, "invalid regex does not crash; warning to stderr")
    expect("invalid regex" in result.stderr.lower() or "warning" in result.stderr.lower(),
           "stderr mentions the bad regex")
    out = json.loads(result.stdout)
    expect(out["suggested"] == [], "broken agent yields no match")


def main() -> int:
    if not SCRIPT.exists():
        print(f"script not found: {SCRIPT}", file=sys.stderr)
        return 1

    tests = [
        test_empty_project_no_matches,
        test_go_project_matches_go_engineer,
        test_swift_project_matches_swift_backend,
        test_proto_files_match_grpc_contracts,
        test_regex_only_match_in_claude_md,
        test_unrelated_text_does_not_match,
        test_all_flag_includes_unmatched,
        test_directory_hint_matches,
        test_shallow_glob_matches,
        test_no_doc_files_no_regex_match,
        test_json_schema_includes_versioning,
        test_invalid_hr_repo_url_scheme,
        test_file_url_with_spaces,
        test_deterministic_ordering,
        test_excluded_dirs_skip_globs,
        test_glob_depth_cap,
        test_directory_hint_with_slash_path,
        test_match_json_field_structure,
        test_malformed_project_config,
        test_malformed_config_ignored_when_overridden,
        test_malformed_manifest_shape,
        test_missing_manifest,
        test_invalid_regex_in_manifest_does_not_crash,
    ]

    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            try:
                fn(Path(d))
            except Exception as exc:
                print(f"FAIL: {fn.__name__}: {exc}")
                return 1

    print(f"\n{len(tests)}/{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
