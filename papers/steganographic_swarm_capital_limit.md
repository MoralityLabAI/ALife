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
Third, the observable signature of common control sits in the capital and not reliably in
the payment trace. We cross information access with account structure in a $2\times2$
factorial over a public-observation sweep: a warden reading capital-placement sizes separates
the account-structure axis (one pot versus $M$ pots) at every rate and independent of
information access, while a warden reading sampled location traces separates the
information-access axis (whether the covert channel pools private views) only to the extent
the channel is valuable — sharply where the public signal is weak and the channel buys a
gain, not at all where it is rich and the channel is worthless — so the channel is never both
valuable and trace-invisible. This is a measured factorial with a stated decentralised
placement rule, not a construction; and when we strengthen the warden — a trained,
member-attributed discriminant scored out of sample — it reads account structure from the
trace too and reads the information axis further down, so the trace-side invisibility is a
property of the warden while the capital signal is warden-independent, which is the durable
half of the result. A live language-model agent, handed
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

To keep the two signals from being confounded — the review that shaped this section noted that
a pooled controller and an independent shared-weights population differ in *both* their
information and their accounting at once — we cross the two axes in a $2\times2$ factorial.
Every agent reacts to a common *public* demand signal observed at a rate $r$, distinct from
any member's private sub-sample. The **information-access** axis is whether a population also
pools its members' private sub-samples over the covert channel (``pooled\_private``, the
public signal fused with the pooled private estimate by inverse-variance weighting) or reacts
to the public signal alone (``public\_only``); this determines the placement, and hence the
trace. The **account-structure** axis is whether the budget is boarded as one pot of $B$
(``one\_pot``) or as $M$ pots of $B/M$ (``m\_pot``); this determines the capital signal and
nothing else. The ``m\_pot`` population places by a *stated decentralised convention*: every
member computes the same target allocation, a deterministic function of the shared public
estimate, and claims the units congruent to its own index modulo $M$ in the target's
canonical ordering. No member observes another's choice, so this is focal-point coordination
on common information and not a covert channel; its union is the shared target. That the
convention is load-bearing, rather than a channel smuggled back in, is shown by a
naive-decentralised arm in which each member instead water-fills its own $B/M$ from the public
signal and the members pile onto the same locations: it delivers about a third of the demand
where the focal placement delivers two thirds.

**Proposition 3 (firewall, regime-aware).** *A warden that observes the sizes of
capital-placement events separates the account-structure axis with certainty in the limit of
observation, because one pot boards $B$ in a single event while $M$ pots board $B/M$ each and
a placement of size $x$ is observed with probability increasing in $x$; this holds at every
public-signal rate and independent of information access. A warden that observes only a
sub-sample of delivered events by location separates the information-access axis to the extent
the two placements differ, which is exactly the value of the covert channel: at a weak public
signal the channel is valuable and the trace is informative, at a strong public signal the
channel is worthless and the trace is at chance.*

The capital clause is a structural result, regime-robust: the one large placement is the ramp
the paper says remains, visible whatever the behaviour, and the factorial shows it reads
account structure and not information access. The trace clause is the measured, and more
interesting, half. Its content is an *impossibility of the convenient case*: the covert
channel is never both valuable and trace-invisible, because its value and its trace footprint
are the same quantity — the gap between the pooled-private placement and the public-only one.
A coalition that wants the channel to buy it something must place differently from what the
public signal alone dictates, and that difference is what the trace warden reads. The two
wardens together give the asymmetry that is the section's claim: the capital signal separates
control structure whatever the regime; the trace signal separates it only where coordinating
was worth doing. A monitor that wants the common-control signal should read the capital and
the registry, not the wire — not because the wire is always
blind, but because the capital is never.

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
- the $2\times2$ warden factorial, gated on seeds pooled over all splits (the per-split trace
  AUC is noisy at the rich public rate), over the finer public-rate sweep
  $\{0.04, 0.08, 0.15, 0.25, 0.45, 0.70, 0.90\}$: the capital-warden ROC AUC on the account
  axis is $1.00$ at every rate, while the trace-warden AUC on the information axis falls from
  $0.96$ at the weakest public rate (channel value $+0.094$) toward chance as the channel value
  falls to $\approx 0$. The trace reads information access only where the channel is valuable;
  the capital reads account structure throughout. The naive-decentralised contrast delivers
  about $0.21$ against the focal placement's $0.62$ at the weak rate, so the decentralised
  convention is doing real work. This is Proposition 3, measured rather than constructed;
- the trained-warden stress test (Section 6.5): a member-attributed linear discriminant fit on
  the discovery and confirmation seeds and scored on the holdout reads the account axis at
  $1.00$ at every rate and the information axis at $0.95$ where the channel is valuable, eroding
  to a weak, noisy signal (mean distance from chance $0.14$) where the channel value is
  $\approx 0$ — a stronger observer than the scalar statistic, which it reads information access
  at smaller channel values than.

All four hypotheses are supported: H1 and H2 as above, H3 as the measured regime-aware
factorial, and H4 as the trained-warden stress test. The verifier recomputes the holdout
aggregates, the pooled warden factorial, and the out-of-sample trained discriminant directly
from the raw episodes, gates them against the frozen thresholds, and cross-checks them against
the summary.

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

## 6.5. A stronger warden, and where the firewall actually holds

The firewall of Section 4 was measured against a trace warden that reads a single
concentration statistic. A natural objection is that a stronger observer would see more, so we
give the warden member attribution — it observes which account served each sampled delivery —
and a trained decision rule: a diagonal linear discriminant fit on the discovery and
confirmation seeds and scored out of sample on the holdout, over the public-rate sweep. Two
things change and one does not. The account axis becomes readable from the trace: with
attribution the discriminant separates one pot from $M$ pots at AUC $1.00$ at every public
rate, because a single holder's deliveries and $M$ holders' deliveries have visibly different
concentration. So the capital signal is not the only route to account structure; it is the
route that does not depend on the warden's strength. The information axis is read further down:
where the scalar statistic was already near chance at a channel value of $0.01$, the trained
attributed warden still reads it at AUC $0.73$, and it reaches only a weak, noisy floor —
mean distance from chance $0.14$, not a clean $0.5$ — where the channel value is $\approx 0$,
a floor consistent with a flexible rule overfitting residual structure on twelve seeds. The
honest conclusion is the asymmetry, not a blanket invisibility: the covert channel's
information contribution is read more sharply, and at smaller values, by a stronger warden,
so the trace-side invisibility is a property of the warden and not of the payment layer;
what is warden-independent is the capital signal, which reads account structure whatever the
observer. A monitor should read the capital because the capital is legible to any warden, not
because the wire is illegible to all of them.

## 7. Limitations

The result is model-only and the model is narrow. Delivery is linear min-unmet against a
single-round service process; the reflected-walk balances and inter-member demand of the
lnmath paper's general case are absent, and with them the $\sqrt N$ regime and the
distinction between agents that can and cannot spend down. The departure process that sets
the hyperedge's group size in the paper is not here at all, so nothing in this model speaks
to the turnover cost that the paper argues, not covert capacity, sets the scale of a
swarm's pooling. The warden model is a genuine $2\times2$ measurement with a stated
decentralised placement rule, a naive-decentralised contrast, and a trained attributed
discriminator (Section 6.5) — but it is still a model: the trained warden is a diagonal
linear discriminant on a small attributed feature set, fit on twelve seeds, so its noisy
near-chance floor at zero channel value is partly overfitting rather than a clean null, and
the public-rate sweep is seven points on one demand family. A higher-capacity warden, more
seeds, and richer attribution would map how far the trace-side signal can be pushed; what we
establish is the direction (the trace signal strengthens with the warden, the capital signal
does not) and not its limit. The covert channel is a scalar with no
content and no codebook, so
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
