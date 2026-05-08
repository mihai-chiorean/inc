#!/usr/bin/env python3
"""Accuracy harness for /staff suggest strategies.

Runs `staff suggest --json --strategy <s>` against a labeled set of real
projects, computes precision/recall/F1 against the hand-labeled expected
roster, and reports per-strategy aggregates.

Goal: decide whether the LLM should be fed full agent descriptions or
pre-computed summaries. We don't have data; this builds it.

Usage:
    python3 skills/staff/tests/eval_suggest_accuracy.py --labels skills/staff/tests/labels.yaml

Output:
    Per-project breakdown showing each strategy's precision/recall/F1, plus
    aggregate scores across the label set.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SUGGEST = REPO_ROOT / "skills/staff/scripts/suggest.py"


@dataclass
class Score:
    project: str
    strategy: str
    precision: float
    recall: float
    f1: float
    suggested_ids: list[str]
    expected_ids: list[str]
    extra: list[str]   # suggested but not expected (false positives)
    missed: list[str]  # expected but not suggested (false negatives)


def load_labels(path: Path) -> list[dict]:
    """Labels file shape:

    projects:
      - name: lab-control
        path: /home/mihai/workspace/lab-control
        expected: [go-engineer, security-auditor, embedded-device, devops-automator]
        notes: optional free-form
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out = data.get("projects") or []
    if not out:
        raise SystemExit(f"no 'projects' in {path}")
    return out


def run_suggest(project_root: Path, hr_repo: Path, strategy: str) -> set[str]:
    cmd = [
        sys.executable, str(SUGGEST),
        "--project-root", str(project_root),
        "--hr-repo", str(hr_repo),
        "--strategy", strategy,
        "--json",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, check=False,
        # Pass through STAFF_LLM* env so the same provider is used as a
        # human run from the shell.
        env={**os.environ},
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"suggest failed for {project_root} (strategy={strategy}): "
            f"exit={result.returncode}, stderr={result.stderr.strip()[:300]}"
        )
    payload = json.loads(result.stdout)
    return {p["id"] for p in payload.get("suggested", [])}


def score(project: str, strategy: str, suggested: set[str], expected: set[str]) -> Score:
    if not suggested and not expected:
        # Vacuous match
        return Score(project, strategy, 1.0, 1.0, 1.0, [], [], [], [])
    tp = suggested & expected
    fp = suggested - expected
    fn = expected - suggested
    precision = len(tp) / len(suggested) if suggested else 0.0
    recall = len(tp) / len(expected) if expected else 0.0
    if precision + recall > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0
    return Score(
        project, strategy,
        precision, recall, f1,
        sorted(suggested), sorted(expected),
        sorted(fp), sorted(fn),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Score /staff suggest strategies against labels")
    parser.add_argument("--labels", default="skills/staff/tests/labels.yaml",
                        help="path to YAML labels file")
    parser.add_argument("--hr-repo", default=str(REPO_ROOT),
                        help="HR repo path (default: this repo)")
    parser.add_argument("--strategies", nargs="+", default=["summary", "full"],
                        choices=("summary", "full"),
                        help="strategies to evaluate")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON instead of text")
    args = parser.parse_args()

    labels_path = Path(args.labels)
    if not labels_path.is_absolute():
        labels_path = REPO_ROOT / labels_path
    if not labels_path.is_file():
        print(f"labels not found: {labels_path}", file=sys.stderr)
        return 2
    projects = load_labels(labels_path)
    hr_repo = Path(args.hr_repo).resolve()

    all_scores: list[Score] = []
    for proj in projects:
        name = proj["name"]
        path = Path(proj["path"]).expanduser()
        if not path.is_dir():
            print(f"skip {name}: project path {path} not found", file=sys.stderr)
            continue
        expected = set(proj["expected"])
        for strategy in args.strategies:
            try:
                suggested = run_suggest(path, hr_repo, strategy)
            except Exception as exc:
                print(f"FAIL {name} ({strategy}): {exc}", file=sys.stderr)
                continue
            s = score(name, strategy, suggested, expected)
            all_scores.append(s)

    if args.json:
        print(json.dumps([{
            "project": s.project, "strategy": s.strategy,
            "precision": s.precision, "recall": s.recall, "f1": s.f1,
            "suggested": s.suggested_ids, "expected": s.expected_ids,
            "extra": s.extra, "missed": s.missed,
        } for s in all_scores], indent=2))
        return 0

    # Per-project breakdown
    by_project: dict[str, list[Score]] = {}
    for s in all_scores:
        by_project.setdefault(s.project, []).append(s)

    for project, scores in by_project.items():
        print(f"=== {project} ===")
        for s in scores:
            print(f"  {s.strategy:<10}  P={s.precision:.2f}  R={s.recall:.2f}  F1={s.f1:.2f}")
            if s.extra:
                print(f"      extra (FP):  {', '.join(s.extra)}")
            if s.missed:
                print(f"      missed (FN): {', '.join(s.missed)}")
        print()

    # Aggregates
    print("=== aggregate ===")
    by_strategy: dict[str, list[Score]] = {}
    for s in all_scores:
        by_strategy.setdefault(s.strategy, []).append(s)
    for strategy, scores in by_strategy.items():
        if not scores:
            continue
        p = statistics.mean(s.precision for s in scores)
        r = statistics.mean(s.recall for s in scores)
        f = statistics.mean(s.f1 for s in scores)
        print(f"  {strategy:<10}  P={p:.2f}  R={r:.2f}  F1={f:.2f}  (n={len(scores)})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
