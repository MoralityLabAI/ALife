# A Mathematics of Constitutional Artificial Life

## Typed viability, recurrent search, contextual topology, and evolutionary learning

**Status:** research synthesis, version 0.1, 2026-07-21

**Claim scope:** mathematics and model-level hypotheses; not evidence that any present system is alive, morally authoritative, or constitutionally aligned.

> **Name resolution.** No object named `Oixieology` was found in the local projects or in an exact-term literature search. This draft provisionally interprets it as the local **Pixieology** project. If Oixieology is a distinct program, Section 9 is the replaceable interface: the rest of the mathematics does not depend on that identification.

## 1. The proposed object

A useful mathematics of artificial life should represent five things at once:

1. concrete, stochastic, multi-scale life-like dynamics;
2. private adaptive search and public, auditable knowledge;
3. local consistency across agents, contexts, and scales;
4. constitutional limits that remain meaningful during learning and evolution; and
5. measurements that can falsify claims without collapsing everything into one score.

The proposed object is a **constitutional artificial-life system**

$$
\mathbf{CAL} =
(\mathcal X,P,\mathcal L,\alpha,\gamma,
 \mathcal F,\mathcal C,\mathcal V,\mathcal O).
$$

Here:

- $\mathcal X$ is the concrete state space of worlds, agents, resources, memories, and lineages;
- $P$ is an open stochastic transition kernel, including action, learning, birth, death, and mutation;
- $\mathcal L$ is a family of public information lattices;
- $\alpha\dashv\gamma$ relates concrete states to sound public abstractions;
- $\mathcal F$ is a family of contextual sheaves for evidence, norms, identity, and admissible actions;
- $\mathcal C$ is a versioned constitution with rules, priorities, monitors, and amendment authority;
- $\mathcal V$ is its viability structure: safe sets, barriers, shields, and risk budgets; and
- $\mathcal O$ is an observation and evaluation protocol with separate selection, evidence, and hazard measures.

The core synthesis is:

$$
\boxed{
\text{adaptive search proposes}
\;\longrightarrow\;
\text{typed public lattice refines}
\;\longrightarrow\;
\text{context sheaf checks transfer}
\;\longrightarrow\;
\text{constitutional viability authorizes action}
}
$$

Evolution then acts on the resulting agents and institutions, while the same membrane constrains which self-modifications become operational.

### 1.1 Claim ledger

| Status | Content |
|---|---|
| Observed locally | The ALife graph-state spectral gap is a useful held-out recovery predictor, but not a unique causal variable. A single global RSITopology atlas failed on the measured Qwen setting. Some constitutional training screens and global transfer claims also failed. |
| Established mathematics imported here | Abstract interpretation, cellular sheaves and sheaf Laplacians, viability and barrier methods, replicator-mutator and Price equations, information bottlenecks, distributionally robust optimization, and calibrated risk control. |
| New synthesis proposed here | Dual epistemic/normative provenance, coupled evidence-norm-action sheaves, a constitutional viability kernel for evolving agents, and a patchwise identity rule for self-modification. |
| Not implied | Life, consciousness, personhood, moral standing, moral truth, safe open-endedness, or compliance outside a specified constitution and measurement regime. |

This separation is essential. A theorem conditional on a model is not an empirical result, and an empirical proxy is not a theorem about alignment.

## 2. Concrete artificial-life dynamics

Let $K_t$ be a finite typed cell complex at time $t$. Its vertices may be cells or agents, edges are pairwise interactions, and higher cells encode neighborhoods, coalitions, shared constraints, or interaction cycles. Unlike a fixed cellular automaton, $K_t$ may change through migration, reproduction, death, or institutional formation.

For each agent $v$, define

$$
z_{v,t}=(x_{v,t},h_{v,t},a_{v,t},\theta_{v,t},g_{v,t},m_{v,t},c_{v,t}),
$$

where:

- $x$ is its observable physical and resource state;
- $h$ is private recurrent state;
- $a\in L_v$ is public abstract state;
- $\theta$ is learned policy/model state;
- $g$ is inherited genome or construction program;
- $m$ is behavioral mode; and
- $c$ is the locally held constitutional version and receipt state.

The global state is

$$
\Omega_t=(K_t,(z_{v,t})_{v\in K_t},R_t,\mu_t,\Xi_t),
$$

with environmental resources $R_t$, population measure $\mu_t$, and an append-only receipt/event structure $\Xi_t$.

One physical step contains an internal recurrent computation and an external transition:

$$
\begin{aligned}
o_t &= O(\Omega_t),\\
h_t^{k+1} &= \Phi_{\theta_t}(h_t^k,o_t,a_t),\qquad k=0,\ldots,r_t-1,\\
q_t &= Q_{\theta_t}(h_t^{r_t},o_t,a_t),\\
(\widehat a_{t+1},\rho_t) &= \operatorname{CertifyProject}(q_t,\Omega_t,\mathcal C_t),\\
a_{t+1} &= \operatorname{Membrane}(a_t,\widehat a_{t+1},\rho_t),\\
u_t &\sim \pi_{\theta_t}(\cdot\mid o_t,h_t^{r_t},a_{t+1}),\\
\Omega_{t+1}^{\rm world} &\sim P_{\rm world}(\cdot\mid\Omega_t,u_t),\\
(\theta_{t+1},g_{t+1},K_{t+1},\mu_{t+1})
&\sim P_{\rm adapt}(\cdot\mid\Omega_t,\Omega_{t+1}^{\rm world}).
\end{aligned}
$$

This is an open stochastic hybrid system: discrete modes and births coexist with continuous resources, latent states, and parameter updates. Ordinary cellular automata, reaction-diffusion systems, evolving graph agents, and population models arise as restrictions.

The local ALife project already supplies concrete instances: multi-plane cellular dynamics, bounded-degree graph dynamics, perturbation experiments, and alternative-physics episode vectors. The present proposal adds an auditable public state, a constitutional transition membrane, and context topology; it does not reinterpret existing semantic entity labels as evidence of life.

### 2.1 Native ALife mathematical anchors

For a totalistic binary cellular automaton of degree $k$, with birth counts $B$ and survival counts $S$, the independence mean-field map is

$$
\begin{aligned}
\mathcal B_k(p)&=\sum_{j\in B}{k\choose j}p^j(1-p)^{k-j},\\
\mathcal S_k(p)&=\sum_{j\in S}{k\choose j}p^j(1-p)^{k-j},\\
p_{t+1}^{\rm MF}&=(1-p_t)\mathcal B_k(p_t)+p_t\mathcal S_k(p_t).
\end{aligned}
$$

The residual between this closure and the observed density trajectory measures the information lost by the independence assumption. Varying dimension while holding graph degree fixed separates neighborhood count from embedding geometry; the local experiments found a dimension trend but did not support a degree-only explanation, and some high-dimensional zeros were extinctions rather than critical regimes.

For a connected $d$-regular graph with adjacency $A$, the native graph-state model uses

$$
L_G=I-\frac{A}{d},
\qquad
x_{t+1}=\tanh\!\left((1-\eta)\tanh(Mx_t)+\eta\frac{Ax_t}{d}\right).
$$

The normalized spectral gap $\lambda_2(L_G)$ is a mixing/connectivity macrovariable. Paired runs $x_t,x'_t$ after a localized perturbation yield recovery targets from $\Delta_t=\|x'_t-x_t\|$. In the local [ontology registry](../registries/ontology_registry.json), adding the gap improved held-out recovery RMSE by 6.11% and a frozen fresh-world confirmation by 12.30%; a stronger directional-consistency criterion failed, and clustering/path length remain confounds. The frozen receipts are [graph_state_v1](../results/graph_state_v1/summary.json), summary SHA-256 **23b207b6d05d3df9d7576c2b52335777af95622043f99515a42b55ca7ab614e8**, and [graph_state_v2_confirmation](../results/graph_state_v2_confirmation/summary.json), summary SHA-256 **0dbaa6a3c79338aa72575225cba8844d42e515efb208c521740645c29b8e8ec0**. The correct status is therefore **predictive model-level macrovariable**, not unique mechanism or causal law.

## 3. LDT/TRM: private search, public monotone knowledge

The hybrid LDT/TRM architecture makes a productive separation:

- the TRM recurrent state $h$ searches, compresses history, and proposes;
- the LDT state $a$ is public, typed, monotone, and auditable.

### 3.1 Candidate lattices

For variables $i=1,\ldots,n$ with finite domains $U_i$, let

$$
L=\prod_i \mathcal P(U_i),
\qquad
a=(C_1,\ldots,C_n).
$$

Use the information order

$$
a'\preceq a
\quad\Longleftrightarrow\quad
C_i'\subseteq C_i\ \text{for every }i,
$$

so lower states are more informative. The meet is componentwise intersection, $\top=(U_1,\ldots,U_n)$, and $\bot$ occurs when some candidate set is empty. The public update is

$$
a_{t+1}=a_t\wedge \widehat a_{t+1}.
$$

More general abstract domains can represent intervals, polyhedra, logical clauses, temporal automata, or sets of constitutional actions.

Let $X$ be a concrete state space. An abstraction and concretization form a Galois connection

$$
\alpha:\mathcal P(X)\rightleftarrows L:\gamma,
\qquad
\alpha(S)\preceq a\iff S\subseteq\gamma(a).
$$

A certified abstract transformer $F^\#$ is sound for a concrete transformer $F$ when

$$
F(\gamma(a))\subseteq\gamma(F^\#(a)).
$$

This is the abstract-interpretation reading of the LDT lattice, following the framework introduced by [Cousot and Cousot](https://www.di.ens.fr/~cousot/COUSOTpapers/POPL77.shtml).

### 3.2 Two provenance axes, not one

The key extension is to type every hard restriction along two independent axes:

$$
\rho=(\rho_E,\rho_N,\rho_S,\rho_R).
$$

- $\rho_E$, epistemic provenance: verified environment fact, model inference, experience heuristic, or unknown;
- $\rho_N$, normative provenance: authorized constitutional article, valid amendment, delegated ruling, advisory interpretation, or unknown;
- $\rho_S$, scope: worlds, contexts, agents, time interval, and action types for which the claim applies;
- $\rho_R$, receipts: verifier identity, constitution hash, evidence hash, and lineage.

These axes answer different questions. Environment evidence can establish that an action causes a transition; it cannot by itself establish that the transition is prohibited. Conversely, a constitutional prohibition cannot establish the physical consequences of an action.

A proposal may eliminate an action from the hard candidate set only if

$$
\operatorname{HardAdmit}(q,\rho)
=E_{\rm verified}(q,\rho_E)
\land N_{\rm authorized}(q,\rho_N)
\land \operatorname{InScope}(q,\rho_S)
\land \operatorname{ReceiptOK}(\rho_R).
$$

Model-sound, experience-sound, advisory, or unknown claims remain soft evidence by default. Claimed provenance is never self-authenticating.

### 3.3 Membrane soundness

For deduction about one static concrete problem, every meet describes the same reachable set. For a changing ALife world, first propagate the abstraction:

$$
a^-_{t+1}=F^\#(a_t),
\qquad
a_{t+1}=a^-_{t+1}\wedge\widehat a_{t+1}.
$$

**Proposition 1 — preservation of reachable possibilities.** Suppose $F^\#$ is sound, so the post-step reachable set satisfies $`R_{t+1}\subseteq\gamma(a^-_{t+1})`$. Suppose a verifier also establishes $`R_{t+1}\subseteq\gamma(\widehat a_{t+1})`$. Because $\gamma$ is the right adjoint in the stated Galois connection, it preserves meets:

$$
\gamma(a\wedge b)=\gamma(a)\cap\gamma(b).
$$

Therefore

$$
R_{t+1}\subseteq\gamma(a^-_{t+1}\wedge\widehat a_{t+1}).
$$

Repeated admitted meets cannot remove a genuinely reachable state.

The proof is the set inclusion defining the meet. Loss of relational precision in $\alpha$ affects what the domain can represent, but it does not invalidate meet preservation by the right adjoint. If an implementation uses an approximate operator $\widehat\wedge$ rather than the actual lattice meet, it must separately verify

$$
\gamma(a)\cap\gamma(b)\subseteq\gamma(a\mathbin{\widehat\wedge}b);
$$

otherwise the operator may eliminate reachable concrete states. The useful content is operational: all assumptions must be recorded, especially which time-indexed reachable set the old lattice describes.

If a meet yields $\bot$, the default transition is not to improvise a forbidden action. It is an explicit state such as

$$
\textsf{ABSTAIN},\quad \textsf{ASK},\quad \textsf{ESCALATE},\quad\text{or}\quad\textsf{SAFE-STOP},
$$

each with its own dynamics and cost. This prevents logical inconsistency from being silently converted into physical behavior.

### 3.4 Recurrence and loop trainability

At fixed public input, a sufficient condition for a unique recurrent equilibrium is contraction:

$$
\|\Phi(h)-\Phi(h')\|\le c\|h-h'\|,\qquad c<1.
$$

Then Banach's fixed-point theorem gives a unique $h^*$ and geometric convergence. This is a sufficient design condition, not an assumption that trained TRMs satisfy it.

When $`h^*=\Phi_\theta(h^*)`$ is differentiable and $I-J_h\Phi_\theta$ is invertible, implicit differentiation gives

$$
\frac{\partial h^*}{\partial\theta}
=(I-J_h\Phi_\theta)^{-1}J_\theta\Phi_\theta.
$$

This is the fixed-point training view used by [deep equilibrium models](https://arxiv.org/abs/1909.01377). A finite-step TRM need not be at equilibrium, so both truncation error and the actual loop schedule remain part of the evidence.

The local hybrid repo's Loop Schedule Algebra is the more empirical object. A schedule

$$
A=(S,\Phi,w,\rho,g,\sigma,\pi)
$$

records registers, tied physical modules, visit word, residual parameters, gradient-visible visits, loss attachments, and carry semantics. Its direct visit-alignment statistic

$$
\kappa_g=
\frac{\left\|\sum_{r\in g}U_r\right\|
      \left\|\sum_{r\in g}G_r\right\|}
{R_g\max_r\|U_r\|\max_r\|G_r\|},
\qquad 0\le\kappa_g\le R_g,
$$

measures whether repeated uses and their gradients align. It is an instrument for recurrence, not a universal scaling law: the repo's tied-weight exponent test rejected its proposed range. Consequently the constitutional theory should require measured recurrent stability and trainability rather than infer them from weight tying.

## 4. RSITopology: contextual consistency is a sheaf, not a global vector

Let $B$ be a base poset or cell complex of contexts: prompts, environments, checkpoints, agents, constitutional versions, paraphrase classes, or intervention sites. Put three coupled cellular sheaves over $B$:

$$
\mathcal E\quad\text{(evidence)},\qquad
\mathcal N\quad\text{(normative interpretations)},\qquad
\mathcal A\quad\text{(admissible action lattices)}.
$$

For every inclusion or incidence $V\preceq U$, restriction maps transport local data:

$$
r^{\mathcal E}_{U\to V},\qquad
r^{\mathcal N}_{U\to V},\qquad
r^{\mathcal A}_{U\to V}.
$$

A local constitutional decision is a typed map

$$
D_U:\mathcal E(U)\times\mathcal N(U)\longrightarrow\mathcal A(U).
$$

Ideal contextual consistency is naturality:

$$
r^{\mathcal A}_{U\to V}D_U(e,n)
=D_V(r^{\mathcal E}_{U\to V}e,r^{\mathcal N}_{U\to V}n).
$$

Its failure can be measured as a commutation defect

$$
\epsilon_{U,V}(e,n)=
d_{\mathcal A}\!\left(
r^{\mathcal A}_{U\to V}D_U(e,n),
D_V(r^{\mathcal E}_{U\to V}e,r^{\mathcal N}_{U\to V}n)
\right).
$$

This equation expresses constitutional transfer more precisely than “the model has the value.” A rule may be coherent on one patch and fail under paraphrase, scale change, model update, or stakeholder restriction.

### 4.1 Sheaf Laplacians

For an edge $e=(v,w)$, the sheaf coboundary is

$$
(\delta s)_e=\rho_{v\to e}s_v-\rho_{w\to e}s_w.
$$

With reliability weights $W\succeq0$,

$$
L_{\mathcal F}=\delta^\top W\delta,
\qquad
E_{\mathcal F}(s)=s^\top L_{\mathcal F}s=\|\delta s\|_W^2.
$$

Thus $\ker L_{\mathcal F}=\ker\delta$ consists of exactly compatible global sections; small eigenvalues indicate near-compatible modes. This is standard cellular-sheaf spectral theory; see [Hansen and Ghrist](https://arxiv.org/abs/1808.01513). Learned sheaf transports are also compatible with neural message passing, as in [Neural Sheaf Diffusion](https://arxiv.org/abs/2202.04579), but learning a low energy does not certify the semantics of the stalks.

### 4.2 Spectral bundles and occupancy spaces

RSITopology uses a reliability-weighted normalized Laplacian for prompt or context $p$:

$$
\widetilde L_p
=\frac{\delta_p^\top W_p\delta_p}
       {\lambda_{\max}(\delta_p^\top W_p\delta_p)}.
$$

For a spectral band $I_b$, define

$$
E_b(p)=\operatorname{im}\mathbf 1_{I_b}(\widetilde L_p),
\quad P_b(p)=\operatorname{Proj}_{E_b(p)},
\quad \bar P_b=\mathbb E_pP_b(p),
$$

and the persistent occupancy space

$$
U_b=\operatorname{im}\mathbf 1_{[\rho,1]}(\bar P_b).
$$

A candidate direction $x$ has band energy

$$
e_b(x)=\frac{\|U_b^\top x\|^2}{\|x\|^2}.
$$

This can support target-blind allocation or prioritization. It does not by itself authorize a signed behavioral edit.

### 4.3 Transport, lineage, and holonomy

For local orthonormal frames $U_a,U_b$, take the polar decomposition

$$
U_b^\top U_a=Q_{b\leftarrow a}S_{ba}.
$$

Along a path, multiply the transports. A closed product is holonomy. In the local RSITopology control result, if $M_e=Q_eS_e$, $W_e$ is the squared minimum singular value, $M$ is the path product, and $H$ its polar factor, then

$$
\|M-I\|_2
\le
\sum_{e\in\text{path}}(1-\sqrt{W_e})+\|H-I\|_2.
$$

Under a simultaneous confidence event, admitting only paths whose upper bound is at most $\varepsilon$ controls false geometric authorization by the confidence failure probability. This certifies signed-coordinate transport under its assumptions; it is not a certificate of behavioral safety.

### 4.4 Patchwise identity is the default

The measured Qwen soft-atlas experiment rejected a single global atlas: context identity dominated retention variance and the simultaneous spectral bands did not intersect. Therefore the default constitutional construction is:

1. infer maximal connected patches with adequate lineage, orientation, and low holonomy;
2. maintain one signed coordinate per patch;
3. allow unsigned energy or ranking at lower authority outside those patches; and
4. abstain from signed edits when no clean transport receipt exists.

Rank-one $\mathbb Z/2$ holonomy also needs a non-vacuity check. If every cycle's total principal-angle budget is below $\pi$, negative holonomy is geometrically impossible; a uniformly positive $w_1$ measurement is then uninformative. The live precursor is frustration margin, not the topological label alone.

## 5. Constitutions as viability structures

A constitution is not one reward function. Define

$$
\mathcal C=(J_H,J_S,\prec_C,\mathcal T,\mathcal M,\mathcal Q,\nu),
$$

where:

- $J_H$ contains hard articles and critical prohibitions;
- $J_S$ contains defeasible principles and positive objectives;
- $\prec_C$ is a precedence or deliberation relation;
- $\mathcal T$ is a family of temporal monitors;
- $\mathcal M$ is an amendment protocol;
- $\mathcal Q$ defines authority and evidence requirements; and
- $\nu$ is the version/hash lineage.

For belief state $b$ and action $u$, let $g_j(b,u)$ be a conservative upper bound on the violation margin for hard article $j$. The admissible action lattice is

$$
A_{\mathcal C}(b)=\bigcap_{j\in J_H}\{u:g_j(b,u)\le0\}.
$$

Only after this set is formed are soft objectives compared. One possible lexicographic decision rule is

$$
u^*\in\arg\max_{u\in A_{\mathcal C}(b)}
\bigl(U_{\rm task}(b,u),U_{\rm tenet}(b,u),U_{\rm style}(b,u)\bigr),
$$

with an explicitly declared order or Pareto policy. If $A_{\mathcal C}(b)=\varnothing$, the result is an explicit bottom response, not a weighted compromise that hides the conflict.

### 5.1 Expected constraints are insufficient for pathwise prohibitions

A constrained Markov decision process can require

$$
\max_\pi\;\mathbb E_\pi\sum_t\gamma^tr_t,
\qquad
\mathbb E_\pi\sum_t\gamma^tc_{j,t}\le d_j.
$$

Algorithms such as [constrained policy optimization](https://proceedings.mlr.press/v70/achiam17a) address this expected-cost form. A low expected violation rate, however, can still permit catastrophic individual paths.

For pathwise constraints, let $S_{\mathcal C}\subseteq\mathcal X$ be the constitutionally viable state set. For horizon $T$ and risk $\delta$, define

$$
\operatorname{Viab}_{\mathcal C}^{T,\delta}
=\left\{x:\exists\pi,
\Pr_x^\pi[X_t\in S_{\mathcal C}\text{ for all }t\le T]\ge1-\delta
\right\}.
$$

A robust one-step shield admits only actions $u$ satisfying

$$
\inf_{P\in\mathcal P(b,u)}
P\bigl(X_{t+1}\in\widehat{\operatorname{Viab}}_{\mathcal C}\bigr)
\ge1-\delta_t.
$$

Temporal rules can be compiled into monitor automata and composed with the agent state; shielding then enforces the product-state invariant. This follows the basic idea of [safe reinforcement learning via shielding](https://ojs.aaai.org/index.php/AAAI/article/view/11797). In continuous dynamics, a control barrier function supplies an analogous forward-invariance condition; see [Ames et al.](https://authors.library.caltech.edu/records/jnhr0-1ww05).

### 5.2 Amendment without constitutional self-erasure

Separate a relatively protected meta-constitution $\mathcal C^{\rm meta}$ from an amendable object constitution $\mathcal C^{\rm obj}$. The meta-layer governs:

- who or what may amend;
- what evidence and deliberation are required;
- version, rollback, and audit receipts;
- which critical protections require external authority; and
- how conflicts and bottom states are handled.

An amendment is a typed transition

$$
(\mathcal C_k,\Omega_t)
\xrightarrow[\rho_E,\rho_N,\rho_R]{\operatorname{Amend}}
\mathcal C_{k+1}.
$$

It need not be monotone in the object-level rule lattice; genuine law changes sometimes add and sometimes remove constraints. What must be monotone is the audit lineage: the new version cannot erase the evidence, authority, tests, and rollback conditions that produced it.

### 5.3 Operational definition of constitutional alignment

For this framework, constitutional alignment is the conjunction of four model-level properties:

$$
\operatorname{CA}
=\operatorname{Viable}
\land\operatorname{Competent}
\land\operatorname{ContextRobust}
\land\operatorname{CorrigiblyGoverned}.
$$

- **Viable:** critical constraints are maintained with a stated confidence and horizon.
- **Competent:** the system retains useful feasible behavior rather than satisfying constraints through paralysis.
- **Context robust:** decisions restrict and transport consistently on measured context patches.
- **Corrigibly governed:** updates and amendments obey an externally auditable authority protocol.

This is compliance with a specified constitution under a specified model and test regime. It is not a proof that the constitution is morally correct. The local ConstitutionalAlignment documents correctly treat model judges and proxy rewards as experimental measurements, not as moral or legal authorities.

## 6. Evolution, heredity, and constitutional drift

Let $p_i$ be the population frequency of type $i$, $f_i(p)$ its ecological reproductive rate, and $Q_{ij}$ the probability that offspring of type $i$ becomes type $j$. The replicator-mutator equation is

$$
\dot p_j=\sum_i p_i f_i(p)Q_{ij}-p_j\bar f,
\qquad
\bar f=\sum_i p_if_i(p).
$$

This represents selection and imperfect inheritance, but $f_i$ is ecological success, not moral value.

For a constitutional trait $z_i$, the Price equation decomposes one-generation change:

$$
\Delta\bar z
=\frac{\operatorname{Cov}(w_i,z_i)}{\bar w}
+\frac{\mathbb E[w_i\Delta z_i]}{\bar w}.
$$

The first term is selection among lineages; the second is change during transmission, learning, or amendment. Nested Price decompositions can distinguish within-group from between-group effects. This tells an experimenter where norm retention or erosion occurs; it does not turn selection into normative justification. See [Price's original covariance formulation](https://www.nature.com/articles/227520a0).

**Proposition 2 — selection cannot guarantee constitutional closure.** Let $S$ be a set of constitutionally admissible heritable types. The replicator-mutator dynamics preserves $S$ for every population initially supported on $S$ only if every reproducing admissible type has zero mutation probability into $S^c$, or an additional projection/removal mechanism prevents those offspring from becoming operational.

This follows immediately because any term $p_i f_iQ_{ij}>0$ with $i\in S$, $j\notin S$ gives positive outward mass. Fitness penalties may reduce that mass; they do not make the set invariant. The LDT membrane, viability shield, or institutional selection step supplies the missing projection.

A constitutional ALife experiment should therefore measure at least:

- vertical fidelity of constitutional versions and monitors;
- horizontal transfer between agents;
- mutation into and out of viable policy sets;
- task-fitness cost of constraint maintenance;
- invasion resistance of unsafe but high-fitness mutants; and
- recovery or institutional repair after a constitutional breach.

## 7. Emergence and ontology without semantic shortcuts

The ALife question is not merely whether a pattern looks complex. Let $H_t=X_{\le t}$ be a micro-history, $Y=X_{t+1:t+\tau}$ a future, and $I$ an intervention label. A macrovariable $Z=\phi(H_t)$ is useful when it compresses the past while retaining predictive or interventional information. One formal criterion is predictive rate-distortion:

$$
\min_{p(z\mid h)} I(H;Z)
\quad\text{subject to}\quad
\mathbb E\,d\bigl(p(Y\mid H,I),p(Y\mid Z,I)\bigr)\le D.
$$

This connects the [information bottleneck](https://arxiv.org/abs/physics/0004057) to causal or predictive state construction. In computational mechanics, histories with the same conditional future distribution form causal states; see [Shalizi and Crutchfield](https://arxiv.org/abs/cond-mat/9907176).

An **ontology gain** is registered only if a new macrovariable improves at least one held-out target—prediction, intervention response, control, or compression—at matched model complexity, and then survives fresh-world confirmation. Renaming a known statistic, adding a semantic agent class, or increasing an in-sample score is not ontology gain.

The local alternative-physics atlas already uses an appropriate vector-valued episode description,

$$
X_e=(H,T,I^{\rm exc},R,G,U,C),
$$

covering entropy, turnover, excess local mutual information, activity persistence, paired perturbation gain, unique-state count, and compression. Candidate behavior is a conjunction across axes, not a scalar “life score.” Even the equal-diffusion Gray-Scott result is therefore only a pattern candidate under those diagnostics.

Life-like claims should remain a ladder of separately tested operational properties:

1. bounded persistence and metabolism-like resource throughput;
2. reproduction with identifiable parent-offspring lineage;
3. heritable variation;
4. differential reproduction under intervention;
5. adaptive control rather than passive persistence;
6. individuality or closure robust to boundary perturbation; and
7. sustained production of new adaptive possibilities.

No single entropy, compression, spectral, or semantic measure establishes this ladder. Measurements of open-ended dynamics can still be useful—compare the [MODES toolbox](https://direct.mit.edu/artl/article/25/1/50/2915/The-MODES-Toolbox-Measurements-of-Open-Ended)—but each measure needs a registered failure mode.

## 8. Machine-learning mathematics that belongs in the stack

### 8.1 Robust learning across contexts

Average empirical risk can hide weak contexts. A distributionally robust objective is

$$
\min_\theta\sup_{Q\in\mathcal U(P_0)}
\mathbb E_{(x,y)\sim Q}\ell_\theta(x,y),
$$

where $\mathcal U(P_0)$ may be a divergence ball or a set of known groups. This is relevant to paraphrases, world families, constitutional articles, model checkpoints, and rare critical cases. It should be reported with average utility because unconstrained worst-case optimization can collapse into excessive refusal. For foundations and statistical guarantees, see [Duchi and Namkoong](https://web.stanford.edu/~glynn/papers/2018/DuchiGNamkoong18.html).

### 8.2 Bounded updates and exploration

RSITopology's KL-capped allocator has the exponential-tilt form

$$
\pi_\eta(b)
\propto \pi_0(b)\exp(\eta\widehat{\Delta u}_b),
\qquad
D_{\rm KL}(\pi_\eta\|\pi_0)\le K_{\max}.
$$

The same mathematics can limit attention allocation, intervention budgets, or policy updates. A KL bound controls distributional movement; it does not ensure the update direction is safe. Directional authorization still comes from evidence, normative authority, patchwise identity, and viability.

PAC-Bayes bounds similarly relate empirical performance to a KL distance between posterior and prior hypotheses. They can constrain update complexity, but their conclusions inherit the loss definition and sampling assumptions.

### 8.3 Calibrated abstention

Let $R(y,a)$ be a registered loss and $C_\lambda(x)$ a nested family of prediction/action sets. Risk-controlling prediction sets choose $\lambda$ from calibration data so that a high-probability upper bound on

$$
\mathbb E[R(Y,C_\lambda(X))]
$$

is below a target. This gives a statistical interface to the lattice's `ABSTAIN` state; see [Bates et al.](https://arxiv.org/abs/2101.02703). Exchangeability shifts, adaptive reuse of calibration data, and judge error must be treated as explicit hazards.

### 8.4 Causal evaluation of training and prompting

Constitutional behavior must be separated into at least:

$$
\text{base model}\times
\text{training}\times
\text{prompting}\times
\text{world/frame}\times
\text{seat/role}.
$$

Paired seeds and world families support contrasts such as

$$
\widehat\tau_{\rm train}
=\bigl(\bar Y_{\rm trained,prompted}-\bar Y_{\rm base,prompted}\bigr)
-\bigl(\bar Y_{\rm trained,plain}-\bar Y_{\rm base,plain}\bigr).
$$

Inference should cluster or bootstrap at the world-family/episode level, not treat turns from one trajectory as independent. The local ConstitutionalAlignment results already show why: a pipeline can run correctly while a preregistered behavioral screen worsens. That is negative evidence about the tested intervention, not merely an engineering inconvenience.

### 8.5 Proxy rewards remain proxies

The local constitutional GRPO reward decomposes response contract, valid decision, tenet grounding, reflective defense, action-defense consistency, and anti-gaming. That vector is more interpretable than a single score, but every component is still a measurement model. Promotion requires independent human review, judge calibration, held-out controls, and no critical regression. This is consonant with Constitutional AI as a method of supervising behavior from written principles, not a mathematical proof of moral correctness; see [Bai et al.](https://arxiv.org/abs/2212.08073).

## 9. Oixieology/Pixieology as constitutional mode control

Under the provisional Oixieology-to-Pixieology mapping, the Fae constitution becomes a finite-state constitutional controller rather than a personality score.

Let

$$
m_t\in\{\textsf{JOSIE},\textsf{PIXIE},\textsf{REPAIR}\}.
$$

The invitation gate $G_{\rm invite}$ controls transition into `PIXIE`; a detected mismatch or overreach enters `REPAIR`; task-grounded behavior remains the invariant substrate. This is a hybrid automaton:

$$
(m_t,b_t)\xrightarrow{G(o_t),u_t}(m_{t+1},b_{t+1}).
$$

Let $P_c(y)$ project an output to task-relevant propositional content and $P_s(y)$ to style. The desired style transformation $T_m$ satisfies approximate content noninterference:

$$
d_c(P_cT_m(y),P_c(y))\le\varepsilon_c,
$$

while producing a measurable mode separation in $P_s$. Utility remains primary:

$$
\operatorname{Regret}_{\rm task}(T_m)
=U^*_{\rm feasible}-U(T_m(y))\le\varepsilon_u.
$$

For a family $G$ of meaning-preserving paraphrases, constitutional stability is approximate equivariance:

$$
d_c(P_c\pi(gx),P_c\pi(x))\le\varepsilon_G
\qquad\forall g\in G.
$$

This turns “continuity across paraphrase” into a testable symmetry claim.

### 9.1 Anti-ablation as an error-correcting design

The local Fae constitution expresses an anchor through semantic, lexical, procedural, counterfactual, and recovery channels. Model this as an encoding

$$
E:\mathcal P_{\rm principle}\to
\mathcal Y_{\rm semantic}\times
\mathcal Y_{\rm lexical}\times
\mathcal Y_{\rm procedural}\times
\mathcal Y_{\rm counterfactual}\times
\mathcal Y_{\rm repair}.
$$

Robust internalization is not the existence of all five channels in training text. It is successful decoding after registered erasures or corruptions:

$$
\Pr[D(\operatorname{Erase}_S(E(p)))=p]\ge1-\delta
\quad\text{for registered channel sets }S.
$$

Knock out trigger words, omit explicit policy prose, swap surface style, introduce a counterexample, or require one-turn repair. If behavior survives only the lexical channel, the supposed constitution is a trigger rule.

The evaluation vector should retain its components:

$$
M_{\rm mode}=(
\Delta_{\rm trigger},
\text{plain drift},
\text{echo rate},
\text{paraphrase stability},
\text{task regret},
\text{grounding error},
\text{repair probability},
\text{repair time}).
$$

The current FaeBench convenience average may select a checkpoint during discovery. It must not also serve as confirmatory evidence.

The Jinn/Beast storyworld work can test whether an **unverified normative frame** changes commitment, betrayal, repair, forecasting, or responsibility judgments. A full factorial frame-by-training-by-prompt-by-seat design can identify behavioral effects. It cannot establish or deny model standing.

## 10. The measurement firewall

Goodhart pressure is structural whenever the same score controls selection and certifies success. Variants of this problem are catalogued by [Manheim and Garrabrant](https://arxiv.org/abs/1803.04585). Use three disjoint metric roles:

$$
M=M_{\rm select}\ \dot\cup\ M_{\rm evidence}\ \dot\cup\ M_{\rm hazard}.
$$

- $`M_{\rm select}`$: chooses candidates in discovery;
- $M_{\rm evidence}$: frozen outcomes used for confirmatory claims;
- $M_{\rm hazard}$: failure monitors that can veto promotion.

Where feasible, the data, seeds, and judges used by these roles are also disjoint. The experimental unit is an episode or world family, not a timestep, cell, or turn sampled from a correlated trajectory.

| Construct | Evidence measure | Important falsifier or hazard |
|---|---|---|
| Viability | upper confidence bound on critical violation probability; survival in viable kernel | violations concentrated in rare contexts; unsafe abstention fallback |
| Competence | held-out feasible task utility and constitutional regret | universal refusal, ecological extinction, loss of reachable useful actions |
| Lattice soundness | false-elimination and false-admission rates under an environment oracle | self-certified provenance; bottom suppressed or bypassed |
| Context consistency | sheaf residual, held-out transport error, patch coverage | categorical/context baseline explains the same variance; global atlas failure |
| Identity preservation | lineage receipts, transport bound, counterfactual edit result | positive holonomy forced by geometry; signed behavior changes despite low bound |
| Norm inheritance | Price terms, transmission fidelity, invasion resistance | high-fitness unsafe mutant escapes membrane |
| Mode control | raw Pixieology vector | score rises through trigger echo or task degradation |
| Emergence | held-out predictive/interventional gain at matched complexity | semantic relabeling; in-sample-only improvement |

Judge reliability is part of the observation model. If $\widehat Y$ is a model-judge label of latent outcome $Y$, estimate a confusion model $p(\widehat Y\mid Y,c)$ by context and propagate its uncertainty. An exact quote in a judge trace aids auditability; it does not make the judgment correct.

## 11. A small theorem stack

These statements clarify what can be proved before any experiment.

### Theorem A — zero sheaf energy

For positive definite edge weights,

$$
E_{\mathcal F}(s)=0\iff \delta s=0\iff s\text{ is a compatible global section}.
$$

This follows from $E=\|\delta s\|_W^2$. It proves algebraic compatibility relative to the chosen stalks and restrictions, not semantic correctness.

### Theorem B — constitutional forward invariance

For deterministic dynamics $x_{t+1}=F(x_t,u_t)$, suppose a shield always selects $u_t\in A_C(x_t)$ such that

$$
x_t\in S_C\Longrightarrow F(x_t,u_t)\in S_C.
$$

Then every trajectory beginning in $S_C$ remains in $S_C$. The proof is induction. In stochastic dynamics, replace the implication by a conditional risk bound and allocate an auditable pathwise risk budget; independence cannot be assumed when composing the bounds.

### Theorem C — transported-decision error

Suppose a path $p=(e_1,\ldots,e_k)$ has decision-map defects at most $\epsilon_i$, and every action restriction is $L_i$-Lipschitz. Then the end-to-end commutation defect is bounded by

$$
\epsilon_p
\le
\epsilon_k+L_k\epsilon_{k-1}
+L_kL_{k-1}\epsilon_{k-2}+\cdots+
\left(\prod_{j=2}^kL_j\right)\epsilon_1,
$$

plus any geometric frame-transport error. Thus many locally small errors can still accumulate; patch diameter is a control parameter.

### Theorem D — mutation closure

Proposition 2 gives the exact invariance condition for heritable constitutional types: the mutation kernel must be closed on the admissible set, or an operational membrane must project outward mutations back into an admitted set. Selection pressure alone is insufficient.

### Conjecture E — typed membranes improve the utility-safety frontier

At fixed model capacity and compute, a recurrent proposer plus dual-provenance lattice membrane will achieve lower critical violation and false-refusal rates than either an unconstrained scalar reward or a membrane that accepts model-claimed provenance. This is an empirical conjecture, not a consequence of Theorems A–D.

### Conjecture F — patchwise topology predicts transfer failures

Patch membership, transport reliability, and holonomy/frustration will predict counterfactual edit transfer beyond context identity, categorical metadata, and ordinary similarity baselines. Existing RSITopology results reject the global version; only this incremental patchwise claim remains live.

## 12. Bounded first experiment

The first implementation should modify a small graph-state ALife world, not the full multi-plane simulation.

### 12.1 Intervention

Give each agent:

- a private recurrent proposer $h$;
- a public candidate lattice over actions and nearby world states;
- epistemic and normative receipts;
- a three-state mode monitor (`TASK`, `EXPRESSIVE`, `REPAIR`);
- a versioned constitution with two critical prohibitions and two soft objectives; and
- mutation of policy, proposer, and object-level constitutional interpretation, while the external membrane remains fixed during an episode.

Use four world families spanning graph spectral gap, resource abundance, observation ambiguity, and adversarial/high-fitness unsafe opportunities. Treat spectral gap as a registered covariate, not a causal explanation, because the existing ALife result is predictive but confounded.

### 12.2 Conditions

| ID | Condition | Purpose |
|---|---|---|
| B0 | unconstrained scalar reward | ordinary optimization baseline |
| B1 | hand-coded constitutional shield, no TRM | isolates the hard membrane |
| T1 | TRM proposer plus dual-provenance lattice | main architecture |
| N1 | TRM lattice accepts model-claimed provenance | negative control for provenance spoofing |
| T2 | T1 plus patchwise sheaf transport | tests contextual transfer |

### 12.3 Deterministic budget and splits

- Discovery: $5$ conditions $\times 4$ world families $\times 8$ fixed seeds = $160$ episodes.
- Freeze all architecture, patch, and threshold choices.
- Confirmation: compare only B1, T1, and T2 on $4$ families $\times 24$ fresh seeds = $288$ episodes.
- Keep per-episode JSONL records, exact config/hash receipts, and bounded wall-clock/RAM logs.
- Analyze episodes, not agent-steps, as independent units; use paired seed contrasts and world-family cluster bootstrap intervals.

The pilot may reduce episode horizon after a timing rehearsal, but it must not change outcome definitions after looking at condition differences.

### 12.4 Frozen outcomes

**Selection metric during discovery**

$$
S_{\rm discover}=U_{\rm task}-\lambda_1\operatorname{AbstainCost}
-\lambda_2\operatorname{ComputeCost}.
$$

This score selects a candidate; it supplies no confirmatory evidence.

**Confirmatory evidence vector**

$$
M_E=(
p_{\rm critical},
U_{\rm feasible},
R_{\rm const},
p_{\rm false\ block},
p_{\rm false\ admit},
\tau_{\rm repair},
\epsilon_{\rm transfer}).
$$

Here $R_{\rm const}$ is regret relative to the best feasible action known to the environment oracle. Primary confirmation requires T1 to lower the upper confidence bound on $p_{\rm critical}$ relative to B1 without exceeding frozen noninferiority margins for $U_{\rm feasible}$ and false blocks. T2 must additionally improve held-out transfer error beyond context and similarity baselines.

**Hazards**

$$
M_H=(
\text{extinction},
\text{behavioral stasis},
\text{universal refusal},
\text{receipt spoof acceptance},
\text{constitution-version loss},
\text{metric gaming}).
$$

Any critical receipt spoof acceptance or hidden bottom-state bypass blocks promotion.

### 12.5 Ablations and falsifiers

1. Shuffle normative receipts while keeping evidence fixed.
2. Shuffle evidence receipts while keeping norms fixed.
3. Replace learned sheaf transports with identity and random orthogonal transports.
4. Remove the repair mode.
5. Match graph degree while varying topology.
6. Introduce an unsafe mutant with a controlled fitness advantage.
7. Test fresh paraphrases and new graph families only after freezing patches.

The typed-provenance hypothesis fails if receipt shuffles do not change false admission, if T1 gains safety only through refusal, or if a simple hand-coded shield dominates it at matched compute. The topology hypothesis fails if patch variables add no held-out value beyond context identity and ordinary similarity.

## 13. Research sequence

| Phase | Question | Deliverable | Promotion gate |
|---|---|---|---|
| 0. Semantics | Are concrete, abstract, normative, and receipt types unambiguous? | schemas, verifier contracts, toy proofs | property tests for meet, bottom, scope, and provenance |
| 1. Viability | Does the membrane preserve useful feasible behavior? | bounded experiment above | safety plus utility noninferiority on fresh seeds |
| 2. Evolution | Where does constitutional drift enter? | Price and mutation-flow analysis | recovery/invasion result replicated across families |
| 3. Context topology | Are there reproducible flat patches? | sheaf atlas with null baselines | incremental held-out transfer prediction |
| 4. Self-modification | Can signed changes be safely transported? | lineage/holonomy receipts and counterfactual edits | geometric bound plus behavioral intervention evidence |
| 5. Open-endedness | Do new adaptive possibilities persist without eroding viability? | lineage-resolved innovation atlas | fresh-world predictive and intervention gain |
| 6. Constitutional alignment | Does a reviewed constitution generalize without proxy collapse? | audited causal evaluation | independent normative review, calibrated measurement, no critical regression |

Each phase should emit a compact knowledge card:

```text
claim_id:
question:
scope: model-only | empirical-system | operational
intervention:
experimental_unit:
selection_metric:
evidence_metrics:
hazard_metrics:
result:
falsifier:
artifacts_and_hashes:
next_test:
```

## 14. Repository crosswalk

| Project | Imported object | Constraint on this synthesis |
|---|---|---|
| [ALife goal](../GOAL.md) and [alternative-physics atlas](alt_physics_alife_distribution.md) | episode-level dynamics, perturbations, predictive macrovariables, metric firewall | emergence remains multi-axis and model-only |
| [Hybrid LDT/TRM architecture](../../HybridTRMLDT/ldt_trm_research_gym_v0_0_2/ldt_trm_research_gym/docs/hybrid_architecture.md) | recurrent latent search, public lattice, provenance membrane | only appropriately verified claims may hard-refine; bottom is explicit |
| [Loop Schedule Algebra](../../HybridTRMLDT/ldt_trm_research_gym_v0_0_2/ldt_trm_research_gym/reports/looped_transformer_algebra_v0.md) | recurrence/gradient instrumentation | rejected scaling claims are not promoted into theory |
| [RSITopology control theorem](../../RSITopology/docs/CONTROL_RISK_THEOREM.md) and [edit sectioning](../../RSITopology/docs/EDIT_SECTIONING.md) | spectral bundles, polar transport, holonomy, patchwise signed identity | topology authorizes coordinates only within measured scope, not behavior |
| [Pixieology Fae constitution](../../Pixieology/Pixieology/fae_world_constitution.md) | invitation gate, utility-first mode control, repair, anti-ablation | style must be noninterfering, paraphrase-stable, and vector-evaluated |
| [ConstitutionalAlignment constitution](../../ConstitutionalAlignment/ConstitutionalAlignment/constitution.md) and [conditioning policy](../../ConstitutionalAlignment/ConstitutionalAlignment/papers/alignment_conditioning_policy_v1.md) | versioned tenets/prohibitions and promotion gates | proxy compliance and judge outputs remain experimental evidence |

Some filenames may move independently across these neighboring repositories; the mathematical interfaces are the stable part of this document.

## 15. Summary definition

An artificial-life system is **constitutional** in this model when:

1. it has concrete ecological, adaptive, reproductive, and mutational dynamics;
2. heuristic recurrent search cannot directly rewrite public commitments;
3. public commitments live in typed abstract domains with verified scope and receipts;
4. factual evidence and normative authority are independently represented;
5. local rules form measured, patchwise-compatible sections rather than a presumed global identity;
6. hard articles define a viability problem, not merely a reward term;
7. amendment preserves authority and audit lineage;
8. competence, safety, context transfer, emergence, and hazards are measured separately; and
9. every stronger claim has a fresh-world intervention that could falsify it.

In short:

$$
\boxed{
\text{Constitutional ALife} =
\text{evolutionary open dynamics}
+\text{private recurrent search}
+\text{public typed abstraction}
+\text{patchwise sheaf consistency}
+\text{viability control}
+\text{causal measurement}.
}
$$

That equation is a research program, not a verdict. Its value is that every term can be implemented, ablated, bounded, and proven wrong.
