# Xenobots exploratory campaign v0.1

**Scope:** fixed simulator with invented voltage-source memory, 25×25 lattice, 220 ticks, seeds 11/23/47. Seven conditions yielded 21 complete CPU episodes. This is within-model validation, rather than biological replication or a confirmatory study. Re-run with `python xenobots/sim.py --campaign` to produce full raw seed rows and paired deltas.

| Arm | Final Dice, seed 11 | Seed 23 | Seed 47 | Mean | Recovery latency (steps; median when defined) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `retained_intact` | 0.667 | 0.667 | 0.667 | 0.667 | 11 |
| `memory_ablated` | 0.000 | 0.000 | 0.000 | 0.000 | undefined |
| `communication_ablated` | 0.212 | 0.212 | 0.212 | 0.212 | 4 |
| `split_contact` | 0.682 | 0.701 | 0.682 | 0.688 | 14 |
| `rewired_contact` | 0.373 | 0.496 | 0.367 | 0.412 | 7 |
| `retarget_ring` | 0.691 | 0.660 | 0.679 | 0.677 | 12 |
| `competing_goals` | 0.284 | 0.288 | 0.284 | 0.285 | 14 |

## Interpretation

The retention-off arm loses its target pattern after cue withdrawal because its memorization mechanism was deliberately removed. Without communication edges, the only sources of target information are the sparse organizers. These changes are verified causal consequences of the invented update rules. The rewired network was worse on all three development seeds; splitting the network across the midline slightly improved agreement in this configuration. Both regions still possess their own organizers, so a split effect is not equivalent to global communication loss.

`retarget_ring` is scored against a ring after externally rewriting the organizer program. Its numerical score should not be compared uncritically with the plus-score of an unswitched arm. The competing-goal run compares the resulting mixed network to both imposed masks. Recovery to the pre-wound fate pattern typically occurs because the signal remains clamped during the injury and the local fate actuator re-expresses that value. This is a planted recovery mechanism, not biological wound healing.

No significance estimate is reported because these are three development seeds and outcomes are nearly identical in several arms. In particular, the limited noise and the hardcoded organizers make large held-out generalization claims unwarranted. The protocol proposes 12 untouched seeds and extensions across organizer densities and shape families. The simulation currently passes its software invariants; it has not met the ALife ontology-gain or downstream transfer gate.

**Model code SHA-256:** `ab5dd9adf7ab88a65ce208b04a8d82c971b32d42049b0a4f485bb1d2f66ba72a`  
**Exploratory campaign SHA-256:** `4480cd4ca557f669d0d9fc0b9bb3615315e7afbae84b0ea454900337f7a2bbb8`  
**Runtime:** deterministic standard-library Python, offline; reports omit any fabricated biological calibration.
