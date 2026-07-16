# Where Structured Activity Lives in a Small Alternative-Physics Atlas

**A deterministic CPU study of lattice physics, dimension, and chemistry**
ALife repository technical paper, 2026-07-16

## Abstract

We ask where persistent, spatially organized activity occurs in a small, replayable atlas of alternative lattice physics. The study crosses three deterministic families—binary totalistic cellular automata, Gray–Scott reaction–diffusion, and cyclic excitable automata—with dimensions 2–4, four profiles per family, and disjoint discovery, confirmatory, and larger/longer holdout seeds. All worlds use a periodic lattice, a fixed degree of 12, and about 4,096 sites in discovery/confirmation. A six-axis measurement portfolio replaces any scalar “complexity” score.

Across the 288 fresh confirmatory and holdout episodes, operational active-and-structured candidate occupancy was 64/96 for Gray–Scott (0.667, Jeffreys 95% interval 0.569–0.755), 16/96 for binary automata (0.167, 0.103–0.251), and 7/96 for cyclic automata (0.073, 0.033–0.138). Candidate occupancy declined from 47/96 in 2-D to 24/96 in 3-D and 16/96 in 4-D. Physics family nevertheless explained more of the regime distribution than dimension in the declared range: mutual information between family and regime was 0.866 bits in confirmation and 0.839 bits in holdout, while the profile-to-within-profile-dimension occupancy-range ratio was 3.16 and 3.00.

The central negative result is equally important. An equal-diffusion Gray–Scott mechanism control passed the operational candidate conjunction in every fresh episode. Thus this atlas locates reproducible **pattern candidates**, not complex life, organisms, or open-ended evolution. Static and global-churn controls did their intended job: all 96 retained high values on at least one tempting scalar diagnostic, while none passed the conjunction.

## 1. Literature shortcut and question

Reaction–diffusion systems are a natural low-compute prior because diffusion-driven symmetry breaking goes back to Turing’s mathematical morphogenesis model ([Turing 1952](https://doi.org/10.1098/rstb.1952.0012)). Pearson then showed that a finite-amplitude perturbation of the Gray–Scott system can produce irregular spatiotemporal patterns, dividing spots, and local overcrowding collapse ([Pearson 1993](https://www.osti.gov/biblio/6385823)). Later work found stable localized moving patterns in a narrow two-dimensional Gray–Scott region ([Munafo 2015](https://arxiv.org/abs/1501.01990)) and mapped Gray–Scott pattern boundaries with Fisher information ([Har Shemesh et al. 2015](https://arxiv.org/abs/1512.02077)). These results justify sampling a few known productive neighborhoods instead of searching a large chemistry grid.

For discrete excitable media, Fisch, Gravner, and Griffeath define cyclic automata in which a color advances when enough neighbors have its successor color; random initial conditions can self-organize into traveling waves and spirals ([Fisch, Gravner, and Griffeath 1991](https://arxiv.org/abs/patt-sol/9304001)). This supplies a second inexpensive physics family. The binary arm reuses the repository’s existing fixed-degree geometry machinery rather than repeating a broad rule search.

The broader ALife literature also tells us what *not* to infer. Langton proposed a relation between phase transitions and emergent computation ([Langton 1990](https://www.sciencedirect.com/science/article/pii/016727899090064V)), but a direct re-examination produced materially different results and rejected a simple universal interpretation of the critical parameter ([Mitchell, Hraber, and Crutchfield 1993](https://arxiv.org/abs/adap-org/9303003)). Lenia demonstrates that continuous automata support many autonomous forms and a mapped parameter hyperspace ([Chan 2019](https://arxiv.org/abs/1812.05433)), including extensions to higher dimensions ([Chan 2020](https://direct.mit.edu/isal/article/doi/10.1162/isal_a_00297/98400/Lenia-and-Expanded-Universe)), but many forms were found through interactive or evolutionary search. We therefore reserve Lenia for a seeded follow-up rather than spend this atlas on an expensive search. Finally, the MODES work argues for multiple hallmarks rather than a binary or single-metric open-endedness judgment ([Dolson et al. 2019](https://direct.mit.edu/artl/article/25/1/50/2915/The-MODES-Toolbox-Measurements-of-Open-Ended)).

Our bounded question is:

> Within three declared deterministic lattice families, where does a frozen portfolio detect persistent active-and-spatially-structured dynamics, and how is that empirical regime distribution associated with family, profile, and dimension?

The claim scope is model-only and descriptive.

## 2. Models and experimental design

Let the world be the periodic lattice

\[
\Lambda_d=(\mathbb Z/L\mathbb Z)^d,
\]

with a deterministic offset set \(\mathcal O_d\) satisfying \(|\mathcal O_d|=12\) and spanning every axis. Holding degree fixed limits one obvious dimension confound, although the resulting offset sets are anisotropic and use longer-range edges in lower dimensions.

### 2.1 Physics

For the binary automaton, with \(s_t(x)\in\{0,1\}\),

\[
n_t(x)=\sum_{o\in\mathcal O_d}s_t(x+o),\qquad
s_{t+1}(x)=
\begin{cases}
1,&s_t(x)=0,\ n_t(x)\in B,\\
1,&s_t(x)=1,\ n_t(x)\in S,\\
0,&\text{otherwise}.
\end{cases}
\]

The two dynamic profiles are a degree-scaled fraction band and literal \(B3/S23\). Identity and global bit-flip rules are static and high-turnover nulls.

For the cyclic automaton, \(s_t(x)\in\{0,\ldots,q-1\}\),

\[
s_{t+1}(x)=
\begin{cases}
s_t(x)+1\pmod q,&
\sum_{o\in\mathcal O_d}\mathbf 1\{s_t(x+o)=s_t(x)+1\pmod q\}\ge \tau,\\
s_t(x),&\text{otherwise}.
\end{cases}
\]

We test \((q,\tau)=(3,1)\) and \((6,2)\), plus frozen \((6,13)\) and global-advance \((6,0)\) nulls.

For Gray–Scott concentrations \(u,v\in[0,1]\),

\[
\begin{aligned}
\dot u &= D_u\Delta u-uv^2+F(1-u),\\
\dot v &= D_v\Delta v+uv^2-(F+k)v,
\end{aligned}
\qquad
\Delta z(x)=\frac1{12}\sum_{o\in\mathcal O_d}z(x+o)-z(x).
\]

Explicit Euler updates use four solver steps per recorded tick. The two literature-informed discrete profiles are \((F,k,D_u,D_v)=(0.022,0.051,0.16,0.08)\) and \((0.035,0.060,0.16,0.08)\). Repository labels `pearson_mitosis` and `pearson_spots` are mnemonics, not exact replications of Pearson’s nondimensional discretization. Equal diffusion \(D_u=D_v=0.12\) and reaction-off diffusion are mechanism limits. Every Gray world starts with a finite central concentration patch and small seeded noise.

### 2.2 Ensemble

The complete factorial slice contains

\[
3\ \text{families}\times4\ \text{profiles}\times3\ \text{dimensions}
\times(2+5+3)\ \text{seeds}=360\ \text{episodes}.
\]

Discovery and confirmation use \(64^2=16^3=8^4=4096\) sites for 64 recorded steps. Holdout uses \(81^2=6561\), \(18^3=5832\), and \(9^4=6561\) sites for 96 steps. Seeds are disjoint. The baseline and a one-site perturbation are advanced in lockstep without post-initialization randomness.

Discovery exposed two measurement defects before confirmation: an arbitrary entropy ceiling of 0.98 rejected a spatially organized cyclic condition, and a half-torus comparison aliased periodic stripes. The frozen confirmatory classifier therefore uses the normalization ceiling \(H\le1\), and excess spatial information subtracts an equally sized deterministic affine-permutation null. A subsequently aborted execution found one invisible sub-bin Gray perturbation; both partial files were invalidated without inspecting outcomes, and the final perturbation was standardized to one adjacent concentration bin. These changes and hashes are recorded in the frozen manifest.

## 3. Mathematics of the empirical distribution

Gray fields are mapped to 64 fixed joint concentration bins; binary and cyclic states retain their native categories. Each episode produces

\[
X_e=(H_e,T_e,I_e^{\rm exc},R_e,G_e,U_e,C_e),
\]

where:

- \(H=-\sum_jp_j\log_2p_j/\log_2K\) is normalized state entropy;
- \(T\) is the mean fraction of sites changing category per recorded step;
- \(I^{\rm exc}=I(S_x;S_{x+o})-I(S_x;S_{\pi(x)})\) is normalized neighbor mutual information minus a frozen affine-permutation baseline;
- \(R=\bar T_{\rm late}/\bar T_{\rm early}\) is activity persistence;
- \(G=\max_t h_t/h_0\) is paired perturbation-response gain, with \(h_0=1/|\Lambda_d|\);
- \(U\) is the fraction of unique recorded state hashes; and
- \(C\) is compression ratio, retained only as a diagnostic.

After removing uniform collapse, short cycles, global churn, static structure, and transient decay in that order, an episode is an `active_structured_candidate` when

\[
0.08\le H\le1,
\quad0.002\le T\le0.8,
\quad I^{\rm exc}\ge0.005,
\quad R\ge0.35,
\quad G\ge2,
\quad \max_t h_t\le0.75,
\quad U\ge0.5.
\]

This is a conjunction, not a complexity index. The empirical conditional distribution for condition \(c\) is

\[
\widehat P_c(A)=\frac1{n_c}\sum_{e:c(e)=c}\mathbf 1\{X_e\in A\}.
\]

For candidate count \(y_c\), uncertainty is summarized by the Jeffreys posterior

\[
\theta_c\mid y_c\sim
\operatorname{Beta}\!\left(y_c+\tfrac12,n_c-y_c+\tfrac12\right).
\]

Dependence between physics family \(F\) and regime \(R_g\) is measured from the full contingency table:

\[
I(F;R_g)=\sum_{f,r}\widehat p(f,r)
\log_2\frac{\widehat p(f,r)}{\widehat p(f)\widehat p(r)}.
\]

Finally, a descriptive scale comparison divides the range of profile-aggregated candidate occupancies by the mean within-profile occupancy range across dimensions. It is not a causal effect estimator.

## 4. Results

### 4.1 Distribution by family and dimension

The following table pools only confirmatory and holdout episodes.

| Factor | Candidates / episodes | Occupancy | Jeffreys 95% interval |
|---|---:|---:|---:|
| Binary CA | 16 / 96 | 0.167 | 0.103–0.251 |
| Gray–Scott | 64 / 96 | 0.667 | 0.569–0.755 |
| Cyclic CA | 7 / 96 | 0.073 | 0.033–0.138 |
| Dimension 2 | 47 / 96 | 0.490 | 0.391–0.589 |
| Dimension 3 | 24 / 96 | 0.250 | 0.172–0.343 |
| Dimension 4 | 16 / 96 | 0.167 | 0.103–0.251 |

Family and dimension both matter, but not in the same way. The fresh-set family/regime mutual information is 0.855 bits when confirmation and holdout are pooled (0.866 and 0.839 separately). The profile-versus-dimension range ratio is 3.16 in confirmation and 3.00 in holdout: large profile changes dominate the mean dimension shift, even though aggregate candidate mass falls with dimension.

### 4.2 Reproducible phase slice

Cells show confirmatory occupancy / holdout occupancy.

| Family and profile | 2-D | 3-D | 4-D | Main observed regime change |
|---|---:|---:|---:|---|
| Binary fraction band | 1.00 / 1.00 | 0 / 0 | 0 / 0 | Spatial excess information falls below threshold |
| Binary literal B3/S23 | 1.00 / 1.00 | 0 / 0 | 0 / 0 | Active but spatially unstructured by this metric |
| Cyclic \(q=6,\tau=2\) | 0.80 / 1.00 | 0 / 0 | 0 / 0 | Becomes global churn in higher dimensions |
| Cyclic \(q=3,\tau=1\) | 0 / 0 | 0 / 0 | 0 / 0 | Short global cycle at degree 12 |
| Gray–Scott 0.022/0.051 | 1.00 / 1.00 | 1.00 / 1.00 | 0 / 0 | Four-dimensional activity decays late |
| Gray–Scott 0.035/0.060 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | Candidate across the sampled dimensions |
| Gray–Scott equal diffusion | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 1.00 | Mechanism control also passes |
| Gray–Scott diffusion only | 0 / 0 | 0 / 0 | 0 / 0 | Static structure or uniform collapse |

Across all fresh episodes, the regime distribution is 87/288 active-structured candidates, 32/288 active-unstructured, 16/288 global churn, 121/288 short cycle, 8/288 static structure, 8/288 transient decay, and 16/288 uniform collapse.

### 4.3 Hypotheses and controls

| Hypothesis | Result | Reason |
|---|---|---|
| Literature-prior enrichment | **Not supported as stated** | The prior pool is enriched (0.453 vs 0.167 in confirmation; 0.467 vs 0.167 in holdout), but equal diffusion accounts for every control pass, defeating the mechanism-control clause. |
| Substrate-specific distribution | **Supported within sample** | \(I(F;R_g)=0.866\) and 0.839 bits on fresh splits. |
| Profile differences exceed dimension differences | **Supported within sample** | Frozen range ratios are 3.16 and 3.00. |
| Scalar-metric Goodhart controls | **Supported within sample** | Candidate and null ranges overlap on entropy and turnover; 48 static and 48 churn episodes retain tempting scalar values, but 0/96 pass the conjunction. |

The equal-diffusion result prevents a stronger claim. It may reflect finite-amplitude transient organization, the normalized nonstandard stencil, finite horizon, or an insufficient portfolio. It does not rescue a claim of chemistry-like life; it shows that the current candidate definition is still broader than the intended concept.

## 5. What this says about alternative physics

1. **Two-dimensional locality is the safest cheap prior in this atlas.** Both binary profiles and the nontrivial cyclic profile produce fresh-seed candidates only in 2-D. At the same degree, higher-dimensional versions remain entropic and active but lose excess local information or become near-global churn.

2. **Reaction–diffusion is the broadest pattern-producing family sampled.** One Gray–Scott profile persists through 4-D, and the other through 3-D. This is useful for generating structured dynamics cheaply, but equal diffusion shows that the portfolio does not yet isolate the autocatalytic mechanism or “life.”

3. **Cyclic thresholds must be interpreted relative to effective mixing.** At degree 12, \((q,\tau)=(3,1)\) is almost guaranteed to advance everywhere and collapses into a short global cycle. \((6,2)\) has a narrow 2-D candidate region but becomes churn in 3-D/4-D. Threshold/range scaling, not dimension alone, is the sensible next coordinate.

4. **There is no scalar edge-of-chaos answer here.** Entropy and turnover are high in both candidates and deliberate counterexamples. The measured object is a condition-dependent distribution over regimes, not a universal critical number.

5. **Complex ALife was not demonstrated.** These systems contain no evolution, reproduction test, resource competition, heredity, or individuated lineage. “Candidate” means persistent active spatial organization plus bounded perturbation response under a frozen measurement contract.

## 6. Efficient next experiments

The evidence suggests three CPU-efficient follow-ups:

- Refine Gray–Scott near the 3-D/4-D persistence boundary while crossing diffusion ratio and autocatalysis in a true factorial design. Add object persistence, component splitting/merging, and a rescue condition so equal diffusion can be diagnosed rather than relabeled.
- Map cyclic \(q=6\) around \(\tau=2\) using threshold as a fraction of degree and a second degree-12 offset construction. Spend fresh seeds near the 2-D-to-churn boundary; do not spend more on \(q=3,\tau=1\) at degree 12.
- Test a small set of published, seeded Lenia organisms in 2-D–4-D without evolutionary search. Measure survival, translation, recovery, and morphology under perturbation; keep discovery of new forms outside the evidence split.

The binary 3-D/4-D cells and diffusion-only high-dimensional cells are low-priority under the present rules. A larger seed count should first target transition cells, not repeat deterministic nulls.

## 7. Reproducibility and claim boundary

The production run retained 360 JSONL episode records and 108 split-condition summaries. It completed in 66.39 seconds with 55.20 MB peak process RSS. All 360 episodes met their declared site-step denominators and began with one visible paired perturbation. The runner replayed one episode per family exactly; the portable verifier then re-derived every summary, checked all trajectory and artifact hashes, and independently replayed three family-spanning episodes with identical deterministic projections.

Artifacts:

- experiment contract: [`experiments/alt_physics_atlas_v1/manifest.json`](../experiments/alt_physics_atlas_v1/manifest.json)
- runner: [`src/alt_physics_atlas.py`](../src/alt_physics_atlas.py)
- verifier: [`src/verify_alt_physics_atlas_artifacts.py`](../src/verify_alt_physics_atlas_artifacts.py)
- raw episodes and summary: `results/alt_physics_atlas_v1/`
- portable verification receipt: `results/alt_physics_atlas_v1/verification.json`

The outputs support a reproducible, model-only map of operational regimes. They do not establish organisms, cognition, biological relevance, open-ended evolution, a universal critical dimension, or a universal distribution of complex life.
