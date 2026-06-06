#!/usr/bin/env python3
"""Tests for runner.py — run directly: `python3 evals/routing/test_runner.py`.

Repo convention: no pytest; print results and sys.exit(1) on failure. Uses
MockJudge — no live Codex calls, CI-safe.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import runner as R       # noqa: E402
import judge_config as J  # noqa: E402
import label as L         # noqa: E402

CFG = J.load_config()
AGENTS = L.load_manifest_agents()
SUMM = R.load_agent_summaries()


def expect(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def ds() -> list[dict]:
    return [
        {"id": "route-001", "prompt": "p1", "expected": "ai-engineer",
         "category": "engineering", "difficulty": "easy", "rationale": "r"},
        {"id": "route-002", "prompt": "p2", "expected": "NONE",
         "category": "meta", "difficulty": "easy", "rationale": "r"},
        {"id": "route-003", "prompt": "p3", "expected": "infra-reviewer",
         "category": "engineering", "difficulty": "easy", "rationale": "r"},
        {"id": "route-004", "prompt": "p4"},  # unlabeled — runner must skip
    ]


def test_parse_judge_output_from_codex_transcript() -> None:
    # mimics the real codex exec transcript shape
    out = ('OpenAI Codex v0.124.0\nmodel: gpt-5.5\n--------\nuser\n...\n'
           'codex\n{"selected_agent":"ai-engineer","confidence":0.8,"runner_up":null}\n'
           'tokens used\n123\n{"selected_agent":"ai-engineer","confidence":0.8,"runner_up":null}\n')
    obj = R.parse_judge_output(out)
    expect(obj["selected_agent"] == "ai-engineer", f"bad parse: {obj}")
    expect(obj["runner_up"] is None, "runner_up should be null/None")


def test_parse_raises_when_absent() -> None:
    try:
        R.parse_judge_output("no json here at all")
    except ValueError:
        return
    raise AssertionError("expected ValueError on missing JSON")


def test_run_eval_scores_correctly() -> None:
    picks = {"route-001": "ai-engineer",   # correct
             "route-002": "NONE",          # correct (NONE)
             "route-003": "swift-backend"} # wrong (expected infra-reviewer)
    judge = R.MockJudge(picks)
    res = R.run_eval(ds(), CFG, judge, AGENTS, SUMM)
    s = res["summary"]
    expect(s["n"] == 3, f"should score 3 labeled rows (skip unlabeled), got {s['n']}")
    expect(s["correct"] == 2, f"expected 2 correct, got {s['correct']}")
    expect(abs(s["accuracy"] - 2/3) < 1e-3, f"accuracy {s['accuracy']}")  # runner rounds to 4dp


def test_run_eval_flags_invalid_agent_pick() -> None:
    judge = R.MockJudge({"route-001": "not-a-real-agent", "route-002": "NONE",
                         "route-003": "infra-reviewer"})
    res = R.run_eval(ds(), CFG, judge, AGENTS, SUMM)
    expect(res["summary"]["invalid_agent_picks"] == 1, "should flag the bogus agent id")
    r1 = next(r for r in res["results"] if r["id"] == "route-001")
    expect(r1["valid_agent"] is False and r1["correct"] is False, "bogus pick is invalid + wrong")


def test_norm_none_case_insensitive() -> None:
    expect(R._norm("none") == "NONE" and R._norm(" NONE ") == "NONE", "NONE should normalize")
    expect(R._norm("ai-engineer") == "ai-engineer", "real ids unchanged")


def test_version_stamp_present() -> None:
    res = R.run_eval(ds(), CFG, R.MockJudge(), AGENTS, SUMM, date="2026-06-05")
    expect(res["judge"]["date"] == "2026-06-05", "date threaded into stamp")
    expect(res["judge"]["requested_model"] == "gpt-5.5", "stamp carries pinned model")


def test_limit() -> None:
    res = R.run_eval(ds(), CFG, R.MockJudge(), AGENTS, SUMM, limit=2)
    expect(res["summary"]["n"] == 2, f"limit=2 should score 2 rows, got {res['summary']['n']}")


def test_limit_zero_means_zero() -> None:
    # --limit 0 must run zero rows, not all of them (no accidental paid run).
    res = R.run_eval(ds(), CFG, R.MockJudge(), AGENTS, SUMM, limit=0)
    expect(res["summary"]["n"] == 0, f"limit=0 should score 0 rows, got {res['summary']['n']}")


def test_negative_limit_rejected() -> None:
    try:
        R.run_eval(ds(), CFG, R.MockJudge(), AGENTS, SUMM, limit=-1)
    except ValueError:
        return
    raise AssertionError("negative limit must raise, not slice rows[:-1]")


def test_parse_ignores_echoed_prompt_template() -> None:
    # The judge prompt echoes a template JSON with placeholder (non-numeric)
    # confidence. If only the echo is present, validate_verdict must reject it.
    echoed = '{"selected_agent": "<agent-id or NONE>", "confidence": <number 0..1>, "runner_up": "<agent-id or null>"}'
    # the echoed template is not even valid JSON (placeholders), so parse fails:
    try:
        R.parse_judge_output(echoed)
    except ValueError:
        pass
    else:
        raise AssertionError("echoed template placeholders should not parse as a verdict")


def test_malformed_verdict_becomes_row_error() -> None:
    expect(R.validate_verdict({"selected_agent": "ai-engineer", "confidence": 0.9,
                               "runner_up": None}) is None, "well-formed verdict should pass")
    expect(R.validate_verdict({"selected_agent": "ai-engineer", "runner_up": None}) is not None,
           "missing confidence should fail")
    expect(R.validate_verdict({"selected_agent": "ai-engineer", "confidence": 1.5,
                               "runner_up": None}) is not None, "out-of-range confidence should fail")
    expect(R.validate_verdict({"selected_agent": "ai-engineer", "confidence": 0.5}) is not None,
           "missing runner_up should fail")

    class BadJudge:
        resolved_model = "bad"
        def judge(self, prompt, roster, row_id):
            return {"selected_agent": "ai-engineer"}  # missing confidence + runner_up
    res = R.run_eval(ds(), CFG, BadJudge(), AGENTS, SUMM)
    expect(res["summary"]["errors"] == res["summary"]["n"], "all malformed verdicts must be row errors")
    expect(res["summary"]["correct"] == 0, "malformed verdicts must not be scored correct")


def main() -> int:
    tests = [
        test_parse_judge_output_from_codex_transcript,
        test_parse_raises_when_absent,
        test_run_eval_scores_correctly,
        test_run_eval_flags_invalid_agent_pick,
        test_norm_none_case_insensitive,
        test_version_stamp_present,
        test_limit,
        test_limit_zero_means_zero,
        test_negative_limit_rejected,
        test_parse_ignores_echoed_prompt_template,
        test_malformed_verdict_becomes_row_error,
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
