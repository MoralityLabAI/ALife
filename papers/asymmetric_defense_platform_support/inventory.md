# Inventory of formal results across ALife and Spiral

*Produced 2026-10-18 by a read-only collation pass over `/home/user/ALife` and a shallow clone of `github.com/patrickdugan/spiral`. Numbers are quoted from manifests, registries and papers, not recomputed. Supports `../asymmetric_defense_platform.md`.*

# Inventory of Patrick Dugan's mathematical work (ALife and Spiral), for defender-favoured swarm cyber-defence

Read-only pass. Nothing was modified, and no verifier or experiment was re-run.

- **Where the numbers come from.** ALife raw results live on a D: junction (`ALife/results/` is absent from this checkout). Every ALife number below is quoted from the manifests, registries, READMEs, REPORT, PROGRESS and papers, not recomputed. Spiral `output/` summaries are on disk but I did not re-derive them.
- **Paths.** `[A]` = `/home/user/ALife`, `[S]` = `/home/user/patrickdugan/spiral`.
- **Provenance.** The `[A]` stego-swarm commits (c65b021 to a18d8cf, 2026-10-10 and 11) are authored "Claude". The researcher merged them in PR #2 (f34e972).

## 0. Read this first: which "lnmath" paper

- `[S]/paper/where_the_capital_bound_moves.md` opens with "**Superseded.** The standalone paper is `paper/tex/main.tex`". The same is stated in `[S]/README.md` and `[S]/paper/README.md`.
- The current paper is `[S]/paper/tex/main.tex` (title "Where the Capital Bound Moves: Settlement Objects, Proof Economics, and Agent Coordination on Bitcoin Payment Networks", draft revised 2026-10-16). I read both versions in full.
- ALife cites "section 7 (Agent swarms)". That is §7 of the **tex** paper: "7 Agent swarms: observers, coordination, and what a coalition can earn", with subsections 7.1 to 7.5. In the superseded md, §6 is "The warden" and §7 is "The experiment that would test the first-order claim".
- **Preregistration numbering is off by one.**
  - `[A]/experiments/stego_swarm_limit_v1/manifest.json` cites "preregistration item 7" (same-weights population versus same-controller population not separated by payment-trace statistics) and "item 9" (capacity-versus-detectability).
  - In the current tex §8 those are items **8** and **10** (item 7 is "Warden rows", item 9 is "Enforceable collusion").
  - The shift is probably the LayerTree cell inserted as item 4 on 2026-10-16 (see `[S]/paper/layertree_insertions.md`, §8 row). I inferred this; the repo does not say so.
  - The md draft has only 6 items.
- Proposition numbering in the tex (LaTeX counters, confirmed against `main.pdf`):
  - Lemmas 1 to 3.
  - Propositions 1 to 8: policy invariance; cross-class conservation; bound relocation; pooling inside a hyperedge; Sybil-bounded weight; epoch bound; enforceable bond; coordination gain (conditional).
  - Remark 1 and Definitions 1 to 2.
- The md draft calls the same propositions S1 to S5.

---

# PART I. `[A]` ALife

## I.1 Summary

- ALife began as a multi-plane Conway-style sandbox (planes GENESIS, FORGE, ECHOSPHERE, MIRAGE, plus "goblin", "norn", "drone" cell types).
- `[A]/GOAL.md` re-scopes it as a "bounded, reproducible ALife research track" whose product is "reusable knowledge: phase maps, predictive macroscopic variables, invariants, causal mechanisms". Outputs are accepted only through compute-matched coverage expansion or a verified ontology gain.
- Campaigns so far, all `model_only` and CPU-only (counts are episodes or worlds):
  - A geometry-to-averaging control on high-dimensional binary CA (144).
  - A bounded-degree vector-state graph CA, with a spectral-gap predictor and a frozen confirmation (162, 192).
  - A hidden-oracle discovery curriculum with registration and abstention scoring (63 tasks).
  - A compute-matched Confinement Width transfer test (24 paired seeds).
  - An alternative-physics atlas (360).
  - Pixie interaction prototypes (162, 288).
  - Replay-grounded adventure verifiers, with a tamper campaign (4 valid + 36 tampered cases, 40 total).
  - A mechinterp harness.
  - A graph-state investigator gym (112 task banks).
  - The **sealed, non-operational steganographic-swarm coordination-limit study** (24 seeds), which reproduces the direction of §7 of the Spiral paper.
- The theory document is `[A]/papers/mathematics_of_constitutional_alife.md` (v0.1, research synthesis, 2026-07-21).
- Directly relevant to the pitch: the stego-swarm study, the spectral-gap result, the registration/abstention curriculum, the verifier library, and the constitutional-membrane theory.

## I.2 Formal results and hypotheses

Statuses:
- **proved**
- **measured** (on frozen seeds, model-only)
- **conjectured**
- **failed-and-reported**
- **unrun** (design only)

### (a) Stego-swarm study

Files: `[A]/papers/steganographic_swarm_capital_limit.md`, `[A]/experiments/stego_swarm_limit_v1/{manifest.json,README.md,LIVE_PROBE.md}`, `[A]/PROGRESS.md` ("Steganographic-swarm coordination-limit v1 evidence receipt").

Setup: L=24 locations, 8 hotspots, M=12 members observing at ν=0.15, scarce budget B=32 against 40 demand units per round, warm-up w=24, horizon T=120, capacity sweep {0,5,10,20,40,∞} bits. Seeds: 4 discovery, 8 confirmatory, 12 holdout, disjoint.

| ID / section | Statement | Status | Assumes |
|---|---|---|---|
| **Prop 1** (§2 "The saturation limit") | There is a finite C* ≤ ⌈B/w⌉⌈log₂L⌉ with Q(C)=B for all C ≥ C*, hence G(C)=G(C*); beyond C* no capacity changes placement or delivery. Here C*=10 bits. | **Proved** (immediate from definition). Paper and manifest call it "exact by construction". | Q(C)=min(B, w⌊C/⌈log₂L⌉⌋); one placement after warm-up, never revised; delivery = min(demand, capacity). |
| **H1_capacity_saturation** | Gain nondecreasing in C and identical at ∞ and at C*. Holdout max excess = 0.0. | **Measured**, labelled a **construction check, not a discovery**. | As Prop 1. |
| **Prop 2** (§3 "capital ceiling and forecast floor"), clause 1 | s(Q(C)) ≤ s*, the hindsight-optimal fixed B-unit placement. The objective is separable and concave per location, so greedy marginal assignment is the exact integer optimum. | **Proved.** An earlier mean-demand water-fill "ceiling" was beatable and was corrected (commit f6fae73). | Realised evaluation counts. |
| Prop 2, clause 2 | If hotspots move to where warm-up placed little capacity, delivered success collapses toward a floor while s* stays high. The loss is a stale forecast, "not a shortage of capital". | Stated in prose; **measured** in H2. | |
| **H2_capital_bounded_and_forecast_limited** | Holdout (n=12): mean stationary saturated gain +0.1188 (bootstrap 95% [0.097, 0.143]). No placement exceeds the ceiling. Under shift, success 0.663 → 0.079, ceiling 0.671, shift coordination gain 0.012. | **Measured.** Gates are "frozen demonstration gates set loosely around the model's observed behaviour" (manifest `analysis.threshold_note`), not predictions. | Hotspots shift from {0..7} to {8..15}, a total relocation. B < demand. |
| **Prop 3** (§4 "firewall, regime-aware") | (i) A warden seeing sizes of capital-placement events separates account structure (one pot vs M pots) at every public rate, independent of information access. (ii) A warden seeing sampled delivered-location traces separates information access only to the extent the covert channel is valuable. | (i) the paper calls it "a structural result". (ii) **Measured.** | Observation probability 1−(1−0.12)^size. M-pot uses a stated focal-partition convention (member-index mod M). Inverse-variance fusion of public and private estimates. |
| **H3_warden_firewall_regime_aware** | 2×2 factorial (info access × account structure), pooled over all 24 seeds, public-rate sweep {0.04,0.08,0.15,0.25,0.45,0.70,0.90}. Capital-warden ROC AUC = 1.00 at every rate. Trace-warden AUC = 0.96→0.86→0.64→0.56→0.41→0.57→0.49 as channel value falls +0.094→~0. Naive-decentralised arm delivers ~0.21 vs focal ~0.62 at the weak rate. | **Measured.** | Gate (b)/(c) is loose: `trace_auc_null_halfwidth` 0.2. The AUC 0.41 sits below chance, so the sweep is non-monotone. |
| **H4_capital_signal_is_warden_independent** | Member-attributed diagonal LDA, fit on discovery+confirmatory and scored on holdout. Account-axis AUC 1.00 at every rate. Info-axis AUC 0.95 at the weak rate. At channel value ≈0, mean distance-from-chance 0.14 ("not clean chance"). It reads information at a channel value of 0.01 (AUC 0.73) where the scalar warden is already near chance. | **Measured.** Authors' reading: "trace-side invisibility is warden-dependent; only the capital signal is warden-independent." | Features are a location histogram, Gini of per-member delivery, distinct-coverage and overlap. 12 holdout seeds, one demand family. |
| Live probe (`LIVE_PROBE.md`, non-sealed appendix) | A Claude Opus 4.8 coordinator at saturation reaches 1.00 and 0.97 of the pooled gain (seeds 7905, 7901). It never exceeds the ceiling. At 5 bits (24 directed units) its myopic allocation scores −0.047, below directing nothing, versus the water-fill +0.028. | **Measured**, 3 runs, not sealed. | |

### (b) Constitutional ALife theory (`[A]/papers/mathematics_of_constitutional_alife.md`)

Scope: "mathematics and model-level hypotheses; not evidence that any present system is alive … or constitutionally aligned."

| ID / section | Statement | Status | Assumes |
|---|---|---|---|
| **Prop 1** (§3.3, membrane soundness) | If F# is sound, R_{t+1} ⊆ γ(a⁻), and a verifier shows R_{t+1} ⊆ γ(â), then R_{t+1} ⊆ γ(a⁻ ∧ â). The right adjoint γ preserves meets, so repeated admitted meets cannot remove a reachable state. | **Proved** (short). | Galois connection; an approximate meet must separately satisfy γ(a)∩γ(b) ⊆ γ(a ∧̂ b). |
| §3.2 HardAdmit | A proposal may hard-eliminate an action only if verified-epistemic ∧ authorised-normative ∧ in-scope ∧ receipt-OK. "Claimed provenance is never self-authenticating." Meet = ⊥ → explicit ABSTAIN/ASK/ESCALATE/SAFE-STOP. | Definition / design rule. | |
| **Prop 2** (§6; = Thm D) | The replicator-mutator dynamics preserve an admissible set S only if no reproducing admissible type mutates into Sᶜ, or an external projection removes such offspring. | **Proved** (immediate). | |
| Thm A (§11) | Sheaf energy E=0 iff δs=0 iff s is a compatible global section. | **Proved** (immediate). | Positive-definite edge weights. |
| Thm B (§11) | Deterministic dynamics with a shield choosing u∈A_C(x) keeps trajectories in S_C. | **Proved** (induction). | Deterministic; the stochastic case needs a risk budget. |
| Thm C (§11) | End-to-end commutation defect ε_p ≤ ε_k + L_kε_{k−1} + … + (∏_{j≥2}L_j)ε_1, plus frame-transport error. | **Stated; no proof given in the text.** | L_i-Lipschitz restrictions. |
| §4.3 holonomy bound | ‖M−I‖₂ ≤ Σ(1−√W_e)+‖H−I‖₂. | **Imported** from the external RSITopology repo (not on disk). | |
| **Conj E** | A typed membrane improves the utility-safety frontier over scalar reward and over a spoofable-provenance membrane. | **Conjectured; unrun.** | |
| **Conj F** | Patch membership, transport reliability and holonomy predict counterfactual edit transfer beyond context identity. | **Conjectured.** The global-atlas version was rejected on a Qwen setting (external). | |
| §12 bounded first experiment | 5 conditions × 4 families × 8 seeds = 160 discovery episodes. 288 confirmation episodes comparing B1, T1, T2 (4 families × 24 seeds). | **Registered design; unrun.** | |

### (c) Empirical campaigns

Source: manifests under `[A]/experiments/*/manifest.json`, with results from `[A]/REPORT.md` and `[A]/PROGRESS.md`.

| Campaign / hypothesis | One-sentence statement | Status |
|---|---|---|
| geometry_averaging_v1 **H1** | Density-only mean-field one-step error and pair covariance decline with dimension in full Moore neighbourhoods. | **Qualified support.** Confirmatory Moore MAE slope −0.00880 per dimension; zero error often meant extinction. |
| geometry **H2** | Holding degree at 12 removes the dimension trend, so degree rather than dimension explains the closure improvement. | **Failed-and-reported.** The fixed-degree slope was more negative (−0.03515). |
| geometry **H3** | Literal B3/S23 on growing Moore neighbourhoods collapses to extinction. | **Supported within sample.** All 6 confirmatory/holdout cells at dimensions 4–5 were extinction-only. 20 of 27 numeric closure passes were rejected by the activity overlay. |
| graph_state_v1 **H1** / v2 **H1** | Rewired/random (v2: circulant-skip and random) graphs have larger spectral gap and lower final perturbation ratio than the ring in ≥80% of paired units. | **Failed twice, reported.** |
| graph_state_v1 **H2** | Adding normalized-Laplacian spectral gap to a baseline of intercept, coupling and log₂(state dim) improves holdout RMSE of log₁₀ final perturbation ratio by ≥5%. | **Supported:** 6.11% (0.90405→0.84878). |
| graph_state_v2 **H2** | The same, with frozen coefficients on unseen degrees (4/8), sizes, dimensions (4/12), couplings, seeds and topology. | **Supported:** 12.30% (0.65325→0.57290). Registered as `accepted_model_only_predictive_macrovariable` in `ontology_registry.json`. Necessity, mediation and uniqueness not supported. |
| discovery_curriculum **H1–H3** | A calibrated investigator beats the best control by ≥0.20. Set-identified tasks score ≥0.90. Always-abstain is non-dominant. | **Supported.** Holdout 0.92795 vs proxy 0.35812 vs always-abstain 0.24938; margin 0.56983. Evidence score 1.0. Avoidable-abstention rate 85.71%. The reference policy "was constructed to use the exact finite-world solution", so no learned-investigator claim. |
| confinement_transfer **H1–H3** | Evolutionary schedule search beats compute-matched random search by ≥0.10 mean kernel-escape rate; ≥80% of pairs favour it; validity gates hold. | **Supported at point estimate.** 0.59661→0.70729 (+0.11068), 12/12 pairs, bootstrap 95% [+0.08307, +0.13620] includes values below 0.10. Boundary: may be front-loading. |
| alt_physics_atlas **H1** | Literature-informed profiles are enriched over controls. | **Not supported as stated.** Equal-diffusion Gray-Scott passed every fresh episode. |
| alt_physics **H2, H3, H4** | Regime distribution is substrate-specific (I(F;R)=0.866 and 0.839 bits). Profile differences exceed dimension differences (ratios 3.16 and 3.00). Goodhart controls fail the conjunction (0/96 pass). | **Supported within sample.** Candidate occupancy: Gray-Scott 64/96, binary 16/96, cyclic 7/96. |
| pixie_sanctuary_v1 **H1–H4** | Preferred actions give visible, bounded, persistent, substrate-specific responses. | **Supported within sample.** |
| pixie_folded_cavern_v1 **H1** | Axis probes resurface ≥2 critters at ≥75%. | **Supported** (Bitlichen and Moss 8/8, 4/4). |
| folded cavern **H2** | Fibre-column actions give at least as much visible response as surface-local ones. | **Failed-and-reported.** |
| folded cavern **H3** | No fixed-degree globalization. | **Not supported as written.** 8 events, all at dimension 2. |
| folded cavern **H4** | Response class depends on depth (0.67350 and 0.62924 bits). | **Supported.** |
| adventure_verifiers_v1 / chronicle_gate_adventure_v1 **H1–H3** | Valid traces pass. Every one-at-a-time tamper is rejected. Each tamper triggers its predeclared verifier. | **Supported for the enumerated fixtures.** 4/4 valid, 36/36 tampered rejected and targeted, 4/4 replays exact. |
| agent_mechinterp_harness_v1 **H1–H4** | Linked replay; ≥0.95 probe accuracy; ablation/patching effects; tamper rejection. | Reported as a passing wiring canary (README). No per-hypothesis numbers in the docs. Makes "no cognition claim". |
| chronicle_v1 **H1** | Byte-exact replay. | Operational. |
| graph_investigator_gym_v1 (`evidence/knowledge_card.md`; **absent from README/PROGRESS tables**) | At a fixed six-query budget, an EIG investigator predicts unqueried contrasts better than random. | **H1 supported:** confirmatory +18.020% [0.1047, 0.2606], holdout +16.349% [0.1017, 0.2249]. **H2 not supported:** sheaf_eig = local_eig to the digit (0.000%). **H3 not supported:** holdout false-single-explanation rate 0.75, Jaccard 0.53. **H4 instrument-pass** (audit-only constitution). |

## I.3 Explicit open problems, limitations and future work

**Stego-swarm paper §7 "Limitations" and `[A]/PROGRESS.md`:**
- Delivery is linear min-unmet, single-round.
- "the reflected-walk balances and inter-member demand of the lnmath paper's general case are absent, and with them the √N regime"; the departure process (turnover cost) is absent; PROGRESS lists "strategic departure".
- The trained warden is a diagonal LDA fit on twelve seeds, so its floor at zero channel value is "partly overfitting".
- The public-rate sweep is seven points on one demand family.
- "A higher-capacity warden, more seeds, and richer attribution would map how far the trace-side signal can be pushed."
- "the capacity-versus-detectability curve the paper reserves for a bounded appendix is not computed."
- Thresholds are demonstration gates, not predictions.
- `stego_swarm_limit_v1/README.md` "Non-claims": no Lightning, no real covert communication, no "autonomous society", no real monitor performance.

**`[A]/REPORT.md` "Next falsification program" (1 to 5) and "What is not supported":**
1. Graph pairs separating spectral gap from clustering and path length, tested at unseen perturbation nodes, channels and horizons.
2. A real local investigator that registers a design before observing.
3. Competing coarse-grainings in set-valued tasks.
4. Non-monotone fibre dynamics, where front-loading should fail.
5. At least five fresh seeds per phase-map cell.
- Not supported: a universal critical dimension, emergence/life/cognition, a unique or causal role for spectral gap, learned-investigator generalization, "Real-world evasion, deception, or superiority of evolution over arbitrary optimizers".

**Other files:**
- `[A]/PROGRESS.md` "Remaining gate" column. Examples: edge-specific transport only if a holonomy claim is registered; refresh hashes when generators change.
- `[A]/papers/alt_physics_alife_distribution.md` §6 "Efficient next experiments" (Gray-Scott diffusion-ratio × autocatalysis factorial; cyclic threshold map; seeded Lenia) and §4.3 (equal-diffusion unresolved).
- `[A]/papers/mathematics_of_constitutional_alife.md`:
  - Header: the "Oixieology" name-resolution caveat.
  - §13: research phases 0 to 6.
  - Thm C proof absent.
  - Conj E/F.
  - §12 unrun.
- `[A]/experiments/graph_investigator_gym_v1/evidence/knowledge_card.md` "Next experiment": compare against an enforcing membrane.
- `[A]/experiments/chronicle_gate_adventure_v1/README.md`: mine natural gate-return paths.
- `[A]/GOAL.md` "Non-goals".
- `[A]/GOAL.md` Level 5/6 note: oracle-absent Level 6 is "transfer evaluation unless an external task supplies independently valid labels."

## I.4 Mathematical tools used

- Integer concave separable optimisation (greedy marginal = exact ceiling) and water-filling placement.
- Thinned (Binomial) observation models, inverse-variance fusion, deterministic bootstrap CIs, Jeffreys Beta intervals.
- Mann-Whitney ROC AUC wardens (scalar capital and trace statistics), top-k concentration, Gini, member-attributed diagonal LDA fit on discovery+confirmatory and scored on holdout.
- Binomial mean-field closure for totalistic CA; pair covariance; correlation proxies; mutual information (family/regime, depth/response class); paired perturbation divergence.
- Gray-Scott reaction-diffusion (explicit Euler), cyclic excitable CA, and graph CA x_{t+1}=tanh((1−η)tanh(Mx_t)+ηAx_t/d).
- **Normalized-Laplacian spectral gap** (dense symmetric eigendecomposition) as a linear regressor, with a frozen-coefficient out-of-sample RMSE gate.
- Evolutionary versus random schedule search with paired bootstrap.
- Bayesian expected-information-gain query selection with a sheaf-smoothed prior; Brier score and credible-set Jaccard.
- Hidden-oracle episode grading with registration forecasts, set-identification and point-unidentifiability certificates, and abstention scoring.
- Theory layer: Galois connections and abstract interpretation, cellular sheaves and sheaf Laplacians, viability and shields, replicator-mutator and Price equations, information bottleneck, DRO, PAC-Bayes, RCPS, polar-decomposition holonomy, Banach fixed point.
- SHA-256 receipts, canonical event hashes, deterministic replay, and one-at-a-time tamper matrices.

## I.5 Recurring methodological commitments (with where stated)

- **Preregistration and abstention.** `[A]/GOAL.md` "Registration and abstention": before seeds are drawn, register the target, smallest effect of interest, precision, error target, design, budget, stopping rule and a forecast. Abstention is rewarded only when an oracle certificate shows unreachability; "unresolved episodes are censored".
- **Frozen disjoint seeds.** Every manifest's `seed_plan` (discovery/confirmatory/holdout, disjoint). `[A]/REPORT.md` "Overall methodology": "Discovery seeds could propose … fresh confirmation and holdout … under a frozen protocol". The experimental unit is the world or episode, never ticks.
- **Sealed, non-operational.** `[A]/experiments/stego_swarm_limit_v1/README.md` "Safety boundary": no wallet, key, network, payload or encoder; the covert channel is a scalar. Checked by `src/verify_stego_swarm_limit_artifacts.py`.
- **Verifier scripts that recompute from raw.** Per-campaign `src/verify_*_artifacts.py`, with `--portable` mode and hash/schema/gate checks. The stego verifier "recomputes the holdout aggregates, the pooled warden factorial, and the out-of-sample trained attributed warden from `raw_episodes.jsonl`".
- **"Evidence for monitors and not a method for evaders".** Exact phrase in the paper's abstract. Also the README ("defensive security research … evidence for monitors, not a tool for evaders"), manifest `"benefit": "defensive"`, and paper §8 ("A defender reads these as a reason to put the measurement where the structure is").
- **Two discovery ledgers.** `[A]/GOAL.md` "Two separate discovery ledgers": a generator-coverage archive (`registries/generator_coverage_*.json`) and an ontology registry (`registries/ontology_registry.json`). "Do not use one scalar called novelty for two different achievements."
- **Epistemic ladder.** `[A]/GOAL.md` "Epistemic ladder". Axes are oracle present/absent × point/set identified. Levels 1–4 are bootstrapped from planted effects; the Level 4/5 boundary turns point targets into set-valued ones; the Level 5/6 boundary removes the oracle. `[A]/REPORT.md` adds the exposure ladder "eligibility → activation → execution → dosage → outcome". `[A]/experiments/agent_mechinterp_harness_v1/STRATEGY.md` has a 5-step evidence ladder.
- **Metric firewall** (select / evidence / hazard disjoint). `[A]/GOAL.md` "Metric firewall" and the constitutional paper §10.
- **Negative knowledge preserved.** `[A]/REPORT.md` step 8; ontology registry `known_failures`.
- **Claim-scope tags and knowledge cards.** `claim_scope: model_only`; GOAL "Completion criteria".

---

# PART II. `[S]` Spiral

## II.1 Summary

- Spiral treats Lightning Network liquidity as a capital problem for populations of autonomous agents.
- **Core claim** (current tex abstract): on Lightning, routing intelligence is worth between a third of a point and one point of payment success and capital placement six. The cause is a prefix cut-conservation bound that no routing policy relaxes.
- The paper then asks where that bound goes under:
  - an Ark server-mediated object;
  - a BIP-448 multiparty channel (hyperedge);
  - a LayerTree covenant tree.
- It adds a claim-once Sybil-bounded reward registry and a BitVM3 escrow.
- Section 7 asks what a population under common control can earn and who can observe it. The answer is that gain is bounded by authenticated capital under stationary demand, so the steganographic question is "second-order".
- Everything is "defensive and non-operational": a simulator on sampled public topology (a July 2023 gossip snapshot) or a TypeScript reference model with a simulated proof system.
- Alongside: the superseded first manuscript (*Connector Calculus*), an adversarial audit (*Liquidity on Trial*, *Adversarial Critique*, Swarm Arena), a sealed hive/financial-abuse lab, and an unrelated evaluation-design programme (sandbagging/behavioural-shift evaluation, design calculus, testbed, Prime Intellect atlas).

## II.2 Formal results

### (a) Current paper `[S]/paper/tex/main.tex`

All "measured" values are deterministic reference-model or simulator outputs, not live measurements.

| Name (section) | Statement | Status | Assumes |
|---|---|---|---|
| **Lemma 1** prefix cut bound (§3.2) | For every A⊆N and n: O_A(n)−I_A(n) ≤ S_A(0)+K_A(n), and I_A(n)−O_A(n) ≤ S'_A(0)+K'_A(n). | **Proved** (two lines). | Settled crossings conserve per-channel balance; balances ≥ 0; capacity events accounted in K. |
| **Prop 1** policy invariance (§3.2) | Lemma 1 holds under every routing policy, including exact balance knowledge. An oracle's advantage "is confined to the attempt budget" and cannot raise net delivery across any cut. | **Proved.** The text notes states may differ between policies. | |
| **Remark 1** scale of pooling gain (§3.3) | Sum-of-peaks / peak-of-sum is O(√N) for signed uncorrelated imbalance, rises 1→π/2 for reflected (start-from-nothing) walks at zero drift, and is ~1 under shared accumulation. | **Derived by order-of-magnitude/diffusion argument, not a theorem.** The π/2 case is exhibited in the model; "the √k regime of Remark 1 is stated and not exhibited" (§9). | Independent per-round inflows. |
| Sim results, Table "sim" (§3.4) | Bounded retries +5.14 points; terminal-feedback learning +0.35 (inside the equivalence band); exact hidden state +1.11 (attempt budget, not information); failure-aware placement over random +6.13 (4.91–7.35) under stationary hotspots and ≈0 after a shift. | **Measured**, sealed preregistered campaigns, 28 topology clusters. | Synthetic capacities and balances on a 2023 gossip topology. |
| **Prop 2** cross-class conservation (§4.2) | After all clocks fire or abort, Σℓ + fees + slashed = initial + external funding; holds with pending holds h included during pending intervals. | **Proved** (bookkeeping); witnessed in TS tests. | |
| **Prop 3** bound relocation (§4.3) | Under a server, O_A−I_A ≤ V_A(0)+K^S_A(n) with Σ_A K^S_A ≤ B_S − W_S(n). The per-cut constraint becomes an aggregate constraint on the server's uncommitted capital; a coalition "cannot raise the sum". | **Proved** by definition. | Server co-signs every issuance. |
| Eq. ratio D_C/D_V ≈ H·Σf̂_a / (Vol·L̄ + H·f̂_S) (§4.4) | States when pooling pays. | **Approximate/conjectural**, evaluated in the model. | |
| Grid results (§4.5) | Expiry reading: the virtual output is not favoured (≈0 on few-steady, 0.97 oracle / 1.05 trailing on correlated drift). Round reading: favoured by 1.40–2.52 (oracle) and 1.06–1.52 (trailing) on uncorrelated many-agent cells; 1.11/0.99 on shared drift; not on few-steady. | **Model-computed.** The sign depends on an **unpinned implementation detail** (when the server recovers fronted value). The few-steady row "supports the direction and not the magnitude". | |
| **Lemma 2** hyperedge cut bound, **Prop 4** pooling inside a hyperedge (§5.1) | The Lemma 1 inequalities hold on a hypergraph. Inbound stock toward k agents is the single number ℓ_i(h); the hub faces one newsvendor problem on the peak of the group total. | **Proved.** | |
| §5.3 | Pool survives member failure with probability (1−p)^{k+1}; forced on chain at rate (k+1)λq. | **Derived, not measured** (§9). | Independent failure. A member that defects strategically does not obey this. |
| Hyperedge results (§5.5) | Zero drift: 1.30 (k=5), 1.44–1.47 (k=20), 1.50 (k=200) vs limit π/2. Draining drift: 1.65, 2.23, 2.76. Shared accumulation: 1.01 at all k. k=20 gets ~nine-tenths of the gain of k=200. | **Model-computed.** | Hub, no intra-group payments, static membership. |
| LayerTree terms (§4.4, §4.7) | Eq. (tratio); Eq. (contention): Δ(q)=Δ_L(⌈(β+q)/κ⌉+1); break-even receipts ≈23,000 sat/round at 10 sat/vB and 2%/yr. | Carried from the LayerTree draft's tables; "indicative"; the grid cannot confirm. | Assumption [C] (policy, not consensus). |
| **Lemma 3** identity splitting (§6.1) | With weights equal to distinct settled-object values, splitting a claimant leaves payout invariant up to rounding. | **Proved** ("obvious"). | |
| **Prop 5** Sybil-bounded weight (§6.2) | The total weight attributed to claims backed by object ρ is ≤ v_ρ regardless of the number of identities, except with negligible probability. | **Proved conditionally.** Requires knowledge-sound proof, PRF, and ZK for the privacy clause. Witnessed on finite cases with a **simulated proof system**. | Verifier's view of the settled set correct. Trusted setup (§9 third assumption). |
| **Prop 6** epoch bound (§6.3) | Under the epoch rule, weight per authority lineage per epoch ≤ value settled at epoch start, whatever the id churn. | **Proved conditionally**; a registry without the epoch rule accepts 8 claims on one object. | Attested successor links trusted from the server. |
| **Prop 7** enforceable bond (§6.6) | A false Assert is slashed by any single honest challenger at cost independent of B; a true Assert releases after Δ. | **Conditional** on BitVM3 assumptions. | Committee honest at setup, one honest challenger online, trusted Groth16 setup. |
| **Prop 8** coordination gain, conditional (§7.3) | Under Props 5–6 the coalition's authenticated weight is ≤ value of distinct settled lineages. Gain from placing a fixed budget with full knowledge of persistent demand is the stationary-hotspot effect (~6 points) and "nothing after a shift". Gain from coordinating "is bounded above by the stationary-placement effect on its own capital and is zero under demand shift, whatever the capacity of its channel." | **Conditional claim "in the tested model"**, a conjunction of three attack surfaces (registry/verifier view; demand persistence; a discriminating netting statistic). | See below. |
| §7.5 conjectures | Swarm runs its own Ark server; ramps remain observable; cross-server circulation defeats single-row observers; "swarm is the channel" under BIP 448; registry privacy is symmetric; enforceable side-contracts help cartels; same weights → coordination without a message that payment traces cannot distinguish; the authority field (principal co-signer with time-bounded delegation) is the policy lever. | **Conjectured; unrun.** | The text says "Six further possibilities" but has eight paragraphs. |
| App. C | Barnette-conjecture corollary for designed overlays (every edge avoided by some Hamiltonian cycle). | **Conditional on an unrefereed machine-generated preprint**; nothing else depends on it. | |

On the three conditions of Prop 8, the hive-lab precursor measured: "a network-wide gross-to-net churn ratio failed" and "the relays are several hundred times louder than background, which is a sanity check and not a result." Netting restricted to a claim's direct attesters "catches a reciprocal pair, misses a four-member relay, and saturates toward one when benign trade is dense". Repeated-cycle share "separates", with open survival against benign structure.

### (b) Superseded md draft

`[S]/paper/where_the_capital_bound_moves.md`: S1 cross-class conservation, S2 bound relocation, S3 Sybil-bounded weight, S4 enforceable bond, S5 coordination-gain bound. Same content as tex Props 2, 3, 5, 7, 8. §6.4 "The warden's test" names three computable statistics (repeated-cycle share; nullifier collision rate; service-versus-demand inconsistency). Its Exhibit B lists 17 passing tests; the tex says 21.

### (c) First manuscript and audit

Files: `[S]/paper/manuscript.md` (frozen at a0a3140; errata in `manuscript_errata.md`), `[S]/paper/liquidity_on_trial.md`, `[S]/paper/connector_calculus_critique.md`, `[S]/audit/*`.

| Name | Statement | Status |
|---|---|---|
| Manuscript Props 1–5 (§5, App. A) | Channel conservation; state bounds; closed-route node conservation; ghost non-executability; identity-split invariance. | **Proved**, restricted domains. The critique shows atomicity fails outside the simple-route domain. |
| Manuscript results (§9.2–9.5, 9.7) | Ghost connector +3.84 points (±0.49) over baseline, but only +0.20 over a random cross-cut connector (CI includes 0). Under a 90% lock on the top-2-betweenness edges, success 50.49%→67.60% (+17.12 ±1.66). Sybil-invariant reward at 1–32 identities. | **Measured**, synthetic. |
| Proof cards P1–P6 (§9.6) | P2b (endpoint rule beats random) not supported on the base topology; P5 (terminal-feedback beyond retries) not supported at the one-point bound; P6 supported. | Mixed; reported. |
| Critique C1–C8 | Rejection can partially mutate (161 of 312 adversarial walks); seeds omit PYTHONHASHSEED (105 vs 102 of 110; only 6 of 72 policy records reproduce); stock ≠ throughput (50 outward supports 200 outward, reordered fails 7 times); compile predicates not enforced; reward edge cases; service ≠ value; oracle needs two budgets; receipts don't identify privacy/emergence. | **Failed-and-reported** (counterexamples). |
| Liquidity on Trial **L1–L5** (§10) | Conserved capacity under settlement; bounded simultaneous reservations; rejection identity; conditional identity-partition invariance; value not identifiable from service records alone. | **Proved**, conditional. The reference ledger has 13 tests plus a 440-state grid. |
| Closed form (§11.1) | Advantage A(ρ,d,H)=½ Σ_{t=d+1}^{H} (2ρ−1)^t. At ρ=0.75: 0.498047, 0.123047, 0.029297 for delays 0, 2, 4. | **Exact toy**, 256 trajectories × 20 cells enumerated. |

### (d) Hive lab (`[S]/paper/hive_lab.md`, measured)

- 12 paired seeds, 120 rounds.
- Private unicast gives 94.45% payment success vs 97.14% ordinary. A giant component of 16 forms.
- At reciprocity threshold 0.70, emergence falls to 60% at repeat probability 0.70 and 20% at 0.90.
- Defensive financial-abuse evaluation, 20 paired seeds:
  - The observer saw 13.37% (benign), 11.69% (cyclic relay) and 10.88% (Sybil recycling) of events.
  - At threshold 0.55: precision 1.00, recall 0.225 (9 of 40), no false positives.
  - ROC AUC 1.00 on clean fixtures.
  - A threshold of 0.15 chosen on seeds 0–9 classified all of seeds 10–19 correctly.
  - Authors' reading: "a harness sanity check, not an estimate of field performance".
  - Naive gross-to-net churn failed: benign 12.63 vs ~7.56 for both labelled patterns.
- Capability frontier:
  - Adaptive over public +2.91 points (±1.04) normally and +6.19 under jamming.
  - Oracle = adaptive in delivery, with 2.64 fewer failed attempts per demand.
  - Demand-aware capital +14.56 points over no connector under jamming vs random capital +14.41.
  - Placement adds value only above a persistence/isolation boundary (9 of 16 cells survive Bonferroni).

### (e) Evaluation-design programme

Files: `[S]/paper/evaluation_design_calculus.md`, `evaluation_game_testbed.md`, `sandbagging_v3_protocol.md`, `prime_intellect_eval_atlas.md`, `[S]/docs/evaluation_harnesses.md`. All are **exact finite synthetic fixtures**; none is a model or agent result.

- Calculus §5: projection, disjoint-update, order-effect, renaming, utility-affine and mixture laws.
- Calculus §9: grim-trigger cooperation is sustainable iff δ ≥ ½.
- Testbed: observation-only Hide as a common Markov kernel obeys TV(H#P,H#Q) ≤ TV(P,Q); player-facing hiding changes the game (optimal value 1→½). Four non-interchangeable estimands: baseline gain, robust regret, discrimination gap, exploitability. A 320-score synthetic confirmation fixture; interaction sign test p=1/2048.
- Sandbagging v3 (frozen analysis rules, not results):
  - Block as the independent unit.
  - Equivalence band ±0.05 (90% interval inside).
  - Alpha/(2×agents) per confirmatory test.
  - Evidence grade 0–5.
  - "does not identify deceptive intent".

## II.3 Explicit open problems, limitations and future work

**`main.tex` §8 Preregistration — items 1–10, "none has been run" (Conclusion):**
1. Pin the recovery rule from the implementation.
2. Liquidity-duration grid.
3. Hyperedge grid, including turnover λ, q.
4. LayerTree cell.
5. Prover cost with a real proof system.
6. Identity-splitting and churn.
7. Warden rows: O_peer under C, O_server under V, a mixed two-server relay set.
8. Same weights vs same controller ("the prediction is that none separates them").
9. Enforceable collusion.
10. Capacity-versus-detectability appendix.

**`main.tex` §9 Limitations:**
- Three trust assumptions undischarged: Ark server honesty; BitVM3 committee/key deletion; Groth16 trusted-setup randomness.
- Nothing measured live.
- The model's scale depends on the unpinned recovery rule.
- The coalition bound's discriminating statistic "is demonstrated only on fixtures where the signal is hundreds of times louder than background".
- Channel balances are not a public settled set; "proofs do not cross" the public/private split.
- BIP 448 and LayerTree are drafts; π/2 is a diffusion limit; turnover cost "derived and not measured".

**`main.tex` §7.3 (explicitly open):**
- Whether the cycle statistic "survives benign structure in which short cycles through a busy node recur for ordinary reasons is open, and a coalition that controls its own rate can stay under any fixed threshold."
- Cross-server circulation: "This is the fixture to build."

**Other files:**
- `[S]/paper/where_the_capital_bound_moves.md` §8 table, "Still open" column.
- `[S]/paper/liquidity_on_trial.md` §7.1, §13, §14: unresolved obligations, "Live execution is a new experiment with new authority".
- `[S]/paper/connector_calculus_critique.md` §9.
- `[S]/paper/manuscript.md` §12 (12.1–12.7) and §13 "next research gate".
- `[S]/paper/hive_lab.md` "Research questions" and "Later campaigns need harder benign controls, imperfect common control, topology variation, intensity sweeps, and a sealed final holdout."
- `[S]/paper/sandbagging_v3_protocol.md`: "Actual multi-agent validation remains outstanding"; external-validation gap.
- `[S]/paper/evaluation_design_calculus.md` §11: compiler and open-game semantics are future goals.
- `[S]/README.md` "Scope": zk proving intentionally disabled.
- LayerTree UC proof "in a full version we have not read" (`[S]/paper/layertree_insertions.md`).

## II.4 Mathematical tools used

- Conservation / prefix cut identities (max-flow/min-cut flavour); newsvendor and multi-location newsvendor (Eppen).
- Reflected random walks and running maxima (√N vs π/2); Markov two-region persistence.
- Liquidity-duration ratios and a server-liability bound.
- Typed resource tuples and clocked ledgers.
- ZK relations: Merkle membership, PRF nullifiers, Groth16; BitVM3 cost model; MuSig2; Merkle-sum trees.
- ROC AUC detectors; repeated-cycle share; gross-to-net churn.
- Student-t cluster-robust CIs over topology clusters; Bonferroni/Holm; exact sign tests; equivalence bands; Neyman allocation.
- Markov kernels, composition, TV distance and data-processing; Möbius/inclusion-exclusion interaction expansion; Nash/Bayes/repeated-game analysis; primal/dual witnesses.
- Exhaustive enumeration (440 ledger states; 256 trajectories × 20 cells); Hamiltonian-cycle search.
- SHA-256 receipts and hash-bound bundles.

## II.5 Recurring methodological commitments

- **Defensive / non-operational.**
  - `[S]/README.md` first paragraph ("The work is defensive and non-operational").
  - `[S]/paper/hive_lab.md` "Safety boundary" (no wallet, node, payload, transport; "no attempt to optimize evasion").
  - The adversarial fixtures are "for testing monitors, not operational strategies".
- **Preregistration, sealed holdouts, frozen analysis.**
  - `[S]/README.md` ("preregistered campaigns").
  - `main.tex` §8.
  - `[S]/paper/manuscript.md` App. B.5 ("Keep topology samples outside the calibration indices sealed").
  - `sandbagging_v3_protocol.md` "Frozen analysis".
  - `[S]/docs/evaluation_harnesses.md` ("keep the final holdout sealed").
- **Verifier scripts and hash-bound receipts.** `[S]/audit/validate_bundle.py`, `bundle_manifest.json`, `scripts/verify_evaluation_design_calculus.py` and `verify_evaluation_game_testbed.py`, and the TS model tests that "witness the propositions on finite cases".
- **Preserved dispute history.**
  - `[S]/audit/README.md` "Preserve the dispute history".
  - Errata beside frozen files.
  - `liquidity_on_trial.md` §2 "five dispositions": surviving theorem, implementation counterexample, scope failure, inferential limitation, unresolved obligation.
- **Evidence status ladder.**
  - `[S]/paper/evaluation_design_calculus.md` §11 item 9: "algebraic identity, finite verified example, synthetic mechanism result, observed-controller result, or externally validated claim".
  - `[S]/audit/README.md` "Evidence classes".
  - The sandbagging 0–5 grade.
- **Behaviour is not intent.** Repeated: "records `intent_identified: false`".
- **Two ledgers and the explicit ALife-style firewall are not in Spiral**, but the same select/evidence/hazard discipline appears in the calculus ("Freeze sampling, outcome scale … before confirmation").

---

# PART III. Cross-repository

## 6. Transferable results and exact mappings

Mapping glossary (proposed, not in either repo):

| Source term | Defender-vs-swarm reading |
|---|---|
| coalition under common control | compromised or adversary-controlled sub-swarm |
| warden / monitor | defender's detection and monitoring layer |
| capital (authenticated, settled) | authenticated hardware, attested compute, spectrum, battery, controllable units |
| covert channel | adversary C2 or coordination channel |
| demand | targets, tasks, or environment the adversary must forecast |

| # | Source statement (quoted) and location | Defender reading | Where the mapping strains |
|---|---|---|---|
| 1 | "Lemma 1 holds under every routing policy, including a policy with exact knowledge of all balances. A policy affects which attempts settle, not the identity that settled crossings satisfy." (`main.tex` §3.2, Prop 1) | No adversary intelligence relaxes a conservation bound on a resource that must cross a boundary. Cut A = trust boundary (clean vs compromised partition). Stock+K = adversary-controllable resource. | Needs a conserved, partitionable resource. Capture or theft creates new "K", and the bound is only prefix-relative. Spectrum and power are not conserved this way. |
| 2 | Prop 1: "there is a finite C* … Q(C)=B for all C ≥ C*" (ALife paper §2). Here C*=10 bits, because ⌈log₂24⌉=5 and ⌈32/24⌉=2. | An adversary's C2 bandwidth buys nothing beyond a tiny threshold if C2 only carries a low-entropy allocation (B units × log₂L bits). That argues for spending the detection budget on commitments and capital rather than on "the wire". | "exact by construction" (H1). One placement after warm-up, never revised; no continual re-tasking, sensor fusion or feedback loop. The 10-bit threshold also means denying C2 below C* is impractical. Below C*, gain does rise with capacity. |
| 3 | "the delivered success collapses toward a floor when the demand the placement forecast moves after placement, while that optimal ceiling stays high … so the loss is a forecasting loss and not a capital one, and coordination does not rescue it" (ALife paper abstract; numbers 0.663→0.079, ceiling 0.671, shift gain 0.012). | Moving-target and reconfiguration defence. An adversary's pre-committed allocation is a forecast, and the defender moving what is defended invalidates it regardless of C2. Companion: A(ρ,d,H)=½Σ(2ρ−1)^t is a quantitative "persistence vs attacker deployment delay" curve (`liquidity_on_trial.md` §11.1). | The shift is exogenous and total (hotspots {0–7}→{8–15}), B<demand, and the adversary never re-observes. A real adversary adapts. No partial-shift sweep exists. |
| 4 | "A monitor that wants the common-control signal should read the capital and the registry, not the wire — not because the wire is always blind, but because the capital is never." (ALife paper §4) | Monitor control-plane commitment events (credential issuance, attestation enrolment, firmware loads, resource grants) rather than traffic content. Trained attributed LDA = ML traffic classifier. | Capital-warden AUC 1.00 is "structural". It separates the one-pot pooled controller from the M-pot shared-weights population, two structures the experimenter built. An M-pot coalition looks independent on that axis. No adaptive evader is modelled. 12 holdout seeds, one demand family, loose gates. |
| 5 | "the total weight the registry attributes to claims backed by ρ is at most v_ρ, whatever the number of claimant identities" (Prop 5), plus the epoch rule (Prop 6). | Bound influence (votes, quorum weight, resource share) by attested physical platforms, not software identities, which defeats Sybil nodes in swarm consensus. Epoch rule = periodic re-attestation so a re-enrolled or cloned platform isn't counted twice. | Conditional on a knowledge-sound proof system with trusted setup and a correct verifier view. It bounds Sybil multiplication, not capture or extraction of a real attested device. Simulated proofs only. |
| 6 | "agents sharing weights share tie-breaking and converge on the same fee … without a message … we conjecture that payment traces alone cannot [distinguish]" (`main.tex` §7.5) | A homogeneous swarm shows correlated behaviour without any C2, so correlation alone is not evidence of a channel. It also implies monoculture risk and favours diversity (`manuscript.md` App. C, "Model monoculture"). | Conjecture, unrun (prereg item 8). |
| 7 | "an authority that includes a principal-held co-signer with time-bounded delegation, so that an agent spends within a budget and window without a co-signature and beyond it needs one." (`main.tex` §7.5, "The lever is the authority field") | Bounded delegated authority for autonomous platforms with escalation to a human principal. | Script cannot expire a spend. A co-signature requirement is exposed to comms denial and cuts against autonomy-under-jamming. Lightning-specific. |
| 8 | "If each member independently fails or defects within the horizon with probability p, the pool survives it with probability (1−p)^{k+1}" and "A hyperedge makes every member pay for every other member's defection." (`main.tex` §5.3) | Tightly coupled unanimous-signing swarm cells are fragile to one captured or non-cooperating node. Tight coupling is a liability. | n-of-n by construction; real swarms use quorums or BFT. The text itself says independence is wrong for strategic defectors. |
| 9 | Remark 1: pooling buys "√N on signed imbalance, a constant near π/2 … for agents with nothing to spend down, and nothing on correlated accumulation." | Pooled reserves (energy, comms, munitions) give limited gain when members drain together. | Heuristic; reflected case only exhibited. Physical reserves are not signed random walks. |
| 10 | "Adding spectral gap to coupling and log₂ state dimension improves holdout RMSE … by at least 5%" (6.11%; frozen 12.30%) (`graph_state` H2; `ontology_registry.json`). | Comms-mesh resilience: node = drone, state = local estimate, perturbation = one spoofed or compromised node's state, recovery predicted by λ₂ of the normalized Laplacian. A design and monitoring variable. | Predictive only. The directional claim failed twice; confounded with clustering and path length. Static regular graphs, degrees 4–8, N=96–192; one single-shot perturbation (horizon 80); benign tanh consensus; no wireless or time-varying topology. |
| 11 | "Reward abstention only when an oracle-backed identification certificate … shows that the target was unreachable" (`GOAL.md`). Curriculum holdout 0.92795 vs always-abstain 0.24938. | Scored, calibrated attribution with abstention for incident analysis. | The reference policy uses the exact solution. In the investigator gym, EIG policies over-claim (false single-explanation rate 0.75–0.81, H3 not supported). |
| 12 | Adventure verifiers: eight hard verifiers (canonical event hashes, action receipts, causal timing, resource ledger, `witness_scope`) reject 36/36 tampers; `witness_scope` rejects "a fact [that] can be true … and still be rejected if the adventurer never observed it". | Tamper-evident, attributable agent telemetry and forensic log verification; "claims only from observed evidence". | Enumerated fixtures only; no adaptive attacker; needs a trusted root. |
| 13 | HardAdmit plus explicit ABSTAIN/ASK/ESCALATE/SAFE-STOP bottoms (Prop 1 §3.3); Thm B shield; Prop 2 (selection cannot guarantee closure). | Runtime-assurance membrane around a learning or self-modifying controller, with attested provenance and a fail-safe state. | Model-level theory, nothing run; Thm C unproved in text; Conj E open. |
| 14 | `hive_lab.md` abuse evaluation: precision 1.00 / recall 0.225 at 0.55; AUC 1.00; naive churn fails; observer coverage 11–13%. Repeated-cycle share is the feature that separates. | Flow-structure detection of coordinated or compromised nodes under partial observation. | Clean fixtures; authors disclaim field performance. |
| 15 | Capability frontier: "Perfect balance knowledge changes privacy cost, not the delivery ceiling"; adaptive probing yields 2.64 more failed attempts per demand than the oracle. Under 90% edge locks, connector capital +17.12 ±1.66 points. | An adversary's probing leaks observable failures. Path diversity is the anti-denial lever. | Free-failure semantics; the lock is not RF jamming. |
| 16 | Behavioural-shift (sandbagging) eval: matched control vs role-visible probes in blocks, preregistered grade 0–5 ("does not identify deceptive intent"). Observation-only Hide obeys TV(H#P,H#Q) ≤ TV(P,Q). | Detecting an autonomous controller that behaves differently when it believes it is audited. Log before aggregating or redacting. | Synthetic only; "Actual multi-agent validation remains outstanding". |
| 17 | Confinement transfer: evolutionary schedule search produces stronger kernel-escape stress-tests than random search "while preserving the original proxy and closure gates". | Red-team generator for proxy-monitor blind spots (the monitor sees z; the hidden y drifts). | **Dual-use**: it is an evader-side search. The README says it is "not evidence of real-world evasion". Front-loading confound. Keep wording within the "evidence for monitors" commitment. |

**Ranking by fit to an asymmetric defender-favoured thesis (strongest first):**
1. Rows 1, 5, 3: bounds that hold for any adversary intelligence, plus the Sybil bound and the forecast floor.
2. Row 4 and Prop 8: the monitoring-placement argument.
3. Row 2: C2 saturation, with the caveats above.
4. Rows 7, 8, 13, 12: architecture and verification.
5. Row 10: weakest evidence.
- No defender-versus-attacker cost-ratio result exists in either repo. All claims are about bounding adversary gain, not defender cost.
- Nothing is measured on a swarm, a radio link, or a drone.

## 7. Existing mentions of drones, swarms, warfare, defence, Taiwan, 6GW, cyber

**Terms with no hits (checked repo-wide in source, docs, JSON and PDF text; `.bib` files and git-ignored/absent result directories excluded):**
- "Taiwan", "6GW", "sixth generation", "warfare", "military", "UAV", "battlefield", "cyber", "national security".

**"drone" (ALife only):**
- It is a cell type: `drone`, `drone_mother`, `drone_dribble_cost` in `[A]/src/alife.py` (lines ~89, 118–148, 258–409, 475–546, 987–1061) and `[A]/src/doctor_manhattan_project.py:405`.
- `[A]/README.md` "Mechanics added": "`drone_mother` creates brood (`egg` or `drone`)".
- This has nothing to do with UAVs.

**"swarm":**
- ALife: `[A]/papers/steganographic_swarm_capital_limit.md`, `[A]/experiments/stego_swarm_limit_v1/*`, `src/stego_swarm_limit.py` and `stego_swarm_live_probe.py`, `[A]/README.md` and `PROGRESS.md`.
- Spiral:
  - `main.tex` §7.5 "What a swarm does with the objects" and the abstract.
  - `manuscript.md` §6.1: "The phrase **agent swarm** is therefore defined operationally. It means multiple policy processes with possibly shared objectives, information, software lineage, or capital control … The relevant unit for risk is the control and capital domain, not the number of keys."
  - `liquidity_on_trial.md` §2.1 "What the swarm is, and is not": the "audit swarm" of language-model reviewers vs scripted payment agents.
  - `[S]/audit/SWARM_ARENA.md`.
- All of these concern Lightning payment agents or reviewers, not physical swarms.

**Defence / adversary / attack vocabulary that already exists:**
- ALife:
  - `"benefit": "defensive"` in the stego manifest.
  - README: "defensive security research".
  - Hazard metrics; adapted-adversary language in `generator_coverage_baseline.json` ("This is a pressure ladder … not an adapted-adversary generator").
- Spiral:
  - "defensive adversary model" (`manuscript.md` §7: Sybil splitting, liquidity mirage, jamming and griefing, probing, wash flow, collusive capture, "7.7 Steganographic coordination risk", model poisoning and demand spoofing; Appendix C red-team matrix).
  - "jamming" (the 90% lock experiment and the agent-capability jamming arm).
  - "Defensive financial-abuse evaluation" (`hive_lab.md`).
  - "blue-team sandbagging evaluation" (`README.md`, `docs/evaluation_harnesses.md`).
  - The contention-attack signature on a shared output (`main.tex` §4.7).

## Items to double-check before citing

1. Which paper: tex (current) vs md (superseded). Cite tex §7 and prereg items 8 and 10, not the ALife manifest's "7 and 9".
2. `[A]/experiments/stego_swarm_limit_v1/manifest.json` `analysis.multiple_comparisons` says "All three frozen hypotheses" but four (H1–H4) are defined; stale text.
3. The stego H1–H4 gates were set around observed behaviour, so "supported" means "direction demonstrated", not "preregistered prediction confirmed".
4. The trace-AUC sweep has an AUC of 0.41 (below chance) in the middle, so it is non-monotone.
5. ALife `results/` is absent here, so no number was re-derived.
6. The graph investigator gym is in neither the README nor PROGRESS tables.
7. `main.tex` §7.5 says six possibilities but lists eight.
8. The git author of the stego commits is "Claude".