#!/usr/bin/env python3
"""Incremental labeling tool for the agent-routing eval dataset (MIT-294).

Subcommands:
  next      print the next unlabeled prompt (non-interactive)
  label     pop the next unlabeled entry, print it + the agent roster, then
            read label fields from STDIN (one per line, in order:
            expected, category, difficulty, rationale, adversarial_against;
            a blank line for adversarial_against omits it). Validate + write.
  add       append a new unlabeled entry with the next route-NNN id
  stats     print total/labeled/unlabeled counts + per-category + adversarial
  validate  validate every entry against the manifest; exit 0/1

Functions are importable for testing; the CLI is guarded by __main__.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

# Valid dataset categories are derived from the manifest at validation time
# (every agent's `category`) plus "meta" for NONE / non-agent rows — see
# valid_categories() — so adding or renaming a manifest category does not
# require editing this file.
META_CATEGORY = "meta"
DIFFICULTIES = ("easy", "medium", "hard")
NONE_SENTINEL = "NONE"

# Prepended to dataset.yaml on every write so the schema contract survives the
# lossy yaml.safe_dump round-trip (PyYAML drops comments).
SCHEMA_HEADER = """\
# Agent-routing eval dataset (MIT-294)
#
# Labeled ground truth for the routing eval: given a natural-language task a
# user might type, which specialist agent SHOULD handle it? Feeds the eval
# runner (MIT-297), touchfile selection (MIT-439), and the extended EvalResult
# schema (MIT-438). Full docs: evals/routing/README.md.
#
# Schema — each list entry is a mapping:
#   id                  REQUIRED. Unique, zero-padded: route-NNN.
#   prompt              REQUIRED. The natural-language task.
#   expected            agent stable-id (key under `agents:` in
#                       agent.manifest.yaml) or the literal NONE. Absent /
#                       null / blank => the entry is UNLABELED.
#   category            one of the manifest agent categories OR "meta".
#   difficulty          easy | medium | hard.
#   rationale           REQUIRED on labeled rows. Why `expected` is right.
#   adversarial_against OPTIONAL. The agent this prompt superficially looks
#                       like but is NOT. Must differ from `expected`.
#
# Maintained by label.py — prefer the tool over hand-editing.
"""


def valid_categories(agents: dict[str, str]) -> set[str]:
    """Categories accepted in the dataset: every manifest agent category plus
    the 'meta' bucket for NONE / non-agent rows."""
    return {c for c in agents.values() if c} | {META_CATEGORY}

# Canonical key order preserved on write.
KEY_ORDER = (
    "id",
    "prompt",
    "expected",
    "category",
    "difficulty",
    "rationale",
    "adversarial_against",
)


# --------------------------------------------------------------------------
# Resolution helpers
# --------------------------------------------------------------------------
def find_manifest(start: Path | None = None) -> Path:
    """Walk up from `start` (default: this script's dir) to find
    agent.manifest.yaml at the repo root."""
    here = (start or Path(__file__).resolve().parent).resolve()
    for d in (here, *here.parents):
        candidate = d / "agent.manifest.yaml"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("agent.manifest.yaml not found walking up from " + str(here))


def default_dataset_path() -> Path:
    """dataset.yaml as a sibling of this script."""
    return Path(__file__).resolve().parent / "dataset.yaml"


def load_manifest_agents(manifest_path: Path | None = None) -> dict[str, str]:
    """Return {agent_id: category} from the manifest."""
    path = manifest_path or find_manifest()
    data = yaml.safe_load(path.read_text()) or {}
    agents = data.get("agents", {}) or {}
    return {aid: meta.get("category") for aid, meta in agents.items()}


def load_dataset(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text()) or []
    if not isinstance(data, list):
        raise ValueError("dataset must be a YAML list")
    return data


def _ordered(entry: dict) -> dict:
    """Reorder keys by KEY_ORDER, dropping null/empty optional values."""
    out = {}
    for k in KEY_ORDER:
        if k in entry and entry[k] is not None:
            out[k] = entry[k]
    # preserve any unexpected extra keys at the end (defensive)
    for k, v in entry.items():
        if k not in out and v is not None:
            out[k] = v
    return out


def dump_dataset(entries: list[dict], path: Path) -> None:
    ordered = [_ordered(e) for e in entries]
    body = yaml.safe_dump(
        ordered,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )
    path.write_text(SCHEMA_HEADER + "\n" + body)


def is_labeled(entry: dict) -> bool:
    # Unlabeled if `expected` is absent, null, or blank — a blank `expected`
    # is malformed input the labeling tool should still be able to pick up.
    return bool(str(entry.get("expected") or "").strip())


def next_id(entries: list[dict]) -> str:
    nums = []
    for e in entries:
        eid = str(e.get("id", ""))
        if eid.startswith("route-"):
            try:
                nums.append(int(eid.split("route-")[1]))
            except ValueError:
                pass
    nxt = (max(nums) + 1) if nums else 1
    return f"route-{nxt:03d}"


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def validate_entries(entries: list[dict], agents: dict[str, str]) -> list[str]:
    """Return a list of human-readable error strings; empty == all valid."""
    import re

    errors: list[str] = []
    seen_ids: dict[str, int] = {}
    id_re = re.compile(r"^route-\d{3,}$")
    categories = valid_categories(agents)

    for i, e in enumerate(entries):
        tag = e.get("id", f"<index {i}>")
        eid = e.get("id")
        if not eid or not isinstance(eid, str) or not id_re.match(eid):
            errors.append(f"{tag}: id must match route-NNN (zero-padded)")
        else:
            if eid in seen_ids:
                errors.append(f"{eid}: duplicate id (also at index {seen_ids[eid]})")
            seen_ids[eid] = i

        if not e.get("prompt"):
            errors.append(f"{tag}: missing prompt")

        if not is_labeled(e):
            # unlabeled entries are valid as long as id/prompt are ok
            continue

        expected = e.get("expected")
        if expected != NONE_SENTINEL and expected not in agents:
            errors.append(f"{tag}: expected '{expected}' is not a manifest agent id (or NONE)")

        category = e.get("category")
        if category not in categories:
            errors.append(
                f"{tag}: category '{category}' invalid "
                f"(must be a manifest category or '{META_CATEGORY}')"
            )

        difficulty = e.get("difficulty")
        if difficulty not in DIFFICULTIES:
            errors.append(f"{tag}: difficulty '{difficulty}' invalid (must be one of {DIFFICULTIES})")

        if not str(e.get("rationale") or "").strip():
            errors.append(f"{tag}: missing rationale (required on labeled rows)")

        adv = e.get("adversarial_against")
        if adv is not None:
            if adv not in agents:
                errors.append(f"{tag}: adversarial_against '{adv}' is not a manifest agent id")
            if adv == expected:
                errors.append(f"{tag}: adversarial_against must differ from expected ('{adv}')")

    return errors


# --------------------------------------------------------------------------
# Mutating operations
# --------------------------------------------------------------------------
def add_entry(path: Path, prompt: str) -> str:
    entries = load_dataset(path)
    nid = next_id(entries)
    entries.append({"id": nid, "prompt": prompt})
    dump_dataset(entries, path)
    return nid


def label_entry(path: Path, fields: dict, agents: dict[str, str]) -> dict:
    """Apply `fields` to the next unlabeled entry, validate, write back.
    Returns the labeled entry. Raises ValueError on validation failure."""
    entries = load_dataset(path)
    target = None
    for e in entries:
        if not is_labeled(e):
            target = e
            break
    if target is None:
        raise ValueError("no unlabeled entries to label")

    candidate = dict(target)
    candidate["expected"] = fields["expected"]
    candidate["category"] = fields["category"]
    candidate["difficulty"] = fields["difficulty"]
    candidate["rationale"] = fields.get("rationale", "")
    adv = fields.get("adversarial_against")
    if adv:
        candidate["adversarial_against"] = adv
    else:
        candidate.pop("adversarial_against", None)

    errors = validate_entries([candidate], agents)
    if errors:
        raise ValueError("label rejected:\n  " + "\n  ".join(errors))

    target.clear()
    target.update(candidate)
    dump_dataset(entries, path)
    return target


def compute_stats(entries: list[dict]) -> dict:
    labeled = [e for e in entries if is_labeled(e)]
    per_cat: dict[str, int] = {}
    adversarial = 0
    for e in labeled:
        per_cat[e.get("category", "?")] = per_cat.get(e.get("category", "?"), 0) + 1
        if e.get("adversarial_against"):
            adversarial += 1
    return {
        "total": len(entries),
        "labeled": len(labeled),
        "unlabeled": len(entries) - len(labeled),
        "per_category": per_cat,
        "adversarial": adversarial,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _agent_roster_text(agents: dict[str, str]) -> str:
    by_cat: dict[str, list[str]] = {}
    for aid, cat in agents.items():
        by_cat.setdefault(cat or "?", []).append(aid)
    lines = ["Available agent IDs (grouped by category):"]
    for cat in sorted(by_cat):
        lines.append(f"  [{cat}]")
        for aid in sorted(by_cat[cat]):
            lines.append(f"    {aid}")
    lines.append(f"  [meta]  (use category 'meta'; expected can be {NONE_SENTINEL})")
    return "\n".join(lines)


def cmd_next(args) -> int:
    entries = load_dataset(args.dataset)
    for e in entries:
        if not is_labeled(e):
            print(f"{e['id']}: {e['prompt']}")
            return 0
    print("all labeled")
    return 0


def cmd_label(args) -> int:
    entries = load_dataset(args.dataset)
    target = next((e for e in entries if not is_labeled(e)), None)
    if target is None:
        print("all labeled")
        return 0
    agents = load_manifest_agents()
    print(f"Labeling {target['id']}:")
    print(f"  PROMPT: {target['prompt']}")
    print()
    print(_agent_roster_text(agents))
    print()
    print("Enter (one per line): expected, category, difficulty, rationale, adversarial_against")
    print("(blank line for adversarial_against = omit)", file=sys.stderr)

    raw = sys.stdin.read().splitlines()
    # take the first 5 lines; pad with blanks
    raw = (raw + ["", "", "", "", ""])[:5]
    fields = {
        "expected": raw[0].strip(),
        "category": raw[1].strip(),
        "difficulty": raw[2].strip(),
        "rationale": raw[3].strip(),
        "adversarial_against": raw[4].strip(),
    }
    try:
        labeled = label_entry(args.dataset, fields, agents)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"\nLabeled {labeled['id']} -> expected={labeled['expected']} "
          f"category={labeled['category']} difficulty={labeled['difficulty']}"
          + (f" adversarial_against={labeled['adversarial_against']}"
             if labeled.get('adversarial_against') else ""))
    return 0


def cmd_add(args) -> int:
    nid = add_entry(args.dataset, args.prompt)
    print(f"added {nid} (unlabeled)")
    return 0


def cmd_stats(args) -> int:
    entries = load_dataset(args.dataset)
    s = compute_stats(entries)
    print(f"total:     {s['total']}")
    print(f"labeled:   {s['labeled']}")
    print(f"unlabeled: {s['unlabeled']}")
    print(f"adversarial rows: {s['adversarial']}")
    print("per-category coverage (labeled rows):")
    if s["per_category"]:
        for cat in sorted(s["per_category"]):
            print(f"  {cat}: {s['per_category'][cat]}")
    else:
        print("  (none)")
    return 0


def cmd_validate(args) -> int:
    entries = load_dataset(args.dataset)
    agents = load_manifest_agents()
    errors = validate_entries(entries, agents)
    if errors:
        print(f"INVALID: {len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"OK: {len(entries)} entries valid")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Routing eval dataset labeling tool")
    p.add_argument("--dataset", type=Path, default=default_dataset_path(),
                   help="path to dataset.yaml (default: sibling of this script)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("next", help="print next unlabeled prompt").set_defaults(func=cmd_next)
    sub.add_parser("label", help="label next unlabeled entry from stdin").set_defaults(func=cmd_label)
    a = sub.add_parser("add", help="append a new unlabeled entry")
    a.add_argument("prompt", help="the natural-language prompt text")
    a.set_defaults(func=cmd_add)
    sub.add_parser("stats", help="print counts").set_defaults(func=cmd_stats)
    sub.add_parser("validate", help="validate every entry").set_defaults(func=cmd_validate)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
