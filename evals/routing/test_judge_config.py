#!/usr/bin/env python3
"""Tests for judge_config.py — run directly: `python3 evals/routing/test_judge_config.py`.

Repo convention: no pytest; print results and sys.exit(1) on failure. Validates
the committed judge_config.yaml and the loader/validator contract. Uses a temp
copy for mutation tests; never mutates the real config.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import judge_config as J  # noqa: E402

REAL = J.load_config()  # the committed judge_config.yaml


def expect(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_real_config_valid() -> None:
    errs = J.validate_config(REAL)
    expect(errs == [], f"committed judge_config.yaml should be valid, got {errs}")


def test_real_config_is_pinned_and_frozen() -> None:
    expect(REAL["determinism"]["temperature"] == 0, "temperature must be pinned to 0")
    expect(isinstance(REAL["determinism"]["seed"], int), "seed must be a fixed int")
    expect(bool(REAL["model"]["name"]), "model.name must be pinned")
    expect(bool(REAL["judge_prompt"]["version"]), "judge_prompt must be version-stamped")
    expect(REAL["model"]["provider"] == "codex-cli", "judge is Codex (cross-family); see docs/judge.md")


def test_validate_rejects_nonzero_temperature() -> None:
    cfg = copy.deepcopy(REAL)
    cfg["determinism"]["temperature"] = 0.7
    errs = J.validate_config(cfg)
    expect(any("temperature" in e for e in errs), f"expected temperature error, got {errs}")


def test_validate_rejects_missing_seed() -> None:
    cfg = copy.deepcopy(REAL)
    cfg["determinism"]["seed"] = None
    errs = J.validate_config(cfg)
    expect(any("seed" in e for e in errs), f"expected seed error, got {errs}")


def test_validate_rejects_bad_output_schema() -> None:
    cfg = copy.deepcopy(REAL)
    cfg["output_schema"]["required"] = ["selected_agent"]  # missing confidence/runner_up
    errs = J.validate_config(cfg)
    expect(any("output_schema.required" in e for e in errs), f"expected schema error, got {errs}")


def test_validate_rejects_template_without_placeholders() -> None:
    cfg = copy.deepcopy(REAL)
    cfg["judge_prompt"]["template"] = "no placeholders here"
    errs = J.validate_config(cfg)
    expect(sum("placeholder" in e for e in errs) == 2, f"expected 2 placeholder errors, got {errs}")


def test_render_prompt_fills_and_preserves_json_braces() -> None:
    rendered = J.render_prompt(REAL, "PROMPT_X", "ROSTER_Y")
    expect("PROMPT_X" in rendered and "ROSTER_Y" in rendered, "placeholders not substituted")
    expect("{prompt}" not in rendered and "{roster}" not in rendered, "placeholders left behind")
    # the literal JSON-object instruction must survive (not eaten by formatting)
    expect('"selected_agent"' in rendered, "literal JSON schema instruction was lost")


def test_version_stamp_shape() -> None:
    stamp = J.version_stamp(REAL, resolved_model="gpt-5.5", resolved_snapshot="gpt-5.5-2026-xx-xx",
                            date="2026-06-05", applied_overrides={"model": "gpt-5.5"})
    for k in ("config_version", "requested_model", "provider", "judge_prompt_version",
              "declared_determinism", "applied_overrides", "resolved_model",
              "resolved_snapshot", "date"):
        expect(k in stamp, f"version_stamp missing {k}")
    expect(stamp["resolved_model"] == "gpt-5.5", "resolved_model not threaded through")
    # declared determinism is what the frozen config pins...
    expect(stamp["declared_determinism"]["temperature"] == 0, "must carry the pinned temperature")
    # ...applied_overrides is what the call actually enforced (no temp/seed there).
    expect("temperature" not in stamp["applied_overrides"], "temp/seed must not be claimed as applied")


def main() -> int:
    tests = [
        test_real_config_valid,
        test_real_config_is_pinned_and_frozen,
        test_validate_rejects_nonzero_temperature,
        test_validate_rejects_missing_seed,
        test_validate_rejects_bad_output_schema,
        test_validate_rejects_template_without_placeholders,
        test_render_prompt_fills_and_preserves_json_braces,
        test_version_stamp_shape,
    ]
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL: {fn.__name__}: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {fn.__name__}: {exc!r}")
            return 1
        print(f"ok: {fn.__name__}")
    print(f"\n{len(tests)}/{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
