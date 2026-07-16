# ALife Lab

Experimental artificial life sandbox inspired by Conway's Game of Life, extended with:

- Multi-plane cellular dynamics (GENESIS / FORGE / ECHOSPHERE / MIRAGE).
- Shape-triggered gateways between planes.
- Manufacturable, evolvable, and interacting cell types.
- Additional mechanics for shard hazards, echo blooms, norn-making, and brood expansion.
- Non-UI, step-by-step terminal simulation.

## Run

```bash
python src/alife.py --steps 200 --width 60 --height 28 --seed 42 --render --plane GENESIS
```

Run the local player/builder co-design league:

```bash
python src/player_builder_lab.py --rounds 3 --episodes 2 --steps 80 --candidates 4 --output results/player_builder_latest.json
```

The league is sequential and CPU-only. Three builders propose policy mutations;
three player personas rank every candidate on shared seeds. The winning policy
becomes the parent for the next round. CLI hard limits prevent accidental large
grids or unbounded episode batches.

Compare scalar selection against replicated multi-axis knowledge coverage:

    python src/knowledge_campaign.py --output results/knowledge_campaign_latest.json

This campaign separates training and holdout seeds and reports viability,
diversity, dynamics, social organization, epistemic activity, generativity, and
hazard as distinct axes. Treat its output as exploratory until a frozen causal
or predictive protocol confirms a specific claim.

`--render` prints an ASCII view of the chosen plane each tick.
For faster experiments, omit `--render` and watch aggregate counts every `--tick-interval` turns.

```bash
python src/alife.py --steps 200 --width 60 --height 28 --seed 42 --plane FORGE --tick-interval 20 --events
```

Run compact batches with aggregate summaries:

```bash
python src/run_batch.py --batch 10 --steps 120 --seed-base 2026 --summary --output results/run_batch.jsonl
```

## Chronicle corpus

The chronicle subsystem emits deterministic gameplay facts, legends-mode
compilations, and narration-ready SFT records with `narration: null`. It makes
no model/API calls. Every SFT fact cites event sequences and is re-derived by
the verifier; complexity, delight, gate flux, and coverage remain diagnostics,
never acceptance gates. Chronicle data does not modify the ontology registry.

Run a bounded campaign and verify sampled episodes:

```bash
python src/chronicle/campaign.py --episodes 20 --steps 8 --max-cells-per-world 4096 --output results/chronicle_smoke
python src/chronicle/verify_chronicle.py results/chronicle_smoke --sample 20
```

Use `--portable` after relocating a corpus. The production PowerShell runner
requires `results` to target `D:` and creates 500 episodes plus a dated ZIP:

```powershell
powershell -File scripts/run_chronicle_overnight.ps1
```

The frozen generator contract is
`experiments/chronicle_v1/manifest.json`. Event, legends, SFT, replay, and
verification records use versioned `alife.chronicle.*.v1` schemas.

## Mechanics added

- `norn_maker` creates nearby `norn` when energy and timing align.
- `drone_mother` creates brood (`egg` or `drone`) in local space.
- `echo` can bloom into nearby empty cells.
- `shard` emits local damage and occasional culling to nearby organisms.
- `norn`/`norn_maker` provide nurturing bonus to neighbors.
- `goblin` species are now modeled as sublineages (`wild`, `lover`, `rager`, `sage`, `weaver`) with different social and cognitive biases.
- `goblin` infiltrates by feeding on nearby cells, occasionally converting weak prey into more `goblin`.
- `goblin` can enter a love frenzy (`goblin_loves`): nearby goblins may become emotionally linked, increasing feeding attempts and conversion aggressiveness for a short period (`goblin_rages`).
- `goblin` pairings (`goblin_romances`, `goblin_pairs`) trigger meme/insight spillovers and can create localized innovation surges.
- Pairing now reacts to local memory and prediction: cache/model neighborhoods can produce `cache_courtships`, `prediction_swerves`, and `memory_recruitments`.
- Gate anchors can be put on cooldown after transfer, preventing immediate repeats.
- `meme` is a memetic pressure layer (not a sentient agent): it can broadcast to nearby empties, attach to goblins, and induce ideological drift into `insight`.

## Complexity Harness (Doctor Manhattan Project)

Each tick now computes:

- `kind_entropy`
- `plane_entropy`
- `volatility`
- `growth`
- `gate_flux`
- `complexity` (combined score from the above)

`run_batch.py` now reports:

- `avg_complexity`
- `peak_complexity`
- `delight` (exploration proxy: complexity + gate activity + plane diversity)
- `dominant_plane` for each run

Example:

```bash
python src/run_batch.py --batch 20 --steps 200 --seed-base 2026 --summary --output results/final_batch.jsonl
```

Output JSONL has:

- `complexity` block
- `delight` scalar
- `dominant_plane`
- `goblin_events_last_tick`
- `goblin_events_total` (episode cumulative)
- `goblin_events_per_step` (episode normalized)
- regular final totals and event counts

## Planes

- `GENESIS`: Baseline stable dynamics with moderate mutation.
- `FORGE`: Higher stability, stronger manufacturing, norn-maker bias.
- `ECHOSPHERE`: High drift, high mutation, strong echo behavior.
- `MIRAGE`: Chaotic regime with volatile rules and unstable echo/shard feedback.

## Next experiments

- Add policy knobs (mutation pressure, gate acceptance, norn bias) so LLM agents can learn and control environment dynamics.
- Add a true policy loop where a model emits a parameter vector and receives `delight` as reward.
- Add structured output for per-step trajectories if you want self-play replay support.

## Emergence and Adaptive Pressure Track

The active research contract is [GOAL.md](GOAL.md). The first completed control
separates lattice dimension from neighborhood degree and asks when a one-step
density-only binomial mean-field model becomes adequate.

Validate and run the frozen campaign:

```powershell
python C:\Users\patri\.codex\skills\alife-knowledge-experiments\scripts\validate_manifest.py experiments\geometry_averaging_v1\manifest.json --check-paths
python src\geometry_averaging_experiment.py --manifest experiments\geometry_averaging_v1\manifest.json --output results\geometry_averaging_v1 --splits all
python src\verify_geometry_averaging_artifacts.py results\geometry_averaging_v1
```

`results` is a junction to `D:\ALife\project_results`, so bulk artifacts do
not consume the constrained C drive. The v1 campaign retains 144 independent
episodes: 32 discovery, 48 confirmatory, and 64 holdout. Read
`results/geometry_averaging_v1/knowledge_card.md` before interpreting its phase
map. In particular, zero-error extinction is separated from nontrivial active-
regime evidence, and the initial hypothesis that increasing degree explains
most of the dimension trend was not supported.

Run and verify the vector-state bounded-degree graph laboratory:

```powershell
python src\graph_state_lab.py --manifest experiments\graph_state_v1\manifest.json --output results\graph_state_v1 --splits all
python src\verify_graph_state_artifacts.py results\graph_state_v1
python src\graph_state_lab.py --manifest experiments\graph_state_v2_confirmation\manifest.json --output results\graph_state_v2_confirmation --splits all
python src\verify_graph_state_artifacts.py results\graph_state_v2_confirmation
```

V1 identified normalized-Laplacian spectral gap as a candidate predictor of
single-node perturbation recovery. V2 evaluated the frozen v1 coefficients on
unseen degrees, dimensions, couplings, sizes, seeds, and a fourth regular
topology. The spectral model improved RMSE by 12.30% versus a registered 5%
gate, so the narrow model-only predictor is recorded in
`registries/ontology_registry.json`. The stronger claim that every higher-gap
topology recovers faster failed its 80% direction-consistency gate.

Run and verify the hidden-oracle discovery curriculum:

```powershell
python src\discovery_curriculum.py --manifest experiments\discovery_curriculum_v1\manifest.json --output results\discovery_curriculum_v1 --splits all
python src\verify_discovery_curriculum_artifacts.py results\discovery_curriculum_v1
```

The 63-task suite distinguishes point identification, set identification, and
registered point-unidentifiability. It verifies the scoring contract using
reference policies; it does not claim that a learned investigator generalizes.

Run and verify the compute-matched Confinement Width transfer test:

```powershell
python src\confinement_transfer.py --manifest experiments\confinement_transfer_v1\manifest.json --output results\confinement_transfer_v1 --splits all
python src\verify_confinement_transfer_artifacts.py results\confinement_transfer_v1
```

Evolutionary schedule search improved the untouched-holdout kernel-escape rate
by `+0.11068` over equal-evaluation random search while preserving the original
proxy and closure gates. The paired interval includes gains below the registered
`+0.10` practical threshold, so the accepted result is the frozen point-estimate
gate plus directional consistency, not a precise lower-bound claim.

For a relocated bundle, add `--portable` to each verifier command. Portable
mode ignores original-machine absolute paths and requires one unique
multi-component suffix match. Runtime-environment differences and non-D storage
are reported as provenance warnings; receipt/hash, schema, scientific-gate, and
ambiguous-path failures still make the artifact invalid.
