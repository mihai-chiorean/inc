#!/usr/bin/env python3
"""Routing eval runner (MIT-297).

For each labeled prompt in dataset.yaml, ask the judge (Codex, configured in
judge_config.yaml) which agent should handle it, then compare the judge's
`selected_agent` to the dataset's `expected` (deterministic id match). Emits a
basic result JSON: per-row correctness + overall accuracy + the judge version
stamp.

Scope: this is the harness + BASIC metrics (accuracy, per-row correct/miss).
Rich metrics (precision/recall/F1, FP/FN lists, persistence + auto-compare) are
MIT-438; gate/periodic CI is MIT-440.

Judges are pluggable:
  - CodexJudge  — real `codex exec` calls (default for `run`)
  - MockJudge   — deterministic, injected by tests (no paid calls)

Subcommands:
  run   run the eval and write a result JSON (default: real Codex judge)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import label as L            # noqa: E402  dataset + manifest helpers
import judge_config as J     # noqa: E402  frozen judge config

# Flat JSON object containing selected_agent (our schema has no nested braces).
_JSON_RE = re.compile(r'\{[^{}]*"selected_agent"[^{}]*\}')
_MODEL_RE = re.compile(r'^\s*model:\s*(\S+)', re.MULTILINE)


def build_roster(agents: dict[str, str], summaries: dict[str, str]) -> str:
    """One line per agent: `<id>: <one-line scope>`."""
    lines = []
    for aid in sorted(agents):
        lines.append(f"{aid}: {summaries.get(aid, '').strip()}")
    return "\n".join(lines)


def load_agent_summaries(manifest_path: Path | None = None) -> dict[str, str]:
    """{agent_id: short scope line} from the manifest (summary, else description head)."""
    path = manifest_path or L.find_manifest()
    import yaml
    data = yaml.safe_load(path.read_text()) or {}
    out = {}
    for aid, meta in (data.get("agents") or {}).items():
        s = (meta.get("description_summary") or meta.get("description") or "")
        s = s.replace("\n", " ").strip()
        out[aid] = (s[:160] + "…") if len(s) > 161 else s
    return out


def parse_judge_output(text: str) -> dict:
    """Extract the trailing {selected_agent,confidence,runner_up} object from
    codex output (which wraps the answer in a transcript)."""
    candidates = _JSON_RE.findall(text)
    for c in reversed(candidates):
        try:
            obj = json.loads(c)
        except json.JSONDecodeError:
            continue
        if "selected_agent" in obj:
            return obj
    raise ValueError("no JSON object with selected_agent found in judge output")


# --------------------------------------------------------------------------
# Judges
# --------------------------------------------------------------------------
class MockJudge:
    """Deterministic judge for tests. `picks` maps row id -> selected_agent;
    unmapped rows return NONE. Records no cost."""

    def __init__(self, picks: dict[str, str] | None = None):
        self.picks = picks or {}
        self.resolved_model = "mock"

    def judge(self, prompt: str, roster: str, row_id: str) -> dict:
        sel = self.picks.get(row_id, "NONE")
        return {"selected_agent": sel, "confidence": 1.0, "runner_up": None}


class CodexJudge:
    """Real judge: `codex exec` pinned to the configured model + reasoning."""

    def __init__(self, cfg: dict, timeout: int = 120):
        model = cfg.get("model") or {}
        self.model = model.get("name", "gpt-5.5")
        self.reasoning = model.get("reasoning_effort", "high")
        self.timeout = timeout
        self.resolved_model = None
        # What we can actually enforce on the call. Note: temperature/seed from
        # the frozen config are NOT here — codex-cli's reasoning judge ignores
        # them (recorded honestly in the version stamp).
        self.applied = {"model": self.model, "model_reasoning_effort": self.reasoning}

    def judge(self, prompt: str, roster: str, row_id: str) -> dict:
        import os
        import tempfile
        rendered = J.render_prompt(_CFG, prompt, roster)
        fd, last_path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        try:
            proc = subprocess.run(
                ["codex", "exec",
                 "-c", f"model={self.model}",
                 "-c", f"model_reasoning_effort={self.reasoning}",
                 # -o writes ONLY the final assistant message, so the echoed
                 # prompt (which contains the template's literal JSON) can't be
                 # mis-parsed as the verdict.
                 "-o", last_path,
                 rendered],
                capture_output=True, text=True, stdin=subprocess.DEVNULL,
                timeout=self.timeout,
            )
            last_msg = Path(last_path).read_text()
        finally:
            try:
                os.unlink(last_path)
            except OSError:
                pass
        m = _MODEL_RE.search(proc.stdout + "\n" + proc.stderr)
        if m:
            self.resolved_model = m.group(1)
        # Parse the final message; fall back to full stdout only if -o was empty.
        return parse_judge_output(last_msg.strip() or (proc.stdout + proc.stderr))


# module-global config handle for CodexJudge.render (set in run_eval)
_CFG: dict = {}


# --------------------------------------------------------------------------
# Eval
# --------------------------------------------------------------------------
def _norm(agent: str | None) -> str:
    a = (agent or "").strip()
    return "NONE" if a.upper() == "NONE" else a


def validate_verdict(verdict: dict) -> str | None:
    """Check a judge response against the frozen output_schema. Returns an error
    string, or None if valid. Malformed verdicts become row errors (not silently
    scored)."""
    if not isinstance(verdict, dict):
        return "verdict is not an object"
    sel = verdict.get("selected_agent")
    if not isinstance(sel, str) or not sel.strip():
        return "selected_agent missing or not a string"
    conf = verdict.get("confidence")
    if not isinstance(conf, (int, float)) or isinstance(conf, bool) or not (0 <= conf <= 1):
        return f"confidence must be a number in [0,1] (got {conf!r})"
    ru = verdict.get("runner_up", "__missing__")
    if ru == "__missing__":
        return "runner_up field is required (may be null)"
    if ru is not None and not isinstance(ru, str):
        return f"runner_up must be a string or null (got {ru!r})"
    return None


def run_eval(dataset: list[dict], cfg: dict, judge, agents: dict[str, str],
             summaries: dict[str, str], *, limit: int | None = None,
             date: str | None = None) -> dict:
    global _CFG
    _CFG = cfg
    roster = build_roster(agents, summaries)
    rows = [e for e in dataset if L.is_labeled(e)]
    if limit is not None:  # explicit: --limit 0 means zero rows, not "all"
        if limit < 0:
            raise ValueError(f"--limit must be >= 0 (got {limit})")
        rows = rows[:limit]

    results = []
    for e in rows:
        rec = {"id": e["id"], "prompt": e["prompt"], "expected": e["expected"],
               "category": e.get("category"), "adversarial_against": e.get("adversarial_against")}
        try:
            verdict = judge.judge(e["prompt"], roster, e["id"])
            verr = validate_verdict(verdict)
            if verr:
                raise ValueError(f"malformed judge verdict: {verr}")
            sel = _norm(verdict.get("selected_agent"))
            rec["selected_agent"] = sel
            rec["confidence"] = verdict.get("confidence")
            rec["runner_up"] = verdict.get("runner_up")
            rec["valid_agent"] = (sel == "NONE") or (sel in agents)
            rec["correct"] = (sel == _norm(e["expected"]))
        except Exception as exc:  # noqa: BLE001 — a judge/parse failure is a row error, not a crash
            rec["error"] = repr(exc)
            rec["correct"] = False
            rec["valid_agent"] = False
        results.append(rec)

    scored = [r for r in results if "error" not in r]
    correct = sum(1 for r in results if r.get("correct"))
    n = len(results)
    return {
        "judge": J.version_stamp(
            cfg,
            resolved_model=getattr(judge, "resolved_model", None),
            resolved_snapshot=None,  # codex-cli does not expose a dated snapshot
            date=date or _dt.date.today().isoformat(),
            applied_overrides=getattr(judge, "applied", None),
        ),
        "summary": {
            "n": n,
            "correct": correct,
            "accuracy": round(correct / n, 4) if n else 0.0,
            "errors": n - len(scored),
            # invalid picks only among rows that actually produced a pick
            "invalid_agent_picks": sum(1 for r in results
                                       if "error" not in r and not r.get("valid_agent")),
        },
        "results": results,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def cmd_run(args) -> int:
    if args.limit is not None and args.limit < 0:
        print(f"--limit must be >= 0 (got {args.limit})", file=sys.stderr)
        return 2
    cfg = J.load_config()
    errs = J.validate_config(cfg)
    if errs:
        print("judge config invalid; fix before running:", *errs, sep="\n  ", file=sys.stderr)
        return 2
    dataset = L.load_dataset(L.default_dataset_path())
    agents = L.load_manifest_agents()
    summaries = load_agent_summaries()
    judge = CodexJudge(cfg, timeout=args.timeout)
    labeled = sum(1 for e in dataset if L.is_labeled(e))
    n_to_run = labeled if args.limit is None else min(args.limit, labeled)
    print(f"running {n_to_run} rows through {cfg['model']['name']} "
          f"(this makes live calls)...", file=sys.stderr)
    result = run_eval(dataset, cfg, judge, agents, summaries, limit=args.limit)

    out = args.out
    if out is None:
        outdir = Path(__file__).resolve().parent / "results"
        outdir.mkdir(exist_ok=True)
        out = outdir / f"run-{result['judge']['date']}.json"
    Path(out).write_text(json.dumps(result, indent=2) + "\n")
    s = result["summary"]
    print(f"accuracy: {s['correct']}/{s['n']} = {s['accuracy']:.1%}  "
          f"(errors {s['errors']}, invalid picks {s['invalid_agent_picks']})")
    print(f"wrote {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Routing eval runner")
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run", help="run the eval (real Codex judge)")
    r.add_argument("--limit", type=int, default=None, help="only run the first N labeled rows")
    r.add_argument("--timeout", type=int, default=120, help="per-call timeout (s)")
    r.add_argument("--out", type=Path, default=None, help="result JSON path")
    r.set_defaults(func=cmd_run)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
