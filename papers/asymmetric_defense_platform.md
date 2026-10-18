# Where the Bound Is: A Research Platform for Defender-Favoured Mathematics of Autonomous-Swarm Conflict

*A proposal for a conference pitch, collated 2026-10-18 from the ALife and Spiral programs and from a literature pass. Status: proposal and research map; nothing here is measured on a drone, a radio link, or a network. Every result quoted from the two programs carries its original claim scope (model-only, sealed, non-operational), and every literature citation was gathered from abstracts and search summaries rather than full texts and must be checked against the paper before it is cited in a submission.*

## 0. The claim in one paragraph

Wherever an attacker's gain is bounded by a resource the defender can meter, and wherever the attacker's coordination cannot be both worth having and invisible, the defender has a structural advantage that does not depend on out-spending the attacker. Two results from our own work, both proved or measured on sealed models and neither yet stated for a physical swarm, say where that advantage lives: a coalition under common control earns no more than its authenticated capital placed under stationary demand, whatever the capacity of its covert channel, and the signal of common control sits in the capital commitment, which any observer reads, rather than in the traffic, which only a strong observer reads and only where coordinating was worth doing. The literature on resilient consensus, secure estimation, covert-channel capacity, Stackelberg commitment, and stake-bounded security contains the pieces of a general theory of this kind, and nobody has assembled them; the nearest statements (Casper's accountable safety, SybilLimit's cut bound, the square-root law for covert communication) are each protocol-specific. The platform proposed here is a program of preregistered, sealed, non-operational model studies that would state the general theorem, measure its conditions, and hand the results to the people who run attestation labs, cyber commands, and drone procurement, in the form of evidence for monitors rather than methods for evaders. Taiwan is the right place to propose it because Taiwan is building the two things the theorem needs to bite, a metered supply chain for autonomous hardware and a national drone-cybersecurity test regime, and because no published treatment of swarm-level cyber compromise in the Strait context exists.

## 1. Which war, which word

"Sixth-generation warfare" has no consensus definition. Slipchenko's Russian usage means precision-strike, no-contact war, with 5GW as nuclear stalemate; the informal Western usage means AI-driven, autonomous, swarm-centred, machine-speed conflict, with 5GW as cognitive or information war; and the defence press uses "sixth-generation" for fighter aircraft that command loyal-wingman drones. The three are not the same axis. This document uses the term in the second sense and only as a label for a descriptive condition: conflict in which the contested layer is the control plane of many cheap autonomous platforms, so that the question "who controls this swarm, and can anyone tell" is the operative one. A pitch should say which meaning it uses, or avoid the term in the title, since a Taiwanese audience that has read the Russian literature will hear Slipchenko first.

The defender-favoured condition, stated without the term: an attacker who wants to turn a swarm, or field one, must commit resources that can be metered (airframes, attested compute, spectrum-time, energy, settled capital), must forecast an environment the defender can move, and must coordinate over channels whose value to the attacker is the same quantity as their footprint to the defender. Each of those three is a theorem target. None of them is a traffic-analysis problem.

## 2. Why Taiwan, why now

Three facts, each from the search pass and each to be verified against the primary source before use in a pitch:

- Taiwan is building a metered supply chain for autonomous hardware. The MOEA drone-industry plan (NT$44.2B to 2030, approved March 2026) targets a "non-red" supply chain by 2027; the Act on Strengthening Defense Autonomy and Developing the Unmanned Vehicles Industry (passed 27 August 2026, promulgated 11 September) sets a six-year NT$240B ceiling with MOEA leading; ITRI runs a verification platform modelled on Blue UAS and became an AUVSI Green UAS assessor in January 2026. A supply chain that is audited is a settled set, in the sense of our registry, and a settled set is what a capital bound is stated over.
- Taiwan has a drone-cybersecurity test regime. The MODA/MOTC Cybersecurity Test Specification for Drones took effect 1 December 2024; MODA's UAV Cybersecurity Joint Testing Laboratory at the Telecom Technology Center is DEKRA-accredited. A test regime is a verifier, and the registry results below are conditional on exactly one thing: that the verifier's view of the settled set is correct.
- The threat is already at the supply chain. Trend Micro's TIDRONE report (September 2024) describes a Chinese-speaking espionage group targeting Taiwanese drone manufacturers through common ERP software. The published GNSS-spoofing literature on swarms (the 2026 "swarm propagation vulnerabilities" work, arXiv 2606.00904) shows that spoofing one platform moves its neighbours. No published analysis treats swarm-level C2 compromise in the Strait context; that is a gap a platform can claim.

The CNAS "Hellscape for Taiwan" report (February 2026) argues for a layered drone-and-mine defence and notes that Taiwan lacks the industrial base and faces institutional hurdles. A mathematics that tells the defender where to put a finite monitoring budget, and which attacker resources are worth metering, is what an under-resourced defender needs from theory. That is the pitch.

## 3. What the two programs already hold

The inventory in `asymmetric_defense_platform_support/inventory.md` lists every formally stated result in both repositories with status and assumptions. The ones that bear on the thesis, with their original claim scope, are these.

| Result | Where | Statement | Status |
|---|---|---|---|
| Capacity saturation | ALife stego paper, Prop. 1 | There is a finite C* ≤ ⌈B/w⌉⌈log₂ L⌉ above which further covert capacity directs no further unit of capital and changes no delivery; C* = 10 bits in the frozen run. | Proved; exact by construction of the directive budget, reported as a construction check, not a discovery. |
| Capital ceiling, forecast floor | ALife stego paper, Prop. 2; H2 | No placement of a fixed budget exceeds the greedy integer optimum of the separable concave delivery objective; a post-placement demand shift collapses delivered success while that optimum stays high, so the loss is a stale forecast and not a capital shortage, and coordination does not rescue it. | Clause 1 proved; clause 2 measured on 12 sealed holdout seeds. |
| Firewall, regime-aware | ALife stego paper, Prop. 3; H3, H4 | A capital-reading warden separates account structure at every public-signal rate; a trace-reading warden separates information access only to the extent the covert channel is valuable, because the channel's value and its trace footprint are the same quantity; a trained, member-attributed warden reads the trace further down, so trace-side invisibility is a property of the warden while the capital signal is warden-independent. | Measured 2×2 factorial over a seven-point public-rate sweep, pooled over 24 seeds; gates loose; one demand family. |
| Policy invariance of the cut bound | Spiral lnmath, Lemma 1, Prop. 1 | The prefix cut bound on net delivery across any partition holds under every routing policy, including exact balance knowledge; intelligence affects which attempts settle, not the identity that settled crossings satisfy. | Proved. |
| Sybil-bounded weight, epoch bound | Spiral lnmath, Props. 5, 6 | Weight attributed to claims backed by a settled object is at most that object's value whatever the number of identities, if the proof system is knowledge-sound and the nullifier is keyed by the object's authority; under an epoch rule, one unit of capital counts once per epoch whatever its id history. | Proved conditionally; witnessed with a simulated proof system. |
| Coordination gain, conditional | Spiral lnmath, Prop. 8 | Under the two propositions above and the measured placement effect, a coalition's gain from coordinating is bounded above by the stationary-placement effect on its own capital and is zero under demand shift, whatever the capacity of its channel. | Conditional claim in the tested model; a conjunction of three attack surfaces (verifier view, demand persistence, a discriminating netting statistic), none of which is a covert-channel problem. |
| Same weights, no message | Spiral lnmath, §7.5 | Agents instantiated from one model converge on the same placement without a message, so correlation of control loops fires on common training as on common control; we conjecture payment traces alone cannot separate them. | Conjectured; preregistered, unrun. |
| Persistence-versus-delay advantage | Spiral, Liquidity on Trial §11.1 | A(ρ,d,H) = ½ Σ_{t=d+1}^{H} (2ρ−1)^t: the advantage of acting on a two-state persistent process decays geometrically in the deployment delay d. | Exact on a toy, enumerated. |
| Pooling scale | Spiral lnmath, Remark 1 | Sum-of-peaks over peak-of-sum is O(√N) for signed uncorrelated imbalance, π/2 for reflected walks at zero drift, about 1 under shared accumulation. | Order-of-magnitude argument; π/2 exhibited, √N stated and not exhibited. |
| Shield invariance, transported-decision error, sheaf consistency | ALife constitutional paper, Thms. A, B, C | A shield that selects admissible actions keeps trajectories in the safe set; end-to-end decision error along a relay path is bounded by a Lipschitz-weighted sum of per-hop defects, so patch diameter is a control parameter; sheaf energy is zero iff local views form a compatible global section. | A, B proved (short); C stated without proof. |
| Spectral-gap recovery predictor | ALife graph_state v1, v2 | Adding the normalised-Laplacian spectral gap to a frozen baseline improves held-out prediction of post-perturbation recovery by 6.11% and, on unseen degrees, sizes and topologies, 12.30%. | Measured; accepted as a model-only predictive macrovariable; the directional claim failed twice. |
| Registration, abstention, verifier discipline | ALife GOAL.md, REPORT.md; Spiral audit | Preregistered targets with abstention scoring; sealed disjoint seed sets; verifier scripts that recompute every gated number from raw episodes; adversarial multi-reviewer audit in which disputes end in a witness, a proof with a stated domain, a narrowed claim, or an open obligation. | Operating practice, with receipts. |

Two housekeeping notes the inventory surfaced. The ALife stego manifest cites the superseded Markdown draft of the lnmath paper and numbers its preregistration items 7 and 9; in the current TeX paper (revised 2026-10-16) those are items 8 and 10, and the proposition the paper calls S5 is Proposition 8. And nothing in either repository mentions Taiwan, warfare, UAVs, or cyber; the word "drone" in ALife is a cell type.

## 4. The mapping, and where it strains

| Source term | Defender reading | Strain |
|---|---|---|
| Coalition under common control | Compromised sub-swarm, or an adversary's swarm posing as independent platforms | Direct. |
| Capital (authenticated, settled) | Attested airframes, attested compute, spectrum-time, energy, munitions, settled funds | Physical resources are not fungible, not always conserved across the boundary (capture creates stock), and not settled on a ledger; the bound needs a conserved, partitionable quantity. |
| Covert channel capacity | Attacker C2 or mesh bandwidth under electronic warfare | Our channel is a scalar with no content and one placement decision; a real adversary re-tasks continuously. |
| Demand process; demand shift | The engagement geometry the attacker must forecast; the defender's reconfiguration | Our shift is exogenous and total; a real adversary re-observes and adapts. |
| Warden (capital row) | Attestation registry, procurement and logistics observation | Direct. |
| Warden (trace row) | Traffic analysis, behavioural sensor fusion | Direct, with the trained-warden caveat that stronger observers read more. |
| Claim-once registry | Swarm admission: consensus weight bounded by attested hardware lineage, no identities required | Conditional on a trusted verifier; bounds Sybil multiplication, not capture of a real attested device. |
| Shield, HardAdmit, SAFE-STOP | Runtime assurance around a learning controller, with a fail-safe | Theory only; nothing run. |
| Sheaf residual | Detector of inconsistent local world-models across platforms | Theory only; the one empirical sheaf test (investigator gym H2) found the sheaf prior added nothing. |
| Spectral gap | Mesh topology chosen for recovery after a node is lost or turned | Benign perturbation, static regular graphs, no radio; weakest evidence in the set. |
| Delivery = min(demand, capacity) | A service model, not an engagement model | No attrition, no adversarial demand. |

The honest summary is that the two programs hold bounds on adversary gain under stated conditions and hold no defender-versus-attacker cost ratio. The literature holds cost ratios (FlipIt's periodic equilibrium, resource-burning bounds, verifier-prover asymmetry) and no general gain bound. The platform's first theorem would join them.

## 5. The research avenues

Each avenue is stated as a question, what the literature holds, what we hold, the theorem or measurement target, a bounded first experiment that can run sealed and non-operational, and the reason the result favours the defender. The literature claims are tagged in the support files; "open" means the cited paper says so.

### 5.1 The capital bound for a compromised sub-swarm

*Question.* For a sub-swarm under one controller holding metered resource B, placed against a process the defender partly controls, is the gain over independent placement bounded by the stationary effect on B, independent of C2 capacity, and under what conditions does the bound fail?

*Literature.* Casper's accountable safety (reverting finality implicates at least one third of stake, a pure quorum-intersection count) and LaKSA's coalition safety are the nearest stake-only statements; SybilLimit bounds accepted Sybil identities by a graph cut, O(log n) per attack edge, whatever the identity count; Gaži, Kiayias and Russell show the proof-of-work threshold r_a < 1/(Δ + 1/r_h) depends on network delay Δ, so a capital-only bound is the Δ → 0 limit; Ferreira and Weinberg show a strategic proof-of-stake miner's reward exceeds its stake share at about 32.8%, so reward-type bounds are not stake-only even when safety-type bounds are. No paper states "coalition advantage ≤ f(stake) for every coordination strategy" in general form.

*Ours.* Prop. 8 (conditional), stego Prop. 2 and H2, Lemma 1 policy invariance.

*Target.* A theorem with the shape "safety-type bounds are stake-only; liveness- and reward-type bounds carry a delay or channel term," stated for a capacity-constrained flow on a graph with node weights, which is the object SybilLimit, Casper, and payment-channel max-flow all instantiate. The conjecture is that the stationary-placement effect is the reward-type term and that it vanishes with the persistence of the process, as A(ρ,d,H) does in the toy.

*First experiment.* Extend the stego model so the defender chooses the demand process after observing the coalition's warm-up behaviour (a Stackelberg demand), sweep partial shifts rather than one total relocation, and let the coalition re-observe at a cost. Register the shape of G as a function of shift fraction and re-observation cost; the bound fails where G stops decreasing in shift.

*Why it favours the defender.* The attacker's gain is a function of a quantity the defender meters at enrolment, not of a quantity the defender must intercept in flight.

### 5.2 Decision-entropy saturation of C2

*Question.* How many bits per round does a swarm task actually need, and is the value of C2 to an attacker a sharp threshold in capacity so that electronic-warfare budgets can be sized to the task's decision entropy rather than to the raw link?

*Literature.* The data-rate theorem (Tatikonda and Mitter; Nair, Fagnani, Zampieri, Evans) gives a sharp threshold: stabilisation needs rate at least the sum of log|λ| over unstable modes, and extra rate buys performance, not feasibility. Sahai and Mitter show Shannon capacity is the wrong quantity over a noisy link and anytime capacity is the right one. Cuff, Permuter and Cover's "coordination capacity" characterises the joint action distributions achievable at given rates as a rate region, not a number. Multi-agent bit counts (one-bit consensus; Hong et al.'s m to 2m bits) are sufficiency results the authors call conservative. No theorem states that coordination value saturates in capacity for a multi-robot task; the empirical OCBC line reports 10× less communication at no task cost.

*Ours.* Stego Prop. 1 and H1 (C* ≤ ⌈B/w⌉⌈log₂ L⌉, exact by construction), and the live-agent finding that below C* a capable coordinator can do worse than a trivial water-fill by optimising its own slice.

*Target.* A coordination-capacity region for a re-tasking swarm, with C* as the rate below which denial changes the outcome and above which it does not, expressed in the entropy of the placement decision rather than in link bits; and a multi-agent anytime-capacity analogue, which the literature does not have.

*First experiment.* Replace the one-shot placement with a re-tasking schedule of period τ and show C*(τ) ∝ H(decision)/τ; then add a noisy warden-observed link and measure whether the Bash square-root law (O(√n) covert bits in n uses) binds before C* does.

*Why it favours the defender.* Denial below C* is a cheap, bounded intervention whose effect is predictable; denial above C* is wasted, and knowing which is which is the budget.

### 5.3 Stationarity as the defender's lever

*Question.* What does it cost the defender to move the environment, what does it cost the attacker to re-reconnoitre, and when is the ratio favourable?

*Literature.* FlipIt (van Dijk, Juels, Oprea, Rivest): in the periodic equilibrium the player with the higher move cost earns zero, and equilibrium rates depend on the cost ratio, which is the cleanest published defender-attacker cost-ratio theorem; periodic dominance fails under hyperbolic discounting. Moving-target-defence timing as a Stackelberg game (value iteration, no closed form). von Stengel and Zamir: a leader's commitment payoff is at least its Nash payoff for two players, and the theorem fails with three or more, which is exactly the colluding-swarm regime. Iliaev, Oren, Segev give a tight bound on the defender's cost reduction from committing first in a Tullock contest.

*Ours.* The forecast floor (success 0.66 → 0.08 under shift while the optimum stays at 0.67; shift gain 0.012), and the closed form A(ρ,d,H), which says the attacker's advantage from persistence decays as (2ρ−1)^d in its deployment delay.

*Target.* A FlipIt-type game in which the defender's move is a shift of the demand process and the attacker's move is re-observation, with the forecast-floor curve as the payoff; the claim is that the defender's move cost is the cost of reconfiguration and the attacker's is a full warm-up, and that the ratio is set by ρ and d, not by capital.

*First experiment.* Partial-shift sweep with an adapting coalition that re-observes at cost; register the break-even shift fraction as a function of persistence.

*Why it favours the defender.* The defender moves what it owns; the attacker must re-learn what it does not.

### 5.4 The firewall: never both valuable and trace-invisible

*Question.* Is it a theorem that a coalition's coordination value equals a divergence between its coordinated behaviour and its public-only behaviour, so that any warden's detection error is lower-bounded by that value, and can common control be separated from common training?

*Literature.* Cachin: steganographic security is KL(P_cover ‖ P_stego), which bounds any warden. Bai, Pasqualetti, Gupta: ε-stealthiness against an arbitrary detector, with the degradation a stealthy attacker can cause characterised. Bash, Goeckel, Towsley: the square-root law. The counterweight is de Witt et al.: perfectly secure steganography is achievable on a known cover distribution with a minimum-entropy coupling, and Motwani et al. show LLM agents can collude steganographically with monitoring and paraphrasing as limited mitigations; detectors in that line (Tailor's "Audit the Whisper") are benchmark-calibrated, not worst-case. No square-root-law analogue exists for agent-to-agent text channels, and no tight detection-versus-capacity trade-off for agent teams.

*Ours.* Stego Prop. 3, H3 and H4: the gap between pooled-private and public-only placement is both the channel's value and the trace warden's signal; the capital warden reads structure at AUC 1.00 at every rate; the trained warden reads information access at channel value 0.01 where the scalar warden is at chance. The "same weights, no message" conjecture.

*Target.* The general statement: value of coordination = a divergence between two placement distributions = a lower bound on any warden's error exponent (Stein's lemma), so the attacker's trade-off curve is a function of the task, not of the codebook; and a separation test for common training versus common control, which our conjecture says traffic cannot make and attestation can.

*First experiment.* Preregistration item 8 of the lnmath paper: two populations on the simulator, one sharing a policy seed with independent budgets, one sharing a controller; test whether any trace statistic separates them and whether the capital statistic does. Then the bounded capacity-versus-detectability appendix (item 10), read against the bound and not as a headline.

*Why it favours the defender.* The defender need not read the wire; it needs to read the commitment, and the attacker cannot make the commitment both useful and quiet.

### 5.5 Identity-free attestation as the root of swarm consensus weight

*Question.* Can the F in resilient consensus (the number of adversarial agents a topology tolerates) be made a registry quantity, bounded by attested hardware lineages rather than by counting identities, so that the "F must be known in advance" assumption of W-MSR becomes an attestation output?

*Literature.* LeBlanc, Zhang, Koutsoukos, Sundaram: under F-total adversaries W-MSR reaches consensus iff the graph is (F+1, F+1)-robust; the guarantee is topological and needs no identification of the bad agents, only a bound F. Wardega et al. list W-MSR's limits: F known in advance, about 2F+1 neighbours, slow propagation. Collective attestation: SEDA (spanning tree, full connectivity), SANA (aggregate signatures, 10⁶ devices in about 2.5 s), PIRANHAS (zkSNARK recursion for asynchronous swarms, 356 ms on capable hardware), VRASED (first formally verified remote attestation); Armknecht et al. give sufficient conditions only. No published bound relates per-device attestation cost to the adversary's cost to forge.

*Ours.* Props. 5 and 6: nullifier keyed by the object's authority, weight per settled object ≤ its value whatever the identity count; the epoch rule as re-attestation cadence; the authority field with a principal-held co-signer and time-bounded delegation as the policy lever.

*Target.* A composition theorem: if consensus weight is bounded by attested lineages (Prop. 5) and the topology is (F+1, F+1)-robust for F equal to the attested-lineage count the registry cannot exclude, then resilient consensus holds without any node identifying a bad neighbour; and a cost statement of the form "attestation cost per device is O(log N) against a transparency log, forgery cost is the proof system's soundness."

*First experiment.* Preregistration item 6 (identity splitting and churn through the registry, 1 to 32 identities, aggregate reward invariant) rerun with the reward replaced by consensus weight, then a W-MSR simulation on r-robust graphs where F is the registry's output rather than a parameter.

*Why it favours the defender.* The defender enrols once, at a lab it controls, and the attacker must forge a proof rather than spoof a count. In Taiwan the enrolment point exists: the non-red supply chain and the TTC test laboratory are the settled set and the verifier.

### 5.6 Runtime assurance as viability: shields, relays, and inconsistent world-models

*Question.* Can the per-platform safety fallback and the per-relay error accumulation be stated as one bound, and does a sheaf residual detect a spoofed platform before its neighbours follow it?

*Literature.* Simplex (Seto, Krogh, Sha) and SOTER (Desai et al., drone surveillance with misbehaving third-party components): the defender trusts a small verified core and a switch, not the stack; Black-Box Simplex and stochastic sandboxing extend it; no paper treats compromise of the monitor itself, and no verification guarantee exists for a swarm under an active adversary. Fawzi, Tabuada, Diggavi: state reconstruction is impossible beyond half the sensors attacked and needs 2q-sparse observability for q; Nakahira and Mo weaken this to 2ρ-detectability. The 2026 swarm GNSS-spoofing work shows spoofing one platform propagates.

*Ours.* Thm. B (shield invariance), Thm. C (end-to-end relay error ε_p ≤ ε_k + L_k ε_{k−1} + …, patch diameter as the control), Thm. A (sheaf energy zero iff compatible global section), HardAdmit with explicit ABSTAIN / ESCALATE / SAFE-STOP bottoms. Thm. C is stated without proof; the one empirical sheaf test added nothing.

*Target.* Prove Thm. C; state the stochastic version of Thm. B with a pathwise risk budget that does not assume independence across platforms; and show, or refute, that the sheaf residual on neighbours' position estimates is a detector of the spoofed platform with a bound in terms of the 2q-sparse-observability margin.

*First experiment.* A sealed swarm-formation model with one spoofed platform; compare sheaf-residual detection time against the cumulative-sign detector (Bonczek et al.) and a plain consistency check; register the margin at which the sheaf adds nothing, since that is what the gym found.

*Why it favours the defender.* The verified core is small and the attacker must defeat it on every platform; the relay bound says how many hops a decision may travel before the defender must re-verify.

### 5.7 Topology for recovery and robustness

*Question.* Is there a cheap spectral certificate for r-robustness, and does the spectral gap predict recovery under adversarial rather than benign perturbation?

*Literature.* Determining a graph's robustness is coNP-complete (Zhang, Fata, Sundaram; others say NP-hard, the labels conflict), so no cheap certificate exists for swarm-scale graphs; robustness is strictly stronger than connectivity and minimum degree; control-barrier functions can maintain strong r-robustness in a reconfiguring swarm; Pirani, Mitra, Sundaram survey the field.

*Ours.* The spectral-gap predictor (6.11% and 12.30% held-out gain), with the directional claim failed twice and clustering and path length unresolved as confounds.

*Target.* A sufficient spectral condition for (r, s)-robustness, or a proof that none exists; and a test of whether λ₂ predicts recovery when the perturbation is an adversary's rather than a random one.

*First experiment.* REPORT.md's first falsification item (graph pairs separating spectral gap from clustering and path length) with the perturbation replaced by a W-MSR-style adversarial node. This is the weakest-evidence avenue and should be last.

### 5.8 Supply-chain integrity as a cut bound

*Question.* What does it cost to audit N mass-produced platforms against the cost of compromising one, and can the registry's settled set be rooted in a binary-transparency log?

*Literature.* Merkle history trees (Crosby and Wallach) and Certificate Transparency give O(log n) membership and consistency proofs with split views detectable by gossip, of which there is "next to no deployment"; CoSi cosigns with thousands of witnesses; reproducible builds (Lamb and Zacchiroli) and diverse double-compiling (Wheeler, with a formal proof) make an artefact auditable once rather than per device. No paper models audit-N-versus-compromise-one for hardware; random inspection detects one bad unit among N with probability about n/N, and a transparency log changes that by auditing the artefact once and reducing per-device substitution to the split-view problem.

*Ours.* The registry's root_n as a Merkle commitment to the settled set; the epoch rule; the adventure-verifier tamper matrix (36 of 36 tampers rejected, each by its predeclared verifier) as a template for tamper-evident platform telemetry.

*Target.* An audit-cost model in which the defender's cost is O(log N) per device plus one build comparison and the attacker's is a split view that gossip detects with a stated probability; and the TIDRONE vector (common ERP software across manufacturers) as the case study.

*First experiment.* A sealed model of N devices, k substituted, with a transparency log and a gossip rate; register detection probability against gossip coverage, and compare to sampling.

*Why it favours the defender.* The audit is of the artefact, once; the attacker must substitute per device and must do so without leaving a split view.

### 5.9 Evaluation discipline as the platform's governance

This is not a theorem target but it is the reason anyone should trust the others. Every study runs preregistered with a stated target, smallest effect of interest, precision, design, budget, stopping rule and a forecast of success; abstention is scored and rewarded only when an oracle certificate shows the target was unreachable; seeds are frozen in disjoint discovery, confirmation and holdout sets; every gated number is recomputed from raw episodes by a verifier script; disputes in review end in a witness, a proof with a stated domain, a narrowed claim, or an open obligation, never in a vote; selection, evidence and hazard metrics are disjoint; and behaviour is never reported as intent. The sandbagging protocol (frozen analysis rules for a controller that behaves differently when it believes it is audited) applies directly to autonomous platforms under evaluation. The dual-use edge is explicit: the confinement-transfer generator is an evader-side search and is reported as a red-team generator for monitor blind spots, within the "evidence for monitors" commitment, and the same wording discipline governs everything the platform publishes.

## 6. The platform

*What it is.* A program of sealed, non-operational model studies, each with its own verifier, run on a shared simulator that carries the objects the theorems are stated over: a metered resource with a settled set and a registry, a demand or engagement process the defender partly controls, a scalar coordination capacity, and a table of observers each of whom sees one row. Nothing connects to a radio, a vehicle, a wallet, or a network. Outputs are bounds, phase maps, and detection curves with receipts.

*What it is not.* It is not an evasion toolkit, a C2 design, a weapon, or a live measurement. The safety boundary is the one already enforced by `verify_stego_swarm_limit_artifacts.py` and the hive-lab README: no transport, no payload, no codec, no attempt to optimise evasion of a real monitor.

*Who plugs in.* The attestation lab (ITRI / TTC) as the verifier whose view of the settled set is the condition on 5.1 and 5.5; the cyber authorities (MODA's Administration for Cyber Security, NICS, TWCERT/CC) as the warden rows; the military cyber command (ICEFCOM) and NCSIST as the consumer of monitoring-placement results; the drone procurement program as the settled set. Each receives bounds and detection curves, not code that runs on a platform.

*Twelve-month deliverables, in order of dependence.*

| Month | Deliverable | Avenue |
|---|---|---|
| 1–2 | The general bound stated and proved for capacity-constrained flow with node weights, with the safety/reward split as a conjecture; preregistration published. | 5.1 |
| 2–4 | Stackelberg-demand and partial-shift extension of the stego model; the forecast-floor curve against persistence and re-observation cost. | 5.1, 5.3 |
| 3–5 | Same-weights-versus-same-controller separation test (lnmath item 8); the capital-versus-trace result restated for attestation rows. | 5.4 |
| 4–6 | Registry-rooted F for W-MSR; identity-splitting rerun with consensus weight. | 5.5 |
| 5–8 | Re-tasking saturation C*(τ) and the noisy-link square-root check. | 5.2 |
| 6–9 | Thm. C proved; sheaf-residual spoofing detector against cumulative-sign, with the registered null. | 5.6 |
| 8–11 | Transparency-log audit model with TIDRONE as the case. | 5.8 |
| 10–12 | Spectral certificate attempt; adversarial-perturbation recovery test. | 5.7 |
| throughout | Verifier scripts, sealed holdouts, adversarial review in the Swarm Arena format, a public knowledge card per result. | 5.9 |

*What is asked.* A speaker slot or a poster, waived registration, and introductions to the attestation lab and the cyber authorities named above. *What is offered.* The first deliverable, the general bound with its preregistration, published before the talk, so that the audience is judging a stated theorem and not a promise.

## 7. Conference plan

The search pass found no confirmed cybersecurity or defence-technology conference in Taiwan between 28 November 2026 and 10 January 2027 with an open call for talks and a known speaker-admission policy. What it found:

| Event | Dates | Standing |
|---|---|---|
| CYBERSEC 2027 (iThome) | May 2027, Taipei | No announcement yet; the 2022 call opened in November–December of the prior year, so the call may open inside the trip window. Primary target. |
| HITCON 2027 | August 2027, Taipei | Call likely in Q2 2027; the 2026 theme was agentic systems, which fits. |
| Taiwan–France Cybersecurity and AI Workshop | 5–6 Nov 2026, Academia Sinica | Poster deadline passed 12 October; late participation only by contacting organisers. |
| TWCERT/CC annual meeting (NICS) | 3 Nov 2026 | No call found. |
| ADI CYBERDAY 2026 (MODA) | Nov 2026, unconfirmed | No call found. |
| TAAI 2026 | 20–21 Nov 2026, New Taipei | Submissions closed; theme "Agentic AI and Physical AI"; attend to meet people. |
| Aggregator listings (ICCAC 29 Nov, ICCCC 3 Dec, "Robotics and Cybersecurity Integration" 4–5 Dec Kaohsiung) | in window | Unverified organisers; likely low quality; do not pitch. |

The practical sequence: send the abstract and the first deliverable to the MODA ADI, NICS, and Taiwan–France workshop contacts now, ask each whether a short talk or a meeting during the December trip is possible and whether speaker registration is waived; watch the CYBERSEC 2027 call and submit the moment it opens; treat the December trip as the meeting round and CYBERSEC as the stage. Chinese-language local events were poorly indexed by the search, so absence is weak evidence and a local contact should be asked.

## Appendix A. Abstract for submission (248 words)

Cheap autonomous platforms move the contested layer of a conflict from the vehicle to its control plane, where the operative question is who controls a swarm and whether anyone can tell. We propose a mathematics for the defender's side of that question and report two results from sealed, non-operational model studies that locate the defender's structural advantage. First, a population of agents under one controller, holding a metered resource and coordinating over a covert channel, gains no more over independent placement than its authenticated resource placed under a stationary environment, whatever the channel's capacity: the coordination value saturates at the bits needed to name a placement, the gain is bounded by an exact optimum of the resource, and it collapses when the environment moves after the placement, which the defender controls. Second, the signature of common control sits in the resource commitment, which any observer reads, rather than in the traffic, which a strong observer reads only where coordinating was worth doing, because the channel's value and its footprint are the same quantity. We map these to swarm defence, state where the mapping strains, and set out eight research avenues joining them to resilient consensus, secure estimation, covert-channel capacity, Stackelberg commitment, collective attestation, and transparency logs, each with a preregistered first experiment. We argue that an audited supply chain and a national drone-cybersecurity test regime are exactly the settled set and the verifier these bounds are stated over, and that the monitoring budget belongs at enrolment and commitment, not on the wire.

## Appendix B. Talk outline, 25 minutes

1. Who controls this swarm, and can anyone tell (2 min). The question, the three meanings of 6GW, which one is meant.
2. Three resources an attacker must spend (3 min). Capital, forecast, channel; the claim that the third is second-order.
3. The saturation limit (3 min). C* ≤ ⌈B/w⌉⌈log₂ L⌉; the live agent that did worse than a water-fill below it.
4. The capital ceiling and the forecast floor (4 min). The exact optimum; the shift; the table of success 0.66 → 0.08 with the ceiling at 0.67.
5. The firewall (4 min). The 2×2 factorial; capital AUC 1.00 at every rate; trace AUC falling with channel value; the trained warden and what it changes.
6. Where the mapping strains (2 min). The honest list from §4.
7. What the literature holds and does not (3 min). Casper, SybilLimit, the square-root law, W-MSR's "F must be known"; the theorem nobody has stated.
8. The platform and the ask (3 min). Settled set, verifier, observers; the attestation lab as the verifier; what is delivered before the talk.
9. Questions (1 min reserved; the rest to the chair).

## Appendix C. Pitch email to an organiser

Subject: A short talk on defender-favoured mathematics for autonomous-swarm security, December visit

I am an independent researcher (TradeLayer; the Spiral and ALife programs, github.com/patrickdugan/spiral and github.com/MoralityLabAI/ALife) and will be in Taiwan in early December. I would like to offer a short talk, or a poster, on two results from sealed model studies that bear on swarm cyber-defence: that a population of autonomous agents under one controller gains no more from covert coordination than its authenticated resource placed under a stationary environment, whatever its channel capacity, and that the signature of common control sits in the resource commitment rather than in the traffic. Both are stated with their conditions and their limits, and both point the monitoring budget toward enrolment and attestation rather than toward the wire, which is where Taiwan's non-red supply chain and the TTC drone-cybersecurity laboratory already sit. The abstract is attached, with a research map of eight avenues and a preregistered first experiment for each. If a slot is possible I would ask whether speaker registration is waived; if not, I would be glad of a meeting with your technical staff during the visit. The work is defensive and non-operational by construction, and every number in it recomputes from a verifier script in the public repositories.

## Support files

- `asymmetric_defense_platform_support/inventory.md`: every formal result, open problem, tool and methodological commitment in both repositories, with paths.
- `asymmetric_defense_platform_support/lit_swarm_resilience.md`: resilient consensus, secure estimation, runtime assurance, security games, covert channels, rate-limited coordination.
- `asymmetric_defense_platform_support/lit_asymmetric_economics.md`: security economics, verifiable computation and attestation, Sybil and stake bounds, payment-channel theory, supply-chain integrity, focal-point coordination.
- `asymmetric_defense_platform_support/doctrine_conferences.md`: the three meanings of 6GW, Taiwan's drone and cyber institutions, the published swarm-threat literature, and the conference landscape with dates.

Two handoff documents on the author's machine, the 6GW mathematical research handoff of 2026-10-18 and the drone-swarm cybersecurity baseline problem, were not available in the session that produced this document and are not reflected in it; they should be reconciled with §3 and §5 before the pitch goes out.
