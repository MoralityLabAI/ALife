# Finite endogenous reporting diagnostic — 2026-09-11

This is a new synthetic finite-game reconstruction motivated by ASMP-12 and
Priority 6 of RSITopology's September 11 review. It uses zero retained worlds,
does not estimate historical StegoHive behavior, and does not modify the
exogenous participation quote in another project or any live system. Its
outputs are separate from retained historical evidence and from the companion
channel reconstruction. There are no statistical replicates in this game census.

## Frozen game and information

Two risk-neutral players, entrant E and reporter R, know all parameters and
observe the entire action history. At time 0, E chooses out, honest entry, or
defecting entry. Out ends the game with both utilities zero. Entry posts bond
`b` and incurs liquidity cost `l*b` regardless of later reporting. Honest entry
has gross value `v`; defection adds private gain `g` and imposes harm `w` on R.
These are cardinal utilities with no wealth constraints beyond the liquidity
charge; honest exclusion means honest continuation utility is strictly below
the outside option, including for an honest-only entrant.

After observing the true entry action, R chooses quiet or report. A report costs
`c+h` (reporting effort and reporter privacy harm). E then chooses accept or
dispute. Acceptance settles the claim automatically, including a false claim.
Dispute costs E `d`, after which an exogenous verification chance accepts a
true claim with probability `q_D` or a false claim with probability `q_H`.
These are conditional verifier accuracies, **not** exogenous reporting or slash
probabilities. Chance is integrated out exactly. Both players know the action,
but settlement can be imperfect. Reporting and dispute strategies are endogenous.

On an accepted claim E loses `b`, R receives `r*b`, and the remaining
`(1-r)*b` exits the two-player system. On a rejected false claim R additionally
pays false-claim penalty `f` to outsiders. A rejected true claim incurs no
false-claim penalty. Undisbursed principal is returned at settlement, so it is
not double-counted as a cost. There is no recovery of `c`, `h`, or `d`.
R has no participation fee and can always remain quiet. No independent auditor,
hidden type, repeated interaction, budget constraint, or external reporter is
present; these limitations make insider coalitions especially powerful.

For entry action `a`, let `G_a=v-l*b+g*1[a=D]`. Quiet payoffs are
`(G_a, -w*1[a=D])`. Under reporting and dispute choice `x`, let `q=1` for
acceptance, otherwise `q=q_a`. Expected payoffs are

```
U_E = G_a - q*b - d*1[x=dispute]
U_R = -w*1[a=D] + q*r*b - c - h - (1-q)*f*1[a=H].
```

Thus reporting is optimal exactly when the increment
`q*r*b-c-h-(1-q)*f*1[a=H]` is nonnegative, with equality retained as a tie.
The joint slash probability conditional on defection is obtained from the
report/dispute policy, not by multiplying marginal empirical rates. In a pure
policy it is zero for quiet, otherwise the appropriate conditional acceptance
probability. No claims are made about access probabilities or field calibration.

## Equilibrium set versus selected outcomes

`pure_spe(p)` returns the complete **pure subgame-perfect equilibrium** set of
this finite game. Each strategy specifies entry and both off-path reporting and
dispute decisions. At each dispute node E maximizes expected utility; at each
report node R maximizes against that continuation; at the root E maximizes
among out and both entry continuations. All exact ties are retained. The
one-step deviation principle proves completeness for these pure strategies:
every subgame is a finite perfect-information tree, and each retained action
is optimal against its selected continuation. Tests independently check all
48 full strategy profiles against every local deviation over 27 parameter cells.
All arithmetic and comparisons are rational, without tolerance-based ties.

Numerical JSON enumerates pure SPE only; it does **not** claim to enumerate
all Nash equilibria or mixed SPE. A full behavioral SPE correspondence is
nevertheless specified recursively: at each terminal dispute node choose any
distribution supported on E's maximizing actions; integrate that distribution
to obtain each reporter continuation value, then choose any distribution
supported on R's maximizing actions; integrate both continuations and choose
any distribution supported on E's maximizing root actions. Take the union over
all such continuation distributions. Backward induction and local optimality
give exactly the behavioral SPE set. Ties allow continuous simplexes locally;
upstream best-response regions depend on the actual continuation probabilities.
It is incorrect to identify this correspondence with an unconditional convex
hull of the enumerated pure profiles.

Selection is a separate, declared algorithm: initialize at each of the 48 pure
strategy profiles, update all dispute nodes, then all report nodes, then entry.
At each update retain an incumbent best response; otherwise use the first
maximizer in the fixed orders accept/dispute, quiet/report, out/honest/defect.
One reverse-depth sweep reaches a pure SPE and a second changes nothing.
This is exact backward-induction selection with initialization-dependent tie
inertia, **not** a claim about decentralized learning or field frequencies.
The JSON lists every initialization in each selected basin separately from
the equilibrium set. Uniform counting measures finite cells, not a prior over
people or an empirical attraction rate.

## Coalition accounting and failure criteria

The coalition is E+R with transferable utility and enforceable ex ante joint
commitment. Enumerate every entry/report/dispute path and compare joint utility
to the selected outcome. If a joint improvement exists, unrestricted side
payments can make both members better off. This is an exact joint-deviation
test for the stated commitment class; it is not a computation of coalition-proof
equilibrium without binding agreements. It includes deviation to quiet defection
and coordinated false reports. The audit reports the maximum joint gain and all
maximizing paths, even when they are individually noncredible without commitment.

The accounting identity under a report is

```
U_E + U_R = G_a - w*1[a=D] - q*(1-r)*b
            - d*1[x=dispute] - c - h - (1-q)*f*1[a=H].
```

The bounty `q*r*b` is an internal transfer and cancels against the corresponding
part of E's slash. Varying `r` can still change joint payoff because it changes
the amount sent to outsiders; cancellation does not imply independence from
`r`. At `r=1` the entire principal transfer cancels and real costs remain.
With no reporter defection harm (`w=0`) and positive gain, an E+R coalition can
often suppress all reporting and keep `g`; a bond alone cannot prevent this
in the declared model. The protected case assumes R internalizes enough harm
to make joint defection unprofitable; it is an assumption, not a general solution.

Each equilibrium records on-path reporting and the counterfactual response to
defection separately. Silence on an honest path alone is compatible with a
credible deterrent. Failure flags mark absent defection-contingent reporting,
profitable coalition deviation, negative honest continuation payoff, and selected
defection. Honest payoff exactly zero is marked as a participation tie; selected
exit is recorded separately. A game may fail even when the entrant individually
complies. The exogenous comparator `g-b*p_perceived<=0` is reported separately
and intentionally omits reporting incentives, dispute costs, and participation.

## Bounded scenarios and expected results

Default values are `b=10, v=4, g=6, l=0.1, c=h=d=1, f=3, r=0.5,
q_D=1, q_H=0, w=0, p_perceived=1`; each row changes only the named parameters.
The exogenous comparator labels every scenario weakly deterrent.

| Scenario | Change | Pure SPE entry outcomes | Diagnostic |
|---|---|---|---|
| Credible individual threat | Defaults | Honest | Reports after defection; insider coalition gains 6 by quiet defection |
| Reporting cost | `c=6` | Defect | No reporting policy despite comparator margin -4 |
| Privacy harm | `h=6` | Defect | Privacy costs eliminate reporting |
| Liquidity exclusion | `l=0.5` | Out | Honest continuation -1; reporting threat still credible |
| False-claim extortion | `d=12` | Out | Honest entrants accept false claims; honest continuation -7 |
| Credible false-claim dispute | `f=20` | Honest | False claims rejected; insider collusion still profitable |
| Reporting/entry indifference | `v=1,g=10,c=4` | Four pure SPE: quiet/defect or report with out/honest/defect | Initial cell basin counts 24, 8, 8, 8; continuous behavioral ties also exist |
| Coalition internalizes harm | `w=8` | Honest | No profitable E+R deviation; does not generalize to outsiders bearing harm |

All other scenarios have one pure SPE selected from all 48 initial strategy
cells. These values are synthetic counterexamples and finite checks, not
calibrated estimates, evidence from retained campaigns, or deployment advice.

## API and verification

`stegohive_followup.reporting_game.run_study()` returns a JSON-serializable
object with evidence labeling, exact parameter strings, exogenous baseline,
complete pure SPE records, conditional slash probabilities, failure flags,
coalition gains, and separate initialization basins. It does no file I/O.
`analyze(Parameters(...))` permits additional bounded cases.

Run from the repository with `PYTHONPATH` pointing to `src`:

```
python -m pytest tests/test_stegohive_reporting_game.py -q -p no:cacheprovider
```

The tests check independent exhaustive subgame optimality, selector membership
and fixed points, exact bounty cancellation, false-claim penalties, reporting
silence, coalition deviations, liquidity exclusion, all tie basins, JSON
serialization, and parameter-domain validation. No historical records are read.

Source context: repository `STEGOHIVE_RECOVERY_AUDIT_2026-08-27.md`;
`E:/Recovered_C_projects/Spiral_target/projects/RSITopology/reports/research_review_20260911/ASMP12_REVIEW.md`
and Priority 6 in its companion `RESEARCH_REVIEW_AND_TRANSFER_IDEAS.md`.
