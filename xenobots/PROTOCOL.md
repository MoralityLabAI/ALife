# Pattern-memory experiment protocol v0.1

Status: **exploratory implementation with a frozen proposed holdout**. Model-dependent causal effects are known because the interventions alter planted controls. Biological inference remains outside the scope of this protocol.

## Registration

- **Unit:** independent seeded simulator episode. Trajectory ticks are repeated observations within that episode.
- **Observable:** continuous voltage/fate and binary threshold phenotype, plus organizer graph and event log.
- **Targets:** experimenter-specified plus and ring masks. Endpoint Dice is scored at tick 220. Recovery latency and injury restoration use a wound at tick 120 following cue withdrawal at tick 65.
- **Initial conditions:** 25×25 square lattice, organizer spacing 3, voltage noise 0.008, gap strength 0.60, leak 0.014, fate update 0.16, all held fixed across paired arms.
- **Exploration seeds:** 11, 23, 47. These were used during development and cannot support an unbiased confirmation claim.
- **Frozen held-out seeds (proposed, not yet run):** 101, 103, 107, 109, 113, 127, 131, 137, 139, 149, 151, 157.
- **Compute:** 12 seeds × 7 arms = 84 episodes, 220 ticks at 25×25; standard-library CPU. A separate robustness run would change size and organizer spacing; it requires another preregistration.
- **No early stopping or arm selection.** Export every seed/arm result, including failed or undefined recovery metrics.

## Tests and acceptance gates

1. **Retention:** compare the intact retained model with its cue-withdrawn, retention-disabled control on matched seeds. Registration: mean final Dice improvement ≥0.20 with ≥10/12 signs positive. This gate tests the effect of *programmed* retention only.
2. **Communication:** compare intact with a graph lacking all communication edges. Registration: mean Dice improvement ≥0.15 with ≥10/12 positive signs. This asks whether local coupling transports the supplied source program.
3. **Rewiring:** record distribution of paired endpoint Dice shifts, including sign, against the intact graph. Direction is exploratory because rewiring may help or hurt depending on the imposed target.
4. **Split:** similarly report the paired effects of cutting midline edges. Do not presuppose that severance lowers the score.
5. **Retarget:** report the final ring Dice in the switched arm and the final plus Dice in the original arm, with a time series of each target's own score. Because goal labels differ, avoid interpreting their raw endpoint Dice difference as a treatment effect.
6. **Goal conflict:** report final plus and ring Dice for the two-program arm. A change from the unified-target arm measures the response to imposed source conflict; neither program has been learned by the modeled cells.
7. **Wound:** report the pre/post drop, restoration fraction, and recovery latency. Separate pattern failure before injury from failure to recover; undefined metrics remain null, never zero-imputed.

There are no multiple-comparison adjusted statistical claims in v0.1. Hypothesis testing on this invented model does not establish general biological truth. To make a discovery claim, freeze an independently implemented mechanistic rival (e.g. contact-limited exchange with voltage-dependent junction gating), then evaluate held-out shapes, graph degrees, sizes, focal lesions, organizer sparsity, and seed populations. An intervention effect robust only under the planted model is a model property.

## Confounds and observability

Organizer positions and values encode the entire target explicitly. This hardcoded source channel can explain successful repair without autonomous goal discovery. The grid is fixed and shape is a fate label rather than physical anatomy. The wound preserves graph/voltage, so restoration tests only the actuator's ability to re-express a prior program. `split` changes only one cut, leaving organizers on both sides. The random noise is small relative to the clamped signals; large uniform-looking seed agreement is expected. A nested exploratory selection would invalidate the held-out registration.

The canonical replay verifier proves that serialized output matches this code's deterministic execution in the current runtime. It does not establish empirical correspondence with xenobot trajectories. Cell-level intervention semantics and all labels are inspectable in `sim.py`. Use ALife's separate generator-coverage and ontology-registry gates before accepting a new hypothesis or a downstream benchmark improvement.
