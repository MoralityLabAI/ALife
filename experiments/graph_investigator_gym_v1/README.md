# Graph-State Investigator Cultivation v1

This campaign cultivates an experiment-selection policy rather than an organism.
Each independently seeded task contains twelve sealed graph-pair outcomes selected
from a ninety-candidate connected regular-graph pool. Policies see structural
descriptor deltas and may reveal only six outcomes before predicting the other six.

The scientific target is deliberately narrower than causal discovery. The finite
full-bank posterior grades how well a policy identifies intervention-indexed
spectral-gap, clustering, path-length, joint, or null explanations. It is not
ground truth and does not turn a correlated graph statistic into a mechanism.

## Conditions

- `sheaf_eig`: expected model-information gain with a discovery-frozen context
  sheaf prior.
- `local_eig`: the same search with an unsmoothed patch prior.
- `global_eig`: the same search with one pooled prior.
- `spectral_proxy`: always selects the largest available spectral-gap contrast.
- four deterministic random orders, averaged per task as the primary baseline.

The four context patches cross graph degree 4/8 with coupling 0.15/0.35. Their
stalks share the same five hypothesis coordinates and use identity restrictions.
The normalized sheaf Laplacian smooths discovery log-priors; holonomy is therefore
trivial by construction and is not an empirical transport result.

## Constitutional scope

`constitution.json` is audit-only. It records model evidence represented as
environment-sound, under-calibrated point claims, inadequate matched exposure,
and explicit bottom states. Audit outputs cannot alter selection or scoring.
Graph validity, budgets, sealed outcomes, hashes, and replay remain fail-closed
operational invariants.

## Validate and run

```powershell
python C:\Users\patri\.codex\skills\alife-knowledge-experiments\scripts\validate_manifest.py experiments\graph_investigator_gym_v1\manifest.json --check-paths
python src\graph_investigator_gym.py --manifest experiments\graph_investigator_gym_v1\manifest.json --output results\graph_investigator_gym_v1_smoke --smoke
python src\graph_investigator_gym.py --manifest experiments\graph_investigator_gym_v1\manifest.json --output results\graph_investigator_gym_v1 --evidence-dir experiments\graph_investigator_gym_v1\evidence
python src\verify_graph_investigator_artifacts.py results\graph_investigator_gym_v1 --portable --replay-samples 4 --evidence-dir experiments\graph_investigator_gym_v1\evidence
```

The full sequential CPU campaign is capped at 112 task banks, 2,688 graph arms,
160 nodes per arm, 100 ticks, 1,200 wall seconds, 2,048 MB process RSS, and
250 MB retained artifacts. Query budgets are matched; FLOPs are not.

## Claim boundary

A successful result would show that this registered deterministic active-search
policy allocates a small graph-experiment budget better within this simulator.
It would not establish cognition, biological life, general scientific reasoning,
causal uniqueness, or the value of enforcing the shadow constitution.
