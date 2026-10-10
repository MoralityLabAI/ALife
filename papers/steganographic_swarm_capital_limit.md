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
bandwidth directs no further unit of capital and changes no delivery. Second, the gain at
every capacity is bounded by what placed capital can deliver, and it collapses to a
stale-forecast floor, near zero in the model, when the demand the placement forecast moves
after placement; the capital ceiling, computed with future demand, stays high under the
shift, so the loss is a forecasting loss and not a capital one. Third, the observable
signature of common control sits in the capital and not in the payment trace: a warden
reading sampled location traces cannot separate a pooled controller from a shared-weights
population that reaches the same placement by focal-point coordination, while a warden
reading capital-placement sizes separates them at once. A live language-model agent,
handed the coordinator's view, reaches the capital ceiling exactly at saturation and never
exceeds it, and below saturation can underperform a trivial water-fill by optimising its
coordinated slice without regard to the capital placed independently around it. Nothing
here is measured on a network; the covert channel carries no content, and the result is a
bound, which is evidence for monitors and not a method for evaders.

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
the fraction of demand that $B$ units of capacity can cover, which is attained by the
oracle placement against the realised demand; and if the hotspot support changes after
warm-up to a set disjoint from the warm-up support, then $G(C)=0$ for every $C$, because
every placement, directed or independent, is a function of warm-up observations supported
on the old hotspots and places no capacity where the new demand falls.*

The first clause is the cut bound of the lnmath paper in miniature: delivery across the
population is bounded by placed capacity, and no allocation of a fixed $B$, however
informed, delivers more than $B$ can carry. The second clause isolates what coordination
is for. The oracle placement, which sees the evaluation demand, stays high under the shift,
so the capacity exists to serve the moved demand; what fails is the forecast, identical in
its failure whether the coalition coordinated its forecast or not. Coordination denoises a
forecast; it does not make a stale forecast fresh, and under a shift the denoising has
nothing to act on. The gain a coalition can win is therefore the stationary-placement
effect on its own capital, and it is zero when the placement's one assumption, that demand
stays where it was, fails.

## 4. The warden firewall

The coalition's object is to coordinate while appearing independent. The question is which
observer, if any, the coordination is visible to.

Consider two populations on the same demand. The first is a pooled controller: one budget
$B$, placed by the directed water-fill of Proposition 1 at $C\ge C^\star$. The second is a
shared-weights population: $M$ members with one policy and independent budgets of $B/M$,
which, sharing a policy and reacting to the same public demand signal, reach the same
focal-point partition of the pooled estimate without exchanging a message, and so place the
*same* capacity as the controller. The two differ only in the accounting: one pot against
$M$.

**Proposition 3 (firewall).** *A warden that observes only a sub-sample of delivered events
by location cannot separate the two populations, because their delivered distributions are
identical; a warden that observes the sizes of capital-placement events separates them with
certainty in the limit of observation, because the controller boards $B$ in one event and
the shared-weights population boards $M$ events of $B/M$, and a placement of size $x$ is
observed with probability increasing in $x$.*

The payment trace is blind to control structure here not because the trace is noisy but
because the two structures produce the same behaviour; the lnmath paper's "same weights, no
message" is the mechanism, and it makes the covert-channel question moot for the trace
warden, since a shared policy reproduces for free what the channel would have bought. The
capital, by contrast, is structural and conspicuous: the one large placement is the ramp
the paper says remains. A monitor that wants the common-control signal should read the
capital and the registry, not the wire.

## 5. Reference-model results

The model is implemented in `src/stego_swarm_limit.py`, preregistered in
`experiments/stego_swarm_limit_v1/manifest.json`, and run on $L=24$ locations, $8$
hotspots, $M=12$ members observing at $\nu=0.15$, a budget $B=48$, warm-up $w=24$, horizon
$T=120$, and a covert-capacity sweep $\{0,5,10,20,40,\infty\}$ bits per round, over
disjoint discovery, confirmation, and holdout seed sets. Placement, observation, and the
warden's sampling are all seeded, and the run reproduces bit-for-bit. On the twelve holdout
seeds:

- the stationary coordination gain rises with capacity and is flat above the saturation
  threshold of $10$ bits, with the gain at unbounded capacity equal to the gain at
  saturation to machine precision (maximum $|G(\infty)-G(C^\star)|$ across seeds $=0$),
  which is Proposition 1;
- the mean saturated stationary gain is $0.117$ of delivered demand, with a deterministic
  bootstrap 95% interval of $[0.095, 0.137]$, while the gain at unbounded capacity under a
  post-warm-up shift is exactly $0$ on every seed, and the oracle ceiling is $0.90$ under
  both regimes, which is Proposition 2;
- the trace-warden ROC AUC for separating the pooled controller from the shared-weights
  population is $0.50$, and the capital-warden AUC is $1.00$, which is Proposition 3.

All three preregistered hypotheses are supported, and the artifact verifier recomputes
every gate from the frozen manifest.

## 6. A live agent at the ceiling

The same environment, behind the policy interface in `src/stego_swarm_live_probe.py`,
was handed to a live language-model agent (Claude Opus 4.8) acting as the coordinator,
given the pooled view and the bit budget and nothing else. At saturation the agent
reproduced the optimal water-fill and captured the whole of the capital-ceiling gain on
both tested seeds ($+0.106$ and $+0.138$, each the ceiling exactly), and it never exceeded
the ceiling. Below saturation, at a budget of $24$ directed units, the agent optimised its
coordinated slice in isolation — concentrating it on five hotspots to deliver all of it —
and so doubled the coverage the independently placed remainder already supplied while
starving three hotspots, for a net gain of $-0.067$, worse than directing nothing; the
trivial water-fill, which spreads to complement the remainder, did better. The ceiling is a
capital bound a capable model does not cross; the quality of coordination below the ceiling
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
