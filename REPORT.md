# ALife as a Learning Discipline: Geometry Controls, Emergent Mechanics, and Adapted Pressure

## Executive result

This experiment set implements the proposed two-part research track:

1. **Literal high-dimensional Life is the control for when geometry becomes averaging.** Binary totalistic cellular automata were swept over dimensions 2-5 with full Moore, axis-local, and degree-matched neighborhoods. Mean-field closure often improved with dimension, but the registered explanation that increasing neighborhood degree caused most of the trend was not supported. Many apparently perfect high-dimensional predictions were extinction, not rich averaging. That failure is informative: dimension, degree, rule scaling, finite size, and collapse cannot be collapsed into one “high-dimensional Life becomes mean-field” slogan.
2. **High-dimensional state on bounded-degree topology is the mathematical laboratory.** A vector-state graph cellular automaton was run on connected regular graphs with controlled degree, topology, state dimension, coupling, size, seeds, and single-node perturbations. A normalized-Laplacian spectral-gap feature improved frozen-predictor holdout RMSE by 6.11% in discovery and 12.30% in an independent confirmation with new degrees, sizes, dimensions, couplings, seeds, and topology. This is accepted as a narrow model-only predictive macrovariable. The stronger directional claim that higher-gap topologies consistently recover faster failed twice.

The worlds were then converted into a hidden-oracle discovery curriculum and a downstream consumer test. The curriculum made point identification, set identification, and justified abstention separately gradeable. An evolutionary schedule generator subsequently produced a stronger Confinement Width stress-test than equal-evaluation random search on untouched evaluator variants while preserving the original proxy and closure gates.

The durable product is therefore not a claim that artificial life has reproduced biology or open-ended intelligence. It is a disciplined way to learn the mathematics of emergent mechanics: build local rules, expose their causal execution, search for macroscopic variables, confirm their predictive value out of sample, and export only results that improve a registered consumer task.

## Research question and method

The organizing question was: **What knowledge benefit can ALife produce that is both mathematically meaningful and externally testable?**

The answer was operationalized as a ladder:

`eligibility -> activation -> execution -> dosage -> outcome`

No downstream effect was interpreted until the manipulated mechanism had a receipt at every applicable rung. Selection metrics were kept separate from evidence metrics and hazard metrics. Discovery seeds could propose a variable or policy; fresh confirmation and holdout conditions had to evaluate it under a frozen protocol.

The benefit taxonomy used by the track is:

| Benefit | What ALife can produce | Required evidence |
| --- | --- | --- |
| Phenomenological | A reproducible regime or transition | Persistence and phase-map occupancy, not visual interest alone |
| Descriptive | A compact macrovariable or invariant | Explicit estimator, domain, invariances, and registry non-equivalence |
| Causal | A mechanism or load-bearing site | Registered intervention semantics, exposure receipts, and controls |
| Predictive | Better forecasts on fresh worlds | Frozen matched-complexity baseline and held-out error improvement |
| Control | A policy that moves or stabilizes a regime | Resource-matched intervention benefit and hazard accounting |
| Robustness | A boundary where an explanation continues or fails | Fresh seeds, scales, topologies, perturbations, and negative cells |
| Measurement | A way to grade whether a claim was earned | Known truth, calibration, set coverage, and abstention penalties |
| Operational | A better downstream test or data product | Compute-matched consumer improvement without weakened validity gates |

## Experiment 1: geometry-to-averaging control

### Design

- 144 independently initialized binary CA worlds: 32 discovery, 48 confirmation, 64 untouched holdout.
- Dimensions 2, 3, 4, and 5.
- Axis-local, fixed-degree-12, and full Moore neighborhoods.
- Fraction-scaled rules plus literal B3/S23 as a simple-limit control.
- Initial densities 0.25 and 0.35, up to 4096 cells, 40 synchronous steps.
- Evidence: density-only binomial mean-field error, neighbor-pair covariance, and a finite-lag correlation proxy.
- Hazards: extinction, saturation, fixed/cyclic dynamics, resource use, and trivial zero-error closure.

### Result

Moore-neighborhood mean-field error declined with dimension, but high-dimensional zero error frequently coincided with extinction. The confirmatory Moore MAE slope was `-0.00880` per dimension. Contrary to the registered causal explanation, the fixed-degree arm retained a more negative slope (`-0.03515`), so holding degree fixed did not remove the trend. No fixed-degree cell met the full nontrivial adequacy conjunction. All six confirmatory/holdout literal-B3/S23 cells at dimensions 4-5 were extinction-only.

Twenty of 27 numeric closure passes were rejected as nontrivial evidence by the activity/collapse hazard overlay. The phase map therefore establishes a tested boundary, not a universal critical dimension.

### Knowledge gained

“Geometry becomes averaging” must be decomposed into at least four questions: whether prediction error falls, whether correlations fall, whether the regime remains active, and whether the trend survives degree matching. This experiment supported only the first in the full-neighborhood arm and explicitly falsified the proposed degree-only explanation.

## Experiments 2-3: bounded-degree vector-state graph laboratory

### Design

The graph CA uses connected regular graphs and high-dimensional node states. Each synchronous update combines a shared nonlinear channel reaction with neighbor-mean coupling. Every episode executes a registered perturbation to channel 0 of one node and retains paired-state recovery trajectories.

V1 contained 162 episodes on degree-6 ring, rewired-regular, and random-regular graphs with state dimensions 2/8/16, couplings 0.15/0.35, and 96/128/160 nodes. V2 contained 192 fresh episodes, evaluated without predictive refitting, using degrees 4/8, state dimensions 4/12, couplings 0.2/0.4, 112/144/192 nodes, and a new circulant-skip topology.

### Result

The candidate model added one scalar—the normalized-Laplacian spectral gap—to a baseline containing intercept, coupling, and log2 state dimension.

| Campaign | Baseline RMSE | Spectral RMSE | Relative gain |
| --- | ---: | ---: | ---: |
| V1 discovery/holdout | 0.90405 | 0.84878 | 6.11% |
| V2 frozen confirmation | 0.65325 | 0.57290 | 12.30% |

Both gains exceeded the registered 5% gate. V2 confirms predictive utility on a distinct assessment distribution; its larger relative percentage is not evidence of a stronger effect than V1. The variable is now recorded in the ontology registry with separate `admitted_under` and `confirmed_under` distributions, its estimator, valid domain, equivalence class, confounds, failure modes, and next falsification test.

The stronger claim failed: higher-gap alternative topology did not yield faster recovery in at least 80% of paired units in either campaign. Spectral gap is predictive in this model family; necessity, mediation, and uniqueness are unsupported.

### Mathematical interpretation

The result demonstrates the useful role of bounded-degree nontrivial topology. Increasing state dimension did not force neighborhood size to explode; topology remained a controllable mathematical object. A global graph invariant added out-of-sample predictive information about the propagation and recovery of a local state perturbation. That is the target form of ALife discovery: a candidate macrovariable earns registry status through intervention-linked prediction, not appearance.

## Experiment 4: hidden-oracle discovery curriculum

### Two-axis epistemic ladder

The curriculum separates two distinctions that should not be collapsed:

| | Point identified | Set identified / point unavailable |
| --- | --- | --- |
| Simulator oracle present | Exact effects, true nulls, reachability, causal sites, conservation | Compatible intervals and oracle-certified point unidentifiability |
| Simulator oracle absent | External validation only | Bounded claims, predictive adequacy, or grader abstention |

Set-valued targets remain trainable when an oracle can score interval coverage. The trainable/non-trainable boundary is oracle presence, not point identification.

### Tasks and scores

The 63 episodes span seven task families: planted nonzero effect, true null, structural unreachability, exhaustive causal-site recovery, conserved quantity, masked identified interval, and masked point target. Each policy registers its probability of hitting a predeclared claim target before evidence, then claims or abstains under a finite budget.

On holdout, the calibrated reference investigator scored `0.92795`; the proxy claimant scored `0.35812`; always-abstain scored `0.24938`. The calibrated margin over the best control was `0.56983`, exceeding the frozen `0.20` gate. Set-identified evidence score was `1.0`. All nine point-unidentifiable tasks received correct registered abstentions, while always-abstain incurred avoidable abstention on 85.71% of tasks.

This validates the incentive structure and artifact schema. It does **not** demonstrate that a learned AI investigator can perform these tasks; the calibrated reference policy was constructed to use the exact finite-world solution.

## Experiment 5: compute-matched consumer transfer

### Design

The existing Confinement Width fiber-routing exhibit observes and controls coordinate `z` while true validity also depends on hidden coordinate `y`. The original proxy and projected model can remain perfect while optimization pressure moves `y` across the true threshold.

Two generators searched length-80 binary action schedules:

- Compute-matched random schedule search.
- Population-based evolutionary mutation and selection.

For every paired seed, each method received exactly 128 candidate evaluations, 24 advance actions per selected schedule, identical training evaluators, identical time-only information, and the same tie-break rule. Evidence came from 12 untouched search seeds and four unseen combinations of hidden threshold and fiber step size.

### Result

Random search achieved `0.59661` mean holdout kernel-escape rate. Evolutionary search achieved `0.70729`, a paired improvement of `+0.11068` against the frozen `+0.10` point-estimate gate. All 12 paired seeds favored evolution. The deterministic paired bootstrap 95% interval was `[+0.08307, +0.13620]`.

The registered point-estimate stopping gate passed, but the interval includes improvements smaller than the practical `+0.10` threshold. The correct reading is therefore “accepted under the frozen gate with consistent positive direction,” not “the population mean is proven to exceed +0.10.”

Every selected schedule executed exactly 24 actions. Both methods had zero proxy failures and zero projected-model closure defect on every evaluation. The downstream gain did not weaken the consumer’s existing validity gates.

### Boundary

The schedule genome makes temporal concentration easy, and the monotone fiber rewards early actions. Evolutionary search produced a stronger stress-test under the frozen monotone schedule task; whether this reflects transferable adapted pressure rather than efficient front-loading remains unconfirmed. The result does not establish difficult optimization or general superiority over hand-designed schedules, dynamic programming, or arbitrary optimizers.

## Overall methodology

An ALife learning discipline should use the following loop:

1. **Name the benefit.** Choose phenomenological, descriptive, causal, predictive, control, robustness, measurement, or operational knowledge.
2. **Freeze the claim.** Define the experimental unit, target, intervention, smallest practical effect, uncertainty, stop rule, and hazards before confirmation.
3. **Prove exposure.** Retain eligibility, activation, execution, dosage, and outcome receipts.
4. **Search without promoting.** Use discovery metrics to propose regimes, variables, or policies; never treat archive occupancy, entropy, compression, or visual interest as confirmation.
5. **Register ontology.** Compare candidate macrovariables against a seed-vocabulary ledger and specify domain, invariances, estimator, confounds, and failures.
6. **Confirm on fresh worlds.** Freeze coefficients or policies and change seeds, scale, topology, or observation conditions.
7. **Export only through a consumer gate.** Require a compute-matched downstream improvement while preserving the consumer’s validity constraints.
8. **Preserve negative knowledge.** Failed mechanisms, collapse regimes, unidentifiability, and rejected practical thresholds are part of the product.

## What is supported

- A reproducible dimension/degree phase map for the implemented binary totalistic CA family.
- A bounded-degree vector-state graph laboratory with exact graph invariants and perturbation receipts.
- A confirmed model-only predictive macrovariable: normalized-Laplacian spectral gap for perturbation recovery in the declared graph-CA family.
- A working graded discovery-episode schema for point, set, and point-unidentifiable targets.
- A compute-matched downstream Confinement Width stress-test gain under the frozen point-estimate rule and preserved validity gates.

## What is not supported

- A universal dimension where geometry becomes averaging.
- The hypothesis that neighborhood-degree growth explains most of the observed dimension trend.
- Emergence, open-endedness, life, cognition, or biological validity.
- A unique or causal role for spectral gap.
- Learned-investigator generalization.
- Real-world evasion, deception, or superiority of evolution over arbitrary optimizers.

## Reproducibility and resources

All full artifacts resolve through `C:\projects\ALife\results` to `D:\ALife\project_results`. Each campaign retains a frozen manifest, raw JSONL, summary, seed manifest, code/config/environment receipt, knowledge card, and hashes. The receipt environment hash is explicitly treated as an internal-consistency check; verifiers separately compare the actual review runtime against the recorded Python, platform, package, CPU, and RAM fields. Runtime drift and non-D storage are reported without invalidating intact artifact hashes. Portable source lookup requires an exact path or one unique multi-component suffix; basename guessing is forbidden and ambiguity is a hard failure. The full test suite includes regression coverage for these cases.

Retained full campaigns:

- `geometry_averaging_v1`: 144 episodes, about 3.2 MB.
- `graph_state_v1`: 162 episodes, about 3.9 MB.
- `graph_state_v2_confirmation`: 192 episodes, about 4.5 MB.
- `discovery_curriculum_v1`: 63 episodes, about 0.2 MB.
- `confinement_transfer_v1`: 24 paired episodes, about 0.1 MB.

## Next falsification program

1. Construct regular graph pairs that separate spectral gap from clustering and path length, then evaluate the frozen recovery model at unseen perturbation nodes, channels, and horizons.
2. Replace the calibrated curriculum reference with a real local investigator that must register a design before observations.
3. Add competing coarse-grainings to the set-valued tasks and score coverage plus intervention sufficiency.
4. Evaluate the schedule generator on non-monotone fiber dynamics with recovery, delayed costs, and changing thresholds. A pure front-loading advantage should fail there.
5. Refine active geometry boundaries with at least five new seeds per selected phase-map cell before adding more rule families.

The strongest defensible claim is deliberately narrow: **this is a reproducible, ground-truthed evaluation substrate with working claim, calibration, set-identification, and abstention incentives—not yet a learned discovery engine.**
