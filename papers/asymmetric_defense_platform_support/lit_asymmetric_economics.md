*Literature pass of 2026-10-18 supporting `../asymmetric_defense_platform.md`. Compiled from search-result abstracts and summaries, with eprint.iacr.org abstracts fetched directly; no full text was read, so every statement must be checked against the paper before citation. Tags: [F] abstract fetched, [S] search summary, [M] researcher background knowledge, [I] inference.*

# Annotated bibliography: defense cheaper than attack — economics, verification, Sybil/capital bounds, PCN theory, supply chain, focal points
(Sonnet researcher, 2026-10-18. Tags: [F] abstract fetched; [S] search summary; [M] memory; [I] inference. Only eprint.iacr.org and microsoft.com resolved for fetch.)

## Headline
- No paper found stating "coalition advantage ≤ authenticated stake regardless of coordination/communication". Nearest: Casper accountable safety (≥1/3 stake burned to revert finality), Sheng et al. BFT forensics, LaKSA coalition safety (reward share ≈ stake share + slack, α<1/3), SybilLimit O(log n) per attack edge, Durvasula–Roughgarden overcollateralization.
- Gaži–Kiayias–Russell (CCS 2020, eprint 2020/661): PoW secure iff r_a < 1/(Δ + 1/r_h); delay Δ enters; capital-only bound is the Δ→0 limit.
- Where stake bound fails: Ferreira–Weinberg (strategic PoS miner wins with ~32.8% stake), Brown-Cohen et al. (no honest NE without external randomness), Chitra–Penna–Schneider (stake splitting under partial slashing), Chung–Shi (no 1-SCP TFM).
- Real cost-asymmetry theorems: Gupta–Saia–Young resource burning, good spend O(√(T·J)+J) vs adversary T (arXiv 2010.06834, JCSS 2023); Chakraborty et al. "Bankrupting DoS Attackers" arXiv 2205.08287; SybilLimit; Casper 1/3; GKR verifier (n+d)polylog(n); Groth16 3 elements/3 pairings; Merkle log O(log n) audits.

## Thread 1 Security economics
- Gordon–Loeb (ACM TISSEC 2002): z* ≤ (1/e)vL for log-convex breach functions; fails for logistic (Ebel & Mitra arXiv 2207.09497 / J. Cybersecurity 2024, Stackelberg extension: attacker presence raises optimal spend, three regimes).
- Anderson & Moore, Science 2006 (framing). Varian 2004 sum/weakest-link/best-shot. Hirshleifer 1983; Kovenock–Roberson–Sheremeta (CESifo WP 3211); Clark–Konrad 2007; Modak Chowdhury–Topolyan 2016; arXiv 2603.25979 (weakest-link/best-shot = General Lotto with budget × battlefields). Böhme & Moore "Iterated Weakest Link" J. Inf. Sec. 2016.
- Korzhyk, Conitzer, Parr AAAI 2010 complexity of Stackelberg security strategies.
- Dwork & Naor CRYPTO '92; Juels & Brainard NDSS 1999; Herley WEIS 2012 (attacker base-rate model).
- Open: no unified Gordon–Loeb with adaptive attackers; no formal "defender's dilemma" source.

## Thread 2 Verifiable computation / attestation
- GKR STOC 2008 / JACM 2015: verifier (n+d)polylog n, comm d polylog n. Groth EUROCRYPT 2016 (eprint 2016/260): 3 elements, 3 pairings; 2-element open. STARKs eprint 2018/046 [F]. Walfish & Blumberg CACM 2015: prover is the bottleneck, amortisation needed.
- Armknecht, Sadeghi, Schulz, Wachsmann CCS 2013 (eprint 2013/083) [F]: formal framework, sufficient conditions only. Castelluccia et al. CCS 2009 attacks on software attestation. VRASED USENIX Sec 2019 (first formally verified RA, MSP430).
- Collective attestation: SEDA CCS 2015 (spanning tree, full connectivity); SANA CCS 2016 (aggregate signatures, 10^6 devices ~2.5 s); PADS arXiv 1806.05766; Catt arXiv 2407.09203 (40 protocols in Tamarin); zRA NDSS 2024, PIRANHAS NDSS 2025 (zkSNARK, recursive aggregation, 356 ms on capable hardware); PRIVÉ SECRYPT 2025 (UC model).
- No published bound on per-device attestation cost vs adversary forge cost; no MCU-class prover measurements found. [gap]

## Thread 3 Sybil / capital-bounded adversaries
- Douceur IPTPS 2002 [F abstract]. Garay–Kiayias–Leonardos (eprint 2014/765) [F]. Gaži–Kiayias–Russell (eprint 2020/661) [F]. Budish NBER 24717 (flow payments must be large vs stock attack gain; security cost linear in attack value).
- Casper FFG arXiv 1710.09437: accountable safety (≥1/3 deposit slashed), plausible liveness; open: attacker cost vs client disagreement. Sheng et al. CCS 2021 BFT forensics (impossible for 2t+1 synchronous). Ouroboros Praos (eprint 2017/573). LaKSA NDSS 2021 coalition safety.
- Failures: Brown-Cohen, Narayanan, Psomas, Weinberg arXiv 1809.06528; Ferreira & Weinberg arXiv 2107.04069; Fanti et al. FC 2019 equitability arXiv 1809.07468; Chung & Shi SODA 2023 (eprint 2021/1474) Thm 1.1; Chung–Roughgarden–Shi EC 2024; Chitra, Penna, Schneider arXiv 2509.18338; Durvasula & Roughgarden ITCS 2025 arXiv 2407.21785; Chitra & Pai arXiv 2408.00928.
- Cut-bounded Sybil: SybilLimit S&P 2008 (O(log n) per attack edge, Θ(n/log n) optimal for mixing-based); Advogato USENIX Sec 1998 (flow trust metric; critique: gain quadratic in attack cost); Cheng & Friedman 2005; Seuken & Parkes impossibility vs Stannat et al. AAMAS 2021; Pan et al. arXiv 2407.14485; Yokoo 2004; Aziz, Bachrach, Elkind, Paterson JAIR 2011 arXiv 1401.3869 (false-name in weighted voting, NP-hard; Rey & Rothe PP-hard).

## Thread 4 Payment-channel theory
- Spider NSDI 2020 arXiv 1809.05088 (throughput bounded by max circulation [M]; deadlocks open). Podiatchev, Orda, Rottenstreich eprint 2024/1393 [F] stopping time. Zibakhsh Shabgahi et al. eprint 2022/1376 [F] random-walk lifespan. arXiv 2511.16376 failure times (capacity²/betweenness; tightness unproved). Dehshali et al. eprint 2022/1614 [F]. Pickhardt et al. arXiv 2103.08576, 2107.05322 (min-cost flow, separable convex). arXiv 2601.04835 (2026, unverified) feasibility iff maxflow ≥ a.
- No fluid-limit throughput theorem under random arrivals found.

## Thread 5 Supply chain / firmware
- Crosby & Wallach USENIX Sec 2009 history tree O(log n). RFC 6962/9162 CT. Chuat et al. arXiv 1511.01514 gossip; arXiv 1806.08817 ("next to no deployment"); CoSi S&P 2016 arXiv 1503.08768; Parker & Ryan 2020 PMC of CT gossip. Sigstore/Rekor threat model (no formal model found). Lamb & Zacchiroli IEEE Software 2022 arXiv 2104.06020; Malka, Zacchiroli, Zimmermann MSR 2025; Wheeler DDC arXiv 1004.5534 (formal proof). Contour (Al-Bassam & Meiklejohn) [M].
- No "audit N vs compromise one" model found. [I] random sampling detects one bad unit w.p. ~n/N; transparency logs audit the artefact once (O(log N)) and reduce per-device substitution to the split-view problem.

## Thread 6 Focal points / common information
- Halpern & Moses JACM 1990 (coordinated attack: no common knowledge without guaranteed delivery). Dwork & Moses 1990 crash failures. Rubinstein 1989 email game; Morris 2000. Monderer & Samet GEB 1989 common p-belief; Neeman 1996 (1−p, tight). Aumann 1974/1976. Bacharach 2006, Sugden 1995 team reasoning; no theorem deriving focal points from common information [gap].
- Bárány MOR 1992: n≥4, correlated equilibrium = NE of cheap-talk extension, needs private pairwise channels; Heller GEB 2010 minority-proof. Abraham, Dolev, Gonen, Halpern PODC 2006 k-resilient. Angluin STOC 1980: no deterministic symmetry breaking in anonymous networks (coverings). Morris & Shin AER 2002 public information. Halpern & Pass JET 2015 costly computation.

## Open problems named
1 Groth 2-element SNARG. 2 Casper attacker cost vs disagreement. 3 Spider deadlocks/incentives. 4 arXiv 2511.16376 tightness. 5 resource-burning survey open list (arXiv 2006.04865). 6 incentive-compatible PoS. 7 Sybil-proof accounting definitions. 8 false-name manipulation complexity. 9 necessary conditions for software attestation. 10 full-connectivity in swarm attestation. 11 CT gossip deployment. 12 forensic support landscape. 13 cheap-talk implementation n<4 [I]. 14 Gordon–Loeb beyond log-convex. 15 coalition resilience in TFM.

## Synthesis [I]
Threads 3 and 4 are conservation-plus-cut bounds (SybilLimit attack-edge cut, Casper quorum intersection, PCN max-flow ≤ min-cut). Conjecture: safety-type bounds can be stake-only; liveness- and reward-type bounds cannot (Δ enters GKR; rewards exceed stake share in Ferreira–Weinberg). Unifying object: capacity-constrained flow on a graph with node weights; no paper does this unification.
