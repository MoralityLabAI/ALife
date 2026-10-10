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

## What is measured (one construction check, one substantive claim, one labelled illustration)

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
3. **H3 — warden firewall (capital result + labelled limiting-case illustration).** The
   robust result: a warden reading capital-placement sizes separates a pooled one-pot
   controller from an `M`-pot shared-weights population (capital ROC AUC = 1). The
   complementary claim — that a warden reading only sampled location traces cannot separate
   them (trace ROC AUC = 0.5) — is an **explicit limiting-case construction**, not a measured
   near-miss: the shared-weights arm is *given* the controller's placement (the paper's "same
   weights, no message" focal-point coordination carried to its limit), so identical behaviour
   yields identical traces. A genuine test needs a public signal distinct from pooled private
   views; see "Non-claims" and the paper's limitations.

The thresholds in `manifest.json` are frozen demonstration gates set loosely around the
model's observed behaviour (see `analysis.threshold_note`), not predictions about any
network, and the run is fully deterministic. The verifier **recomputes** the holdout
aggregates (gains, success collapse, ceiling, ROC AUCs) directly from `raw_episodes.jsonl`,
gates them against the frozen thresholds, and cross-checks them against `summary.json`.

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

The trace-indistinguishability half of H3 is a construction, not a measurement: the
shared-weights arm is handed the controller's placement, so of course the traces match.
This is deliberate — it isolates the capital signal as the robust separator — but it means
the experiment does **not** show that a trace warden fails on genuinely distinct
behaviour. A faithful test would give the shared-weights population a public demand signal
distinct from the coalition's pooled private views and measure whether partial observation
alone suppresses the signal; that is left as the registered next step. Relatedly, H1's
saturation is arithmetic on the directable-unit count `Q`, not an empirical surprise.
