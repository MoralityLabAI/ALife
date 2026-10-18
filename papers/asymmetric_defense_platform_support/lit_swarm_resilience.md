*Literature pass of 2026-10-18 supporting `../asymmetric_defense_platform.md`. Compiled from search-result abstracts and summaries; no full text was read in the session, so every statement must be checked against the paper before citation. Tags: [A] stated in an abstract or snippet, [M] researcher background knowledge, [X] sources conflict.*

# Annotated bibliography: swarm resilience / detection / verification / games / covert channels / rate-limited coordination
(Sonnet researcher report, 2026-10-18. Evidence tags: [A] stated in abstract/snippet; [M] researcher's background knowledge, unverified; [X] sources disagree. WebFetch failed on every host; nothing read from full text.)

## Thread 1 Resilient consensus
- LeBlanc, Zhang, Koutsoukos, Sundaram, "Resilient Asymptotic Consensus in Robust Networks," IEEE JSAC 31(4) 2013. W-MSR; F-total needs (F+1,F+1)-robustness (iff); F-local: (2F+1)-robust sufficient, (F+1,F+1) necessary [M, partly corroborated]. Guarantee purely topological; nodes need only bound F.
- Zhang & Sundaram, arXiv 1110.3843 (2012): r-robustness; construction; preferential attachment graphs robust.
- Zhang, Fata, Sundaram, arXiv 1203.6119 / IEEE TCNS: robustness strictly stronger than connectivity + min degree; same threshold on ER/geometric/PA; determining robustness extent is coNP-complete [A] (other papers say NP-hard, MILP: 1906.09096) [X].
- Vaidya, Tseng, Liang, PODC 2012, arXiv 1201.4183: tight graph condition for iterative approximate Byzantine consensus on directed graphs.
- Time-varying: Saldaña et al. ACC 2017; Usevitch & Panagou IEEE TAC 2020 (arXiv 1906.09096); joint robustness IEEE TAC 2023 (precursor Wen, Lv, Zhou, Fu 2020: jointly (F+1,F+1)-robust iff); Lee & Panagou arXiv 2510.01144 partial resilient consensus (2026); Pirani, Mitra, Sundaram survey Automatica 2023, arXiv 2205.12498.
- Design: CBF maintaining strong r-robustness, arXiv 2409.14675; Cavorsi et al. T-RO 2023.
- Open (Wardega et al. AAMAS 2023, arXiv 2301.06977): F must be known; ~2F+1 neighbours; slow propagation; tied to linear consensus. coNP-completeness of robustness checking.

## Thread 2 Detection / secure estimation
- Fawzi, Tabuada, Diggavi IEEE TAC 2014, arXiv 1205.5073: impossible beyond half the sensors attacked; characterises max detectable/correctable attacks via (A,C); 2q-sparse observability [M].
- Mishra, Shoukry, Karamchandani, Diggavi, Tabuada IEEE TCNS 2017, arXiv 1510.02462: optimal error bounds with noise. Shoukry & Tabuada arXiv 1309.3511.
- Nakahira & Mo IEEE TAC 2018, arXiv 1803.07053: 2ρ-detectability necessary (weaker than 2ρ-observability); estimator meets it.
- Pasqualetti, Dörfler, Bullo IEEE TAC 2013 Parts I/II, arXiv 1202.6144 / 1202.6049: fundamental limits of detection/identification; undetectability via invariant zeros [M].
- Pasqualetti, Bicchi, Bullo IEEE TAC 2012, arXiv 1007.2738: misbehaving agents as unknown inputs; FDI; graph-theoretic solvability.
- Mo & Sinopoli Allerton 2009 watermarking (χ² detector, performance cost); Mo, Weerakkody, Sinopoli IEEE CSM 2015; online watermark design arXiv 1911.01868, 1809.05299.
- Bai, Pasqualetti, Gupta Automatica 2017, arXiv 1704.00748: ε-stealthiness against arbitrary detector; degradation characterised [KL divergence, M].
- Swarm-specific: Bonczek et al. T-RO 2022 cumulative-sign detector with bounds; Wardega et al. AAMAS 2023 decentralised blocklist from accusations.
- Open: no information-theoretic converse "any detector needs ≥N observations" for a stealthy swarm attack [inferred]; necessary-and-sufficient with noise; decentralised identification under unknown F.

## Thread 3 Runtime assurance / verification
- Simplex: Seto, Krogh, Sha, Chutinan ACC 1998; Sha IEEE Software 2001. Black-Box Simplex arXiv 2102.12981 (multi-agent variant exists). SOTER (Desai, Ghosh, Seshia, Shankar, Tiwari DSN 2019, arXiv 1808.07921): drone surveillance with misbehaving third-party components. Zhong, Zamani, Caccamo arXiv 2109.11264 stochastic sandboxing.
- PMC: Kwiatkowska, Norman, Parker ARCRAS 2022 arXiv 2111.10630 (PRISM-games); Gainer et al. drone foraging; Gu et al. RO-MAN 2023 runtime SMC; arXiv 2504.02964 predictive RV under STL (centralised); Luckcuck et al. survey arXiv 1807.00048 (scaling barrier).
- Open: no verification guarantee for a swarm under an active adversary [inferred]; Simplex assumes core + switch uncompromised; no treatment of compromised monitor found.

## Thread 4 Games with asymmetry
- FlipIt: van Dijk, Juels, Oprea, Rivest J. Cryptology 2013; periodic strategies dominate renewal; in periodic NE the higher-move-cost player gets benefit 0 [A via 1508.01950]; equilibrium rates depend on cost ratio [M]. Caveat: hyperbolic discounting breaks periodic dominance (MDPI Games 14(6):74, 2023). QFlip arXiv 1906.11938.
- SSG: Korzhyk, Yin, Kiekintveld, Conitzer, Tambe JAIR 41 (2011); von Stengel & Zamir GEB 2010: leader payoff ≥ Nash payoff (two players; fails with ≥3); An et al. AAAI 2011; Guo et al. AAAI 2019 arXiv 1811.03823 inducibility.
- Cost asymmetry: Iliaev, Oren, Segev Ann. Oper. Res. 320 (2023) Tullock contest: tight upper bound on defender cost reduction from sequential commitment. No general "ratio ≤ X" theorem found.
- MTD: survey arXiv 1909.08092; optimal timing Stackelberg arXiv 1905.13293; Pawlick, Colbert, Zhu arXiv 1503.05458, 1804.06831 (evidence always helps uninformed player); deception taxonomy arXiv 1712.05441; optimal deception vs informed attacker NP-hard (USC CAIS).
- Open: no SSG/FlipIt results specific to swarms; commitment theorems fail with ≥3 players / multi-target followers (exactly the colluding-swarm regime).

## Thread 5 Covert channels / collusion
- Cachin 1998 (ePrint 2000/028): steganographic security = KL(P_C || P_S).
- Wang & Moulin arXiv cs/0702161: capacity of perfectly secure stego.
- Bash, Goeckel, Towsley IEEE JSAC 2013, arXiv 1202.6423: square-root law, O(√n) covert bits in n uses; arXiv 1403.1013 timing ignorance gains O(min{√n log T, n}).
- de Witt, Sokota, Kolter, Foerster, Strohmeier ICLR 2023, arXiv 2210.14889: perfectly secure iff induced by a coupling; max throughput iff minimum-entropy coupling (attacker-side achievability on known cover distributions).
- Motwani et al. NeurIPS 2024, arXiv 2402.07510: secret collusion among AI agents; capacity/incentive theory; mitigation limits.
- Mathew et al. arXiv 2410.03768 (emergence under misspecified reward); Tailor arXiv 2510.04303 "Audit the Whisper" (capacity + detectors, FP budget); arXiv 2603.15655 circuit breaker for latent-channel collusion in MARL; arXiv 2604.01151 NARCBench activation probes.
- Open: no square-root-law analogue for text/agent channels; detector guarantees benchmark-calibrated not worst-case; no tight detection-vs-capacity tradeoff for agent teams.

## Thread 6 Rate-limited coordination
- Data-rate theorem: Tatikonda & Mitter IEEE TAC 2004; Nair, Fagnani, Zampieri, Evans Proc. IEEE 2007: rate ≥ Σ log|λ_i| over unstable modes; sharp threshold. Sahai & Mitter anytime capacity arXiv cs/0601007.
- Multi-agent bits: Li, Fu, Xie, Zhang one-bit consensus; Hong et al. arXiv 1609.09206 (m to 2m bits, earlier results conservative); Feng & Ishii bit-rate under DoS.
- Cuff, Permuter, Cover "Coordination Capacity" IEEE TIT 2010, arXiv 0909.2408: achievable joint action distributions given rates; rate region; Cover–Permuter ISIT 2007 left a three-node problem open.
- Empirical: Marcotte et al. OCBC (10x less comms); no theorem that coordination value saturates in capacity for multi-robot tasks.
- Open: necessary minimum rates for consensus on general linear MAS; multi-agent anytime-capacity analogue.
