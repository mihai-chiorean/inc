#!/usr/bin/env python3
"""Tests for label.py — run directly: `python3 evals/routing/test_label.py`.

Repo convention: no pytest; print results and sys.exit(1) on failure.
Uses a temp dataset; never mutates the real dataset.yaml. Uses the real
manifest for agent-id validation.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import label as L  # noqa: E402

AGENTS = L.load_manifest_agents()  # real manifest

# A minimally valid agent id present in the real manifest, used across tests.
GOOD_AGENT = "ai-engineer"
ADV_AGENT = "security-auditor"
assert GOOD_AGENT in AGENTS, "test fixture assumes ai-engineer exists in manifest"
assert ADV_AGENT in AGENTS, "test fixture assumes security-auditor exists in manifest"


def expect(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def write_dataset(d: Path, entries: list[dict]) -> Path:
    p = d / "dataset.yaml"
    L.dump_dataset(entries, p)
    return p


def good_dataset() -> list[dict]:
    return [
        {"id": "route-001", "prompt": "p1", "expected": GOOD_AGENT,
         "category": "engineering", "difficulty": "easy", "rationale": "r"},
        {"id": "route-002", "prompt": "p2", "expected": "NONE",
         "category": "meta", "difficulty": "hard", "rationale": "r"},
        {"id": "route-003", "prompt": "p3", "expected": "infra-reviewer",
         "category": "engineering", "difficulty": "medium", "rationale": "r",
         "adversarial_against": ADV_AGENT},
        {"id": "route-004", "prompt": "p4"},  # unlabeled
    ]


# --------------------------------------------------------------------------
def test_validate_passes_on_good(d: Path) -> None:
    errs = L.validate_entries(good_dataset(), AGENTS)
    expect(errs == [], f"expected no errors, got {errs}")


def test_validate_unknown_agent(d: Path) -> None:
    ents = good_dataset()
    ents[0]["expected"] = "not-a-real-agent"
    errs = L.validate_entries(ents, AGENTS)
    expect(any("not a manifest agent" in e for e in errs), f"expected unknown-agent error, got {errs}")


def test_validate_bad_category(d: Path) -> None:
    ents = good_dataset()
    ents[0]["category"] = "frobnicate"
    errs = L.validate_entries(ents, AGENTS)
    expect(any("category" in e for e in errs), f"expected category error, got {errs}")


def test_validate_bad_difficulty(d: Path) -> None:
    ents = good_dataset()
    ents[0]["difficulty"] = "trivial"
    errs = L.validate_entries(ents, AGENTS)
    expect(any("difficulty" in e for e in errs), f"expected difficulty error, got {errs}")


def test_validate_duplicate_id(d: Path) -> None:
    ents = good_dataset()
    ents[1]["id"] = "route-001"
    errs = L.validate_entries(ents, AGENTS)
    expect(any("duplicate id" in e for e in errs), f"expected duplicate-id error, got {errs}")


def test_validate_adversarial_equals_expected(d: Path) -> None:
    ents = good_dataset()
    ents[2]["adversarial_against"] = ents[2]["expected"]  # == infra-reviewer
    errs = L.validate_entries(ents, AGENTS)
    expect(any("must differ from expected" in e for e in errs),
           f"expected adversarial==expected error, got {errs}")


def test_add_appends_next_id(d: Path) -> None:
    p = write_dataset(d, good_dataset())
    nid = L.add_entry(p, "a brand new prompt")
    expect(nid == "route-005", f"expected route-005, got {nid}")
    ents = L.load_dataset(p)
    expect(len(ents) == 5, f"expected 5 entries, got {len(ents)}")
    expect(ents[-1]["prompt"] == "a brand new prompt", "new prompt not appended")
    expect(not L.is_labeled(ents[-1]), "newly added entry should be unlabeled")


def test_label_writes_back(d: Path) -> None:
    p = write_dataset(d, good_dataset())
    fields = {"expected": "grpc-contracts", "category": "engineering",
              "difficulty": "medium", "rationale": "gRPC contract review",
              "adversarial_against": "swift-backend"}
    labeled = L.label_entry(p, fields, AGENTS)
    expect(labeled["id"] == "route-004", f"expected to label route-004, got {labeled['id']}")
    ents = L.load_dataset(p)
    row = next(e for e in ents if e["id"] == "route-004")
    expect(L.is_labeled(row), "route-004 should now be labeled")
    expect(row["expected"] == "grpc-contracts", "expected not written")
    expect(row["adversarial_against"] == "swift-backend", "adversarial_against not written")
    # other entries preserved
    expect(len(ents) == 4, f"entry count changed: {len(ents)}")
    expect(ents[0]["expected"] == GOOD_AGENT, "existing labeled row mutated")


def test_label_omits_blank_adversarial(d: Path) -> None:
    p = write_dataset(d, good_dataset())
    fields = {"expected": "NONE", "category": "meta", "difficulty": "easy",
              "rationale": "no agent fits", "adversarial_against": ""}
    labeled = L.label_entry(p, fields, AGENTS)
    expect("adversarial_against" not in labeled, "blank adversarial_against should be omitted")


def test_label_rejects_bad(d: Path) -> None:
    p = write_dataset(d, good_dataset())
    fields = {"expected": "totally-fake", "category": "engineering",
              "difficulty": "easy", "rationale": "x", "adversarial_against": ""}
    try:
        L.label_entry(p, fields, AGENTS)
    except ValueError:
        # confirm dataset untouched (route-004 still unlabeled)
        ents = L.load_dataset(p)
        row = next(e for e in ents if e["id"] == "route-004")
        expect(not L.is_labeled(row), "rejected label must not be written")
        return
    raise AssertionError("expected label_entry to raise on unknown agent")


def test_validate_missing_rationale(d: Path) -> None:
    ents = good_dataset()
    ents[0].pop("rationale")
    errs = L.validate_entries(ents, AGENTS)
    expect(any("rationale" in e for e in errs), f"expected missing-rationale error, got {errs}")


def test_validate_category_derived_from_manifest(d: Path) -> None:
    # every real manifest category is accepted; "meta" too; junk is not.
    cats = L.valid_categories(AGENTS)
    expect("engineering" in cats and "meta" in cats, f"derived cats missing expected: {sorted(cats)}")
    expect("frobnicate" not in cats, "junk category should not be derived")


def test_empty_expected_is_unlabeled(d: Path) -> None:
    # a blank `expected` is treated as unlabeled so the tool can pick it up,
    # rather than being a stuck "labeled-but-invalid" row.
    expect(not L.is_labeled({"id": "route-009", "prompt": "p", "expected": ""}),
           "blank expected should count as unlabeled")
    expect(not L.is_labeled({"id": "route-009", "prompt": "p", "expected": None}),
           "null expected should count as unlabeled")
    expect(L.is_labeled({"id": "route-009", "prompt": "p", "expected": "NONE"}),
           "expected=NONE is a real label")


def test_stats_counts(d: Path) -> None:
    s = L.compute_stats(good_dataset())
    expect(s["total"] == 4, f"total {s['total']}")
    expect(s["labeled"] == 3, f"labeled {s['labeled']}")
    expect(s["unlabeled"] == 1, f"unlabeled {s['unlabeled']}")
    expect(s["adversarial"] == 1, f"adversarial {s['adversarial']}")
    expect(s["per_category"].get("engineering") == 2, f"engineering count {s['per_category']}")
    expect(s["per_category"].get("meta") == 1, f"meta count {s['per_category']}")


def main() -> int:
    tests = [
        test_validate_passes_on_good,
        test_validate_unknown_agent,
        test_validate_bad_category,
        test_validate_bad_difficulty,
        test_validate_duplicate_id,
        test_validate_adversarial_equals_expected,
        test_add_appends_next_id,
        test_label_writes_back,
        test_label_omits_blank_adversarial,
        test_label_rejects_bad,
        test_validate_missing_rationale,
        test_validate_category_derived_from_manifest,
        test_empty_expected_is_unlabeled,
        test_stats_counts,
    ]
    for fn in tests:
        with tempfile.TemporaryDirectory() as d:
            try:
                fn(Path(d))
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
