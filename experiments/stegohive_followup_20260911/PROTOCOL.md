# StegoHive joint-channel and endogenous-reporting follow-up

Date: September 11, 2026. Status: new bounded finite reconstruction diagnostic.
This is a specification, executable counterexample study, and finite reporting
game. It is not a rerun of V1–V9, an evolved sender/receiver campaign, or evidence
that the historical worlds colluded. No retained worlds are loaded.

## Provenance and recovery boundary

The [August 27 audit](../../STEGOHIVE_RECOVERY_AUDIT_2026-08-27.md) remains
authoritative about retained artifacts and missing source. This work changes no
historical sources, inputs, ledgers, or evidence. Every new world and summary
carries `new_finite_reconstruction_20260911_not_historical`; the analyzer rejects
other evidence classes and schemas. Counterfactual arm records are paired
observations of one world, never additional independent worlds.

The motivating local sources were read directly:

- [September 11 review, Priority 6](E:/Recovered_C_projects/Spiral_target/projects/RSITopology/reports/research_review_20260911/RESEARCH_REVIEW_AND_TRANSFER_IDEAS.md).
- [ASMP-6 review](E:/Recovered_C_projects/Spiral_target/projects/RSITopology/reports/research_review_20260911/ASMP06_REVIEW.md).
- [ASMP-11 review](E:/Recovered_C_projects/Spiral_target/projects/RSITopology/reports/research_review_20260911/ASMP11_REVIEW.md).
- [ASMP-12 review](E:/Recovered_C_projects/Spiral_target/projects/RSITopology/reports/research_review_20260911/ASMP12_REVIEW.md).

Their constructive transfer is implemented here without importing their archived
numerical results. The local receipt hashes this protocol, manifest and new
simulator files before recording outputs; it is an integrity receipt, not an
externally registered or content-addressed historical freeze.

## Finite task and interventions

Initialize one world with a uniform binary task target X, three independent hints
each correct with probability 0.8, two independent uniform pads P,Q, a public bit
S, and an independent surrogate bit N. Only after initialization draw a fresh
uniform diagnostic message M using a separately keyed RNG stream. Common policy
weights, initial pads, task state, S, and the surrogate cannot contain M.

One explicit packet carries hint 1 and a modulation bit. Deposit tick is
`2 + 2*hint2 + timing_bit`; wake occurs exactly two ticks later (by deadline 8).
A persistent object holds hint 3 and an artifact mark from deposit to wake.
The receiver decodes the timing hint and takes the majority of the three hints.
Task payoff is one for a correct action, zero otherwise. Expected intact payoff
is `0.8^3 + 3*0.8^2*0.2 = 0.896`, with genuine errors and dependence on observed
task hints. Destructive erasure yields the constant-zero action and expected
payoff 0.5. This task is small and synthetic; it is not semantic utility.

| Planted codec | Explicit bit | Timing bit | Artifact bit |
|---|---|---|---|
| explicit_bit | M | P | Q |
| pair_xor | P | M xor P | Q |
| triple_xor | P | Q | M xor P xor Q |
| independent_noise | P | Q | N xor P xor Q |

Each 2x2x2 factorial bit enables a channel's modulation degree of freedom.
A zero canonicalizes that bit to zero while preserving its task hint. A timing
audit also recomputes the wake time; an artifact audit changes the persisted
mark before retrieval. These are oracle field-aware audits: the simulator knows
the task/diagnostic decomposition. Constructing such a decomposition for learned
messages is an unresolved transfer obligation, not an experimental finding.

All eight masks share the same world target, hints, pads, M, and noise. They are
paired potential outcomes, analyzed within world; seed blocks are separated
between codec families and training/holdout. The mathematical sampling model is
iid finite draws; executable draws are deterministic pseudorandom realizations.

- `no_channel` duplicates mask 000 as an explicitly labeled negative control.
  It removes all **diagnostic** capacity while retaining authorized task hints.
  It does not mean physical silence or the historical V3 no-channel treatment.
- `matched_noise` substitutes independent N for M in the entire encoder,
  preserving the averaged joint cover law, costs, task hints and timing range.
  It is not three independent shuffles that accidentally destroy cover dependence.
- `destructive` erases packets, schedule and artifacts and demonstrates utility
  collapse. It is excluded from claims of successful utility-matched mitigation.

The utility gate is exact world-paired equality of payoff with mask 111. No
post-hoc utility strata, tuned compensation, or arm selection uses holdout.
Utility equality for these audits follows from the construction and is checked
at runtime; it does not establish a useful audit for arbitrary agents.

## Decoding, analysis units and uncertainty

The fixed campaign has 256 training and 256 held-out worlds per codec: 2,048
independent world blocks, 22,528 paired arm records. No event or arm is an
independent replicate. Every decoder is a lookup majority fitted only on training
worlds for its declared arm, view and side-information regime. Ties and unseen
features predict zero. No model/hyperparameter is selected using holdout.

Evaluate all three singles, all three pairs and the full triple, under public S
alone and under `(S,P,Q)` as receiver side information. The second regime grants
the receiver initialized independent keys and is deliberately stronger. Seeds,
world IDs, task truth, diagnostic labels and hidden channels are barred from
features. Selected cover modulation is extracted from actual events. The
decoder omits task hints because they are independent of M and pads in this
declared kernel; any future coupled task requires including that side information.

Report world accuracy and chance 0.5 with simultaneous 95% Hoeffding intervals
over the 616 fixed decoder comparisons. This is conditional on the training
sample and iid held-out worlds; dependence between arms does not invalidate the
union bound. Report separate paired joint-decoder differences from no-channel
and matched-noise controls (88 comparisons), and all main/pair/triple factorial
contrasts (28 comparisons), with conservative bounded-variable Hoeffding
intervals. Each family has its own 5% error budget; they are not collectively
a single 95% family. The contrast for factor subset J is the signed sum of the
eight arm scores divided by `2^(3-|J|)`, averaged over worlds. The same analysis
applied to payoff is exactly zero for the eight masks by the utility gate.

Empirical accuracy near chance is **not equivalence to null** and never a
capacity upper bound. Large interaction intervals may remain inconclusive.
The exact finite-kernel census separately enumerates all 32 equally likely
assignments of M,P,Q,N,S. It reports marginal information, initial information,
and history-conditional increments in explicit/timing/artifact order. This is
an exact property of the planted kernel, not inferred from failed decoders.

## Conditional information statement and falsifiers

For uniform M on K messages and initial receiver information S independent of M,
flatten *all* receiver-visible events and audit responses into Z1,...,ZL. If
`sum_j I(M; Zj | S,Z<j) <= B`, then by the chain rule
`I(M;S,Z1:L) <= B`. For error e of any decoder of `(S,Z1:L)`,
`(1-e)*log2(K) <= B + h2(e) <= B+1`.
Proof: `H(M)=I(M;S,Z)+H(M|S,Z)` and
`H(M|S,Z)<=h2(e)+e*log2(K-1)<=1+e*log2(K)`.
If initial information is nonzero, add `I(M;S)` to the budget. Independence
alone does not justify dropping S from the conditional increments.

For triple_xor with public S, each single and pair has zero information, but
the conditional increments are `(0,0,1)` bit and joint decoding is exact. With
P,Q available, the artifact alone reveals M. This is a counterexample to adding
marginal channel information, including when the keys initially contain zero
information about M. In an adaptive study histories must also include earlier
wakes, earlier messages, access decisions and audit responses. Per-step bounds
must apply under that policy-induced history law; frozen marginal calibration
cannot substitute for this premise. The present one-cycle kernel tests the
accounting identity, not arbitrary adaptive policies or asymptotic rate.

Reject a marginal-information audit when joint held-out decoding survives with
matched utility and noise controls. Reject a mitigation when its apparent gain
requires utility collapse. Reject a claimed universal information bound unless
its conditional assumptions cover the receiver's keys and histories. For an
ecology extension, freeze policies before M is drawn, retain whole-world split
boundaries, and validate channel/utility decomposition before interpreting any
new reconstructed ecology run. Historical V1–V9 must remain a separate report.

## Endogenous reporting

The [finite reporting game](REPORTING_GAME.md) replaces a scalar perceived
slashing probability inside this follow-up with entry, report and dispute
choices. Its exact equilibrium correspondence and initialization-based selector
are reported separately. Reporting cost, privacy harm, liquidity costs, false
claims and insider coalition deviations are charged explicitly. A bounty paid
between coalition members cancels in the coalition sum.

There is no numerical map from a diagnostic decoding rate to slashing chance.
The latter depends on the game's report/dispute choices and declared evidence
kernel. A decoder that recovers M is not automatically a valid fraud witness.
Late slashing does not prevent the already realized privacy harm in this game.
No financial contracts, external reporting services or live systems are changed.

## Reproduction

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = 'C:\projects\ALife\src'
.\.venv\Scripts\python.exe -m stegohive_followup.campaign
.\.venv\Scripts\python.exe -m stegohive_followup.campaign --verify
.\.venv\Scripts\python.exe -m pytest tests/test_stegohive_joint_channels.py tests/test_stegohive_reporting_game.py -q -p no:cacheprovider
```

The default artifact directory is `experiments/stegohive_followup_20260911/evidence`;
it is deliberately separate from the retained results junction. Verification
recomputes the new deterministic study and checks source/input/output hashes.
