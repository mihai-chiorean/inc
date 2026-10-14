#!/usr/bin/env python3
"""Tests for scripts/validate-agents.py.

MIT-413: Verify the validator matches Anthropic's published spec for agent
and skill frontmatter (research/agent-skill-spec-ground-truth-MIT-410.md):
spec-correct fields don't warn, non-spec fields warn (will tighten to HARD
after MIT-412), skill description+when_to_use cap is enforced at 1,536
chars, and the inc-repo `scope:` carve-out on agents is silent.

We invoke the validator as a subprocess against a temp tree to avoid
coupling tests to the live repo's category dirs and skill set."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR = REPO_ROOT / "scripts/validate-agents.py"


def run_validator(root: Path, *extra_args: str) -> tuple[int, dict]:
    """Run the validator with REPO_ROOT pointed at `root`. The validator
    resolves REPO_ROOT from __file__, so we copy it into the temp tree."""
    # Mirror the repo layout the validator expects: scripts/ + category dirs
    # + skills/ at the same parent.
    tmp_validator = root / "scripts" / "validate-agents.py"
    tmp_validator.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(VALIDATOR, tmp_validator)
    result = subprocess.run(
        [sys.executable, str(tmp_validator), "--json", *extra_args],
        capture_output=True, text=True, check=False,
    )
    payload = json.loads(result.stdout) if result.stdout.strip() else {}
    return result.returncode, payload


def write_agent(root: Path, category: str, name: str, body: str) -> Path:
    """Write an agent .md under root/<category>/<name>.md."""
    (root / category).mkdir(parents=True, exist_ok=True)
    p = root / category / f"{name}.md"
    p.write_text(body)
    return p


def write_skill(root: Path, name: str, body: str) -> Path:
    """Write a SKILL.md under root/skills/<name>/SKILL.md."""
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    p = skill_dir / "SKILL.md"
    p.write_text(body)
    return p


def write_baseline(
    root: Path,
    grandfathered_agents: list[dict] | None = None,
    grandfathered_skills: list[dict] | None = None,
) -> Path:
    """Write the grandfather baseline next to where the validator will look
    for it (root/scripts/validate-agents-baseline.json). Each entry has
    keys {file, non_spec_keys}; missing entries → new debt → HARD-fail."""
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    baseline = {
        "_comment": "test baseline",
        "grandfathered_agents": grandfathered_agents or [],
        "grandfathered_skills": grandfathered_skills or [],
    }
    p = root / "scripts" / "validate-agents-baseline.json"
    p.write_text(json.dumps(baseline) + "\n")
    return p


def _find(payload: dict, file_suffix: str) -> dict:
    """Locate the result entry for a file path ending with `file_suffix`."""
    for r in payload["results"]:
        if r["file"].endswith(file_suffix):
            return r
    raise AssertionError(f"no result entry ending with {file_suffix!r}; "
                         f"got {[r['file'] for r in payload['results']]}")


class TestAgentValidation(unittest.TestCase):
    def test_agent_with_only_spec_fields_is_clean(self) -> None:
        """An agent using name/description/model/tools/color/skills
        (all in the June-2026 sub-agents.md spec) validates clean."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "alpha",
                        "---\nname: alpha\ndescription: Does the alpha thing.\n"
                        "model: sonnet\ntools: Read Write\ncolor: cyan\n"
                        "skills: [postgres]\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0)
            r = _find(payload, "engineering/alpha.md")
            self.assertEqual(r["hard_errors"], [])
            self.assertEqual(r["warnings"], [])

    def test_agent_with_allowed_tools_hard_fails(self) -> None:
        """allowed-tools is a SKILL field; on an agent it is silently ignored
        (the restriction never takes effect) -> HARD, targeted message."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "alpha",
                        "---\nname: alpha\ndescription: Alpha.\n"
                        "allowed-tools: Read, Write\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 1, "skill-only key on agent must HARD-fail")
            r = _find(payload, "engineering/alpha.md")
            self.assertTrue(any("skill-only" in e and "allowed-tools" in e
                                for e in r["hard_errors"]),
                            f"expected skill-only HARD, got {r['hard_errors']}")

    def test_agent_with_tools_field_is_clean(self) -> None:
        """tools: is the spec allowlist field for agents (June-2026 spec)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "alpha",
                        "---\nname: alpha\ndescription: Alpha.\n"
                        "tools: Read, Write\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0)
            r = _find(payload, "engineering/alpha.md")
            self.assertEqual(r["hard_errors"], [])
            self.assertEqual(r["warnings"], [])

    def test_agent_offenum_color_warns(self) -> None:
        """A color outside the official enum is ignored by the UI -> WARN."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "alpha",
                        "---\nname: alpha\ndescription: Alpha.\n"
                        "color: chartreuse\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0, "off-enum color is WARN, not HARD")
            r = _find(payload, "engineering/alpha.md")
            self.assertTrue(any("color" in w and "chartreuse" in w
                                for w in r["warnings"]),
                            f"expected off-enum color warn, got {r['warnings']}")

    def test_agent_nonspec_key_grandfathered_warns(self) -> None:
        """A truly non-spec key on a grandfathered agent: WARN only (exercises
        the grandfather mechanism with a made-up key)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "alpha",
                        "---\nname: alpha\ndescription: Alpha.\n"
                        "frobnicate: yes\n---\n\nBody.\n")
            write_baseline(root, grandfathered_agents=[
                {"file": "engineering/alpha.md", "non_spec_keys": ["frobnicate"]},
            ])
            code, payload = run_validator(root)
            self.assertEqual(code, 0, "grandfathered non-spec key must NOT HARD-fail")
            r = _find(payload, "engineering/alpha.md")
            self.assertTrue(any("grandfathered" in w and "'frobnicate'" in w
                                for w in r["warnings"]),
                            f"expected grandfather warn, got {r['warnings']}")

    def test_agent_with_scope_does_not_warn(self) -> None:
        """`scope:` is an inc-repo extension consumed by install.sh — carve-out."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "alpha",
                        "---\nname: alpha\ndescription: Alpha.\nscope: org\n---\n\nBody.\n")
            _code, payload = run_validator(root)
            r = _find(payload, "engineering/alpha.md")
            self.assertEqual(r["warnings"], [],
                             f"scope carve-out failed: {r['warnings']}")
            self.assertEqual(r["hard_errors"], [])

    def test_agent_with_long_description_warns(self) -> None:
        """Agents with description > 2000 chars get a WARN (no spec cap)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            long_desc = "x" * 2100
            write_agent(root, "engineering", "verbose",
                        f"---\nname: verbose\ndescription: {long_desc}\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0)
            r = _find(payload, "engineering/verbose.md")
            self.assertEqual(r["hard_errors"], [])
            self.assertTrue(any("description is 2100 chars" in w for w in r["warnings"]),
                            f"expected long-description warn, got {r['warnings']}")


class TestSkillValidation(unittest.TestCase):
    def test_skill_with_when_to_use_is_clean(self) -> None:
        """`when_to_use` is spec — must NOT warn."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(root, "good",
                        "---\nname: good\ndescription: Does the good thing.\n"
                        "when_to_use: When user mentions good.\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0)
            r = _find(payload, "skills/good/SKILL.md")
            self.assertEqual(r["hard_errors"], [])
            self.assertEqual(r["warnings"], [])

    def test_skill_combined_over_cap_hard_fails(self) -> None:
        """Combined description + when_to_use > 1536 chars: HARD-fail."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            desc = "a" * 1000
            wtu = "b" * 600  # combined = 1600 > 1536
            write_skill(root, "fat",
                        f"---\nname: fat\ndescription: {desc}\n"
                        f"when_to_use: {wtu}\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 1, "skill over 1536 char cap must HARD-fail")
            r = _find(payload, "skills/fat/SKILL.md")
            self.assertTrue(any("1600 chars" in e for e in r["hard_errors"]),
                            f"expected 1600-char hard error, got {r['hard_errors']}")

    def test_skill_combined_at_cap_is_clean(self) -> None:
        """Combined description + when_to_use ≤ 1536 chars: no hard, no warn."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            desc = "a" * 1000
            wtu = "b" * 500  # combined = 1500 ≤ 1536
            write_skill(root, "lean",
                        f"---\nname: lean\ndescription: {desc}\n"
                        f"when_to_use: {wtu}\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0)
            r = _find(payload, "skills/lean/SKILL.md")
            self.assertEqual(r["hard_errors"], [])
            self.assertEqual(r["warnings"], [])

    def test_skill_with_non_spec_field_new_hard_fails(self) -> None:
        """Non-spec key on a fresh (non-grandfathered) skill: NEW debt → HARD.
        Uses `references` since `version` is now spec-correct per MIT-437."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(root, "refz",
                        "---\nname: refz\ndescription: Refz.\nreferences: foo\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 1)
            r = _find(payload, "skills/refz/SKILL.md")
            self.assertTrue(any("'references'" in e for e in r["hard_errors"]),
                            f"expected HARD on 'references', got {r['hard_errors']}")

    def test_skill_with_non_spec_field_grandfathered_warns(self) -> None:
        """Grandfathered skills WARN, not HARD, on listed non-spec keys.
        Uses `references` since `version` is now spec-correct per MIT-437."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(root, "refz",
                        "---\nname: refz\ndescription: Refz.\nreferences: foo\n---\n\nBody.\n")
            write_baseline(root, grandfathered_skills=[
                {"file": "skills/refz/SKILL.md", "non_spec_keys": ["references"]},
            ])
            code, payload = run_validator(root)
            self.assertEqual(code, 0)
            r = _find(payload, "skills/refz/SKILL.md")
            self.assertTrue(any("'references'" in w and "grandfathered" in w
                                for w in r["warnings"]))

    def test_skill_top_level_version_warns_move_to_metadata(self) -> None:
        """2026-10: Claude Code's skills table has no `version` /
        `deprecation-notice` (MIT-437 accepted them at top level). They are
        ignored by the loader -> WARN asking to move them under `metadata:`,
        not HARD (they were legal here until now)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(root, "vskill",
                        "---\nname: vskill\ndescription: V.\nversion: 1.0.0\n"
                        "deprecation-notice: Use foo instead\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0)
            r = _find(payload, "skills/vskill/SKILL.md")
            self.assertEqual(r["hard_errors"], [])
            self.assertTrue(any("metadata" in w and "'version'" in w
                                and "'deprecation-notice'" in w
                                for w in r["warnings"]),
                            f"expected move-to-metadata warn, got {r['warnings']}")

    def test_skill_new_official_fields_are_clean(self) -> None:
        """metadata (holding version/references), license, compatibility and
        background are official skill fields (2026-10)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(root, "meta",
                        "---\nname: meta\ndescription: Meta.\nlicense: MIT\n"
                        "compatibility: Needs python3 and gh.\nbackground: true\n"
                        "metadata:\n  version: \"0\"\n  references:\n    - a.md\n"
                        "---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0)
            r = _find(payload, "skills/meta/SKILL.md")
            self.assertEqual(r["hard_errors"], [])
            self.assertEqual(r["warnings"], [])

    def test_skill_metadata_must_be_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(root, "meta",
                        "---\nname: meta\ndescription: Meta.\nmetadata: v1\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 1)
            r = _find(payload, "skills/meta/SKILL.md")
            self.assertTrue(any("metadata must be a mapping" in e for e in r["hard_errors"]))

    def test_skill_name_must_match_directory_and_shape(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(root, "right-dir",
                        "---\nname: other-name\ndescription: D.\n---\n\nBody.\n")
            write_skill(root, "Bad_Dir",
                        "---\nname: Bad_Dir\ndescription: D.\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 1)
            r = _find(payload, "skills/right-dir/SKILL.md")
            self.assertTrue(any("does not match its directory" in e for e in r["hard_errors"]),
                            r["hard_errors"])
            r = _find(payload, "skills/Bad_Dir/SKILL.md")
            self.assertTrue(any("lowercase letters" in e for e in r["hard_errors"]),
                            r["hard_errors"])

    def test_skill_body_over_500_lines_warns(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            body = "\n".join(f"line {i}" for i in range(520))
            write_skill(root, "big", f"---\nname: big\ndescription: Big.\n---\n{body}\n")
            write_skill(root, "small", "---\nname: small\ndescription: Small.\n---\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0, "line count is WARN only")
            r = _find(payload, "skills/big/SKILL.md")
            self.assertTrue(any("520 lines" in w for w in r["warnings"]), r["warnings"])
            self.assertEqual(_find(payload, "skills/small/SKILL.md")["warnings"], [])

    def test_skill_portability_description_cap_only_with_flag(self) -> None:
        """The open-standard 1,024-char description cap WARNs only under
        --check-portability (Claude Code itself allows 1,536)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(root, "wide",
                        f"---\nname: wide\ndescription: {'d' * 1100}\n---\n\nBody.\n")
            _code, payload = run_validator(root)
            self.assertEqual(_find(payload, "skills/wide/SKILL.md")["warnings"], [])
            _code, payload = run_validator(root, "--check-portability")
            warns = _find(payload, "skills/wide/SKILL.md")["warnings"]
            self.assertTrue(any("1100 chars" in w and "1024" in w for w in warns), warns)

    def test_skill_compatibility_cap_always_checked(self) -> None:
        """compatibility ≤500 chars is part of the field's spec -> WARN in
        every run, not just under --check-portability."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(root, "compat",
                        f"---\nname: compat\ndescription: D.\n"
                        f"compatibility: {'c' * 600}\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0)
            warns = _find(payload, "skills/compat/SKILL.md")["warnings"]
            self.assertTrue(any("compatibility is 600 chars" in w for w in warns), warns)

    def test_agent_name_optional_per_spec(self) -> None:
        """Per Anthropic spec, `name` is optional for agents — must not HARD-fail."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "noname",
                        "---\ndescription: An agent with no explicit name.\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0, "missing `name` should NOT HARD-fail")
            r = _find(payload, "engineering/noname.md")
            self.assertEqual(r["hard_errors"], [])

    def test_skill_name_optional_per_spec(self) -> None:
        """Skills have `name` optional (defaults to directory name)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(root, "noname",
                        "---\ndescription: A skill with no explicit name.\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0)
            r = _find(payload, "skills/noname/SKILL.md")
            self.assertEqual(r["hard_errors"], [])

    def test_skill_description_body_fallback(self) -> None:
        """Per spec, skills with no frontmatter description fall back to first
        markdown paragraph. Validator should WARN (recommend explicit) but not HARD."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(root, "fallback",
                        "---\nname: fallback\n---\n\n"
                        "This is the first paragraph of the body. It serves as the "
                        "fallback description per Anthropic's skill spec.\n\n"
                        "Second paragraph follows.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0, "body-fallback description should NOT HARD-fail")
            r = _find(payload, "skills/fallback/SKILL.md")
            self.assertEqual(r["hard_errors"], [])
            self.assertTrue(any("falling back" in w.lower() or "fallback" in w.lower()
                                for w in r["warnings"]),
                            f"expected fallback-mention warn, got {r['warnings']}")

    def test_skill_no_description_no_body_hard_fails(self) -> None:
        """No frontmatter description AND no body content → HARD-fail."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_skill(root, "empty", "---\nname: empty\n---\n\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 1)
            r = _find(payload, "skills/empty/SKILL.md")
            self.assertTrue(any("description" in e.lower() for e in r["hard_errors"]))

    def test_agent_with_disallowed_tools_clean(self) -> None:
        """`disallowed-tools` is spec — should not warn."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "restricted",
                        "---\nname: restricted\ndescription: Restricted agent.\n"
                        "disallowed-tools: Bash, Write\n---\n\nBody.\n")
            _code, payload = run_validator(root)
            r = _find(payload, "engineering/restricted.md")
            self.assertEqual(r["warnings"], [])

    def test_agent_with_when_to_use_hard_fails(self) -> None:
        """when_to_use is a skills-only field. On agents it is silently
        ignored -> HARD (skill-only key check, June-2026 spec)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "alpha",
                        "---\nname: alpha\ndescription: Alpha.\n"
                        "when_to_use: When user asks.\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 1, "skill-only key on agent must HARD-fail")
            r = _find(payload, "engineering/alpha.md")
            self.assertTrue(any("skill-only" in e and "when_to_use" in e
                                for e in r["hard_errors"]),
                            f"expected skill-only HARD, got {r['hard_errors']}")


def _agent_result(fm_lines: str, body: str = "Body.\n") -> tuple[int, dict]:
    """Validate a single agent `engineering/alpha.md` with the given extra
    frontmatter lines; returns (exit code, that file's result entry)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_agent(root, "engineering", "alpha",
                    f"---\nname: alpha\ndescription: Alpha.\n{fm_lines}---\n\n{body}")
        code, payload = run_validator(root)
        return code, _find(payload, "engineering/alpha.md")


class TestAgentValues2026_10(unittest.TestCase):
    """2026-10 spec: three new fields and value-level checks."""

    def test_new_fields_and_valid_values_are_clean(self) -> None:
        code, r = _agent_result(
            "model: opus\neffort: high\npermissionMode: auto\nmemory: project\n"
            "isolation: worktree\nbackground: false\nomitClaudeMd: true\n"
            "maxTurns: 20\nautoCompactWindow: 200000\n"
            "experimental:\n  cacheTtl: 1h\n")
        self.assertEqual(code, 0)
        self.assertEqual(r["hard_errors"], [])
        self.assertEqual(r["warnings"], [])

    def test_model_aliases_clean(self) -> None:
        for model in ("sonnet", "opus", "haiku", "fable", "inherit", "opus[1m]"):
            code, r = _agent_result(f"model: {model}\n")
            self.assertEqual((code, r["hard_errors"], r["warnings"]), (0, [], []), model)

    def test_full_model_id_warns(self) -> None:
        for model in ("claude-fable-5-1", "claude-sonnet-4-5-20250929",
                      "claude-3-5-sonnet-20241022", "claude-opus-5-5[1m]"):
            code, r = _agent_result(f"model: {model}\n")
            self.assertEqual(code, 0, f"{model}: a pinned ID is valid -> WARN, not HARD")
            self.assertTrue(any("pins a version" in w for w in r["warnings"]),
                            f"{model}: {r['warnings']}")

    def test_unknown_model_hard_fails(self) -> None:
        for fm in ("model: gpt-5\n", 'model: "sonnet\\n"\n', "model: claude-opus\n",
                   "model: [opus]\n", "model: claude-123-456\n", "model: claude-opus-5x-5\n"):
            code, r = _agent_result(fm)
            self.assertEqual(code, 1, f"{fm!r} must HARD-fail")
            self.assertTrue(any("model" in e for e in r["hard_errors"]),
                            f"{fm!r}: {r['hard_errors']}")

    def test_non_scalar_enum_values_hard_fail_without_crashing(self) -> None:
        """Unhashable values used to raise TypeError in set membership."""
        for fm in ("effort: [high]\n", "permissionMode: {}\n", "memory: [project]\n",
                   "isolation: {a: b}\n", "experimental:\n  cacheTtl: [1h]\n  1: x\n"):
            code, r = _agent_result(fm)
            self.assertEqual(code, 1, f"{fm!r} must HARD-fail, not crash")

    def test_filename_is_checked_when_name_omitted(self) -> None:
        """Without `name`, the filename stem becomes the agent name."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "-bad", "---\ndescription: D.\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 1)
            r = _find(payload, "engineering/-bad.md")
            self.assertTrue(any("'-'" in e for e in r["hard_errors"]), r["hard_errors"])

    def test_prohibition_wording_without_tool_name_is_quiet(self) -> None:
        """The README template's wording must not trip the unavailable-tool
        warning when an agent copies it."""
        _code, r = _agent_result(
            "", "you cannot ask the user directly (subagents have no question tool)\n")
        self.assertEqual(r["warnings"], [])

    def test_bad_enum_values_hard_fail(self) -> None:
        cases = {
            "effort: hgh\n": "effort",
            "permissionMode: yolo\n": "permissionMode",
            "memory: global\n": "memory",
            "isolation: container\n": "isolation",
            "omitClaudeMd: maybe\n": "omitClaudeMd",
            "background: sometimes\n": "background",
            "maxTurns: 0\n": "maxTurns",
            "autoCompactWindow: 50000\n": "autoCompactWindow",
            "autoCompactWindow: true\n": "autoCompactWindow",
            "experimental:\n  cacheTtl: 2h\n": "cacheTtl",
            "experimental: on\n": "experimental",
        }
        for fm, key in cases.items():
            code, r = _agent_result(fm)
            self.assertEqual(code, 1, f"{fm!r} must HARD-fail")
            self.assertTrue(any(key in e for e in r["hard_errors"]),
                            f"{fm!r}: expected HARD naming {key}, got {r['hard_errors']}")

    def test_risky_values_warn(self) -> None:
        for fm, needle in (("effort: max\n", "effort: max"),
                           ("permissionMode: bypassPermissions\n", "bypassPermissions"),
                           ("experimental:\n  cacheTtl: 5m\n  turbo: true\n", "turbo")):
            code, r = _agent_result(fm)
            self.assertEqual(code, 0, fm)
            self.assertTrue(any(needle in w for w in r["warnings"]), f"{fm!r}: {r['warnings']}")

    def test_name_shape_hard_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "alpha",
                        "---\nname: plug:alpha\ndescription: Alpha.\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 1)
            r = _find(payload, "engineering/alpha.md")
            self.assertTrue(any("':'" in e for e in r["hard_errors"]), r["hard_errors"])

    def test_body_mentioning_unavailable_tool_warns(self) -> None:
        code, r = _agent_result("", "## Phase 1\nUse `AskUserQuestion` iteratively.\n")
        self.assertEqual(code, 0)
        self.assertTrue(any("AskUserQuestion" in w and "never receive" in w
                            for w in r["warnings"]), r["warnings"])

    def test_tools_listing_unavailable_tool_warns(self) -> None:
        code, r = _agent_result("tools: Read, ExitPlanMode\n")
        self.assertEqual(code, 0)
        self.assertTrue(any("tools lists ['ExitPlanMode']" in w for w in r["warnings"]),
                        r["warnings"])

    def test_workflow_heading_does_not_warn_but_tool_mention_does(self) -> None:
        _code, r = _agent_result("", "## Workflow\n1. Read the diff.\n")
        self.assertEqual(r["warnings"], [], "a '## Workflow' heading is not the tool")
        _code, r = _agent_result("", "Run the `Workflow` tool to fan out.\n")
        self.assertTrue(any("'Workflow'" in w for w in r["warnings"]), r["warnings"])


class TestRosterDescriptionBudget(unittest.TestCase):
    def test_over_budget_roster_warns_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(4):  # 4 x 16,000 chars = 64,000 chars ≈ 16,000 tokens
                write_agent(root, "engineering", f"a{i}",
                            f"---\nname: a{i}\ndescription: {'x' * 16000}\n---\n\nBody.\n")
            code, payload = run_validator(root)
            self.assertEqual(code, 0, "budget is a WARN")
            rw = payload["roster_warnings"]
            self.assertTrue(any("all agents" in w and "64,000 chars" in w and "16,000 tokens" in w
                                for w in rw), rw)
            self.assertFalse(any("org-scope" in w for w in rw), "no org agents -> no org warn")

    def test_org_scope_subset_checked_separately(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(4):
                write_agent(root, "engineering", f"a{i}",
                            f"---\nname: a{i}\nscope: org\ndescription: {'x' * 16000}\n"
                            "---\n\nBody.\n")
            _code, payload = run_validator(root)
            self.assertTrue(any("org-scope" in w for w in payload["roster_warnings"]))

    def test_org_scope_matches_case_insensitively_in_mixed_roster(self) -> None:
        """install.sh treats `scope: Org` as org; the budget must too. Mixed
        roster: 4 big org agents plus small project agents."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(4):
                write_agent(root, "engineering", f"o{i}",
                            f"---\nname: o{i}\nscope: Org\ndescription: {'x' * 16000}\n"
                            "---\n\nBody.\n")
            write_agent(root, "engineering", "p", "---\nname: p\nscope: project\n"
                        "description: Small.\n---\n\nBody.\n")
            _code, payload = run_validator(root)
            org = [w for w in payload["roster_warnings"] if "org-scope" in w]
            self.assertEqual(len(org), 1, payload["roster_warnings"])
            self.assertIn("4 descriptions", org[0])

    def test_under_budget_roster_is_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "a", "---\nname: a\ndescription: Small.\n---\n\nB.\n")
            _code, payload = run_validator(root)
            self.assertEqual(payload["roster_warnings"], [])


class TestSummaryShape(unittest.TestCase):
    """Validator should report agents and skills separately."""

    def test_summary_breaks_down_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            write_agent(root, "engineering", "alpha",
                        "---\nname: alpha\ndescription: Alpha.\n---\n\n")
            write_skill(root, "good",
                        "---\nname: good\ndescription: Good.\n---\n\n")
            _code, payload = run_validator(root)
            self.assertIn("agents", payload)
            self.assertIn("skills", payload)
            self.assertEqual(payload["agents"]["clean"], 1)
            self.assertEqual(payload["skills"]["clean"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
