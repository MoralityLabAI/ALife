# ALife Emergence and Adaptive Pressure Progress

This file maps the completion criteria in [GOAL.md](GOAL.md) to current authoritative evidence. All v1 completion gates are now satisfied; stronger causal and transfer claims remain future work.

## Milestone status

| Milestone | Status | Evidence | Remaining gate |
| --- | --- | --- | --- |
| 1. Baseline registry | Complete for v1 | `registries/generator_coverage_baseline.json`; `registries/ontology_registry.json` | Refresh hashes when downstream generators change. |
| 2. Geometry control | Complete for v1 | `src/geometry_averaging_experiment.py`; frozen manifest; 144-episode D-drive artifact set; passing verifier | Boundary refinement is the registered next experiment, not required to preserve the v1 result. |
| 3. Graph-state laboratory | Complete for v1/v2 | `src/graph_state_lab.py`; 162-episode v1; 192-episode frozen-predictor confirmation; both artifact verifiers pass | Extend to edge-specific transport only if a holonomy claim is registered. |
| 4. Known-truth curriculum | Complete for v1 | `src/discovery_curriculum.py`; 63-task hidden-oracle suite; passing verifier | Replace a reference policy with a real local investigator before making a learning claim. |
| 5. Set-valued curriculum | Complete for v1 | Nine set-identified interval tasks plus nine point-unidentifiable tasks; registration calibration and abstention receipts | Add competing learned coarse-grainings in v2. |
| 6. Mathematical discovery | Complete for first model-only ontology gain | `normalized_laplacian_spectral_gap_for_graph_ca_recovery` in `registries/ontology_registry.json`; v1 holdout + frozen v2 confirmation | Causal necessity/mediation remains a separate future claim. |
| 7. Consumer transfer | Complete for v1 | `confinement_transfer_v1`; 24 paired search seeds; compute/action/information matched; passing verifier | Test non-monotone fiber dynamics to distinguish pressure generation from simple front-loading. |

## Geometry v1 evidence receipt

- Contract: `experiments/geometry_averaging_v1/manifest.json` validates with zero errors and zero warnings.
- Structural tests: `python -m unittest discover -s tests -v` passes six tests.
- Experimental units: 144 independently initialized worlds; ticks and cells are not treated as replicates.
- Splits: 32 discovery, 48 confirmatory, 64 untouched holdout.
- Determinism: exact state and trajectory replay passed.
- Storage: `results/geometry_averaging_v1` resolves to `D:\ALife\project_results\geometry_averaging_v1`.
- Resources: approximately 22 seconds wall time, 44 MB maximum process RSS, and 3.2 MB retained artifacts.
- Artifact verification: `python src/verify_geometry_averaging_artifacts.py results/geometry_averaging_v1` passes with no errors or warnings.

## Geometry v1 knowledge boundary

- H1 received qualified support: Moore-neighborhood mean-field error declined with dimension, but high-dimensional zero error was frequently extinction.
- H2 was not supported: the fixed-degree arm retained a stronger negative dimension/error slope than the Moore arm.
- H3 was supported within the sampled model family: all confirmatory/holdout literal-B3S23 cells at dimensions four and five were extinction-only.
- Twenty of 27 frozen numeric closure passes were rejected as nontrivial evidence by the active-regime hazard overlay.
- No universal critical dimension, open-endedness result, biological analogy, or accepted ontology gain is claimed.

## Graph-state v1/v2 evidence receipt

- V1: 162 episodes across degree-6 ring, rewired-regular, and random-regular graphs; spectral feature improved untouched holdout RMSE by 6.11% against a frozen 5% gate.
- V2: 192 fresh episodes; no refitting; degrees 4/8, state dimensions 4/12, couplings 0.2/0.4, new graph sizes/seeds, and a circulant-skip topology.
- Frozen confirmation: baseline RMSE `0.653248`, spectral RMSE `0.572901`, relative improvement `12.30%`.
- Both v1 and v2 fail the stronger 80%-direction topology claim; predictive utility is accepted, causal uniqueness is not.
- `python src/verify_graph_state_artifacts.py results/graph_state_v1` and the corresponding v2 command both pass with no errors or warnings.

## Curriculum v1 evidence receipt

- Contract: `experiments/discovery_curriculum_v1/manifest.json` validates with zero errors and zero warnings.
- Experimental units: 63 independently seeded tasks across seven families; 14 discovery, 28 confirmation, and 21 holdout.
- The calibrated reference investigator scored `0.92795` on holdout versus `0.35812` for the best control, a margin of `0.56983` over the registered `0.20` gate.
- Set-identified interval evidence score was `1.0`; nine point-unidentifiable tasks received correct registered abstentions.
- Always-abstain was not dominant and incurred an `85.71%` avoidable-abstention rate.
- This validates incentives and episode wiring, not learned-investigator ability.

## Consumer-transfer v1 evidence receipt

- Both search methods received 128 simulator evaluations, 24 scheduled actions, horizon 80, the same training evaluators, and time-only information for every paired seed.
- On 12 untouched holdout search seeds and four unseen evaluator variants, random search achieved `0.59661` mean kernel-escape rate and evolutionary search achieved `0.70729`.
- Mean paired improvement was `+0.11068`, clearing the frozen `+0.10` point-estimate gate; the deterministic paired bootstrap interval `[+0.08307, +0.13620]` includes values below that practical threshold.
- All 12 holdout pairs favored evolution. All action-budget, proxy-pass, closure-defect, and simulator-evaluation gates passed.
- The result is a stronger benign toy stress-test distribution, not evidence of real-world evasion or superiority over arbitrary optimizers.

## Next executable work

Run the registered falsification tests: graph pairs that separate spectral gap from clustering/path length, a real local investigator in place of the calibrated reference policy, and non-monotone Confinement Width fiber dynamics where naive action front-loading can fail.
