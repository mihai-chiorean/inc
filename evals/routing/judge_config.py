#!/usr/bin/env python3
"""Loader + validator for the frozen routing-judge config (MIT-296).

The judge config (judge_config.yaml) pins the Codex model, a frozen prompt
template, the output schema, and determinism settings so routing-eval runs are
reproducible and comparable. Codex (non-Claude family) is used to avoid
correlated bias with the Claude-authored roster — see docs/judge.md.

Subcommands:
  validate  validate judge_config.yaml against the frozen-config contract
  show      print the resolved config + a version stamp

Functions are importable for testing; the CLI is guarded by __main__.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

PROMPT_PLACEHOLDERS = ("{prompt}", "{roster}")
REQUIRED_OUTPUT_FIELDS = {"selected_agent", "confidence", "runner_up"}


def default_config_path() -> Path:
    """judge_config.yaml as a sibling of this script."""
    return Path(__file__).resolve().parent / "judge_config.yaml"


def load_config(path: Path | None = None) -> dict:
    p = path or default_config_path()
    data = yaml.safe_load(p.read_text()) or {}
    if not isinstance(data, dict):
        raise ValueError("judge config must be a YAML mapping")
    return data


def validate_config(cfg: dict) -> list[str]:
    """Return a list of human-readable error strings; empty == valid."""
    errors: list[str] = []

    if not cfg.get("config_version"):
        errors.append("missing config_version")

    model = cfg.get("model") or {}
    if not model.get("name"):
        errors.append("model.name is required (the pinned judge model)")
    if not model.get("provider"):
        errors.append("model.provider is required")

    det = cfg.get("determinism") or {}
    if det.get("temperature") != 0:
        errors.append(f"determinism.temperature must be 0 (got {det.get('temperature')!r})")
    if not isinstance(det.get("seed"), int):
        errors.append("determinism.seed must be a fixed integer")

    jp = cfg.get("judge_prompt") or {}
    if not jp.get("version"):
        errors.append("judge_prompt.version is required (frozen, version-stamped)")
    template = jp.get("template") or ""
    for ph in PROMPT_PLACEHOLDERS:
        if ph not in template:
            errors.append(f"judge_prompt.template must contain the {ph} placeholder")

    schema = cfg.get("output_schema") or {}
    required = set(schema.get("required") or [])
    if required != REQUIRED_OUTPUT_FIELDS:
        errors.append(
            f"output_schema.required must be {sorted(REQUIRED_OUTPUT_FIELDS)} "
            f"(got {sorted(required)})"
        )
    props = schema.get("properties") or {}
    conf = props.get("confidence") or {}
    if conf.get("minimum") != 0 or conf.get("maximum") != 1:
        errors.append("output_schema.properties.confidence must be bounded 0..1")

    return errors


def render_prompt(cfg: dict, prompt: str, roster: str) -> str:
    """Fill the frozen template. Uses str.replace (not str.format) so the
    literal JSON braces in the template survive."""
    template = (cfg.get("judge_prompt") or {}).get("template") or ""
    return template.replace("{prompt}", prompt).replace("{roster}", roster)


def version_stamp(cfg: dict, *, resolved_model: str | None = None,
                  resolved_snapshot: str | None = None, date: str | None = None,
                  applied_overrides: dict | None = None) -> dict:
    """The provenance block the runner (MIT-297) records into each run's output.

    `resolved_model` / `resolved_snapshot` / `date` are filled in at call time
    from what Codex actually returned (the static config cannot know the dated
    snapshot).

    `declared_determinism` is what the frozen config *pins*; `applied_overrides`
    is what the runner could actually enforce on the call. They differ on
    purpose: the gpt-5.5 reasoning judge via codex-cli does not honor
    temperature/seed, so those are declared-but-not-enforced — see docs/judge.md.
    """
    model = cfg.get("model") or {}
    det = cfg.get("determinism") or {}
    return {
        "config_version": cfg.get("config_version"),
        "requested_model": model.get("name"),
        "provider": model.get("provider"),
        "provider_version": model.get("provider_version"),
        "reasoning_effort": model.get("reasoning_effort"),
        "judge_prompt_version": (cfg.get("judge_prompt") or {}).get("version"),
        "declared_determinism": {"temperature": det.get("temperature"), "seed": det.get("seed")},
        "applied_overrides": applied_overrides or {},
        "determinism_note": "temperature/seed are declared in judge_config but NOT "
                            "enforced by the gpt-5.5 reasoning judge via codex-cli; "
                            "runs are near-deterministic — see docs/judge.md",
        # filled per-run by the runner:
        "resolved_model": resolved_model,
        "resolved_snapshot": resolved_snapshot,
        "date": date,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def cmd_validate(args) -> int:
    cfg = load_config(args.config)
    errors = validate_config(cfg)
    if errors:
        print(f"INVALID: {len(errors)} error(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"OK: judge config {cfg.get('config_version')} valid "
          f"(model {cfg.get('model', {}).get('name')}, "
          f"prompt {cfg.get('judge_prompt', {}).get('version')})")
    return 0


def cmd_show(args) -> int:
    cfg = load_config(args.config)
    print(json.dumps(version_stamp(cfg), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Routing-eval judge config loader/validator")
    p.add_argument("--config", type=Path, default=default_config_path(),
                   help="path to judge_config.yaml (default: sibling of this script)")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate the judge config").set_defaults(func=cmd_validate)
    sub.add_parser("show", help="print the config version stamp").set_defaults(func=cmd_show)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
