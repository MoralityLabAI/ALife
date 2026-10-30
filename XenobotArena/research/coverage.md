# Xenobot research coverage and model boundaries

Checked 2026-10-29 against the official Tufts synthetic-morphology and computational publication indexes, ICDO's list, primary publisher pages, author project pages and indexed primary preprints. The 20 records in `sources.json` have different review depths. A title or abstract check is not a full-paper audit. Every record includes its retrieval basis.

## Source-to-model map

| Records | Source contribution | Arena treatment |
| --- | --- | --- |
| X01 (2020) | Original computational-design/embodiment study | Historical anchor; 3D tissue mechanics not reproduced |
| X03, X05 (2021) | Ciliated movement, swarm particle handling, repair, and an exposure reporter | Motion/contact assays; recorder and recovery are explicit surrogate rules |
| X04 (2021) | Kinematic replication | Literature coverage only; population counts are invariant |
| X10 (2023) | Simulated swarm composition and obstructed exploration | Mixed-motion baselines and obstacle scenario; original algorithm not reproduced |
| X12 (2025) | Transcriptomic changes and acoustic response | Generic pulse interface, with no acoustic calibration or gene-expression model |
| X13, X14 (2025) | Information organization in aneural tissue | Future observational-data analysis adapter; no causal or consciousness inference |
| X15 (2025) | Bidirectional-culture communication research | Source/code pointer; no communication mechanism asserted in this model |
| X16 (2026 preprint) | Behavioral and physiological memory | Synthetic latent-state assay and memory-off ablation; no fitted biological mechanism |
| X17 (2026 preprint) | Coordination under signaling perturbation | Indexed, not implemented |
| X18 (2026) | Neurobots with neural tissue | Separate extension, not conflated with aneural constructs |
| X19, X20 | Human-cell anthrobots | Related comparator platform, not xenobots |
| X02, X06-X09, X11 | Ethics, theory, reviews and open problems | Framing; these sources do not validate the numerical model |

## What the repository now contains

The artifact is an original standard-library simulator, offline viewer, tests, a metadata inventory and source-linked research notes. It contains no publisher PDFs, downloaded audio, full-video transcripts or copied upstream implementation. Upstream repositories are discovery links; their licenses and exact commits have not been audited or vendored.

## Retrieval gaps

Several publisher endpoints returned access errors. The 2023 ALIFE paper and 2025 communication paper are represented by official bibliographic records rather than full-paper reproductions. Direct bioRxiv retrieval returned 403; preprint records retain primary URLs and indexed evidence levels. The exact review status of later versions has not been established. The index does not claim all talks, supplementary files, reviews, or newly appearing papers have been found.

A full-text pass should log a stable version and checksum for each acquired source, respecting its actual access and reuse terms. Reconcile preprints with subsequent publications by DOI and author/title matching. Future updates must keep anthrobots, aneural xenobots, early muscle-driven constructs and neurobots distinguishable.

## Next scientific tests

A real calibration pass requires held-out measured trajectories and measurement uncertainty. Candidate fits should be compared against passive, persistent-random-walk and circular-motion controls at matched computational cost. Hold out entire recordings or experimental batches; adjacent frames are not independent examples. Use out-of-sample displacement distributions, turning statistics and contact-response measures before claiming fidelity.

A compactification study can compare a representation of full simulator state with coarser histories on future motion under declared interventions. Register the prediction horizon and the allowed action interface. Keep hidden memory state available only to the full-state oracle. A history-aware predictor beating a position-only predictor here would establish a property of the planted model. It would not demonstrate a biological mind or validate a Platonic interpretation.

The initial fixed-seed run is an engineering smoke campaign. Its numerical evidence is in `../examples/smoke_report.json`; the values are observations of this model, with its own source hash. No biological validation has occurred.
