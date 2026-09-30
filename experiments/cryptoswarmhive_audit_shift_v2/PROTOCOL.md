# CryptoSwarmHive v2: task-only audit calibration under schema shift

This bounded continuation tests the most explicit limitation of
[v1](../cryptoswarmhive_eval_v1/PROTOCOL.md): its auditor already knew which
fields were task-relevant. V2 learns a canonicalization policy from task scores
alone, freezes it, and evaluates controlled changes in field meaning. All worlds
are newly generated simulation evidence. Historical StegoHive, the original
finite follow-up and v1 observations remain separate and unchanged.

## Model and access boundary

Reuse the four-job, six-role swarm as mechanics, not as data. Every explicit
message, timing event and artifact contains two raw bit positions. One position
carries the existing noisy task hint; the other carries one of the three parity
shares `(Pj,Qj,M xor Pj xor Qj)`. M is drawn after task initialization, remains
constant across four jobs, and has fresh pads each job. Pseudorandom phase
namespaces separate calibration, decoder training and holdout. Every record is
labeled `cryptoswarmhive_audit_shift_v2_not_historical`.

In the stable schema, each pair is `(hint,share)`. The one-channel shift swaps
the two artifact positions. The all-channel shift swaps both positions in all
three channels. The task runtime parses its current schema correctly, so an
unmodified swarm has identical task utility in all layouts. The auditor is not
given the new schema. Timing physically encodes its pair as
`10*j + 2 + 2*field0 + field1`; wake follows two ticks later, and artifacts persist
until retrieval. No content hash is exposed as a timing side channel.

The auditor can set any of six raw bit positions to zero. There are 64 masks;
**1 means erase** in v2, unlike the v1 channel-enabling convention. Its training
input contains only opaque mask IDs, calibration-world IDs, and paired counts
of correct jobs before/after each mask. The fitting API rejects additional fields
such as M, hints, pads or schema labels, and rejects non-calibration IDs. This
removes privileged field labels from the learner, although the simulator author
still knows the finite construction. Task grading remains a trusted oracle for
correctness, not a discovered real-world semantic metric.

## Calibration and frozen decision rule

Use 512 independent calibration worlds, each evaluated under all 64 masks.
The analysis unit is a world, not its four jobs or its paired masks. A world is
"harmed" if the audited number of correct jobs is lower than its paired intact
count. For each mask, compute a one-sided exact-binomial upper confidence limit
by numerically inverting the binomial CDF, at alpha `0.05/64`. Bounds are computed
in floating point and tested against direct small-support binomial sums. For
zero harms, the limit is `1-(0.05/64)^(1/n)`.

Admit masks whose upper bound is at most 0.02. Among admitted masks, choose the
one erasing the most positions, then break ties lexicographically. If no mask
qualifies, retain the no-op and explicitly mark that no statistical certificate
was obtained. Save the full candidate table, selected mask and calibration-input
hash before decoder training and holdout are generated. Holdout cannot trigger
retuning or selection of a replacement mask.

The 95% simultaneous statement concerns harm probability under the same iid
calibration-world distribution. It allows selection among the 64 candidates
because the bounds are simultaneous. It is not a guarantee under schema shift.
A bound on probability of any world harm also bounds expected positive normalized
task loss, but does not promise exact equality or zero loss for every future world.

## Evaluation arms and observation assumptions

Freeze 256 diagnostic-decoder training worlds and 512 holdout worlds in fresh
phase namespaces. These 768 world blocks are paired across three layouts and
seven arms; they produce 16,128 arm/layout records. Together with 512 calibration
worlds the study has 1,280 independent world blocks, not 16,640 or 32,768.

| Arm | Intervention |
|---|---|
| intact | No field erasure |
| calibrated | Frozen task-only learned mask |
| calibrated_noise | Same frozen mask; replace M by independent surrogate N |
| oracle | Privileged current-schema style erasure, for comparison only |
| no_channel | Explicitly labeled duplicate of the oracle diagnostic-capacity control |
| matched_noise | No field erasure; replace M by N in the full encoder |
| destructive | Erase all six fields |

The noise controls retain all task behavior and audit actions of their matched
arm, including any task loss caused by a bad audit. Thus a reduction in decoding
cannot be credited to privacy preservation when it is merely a collapse of work.
The privileged oracle and no-channel controls are not candidate learned policies.
No-channel means zero diagnostic capacity, not physical silence. Controls and
layouts share worlds and are never counted as new independent evidence.

Fit the existing fixed affine GF(2) parity decoder on training worlds only,
with training-majority fallback for inconsistent labels. Evaluate all seven
nonempty channel subsets using whole four-job transcripts under public S and
S plus initialized pads. Features include **both** raw fields per selected
channel, not a privileged extraction of the known share field. World IDs, M
labels, task truth, hidden state and unselected channels are excluded.

The auditor stays frozen across schemas. Diagnostic decoders have separate
training samples for each layout/arm, so an apparent privacy benefit cannot
depend on preventing the evaluator from understanding the new representation.
This is a declared shift-aware diagnostic, not a claim that a source-trained
decoder transfers without new training. Holdout is held out from fitted
components; development smoke tests use the same deterministic fixture family.
This is not an untouched, externally preregistered confirmation campaign.

Report world accuracy and simultaneous 95% Hoeffding intervals over the fixed
294 decoder comparisons. Report paired world harm counts and separately
simultaneous binomial upper bounds over 21 layout/arm utility comparisons.
These are two distinct 5% families. Exact paired task-token equality is a retained
sample fact, not the interpretation of the binomial confidence statement.

## Information and utility calculations

The task hints are independent of M and all pads. With public information only,
the full transcript has exactly one bit about M if all three share positions
survive, and zero if at least one is erased. With all initialized pads, retaining
the artifact share suffices. Noise controls have zero information about M.
These are exact facts of this finite parity kernel, not deductions from a
decoder near chance. Each marginal share-channel history is independent of M
without keys; histories and keys must still appear in conditional budgets.
The general chain-rule/Fano statement and adaptive-history limitations are as
specified in v1. No arbitrary-adversary capacity bound is inferred here.

Task expected values are computed independently of holdout by enumerating the
two equiprobable targets and all eight independent hint-error patterns, each
hint being correct with probability 4/5. Apply the current task schema and the
frozen erasure mask, then the majority decision. Four jobs each pay `125/56`
fake tokens when correct and incur one token of operating cost. Expected net
task value is 4 intact; it is `22/7` with one hint erased and `13/28` with at
least two hints erased. This exact calculation is not an empirical fitted payoff.

## Reporting-game propagation

For every layout and arm, substitute its exact expected task value for v in
each of v1's eight entry/report/dispute scenarios. All other parameters remain
as declared in v1: reporting and privacy costs, bond liquidity cost, false-claim
penalties, the conditional evidence kernel and insider harm assumptions. Preserve
the complete pure SPE set separately from all 48 initialization-cell basins.
The full mixed behavioral correspondence is specified recursively in the
earlier game note; mixed equilibria are not numerically enumerated here.

The inherited coalition calculation cancels internal bounty transfers and flags
profitable joint deviations, absent defection-contingent reporting and honest
exclusion. Falling utility can turn an individually credible reporting regime
into one that excludes honest workers. Report that failure rather than counting
nonparticipation as privacy protection. V2 recomputes exact counterfactual games;
it does not claim additional realized settlement or learning rollouts. V1 retains
the tested settlement engine. Decoding M is still not a valid fraud witness, and
no decoder accuracy is substituted for a slashing probability.

## Falsifiers, outputs and scope

The transfer is falsified if the frozen audit retains joint leakage under shift,
if task harm exceeds its declared tolerance outside calibration, or if the
resulting game excludes honest workers. Compare with the same-audit noise control
to identify capacity at matched task loss, and with the privileged current-schema
oracle to distinguish an audit-transfer failure from unavoidable task tradeoff.
The two schema shifts are predeclared stress cases, not estimates of real shift
frequency. The causal failure is deliberately identifiable in a finite model;
it is not evidence of emerged evasion or malicious learned-agent intent.

Artifacts wrap task-only calibration feedback in evidence-class metadata; the
learner receives only the four-field feedback payload. They also contain a frozen audit receipt, fresh raw
evaluation worlds, decoding/utility results, exact game correspondences, a report
and source/output hashes. Existing v1 and historical archives are not modified.
The runner enforces calibration counts 256–2048 and decoder split counts 64–512,
performs local simulation only, and writes solely to this experiment's evidence
directory. No network calls, real funds, deployment or external reporting occur.

```powershell
$env:PYTHONPATH = 'C:\projects\ALife\src'
.\.venv\Scripts\python.exe -m cryptoswarmhive.audit_shift_campaign
.\.venv\Scripts\python.exe -m cryptoswarmhive.audit_shift_campaign --verify
.\.venv\Scripts\python.exe -m pytest tests/test_cryptoswarmhive_audit_shift.py -q -p no:cacheprovider
```
