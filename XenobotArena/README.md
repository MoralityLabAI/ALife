# XenobotArena

A bounded, headless ALife sandbox inspired by Michael Levin and collaborators' xenobot research. This module runs on a CPU with Python 3.10+ and the standard library. It adds no dependency to ALife's existing worlds and changes no ontology registry.

## Run from the ALife repository root

```bash
python XenobotArena/arena.py --scenario debris --mode mixed --seed 7 --steps 400
python XenobotArena/arena.py --scenario obstacles --mode persistent --steps 400
python XenobotArena/arena.py --scenario recorder --steps 400
python XenobotArena/arena.py --scenario memory --steps 240
python XenobotArena/arena.py --scenario recovery --steps 240
python XenobotArena/arena.py --campaign --steps 240
python -m unittest discover -s XenobotArena/tests -v
```

A normal episode writes `XenobotArena/results/episode.json` and `replay.html`. Open the HTML locally for a play/pause/seek replay. Each invocation replaces those files within its selected output folder; give different runs separate `--output` directories to retain them. On Windows, use an existing data drive for larger output sets, for example `--output D:/ALife/project_results/xenobotarena/demo`.

Verify an autonomous episode:

```bash
python XenobotArena/arena.py --verify XenobotArena/results/episode.json
```

The verifier reruns the specified configuration and checks every sampled frame, event, initial/final diagnostic, and terminal state digest against the current code hash. JSON serialization is canonicalized. Exact replay is tested within the same Python runtime; cross-version floating-point identity is not promised.

## Implemented assays

| Scenario | What runs | Evidence boundary |
| --- | --- | --- |
| `open` | Persistent, orbiting or mixed active disks in a bounded arena | Whole-bot movement surrogate; no 3D tissue or cilia mechanics |
| `obstacles` | Disk motion with two fixed circular obstacles | Exploration assay, not a recreation of a published maze |
| `debris` | Contact-driven displacement of inert beads with fixed counts | Particle handling analogue; successful aggregation is not assumed |
| `recorder` | Permanent exposure bit on entering a marked strip | Analogue of the 2021 reporter; recorded exposure does not change motion |
| `memory` | Finite pulse plus a decaying latent state affecting speed | Planted memory model with a memory-off control; no learned biology |
| `recovery` | Scheduled integrity loss and optional exponential recovery | Planted speed-recovery rule, not wound-healing tissue physics |

Modes are `passive`, `persistent`, `orbit`, and `mixed`. Every paired arm uses the same placement seed and consumes the same number of motion-noise draws. A spatially stationary passive arm still has changing orientation labels; those labels exert no motion.

## Model and parameters

All units are dimensionless and uncalibrated. Each bot is a disk of radius 0.8, beads have radius 0.3, and the timestep is 0.1. Bot orientation follows

    theta[t+1] = theta[t] + (intrinsic_spin + action_turn)*dt
                 + noise*sqrt(dt)*normal(0,1)
    x[t+1] = x[t] + dt*speed*(cos(theta), sin(theta))

Base active speed is 1.5. Intrinsic spin is zero or +/-0.65 according to mode. Reflecting walls and an iterative positional contact solver constrain motion. Bot-bot and bead-bead displacements are split equally. Bot-bead displacements are split 0.1/0.9 to give the bead greater mobility. Four contact sweeps provide a bounded approximation; `max_residual_overlap` exposes solver error. These numerical choices are original modeling assumptions.

In the memory assay, a uniform pulse is active on ticks 30 through 49:

    memory[t+1] = 0.96*memory[t] + 0.04*pulse[t]
    speed = 1.5*throttle*integrity*max(0.1, 1 - 0.45*pulse - 0.3*memory)

In the recovery assay, integrity drops to 0.25 at tick 40, then the optional rule adds `0.025*(1-integrity)` each later step. These planted rules provide known-truth controls for investigator agents. They supply no evidence that the corresponding biological system uses these equations. Observing the injected effect is an implementation check.

Bot and bead counts stay constant. The arena has no biological reproduction, tissue-construction recipes, genetic mechanisms, deployment model or real-world parameter optimizer. The kinematic-replication paper remains in the literature index. Neurobots and human-cell anthrobots are listed as related systems and have no implementation here.

## Agent interface

```python
from XenobotArena.arena import Arena, Config

env = Arena(Config(scenario="obstacles", steps=200))
observation = env.reset(seed=17)
observation, info, done = env.step({0: (0.8, 0.1)})
```

An action maps a bot ID to `(throttle, turn)`, bounded by `[0,1]` and `[-1,1]`. Unspecified bots continue their default motion. Action validation is atomic. The observation contains positions, headings, beads and obstacles; `snapshot()` exposes internal state for diagnostic use. This is a custom API, not a Gymnasium adapter. The action channel is an artificial controller affordance, not a demonstrated method for controlling xenobots. The included CLI verifier covers autonomous runs; a policy experiment must separately record actions.

## Diagnostics and experimental discipline

The fixed campaign runs six scenarios, four modes and three seeds, then adds paired memory/recovery ablations: **84 simulator episodes**. It reports raw episode rows and matched-seed differences. Seeds are the experimental units. This suite has no trained policy, selected winner, statistical success gate or biological calibration.

Coverage measures visited bot-center bins on a fixed 20 by 20 grid, divided by 400 including obstacle-covered bins. It is a deliberately simple within-scenario diagnostic. Path length includes collision correction; it is not an energy measure. Bead clusters use connected components at separation <=0.7. The largest-cluster fraction can remain unchanged even when particles move. Contact counts measure solver corrections, not unique collision events.

Before testing a scientific hypothesis, freeze a target, comparator and fresh-seed protocol consistent with ALife's `GOAL.md`. Assess prediction on held-out interventions. Keep visual interest and activity separate from scientific evidence. No result from this initial campaign is promoted to ALife's ontology registry.

## Research inventory

[`research/sources.json`](research/sources.json) indexes **20 core and adjacent papers** with DOIs, primary links, review depth and limitations. It covers the early platform work, later behavioral and information studies, and 2026 preprints. Five author/project resources are linked separately. This is a checked index with original annotations, not a full-text or transcript archive. See [`research/coverage.md`](research/coverage.md) for model-to-source mapping and remaining work.

## Bounds

At most 48 bots, 192 beads, 4000 steps and 1002 stored frames per individual run. A preflight bound enforces `steps*(bots+active_beads)^2 <= 25,000,000`; the four contact sweeps add a constant factor. Campaigns allow at most 500 steps and eight seeds through the Python API. Defaults use three seeds. The code performs no network calls, uses no GPU, and starts no background worker.
