# CryptoSwarmHive v1 completion audit

Audited September 11, 2026 against the active goal: build, run and verify a
bounded simulated CryptoSwarmHive evaluation applying joint-channel leakage and
endogenous reporting, with reproducible artifacts and a separate historical
evidence boundary. This audit records completed work, not future commitments.

The full default campaign ran successfully and its eight artifacts replayed
byte-for-byte, including current source/input hashes. The focused regression
command completed with **68 passed**: 20 CryptoSwarmHive tests, 8 prior channel
tests, 34 reporting-game tests and 6 StegoHive recovery tests. A separate
postrun inspection checked actual saved artifacts, not just test fixtures;
its receipt-bound result is [verification.json](verification.json).

| Goal requirement | Authoritative evidence inspected | Outcome |
|---|---|---|
| Bounded simulated swarm | [Simulator](../../src/cryptoswarmhive/simulation.py), [manifest](manifest.json), retained event records | Six roles, four jobs/world, hard split/rollout caps, deterministic local execution |
| Explicit, deposit/wake and persistent-artifact channels | `execute_tasks`, `observed_channels`, event replay and sequential-task tests | Actual packets, deposit ticks, two-tick sleep/wake delay and stored/retrieved artifacts |
| Utility-matched factorial and controls | [Stress summary](evidence/stress_summary.json), raw paired world records | All eight masks plus no-channel/matched-noise controls; 50 policy/arm utility summaries preserve net task tokens exactly; destructive control fails the gate |
| World-level units and held-out decoding | Training-only decoder code, input guards, saved world IDs and decoder census | 2,560 independent world blocks, 28,160 paired records, disjoint 256/256 train/holdout per policy; 770 single/pair/joint comparisons |
| Conditional histories and side information | [Protocol](PROTOCOL.md), [exact information](evidence/exact_information.json), actual-event rank tests | Public and initialized-key views; four-job histories; exact synergy and late-history examples, separate from empirical decoding |
| Task payoff and endogenous participation | Actual job fees/costs, arm-specific expected values, [selected outcomes](evidence/selected_summary.json) | Game v derived from task model; realized payoff residuals retained; exit means no completed work |
| Entry/report/dispute, reporting/privacy/liquidity/false-claim costs | Solver parameters, settlement ledger, exhaustive terminal-profile tests | All costs and chance branches implemented; imperfect-evidence kernel is conditional and distinct from diagnostic decoding |
| Insider coalitions and bounty cancellation | Rational coalition audit, realized ledger tests and saved balances | Bounty cancels within E+R; outside slash and costs remain; every selected ledger conserves 300 fake tokens and closes escrow |
| Equilibrium sets versus selected basins | [Game census](evidence/game_census.json), all saved basin members | 88 arm/scenario games; complete pure SPE sets and separate 48-initialization selections; mixed behavioral scope stated explicitly |
| Deterrence failure flags | Exact equilibrium records and selected rollouts | Reporting silence, profitable insider deviation, honest exclusion and selected defection exposed; honest quiet paths distinguished from absent threats |
| Actual selected-policy evaluation | [Selected raw worlds](evidence/selected_worlds.jsonl.gz), frozen-decoder application tests | 7,616 rollouts on 64 overlapping held-out triple-policy worlds; all selected profiles verified pure SPE; no duplicate independent sample claim |
| Reproducible outputs and validation | [Runner](../../src/cryptoswarmhive/campaign.py), [receipt](evidence/receipt.json), full replay, tamper tests | Eight complete artifacts; hashes, world/event replay, game correspondence, closed-ledger invariants and corruption rejection verified |
| Preserve historical boundary | Evidence-class guards, source/I/O inspection, prior follow-up replay | New evidence only; retained historical artifacts unchanged and never pooled; prior finite follow-up still replays exactly |
| No live systems or real funds | Imports, code paths, output directory and tool actions | Local standard-library simulation and file outputs only; no network, wallet, deployment or real transaction operations |

The inspected default output shows 100% held-out joint decoding for each of the
four planted message policies, versus near-chance controls, while individual
histories remain exactly null in the parity kernels. In the intact arm, costly
reporting and report privacy select silent defection with 100% joint decoding.
Liquidity and false-claim extortion select exit; individual honest compliance
can still admit a profitable insider deviation. These are bounded simulator
findings, not historical StegoHive results or evidence about a live swarm.

The completion claim is limited to the stated evaluation. It does not claim
emerged collusion, learned semantic audits, cryptographic security, decentralized
learning convergence, all mixed-equilibrium enumeration, or arbitrary-adversary
deterrence. Those are expressly outside the protocol and are not silently
substituted for the goal's simulator-level deliverables.

Reproduction commands are in the [protocol](PROTOCOL.md). The postrun audit
checked 35 factorial contrasts, 110 paired control contrasts, all game basin
members, every selected ledger's final balance/escrow and all output/source
hashes. The byte-identical campaign verification and independent property tests
provide complementary checks; neither is presented as a recovered historical
freeze or an independent second simulator implementation.
