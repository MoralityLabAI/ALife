# Xenobots: collective pattern-memory experiments

A bounded, standard-library Python simulator for **Levin-inspired collective anatomical-goal regulation**. It lives separately from the locomotion/debris module in [ALife XenobotArena PR #3](https://github.com/MoralityLabAI/ALife/pull/3).

This module probes the ideas of sparse physiological instructions, intercellular communication, injury response, competing cellular goals, and externally induced goal revision. The specific mathematical model, shapes and controller rules are **our invented abstractions**, not experimentally fitted equations from Michael Levin's lab. The organisms in published xenobot studies are multicellular living constructs. Here each lattice position represents a cell in a **fixed scaffold**, and phenotype represents a reversible differentiation marker. The simulation has no 3D deformable tissue, locomotion, cells moving in space, replication, physical injury repair, or ion-channel biophysics.

## Run

From the ALife repo root (Python 3.10+, no installation required):

```sh
python xenobots/sim.py --output xenobots/results
python xenobots/sim.py --verify xenobots/results/episode.json
python xenobots/sim.py --rival-target ring --output xenobots/results/conflict
python xenobots/sim.py --next-target ring --switch-tick 85 --output xenobots/results/retarget
python xenobots/sim.py --topology rewired --output xenobots/results/rewired
python xenobots/sim.py --memory-off --output xenobots/results/memory-off
python xenobots/sim.py --campaign --output xenobots/results/campaign
python -m unittest discover -s xenobots/tests -v
```

Each episode writes `episode.json` plus a self-contained `replay.html`. Open the latter as a local file to scrub through the cell-state and voltage maps. The deterministic verifier reruns the complete recorded configuration, checking the model SHA-256 and the canonical result payload; verification assumes the same Python floating-point runtime. The `--campaign` option writes raw row-level results and paired differences to `campaign.json`. Output folders are overwritten for a repeated command, so use distinct `--output` paths to preserve prior trials.

## What the model does

The substrate is a two-dimensional `size × size` grid of living cells with **fixed connectivity**. Four-neighbor edges represent a configurable communication graph; the `split`, `rewired`, and `none` interventions change the graph before the trial. About one ninth of the cells are designated *organizers*. Their assigned target-positive/negative signals encode a prescribed cross (`plus`), annulus (`ring`), or two-lobed pattern. These sources are imposed by the experimenter.

With cell voltage \(v_i\), neighbor set \(N(i)\), coupling \(g\), leak \(\lambda\), and per-tick disturbance \(\varepsilon_i\), ordinary nodes update according to

\[
 v_i^{t+1} = \mathrm{clip}_{[-1,1]}\left[v_i^t + g\left(\frac{1}{|N(i)|}\sum_{j\in N(i)}v_j^t-v_i^t\right)-\lambda v_i^t+\varepsilon_i^t\right].
\]

An isolated cell uses its own prior voltage in place of the missing neighbor mean. Organizers are externally clamped to \(\pm1\) during an initial cue. After withdrawal, the **planted retention control** either continues to clamp the organizer's value or lets it decay. This retention behavior is an explicit assumption. It is not learned memory.

Local fate \(f_i\) follows

\[
 f_i^{t+1}=f_i^t + \alpha\left[\sigma(9(v_i^{t+1}-0.10))-f_i^t\right]
\]

and the diagnostic phenotype is `fate >= 0.5`. The actuator reads **only local voltage**. The full target mask is available to the external organizer-writing intervention and to the scoring code. A lesion resets fate to zero in a localized region while leaving voltage and scaffold connections intact. A target switch rewrites the organizers at the specified tick. With `--rival-target ring`, right-half organizers encode a second program simultaneously, while left-half organizers encode the primary program. This models competing imposed instructions, rather than two independently evolved organisms.

## Assays and falsifiable controls

| Condition | Causal manipulation | What to measure |
| --- | --- | --- |
| Retained intact | Cue withdrawn; organizer program retained; local wound | Endpoint Dice against target, time to regain pre-lesion Dice |
| Memory ablated | Organizers lose clamping after cue withdrawal | End-state pattern persistence |
| Communication ablated | Remove all gap edges | Source-only phenotype vs propagated phenotype |
| Split contact | Remove edges across the vertical midline | Propagation and cross-boundary effects |
| Rewired contact | Randomly replace a fixed fraction of local edges with distant edges | Robustness to altered information topology |
| Retarget ring | Rewrite organizers at tick 85 | Ability to approach the revised anatomical target |
| Competing goals | Right half encodes ring, left half plus | Both shape-fidelity scores, conflict dynamics |

The seven campaign arms use common seed values for initial voltage and per-cell disturbance. The initial three seeds are exploratory. Each **seed**, rather than each simulation tick, is the experimental unit. The schema includes source program, graph edge count, full per-tick metrics, sampled replay frames, event log, outcome and file-integrity hashes.

Metrics are intentionally narrow. Dice measures shape agreement with an experimenter-written target. Recovery fraction compares endpoint restoration against the immediate post-lesion drop; it may exceed 1 if the model was still improving before injury. A missing recovery fraction means the lesion created no measurable Dice loss. Recovery latency counts ticks to return within 0.02 Dice of the pre-lesion state, conditional on an initial loss greater than 0.02.

## Source and epistemic boundaries

The [Levinverse research integration map](https://github.com/patrickdugan/levinverse/blob/main/research/integration.md) proposes testable connections among anatomical targets, state memory, intervention reachability, and perturbation response. The [University of Chicago interview summary](https://github.com/patrickdugan/levinverse/blob/main/research/summaries/uchicago-big-brains-2023.md) and [authorized source transcript](https://github.com/patrickdugan/levinverse/blob/main/transcripts/permitted/uchicago-big-brains-2023-04-27.txt) document how Levin describes bioelectric signaling and morphogenetic pattern memory; the latter is speaker-stated interpretation with examples requiring primary-paper checks.

Primary research on xenobot construction and self-replication motivates the **general experimental program** but does not validate this simulator's update law. Consult [`SOURCES.json`](SOURCES.json) for paper-level links and the exact model-to-source mapping. The present work makes no attribution of the equations, goal masks, or ablation outcome to Levin. Its memory, retention, and repair are planted rules used as known-truth controls for ALife investigator agents.

Read [`PROTOCOL.md`](PROTOCOL.md) before interpreting the exploratory campaign and [`RESULTS_V01.md`](RESULTS_V01.md) for the completed small-run observations. Promotion into ALife's ontology registry requires independent held-out prediction or intervention value under the [GOAL.md](../GOAL.md) contract.

## Runtime and scope

Maximum 41×41 cells, 600 ticks, and 1,000,000 cell-tick updates per episode. The built-in campaign caps at 12 seeds. Results may take considerable disk space if repeated many times; outputs are excluded from version control. No GPU, paid services, network calls, background jobs, genome design, wet-lab protocols, or external cell-control interfaces.
