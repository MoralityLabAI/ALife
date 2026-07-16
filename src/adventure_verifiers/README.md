# Adventure Verifiers

`adventure_verifiers` is a deterministic verification library for agents or
players acting as adventurers in ALife environments. It verifies submitted
routes, actions, resources, goals, and atomic claims against canonical replay
events. It does not generate narration and it does not call a model or API.

## Contract

Verification consumes three JSON objects:

1. A task declares the environment, movement/resource rules, goals, required
   hard verifiers, and diagnostics.
2. A trace contains the adventurer's ordered locations, actions, receipt IDs,
   observed/outcome event IDs, atomic claims, and final resource ledger.
3. An environment envelope contains canonical events, source and normalized
   hashes, and the exact replay receipt.

The suite returns a vector of verifier results. `accepted` is true only when
the task is valid and every declared hard verifier passes. There is no weighted
score and diagnostics cannot be promoted into acceptance gates.

## Built-in hard verifiers

| Verifier | Rejects |
| --- | --- |
| `trace_schema` | malformed or cross-episode task/trace identities |
| `event_stream_integrity` | changed hashes, malformed events, non-finite JSON, future causes, or causal cycles |
| `action_receipts` | fabricated, disallowed, wrong-tick, wrong-position, or wrong-action receipts |
| `causal_grounding` | future observations, unknown evidence, and outcomes unrelated to their action |
| `route_continuity` | out-of-bounds positions and movement beyond the declared toroidal step cap |
| `resource_ledger` | altered costs, overspending, and incorrect final balances |
| `goal_completion` | event, visit, or claim-count goals that cannot be re-derived |
| `claim_grounding` | atomic facts, counts, or visits not derivable from cited evidence |

`exploration_coverage` and `response_diversity` are diagnostic-only. Their
outputs may help curriculum construction but never establish success.

## Python API

```python
from adventure_verifiers import verify_adventure

suite = verify_adventure(task, trace, environment)
if suite["accepted"]:
    keep_for_training(trace)
```

Adapters normalize Pixie Sanctuary and Folded Cavern episode rows, while
`adapt_chronicle_events` handles Chronicle streams. `build_pixie_adventure`
constructs a valid reference task and trace from a Pixie episode.

Downstream games can inject a new `VerifierSpec` through `extra_verifiers`.
Custom IDs cannot override built-ins:

```python
from adventure_verifiers import VerifierSpec, make_result, verify_adventure

def has_guild_badge(task, trace, environment):
    passed = trace["adventure_id"].startswith("guild-")
    return make_result(
        "guild_badge",
        passed=passed,
        acceptance_eligible=True,
        failures=[] if passed else ["missing guild badge"],
    )

extra = {
    "guild_badge": VerifierSpec(
        "guild_badge", True, "Require a guild-issued trace ID.", has_guild_badge
    )
}
suite = verify_adventure(task, trace, environment, extra_verifiers=extra)
```

## CLI and fixture campaign

```powershell
python src\adventure_verifiers_cli.py --list
python src\adventure_verifiers_cli.py task.json trace.json environment.json
python src\run_adventure_verifier_campaign.py --manifest experiments\adventure_verifiers_v1\manifest.json --output results\adventure_verifiers_v1
python src\verify_adventure_verifier_artifacts.py results\adventure_verifiers_v1 --portable
```

The frozen campaign crosses four replayed source seeds with one valid control
and nine one-at-a-time tamper classes. Passing this suite validates the declared
fixtures and implementation wiring, not universal resistance to exploits or
the competence of an adventurer policy.
