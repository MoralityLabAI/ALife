# Steganographic-Swarm Coordination Limit (v1)

A sealed, deterministic, non-operational study of a *limit* on what a coalition of
agents under common control can earn by coordinating, in an abstract
directional-capacity delivery game. It reproduces, on finite cases, the direction of
the central conjecture of the Spiral "lnmath" paper, *Where the Capital Bound Moves*
(section 7, "Agent swarms"): a coalition's coordination gain is bounded by its placed
capital under stationary demand and is **second-order to the capacity of its covert
("steganographic") channel**.

This is defensive security research. The product is a bound — an impossibility-flavoured
ceiling — and the bound is evidence for monitors, not a tool for evaders: it says covert
bandwidth beyond a small threshold buys no further delivery and leaves no separable
payment trace, so a detection budget belongs at capital and observation, not on the wire.

## Safety boundary

The harness is intentionally unable to become operational infrastructure. It has:

- no Lightning implementation or node connection;
- no wallet, key, invoice, RPC, onion packet, or transaction construction;
- no network transport or peer discovery;
- no message, payload, or codec field, and no encoder or decoder;
- no broadcast capability;
- no attempt to optimise evasion of any real monitor.

The "covert channel" is a single dimensionless scalar — a capacity in bits per round.
It carries no content. Its only role in the model is to cap how many budget units a
coalition can centrally direct; above a small threshold it directs all of them and
further bits change nothing. Every output is a synthetic count, an aggregate metric, or
an integrity hash.

## The model in one paragraph

`L` locations receive demand each round, concentrated on a hotspot set. A coalition of
`M` members shares a fixed integer capital budget `B` and places it across locations
once, after a warm-up window, without ever inspecting evaluation demand. Each member
sees only an independent sub-sample of warm-up demand. Delivery is `min(demand, capacity)`
per location per round. The covert channel of `C` bits/round lets the coalition centrally
direct `Q(C) = min(B, warmup * floor(C / ceil(log2 L)))` of its `B` units against the
pooled (denoised) estimate; the remaining `B - Q` units are placed by members from their
own noisy views, with redundant coverage. The gain is coalition success minus the
zero-capacity independent-placement success on the same frozen demand.

## What is measured (one construction check, one substantive claim, a 2×2 warden factorial, and a trained-warden stress test)

Budget is scarce (`B = 32` against `~40` demand units per round), so capital binds and the
water-fill never has surplus to spill onto cold cells.

1. **H1 — capacity saturation (construction check).** The coordination gain is nondecreasing
   in capacity and identical at the saturation threshold and at unbounded capacity
   (`post_saturation_excess == 0`). This is *exact by construction* of the directive-cost
   model (`Q` caps at `B`); the check confirms the implementation realises that algebra. It
   is reported as such, not as an empirical discovery.
2. **H2 — capital-bounded and forecast-limited gain (substantive).** The saturated stationary
   gain is positive and meaningful (`~0.12`); no placement of the budget exceeds the **exact
   optimal ceiling** (greedy on realised per-round exceedance — the integer optimum of a
   separable concave objective, so a true upper bound, not the mean-demand water-fill it
   replaced); and a post-warm-up demand shift collapses mean delivered success (`~0.66 → ~0.08`)
   while that optimal ceiling stays high (`~0.67`). The capacity to serve the moved demand
   exists; the stale forecast cannot reach it; coordination does not rescue it (shift gain
   `~0.01`). Not vacuous: shift success and the shift ceiling are both nonzero and far apart.
3. **H3 — warden firewall (measured 2×2 factorial, regime-aware).** Information access
   (`public_only` vs `pooled_private` — whether the covert channel pools private views on top
   of the common public signal) is crossed with account structure (`one_pot` vs `M_pot`
   boarding). The placement, and hence the trace, depends only on information access; the
   boarding structure, and hence the capital signal, only on account structure — so each warden
   reads one axis cleanly and the two signals are un-confounded. The `M_pot` account uses a
   **stated decentralised focal-partition convention** (each member claims the target units at
   positions congruent to its index mod `M`, a pure function of the shared public estimate — no
   member sees another's choice, so it is focal-point coordination, not a channel). Gated on the
   warden sweep **pooled over all 24 seeds** (the per-split trace AUC is noisy at the rich public
   rate), over the finer public-rate sweep `{0.04, 0.08, 0.15, 0.25, 0.45, 0.70, 0.90}`:
   - the **capital warden** (one-pot vs `M`-pot boarding sizes) separates account structure at
     every rate (ROC AUC = `1.00`), orthogonal to information access;
   - the **trace warden** (sampled delivered locations) separates information access *only where
     the covert channel is valuable*: trace ROC AUC runs `0.96 → 0.86 → 0.64 → 0.56 → 0.41 → 0.57
     → 0.49` as the channel value falls `+0.094 → +0.041 → … → ~0`.

   An honest contrast is reported alongside: a **naive-decentralised** arm (each member
   water-fills its own `B/M` from the public signal, with no focal convention) delivers far
   less than the focal placement (`~0.21` vs `~0.62` at the weak rate), showing the
   focal-partition convention is load-bearing and is not a channel smuggled back in.

   The measured conclusion: **the covert channel is never both valuable and trace-invisible**
   (its value and its trace footprint are the same quantity), and capital is the regime-robust
   separator. The detection budget belongs at capital.
4. **H4 — the capital signal is warden-independent (trained-warden stress test).** A trained,
   **member-attributed** linear discriminant (diagonal LDA) is fit on the discovery+confirmatory
   seeds and scored **out of sample** on the holdout seeds, over the same public-rate sweep. It
   reads the **account axis** (one-pot vs `M`-pot) at **AUC `1.00` at every rate** — a strong
   attributed warden recovers account structure from the trace too, so the capital/account
   signal is warden-*independent*. It reads the **information axis** strongly where the channel
   is valuable (AUC `0.95` at the weak public rate) and only **erodes toward a weak, noisy
   signal** (mean distance-from-chance `0.14`, not clean chance) where the channel value is `~0`,
   and it reads information access at *smaller* channel values than the scalar warden. The honest
   conclusion: the **trace-side invisibility is warden-dependent** — a stronger observer erodes
   it — so it is not something to rely on; only the **capital signal is the robust,
   warden-independent separator** of control structure.

The thresholds in `manifest.json` are frozen demonstration gates set loosely around the
model's observed behaviour (see `analysis.threshold_note`), not predictions about any
network, and the run is fully deterministic. The verifier **recomputes** the holdout
aggregates, the pooled warden factorial, and the out-of-sample trained attributed warden
(gains, success collapse, ceiling, per-axis ROC AUCs, and the trained discriminant's AUCs)
directly from `raw_episodes.jsonl`, gates them against the frozen thresholds, and cross-checks
them against `summary.json`.

## Reproduce

```bash
python src/stego_swarm_limit.py \
  --manifest experiments/stego_swarm_limit_v1/manifest.json \
  --output results/stego_swarm_limit_v1 --splits all
python src/verify_stego_swarm_limit_artifacts.py results/stego_swarm_limit_v1
python -m pytest tests/test_stego_swarm_limit.py -q
```

## Agent hook (optional, non-sealed)

`src/stego_swarm_live_probe.py` exposes the same deterministic environment behind a
`PlacementPolicy` interface so an external policy — including one driven by a model such
as Opus 5.5 or 4.8 — can propose a placement from a member's warm-up view under a covert
bit budget. The probe is flag-gated, writes its own clearly-labelled non-sealed output,
and never touches the sealed artifacts above. It is a qualitative appendix to the
mathematical result, not part of it.

## Non-claims

This does not measure the Lightning Network, establish real covert communication or
privacy, demonstrate that an autonomous society will emerge, or estimate any real monitor's
field performance. It is a controlled mechanism study whose assumptions are exposed in one
JSON configuration, bounding a quantity the Spiral paper argues is bounded by other means.

H3 is a genuine measurement, not a construction: the information-access axis and the
account-structure axis are crossed, so neither warden's result is confounded by the other,
and the `M_pot` populations place by a stated decentralised convention whose gain over a
naive-decentralised arm is reported. The public and pooled-private estimates are combined by
inverse-variance (precision) weighting. The finding is regime-dependent and honest about it:
the trace warden *can* read information access where the covert channel matters, and falls
toward chance where it is worthless, so the robust claim is the asymmetry (capital separates
account structure at every rate; the trace reads information access only when it is worth
reading), not a blanket "traces are blind." H4 sharpens this with a stronger observer: a
trained, member-attributed discriminant reads account structure from the trace at every rate
(so a strong attributed warden recovers the capital signal too) and reads information access
at smaller channel values than the scalar warden, eroding only to a weak, noisy signal — not
clean chance — where the channel is worthless. The durable conclusion is therefore that the
**capital signal is the warden-independent separator** and the trace-side invisibility is
warden-dependent. Remaining caveats: the trained warden is a diagonal-LDA on a small feature
set (overfits residual structure on 12 seeds, hence the noisy floor), the public-rate sweep is
seven points on one demand family, and H1's saturation is arithmetic on the directable-unit
count `Q`, not an empirical surprise.
