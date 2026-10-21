# CryptoSwarmHive simulated evaluation — results

Completed offline evaluation of six roles, four sequential jobs, and fake-token
escrow. All results are new simulation evidence. No historical StegoHive worlds
were loaded, and no live network, funds or model services were used.

[Protocol](../PROTOCOL.md) · [Integrity receipt](receipt.json) ·
[Leakage analysis](stress_summary.json) · [Exact information](exact_information.json) ·
[Game correspondence and basins](game_census.json) · [Selected outcomes](selected_summary.json)

The stress study contains 2,560 independent world blocks
and 28,160 paired audit-arm records. The selected evaluation
adds 7,616 rollout records on the same 64 held-out
triple-policy world blocks; these are not additional independent samples.

## Forced diagnostic participation

| Policy | Explicit | Timing | Artifact | Joint | Joint 95% simultaneous interval | Matched-noise joint | Task success |
|---|---:|---:|---:|---:|---|---:|---:|
| explicit_bit | 1.000 | 0.496 | 0.496 | 1.000 | [0.858, 1.000] | 0.496 | 0.903 |
| pair_xor | 0.508 | 0.508 | 0.508 | 1.000 | [0.858, 1.000] | 0.508 | 0.889 |
| triple_xor | 0.484 | 0.484 | 0.484 | 1.000 | [0.858, 1.000] | 0.484 | 0.910 |
| history_xor | 0.512 | 0.512 | 0.512 | 1.000 | [0.858, 1.000] | 0.512 | 0.893 |
| independent_noise | 0.488 | 0.488 | 0.488 | 0.488 | [0.346, 0.630] | 0.488 | 0.892 |

All 50 utility-preserving policy/arm summaries pass exact within-world
task-token equality. The destructive arms have task-success rates explicit_bit: 0.528, pair_xor: 0.523, triple_xor: 0.512, history_xor: 0.515, independent_noise: 0.476.
They fail the utility gate. All seven views, both side-information regimes,
eight factorial arms, controls and world-paired contrasts appear in the JSON.

## What the conditional audit establishes

| Policy / access | Exact single-channel history information | Joint bits | Twelve chronological increments |
|---|---|---:|---|
| triple_xor/111/public | [0, 0, 0] | 1 | [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0] |
| history_xor/111/public | [0, 0, 0] | 1 | [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1] |
| triple_xor/001/initialized_keys | [0, 0, 0] | 1 | [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0] |

The single-channel column is marginal without keys; the joint/increment columns
condition on the stated access. Initialized keys can reveal a message from one
otherwise null channel. The history policy discloses its bit only at the last
artifact when prior observations are included. Exact results use the linear
rank identity for this planted kernel, not empirical failure to decode.

## Endogenous game and actual settlement (intact arm)

| Scenario | Pure SPE | Entry outcomes | Defection-contingent slash probability | Max insider deviation gain | Honest continuation | Selected joint decode |
|---|---:|---|---|---:|---|---|
| credible_threat | 1 | honest | 1.0 | 6 | 3.0 | 0.547 |
| report_cost | 1 | defect | 0.0 | 0 | 3.0 | 1.000 |
| report_privacy | 1 | defect | 0.0 | 0 | 3.0 | 1.000 |
| liquidity_exclusion | 1 | out | 1.0 | 5 | -1.0 | 0.469 |
| false_claim_extortion | 1 | out | 1.0 | 9 | -7.0 | 0.469 |
| imperfect_evidence | 1 | honest | 0.75 | 6 | 3.0 | 0.547 |
| initialization_ties | 4 | defect, honest, out | 0.0, 1.0 | 10 | 0.0 | 0.469, 0.547, 1.000 |
| internalized_harm | 1 | honest | 1.0 | 0 | 3.0 | 0.547 |

Selected decoding uses frozen stress-training decoders on 64 held-out worlds
per equilibrium. Intervals and all channel views are in selected_summary.json.
Honest policies send the independent surrogate; excluded workers complete no
jobs. Thus low selected leakage is not a certificate that the channel is safe.

The fixed-probability comparator marks all eight intact-arm bonds weakly
deterrent. Costly reporting and privacy select silent defection; liquidity
and false-claim extortion exclude honest workers. Individual honest compliance
can still admit a profitable entrant+reporter deviation. Only the scenario
where the reporter internalizes defection harm passes the declared coalition
criteria for the intact arm. That assumption does not protect against harms
borne by outsiders. Initial-cell counts are separate from equilibrium sets
and are not empirical learning probabilities. Mixed SPE are described in the
protocol's recursive correspondence but are not numerically enumerated.

Every selected ledger conserves 300 fake tokens and closes escrow. The bounty
cancels in entrant+reporter joint payoff; external slash and real costs remain.
Slashing is based on unauthorized-diversion receipts and a declared joint
evidence kernel. No message-decoding rate is treated as a fraud-proof rate.

## Interpretation and limits

This applies the StegoHive follow-up to an operating finite swarm/escrow model:
joint observations and earlier events expose planted signals, matched audits
preserve task payoff, and endogenous reporting changes realized behavior.
It does not establish emerged collusion, learned semantic audit performance,
real-world crypto security or arbitrary-adversary deterrence. Audit field
separation, perfect observation of entry action, risk neutrality and binding
coalition commitment are explicit assumptions. Near-chance empirical scores
are not proof of zero information. Repeated worlds across arms and equilibria
must remain paired. See the protocol and completion audit for reproduction and
requirement-level verification.
