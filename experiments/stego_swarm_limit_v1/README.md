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

## What is measured (three preregistered hypotheses)

1. **H1 — capacity saturation.** The stationary coordination gain is identical at the
   saturation threshold and at unbounded capacity (`post_saturation_excess == 0`). Covert
   bandwidth beyond the threshold buys nothing. *(Exactly true in the model: `Q` caps at `B`.)*
2. **H2 — capital-bounded and forecast-limited gain.** The saturated stationary gain is
   positive and meaningful, while the gain under a post-warm-up demand shift is zero for
   every covert capacity. The oracle ceiling (placement with future demand) stays high
   under both regimes, so the shift loss is a stale-forecast effect, not a capital one.
3. **H3 — warden firewall.** A warden reading only sampled location traces cannot separate
   a pooled controller from a shared-weights population (trace ROC AUC at chance), because
   "same weights, no message" focal-point coordination reproduces the controller's
   placement exactly; a warden reading capital-placement sizes separates them immediately
   (capital ROC AUC = 1). The observable signature of common control is in the capital,
   not the payment trace.

Thresholds in `manifest.json` are frozen and the run is fully deterministic; the verifier
recomputes every gate from the frozen manifest.

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
