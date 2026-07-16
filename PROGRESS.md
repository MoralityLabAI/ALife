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
| 8. Alternative-physics atlas | Complete for descriptive v1 | `alt_physics_atlas_v1`; 360 deterministic episodes across three families and dimensions 2-4; short paper; passing portable verifier | Separate Gray-Scott reaction mechanism from equal-diffusion pattern candidates before making a stronger emergence claim. |
| Pixie interaction sanctuary | Complete prototype v1 | `pixie_sanctuary_v1`; 162 paired episodes covering three critters by six actions; passing portable verifier | Move legible interactions into bounded terrain with a moving Pixie before judging playability. |
| Pixie folded cavern | Complete higher-dimensional prototype v1 | `pixie_folded_cavern_v1`; 288 paired episodes through dimension 11; passing portable verifier | Add axis-selective notes and tomography, then dosage-match surface and fiber actions. |

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

Run the registered falsification tests: graph pairs that separate spectral gap from clustering/path length, a real local investigator in place of the calibrated reference policy, non-monotone Confinement Width fiber dynamics where naive action front-loading can fail, and a Gray-Scott diffusion-ratio/autocatalysis factorial that can distinguish the equal-diffusion control from reaction-supported organization.

For Pixie encounters, take one response per substrate into a bounded-cavern
factorial: Bitlichen touch for colony scars, Prism Wyrm song for recoverable
waves, and Mitosis Moss feed for local concentration scars. Vary Pixie motion,
action timing, and walls before adding a single mixed-critter resource coupling.

For higher-dimensional encounters, use fixed-degree folded routes as the
default. Deep probes reliably resurfaced Bitlichen and Mitosis Moss, while
Prism Wyrm often remained hidden at dimensions 8 and 11. The next implementation
should let notes select a hidden axis and provide a second projection, not
increase global action strength.

## Alternative-physics atlas v1 evidence receipt

- Contract: `experiments/alt_physics_atlas_v1/manifest.json` validates with zero errors and zero warnings; discovery calibration and invalidated technical runs are recorded explicitly.
- Experimental units: 360 independently initialized worlds; 72 discovery, 180 confirmatory, and 108 larger/longer holdout episodes.
- Substrates: binary totalistic CA, Gray-Scott reaction-diffusion, and cyclic excitable CA in dimensions 2-4 at fixed degree 12.
- Fresh-set candidate occupancy: binary `16/96`, Gray-Scott `64/96`, cyclic `7/96`; the candidate label is an operational multi-axis pattern detector, not an organism or open-endedness claim.
- Dimension occupancy: 2-D `47/96`, 3-D `24/96`, 4-D `16/96`; family/regime mutual information was `0.86558` bits in confirmation and `0.83885` in holdout.
- Goodhart audit: 48 static and 48 global-churn fresh episodes retained tempting individual diagnostics, while `0/96` passed the frozen conjunction.
- Falsification: equal-diffusion Gray-Scott passed every fresh condition, so literature-prior enrichment is not supported as a mechanism claim.
- Resources: `66.39` seconds wall time, `55.20` MB maximum process RSS, and about `12.1` MB retained artifacts on the D-drive junction.
- Verification: every summary and trajectory hash re-derived; three family-spanning portable exact replays passed with no errors or warnings.
- Paper: `papers/alt_physics_alife_distribution.md`.

## Pixie sanctuary v1 evidence receipt

- Contract: `experiments/pixie_sanctuary_v1/manifest.json`; taxonomy: `mechanics_taxonomy.json`.
- Experimental units: 162 independently seeded paired treated/untreated worlds; 36 discovery, 72 confirmatory, and 54 larger/longer holdout episodes.
- Matrix: three substrate-native critters by six universal Pixie affordances, with all 54 split-aware cells retained.
- Exposure: all 162 episodes executed every scheduled action receipt; all 135 non-observe episodes changed exact substrate state; all 27 observe controls remained identical to their comparators.
- Fresh preferred interactions were visible and bounded in every episode. Bitlichen touch produced morphology changes or waves; Mitosis Moss feed produced localized scars; Prism Wyrm song produced transient recovery or propagation.
- The four frozen model-only hypotheses were supported within sample. This is control/design illumination, not evidence of emotion, bonding, learning, life, or player enjoyment.
- Resources: `49.47` seconds wall time and about `5.6` MB retained artifacts on the D-drive results junction.
- Verification: schemas, taxonomy coverage, raw summaries, trajectory/event hashes, cause references, and three substrate-spanning portable replays passed with no errors or warnings.

## Pixie folded cavern v1 evidence receipt

- Contract: `experiments/pixie_folded_cavern_v1/manifest.json`; world-mechanics taxonomy: `world_mechanics_taxonomy.json`.
- Experimental units: 288 independently seeded paired treated/untreated worlds; 72 discovery, 144 confirmatory, and 72 holdout episodes.
- Geometry: an 8x8 visible torus times zero to nine binary hidden axes, producing dimensions 2, 4, 6, 8, and 11 and up to 32,768 sites.
- Neighborhoods: fixed-degree-16 across all dimensions plus product-Moore controls at dimensions 2, 4, and 6. The latter is capped at degree 143.
- Exposure: all 288 episodes executed every scheduled action and changed exact substrate state.
- Deep-probe resurfacing on fresh fixed-degree worlds was 100% for Bitlichen and Mitosis Moss. Prism Wyrm resurfaced in 3/8 confirmatory and 2/4 holdout dimension cells.
- Fiber-column actions had lower mean visible response than surface-local actions for every critter on both fresh splits, falsifying the registered “more depth gives more surface control” prediction.
- All eight fresh fixed-degree globalizations occurred in the 2-D control; none occurred at dimensions 4-11. The broader preregistered no-globalization hypothesis therefore remains not supported.
- Depth/response-class mutual information was `0.67350` bits in confirmation and `0.62924` bits in holdout.
- Resources: `36.97` seconds wall time, `52.71` MB peak RSS, and about `6.8` MB retained artifacts on the D-drive results junction.
- Verification: all schemas, mechanics cells, geometry degrees, summaries, event causes, hashes, and exact dimension-2/6/11 replays passed with no errors or warnings.
