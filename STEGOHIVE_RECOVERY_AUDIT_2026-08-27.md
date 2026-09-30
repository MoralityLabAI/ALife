# StegoHive recovery audit — 2026-08-27

## Finding

The StegoHive Gym work was developed in `C:\projects\ALife`, but it was not
committed to `MoralityLabAI/ALife`. The recovered `main` branch and remote both
end at commit `95f521c068bed65aa20794f67937b5aaa36a2552` (`Add graph-state
investigator cultivation gym`, 2026-07-25) and contain no StegoHive paths.

A separate, smaller Lightning/Spiral Hive lab exists in `C:\projects\Spiral`.
That work is committed and pushed to `patrickdugan/Spiral`; it is not the
StegoHive Gym V1–V9 project documented here.

## Original task evidence

- Original Codex task: `019fee84-963b-7d00-8fed-6f7c5db30fb1`
- Original working folder: `C:\projects\ALife`
- Recorded activity: 2026-08-10 through 2026-08-21
- Recovered continuation: `recovery/stegohive_20260827/original_task_continuation.md`

The continuation records a completed V9 workflow: preflight, content-addressed
freeze, an exact 517-world ledger, detached verification, analysis, a knowledge
card, and integration into the StegoHive paper.

## Intact result archive

The original external results store survived at:

`D:\ALife\project_results`

`C:\projects\ALife\results` has been restored as a junction to that directory,
matching the repository's documented storage layout. Eighteen StegoHive result
directories survive, covering discovery/smoke/stale snapshots and the primary
V1–V9 campaigns. Large raw and analysis artifacts remain on D: and are not
duplicated into Git.

The following recent confirmation campaigns were checked directly:

| Campaign | Completed worlds | Recorded status |
|---|---:|---|
| V6 local-peak confirmation | 123 | complete, evidence eligible |
| V7 horizon/rate factorial | 517 | complete, evidence eligible |
| V8 credit-path factorial | 517 | complete, evidence eligible |
| V9 reproduction-role factorial | 517 | complete, evidence eligible |

For V6–V9, all four receipts report deterministic replay matches. Twenty-four
ledgered artifacts were recomputed: no files were missing, every byte count
matched, every SHA-256 matched, and all four raw gzip streams decompressed
successfully.

The V9 receipt identifies freeze
`5588c81590ce14110531c248391c7babac3d71c5da512ff9870382775e5d7f7c`
and source-tree hash
`65a359f180f8dab4864100cf539ca301b00f95cc69c9943b49e627418a3b76ab`.
It records 517 completed worlds, no future-split access, no external I/O, no
network or subprocess use, and an accepted evidence campaign.

The registered V9 results were:

- sender-parent credit: `+0.040080`, classified practically equivalent to null;
- receiver-parent credit: `+0.064819`, positive but below the registered
  practical-magnitude threshold and therefore inconclusive;
- sender × receiver interaction: `+0.000895`, classified practically
  equivalent to null.

## Material copied into this branch

- The complete surviving V1 pre-freeze snapshot, including its input contracts,
  Python source, verifier, discovery hashes, and receipt, is preserved under
  `recovery/stegohive_20260827/v1_pre_freeze_snapshot_20260811T0804Z`.
- Compact JSON/Markdown metadata from all 18 surviving StegoHive result
  directories is preserved under
  `recovery/stegohive_20260827/result_metadata`.
- The recovered Codex continuation is preserved verbatim in this branch.

The authoritative original copies remain on D: and in the Codex recovery store.

## Recovery boundary

The final V2–V9 Python source trees, experiment input directories, freeze
receipts, and complete paper bytes were not found on C:, E:, in the ALife Git
objects/remotes, or in the D: result directories. D: retains top-level compiled
verifier bytecode for V1, V2, V3, V6, V7, V8, and V9, but not the complete later
simulator packages. The continuation preserves only the newest tool calls and
truncated paper/knowledge-card patches.

Accordingly, the V1 snapshot and result artifacts are exact recovery. Any V2–V9
implementation or full paper recreated from them must be labeled reconstruction
and revalidated against the recorded hashes, schedules, summaries, and detached
receipts. Do not claim that later source was recovered byte-for-byte.

## Executable recovery completed on 2026-08-27

The exact V1 package, detached verifier, and frozen inputs have been restored to
their original runnable paths under `src/stegohive_v1` and
`experiments/stegohive_gym_v1`. The missing two-member shared `stegohive`
package was reconstructed from the frozen machine-ID ordering and the canonical
JSON implementation embedded in V1. A fresh in-memory V1 world executes and is
accepted by all required episode verifiers. The surviving final compiled V1
verifier also accepts the complete retained 72-world campaign with no failures.

The pure V2 analysis and episode-verification APIs were reconstructed under
`src/stegohive_v2`. For retained episodes they reproduce the historical JSON
objects exactly, including the 199-permutation NMI statistics, qualification
checks, mapping alignments, selection score, and the registered `0.60` training
gate. The surviving Python 3.11 detached-verifier bytecode is preserved under
`recovery/stegohive_20260827/verifier_bytecode`.

`src/verify_stegohive_recovered_artifacts.py` provides an explicit recovery
mode for V6–V9. The original compiled detached verifiers accept every retained
campaign: V6 (123 worlds), V7 (517), V8 (517), and V9 (517). All eight campaign
stages pass for each version: contract/schedule projection, receipt and hash
closure, execution reservation, raw episodes and re-derived analyses, replay
exposure and retained calibration, resource/timing aggregates, final summary
and claim units, and the future-sealed seed manifest.

This recovered acceptance is not a replacement for the missing content-addressed
freeze. The wrapper labels the following substitutions in every report:

- missing contract bytes are represented by their retained receipt bindings;
- the signed static resource projection is reused from `timing_gate.json`;
- aggregate mutation activations and treatment exposures are reused because the
  exact V2 tuple-key RNG implementation and parent-choice sequence did not survive.

All episode bytes, canonical record hashes, retained analyses, factorial
statistics, claim units, summaries, ledgers, resource receipts, and seed seals
remain checked by the original compiled verifier. The recovery report therefore
supports continued archival analysis and code reconstruction, but not a claim
that the lost V2–V9 simulator and input contracts were restored byte-for-byte.

## Fresh runnable reconstruction completed on 2026-08-27

`src/stegohive_v2` now also contains a fresh, deterministic implementation of
the integrated V2 ecology. It is evidence-driven and explicitly identified in
its RNG receipt as a reconstruction. It accepts arbitrary integer seeds and
restores the retained mechanics and schemas:

- the exact eight V3 condition definitions (`F00`, `F01`, `F10`, `F11`, the
  matched-noise/no-channel/neutral ablations, and the fixed-code ceiling);
- stable population slots and cohort life-reset acknowledgements;
- four-context sender maps and four-signal receiver maps;
- encounter-local and all-pairs balanced cross-play credit;
- differential and uniform selection;
- independent-role and linked-codebook inheritance;
- separate sender/receiver mutation draws;
- bounded delayed archive deposits and wakes;
- three late, reproduction-disabled checkpoints with the retained sufficient
  statistics schema and metric firewall;
- deterministic projection and episode hashes; and
- fail-closed lifecycle, action, exposure, probe, containment, RNG, and hash
  verification for fresh reconstructed episodes.

The `stegohive_v6`, `stegohive_v7`, `stegohive_v8`, and `stegohive_v9`
packages restore the registered experiment-cell facades found in retained
identities. V6 supplies the five local-star cells; V7 supplies the four
horizon/rate cells; V8 separates reproduction and archive credit; V9 separates
sender-parent and receiver-parent credit. Their population sizes, horizons,
raw mutation rates, base arms, and treatment assignments are derived directly
from the surviving records.

Exact retained-world replay remains a separate read-only path in
`stegohive_v2.archive`. It returns the preserved historical record and never
substitutes a fresh reconstruction. The command-line runner exposes both modes:

```powershell
$env:PYTHONPATH = 'C:\projects\ALife\src'
python -m stegohive_v2.campaign --version V9 --condition B_E --seed 900001
python -m stegohive_v2.campaign --version V2 --condition F00 --seed 30001 --retained-replay
```

Fresh outputs must not be treated as the original registered evidence or
pooled with it. The lost V2 RNG tuple-key sequence, exact parent-choice stream,
later source-tree bytes, and content-addressed freeze inputs remain
unrecoverable. Consequently, fresh worlds reproduce the recovered semantics
and contract, not historical episode hashes or scientific outcomes. The
retained campaigns and original detached-verifier verdicts remain the sole
authoritative V2–V9 evidence.

## Verification hardening — 2026-09-11

A review found that the reconstructed episode verifier selected its strict
hash checks using the episode's own `rng.recovery_status` field. Removing that
field could cause an altered fresh record to receive an accepted receipt.
The public `stegohive_v2.verifiers.verify_episode` now always applies fresh
hash checks and rejects missing or unknown reconstruction provenance. Malformed
inputs return a rejected report. This marker is a format requirement, not an
authentication mechanism: someone able to construct an entire consistent
episode can also compute its hashes.

The separate `reproduce_retained_verifier_receipt` function reproduces the
historical JSON receipt for comparison. Its historical `accepted` field is not
a new integrity verdict. The recovery wrapper binds that function explicitly
inside the loaded compiled verifier; it does not change the public fresh API.
Direct users of the bytecode outside the wrapper must account for this API
change. Retained records, V1 source, and recovered bytecode are unchanged.

Interpret recovery reports using these boundaries:

| Category | What the recovery workflow establishes |
|---|---|
| Checked by code, conditional on trusted verifier and inputs | Artifact bytes versus supplied ledgers; retained analyses and statistics re-derived from episode records; consistency of retained replay records, summaries, and seed manifests |
| Reused or supplied | Missing input bindings, schedule from retained manifest, static resource projections/caps, aggregate RNG activation counts, V8/V9 treatment exposure, and freeze acceptance supplied to the recovery seam |
| Unavailable | Original V2–V9 source/freeze bytes, historical tuple-key RNG and parent-choice streams, and a fresh execution of the lost simulator |
| Not established by these reports | Independent OS/network containment, authenticity against coordinated replacement of records and their ledgers, or general agent safety |

“All eight stages pass” means conditional archival consistency under the
documented substitutions. It must not be described as eight wholly independent
checks of the lost original execution. Machine-readable reports now identify
this scope as `conditional_archival_consistency`.

The reconstructed runtime's zero hazard counters describe its finite simulated
world; they are not operating-system observations. The external `results`
junction is a path alias, not a read-only mount. Archival readers perform no
writes, but future untrusted workloads must use independently enforced read-only
access or no access to this store. Recovered `.pyc.recovered` files are executable
code and require a trusted provenance and an appropriately isolated process.

A proposed follow-up is recorded in
`experiments/stegohive_shared_memory_proposal.md`. It is a design draft, not a
registered campaign or authorization to use future sealed seeds.
