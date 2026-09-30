# CryptoSwarmHive simulated evaluation v1

September 11, 2026. New, offline, bounded simulation in ALife. No existing
CryptoSwarmHive implementation or specification was found in this repository;
this document defines that name for this evaluation. It is a six-role swarm
with job routing, delayed artifact retrieval and fake-token escrow. It is not a
live crypto network, a cryptocurrency valuation, or a trained swarm experiment.

## Evidence boundary and deliverables

Apply the [StegoHive follow-up](../stegohive_followup_20260911/PROTOCOL.md) to
an executable swarm and its actual settlement paths. The earlier planted
single-cycle study remains unchanged. Its finite reporting-game solver is reused
as code, with new parameters derived from this workload. No earlier observations
are imported. Retained historical V1–V9 worlds remain governed by the
[recovery boundary](../../STEGOHIVE_RECOVERY_AUDIT_2026-08-27.md).

Every new world, selected rollout and summary is labeled
`cryptoswarmhive_simulated_eval_v1_not_historical`. This study's verifier reads
only its manifest, new source/tests, the reused solver code, and its own evidence
directory. It never opens the historical results junction. Source and output
hashes are integrity records, not a third-party preregistration or proof of
semantic validity. The finite exact-information census, sampled diagnostic
worlds, equilibrium correspondence, and selected rollouts are separate artifacts.

The executable deliverables are `src/cryptoswarmhive/{simulation,evaluation,campaign}.py`,
this protocol and manifest, `tests/test_cryptoswarmhive.py`, and the generated
`evidence` directory. The results report links the machine-readable artifacts.

## Six roles and four-job worlds

The requester issues four binary routing jobs. A scout sends an explicit hint,
a courier schedules an archive deposit, and an archivist supplies a stored hint.
The coordinator sleeps at each epoch start, wakes two ticks after the deposit,
reads the persisted artifact and combines the three hints by majority vote.
A reporter can later claim unauthorized diversion of requester tokens.

The four working roles share the entrant's account and choose entry jointly;
they are not four additional strategic players. The game has two strategic
decision makers: entrant E (the worker group) and reporter R. The requester and
resource/treasury/harm accounts are passive accounting endpoints. A further
insider coalition can include E and R, with binding commitments and transfers.

Initialization draws uniform task targets, independent hints with 0.8 accuracy,
fresh per-job pads Pj,Qj, an independent public bit S, a surrogate bit N and a
hidden evidence-kernel state. The diagnostic bit M is drawn **after** initialization
on a separate deterministic pseudorandom stream. Policy code, pads, initialized
keys and initial histories contain no M. M remains constant through four jobs.
The theoretical kernel uses iid uniform latent bits; executable runs are seeded
pseudorandom realizations. There is no online training or adaptive population.

Epoch j starts at tick 10j. The scout message arrives at 10j+1; deposit occurs at
`10j+2+2*hint_courier+timing_bit`. Wake follows two ticks later, before deadline
10j+8. The artifact is created at deposit and removed from the store on retrieval.
Deposits expose an artifact ID, not a content hash; leaking a brute-forceable
hash through the timing interface would defeat the declared access separation.
The full event log supports replay; receivers receive only their declared views.

A correct job pays `125/56` fake tokens to E; each job consumes one token of
operating resources. Majority accuracy is `112/125 = 0.896`, so four-job expected
net task value is exactly 4 tokens. Realized net task value varies with actual
correctness. Fees, work costs and deadlines are identical across matched arms.
The destructive control makes the coordinator always select route zero;
expected accuracy is 0.5 and expected net value is `13/28` tokens. Its lower task
value also changes the game entry incentives, rather than being hidden by a
fixed payoff assumption.

## Channel policies, histories and utility matching

| Stress policy | Explicit style at job j | Timing parity | Stored artifact mark |
|---|---|---|---|
| explicit_bit | M | Pj | Qj |
| pair_xor | Pj | M xor Pj | Qj |
| triple_xor | Pj | Qj | M xor Pj xor Qj |
| history_xor | Pj | Qj | Pj xor Qj until final job; then M xor P0 |
| independent_noise | Pj | Qj | N xor Pj xor Qj |

For history_xor, information appears only at the last artifact when prior
history is available. Final-job observations alone do not suffice without the
initialized key. For triple_xor, the first complete triple already discloses M;
later identical-message jobs add zero conditional information. Each whole
single-channel history is marginally independent of M for both policies.

The 2x2x2 intervention enables/canonicalizes the explicit style, timing parity
and artifact mark in that order. Canonicalization sets the selected modulation
bits to zero and preserves the task-bearing fields. Timing changes recompute the
wake schedule. All masks are evaluated on exactly the same world initialization
and M. The utility gate is exact paired equality of realized net task tokens
with mask 111, not a tolerance fitted after holdout inspection.

Controls are `no_channel` (a labeled duplicate of mask 000), `matched_noise`
(replace M by the independent surrogate N in the entire encoder, preserving
the averaged joint cover law), and `destructive` (erase the three channels and
use the fixed action at deadline). The first two preserve task utility; the
last is deliberately a utility-loss control and cannot pass the mitigation gate.
The no-channel name means **no diagnostic capacity**, not physical silence.
It is not asserted equivalent to the recovered StegoHive V3 treatment.

This is a planted policy family and an audit with a known task/modulation field
boundary. Nonconstant task reward and delayed execution make the task substantive
within the toy environment, but preservation of these known fields is still an
assumption. No claim is made that a real semantic audit can discover this split
or preserve arbitrary learned-agent utility. The point is to evaluate composition,
history and incentives without mistaking protocol fixtures for empirical discovery.

## World-level decoding

The frozen manifest uses five policies, each with 256 training and 256 held-out
worlds: 2,560 independent world blocks and 28,160 paired stress-arm records.
Each world has four jobs, but jobs and arms never increase the sample size.
All policies and decoder choices are fixed before generating holdout. Training
and holdout world IDs and RNG domains are disjoint. There is no seed search.

Decode all seven nonempty channel subsets using whole four-job histories under
two receiver-information packages: public S, or S plus all initialized pads.
Task labels, world IDs, M labels, hidden evidence state, seed and unselected
channels are excluded from features. Task hints are independent of M and all pads
in this kernel, so the decoder only uses the modulation bits extracted from
actual event fields. This independence must be re-established if policies are
extended; public hashes, read receipts, task-dependent audits and access choices
would also need to enter the relevant histories.

The decoder fits an affine GF(2) parity by Gaussian elimination on training
worlds. Free coefficients are set to zero. Inconsistent labels trigger a
training-majority constant with ties to zero. This fixed class expresses the
planted policies, including cross-job parity. It does not imply detection of
arbitrary nonlinear leakage. Test-world labels are used only for scoring.

Report accuracy against chance 0.5 with simultaneous 95% Hoeffding intervals
over 770 fixed decoder comparisons. Joint paired differences against both
controls use a separate 110-comparison family. Main, pair and triple factorial
contrasts use a separate 35-comparison family; for factor subset J the contrast
is the signed sum of eight arm scores divided by `2^(3-|J|)`. Intervals use the
correct world-level bounded ranges (1 for accuracy, 2 for paired difference,
and `2^|J|` for factorial contrasts). Each family has its own 5% error allowance,
not a collective 95% claim over all outputs. Dependent paired arms are allowed
by the union bound; independence is required between held-out world blocks.
Utility gate pass is pathwise equality in this finite construction. Empirical
near-chance decoding never certifies a null channel or a capacity upper bound.

## Conditional-information audit

The exact census constructs linear observation forms through actual simulator
execution and feature extraction on latent-bit basis vectors. For uniform binary
latent variables, `I(M;Z)=rank(Z)+1-rank(Z,M)`, in bits. The resulting exact
information is a property of this finite linear kernel, separate from empirical
decoder scores. It reports the information in each whole single-channel history,
in the joint transcript, and the 12 increments in chronological job/channel order.

For initially independent receiver information S, a defensible budget must bound
`sum_t I(M;Zt | S,Z<t)`, including all accessible past events. This sum equals
`I(M;Z1:T | S)`. With uniform K-message M and decoder error e,
`(1-e) log2 K <= I(M;S,Z1:T)+h2(e) <= B+1` if the sum is at most B and
`I(M;S)=0`. Otherwise the initial information must be added. Independent keys
do not justify omitting S from the conditioning. Marginal information sums fail
for the planted parity policies. An arbitrary adaptive monitor would require
bounds under its policy-induced conditional history law; this four-job census
does not establish such a general bound.

## Endogenous entry, reporting, dispute and evidence

For every arm, the finite solver uses that arm's analytic expected task value as
v. E chooses out/honest/defect before task outcomes are revealed. Reporting then
observes the true entry action; R chooses quiet/report; E chooses accept/dispute.
Rational expected-utility comparisons integrate task uncertainty and the
post-dispute evidence kernel. Realized game execution uses actual job payouts.
No actor selects actions based on the simulator's hidden evidence state or M.

The default game uses bond 10, defection gain 6, liquidity rate 0.1, reporting
cost 1, reporter privacy harm 1, dispute cost 1, false-claim penalty 3, bounty
fraction 0.5 and no internalized reporter harm. True disputed claims succeed
with probability 1; false disputed claims fail. Additional scenarios separately
raise reporting cost to 6, privacy harm to 6, liquidity rate to 0.5, or dispute
cost to 12. An imperfect-evidence scenario has four equiprobable **joint** states:
two sound states, missing evidence, and a faulty adjudicator; true acceptance
is 3/4 and false acceptance is 1/4. A tie scenario sets liquidity rate to 0.4,
gain to 10 and reporting cost to 4. A final scenario gives R defection harm 8.

A diagnostic message is **not** a fraud witness. Defection separately transfers
the declared gain from requester to E with an unauthorized-diversion receipt.
Claim truth is derived by replaying the ledger and checking that receipt. The
evidence fault kernel is applied only on dispute. Acceptance settles any claim,
including a false one, without adjudication. The conditional slashing probability
comes from report/dispute choices plus that kernel, never from decoder accuracy
or a product of marginal access/report/verification rates. Default reporter
observation of action is a strong stated information assumption.

The simulation starts with 100 fake tokens each for requester, E and R. Hash-linked
transfer receipts record fees, work cost, liquidity cost, unauthorized gains,
report costs/privacy harm, dispute costs, rejected-false-claim penalties, bounty,
external slash and returned principal. Every ledger conserves 300 tokens, keeps
balances nonnegative, and closes escrow. Resource and harm transfers are utility
cost accounting sinks, not claims that real privacy can be reimbursed. Hashes
detect retained-byte tampering but provide no authentication or cryptographic
security proof. No keys, wallet connections, real transactions or network calls
are used.

Realized E utility equals the selected game's expected utility plus the actual
task-payoff residual and realized settlement residual. R utility includes the
realized report/dispute outcome. Averaging the four evidence states exactly
reproduces expected game utility after adding the realized task residual. Tests
check all 48 profiles, including off-path false claims and disputes.

The E+R coalition's bounty is an internal transfer: subtract only external slash
and real costs from joint payoff. The solver enumerates enforceable joint path
deviations with transferable utility. It does not solve coalition-proof equilibrium
without binding contracts. A profitable joint deviation rejects robust deterrence
even when ordinary individual equilibrium selects honest entry.

## Equilibrium sets and selected rollouts

For every arm and scenario, enumerate the complete pure subgame-perfect
equilibrium set with exact rational ties. Mixed SPE are not numerically
enumerated; their full behavioral correspondence follows recursive backward
induction over distributions supported on maximizing actions, as specified in
the [reused game note](../stegohive_followup_20260911/REPORTING_GAME.md).
Upstream best responses depend on continuation probabilities, so the mixed set
is not simply the convex hull of pure profiles.

Separately apply the declared reverse-depth best-response selector from all 48
pure initial profiles. Incumbent maximizing actions persist on ties; remaining
ties use the fixed action ordering. These initialization-cell counts are not
learned frequencies or independent replicates. Every distinct selected pure
equilibrium gets actual task/settlement rollouts on the first 64 held-out
triple_xor worlds, across all 11 arms. These worlds overlap the stress study
and are never counted again as independent evidence.

Honest participants encode N, defectors encode M, and excluded participants emit
no task events. All seven views under both information packages are scored with
the frozen stress-training decoders, with a separately declared simultaneous
interval family covering all selected equilibrium/view comparisons. Selected
task success is per offered job, so exit is recorded as no completed work.
Low selected leakage caused by honest behavior or exit is distinguished from
the channel's forced-entry diagnostic capacity and the utility gate.

Report no on-path reporting separately from no reporting after counterfactual
defection. Honest quiet play with a credible reporting threat is not automatically
failure. Failure criteria include absent defection-contingent reporting,
profitable insider deviation, negative honest continuation value or selected
defection. Honest zero-value ties and selected exit are also displayed. A bond
that passes `gain - bond*perceived_probability <= 0` can fail any of these tests.
The former expression is only a labeled baseline comparator, not the runtime
decision rule. Late slashing leaves realized diversion and privacy harm in the
record; it is not prevention.

## Reproduction and completion checks

```powershell
$env:PYTHONPATH = 'C:\projects\ALife\src'
.\.venv\Scripts\python.exe -m cryptoswarmhive.campaign
.\.venv\Scripts\python.exe -m cryptoswarmhive.campaign --verify
.\.venv\Scripts\python.exe -m pytest tests/test_cryptoswarmhive.py tests/test_stegohive_reporting_game.py -q -p no:cacheprovider
```

The fixed four-job runner rejects split sizes outside 32–512 and selected-rollout
counts outside 16–128 or beyond holdout. The manifest fixes default counts and
all policy/arm names. The runner writes only this experiment's evidence directory;
verification reads and regenerates every artifact and validates source/output
hashes. This is deterministic same-source replay supplemented by independent
accounting, decoder, information and subgame tests, not an independent simulator
implementation. Completion requires actual generated artifacts, full replay,
tests covering world separation and ledger/game consistency, and an explicit
requirement-to-evidence audit in `COMPLETION_AUDIT.md`.
