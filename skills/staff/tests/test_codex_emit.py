#!/usr/bin/env python3
"""Smoke tests for skills/staff/scripts/codex_emit.py.

Covers the inc agent .md -> Codex subagent TOML conversion: valid TOML output,
required-field mapping, the model->reasoning-effort translation, escaping of
nasty bodies (backslashes, quotes, triple-quotes, code fences), and the
--user batch emitter against a fake HR repo.
"""

from __future__ import annotations

import sys
import tempfile
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "skills/staff/scripts"))

import codex_emit  # noqa: E402


def expect(condition: bool, msg: str) -> None:
    if not condition:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  ok: {msg}")


def _agent(name: str, description: str, body: str, model: str = "opus") -> str:
    return f"---\nname: {name}\nmodel: {model}\ndescription: {description!r}\n---\n{body}\n"


def test_basic_conversion(_root: Path) -> None:
    md = _agent("go-engineer", "Use when writing Go.", "You are a Go expert.\n\n## Rules\n- ship")
    name, toml = codex_emit.agent_md_to_toml(md)
    data = tomllib.loads(toml)  # must be valid TOML
    expect(name == "go-engineer", "name returned")
    expect(data["name"] == "go-engineer", "name in toml")
    expect(data["description"] == "Use when writing Go.", "description maps through")
    expect("You are a Go expert." in data["developer_instructions"], "body -> developer_instructions")
    expect(data["developer_instructions"].rstrip().endswith("- ship"), "full body preserved")


def test_model_to_effort(_root: Path) -> None:
    for model, effort in [("opus", "high"), ("sonnet", "medium"), ("haiku", "low")]:
        _name, toml = codex_emit.agent_md_to_toml(_agent("a", "d", "b", model))
        data = tomllib.loads(toml)
        expect(data.get("model_reasoning_effort") == effort, f"{model} -> effort {effort}")
    # unknown / non-tier model id is dropped (Codex inherits its own model)
    data = tomllib.loads(codex_emit.agent_md_to_toml(_agent("a", "d", "b", "gpt-5.5"))[1])
    expect("model_reasoning_effort" not in data, "unknown model tier dropped")
    expect("model" not in data, "raw model field never emitted (cross-vendor)")


def test_nasty_body_escaping(_root: Path) -> None:
    body = (
        'Regex: \\d+\\.\\w  and a path C:\\temp\\x\n'
        'A "quoted" phrase and a triple """ inside.\n'
        '```python\nprint("""x""")\n```\n'
        'Trailing quote here "'
    )
    md = _agent("nasty", "edge cases", body)
    _name, toml = codex_emit.agent_md_to_toml(md)
    data = tomllib.loads(toml)  # the real assertion: it parses at all
    out = data["developer_instructions"]
    expect("\\d+\\.\\w" in out, "backslash sequences preserved verbatim")
    expect('"quoted"' in out, "double quotes preserved")
    expect('"""' in out, "triple quotes preserved")
    expect('print("""x""")' in out, "code fence with triple quotes preserved")


def test_missing_fields_raise(_root: Path) -> None:
    for bad, why in [
        ("---\nname: x\nmodel: opus\n---\nbody", "no description"),
        ("---\nname: x\nmodel: opus\ndescription: ''\n---\nbody", "empty description"),
        ("---\nname: x\nmodel: opus\ndescription: d\n---\n", "empty body"),
    ]:
        try:
            codex_emit.agent_md_to_toml(bad)
            expect(False, f"should raise on {why}")
        except ValueError:
            expect(True, f"raises on {why}")


def test_emit_user_batch(root: Path) -> None:
    # Fake HR repo: one org agent, one project agent, one skill.
    hr = root / "hr"
    (hr / "engineering").mkdir(parents=True)
    (hr / "writing").mkdir(parents=True)
    (hr / "skills" / "demo").mkdir(parents=True)
    (hr / "engineering" / "org-one.md").write_text(
        "---\nname: org-one\nmodel: sonnet\nscope: org\ndescription: org agent\n---\nYou are org-one.\n")
    (hr / "writing" / "proj-one.md").write_text(
        "---\nname: proj-one\nmodel: haiku\ndescription: project agent\n---\nYou are proj-one.\n")
    (hr / "skills" / "demo" / "SKILL.md").write_text(
        "---\nname: demo\ndescription: a demo skill\n---\n# Demo\n")
    (hr / "agent.manifest.yaml").write_text(
        "schema_version: 1\nagents:\n"
        "  org-one: {file: engineering/org-one.md}\n"
        "  proj-one: {file: writing/proj-one.md}\n")

    codex_home = root / "codexhome"
    rc = codex_emit.emit_user(hr, codex_home, do_skills=True)
    expect(rc == 0, "emit_user returns 0")
    emitted = sorted(p.name for p in (codex_home / "agents").glob("*.toml"))
    expect(emitted == ["org-one.toml"], "only scope:org agent emitted (not project agent)")
    expect((codex_home / "skills" / "demo" / "SKILL.md").exists(), "skill mirrored")
    data = tomllib.loads((codex_home / "agents" / "org-one.toml").read_text())
    expect(data["model_reasoning_effort"] == "medium", "sonnet -> medium in batch path")


def test_emit_project_pinned_source_and_safe_prune(root: Path) -> None:
    # Project with two staffed agents, applied to .claude/agents/ (the pinned
    # artifacts Codex must mirror — NOT HR HEAD).
    proj = root / "proj"
    (proj / ".claude" / "agents").mkdir(parents=True)
    (proj / ".claude" / "staff").mkdir(parents=True)
    (proj / ".claude" / "agents" / "alpha.md").write_text(
        "---\nname: alpha\nmodel: opus\ndescription: alpha desc\n---\nPINNED-ALPHA-BODY\n")
    (proj / ".claude" / "agents" / "beta.md").write_text(
        "---\nname: beta\nmodel: haiku\ndescription: beta desc\n---\nBETA-BODY\n")
    (proj / ".claude" / "staff" / "lock.yaml").write_text(
        "schema_version: 1\nstaffed:\n"
        "  alpha: {file: engineering/alpha.md}\n"
        "  beta: {file: engineering/beta.md}\n")

    # Pre-seed .codex/agents with a STALE generated file (unstaffed gamma) and a
    # HAND-MADE file (no header) that pruning must never touch.
    codex_agents = proj / ".codex" / "agents"
    codex_agents.mkdir(parents=True)
    (codex_agents / "gamma.toml").write_text(
        "# Generated from inc agent 'gamma' by `staff codex` — do not edit.\n"
        'name = "gamma"\n')
    (codex_agents / "handmade.toml").write_text('name = "handmade"\n# mine\n')

    rc = codex_emit.emit_project(proj)
    expect(rc == 0, "emit_project returns 0")

    alpha = tomllib.loads((codex_agents / "alpha.toml").read_text())
    expect("PINNED-ALPHA-BODY" in alpha["developer_instructions"],
           "emits from applied .claude/agents/<id>.md (pinned), not HR")
    expect((codex_agents / "beta.toml").exists(), "second staffed agent emitted")
    expect(not (codex_agents / "gamma.toml").exists(),
           "stale inc-generated TOML pruned")
    expect((codex_agents / "handmade.toml").exists(),
           "hand-made TOML (no header) survives prune")


def test_user_emit_defaults_hr_to_inc_repo(root: Path) -> None:
    # `staff codex --user` with no --hr-repo / env / project config must still
    # work — it defaults to the inc repo this script lives in. (Regression: it
    # used to raise from cwd-based HR discovery.)
    import os
    saved = os.environ.pop("STAFF_HR_REPO", None)
    try:
        rc = codex_emit.main(["--user", "--codex-home", str(root / "ch")])
        expect(rc == 0, "main --user returns 0 without --hr-repo")
        emitted = list((root / "ch" / "agents").glob("*.toml"))
        expect(len(emitted) > 0, "org subagents emitted from inferred inc repo")
    finally:
        if saved is not None:
            os.environ["STAFF_HR_REPO"] = saved


def test_codex_hook_never_raises_on_bad_config(root: Path) -> None:
    # apply._maybe_emit_codex must swallow a malformed project config rather than
    # crash a successful apply/sync.
    import apply
    proj = root / "proj"
    (proj / ".claude" / "staff").mkdir(parents=True)
    (proj / ".claude" / "staff" / "config.yaml").write_text("emit_codex: true\n: : not yaml\n")
    apply._maybe_emit_codex(proj, root)  # must not raise
    expect(True, "_maybe_emit_codex swallowed malformed config")


def main() -> int:
    tests = [
        test_basic_conversion,
        test_model_to_effort,
        test_nasty_body_escaping,
        test_missing_fields_raise,
        test_emit_user_batch,
        test_emit_project_pinned_source_and_safe_prune,
        test_user_emit_defaults_hr_to_inc_repo,
        test_codex_hook_never_raises_on_bad_config,
    ]
    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            try:
                fn(Path(d))
            except SystemExit:
                raise
            except Exception as exc:  # noqa: BLE001
                print(f"FAIL: {fn.__name__}: {exc!r}")
                return 1
    print(f"\n{len(tests)}/{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
