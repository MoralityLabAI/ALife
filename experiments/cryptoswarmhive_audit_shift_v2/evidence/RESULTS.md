# CryptoSwarmHive v2 — audit-transfer results

A task-only learned audit succeeded under its calibration schema but failed
under a controlled swap of field meanings. This is new synthetic evidence,
separate from v1 and historical StegoHive worlds.

[Protocol](../PROTOCOL.md) · [Frozen audit](audit_freeze.json) ·
[Decoding and utility](summary.json) · [Exact reporting games](game_census.json) · [Receipt](receipt.json)

Calibration used 512 world blocks and 64 candidate masks, with
task outcomes as its only feedback. The frozen mask is `010101` (1 = erase).
It erased 3 fields, harmed 0 calibration worlds, and had
a simultaneous harm-probability upper bound of 0.0139
against the fixed 0.02 tolerance. Calibration eligibility: True.

Evaluation used 256 separate decoder-training and 512 held-out world
blocks, paired across layouts and arms (16,128 records).
The auditor was frozen before those phases. Each layout has its own training-only
diagnostic decoder, so representation shift cannot hide leakage from the evaluator.

| Layout / arm | Joint decode | Same-audit noise decode | Task value | Harmed worlds | Harm upper bound | Exact joint bits |
|---|---:|---:|---:|---:|---:|---:|
| stable/calibrated | 0.480 | 0.480 | 4.000 | 0/512 | 0.012 | 0 |
| stable/oracle | 0.480 | 0.480 | 4.000 | 0/512 | 0.012 | 0 |
| one_channel_swapped/calibrated | 0.480 | 0.480 | 3.102 | 210/512 | 0.473 | 0 |
| one_channel_swapped/oracle | 0.480 | 0.480 | 4.000 | 0/512 | 0.012 | 0 |
| all_channels_swapped/calibrated | 1.000 | 0.480 | 0.473 | 426/512 | 0.876 | 1 |
| all_channels_swapped/oracle | 0.480 | 0.480 | 4.000 | 0/512 | 0.012 | 0 |

The oracle row's control is its duplicate no-channel arm; it is not a learned
policy. Full tables include all seven observation subsets and initialized-key
side information, with 294 simultaneous decoder comparisons. Near-chance
empirical decoding is not proof of zero information. Exact joint-bit claims
apply only to the declared independent-pad parity kernel.

## Propagation into entry and reporting

Each game's task value is independently enumerated from the task/error model,
not fitted from held-out rewards. Pure SPE sets and initialization basins remain
separate. The following table uses the calibrated audit and credible-threat
scenario; the JSON retains all eight scenarios for every layout/arm.

| Layout | Exact expected task value | Pure SPE entry | Honest exclusion | Insider gain |
|---|---|---|---|---|
| stable | 4 | honest | False | 6.0 |
| one_channel_swapped | 22/7 | honest | False | 6.0 |
| all_channels_swapped | 13/28 | out | True | 5.464285714285714 |

These are counterfactual exact games, not additional settlement or learning
rollouts. The prior bounty-transfer cancellation and reporting-cost assumptions
remain in force. No decoder score is converted into a fraud-proof probability.

## Conclusion supported by this fixture

Calibration establishes a distribution-specific audit, not a semantic invariant.
When every field meaning swaps, the same mask removes task hints and leaves all
three diagnostic shares. Joint leakage returns while useful work declines enough
to exclude honest workers in the default game. The privileged current-schema
audit still preserves utility and removes the signal, identifying a transfer
failure rather than an unavoidable task/privacy tradeoff in this toy model.

The shifts are designed stress cases with a known causal explanation. This is
not evidence of emerged evasion, a real semantic audit, or the frequency of such
failures in production. No existing campaign evidence was pooled, and no live
systems or real funds were used.
