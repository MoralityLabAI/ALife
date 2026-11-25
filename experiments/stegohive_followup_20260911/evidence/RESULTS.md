# StegoHive finite follow-up results — September 11, 2026

New planted reconstruction diagnostic and synthetic game census. Zero retained
historical worlds were loaded. These results do not measure evolved collusion.

See [protocol](../PROTOCOL.md), [game definition](../REPORTING_GAME.md),
and [integrity receipt](receipt.json).

The leakage study has 2,048 independent world blocks
and 22,528 paired arm records. Training and holdout are disjoint.

## Held-out decoding with public side information

| Codec / arm | Explicit | Timing | Artifact | Joint | Task payoff |
|---|---:|---:|---:|---:|---:|
| explicit_bit / 111 | 1.000 | 0.496 | 0.508 | 1.000 | 0.898 |
| explicit_bit / no_channel | 0.465 | 0.465 | 0.465 | 0.465 | 0.898 |
| explicit_bit / matched_noise | 0.523 | 0.496 | 0.508 | 0.523 | 0.898 |
| explicit_bit / destructive | 0.465 | 0.465 | 0.465 | 0.465 | 0.484 |
| pair_xor / 111 | 0.465 | 0.473 | 0.578 | 1.000 | 0.930 |
| pair_xor / no_channel | 0.465 | 0.465 | 0.465 | 0.465 | 0.930 |
| pair_xor / matched_noise | 0.465 | 0.547 | 0.578 | 0.484 | 0.930 |
| pair_xor / destructive | 0.465 | 0.465 | 0.465 | 0.465 | 0.488 |
| triple_xor / 111 | 0.539 | 0.516 | 0.543 | 1.000 | 0.895 |
| triple_xor / no_channel | 0.508 | 0.508 | 0.508 | 0.508 | 0.895 |
| triple_xor / matched_noise | 0.539 | 0.516 | 0.543 | 0.500 | 0.895 |
| triple_xor / destructive | 0.508 | 0.508 | 0.508 | 0.508 | 0.512 |
| independent_noise / 111 | 0.480 | 0.543 | 0.484 | 0.473 | 0.887 |
| independent_noise / no_channel | 0.543 | 0.543 | 0.543 | 0.543 | 0.887 |
| independent_noise / matched_noise | 0.480 | 0.543 | 0.484 | 0.473 | 0.887 |
| independent_noise / destructive | 0.543 | 0.543 | 0.543 | 0.543 | 0.445 |

The JSON reports all seven channel views, two side-information regimes,
all factorial arms, paired control contrasts and conservative simultaneous
intervals. The three-channel kernel has exact marginal and pairwise information
zero, while joint information is one bit; its history-conditional increments
are (0,0,1). With initialized independent keys, the artifact alone can reveal M.

Near-chance empirical accuracy does not prove a null channel. Exact information
claims come only from enumeration of the declared finite kernel. The field-aware
audits preserve task payoff identically in every paired world; destructive
erasure does not pass that utility gate. Utility preservation is a structural
assumption of this fixture, not a discovered semantic audit.

## Endogenous entry/report/dispute outcomes

The complete pure SPE sets are separate from the 48-cell initialization census.
Mixed SPE are characterized recursively in the game note, not numerically enumerated.

| Scenario | Pure SPE count | Entries | Defection slash probabilities | Largest coalition gain |
|---|---:|---|---|---:|
| credible_individual_threat_but_insider_collusion | 1 | honest | 1.0 | 6 |
| costly_reporting_silence | 1 | defect | 0.0 | 0 |
| liquidity_excludes_honest | 1 | out | 1.0 | 5 |
| privacy_suppresses_reporting | 1 | defect | 0.0 | 0 |
| false_claim_extortion | 1 | out | 1.0 | 9 |
| high_false_penalty_with_credible_dispute | 1 | honest | 1.0 | 6 |
| reporter_and_entry_indifference | 4 | defect, honest, out | 0.0, 1.0 | 10 |
| coalition_internalizes_defection_harm | 1 | honest | 1.0 | 0 |

The exogenous comparator labels all eight scenario bonds weakly deterrent.
Endogenous play exposes costly/privacy-suppressed reporting, honest exclusion,
false-claim extortion, and profitable insider deviations. An honest quiet path
alone is not a failed threat: inspect the response to counterfactual defection.
The coalition test assumes enforceable commitment and transferable utility;
within-coalition bounty transfers cancel. The protected scenario assumes that
the reporter internalizes enough defection harm, and does not generalize to
harm borne by outsiders. Basin cell counts are not behavioral probabilities.

No decoder accuracy is converted into a valid-slash probability. No live system
was changed. The executable verification replays this new study and checks
input/source/output hashes; it does not verify historical ecology evidence.
