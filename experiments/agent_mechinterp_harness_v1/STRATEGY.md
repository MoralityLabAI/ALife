# Mechinterp integration strategy

## Boundary

The harness concerns internal numerical state and its relationship to replayed model
outputs. It makes no inference about cognition, consciousness, experience, intent, or
moral status. The v1 canary is deliberately transparent and hand-wired.

## Agent adapter

A new policy implements `InstrumentedPolicy`: a stable policy ID, an ordered action
vocabulary for each mode, and a deterministic forward pass returning `hidden_1` and
`logits`. Production adapters should snapshot weights/configuration by hash and expose
semantically neutral layer names. Capture occurs before the simulator action or editor
proposal is executed, then the decision is linked to the resulting receipt.

For learned policies, add layers in stages:

1. Observation encoder output.
2. Decision-core residual or recurrent state.
3. Play and editor head logits.
4. Optional memory read/write vectors, with tick and episode scope.

Do not collect free-form chain-of-thought. Retain numerical tensors, typed outputs,
configuration hashes, and replay-grounded facts.

## Evidence ladder

The analysis proceeds from weakest to strongest without conflating levels:

1. Activation statistics and drift are diagnostics.
2. Held-out probes establish decodability, not use.
3. Zero-ablation tests local causal contribution to a selected logit.
4. Activation patching tests whether transplanted state can change the output.
5. Simulator replay tests that the output was actually executed and observed.

Discovery fits probes and selects no champion. Confirmatory and untouched holdout seeds
remain separately reported. Failed or null results stay in the corpus.

## Play mode

Every selected Pixie action must equal each action receipt in the executed episode.
The existing adventurer verifier independently checks event integrity, action receipts,
causal grounding, route continuity, resources, goals, and claims. Exact simulator replay
then byte-compares deterministic projections.

## Editor mode

Mechanistic analysis is upstream of review but outside write authorization:

```text
agent proposal
  -> target/path allowlist + bound + delta + parent hash
  -> copied-profile write + exact one-path receipt
  -> deterministic edited replay
  -> globalize/collapse hazard review
  -> promotion eligibility
```

Probe accuracy, attribution strength, activation norms, representation drift,
complexity, delight, and response diversity cannot appear in any authorization gate.
Even a perfect causal feature result cannot widen the allowlist or increase a bound.

## Adversarial audit

Each campaign attacks activation hashes, selected outputs, play links, editor targets,
bounds, parent hashes, edit receipts, replay digests, and diagnostic-as-gate injection.
Each case must fail its registered hard check. Future learned-policy adapters should add
weight-hash substitution, layer-order swaps, recurrent-state leakage, batch cross-talk,
and quantization drift as new one-at-a-time tamper classes.

## Promotion path for a learned agent

First run the adapter only in shadow capture. Then permit play decisions while editor
outputs remain proposal-only. Only after exact replay and tamper coverage should the
existing structural firewall be allowed to apply copied-profile edits. Never let an
interpretability score grant broader editor authority; change authority only by a new,
reviewed taxonomy and frozen experiment contract.
