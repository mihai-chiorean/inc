# Routing eval: why Codex is the judge

The routing eval (MIT-294–302) measures whether a natural-language task gets
routed to the correct specialist agent. The **judge** is the model that, given a
prompt and the agent roster, predicts which agent should handle it. Its
prediction is compared against the hand-labeled `expected` in
`evals/routing/dataset.yaml`.

The judge is configured in `evals/routing/judge_config.yaml` (loaded/validated by
`judge_config.py`). This doc explains the two decisions that config encodes:
**why Codex, not Claude** and **why it's pinned + frozen**.

## Why Codex (a non-Claude model), not Claude

The roster lives in this repo: the agent descriptions, the `agent.manifest.yaml`
routing text, and the whole taxonomy were authored *for and largely by* Claude.
The system whose routing we're grading is also Claude.

If we used Claude to judge Claude's routing, the judge and the system-under-test
share a model family — and therefore share blind spots. A Claude judge is liable
to **rationalize the same wrong pick** a Claude router makes: if both read
"review this Terraform" as a security task, a Claude judge happily confirms
`security-auditor` and the eval reports a false pass. Correlated grader/subject
error inflates the score precisely where the roster is weakest.

Using a **different model family** (Codex / `gpt-5.5`) as the judge breaks that
correlation. Codex has no special allegiance to how *we* described the agents; it
reasons about the prompt and the roster text independently. Disagreements between
Codex's pick and our `expected` label surface real routing ambiguity instead of
being smoothed over by a same-family judge. This is standard eval hygiene:
**don't grade a model with itself.**

(Routing accuracy itself stays deterministic — `selected_agent == expected` is an
exact id match. The judge is an *independent router*, not a soft rubric grader.
Numeric/rubric judging is reserved for genuinely qualitative cases like
conflict-detection rationale.)

## Why pinned + frozen

`judge_config.yaml` pins, and `judge_config.py validate` enforces:

- **`model`** — `gpt-5.5` via the codex CLI (`provider_version` records the CLI
  version at pinning time).
- **`determinism.temperature: 0`, `determinism.seed`** — a fixed seed for
  near-deterministic runs.
- **`judge_prompt.version`** — the prompt template is frozen and version-stamped.
- **`output_schema`** — `{selected_agent, confidence 0..1, runner_up}`.

A judge that drifts is worse than no judge: you can't tell a real routing
regression from the judge quietly getting nicer/stricter. Pinning the model,
prompt, and decoding params makes a score change *attributable* to the roster,
not the grader.

**Changing the model, prompt, or schema breaks comparability with prior runs.**
When you must change one: bump `config_version` and record it in the trend file
(MIT-299) so the discontinuity is visible. Calibration + drift probes (MIT-300)
exist to catch unflagged judge drift.

## The dated snapshot is recorded per run, not in the config

The codex CLI does not statically expose the exact dated model snapshot
(e.g. `gpt-5.5-YYYY-MM-DD`), so it cannot be hardcoded. Instead the runner
(MIT-297) calls `version_stamp(...)` with the model + snapshot + date Codex
actually returned and writes that block into every run's output JSON. So each
result is self-describing: you can always tell which exact judge produced it,
even though the config only pins the *request*.

## Determinism caveat

High-reasoning models may not honor `temperature`/`seed` exactly, so runs are
**near-deterministic**, not bit-identical. That's the other reason every run
records its resolved model + snapshot + date: when two runs disagree, you can
check whether the judge snapshot moved underneath you before blaming the roster.

## How it's consumed

- `judge_config.py validate` — CI/local gate that the config still satisfies the
  frozen-config contract.
- `judge_config.py show` — prints the version stamp.
- The runner (MIT-297) calls `render_prompt(cfg, prompt, roster)` per dataset row,
  invokes Codex, parses against `output_schema`, compares `selected_agent` to
  `expected`, and records `version_stamp(...)` into the run output (MIT-438).
