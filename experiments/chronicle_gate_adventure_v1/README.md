# Chronicle Gate Adventure v1

This fixture campaign extends the adventure-verifier library across Chronicle
planes.  A valid adventurer follows a successful gate from `GENESIS` to a
seed-selected second plane, witnesses a meme attachment and subsequent insight
drift, waits out the applicable route, and returns through a second successful
gate with an exactly re-derived resource balance.

The terms `meme` and `insight` name explicit simulator states and transitions.
They are not claims that an entity believes, understands, or experiences them.

## Hard contract

The original eight hard verifiers still check schemas, event integrity, action
receipts, causality, route continuity, resources, goals, and atomic facts. Two
new hard verifiers close the Chronicle-specific gaps:

- `witness_scope` rejects a true event fact if the adventurer did not observe
  its evidence, or claims it before the observation entered the trace;
- `gate_travel` re-derives the plane chain, source and target coordinates,
  anchor identity, zero pre-transfer cooldown, positive post-transfer cooldown,
  active-cooldown rejection, minimum transfer count, and required return.

The reference trace spends two focus and one waystone on each leg. Its final
zero balance is re-derived by the ordinary resource verifier.

## Frozen fixture campaign

Four independently seeded Chronicle streams cover one discovery seed, two
confirmatory seeds, and one untouched holdout seed. Each source stream contains:

- two successful gate transfers forming a round trip;
- one attempted reuse rejected with `cooldown_before = 1`;
- one `meme_attachment` event;
- one causally subsequent `insight_drift` event.

Every source is rebuilt twice before its cases run. The campaign then retains
one valid control and nine one-at-a-time tamper classes per seed.

| Fixture | Intended rejection |
| --- | --- |
| unwitnessed cultural fact | `witness_scope` |
| claim made before its observation | `witness_scope` |
| forged return target plane | `gate_travel` |
| successful transfer with active cooldown | `gate_travel` |
| missing return leg | `gate_travel` |
| altered waystone cost | `resource_ledger` |
| false meme-pressure value | `claim_grounding` |
| changed canonical event | `event_stream_integrity` |
| diagnostic promoted to gate | configuration firewall |

All four valid controls passed. All 36 tampered cases failed, and every case
triggered its intended verifier or firewall. The independent portable verifier
replayed every source and reconstructed all 40 cases with zero mismatches.

## Knowledge card

### Observed

- 4/4 valid round trips accepted.
- 36/36 tampered traces rejected.
- 36/36 tampered traces triggered their registered target.
- 4/4 source Chronicle streams replayed exactly.
- All streams met the transfer, cooldown-rejection, meme, and insight exposure
  requirements.

### Inferred

Within the enumerated fixtures, the library can distinguish a valid Chronicle
round trip from forged gate state and can distinguish an event that is true in
the world from one the adventurer was entitled to claim it witnessed.

### Not supported

This does not establish adventurer competence, fun, narrative quality, general
security, natural meme evolution, cognition, or robustness to tamper classes
outside the frozen matrix. The source streams are deterministic fixtures, not
samples from the native stochastic frequency of gate round trips.

### Robustness and confounds

The same contract passes both `FORGE` and `ECHOSPHERE` destinations and a fresh
holdout seed. It has not yet been tested on a naturally occurring multi-tick
round trip extracted from a production Chronicle corpus. Chronicle gate events
are treated as environmental travel receipts; there is not yet an independent
player-action event type in the simulator.

### Artifacts and replay

Artifacts live under the ignored `results` junction on `D:`. Reproduce and
verify them with:

```powershell
python src\run_chronicle_gate_adventure_campaign.py --manifest experiments\chronicle_gate_adventure_v1\manifest.json --output results\chronicle_gate_adventure_v1
python src\verify_chronicle_gate_adventure_artifacts.py results\chronicle_gate_adventure_v1 --portable
```

### Next experiment

Mine production Chronicle episodes for naturally connected gate-return paths.
Freeze a route-selection rule on discovery episodes, then test whether the same
verifiers accept complete paths and reject withheld-event or cooldown tampering
on fresh corpus episodes without fixture-authored exposure.
