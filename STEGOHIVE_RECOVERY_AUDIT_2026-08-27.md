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
mode for V6–V9. On V9, the original compiled detached verifier accepts all 517
worlds and all eight campaign stages: contract/schedule projection, receipt and
hash closure, execution reservation, raw episodes and re-derived analyses,
replay exposure and retained calibration, resource/timing aggregates, final
summary and claim units, and the future-sealed seed manifest.

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
