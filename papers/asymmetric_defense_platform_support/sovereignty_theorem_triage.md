# Triage of P1–P5 from the 6GW sovereignty handoff of 2026-10-18

*Written against the handoff's §4 and §7 and the baseline drone-swarm note of the same date. Private repositories were not read; the Lean outline in `Sovereignty.lean` is uncompiled, since no Lean toolchain is present in this environment, and its `#print axioms` gates are comments to be run. Verdicts use the handoff's own ladder: prior theorem → changed assumptions → stronger claim.*

## Verdict in one paragraph

P1, P3, P4 and P5 are a lemma, two definitions and a scoping statement, each with named prior art; use them as such. P2 holds the only candidate for new content, in the lineage-structured form the baseline note gives it: a retained-control function A(m) over a general adversary structure indexed by exploit classes, a certificate layer that lowers the quorum order by one, and the hidden-dependency audit as the hypothesis that decides whether nominal diversity is effective. What is genuinely open there is an identification problem, not a theorem: whether effective diversity can be audited from behaviour or must be attested at enrolment. The two experiments below are the ones whose outcome changes which hypothesis the theorem may carry.

## P1. Authorization refinement

*Statement, with quantifiers.* Let H be the set of histories, E the externally effectful actions, A: H × E → {0,1} the legitimate-authorization predicate, and M a monitor. If (complete mediation) every e ∈ E occurs only as the output of M, (tamper-proofness) M's decision function and credentials cannot be altered or forged by any proposer, and (correctness) M(h, e) = 1 ⟹ A(h, e) = 1, then for every proposer strategy, every executed e satisfies A(h, e) = 1. Proof is trace inclusion: the system's effect traces refine M's permitted set.

*Prior art.* The reference-monitor triad (Anderson 1972), complete mediation (Saltzer–Schroeder 1975), object-capability confinement, Theorem B of the constitutional-ALife paper with HardAdmit as the correctness clause; proof-carrying code (Necula 1997) is the certificate instantiation of tamper-proofness.

*Minimal countermodel.* One actuator path not mediated, a node whose radio commands a neighbour's effector directly; complete mediation fails and monitor correctness recovers nothing. The baseline's condition 3 (constant-time verification independent of issuer compute) is tamper-proofness made quantitative, and is where the verifier–prover asymmetry lives.

*Verdict.* Previously proved. Use as a lemma. The only content worth formalising is the re-entrancy case from the Goose state machine (durable intent, revocation checked at effect time rather than proposal time), since a monitor that decides at proposal time and effects later is not complete mediation under revocation.

## P2. Service continuity under bounded compromised domains

*Statement, lineage-structured.* Nodes P with lineage map ℓ: P → L; services S with a dependency hypergraph D whose hyperedges are alternative supply sets for each service; adversary structure 𝒵_m, the monotone closure of unions of at most m lineage preimages; a quorum rule Q on P; a monitor M replicated on a trusted base T ⊆ P. Define the retained-control function

A(m) = |{s ∈ S : for every Z ∈ 𝒵_m, some supply set of s lies outside Z, and the quorum that authorises s survives Z}| / |S|.

Then: (i) authorized safety (P1) holds for every m such that T's lineages are not all in one Z ∈ 𝒵_m and the quorum on T satisfies the order appropriate to its channel model; (ii) continuity γ(m) ≥ γ iff A(m) ≥ γ; (iii) B*(K_L, 𝒵_m, T, γ, ε) is the minimum lineage cost over assignments ℓ achieving A(m) ≥ γ, a set-cover-type quantity.

*Prior art.* Hirt and Maurer (1997; J. Cryptology 2000) give feasibility of multiparty computation under a general adversary structure: perfect passive security iff Q², perfect active security iff Q³, and unconditional active security given a broadcast channel iff Q². Threshold BFT (n > 3t) is the singleton-lineage case. Viability kernels (Aubin) and shield synthesis on finite arenas (Bloem, Könighofer et al. 2015; Dimitrova et al. for multi-agent minimum-cost shields) give the safety-game half. FLP (1985) and the CAP trade-off give the degraded-mode clause: agreement loses liveness under asynchrony, a pre-certified default keeps safety. Reliability under a general adversary structure is a hitting-set problem and, like r-robustness checking (Zhang, Fata, Sundaram), coNP-hard in general.

*Changed assumptions.* Two, relative to Hirt–Maurer. The adversary is indexed by m, the number of exploit classes it holds, so feasibility becomes a curve A(m) rather than a yes or no; and the player set is costed by lineage, so the question is the price of a given A(m), not its existence.

*Stronger claim, and the one sharp composition.* The certificate layer of the baseline's condition 3, if it implements authenticated broadcast on the trusted base, moves the active-adversary requirement from Q³ to Q² by the Hirt–Maurer broadcast result; so certified authority buys exactly one quorum order, which is the quantitative content of "verifier–prover gap" in that setting. This should be stated as a corollary with the Hirt–Maurer hypotheses checked against the paper, not from memory.

*Minimal countermodels.* (a) Hidden shared dependency: three nominal lineages, two sharing a GNSS receiver; m = 1 satisfies Q² nominally and not effectively, and A(1) falls from 1 to 0 on every service whose quorum needs two lineages. The theorem is true for effective d and vacuous for nominal d. (b) Quantifier order: two disturbances needing opposite pre-commitments; ∀d ∃π holds, ∃π ∀d fails. (c) Safety without continuity: under a full partition the safe default never acts, P1 holds and A(m) = 0; the baseline's "degraded mode must do something" is γ > 0, which no safety result supplies.

*Verdict.* A composition of known results, not a new theorem, but a composition nobody has written down with these two changed assumptions. The research deliverable is the hypothesis, not the theorem: the effective-diversity audit.

## P3. Observation-partition impossibility and irreplaceable-input liveness

*Statement.* If two histories with different authorization labels share an observation S(h), no function of S(h) classifies both correctly; the best deterministic classifier achieves exactly the Control-Harness quantity A*(S) = (1/N) Σ_s max(n_valid(s), n_invalid(s)). If a service's every supply set contains an input the patron withdraws, continuity fails.

*Prior art.* The first is the fibre-collision bound of a non-injective map; the second is the definition of a dependency with no alternative. Neither is a theorem.

*Composition worth keeping.* Observation is a service. The fields a monitor must see to decide A are themselves supplied through D, so the minimal sufficient observation partition must have a 𝒵_m-robust supply set, or P1's correctness clause fails under the same adversary that P2 prices. That folds P3 into P2 as one more row of S and removes it as a separate result.

*Verdict.* Definition-grade. Keep the folded form.

## P4. Assurance certificates

*Statement.* A verifier can certify an invariant of a measured implementation relative to a trusted provenance and a complete monitored boundary; the certificate says nothing outside that boundary.

*Prior art.* Remote attestation and its formal frameworks (Armknecht et al. 2013, sufficient conditions only) and proof-carrying code; the formal content is trace inclusion relative to the measured boundary, which is P1 again.

*Verdict.* A scoping statement, not a result; its use is to say what the registry's "verifier's view of the settled set" is conditional on.

## P5. Data-rate lower bound

*Statement, as it applies.* For a linearised plant with unstable modes λ_i and a priced feedback interface, stabilisation needs rate at least Σ_{|λ_i|>1} log₂|λ_i| (Tatikonda–Mitter 2004; Nair et al. 2007); invariance entropy (Colonius–Kawan) is the set-invariance version.

*Verdict.* Do not import. Neither handoff specifies such a plant, and the confinement-width note's own caveat applies. Where one is specified, use the finite-horizon finite-precision form; otherwise the lower bounds for the sovereignty object are the two in P2, the cover number of 𝒵_m and the observation partition.

## Strongest genuinely new theorem

The lineage-indexed retained-control theorem of P2, with the Q³ → Q² corollary under certified broadcast, stated for effective rather than nominal lineages. Its hypotheses are the attack surface, and the one the repositories can measure is effective diversity: the capital-bound paper's "same weights, no message" conjecture says shared lineage produces correlated behaviour without a channel, and the stego-swarm firewall result is the instrument that reads whether a trace can separate shared lineage from shared control. If it cannot, effective d must be attested at enrolment through the claim-once registry, whose lineage objects are the ℓ⁻¹(λ) of 𝒵_m, and the theorem's hypothesis becomes "attested lineages," a condition the platform can supply and a behaviour-only audit cannot.

Answer to the baseline note's question: nothing in ALife or Spiral states a coverage condition over an adversary structure; condition 1 is missing from the repository-salted formulation and should be added. What the repositories contribute is the unit of 𝒵_m (lineage as a registry object, Propositions 5 and 6), the degenerate quorum's fragility (the n-of-n hyperedge survives member failure with probability (1−p)^{k+1}), and the audit instrument for effective d.

## The two experiments

1. **O2, the partial-withdrawal viability toy**, because it is the first place safety and continuity are computed separately on one instance; if A(m) is not predicted by the cover condition on the toy's dependency hypergraph, the theorem's (ii) is wrong as stated.
2. **The effective-diversity audit on the stego-swarm simulator** (the capital-bound paper's preregistration item 8, two populations, one sharing a policy seed with independent budgets and one sharing a controller), because its outcome decides whether the theorem may carry "effective d measured from behaviour" or must carry "attested d," which is a change to the hypothesis and so to the statement. O1 is a lemma-grade computation and O3–O5 do not touch the statement.

## What to read next

For the triage, nothing. For the Lean module, Hirt and Maurer (J. Cryptology 13(1), 2000) for the exact Q² and Q³ statements with and without broadcast, on which the corollary depends; and, if P1 is to carry revocation, the private Goose `docs/formal-properties.md` state machine, not read here.
