# Agent-routing eval dataset (MIT-294)

Ground-truth dataset + incremental labeling tool for the **routing eval**:
given a natural-language task a user might type, does Claude route it to the
correct specialist agent?

This dataset feeds the eval runner (**MIT-297**), touchfile selection
(**MIT-439**), and the extended EvalResult schema (**MIT-438**).

## Files

| File | Purpose |
| --- | --- |
| `dataset.yaml` | Labeled (and unlabeled) routing examples — the ground truth. |
| `label.py` | Incremental labeling + validation CLI. |
| `test_label.py` | Tests; run directly (no pytest). |

## Schema (`dataset.yaml`)

A YAML list of entries. Each entry:

| Field | Req? | Description |
| --- | --- | --- |
| `id` | required | Unique, zero-padded `route-NNN`. |
| `prompt` | required | The natural-language task. |
| `expected` | optional | Agent stable-id that should handle it, or `NONE`. **Missing/null => the row is unlabeled.** |
| `category` | labeled | One of the 9 manifest categories, or `meta`. |
| `difficulty` | labeled | `easy` \| `medium` \| `hard`. |
| `rationale` | labeled | Why `expected` is correct. |
| `adversarial_against` | optional | A trap: the agent the prompt superficially looks like but is **not** the answer. Must differ from `expected`. |

The 9 manifest categories: `bonus`, `design`, `engineering`, `marketing`,
`product`, `project-management`, `studio-operations`, `testing`, `writing`.
The dataset additionally allows `meta` (e.g. `NONE` / out-of-scope prompts).

### Validation against `agent.manifest.yaml`

`label.py` resolves `agent.manifest.yaml` by walking up from the script
directory to the repo root. The valid agent stable-ids are the keys under
`agents:`. Both `expected` (unless `NONE`) and `adversarial_against` must be
real manifest ids — this is what catches typos. `adversarial_against` must
also differ from `expected` (otherwise it isn't a trap).

## Tool (`label.py`)

Resolves `dataset.yaml` as a sibling of the script; override with
`--dataset PATH`.

```bash
# Show the next unlabeled prompt (non-interactive)
python3 evals/routing/label.py next

# Label the next unlabeled entry. Reads 5 lines from STDIN in order:
#   expected, category, difficulty, rationale, adversarial_against
# (blank last line = omit adversarial_against). Scriptable for testing.
printf 'grpc-contracts\nengineering\nmedium\ngRPC contract review\nswift-backend\n' \
  | python3 evals/routing/label.py label

# Append a new unlabeled entry (auto-assigns next route-NNN)
python3 evals/routing/label.py add "How do we A/B test the new pricing page?"

# Counts: total / labeled / unlabeled, per-category coverage, adversarial count
python3 evals/routing/label.py stats

# Validate every entry; exit 0 if all valid, exit 1 with per-entry errors
python3 evals/routing/label.py validate
```

## Tests

```bash
python3 evals/routing/test_label.py   # prints results; exit 1 on failure
```

Tests use a temp dataset and never mutate the real `dataset.yaml`; they use
the real manifest for agent-id validation.
