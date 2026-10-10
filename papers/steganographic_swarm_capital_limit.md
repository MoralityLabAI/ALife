# The Covert Channel Is Second-Order: A Capacity-Saturation Limit on Swarm Coordination

*A sealed, non-operational ALife study, reproducing on finite cases the direction of
section 7 of the Spiral paper* Where the Capital Bound Moves *(the "lnmath" paper).*

## Abstract

A population of agents under common control that wants to earn more than its share from a
capacity-constrained delivery network has three resources it might spend: capital,
forecasting, and whatever it can say to itself over a covert channel the network's wardens
do not read. The lnmath paper argues that the third is second-order to the first two, and
bounds the coalition's gain by its authenticated capital under stationary demand whatever
the capacity of its covert channel. We give that argument a reference model it did not
have, in the form of an abstract directional-capacity delivery game in which the covert
channel is a scalar bit budget with no content, and we witness three things on finite,
frozen, deterministic cases. First, the coalition's coordination gain saturates in
covert-channel capacity: there is a threshold, set by the budget and the warm-up window
and no larger than the bits needed to name the budget's placement, above which further
bandwidth directs no further unit of capital and changes no delivery; this is exact by the
construction of the directive budget, not a surprise. Second, delivery at every capacity is
bounded by an exact optimal capital placement that no allocation of the same budget
exceeds, and the delivered success collapses toward a floor when the demand the placement
forecast moves after placement, while that optimal ceiling stays high under the shift, so
the loss is a forecasting loss and not a capital one, and coordination does not rescue it.
Third, the observable signature of common control sits in the capital and not in the
payment trace: a warden reading capital-placement sizes separates a pooled one-pot
controller from an $M$-pot shared-weights population at once, while a warden reading sampled
location traces cannot separate them — but this last is an explicit limiting-case
construction, in which the shared-weights arm is handed the controller's placement, and not
a measured near-miss on genuinely distinct behaviour. A live language-model agent, handed
the coordinator's view, reaches the achievable coordination gain at saturation and never
exceeds the optimal ceiling, and below saturation can underperform a trivial water-fill by
optimising its coordinated slice without regard to the capital placed independently around
it. Nothing here is measured on a network; the covert channel carries no content, and the
result is a bound, which is evidence for monitors and not a method for evaders.

## 1. Setting

Let there be $L$ abstract locations and a demand process that, each round over a horizon
$T$, delivers $d$ unit demands to locations drawn from a distribution concentrated on a
hotspot set. A coalition of $M$ members holds a fixed integer capital budget $B$, which it
places as per-round capacity across locations once, after a warm-up window of $w$ rounds,
and does not revise; the placement cannot inspect demand after $w$. Delivery at a location
in a round is $\min(\text{demand}, \text{capacity})$, so capacity placed beyond a
location's per-round demand is wasted and capacity short of it loses the shortfall. Each
member observes, during warm-up, an independent sub-sample of demand: it sees each unit
with probability $\nu$, so its observed count at a location is a thinned, noisy copy of the
warm-up truth, and two members disagree on the ranking of locations by exactly as much as
that thinning makes them.

The covert channel is a capacity $C$ in bits per round, and it carries no content. Its only
role is to bound how much of the budget the coalition can direct from a pooled view: a
single placement directive, "put one unit at location $\ell$," costs $\lceil\log_2
L\rceil$ bits, so over the warm-up the channel can agree on
\[
Q(C) \;=\; \min\!\Big(B,\; w\big\lfloor C/\lceil\log_2 L\rceil\big\rfloor\Big)
\]
directed units, placed by water-filling the pooled observation; the remaining $B-Q(C)$
units are placed by the members independently, from their own noisy views, with the
redundant coverage that independence forces. At $C=0$ nothing is directed and the coalition
is $M$ independent placers; as $C\to\infty$, $Q=B$ and the whole budget is placed from the
pooled, denoised view.

Write $s(Q)$ for the coalition's delivered fraction when $Q$ of its units are centrally
directed, and $G(C)=s(Q(C))-s(0)$ for its gain over the uncoordinated baseline on the same
frozen demand.

## 2. The saturation limit

**Proposition 1 (capacity saturation).** *There is a finite $C^\star$, with
$C^\star \le \lceil B/w\rceil\,\lceil\log_2 L\rceil$, such that $Q(C)=B$ for all
$C\ge C^\star$, and therefore $G(C)=G(C^\star)$ for all $C\ge C^\star$. No unit of covert
capacity beyond $C^\star$ changes the placement or the delivery.*

The proposition is immediate from the definition of $Q$: the floor in $Q(C)$ reaches $B$
once $w\lfloor C/\lceil\log_2 L\rceil\rfloor \ge B$, which happens at
$C=\lceil B/w\rceil\lceil\log_2 L\rceil$, and $Q$ is clamped at $B$ above it, so the placed
capacity vector, and hence $s$ and $G$, are constant there. The content of the proposition
is not the arithmetic but what it says about the question: the decision a covert channel
informs — where the budget goes — is a low-entropy object, fully described by $B$
directives, so a channel wide enough to describe it extracts the whole of the coordination
value and a wider one extracts nothing further. This is the sense in which the covert
channel is second-order. It is worth exactly the decision it carries, and the decision is
bounded.

## 3. The capital ceiling and the forecast floor

The saturated gain is not unbounded in the budget either, nor robust to the demand moving.

**Proposition 2 (capital bound and forecast floor).** *For every $C$, $s(Q(C))$ is at most
$s^\star$, the delivery of the fixed per-round capacity vector of $B$ units that maximises
$\sum_t \min(d_t, c)$ against the realised evaluation counts. Because that objective is
separable across locations and concave in each per-location capacity (the marginal of a
unit at a location is the number of rounds whose demand exceeds its current capacity, which
is nonincreasing), the greedy assignment of each unit to the largest current marginal is
the exact integer optimum, so $s^\star$ bounds every placement of the same budget. And if
the hotspot support moves after warm-up to a set on which the warm-up placed little
capacity, the delivered success collapses toward a floor while $s^\star$ stays high, so the
loss is a stale forecast and not a shortage of capital.*

The first clause is the cut bound of the lnmath paper in miniature: delivery is bounded by
placed capacity, and no allocation of a fixed $B$, however informed, beats the concave
optimum $s^\star$ — which an earlier version of this model wrongly identified with a
mean-demand water-fill that the pooled placement could exceed on several seeds; the greedy
exceedance optimum is the real bound and nothing crosses it. The second clause isolates what
coordination is for. The optimal placement, which sees the evaluation demand, stays high
under the shift, so the capacity exists to serve the moved demand; what fails is the
forecast, identical in its failure whether the coalition coordinated its forecast or not.
With a scarce budget ($B$ below the per-round demand) the placer has no surplus to spread
onto the vacated cells, so coordination buys almost nothing under the shift. Coordination
denoises a
forecast; it does not make a stale forecast fresh, and under a shift the denoising has
nothing to act on. The gain a coalition can win is therefore the stationary-placement
effect on its own capital, and it is zero when the placement's one assumption, that demand
stays where it was, fails.

## 4. The warden firewall

The coalition's object is to coordinate while appearing independent. The question is which
observer, if any, the coordination is visible to.

Consider two populations on the same demand. The first is a pooled controller: one budget
$B$, placed by the directed water-fill of Proposition 1 at $C\ge C^\star$. The second is a
shared-weights population: $M$ members with one policy and independent budgets of $B/M$. The
lnmath paper's "same weights, no message" argument is that such members, sharing a policy
and reacting to the same public events, reach the controller's coordinated placement by a
focal-point partition without exchanging a message. We carry that argument to its limit and
*give* the shared-weights arm the controller's placement by construction. The two
populations then differ only in the accounting: one pot of $B$ against $M$ pots of $B/M$.

**Proposition 3 (firewall), with one clause a construction.** *A warden that observes the
sizes of capital-placement events separates the two populations with certainty in the limit
of observation, because the controller boards $B$ in one event and the shared-weights
population boards $M$ events of $B/M$, and a placement of size $x$ is observed with
probability increasing in $x$. A warden that observes only a sub-sample of delivered events
by location cannot separate them — but only because, by the construction above, their
delivered distributions are identical.*

The capital clause is a real, structural result: the one large placement is the ramp the
paper says remains, visible whatever the behaviour. The trace clause is honest only as a
limiting case, and we flag it as such: it holds because we handed the shared-weights arm the
controller's placement, so of course the traces match. It does *not* show that a trace
warden fails on genuinely distinct behaviour. The faithful test — giving the shared-weights
population a public demand signal distinct from the coalition's pooled private views, and
measuring whether partial observation alone suppresses the signal — is not run here, and we
flag it in the limitations; indeed it is in tension with the gain of Section 2, since the
channel is valuable exactly when the public signal is poor, and exactly then the two
populations place differently. The defensible reading is the asymmetric one: the capital
signal is the robust separator, so a monitor that wants the common-control signal should
read the capital and the registry, not the wire.

## 5. Reference-model results

The model is implemented in `src/stego_swarm_limit.py`, with a frozen demonstration
configuration in `experiments/stego_swarm_limit_v1/manifest.json` whose gates are set
loosely around the model's observed behaviour rather than as predictions (the manifest says
so). It runs on $L=24$ locations, $8$ hotspots, $M=12$ members observing at $\nu=0.15$, a
scarce budget $B=32$ against $40$ demand units per round (so capital binds and the
water-fill has no surplus to spill), warm-up $w=24$, horizon $T=120$, and a covert-capacity
sweep $\{0,5,10,20,40,\infty\}$ bits per round, over disjoint discovery, confirmation, and
holdout seed sets. Placement, observation, and the warden's sampling are all seeded, and the
run reproduces bit-for-bit. On the twelve holdout seeds:

- the coordination gain rises with capacity and is flat above the saturation threshold of
  $10$ bits, with the gain at unbounded capacity equal to the gain at saturation to machine
  precision (maximum $|G(\infty)-G(C^\star)|$ across seeds $=0$); this is Proposition 1 and
  is exact by construction of $Q$, not an empirical surprise;
- the mean saturated stationary gain is $0.119$ of delivered demand, with a deterministic
  bootstrap 95% interval of $[0.097, 0.143]$; no placement exceeds the exact optimal
  ceiling; a post-warm-up shift collapses mean delivered success from $0.66$ to $0.08$ while
  the optimal ceiling stays at $0.67$, and the coordination gain under the shift is $0.012$
  (coordination does not rescue the stale forecast); this is Proposition 2;
- the capital-warden ROC AUC for separating the pooled controller from the shared-weights
  population is $1.00$; the trace-warden AUC is $0.50$, which under the construction of
  Section 4 is at chance by construction and not a measured near-miss; this is Proposition 3.

H1 and H2 are supported; H3's capital clause is supported and its trace clause is an
illustrated limiting case. The verifier recomputes the holdout aggregates directly from the
raw episodes, gates them against the frozen thresholds, and cross-checks them against the
summary.

## 6. A live agent at the ceiling

The same environment, behind the policy interface in `src/stego_swarm_live_probe.py`,
was handed to a live language-model agent (Claude Opus 4.8) acting as the coordinator,
given the pooled view and the bit budget and nothing else; the ceiling it is scored against
is the exact optimal placement of Proposition 2, so "does not cross it" is a genuine bound.
At saturation the agent captured the achievable pooled-coordination gain, in full on one
tested seed ($+0.136$, fraction $1.00$) and almost in full on the other ($+0.054$ against
$+0.056$, fraction $0.97$), and it never exceeded the optimal ceiling on any run. Below
saturation, at $24$ directed units, the agent optimised its coordinated slice in isolation —
concentrating it on six hotspots to "deliver $24.0$," leaving two hotspots at zero — and so
doubled the coverage the independently placed remainder already supplied while starving
others, for a net gain of $-0.047$, worse than directing nothing; the trivial water-fill,
which spreads to complement the remainder, did better ($+0.028$). The ceiling is a capital
bound a capable model does not cross; the quality of coordination below the ceiling
is a fragile thing that reasoning about one's own slice can get wrong. The probe is a
non-sealed appendix (`experiments/stego_swarm_limit_v1/LIVE_PROBE.md`) and the agent's
allocation vectors are recorded there for re-scoring.

## 7. Limitations

The result is model-only and the model is narrow. Delivery is linear min-unmet against a
single-round service process; the reflected-walk balances and inter-member demand of the
lnmath paper's general case are absent, and with them the $\sqrt N$ regime and the
distinction between agents that can and cannot spend down. The departure process that sets
the hyperedge's group size in the paper is not here at all, so nothing in this model speaks
to the turnover cost that the paper argues, not covert capacity, sets the scale of a
swarm's pooling. The shared-weights population is given, by construction, the same placement
as the controller, which makes the trace warden's indistinguishability a statement about a
limiting case and not a measured near-miss; a model in which the two populations differ
slightly in behaviour, and a warden with member attribution, would test whether partial
observation alone suppresses a real signal, which is the sharper form of the paper's
preregistration item 7. The covert channel is a scalar with no content and no codebook, so
the capacity-versus-detectability curve the paper reserves for a bounded appendix is not
computed; what is shown is only that the gain the curve would bound is already bounded by
other means. The thresholds in the manifest are chosen to be met by the frozen run and are
a demonstration of direction, not an empirical prediction about any network. Nothing is
measured live, and the covert channel is not a communication system.

## 8. What it is for

The lnmath paper's claim about agent swarms is that the interesting quantity is not what a
population under common control can secretly say but what it can prove and where it stands,
and that a monitor's budget is wasted on the covert channel and well spent on capital and
observation. This reference model is a place to witness that claim and, where it can be
sharpened, to sharpen it: the saturation limit says the covert channel is worth a bounded,
small decision; the capital bound and forecast floor say the gain the decision buys is
bounded by placed capital and by the demand holding still; and the firewall says the signal
a warden wants is in the ramp, not the trace. A defender reads these as a reason to put the
measurement where the structure is. An evader reads them as a reason the covert channel was
never the lever.

## References

- Dugan, P. B., *Where the Capital Bound Moves: Settlement Objects, Proof Economics, and
  Agent Coordination on Bitcoin Payment Networks*, Spiral program, 2026
  (`github.com/patrickdugan/Spiral`), section 7 and preregistration items 7 and 9.
