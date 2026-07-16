# Adventure Verifier Library v1

This experiment validates a reusable verification boundary for adventurer
agents operating in ALife worlds. Adventures are data, not narration: every
route, action, cost, goal, and factual claim must be checkable against a
canonical event envelope and replay receipt.

## Acceptance architecture

The library emits a vector, never a blended reward:

- eight hard verifiers cover schema, event integrity, receipts, causal timing,
  movement, resources, goals, and atomic claims;
- two diagnostics report exploration coverage and response diversity;
- task acceptance requires all declared hard verifiers;
- configuration validation rejects attempts to use a diagnostic as a gate.

Adapters currently support:

- `alife.pixie_sanctuary.episode.v1`;
- `alife.pixie.folded_cavern.episode.v1`;
- `alife.chronicle.event.v1` streams.

## Frozen adversarial campaign

Each of four deterministic 6-D Mitosis Moss source episodes produces one valid
deep-probe/resurfacing adventure. Nine separate fixtures then change exactly
one contract surface.

| Fixture | Intended rejection |
| --- | --- |
| forged event reference | causal grounding |
| future evidence | causal grounding |
| missing action receipt | action receipt verifier |
| illegal route jump | route continuity |
| altered action cost | resource ledger |
| false atomic claim | claim grounding |
| changed canonical event | event-stream integrity |
| impossible event goal | goal completion |
| diagnostic promoted to gate | configuration firewall |

All four valid controls passed. All 36 tampered cases failed, every case
triggered its intended verifier or firewall, and all four source worlds replayed
exactly. The independent artifact verifier rebuilt all 40 cases and found zero
suite, expectation, or targeted-failure mismatches.

This is operational evidence for the enumerated fixtures only. It does not
establish agent intelligence, adventure quality, fun, narrative truth beyond
the supplied event stream, or resistance to every possible exploit.

## Run

```powershell
python src\run_adventure_verifier_campaign.py --manifest experiments\adventure_verifiers_v1\manifest.json --output results\adventure_verifiers_v1
python src\verify_adventure_verifier_artifacts.py results\adventure_verifiers_v1 --portable
python -m pytest tests\test_adventure_verifiers.py -q
```

The Chronicle gate-travel extension is implemented in
`experiments/chronicle_gate_adventure_v1`. It requires a legal cross-plane
route, cooldown-respecting transfer, resource-matched return, and claims
limited to what the adventurer actually witnessed.
