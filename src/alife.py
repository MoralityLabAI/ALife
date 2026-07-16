#!/usr/bin/env python3
# Simultaneous multi-plane artificial life experiment:
# - Conway-style life dynamics
# - shape-triggered gateways between planes
# - manufacturable and evolvable cell types
# - abstract mechanics inspired by generational swarms/agents (Creatures-style flavor)

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Coord = Tuple[int, int]


@dataclass
class Cell:
    kind: str
    age: int = 0
    energy: float = 1.0
    flavor: str = "native"
    love: float = 0.0
    fervor: float = 0.0
    focus: float = 0.0
    coherence: float = 0.0
    mania: float = 0.0
    meme: float = 0.0
    bond: float = 0.0
    pair_lock: float = 0.0
    species: str = "wild"
    attention: float = 0.0
    imprint: float = 0.0
    prediction: float = 0.5
    surprise: float = 0.0

    def copy(self) -> "Cell":
        return Cell(
            kind=self.kind,
            age=self.age,
            energy=self.energy,
            flavor=self.flavor,
            love=self.love,
            fervor=self.fervor,
            focus=self.focus,
            coherence=self.coherence,
            mania=self.mania,
            meme=self.meme,
            bond=self.bond,
            pair_lock=self.pair_lock,
            species=self.species,
            attention=self.attention,
            imprint=self.imprint,
            prediction=self.prediction,
            surprise=self.surprise,
        )


@dataclass
class PlaneRules:
    name: str
    survive: Tuple[int, ...]
    birth: Tuple[int, ...]
    life_gain: float = 1.4
    life_cost: float = 1.0
    decay: float = 0.08
    manufacturer_spawn_cost: float = 1.6
    manufacturer_spawn_energy: float = 1.4
    manufacturer_birth_bonus: float = 0.5
    mutation_rate: float = 0.05
    egg_hatch_turns: int = 4
    # kind -> possible evolutions with weights
    evolution_map: Dict[str, List[Tuple[str, float]]] = field(default_factory=dict)
    # planes can inject special interpretation on spawn / energy
    gate_risk_penalty: float = 0.0
    max_age: int = 90
    # plane mechanics
    shard_decay_penalty: float = 0.0
    echo_propagate_chance: float = 0.0
    norn_nurture: float = 0.0
    drone_dribble_cost: float = 0.0
    gate_cooldown: int = 1


@dataclass
class GateRule:
    """
    A gateway shape check uses relative coordinate offsets and required kinds.
    Kind can be "any" or "empty" to widen the match.
    """

    name: str
    from_plane: str
    to_plane: str
    to_kind: str
    chance: float
    checks: List[Tuple[int, int, str]]
    anchor: Coord = (0, 0)
    consume: bool = True
    min_age: int = 1
    effects_enabled: bool = True
    # Experimental collision diagnostic. Zero preserves native placement.
    placement_search_radius: int = 0


ALIVE = {
    "life",
    "norn",
    "manufacturer",
    "drone",
    "shard",
    "echo",
    "drone_mother",
    "norn_maker",
    "goblin",
    "insight",
    "anomaly",
    "meme",
    "axiom",
    "cult",
    "ritual",
    "model",
    "oracle",
    "cache",
    "proof",
    "bug",
    "trace",
}
CHAR_FOR_KIND = {
    "empty": ".",
    "life": "O",
    "norn": "N",
    "manufacturer": "M",
    "egg": "e",
    "drone": "d",
    "goblin": "g",
    "shard": "s",
    "echo": "E",
    "norn_maker": "@",
    "drone_mother": "#",
    "insight": "I",
    "meme": "v",
    "anomaly": "A",
    "axiom": "Y",
    "cult": "C",
    "ritual": "R",
    "model": "P",
    "oracle": "W",
    "cache": "K",
    "proof": "p",
    "bug": "x",
    "trace": "T",
}


class LifeUniverse:
    def __init__(
        self,
        width: int,
        height: int,
        seed: int,
        seed_density: float = 0.22,
        rule_modifiers: Optional[Dict[str, float]] = None,
    ):
        self.width = width
        self.height = height
        random.seed(seed)

        self.planes: Dict[str, PlaneRules] = self._build_planes()
        self.gates: List[GateRule] = self._build_gate_rules()
        self.rule_modifiers = rule_modifiers or {}
        self.cache_pressure_scale = self.rule_modifiers.get("cache_pressure_scale", 1.0)
        self.proof_stability_scale = self.rule_modifiers.get("proof_stability_scale", 1.0)
        self.bug_parasite_scale = self.rule_modifiers.get("bug_parasite_scale", 1.0)
        self.evolution_cache_scale = self.rule_modifiers.get("evolution_cache_scale", 1.0)
        self.evolution_bug_scale = self.rule_modifiers.get("evolution_bug_scale", 1.0)
        self.conversion_cache_scale = self.rule_modifiers.get("conversion_cache_scale", 1.0)

        self.grids: Dict[str, List[List[Optional[Cell]]]] = {
            plane_id: [[None for _ in range(width)] for _ in range(height)]
            for plane_id in self.planes
        }
        self._seed_initial(seed_density)
        self.tick_count = 0
        self.last_events: Dict[str, int] = {}
        self.complexity_history: List[float] = []
        self.last_metrics: Dict[str, float] = {}
        self._last_counts: Optional[Dict[str, Dict[str, int]]] = None
        self._gate_cooldowns: Dict[str, List[List[int]]] = {
            plane_id: [[0 for _ in range(width)] for _ in range(height)] for plane_id in self.planes
        }
        self._apply_rule_modifiers()
        self.goblin_love_probability_scale = self.rule_modifiers.get("goblin_love_probability_scale", 1.0)
        self.goblin_feed_probability_scale = self.rule_modifiers.get("goblin_feed_probability_scale", 1.0)
        self.goblin_mania_gain_scale = self.rule_modifiers.get("goblin_mania_gain_scale", 1.0)
        self.goblin_mania_decay_scale = self.rule_modifiers.get("goblin_mania_decay_scale", 1.0)
        self.goblin_pressure_scale = self.rule_modifiers.get("goblin_pressure_scale", 1.0)
        self.goblin_conversion_scale = self.rule_modifiers.get("goblin_conversion_scale", 1.0)
        self.goblin_mania_attack_scale = self.rule_modifiers.get("goblin_mania_attack_scale", 1.0)
        self.goblin_species_carry_scale = self.rule_modifiers.get("goblin_species_carry_scale", 1.0)
        self.goblin_species_mutation_scale = self.rule_modifiers.get("goblin_species_mutation_scale", 1.0)
        self.goblin_romance_scale = self.rule_modifiers.get("goblin_romance_scale", 1.0)
        self.goblin_species_romance_scale = self.rule_modifiers.get("goblin_species_romance_scale", 1.0)
        self.goblin_pair_pressure_scale = self.rule_modifiers.get("goblin_pair_pressure_scale", 1.0)
        self.goblin_pair_bond_gain_scale = self.rule_modifiers.get("goblin_pair_bond_gain_scale", 1.0)
        self.goblin_pair_lock_scale = self.rule_modifiers.get("goblin_pair_lock_scale", 1.0)
        self.goblin_pair_lock_decay_scale = self.rule_modifiers.get("goblin_pair_lock_decay_scale", 1.0)
        self.goblin_pair_crazy_scale = self.rule_modifiers.get("goblin_pair_crazy_scale", 1.0)
        self.goblin_pairing_lock_threshold = self.rule_modifiers.get("goblin_pairing_lock_threshold", 0.50)
        self.goblin_pairing_crazy_threshold = self.rule_modifiers.get("goblin_pairing_crazy_threshold", 0.46)
        self.goblin_species_ascend_scale = self.rule_modifiers.get("goblin_species_ascend_scale", 1.0)
        self.goblin_cult_scale = self.rule_modifiers.get("goblin_cult_scale", 1.0)
        self.goblin_axiom_scale = self.rule_modifiers.get("goblin_axiom_scale", 1.0)
        self.goblin_fervor_scale = self.rule_modifiers.get("goblin_fervor_scale", 1.0)
        self.goblin_focus_scale = self.rule_modifiers.get("goblin_focus_scale", 1.0)
        self.goblin_obsession_scale = self.rule_modifiers.get("goblin_obsession_scale", 1.0)
        self.goblin_overclock_scale = self.rule_modifiers.get("goblin_overclock_scale", 1.0)
        self.goblin_overflow_scale = self.rule_modifiers.get("goblin_overflow_scale", 1.0)
        self.goblin_attention_scale = self.rule_modifiers.get("goblin_attention_scale", 1.0)
        self.goblin_attention_decay_scale = self.rule_modifiers.get("goblin_attention_decay_scale", 1.0)
        self.goblin_imprint_scale = self.rule_modifiers.get("goblin_imprint_scale", 1.0)
        self.goblin_imprint_decay_scale = self.rule_modifiers.get("goblin_imprint_decay_scale", 1.0)
        self.goblin_prediction_scale = self.rule_modifiers.get("goblin_prediction_scale", 1.0)
        self.goblin_surprise_scale = self.rule_modifiers.get("goblin_surprise_scale", 1.0)
        self.goblin_trace_scale = self.rule_modifiers.get("goblin_trace_scale", 1.0)
        self.model_projection_scale = self.rule_modifiers.get("model_projection_scale", 1.0)
        self.oracle_projection_scale = self.rule_modifiers.get("oracle_projection_scale", 1.0)
        self.cognition_decay_scale = self.rule_modifiers.get("cognition_decay_scale", 1.0)
        self.insight_spawn_scale = self.rule_modifiers.get("insight_spawn_scale", 1.0)
        self.insight_learn_scale = self.rule_modifiers.get("insight_learn_scale", 1.0)
        self.insight_decay_scale = self.rule_modifiers.get("insight_decay_scale", 1.0)
        self.insight_transmute_scale = self.rule_modifiers.get("insight_transmute_scale", 1.0)
        self.insight_paradox_scale = self.rule_modifiers.get("insight_paradox_scale", 1.0)
        self.insight_cascade_scale = self.rule_modifiers.get("insight_cascade_scale", 1.0)
        self.meme_spawn_scale = self.rule_modifiers.get("meme_spawn_scale", 1.0)
        self.meme_broadcast_scale = self.rule_modifiers.get("meme_broadcast_scale", 1.0)
        self.meme_decay_scale = self.rule_modifiers.get("meme_decay_scale", 1.0)
        self.meme_conversion_scale = self.rule_modifiers.get("meme_conversion_scale", 1.0)
        self.meme_pressure_scale = self.rule_modifiers.get("meme_pressure_scale", 1.0)

    def _apply_rule_modifiers(self) -> None:
        # Optional knobs for model-driven experimentation.
        mutation_scale = self.rule_modifiers.get("mutation_scale", 1.0)
        life_gain_scale = self.rule_modifiers.get("life_gain_scale", 1.0)
        life_cost_scale = self.rule_modifiers.get("life_cost_scale", 1.0)
        decay_scale = self.rule_modifiers.get("decay_scale", 1.0)
        drone_cost_scale = self.rule_modifiers.get("drone_dribble_scale", 1.0)
        shard_penalty_scale = self.rule_modifiers.get("shard_penalty_scale", 1.0)
        echo_scale = self.rule_modifiers.get("echo_scale", 1.0)
        norn_scale = self.rule_modifiers.get("norn_scale", 1.0)
        gate_scale = self.rule_modifiers.get("gate_scale", 1.0)
        gate_risk_scale = self.rule_modifiers.get("gate_risk_scale", 1.0)

        for cfg in self.planes.values():
            cfg.mutation_rate *= mutation_scale
            cfg.life_gain *= life_gain_scale
            cfg.life_cost *= life_cost_scale
            cfg.decay *= decay_scale
            cfg.drone_dribble_cost *= drone_cost_scale
            cfg.shard_decay_penalty *= shard_penalty_scale
            cfg.echo_propagate_chance *= echo_scale
            cfg.norn_nurture *= norn_scale
            cfg.gate_cooldown = max(0, int(cfg.gate_cooldown))
            cfg.gate_risk_penalty = min(1.0, max(0.0, cfg.gate_risk_penalty * gate_risk_scale))

            # Species-level weights for late-ecosystem transitions.
            for source_kind, transitions in list(cfg.evolution_map.items()):
                scaled_transitions = []
                for target_kind, weight in transitions:
                    if target_kind == "cache":
                        weight *= self.evolution_cache_scale
                    elif target_kind == "proof":
                        weight *= self.proof_stability_scale
                    elif target_kind == "bug":
                        weight *= self.evolution_bug_scale
                    scaled_transitions.append((target_kind, max(0.0, weight)))
                cfg.evolution_map[source_kind] = scaled_transitions

        for gate in self.gates:
            gate.chance = min(1.0, max(0.0, gate.chance * gate_scale))

    @staticmethod
    def _build_planes() -> Dict[str, PlaneRules]:
        return {
            "GENESIS": PlaneRules(
                name="GENESIS",
                survive=(2, 3),
                birth=(3,),
                life_gain=1.2,
                life_cost=1.0,
                decay=0.05,
                manufacturer_spawn_cost=1.6,
                manufacturer_spawn_energy=1.2,
                mutation_rate=0.06,
                shard_decay_penalty=0.06,
                echo_propagate_chance=0.02,
                norn_nurture=0.18,
                drone_dribble_cost=0.0,
                gate_cooldown=2,
                evolution_map={
                    "norn": [("norn", 0.38), ("drone", 0.30), ("manufacturer", 0.18), ("goblin", 0.05), ("cache", 0.05), ("proof", 0.04)],
                    "egg": [("life", 0.45), ("norn", 0.25), ("drone", 0.12), ("goblin", 0.06), ("cache", 0.06), ("proof", 0.02), ("bug", 0.04)],
                    "drone": [("drone", 0.68), ("shard", 0.20), ("goblin", 0.05), ("cache", 0.05), ("proof", 0.02)],
                    "life": [("life", 0.90), ("norn_maker", 0.02), ("cache", 0.08)],
                    "shard": [("shard", 0.80), ("echo", 0.12), ("goblin", 0.04), ("bug", 0.03), ("proof", 0.01)],
                    "goblin": [("goblin", 0.62), ("shard", 0.16), ("drone", 0.10), ("norn", 0.08), ("cache", 0.02), ("proof", 0.02)],
                    "meme": [("meme", 0.54), ("insight", 0.18), ("axiom", 0.12), ("goblin", 0.04), ("life", 0.03), ("proof", 0.04), ("cache", 0.05)],
                    "insight": [("insight", 0.70), ("meme", 0.12), ("axiom", 0.10), ("cult", 0.02), ("goblin", 0.02), ("proof", 0.04), ("cache", 0.02)],
                    "axiom": [("axiom", 0.78), ("insight", 0.08), ("meme", 0.05), ("goblin", 0.03), ("cult", 0.01), ("proof", 0.05)],
                    "cult": [("cult", 0.66), ("meme", 0.12), ("insight", 0.10), ("life", 0.06), ("axiom", 0.02), ("proof", 0.04)],
                    "model": [("model", 0.56), ("insight", 0.14), ("axiom", 0.10), ("meme", 0.10), ("oracle", 0.06), ("proof", 0.04)],
                    "oracle": [("oracle", 0.66), ("model", 0.20), ("axiom", 0.10), ("proof", 0.04)],
                },
            ),
            "FORGE": PlaneRules(
                name="FORGE",
                survive=(2, 3, 4),
                birth=(3, 5),
                life_gain=1.0,
                life_cost=1.1,
                decay=0.04,
                manufacturer_spawn_cost=1.2,
                manufacturer_spawn_energy=1.6,
                mutation_rate=0.1,
                shard_decay_penalty=0.03,
                echo_propagate_chance=0.04,
                norn_nurture=0.26,
                drone_dribble_cost=0.35,
                gate_cooldown=1,
                evolution_map={
                    "norn": [("norn_maker", 0.32), ("drone", 0.22), ("manufacturer", 0.26), ("goblin", 0.05), ("insight", 0.03), ("cache", 0.12)],
                    "egg": [("drone", 0.47), ("manufacturer", 0.30), ("shard", 0.13), ("goblin", 0.03), ("cache", 0.05), ("proof", 0.02)],
                    "manufacturer": [("manufacturer", 0.68), ("norn_maker", 0.20), ("goblin", 0.05), ("cache", 0.07)],
                    "life": [("life", 0.88), ("drone_mother", 0.05), ("norn_maker", 0.02), ("goblin", 0.01), ("cache", 0.04)],
                    "shard": [("shard", 0.74), ("drone", 0.18), ("bug", 0.04), ("proof", 0.04)],
                    "goblin": [("goblin", 0.63), ("drone", 0.14), ("shard", 0.10), ("insight", 0.10), ("cache", 0.03), ("proof", 0.03)],
                    "meme": [("meme", 0.50), ("insight", 0.22), ("axiom", 0.10), ("goblin", 0.06), ("cult", 0.01), ("cache", 0.11)],
                    "insight": [("insight", 0.62), ("meme", 0.14), ("axiom", 0.14), ("cult", 0.03), ("goblin", 0.03), ("proof", 0.04)],
                    "axiom": [("axiom", 0.76), ("insight", 0.10), ("meme", 0.04), ("goblin", 0.03), ("cult", 0.03), ("proof", 0.04)],
                    "cult": [("cult", 0.68), ("meme", 0.12), ("insight", 0.08), ("life", 0.06), ("axiom", 0.02), ("proof", 0.04)],
                    "model": [("model", 0.54), ("meme", 0.14), ("insight", 0.14), ("axiom", 0.08), ("oracle", 0.04), ("proof", 0.06)],
                    "oracle": [("oracle", 0.64), ("model", 0.22), ("axiom", 0.10), ("proof", 0.04)],
                },
            ),
            "ECHOSPHERE": PlaneRules(
                name="ECHOSPHERE",
                survive=(1, 2, 5),
                birth=(2, 3, 4),
                life_gain=1.35,
                life_cost=1.1,
                decay=0.07,
                manufacturer_spawn_cost=1.0,
                manufacturer_spawn_energy=1.2,
                mutation_rate=0.16,
                gate_risk_penalty=0.2,
                shard_decay_penalty=0.08,
                echo_propagate_chance=0.12,
                norn_nurture=0.22,
                drone_dribble_cost=0.12,
                gate_cooldown=3,
                evolution_map={
                    "norn": [("echo", 0.36), ("drone", 0.24), ("shard", 0.25), ("goblin", 0.08), ("cache", 0.07)],
                    "egg": [("echo", 0.39), ("norn", 0.28), ("shard", 0.20), ("goblin", 0.08), ("cache", 0.05)],
                    "drone": [("drone", 0.47), ("echo", 0.30), ("goblin", 0.10), ("insight", 0.02), ("proof", 0.06), ("bug", 0.05)],
                    "life": [("life", 0.86), ("echo", 0.08), ("goblin", 0.03), ("cache", 0.03)],
                    "shard": [("shard", 0.66), ("echo", 0.22), ("goblin", 0.05), ("bug", 0.07)],
                    "goblin": [("goblin", 0.66), ("echo", 0.13), ("shard", 0.11), ("proof", 0.10)],
                    "meme": [("meme", 0.47), ("echo", 0.20), ("axiom", 0.17), ("cult", 0.06), ("insight", 0.02), ("proof", 0.08)],
                    "insight": [("insight", 0.54), ("meme", 0.20), ("echo", 0.10), ("axiom", 0.08), ("cult", 0.04), ("proof", 0.08)],
                    "axiom": [("axiom", 0.78), ("insight", 0.07), ("meme", 0.04), ("echo", 0.02), ("cult", 0.03), ("proof", 0.06)],
                    "cult": [("cult", 0.56), ("meme", 0.18), ("echo", 0.10), ("insight", 0.07), ("axiom", 0.03), ("proof", 0.06)],
                    "model": [("model", 0.50), ("echo", 0.16), ("insight", 0.14), ("meme", 0.07), ("oracle", 0.03), ("proof", 0.10)],
                    "oracle": [("oracle", 0.58), ("model", 0.24), ("meme", 0.10), ("axiom", 0.05), ("proof", 0.03)],
                },
            ),
            "MIRAGE": PlaneRules(
                name="MIRAGE",
                survive=(0, 2, 4, 6),
                birth=(2, 3, 5, 7),
                life_gain=1.45,
                life_cost=1.0,
                decay=0.1,
                manufacturer_spawn_cost=2.2,
                manufacturer_spawn_energy=0.9,
                mutation_rate=0.25,
                max_age=140,
                shard_decay_penalty=0.04,
                echo_propagate_chance=0.08,
                norn_nurture=0.1,
                drone_dribble_cost=0.08,
                gate_cooldown=2,
                evolution_map={
                    "norn": [("echo", 0.38), ("drone", 0.16), ("shard", 0.25), ("goblin", 0.04), ("insight", 0.04), ("bug", 0.13)],
                    "egg": [("shard", 0.25), ("echo", 0.28), ("norn", 0.25), ("goblin", 0.09), ("bug", 0.13)],
                    "shard": [("shard", 0.42), ("echo", 0.35), ("goblin", 0.06), ("anomaly", 0.04), ("bug", 0.13)],
                    "drone": [("drone", 0.49), ("shard", 0.18), ("norn", 0.09), ("goblin", 0.11), ("bug", 0.13)],
                    "manufacturer": [("shard", 0.10), ("manufacturer", 0.66), ("goblin", 0.02), ("bug", 0.22)],
                    "goblin": [("goblin", 0.58), ("drone", 0.12), ("shard", 0.10), ("insight", 0.08), ("anomaly", 0.08), ("bug", 0.04)],
                    "meme": [("meme", 0.34), ("anomaly", 0.20), ("axiom", 0.18), ("goblin", 0.12), ("cult", 0.06), ("proof", 0.10)],
                    "insight": [("anomaly", 0.18), ("insight", 0.35), ("axiom", 0.22), ("meme", 0.13), ("proof", 0.12)],
                    "axiom": [("axiom", 0.52), ("anomaly", 0.13), ("insight", 0.15), ("meme", 0.08), ("cult", 0.05), ("proof", 0.07)],
                    "cult": [("cult", 0.56), ("anomaly", 0.12), ("meme", 0.12), ("axiom", 0.10), ("life", 0.02), ("proof", 0.08)],
                    "model": [("model", 0.40), ("anomaly", 0.12), ("meme", 0.17), ("axiom", 0.13), ("oracle", 0.08), ("proof", 0.10)],
                    "oracle": [("oracle", 0.48), ("model", 0.26), ("anomaly", 0.12), ("axiom", 0.08), ("proof", 0.06)],
                },
            ),
        }

    @staticmethod
    def _build_gate_rules() -> List[GateRule]:
        return [
            GateRule(
                name="Needle-Through-Corridor",
                from_plane="GENESIS",
                to_plane="FORGE",
                to_kind="manufacturer",
                chance=0.14,
                checks=[
                    (-1, 0, "norn"),
                    (0, 0, "norn"),
                    (1, 0, "norn"),
                    (0, -1, "manufacturer"),
                    (0, 1, "manufacturer"),
                ],
            ),
            GateRule(
                name="Genesis-Impulse Portal",
                from_plane="GENESIS",
                to_plane="FORGE",
                to_kind="manufacturer",
                chance=0.28,
                checks=[
                    (0, 0, "manufacturer"),
                    (1, 0, "norn"),
                    (0, 1, "life"),
                    (-1, 0, "life"),
                ],
                min_age=0,
            ),
            GateRule(
                name="Forge-Oracle Ring",
                from_plane="FORGE",
                to_plane="ECHOSPHERE",
                to_kind="shard",
                chance=0.12,
                checks=[
                    (0, 0, "norn"),
                    (-1, -1, "life"),
                    (0, -1, "life"),
                    (1, -1, "life"),
                    (-1, 1, "life"),
                    (0, 1, "life"),
                    (1, 1, "life"),
                ],
            ),
            GateRule(
                name="Echo-Backbone Echo",
                from_plane="ECHOSPHERE",
                to_plane="MIRAGE",
                to_kind="echo",
                chance=0.11,
                checks=[
                    (0, 0, "echo"),
                    (-1, 0, "drone"),
                    (1, 0, "drone"),
                    (0, -1, "drone"),
                    (0, 1, "drone"),
                    (-1, -1, "any"),
                    (1, 1, "any"),
                ],
            ),
            GateRule(
                name="Cognitive Feedback Loop",
                from_plane="ECHOSPHERE",
                to_plane="MIRAGE",
                to_kind="insight",
                chance=0.14,
                checks=[
                    (0, 0, "echo"),
                    (-1, 0, "goblin"),
                    (1, 0, "insight"),
                    (0, -1, "norn"),
                    (0, 1, "drone"),
                ],
                min_age=1,
            ),
            GateRule(
                name="Recursive Model Gate",
                from_plane="ECHOSPHERE",
                to_plane="MIRAGE",
                to_kind="model",
                chance=0.12,
                checks=[
                    (0, 0, "model"),
                    (-1, -1, "insight"),
                    (1, 1, "axiom"),
                    (0, -1, "meme"),
                    (0, 1, "goblin"),
                    (-1, 0, "life"),
                ],
                min_age=2,
            ),
            GateRule(
                name="Resonance Choir",
                from_plane="FORGE",
                to_plane="ECHOSPHERE",
                to_kind="meme",
                chance=0.09,
                checks=[
                    (0, 0, "goblin"),
                    (-1, -1, "insight"),
                    (1, 1, "insight"),
                    (0, 1, "norn"),
                    (0, -1, "drone"),
                ],
            ),
            GateRule(
                name="Axionic Lattice",
                from_plane="FORGE",
                to_plane="MIRAGE",
                to_kind="axiom",
                chance=0.14,
                checks=[
                    (0, 0, "goblin"),
                    (0, -1, "insight"),
                    (0, 1, "meme"),
                    (-1, 0, "norn"),
                    (1, 0, "drone"),
                ],
            ),
            GateRule(
                name="Deep Echo Drift",
                from_plane="ECHOSPHERE",
                to_plane="MIRAGE",
                to_kind="drone",
                chance=0.18,
                checks=[
                    (0, 0, "echo"),
                    (0, 1, "any"),
                    (1, 0, "any"),
                    (-1, 0, "any"),
                ],
                consume=False,
            ),
            GateRule(
                name="Meme Crash Gate",
                from_plane="MIRAGE",
                to_plane="GENESIS",
                to_kind="meme",
                chance=0.14,
                checks=[
                    (0, 0, "anomaly"),
                    (-1, 0, "insight"),
                    (1, 0, "anomaly"),
                    (0, -1, "meme"),
                    (0, 1, "meme"),
                ],
                min_age=0,
            ),
            GateRule(
                name="Cult Drift Gate",
                from_plane="ECHOSPHERE",
                to_plane="MIRAGE",
                to_kind="cult",
                chance=0.13,
                checks=[
                    (0, 0, "goblin"),
                    (-1, 0, "meme"),
                    (1, 0, "meme"),
                    (0, -1, "insight"),
                    (0, 1, "insight"),
                ],
            ),
            GateRule(
                name="Axiomic Feedback Gate",
                from_plane="ECHOSPHERE",
                to_plane="MIRAGE",
                to_kind="axiom",
                chance=0.12,
                checks=[
                    (0, 0, "axiom"),
                    (-1, 0, "meme"),
                    (1, 0, "meme"),
                    (0, -1, "insight"),
                    (0, 1, "insight"),
                    (-1, 1, "cult"),
                ],
            ),
            GateRule(
                name="Mirage Return Weave",
                from_plane="MIRAGE",
                to_plane="GENESIS",
                to_kind="norn",
                chance=0.1,
                checks=[
                    (0, 0, "shard"),
                    (1, 0, "shard"),
                    (0, 1, "shard"),
                    (-1, 0, "shard"),
                    (0, -1, "shard"),
                ],
            ),
            GateRule(
                name="Cache Compression Gate",
                from_plane="FORGE",
                to_plane="ECHOSPHERE",
                to_kind="proof",
                chance=0.12,
                checks=[
                    (0, 0, "cache"),
                    (-1, -1, "manufacturer"),
                    (1, 1, "insight"),
                    (0, -1, "norn_maker"),
                    (0, 1, "meme"),
                ],
            ),
            GateRule(
                name="Proof Echo Gate",
                from_plane="ECHOSPHERE",
                to_plane="MIRAGE",
                to_kind="bug",
                chance=0.10,
                checks=[
                    (0, 0, "proof"),
                    (-1, 0, "anomaly"),
                    (1, 0, "meme"),
                    (0, -1, "axiom"),
                    (0, 1, "insight"),
                ],
            ),
            GateRule(
                name="Bug Spillback Gate",
                from_plane="MIRAGE",
                to_plane="GENESIS",
                to_kind="bug",
                chance=0.08,
                checks=[
                    (0, 0, "bug"),
                    (1, 0, "anomaly"),
                    (-1, 0, "anomaly"),
                    (0, 1, "shard"),
                    (0, -1, "drone"),
                ],
                min_age=0,
            ),
        ]

    def _seed_initial(self, seed_density: float) -> None:
        for plane_id in self.planes:
            grid = self.grids[plane_id]
            for y in range(self.height):
                for x in range(self.width):
                    if random.random() < seed_density:
                        kind = self._random_birth_kind(plane_id)
                        grid[y][x] = Cell(kind=kind, age=random.randint(0, 3), energy=1.2 + random.random())
                    else:
                        grid[y][x] = None

        # Add deliberate seed structures to invite gateway activations.
        gx, gy = self.width // 2, self.height // 2
        g = self.grids["GENESIS"]
        self._set(g, gx - 1, gy, Cell("norn", age=4, energy=2.4))
        self._set(g, gx, gy, Cell("norn", age=3, energy=2.2))
        self._set(g, gx + 1, gy, Cell("norn", age=3, energy=2.2))
        self._set(g, gx, gy - 1, Cell("manufacturer", age=6, energy=3.1, flavor="forge_starter"))
        self._set(g, gx, gy + 1, Cell("manufacturer", age=6, energy=3.1, flavor="forge_starter"))

        f = self.grids["FORGE"]
        self._set(f, gx + 4, gy + 2, Cell("norn", age=3, energy=2.0))
        self._set(f, gx + 3, gy + 3, Cell("life", age=1, energy=1.4))
        self._set(f, gx + 4, gy + 3, Cell("life", age=1, energy=1.4))
        self._set(f, gx + 5, gy + 3, Cell("life", age=1, energy=1.4))
        self._set(f, gx + 4, gy + 4, Cell("life", age=1, energy=1.4))
        self._set(f, gx + 2, gy + 2, Cell("goblin", age=2, energy=1.7, flavor="seed_goblin"))

        e = self.grids["ECHOSPHERE"]
        self._set(e, gx + 4, gy + 4, Cell("goblin", age=3, energy=1.8, flavor="void_spawn"))

        # Seed cognitive strata to guarantee occasional cultural/axiomatic arcs.
        self._set(g, gx + 2, gy + 2, Cell("cult", age=2, energy=1.9, flavor="seed_cult"))
        self._set(f, gx - 2, gy, Cell("axiom", age=1, energy=2.1, flavor="seed_axiom", meme=0.7))
        self._set(e, gx + 1, gy - 2, Cell("axiom", age=1, energy=2.0, flavor="seed_axiom", meme=0.6))
        self._set(e, gx - 2, gy + 1, Cell("cult", age=2, energy=1.7, flavor="echo_cult", meme=0.3))
        self._set(self.grids["MIRAGE"], gx + 1, gy + 2, Cell("cult", age=3, energy=2.0, flavor="moon_cult", meme=0.45))
        self._set(self.grids["MIRAGE"], gx - 1, gy - 3, Cell("axiom", age=2, energy=1.9, flavor="moon_axiom", meme=0.85))
        self._set(self.grids["GENESIS"], gx - 3, gy + 3, Cell("model", age=2, energy=1.6, flavor="seed_model", focus=0.6, coherence=0.55))
        self._set(e, gx + 3, gy + 2, Cell("model", age=2, energy=1.6, flavor="echo_model", focus=0.52, coherence=0.52))
        self._set(f, gx - 4, gy + 5, Cell("oracle", age=1, energy=2.2, flavor="seed_oracle", focus=0.95, coherence=0.9))
        self._set(g, gx + 4, gy + 3, Cell("cache", age=5, energy=2.6, flavor="deep_cache", meme=0.3))
        self._set(e, gx - 4, gy - 3, Cell("cache", age=4, energy=2.2, flavor="drifting_cache", meme=0.2))
        self._set(f, gx + 6, gy, Cell("proof", age=4, energy=1.8, flavor="proto_proof", coherence=0.6, meme=0.6))
        self._set(f, gx + 2, gy - 2, Cell("bug", age=3, energy=0.9, flavor="seed_bug", focus=0.24))
        self._set(e, gx - 6, gy + 2, Cell("bug", age=2, energy=0.9, flavor="echo_bug", focus=0.28))

    def _set(self, grid: List[List[Optional[Cell]]], x: int, y: int, value: Optional[Cell]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            grid[y][x] = value

    def _get(self, grid: List[List[Optional[Cell]]], x: int, y: int) -> Optional[Cell]:
        return grid[y % self.height][x % self.width]

    def _alive_neighbors(self, grid: List[List[Optional[Cell]]], x: int, y: int) -> int:
        total = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                neighbor = self._get(grid, x + dx, y + dy)
                if neighbor is not None and neighbor.kind in ALIVE:
                    total += 1
        return total

    def _choose_goblin_species(self, plane_id: str, neighbor_cells: List[Tuple[int, int, Optional[Cell]]], source_species: Optional[str] = None) -> str:
        # Carry ancestry where possible, then drift toward local cultural signals.
        if source_species is not None and random.random() < 0.80 * self.goblin_species_carry_scale:
            if random.random() < 0.90 * self.goblin_species_mutation_scale:
                return source_species

        has_insight = any(neighbor is not None and neighbor.kind == "insight" for _, _, neighbor in neighbor_cells)
        has_meme = any(neighbor is not None and neighbor.kind == "meme" for _, _, neighbor in neighbor_cells)
        has_model = any(
            neighbor is not None and neighbor.kind in {"model", "oracle"}
            for _, _, neighbor in neighbor_cells
        )
        nearby_goblins = [neighbor for _, _, neighbor in neighbor_cells if neighbor is not None and neighbor.kind == "goblin"]
        near_goblin_count = len(nearby_goblins)
        species_weights = {
            "wild": 1.0,
            "lover": 0.15 + 0.12 * near_goblin_count,
            "rager": 0.18,
            "sage": 0.16,
            "weaver": 0.14,
        }

        if has_insight:
            species_weights["sage"] += 0.70
            species_weights["weaver"] += 0.28
        if has_model:
            species_weights["sage"] += 0.55
            species_weights["weaver"] += 0.55
        if has_meme:
            species_weights["weaver"] += 0.70
            species_weights["lover"] += 0.18
        if plane_id == "MIRAGE":
            species_weights["rager"] += 0.45
            species_weights["wild"] += 0.05
        elif plane_id == "ECHOSPHERE":
            species_weights["sage"] += 0.40
            species_weights["weaver"] += 0.23
        elif plane_id == "FORGE":
            species_weights["rager"] += 0.22
        elif plane_id == "GENESIS":
            species_weights["wild"] += 0.22

        return self._choose_weighted(list(species_weights.items()))

    def _make_goblin(
        self,
        plane_id: str,
        neighbor_cells: List[Tuple[int, int, Optional[Cell]]],
        age: int = 0,
        energy: float = 1.0,
        flavor: str = "spawn",
        source_species: Optional[str] = None,
    ) -> Cell:
        return Cell(
            kind="goblin",
            age=age,
            energy=energy,
            flavor=flavor,
            species=self._choose_goblin_species(plane_id, neighbor_cells, source_species=source_species),
            mania=0.03 if source_species is not None else 0.0,
        )

    def _maybe_mutate_species(self, species: str) -> str:
        if random.random() > (0.04 * self.goblin_species_mutation_scale):
            return species
        alternatives = [option for option in {"wild", "lover", "rager", "sage", "weaver"} if option != species]
        if not alternatives:
            return species
        return random.choice(alternatives)

    def _neighbors(self, grid: List[List[Optional[Cell]]], x: int, y: int) -> List[Tuple[int, int, Optional[Cell]]]:
        entries: List[Tuple[int, int, Optional[Cell]]] = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = (x + dx) % self.width
                ny = (y + dy) % self.height
                entries.append((nx, ny, grid[ny][nx]))
        return entries

    def _count_neighbors_kind(self, grid: List[List[Optional[Cell]]], x: int, y: int, target: str) -> int:
        total = 0
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                neighbor = self._get(grid, x + dx, y + dy)
                if neighbor is not None and neighbor.kind == target:
                    total += 1
        return total

    @staticmethod
    def _shannon_entropy(counts: Dict[str, int]) -> float:
        total = sum(counts.values())
        if total <= 0:
            return 0.0
        entropy = 0.0
        for count in counts.values():
            if count <= 0:
                continue
            p = count / total
            entropy -= p * math.log2(p)
        return entropy

    def _compute_complexity(self, stats: Dict[str, Dict[str, int]]) -> Tuple[float, Dict[str, float]]:
        all_cells: Dict[str, int] = {}
        plane_totals: Dict[str, int] = {}
        for plane_id, counts in stats.items():
            plane_total = counts.get("total", 0)
            plane_totals[plane_id] = plane_total
            for kind, amount in counts.items():
                if kind == "total":
                    continue
                all_cells[kind] = all_cells.get(kind, 0) + amount

        total_cells = sum(plane_totals.values())
        if total_cells == 0:
            return 0.0, {"kind_entropy": 0.0, "plane_entropy": 0.0, "volatility": 0.0, "gate_flux": 0.0, "growth": 0.0}

        kind_entropy = self._shannon_entropy(all_cells)
        plane_entropy = self._shannon_entropy(plane_totals)

        previous_total = 0
        previous_by_kind: Dict[str, int] = {}
        if self._last_counts is not None:
            previous_total = sum(max(0, v.get("total", 0)) for v in self._last_counts.values())
            for counts in self._last_counts.values():
                for kind, amount in counts.items():
                    if kind == "total":
                        continue
                    previous_by_kind[kind] = previous_by_kind.get(kind, 0) + amount

        if previous_total > 0:
            deltas = []
            all_kinds = set(all_cells) | set(previous_by_kind)
            for kind in all_kinds:
                before = previous_by_kind.get(kind, 0)
                after = all_cells.get(kind, 0)
                deltas.append(abs(after - before) / previous_total)
            volatility = sum(deltas) / max(1, len(deltas))
            growth = abs(total_cells - previous_total) / max(1, previous_total)
        else:
            volatility = 0.0
            growth = total_cells / max(1, total_cells)

        gate_flux = self.last_events.get(
            "gate_placements",
            self.last_events.get("gate_transfers", 0),
        ) / max(1, total_cells)
        complexity = (
            0.45 * (kind_entropy / max(1.0, math.log2(max(3, len(all_cells) + 1))))
            + 0.30 * (plane_entropy / max(1.0, math.log2(max(3, len(self.planes) + 1))))
            + 0.15 * min(1.0, volatility * 2)
            + 0.10 * min(1.0, growth * 2)
            + 0.10 * min(1.0, gate_flux * 3)
        )

        metrics = {
            "kind_entropy": kind_entropy,
            "plane_entropy": plane_entropy,
            "volatility": volatility,
            "growth": growth,
            "gate_flux": gate_flux,
            "total_cells": float(total_cells),
        }
        return complexity, metrics

    def _random_birth_kind(self, plane_id: str) -> str:
        rolls = random.random()
        if plane_id == "FORGE":
            if rolls < 0.04:
                return "goblin"
            if rolls < 0.12:
                return "manufacturer"
            if rolls < 0.22:
                return "norn"
            if rolls < 0.26:
                return "norn_maker"
            if rolls < 0.32:
                return "insight"
            if rolls < 0.345:
                return "meme"
            if rolls < 0.365:
                return "cult"
            if rolls < 0.385:
                return "model"
            if rolls < 0.405:
                return "oracle"
            if rolls < 0.425:
                return "axiom"
            if rolls < 0.445:
                return "drone_mother"
            if rolls < 0.455:
                return "cache"
            if rolls < 0.47:
                return "proof"
            if rolls < 0.485:
                return "bug"
            return "life"
        if plane_id == "ECHOSPHERE":
            if rolls < 0.1:
                return "norn"
            if rolls < 0.18:
                return "drone"
            if rolls < 0.24:
                return "echo"
            if rolls < 0.28:
                return "goblin"
            if rolls < 0.30:
                return "norn_maker"
            if rolls < 0.34:
                return "insight"
            if rolls < 0.38:
                return "meme"
            if rolls < 0.42:
                return "drone_mother"
            if rolls < 0.45:
                return "insight"
            if rolls < 0.485:
                return "cult"
            if rolls < 0.515:
                return "axiom"
            if rolls < 0.54:
                return "model"
            if rolls < 0.56:
                return "anomaly"
            if rolls < 0.58:
                return "oracle"
            if rolls < 0.61:
                return "cache"
            if rolls < 0.63:
                return "proof"
            if rolls < 0.645:
                return "bug"
            if rolls < 0.67:
                return "drone_mother"
            return "life"
        if plane_id == "MIRAGE":
            if rolls < 0.06:
                return "shard"
            if rolls < 0.15:
                return "goblin"
            if rolls < 0.24:
                return "echo"
            if rolls < 0.34:
                return "anomaly"
            if rolls < 0.40:
                return "meme"
            if rolls < 0.46:
                return "norn"
            if rolls < 0.49:
                return "axiom"
            if rolls < 0.515:
                return "model"
            if rolls < 0.535:
                return "oracle"
            if rolls < 0.56:
                return "bug"
            if rolls < 0.58:
                return "cache"
            if rolls < 0.595:
                return "proof"
            if rolls < 0.62:
                return "cult"
            if rolls < 0.64:
                return "drone_mother"
            return "life"
        return "life"

    def _choose_weighted(self, options: List[Tuple[str, float]]) -> str:
        total = sum(weight for _, weight in options)
        if total <= 0:
            return options[0][0]
        threshold = random.random() * total
        running = 0.0
        for kind, weight in options:
            running += weight
            if threshold <= running:
                return kind
        return options[-1][0]

    @staticmethod
    def _local_diversity(neighbors: List[Tuple[int, int, Optional[Cell]]]) -> int:
        kinds = {neighbor.kind for _, _, neighbor in neighbors if neighbor is not None}
        return len(kinds)

    def _match_gate(self, plane_id: str, grid: List[List[Optional[Cell]]], x: int, y: int, rule: GateRule) -> bool:
        if plane_id != rule.from_plane:
            return False
        for dx, dy, required in rule.checks:
            cell = self._get(grid, x + dx, y + dy)
            if required == "any":
                continue
            if required == "empty":
                if cell is not None:
                    return False
                continue
            if cell is None or cell.kind != required:
                return False
        anchor = self._get(grid, x + rule.anchor[0], y + rule.anchor[1])
        if anchor is None:
            return False
        if anchor.age < rule.min_age:
            return False
        return True

    def _spawn_or_upgrade(self, target_plane: str, x: int, y: int, kind: str, source: Optional[Cell], next_grids: Dict[str, List[List[Optional[Cell]]]]) -> bool:
        grid = next_grids[target_plane]
        if grid[y][x] is None:
            energy = max(1.0, (source.energy if source else 1.0) * 0.75)
            grid[y][x] = Cell(kind=kind, age=0, energy=energy)
            return True
        return False

    def step(self) -> Dict[str, Dict[str, int]]:
        self.tick_count += 1
        event_counts = {
            "births": 0,
            "deaths": 0,
            "mutations": 0,
            "hatches": 0,
            "manufacture_attempts": 0,
            "manufacture_success": 0,
            "gate_checks": 0,
            "gate_shape_matches": 0,
            "gate_transfers": 0,
            "gate_placements": 0,
            "gate_target_occupied": 0,
            "gate_rescued_placements": 0,
            "gate_source_consumed": 0,
            "gate_effects_suppressed": 0,
            "gate_rejections": 0,
            "norn_nurture": 0,
            "goblin_feeds": 0,
            "goblin_conversions": 0,
            "goblin_breeds": 0,
            "goblin_cells_seen": 0,
            "goblin_nearby_checks": 0,
            "goblin_loves": 0,
            "goblin_rages": 0,
            "goblin_rage_kills": 0,
            "norn_makers": 0,
            "drone_mothers": 0,
            "insight_births": 0,
            "insight_reads": 0,
            "insight_cascades": 0,
            "insight_stabilizations": 0,
            "anomaly_ticks": 0,
            "anomaly_cascades": 0,
            "meme_births": 0,
            "meme_broadcasts": 0,
            "meme_attunements": 0,
            "meme_parasites": 0,
            "cache_births": 0,
            "cache_stimuli": 0,
            "cache_depletion": 0,
            "cache_loyalty": 0,
            "proof_births": 0,
            "proof_stabilizations": 0,
            "proof_radiance": 0,
            "proof_cascades": 0,
            "bug_births": 0,
            "bug_infests": 0,
            "bug_swarm": 0,
            "bug_explosions": 0,
            "rituals": 0,
            "goblin_frenzies": 0,
            "ritual_stimuli": 0,
            "love_spikes": 0,
            "obsession_flares": 0,
            "cognitive_spills": 0,
            "attention_surges": 0,
            "attention_overloads": 0,
            "attention_feedback_loops": 0,
            "imprint_growths": 0,
            "imprint_hives": 0,
            "prediction_updates": 0,
            "prediction_swerves": 0,
            "surprise_spikes": 0,
            "cognitive_resonances": 0,
            "trace_deposits": 0,
            "trace_decay": 0,
            "insight_overloads": 0,
            "focus_fractures": 0,
            "obsessive_feedback_loops": 0,
            "model_births": 0,
            "model_projections": 0,
            "model_fractures": 0,
            "oracle_awakenings": 0,
            "oracle_broadcasts": 0,
            "model_coherence_decay": 0,
            "goblin_pairs": 0,
            "goblin_romances": 0,
            "goblin_species_shifts": 0,
            "goblin_innovation_surges": 0,
            "goblin_cults": 0,
            "goblin_cult_births": 0,
            "goblin_cult_conversions": 0,
            "goblin_pairing_frenzies": 0,
            "goblin_pair_breaks": 0,
            "goblin_crazy_pairs": 0,
            "goblin_pair_lock_surges": 0,
            "goblin_pair_affiliations": 0,
            "cache_courtships": 0,
            "memory_recruitments": 0,
            "axiom_formations": 0,
            "axiom_sparks": 0,
            "axiom_decay": 0,
            "echo_blooms": 0,
            "shard_corruptions": 0,
            "shard_culls": 0,
            "energy_hits": 0,
        }
        next_grids: Dict[str, List[List[Optional[Cell]]]] = {
            plane_id: [[None for _ in range(self.width)] for _ in range(self.height)]
            for plane_id in self.planes
        }
        # Per-cell gate cooldown prevents immediate re-triggering the same anchor.
        for cd_plane in self._gate_cooldowns.values():
            for gy in range(self.height):
                for gx in range(self.width):
                    if cd_plane[gy][gx] > 0:
                        cd_plane[gy][gx] -= 1

        # Gather cross-plane warp events, then apply at end of tick.
        gates: List[Tuple[str, int, int, str, Optional[Cell], bool, int]] = []
        # Gather same-plane special spawns and updates.
        pending_spawns: List[Tuple[str, int, int, Cell]] = []
        pending_kills: List[Tuple[str, int, int]] = []
        pending_damage: Dict[Tuple[str, int, int], float] = {}
        pending_fervor: Dict[Tuple[str, int, int], float] = {}
        pending_bond: Dict[Tuple[str, int, int], float] = {}
        pending_pair_lock: Dict[Tuple[str, int, int], float] = {}
        pending_prediction: Dict[Tuple[str, int, int], float] = {}

        for plane_id, cfg in self.planes.items():
            grid = self.grids[plane_id]
            next_grid = next_grids[plane_id]
            cooldown_grid = self._gate_cooldowns[plane_id]
            for y in range(self.height):
                for x in range(self.width):
                    current = grid[y][x]
                    alive_neighbors = self._alive_neighbors(grid, x, y)
                    neighbor_cells = self._neighbors(grid, x, y)

                    if current is None:
                        if alive_neighbors in cfg.birth:
                            event_counts["births"] += 1
                            # Empty space can become new life from birth conditions.
                            kind_roll = random.random()
                            local_diversity = self._local_diversity(neighbor_cells)
                            norn_neighbors = self._count_neighbors_kind(grid, x, y, "norn")
                            neighbor_kinds = [neighbor.kind for _, _, neighbor in neighbor_cells if neighbor is not None]
                            has_insight = "insight" in neighbor_kinds
                            has_meme = "meme" in neighbor_kinds
                            has_cult = "cult" in neighbor_kinds
                            has_axiom = "axiom" in neighbor_kinds
                            has_model = "model" in neighbor_kinds or "oracle" in neighbor_kinds
                            has_cache = "cache" in neighbor_kinds
                            has_proof = "proof" in neighbor_kinds
                            has_bug = "bug" in neighbor_kinds
                            if kind_roll < 0.10 and norn_neighbors > 0:
                                new_kind = "norn"
                            elif kind_roll < 0.16 and norn_neighbors > 1:
                                new_kind = "manufacturer"
                            elif kind_roll < 0.18 and plane_id == "ECHOSPHERE":
                                new_kind = "echo"
                            elif kind_roll < 0.19 and plane_id in {"FORGE", "ECHOSPHERE", "MIRAGE"}:
                                new_kind = "goblin"
                                next_grid[y][x] = self._make_goblin(
                                    plane_id,
                                    neighbor_cells,
                                    age=0,
                                    energy=cfg.life_gain * 0.8 + random.random() * 0.4,
                                    flavor="seeded-goblin",
                                )
                            elif kind_roll < 0.205 and has_insight and has_meme and random.random() < 0.45 * self.goblin_cult_scale:
                                new_kind = "cult"
                                event_counts["goblin_cult_births"] += 1
                            elif kind_roll < 0.21 and has_insight and has_meme and local_diversity >= 4 and random.random() < 0.35 * self.goblin_fervor_scale:
                                new_kind = "ritual"
                                event_counts["rituals"] += 1
                            elif kind_roll < 0.225 and local_diversity >= 3 and random.random() < 0.65 * self.insight_spawn_scale:
                                new_kind = "insight"
                                event_counts["insight_births"] += 1
                            elif kind_roll < 0.24 and has_cult and random.random() < 0.35 * self.goblin_axiom_scale:
                                new_kind = "cult"
                                event_counts["goblin_cult_births"] += 1
                            elif kind_roll < 0.255 and (has_meme or has_axiom or has_insight) and random.random() < 0.85 * self.goblin_axiom_scale:
                                new_kind = "axiom"
                                event_counts["axiom_formations"] += 1
                            elif kind_roll < 0.28 and (has_meme or has_insight) and random.random() < 0.82 * self.meme_spawn_scale:
                                new_kind = "meme"
                                event_counts["meme_births"] += 1
                            elif kind_roll < 0.295 and has_model and random.random() < 0.40 * self.model_projection_scale:
                                new_kind = "model"
                                event_counts["model_births"] += 1
                            elif kind_roll < 0.31 and local_diversity >= 3 and random.random() < 0.55 * self.meme_spawn_scale:
                                new_kind = "meme"
                                event_counts["meme_births"] += 1
                            elif kind_roll < 0.325 and has_cache and random.random() < 0.6 * self.cache_pressure_scale:
                                new_kind = "cache"
                                event_counts["cache_births"] += 1
                            elif kind_roll < 0.335 and has_proof and random.random() < 0.35 * self.proof_stability_scale:
                                new_kind = "proof"
                                event_counts["proof_births"] += 1
                            elif kind_roll < 0.35 and has_bug and random.random() < 0.55 * self.bug_parasite_scale:
                                new_kind = "bug"
                                event_counts["bug_births"] += 1
                            else:
                                new_kind = "life"
                            if new_kind != "goblin":
                                next_grid[y][x] = Cell(
                                    kind=new_kind,
                                    age=0,
                                    energy=cfg.life_gain * 0.8 + random.random() * 0.4,
                                    flavor="seeded",
                                    meme=0.6 if new_kind == "meme" else 0.0,
                                )
                        continue

                    # Existing cell.
                    cell = current.copy()
                    neighbor_kinds = [neighbor.kind for _, _, neighbor in neighbor_cells if neighbor is not None]
                    has_insight = "insight" in neighbor_kinds
                    has_anomaly = "anomaly" in neighbor_kinds
                    has_meme = "meme" in neighbor_kinds
                    has_cult = "cult" in neighbor_kinds
                    has_axiom = "axiom" in neighbor_kinds
                    has_model = "model" in neighbor_kinds or "oracle" in neighbor_kinds
                    has_cache = "cache" in neighbor_kinds
                    has_proof = "proof" in neighbor_kinds
                    has_bug = "bug" in neighbor_kinds
                    survives = alive_neighbors in cfg.survive
                    if cell.kind == "model":
                        survives = survives or alive_neighbors >= 1 or cell.energy > 1.3
                    elif cell.kind == "oracle":
                        survives = survives or alive_neighbors >= 1 or cell.energy > 1.1

                    if survives:
                        # Shared local context for all living cells.
                        local_diversity = self._local_diversity(neighbor_cells)
                        cache_neighbors = [
                            (nx, ny, neighbor)
                            for nx, ny, neighbor in neighbor_cells
                            if neighbor is not None and neighbor.kind == "cache"
                        ]
                        proof_neighbors = [
                            (nx, ny, neighbor)
                            for nx, ny, neighbor in neighbor_cells
                            if neighbor is not None and neighbor.kind == "proof"
                        ]
                        bug_neighbors = [
                            (nx, ny, neighbor)
                            for nx, ny, neighbor in neighbor_cells
                            if neighbor is not None and neighbor.kind == "bug"
                        ]

                        if cell.kind in {"model", "oracle"} and cell.age < cfg.max_age:
                            # Basic metabolism.
                            cell.age += 1
                            cell.energy += cfg.life_gain + (alive_neighbors * 0.12) - cfg.life_cost
                            cell.energy -= cfg.decay + cfg.drone_dribble_cost

                        # Cognitive attention pressure from neighboring epistemic material.
                        attention_pressure = (
                            0.12 * int(has_insight)
                            + 0.10 * int(has_meme)
                            + 0.08 * int(has_axiom)
                            + 0.06 * int(has_proof)
                            + 0.05 * int(has_model)
                            + 0.05 * int(has_cache)
                            + 0.06 * int(has_bug)
                            + 0.02 * local_diversity
                        )
                        if has_anomaly:
                            attention_pressure += 0.16
                        cell.attention = min(1.0, cell.attention + attention_pressure * self.goblin_attention_scale)
                        if has_anomaly and random.random() < 0.35 * self.goblin_attention_scale:
                            cell.attention = min(1.0, cell.attention + 0.15)
                        if cell.kind == "goblin" and random.random() < 0.04 * self.goblin_attention_scale:
                            cell.attention = max(0.0, cell.attention - 0.04)

                        if cell.attention > 0.95 and random.random() < 0.08 * self.goblin_attention_scale:
                            event_counts["attention_feedback_loops"] += 1
                            if random.random() < 0.50:
                                cell.attention = max(0.0, cell.attention - 0.25)
                            else:
                                cell.coherence = max(0.0, cell.coherence - 0.10)

                        cell.attention = max(0.0, cell.attention - 0.022 * self.goblin_attention_decay_scale)

                        # Local ecology.
                        norn_influence = sum(
                            1
                            for _, _, neighbor in neighbor_cells
                            if neighbor is not None and neighbor.kind in {"norn", "norn_maker"}
                        )
                        if norn_influence > 0:
                            cell.energy += norn_influence * cfg.norn_nurture
                            event_counts["norn_nurture"] += 1
                        cell.focus = max(0.0, cell.focus - 0.02)
                        if cell.bond > 0.0:
                            if cell.love > 0.0:
                                cell.bond = min(1.0, cell.bond + 0.02 * self.goblin_romance_scale)
                            else:
                                cell.bond = max(0.0, cell.bond - 0.03 * self.goblin_romance_scale)
                                if cell.bond <= 0.0:
                                    event_counts["goblin_pair_breaks"] += 1
                                    cell.bond = 0.0
                                    cell.pair_lock = 0.0
                        if cell.pair_lock > 0.0:
                            cell.pair_lock = max(
                                0.0,
                                cell.pair_lock
                                - (0.012 * self.goblin_romance_scale * self.goblin_pair_lock_decay_scale),
                            )
                        cell.coherence = max(0.0, cell.coherence - 0.015 * self.cognition_decay_scale)

                        if cell.kind == "goblin":
                            if cache_neighbors and random.random() < 0.08 * self.cache_pressure_scale * (1.0 + cell.fervor):
                                cache_x, cache_y, _ = random.choice(cache_neighbors)
                                pending_kills.append((plane_id, cache_x, cache_y))
                                cell.energy += 0.45 * self.conversion_cache_scale
                                cell.focus = min(1.0, cell.focus + 0.08)
                                cell.mania = min(1.0, cell.mania + 0.04 * self.goblin_fervor_scale)
                                event_counts["cache_depletion"] += 1
                                if random.random() < 0.42:
                                    event_counts["cache_loyalty"] += 1
                                    cell.fervor = min(1.0, cell.fervor + 0.10)
                            if has_proof and random.random() < 0.04 * self.proof_stability_scale:
                                cell.focus = min(1.0, cell.focus + 0.11)
                                cell.coherence = min(1.0, cell.coherence + 0.06)
                                event_counts["proof_stabilizations"] += 1
                            if has_bug and random.random() < 0.06 * self.bug_parasite_scale:
                                event_counts["bug_infests"] += 1
                                cell.love = min(1.0, cell.love + 0.2)
                                cell.mania = min(1.0, cell.mania + 0.06)
                                if random.random() < 0.5:
                                    cell.focus = min(1.0, cell.focus + 0.12)
                            model_neighbors = [
                                neighbor
                                for _, _, neighbor in neighbor_cells
                                if neighbor is not None and neighbor.kind in {"model", "oracle"}
                            ]
                            model_pressure = 0.30 * len(model_neighbors)
                            cell.focus = min(
                                1.0,
                                cell.focus + model_pressure * self.model_projection_scale * self.goblin_focus_scale,
                            )
                            if has_meme:
                                cell.focus = min(1.0, cell.focus + 0.06 * self.model_projection_scale)
                            if has_anomaly:
                                cell.coherence = max(0.0, cell.coherence - 0.10 * self.cognition_decay_scale)
                            else:
                                cell.coherence = min(1.0, cell.coherence + 0.03)
                            if (
                                cell.love > 0.10
                                and random.random() < 0.05 * self.goblin_obsession_scale
                            ):
                                event_counts["love_spikes"] += 1
                                cell.focus = min(1.0, cell.focus + 0.16)
                                if random.random() < 0.55:
                                    event_counts["cognitive_spills"] += 1
                                    if random.random() < 0.5 and has_insight:
                                        spawn_kind = "insight"
                                        event_counts["insight_births"] += 1
                                        spawn_favor = 0.8
                                    else:
                                        spawn_kind = "meme"
                                        event_counts["meme_births"] += 1
                                        spawn_favor = 0.9
                                    random.shuffle(neighbor_cells)
                                    for nx, ny, spot in neighbor_cells:
                                        if spot is None and next_grid[ny][nx] is None:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind=spawn_kind,
                                                        age=0,
                                                        energy=0.74,
                                                        flavor="obsessive_spill",
                                                        meme=spawn_favor,
                                                    ),
                                                )
                                            )
                                            break
                                else:
                                    event_counts["obsession_flares"] += 1
                                    random.shuffle(neighbor_cells)
                                    for nx, ny, spot in neighbor_cells:
                                        if spot is None and next_grid[ny][nx] is None:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    self._make_goblin(
                                                        plane_id=plane_id,
                                                        neighbor_cells=neighbor_cells,
                                                        age=0,
                                                        energy=0.65 + random.random() * 0.25,
                                                        flavor="obsessive_offspring",
                                                        source_species=cell.species,
                                                    ),
                                                )
                                            )
                                            event_counts["goblin_breeds"] += 1
                                            break

                            if cell.species not in {"wild", "lover", "rager", "sage", "weaver"}:
                                cell.species = "wild"
                            # Some species drift over time; tiny mutation keeps lineages interesting.
                            if random.random() < 0.004 * self.goblin_species_mutation_scale:
                                old_species = cell.species
                                mutated = self._maybe_mutate_species(cell.species)
                                if mutated != old_species:
                                    cell.species = mutated
                                    event_counts["goblin_species_shifts"] += 1

                            species = cell.species
                            event_counts["goblin_cells_seen"] += 1
                            species_romance_scale = 1.0
                            species_feed_scale = 1.0
                            species_mania_scale = 1.0
                            attention_drive = 1.0 + (0.35 * cell.attention)
                            if species == "lover":
                                species_romance_scale = 2.2
                                species_mania_scale = 1.35
                            elif species == "rager":
                                species_feed_scale = 1.55
                                species_mania_scale = 1.45
                            elif species == "sage":
                                species_mania_scale = 1.05
                                species_feed_scale = 0.85
                            elif species == "weaver":
                                species_romance_scale = 1.35
                                species_feed_scale = 1.20

                            if cell.attention > 0.60 and random.random() < 0.03 * self.goblin_attention_scale * species_mania_scale:
                                event_counts["attention_surges"] += 1
                                cell.mania = min(1.0, cell.mania + 0.10)
                                cell.love = min(1.0, cell.love + 0.10)
                                if has_insight and random.random() < 0.5:
                                    random.shuffle(neighbor_cells)
                                    for nx, ny, spot in neighbor_cells:
                                        if spot is None and next_grid[ny][nx] is None:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind="insight",
                                                        age=0,
                                                        energy=0.64,
                                                        flavor="attention_bleed",
                                                        meme=0.6,
                                                    ),
                                                )
                                            )
                                            event_counts["insight_births"] += 1
                                            break

                            # Goblin social state: nearby goblins may trigger infatuation -> mania.
                            neighbors = [
                                (nx, ny, neighbor)
                                for nx, ny, neighbor in neighbor_cells
                                if neighbor is not None and neighbor.kind not in {"shard", "goblin"}
                            ]
                            nearby_goblins = [
                                (nx, ny, neighbor)
                                for nx, ny, neighbor in neighbor_cells
                                if neighbor is not None and neighbor.kind == "goblin"
                            ]
                            if nearby_goblins:
                                event_counts["goblin_nearby_checks"] += 1
                            if (
                                cell.love <= 0.0
                                and nearby_goblins
                                and random.random() < 0.06 * self.goblin_love_probability_scale * species_romance_scale * self.goblin_species_romance_scale
                            ):
                                cell.love = (2.5 + random.random() * 3.0) * self.goblin_love_probability_scale
                                cell.mania = max(cell.mania, 0.6)
                                cell.fervor = min(1.0, cell.fervor + 0.38 * self.goblin_fervor_scale)
                                event_counts["goblin_loves"] += 1
                                if species == "lover":
                                    event_counts["goblin_romances"] += 1
                                if cell.love > 0.0 and random.random() < 0.05 * self.goblin_obsession_scale:
                                    event_counts["love_spikes"] += 1
                                    if random.random() < 0.5 and has_insight:
                                        spawn_kind = "insight"
                                        spawn_value = 0.86
                                        event_counts["insight_births"] += 1
                                    else:
                                        spawn_kind = "meme"
                                        spawn_value = 0.9
                                        event_counts["meme_births"] += 1
                                    random.shuffle(neighbor_cells)
                                    for nx, ny, spot in neighbor_cells:
                                        if spot is None and next_grid[ny][nx] is None:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind=spawn_kind,
                                                        age=0,
                                                        energy=0.76,
                                                        flavor="romance_feedback",
                                                        meme=spawn_value,
                                                    ),
                                                )
                                            )
                                            break

                            if cell.love > 0.0:
                                cell.love = max(0.0, cell.love - 1.0)
                                cell.mania = min(1.0, cell.mania + (0.12 * self.goblin_mania_gain_scale * species_mania_scale))
                                cell.fervor = min(1.0, cell.fervor + 0.03 * self.goblin_fervor_scale)
                                if has_insight and random.random() < 0.08 * self.goblin_obsession_scale:
                                    # Insight-coupled desire creates short, dangerous cognitive spikes.
                                    cell.mania = min(1.0, cell.mania + 0.08 * self.goblin_obsession_scale)
                                    cell.focus = min(1.0, cell.focus + 0.06 * self.goblin_focus_scale)
                                event_counts["goblin_rages"] += 1
                            else:
                                cell.mania = max(0.0, cell.mania - (0.03 * self.goblin_mania_decay_scale))
                                cell.fervor = max(0.0, cell.fervor - 0.06 * self.goblin_fervor_scale)

                            if has_meme:
                                cell.meme = min(1.0, cell.meme + (0.16 * self.meme_conversion_scale))
                                if cell.love > 0.0:
                                    cell.mania = min(1.0, cell.mania + (0.08 * self.meme_pressure_scale))
                                if random.random() < 0.12 * self.meme_pressure_scale:
                                    cell.energy += 0.25
                                    event_counts["meme_parasites"] += 1
                            obsession_pressure = (cell.focus * 0.5) + (cell.fervor * 0.2) + (cell.mania * 0.3)
                            insight_density = 0.20 if has_insight else 0.0
                            insight_density += 0.10 if has_model else 0.0
                            insight_density += 0.05 if has_meme else 0.0
                            insight_density += 0.05 if has_axiom else 0.0
                            insight_density += 0.05 if has_cult else 0.0
                            insight_pressure = obsession_pressure * (1.0 + insight_density) * self.goblin_overclock_scale
                            # Love-triggered overclock: low-threshold for experimentation, with
                            # focus and insight density providing the stronger route.
                            if (
                                cell.love > 0.05
                                and random.random() < 0.08 * self.goblin_overclock_scale
                                and (cell.focus > 0.10 or random.random() < 0.22)
                            ):
                                event_counts["insight_overloads"] += 1
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        if (
                                            has_model
                                            and random.random() < 0.18 * self.model_projection_scale
                                            and random.random() < 0.60 * (0.7 + 0.3 * min(1.0, cell.love))
                                        ):
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind="model",
                                                        age=0,
                                                        energy=0.85,
                                                        flavor="overclock_projection",
                                                        focus=min(1.0, cell.focus + 0.25),
                                                        coherence=0.55,
                                                    ),
                                                )
                                            )
                                            event_counts["model_births"] += 1
                                        elif random.random() < 0.60 * (0.7 + 0.3 * min(1.0, cell.love)):
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind="insight",
                                                        age=0,
                                                        energy=0.82,
                                                        flavor="overclock_bloom",
                                                        meme=0.8,
                                                    ),
                                                )
                                            )
                                            event_counts["insight_births"] += 1
                                        else:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind="meme",
                                                        age=0,
                                                        energy=0.89,
                                                        flavor="overclock_bloom",
                                                        meme=0.88,
                                                    ),
                                                )
                                            )
                                            event_counts["meme_births"] += 1
                                        break
                            if (
                                cell.love > 0.0
                                and random.random() < 0.06 * self.goblin_obsession_scale * self.goblin_focus_scale
                            ):
                                event_counts["love_spikes"] += 1
                                if has_model and random.random() < 0.35 and cell.focus > 0.3:
                                    event_counts["model_births"] += 1
                                    event_counts["cognitive_spills"] += 1
                                    spawn_kind = "model"
                                    spawn_meme = 0.0
                                elif random.random() < 0.5:
                                    event_counts["cognitive_spills"] += 1
                                    spawn_kind = "insight"
                                    spawn_meme = 0.75
                                else:
                                    event_counts["obsession_flares"] += 1
                                    spawn_kind = "meme"
                                    spawn_meme = 0.92
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (
                                                plane_id,
                                                nx,
                                                ny,
                                                Cell(
                                                    kind=spawn_kind,
                                                    age=0,
                                                    energy=0.72,
                                                    flavor="obsessive_emergence",
                                                    meme=spawn_meme,
                                                ),
                                            )
                                        )
                                        break
                            if (
                                cell.focus > 0.95
                                and cell.love > 0.25
                                and cell.mania > 0.6
                                and random.random() < 0.06 * self.goblin_obsession_scale
                            ):
                                event_counts["obsession_flares"] += 1
                                cell.mania = min(1.0, cell.mania + 0.20)
                                cell.love = max(0.0, cell.love - 0.06)
                            if (
                                cell.focus > 0.9
                                and random.random() < 0.05 * self.goblin_overflow_scale * self.goblin_obsession_scale
                            ):
                                event_counts["focus_fractures"] += 1
                                cell.focus = max(0.0, cell.focus * 0.55)
                                cell.coherence = max(0.0, cell.coherence - 0.30)
                                if random.random() < 0.4:
                                    pending_damage[(plane_id, x, y)] = pending_damage.get((plane_id, x, y), 0.0) - 0.35
                                    event_counts["insight_reads"] += 1
                                if random.random() < 0.38 and has_model:
                                    random.shuffle(neighbor_cells)
                                    for nx, ny, spot in neighbor_cells:
                                        if spot is None and next_grid[ny][nx] is None:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind="model",
                                                        age=0,
                                                        energy=0.72,
                                                        flavor="fracture_projection",
                                                        focus=min(1.0, cell.focus + 0.4),
                                                        coherence=0.44,
                                                    ),
                                                )
                                            )
                                            event_counts["model_births"] += 1
                                            break
                                    else:
                                        random.shuffle(neighbor_cells)
                                        for nx, ny, spot in neighbor_cells:
                                            if spot is None and next_grid[ny][nx] is None:
                                                pending_spawns.append(
                                                    (
                                                        plane_id,
                                                        nx,
                                                        ny,
                                                        Cell(
                                                            kind="anomaly",
                                                            age=0,
                                                            energy=0.62,
                                                            flavor="fracture_anomaly",
                                                            meme=0.28,
                                                        ),
                                                    )
                                                )
                                                break
                            if (
                                cell.love > 0.01
                                and random.random() < 0.12 * self.goblin_overflow_scale * self.goblin_obsession_scale
                            ):
                                event_counts["obsessive_feedback_loops"] += 1
                                if random.random() < 0.3 and has_meme:
                                    event_counts["cognitive_spills"] += 1
                                    for nx, ny, spot in neighbor_cells:
                                        if spot is None and next_grid[ny][nx] is None:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind="insight",
                                                        age=0,
                                                        energy=0.68,
                                                        flavor="feedback_flash",
                                                        meme=0.88,
                                                    ),
                                                )
                                            )
                                            break
                                if random.random() < 0.7 and nearby_goblins:
                                    partner_x, partner_y, _ = random.choice(nearby_goblins)
                                    partner_key = (plane_id, partner_x, partner_y)
                                    pending_fervor[partner_key] = min(
                                        1.0,
                                        pending_fervor.get(partner_key, 0.0) + (0.2 * self.goblin_fervor_scale),
                                    )
                                if has_insight and random.random() < 0.42:
                                    cell.mania = min(1.0, cell.mania + 0.20)
                                    cell.focus = min(1.0, cell.focus + 0.20)
                                    event_counts["insight_reads"] += 1
                                elif has_meme and random.random() < 0.30:
                                    for nx, ny, spot in neighbor_cells:
                                        if spot is None and next_grid[ny][nx] is None:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind="meme",
                                                        age=0,
                                                        energy=0.64,
                                                        flavor="feedback_residue",
                                                        meme=0.90,
                                                    ),
                                                )
                                            )
                                            event_counts["cognitive_spills"] += 1
                                            break
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (
                                                plane_id,
                                                nx,
                                                ny,
                                                Cell(
                                                    kind="model",
                                                    age=0,
                                                    energy=0.92,
                                                    flavor="obsessive_projection",
                                                    focus=0.9,
                                                    coherence=0.7,
                                                ),
                                            )
                                        )
                                        break
                                if random.random() < 0.25 * self.model_projection_scale:
                                    random.shuffle(neighbor_cells)
                                    for nx, ny, spot in neighbor_cells:
                                        if spot is None and next_grid[ny][nx] is None:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind="model",
                                                        age=0,
                                                        energy=0.88,
                                                        flavor="obsessive_feedback_projection",
                                                        focus=min(1.0, cell.focus + 0.20),
                                                        coherence=max(0.2, cell.coherence + 0.15),
                                                    ),
                                                )
                                            )
                                            event_counts["model_births"] += 1
                                            break

                            # Love-fueled goblins act greedier and more erratic.
                            attacks = 1 + int(cell.mania > 0.4) + int(cell.mania > 0.8)
                            attacks = min(
                                6,
                                max(1, int(attacks * self.goblin_mania_attack_scale * species_feed_scale * (1.0 + 0.5 * cell.attention))),
                            )
                            if has_insight:
                                attacks = min(6, int(attacks * self.insight_learn_scale))
                            for attempt in range(attacks):
                                if not neighbors:
                                    break
                                if attempt > 0 and random.random() > 0.65:
                                    break
                                nx, ny, prey = random.choice(neighbors)
                                pressure = 0.30 if prey.kind in {"manufacturer", "drone_mother", "norn", "norn_maker", "drone"} else 0.18
                                pressure *= self.goblin_pressure_scale
                                if cell.mania > 0.8:
                                    pressure *= 1.15
                                key = (plane_id, nx, ny)
                                pending_damage[key] = pending_damage.get(key, 0.0) - pressure
                                cell.energy += pressure * 0.6
                                event_counts["goblin_feeds"] += 1
                                event_counts["energy_hits"] += 1

                                if prey.kind in {"life", "egg", "drone", "norn", "drone_mother"} and random.random() < (0.10 + 0.5 * cell.mania) * self.goblin_conversion_scale and prey.energy <= (1.35 + 0.5 * cell.mania):
                                    pending_kills.append(key)
                                    pending_spawns.append(
                                        (
                                            plane_id,
                                            nx,
                                            ny,
                                            self._make_goblin(
                                                plane_id=plane_id,
                                                neighbor_cells=neighbor_cells,
                                                age=0,
                                                energy=0.5 + random.random() * 0.35,
                                                flavor="conversion",
                                                source_species=cell.species,
                                            ),
                                        )
                                    )
                                    event_counts["goblin_conversions"] += 1
                                    event_counts["goblin_rage_kills"] += 1
                                    cell.energy -= 0.20
                                    if cell.mania > 0.5:
                                        cell.mania = min(1.0, cell.mania + 0.06)

                            if has_insight and random.random() < 0.05 * self.insight_learn_scale:
                                cell.mania = min(1.0, cell.mania + 0.2)
                                cell.energy += 0.3
                                event_counts["insight_reads"] += 1
                                if species == "sage" and random.random() < 0.45:
                                    event_counts["goblin_innovation_surges"] += 1

                            if has_insight and cell.love > 0.0 and cell.mania > 0.88 and random.random() < 0.08 * self.insight_learn_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        spawned_cell = Cell(
                                            kind="axiom" if has_axiom else "insight",
                                            age=0,
                                            energy=0.82,
                                            flavor="lovesick_breakthrough",
                                            meme=0.75,
                                        )
                                        pending_spawns.append((plane_id, nx, ny, spawned_cell))
                                        if has_axiom:
                                            event_counts["axiom_formations"] += 1
                                        else:
                                            event_counts["insight_births"] += 1
                                        break

                            if nearby_goblins and (
                                has_meme or has_insight or has_cult
                                or len(nearby_goblins) >= 2
                                or cell.love > 0.0
                            ):
                                if cell.attention > 0.78 and random.random() < 0.10 * self.goblin_attention_scale:
                                    event_counts["attention_overloads"] += 1
                                    cell.attention = max(0.0, cell.attention - 0.30)
                                pair_pressure = (
                                    0.05
                                    * self.meme_pressure_scale
                                    * species_romance_scale
                                    * self.goblin_romance_scale
                                    * self.goblin_pair_pressure_scale
                                    * (1.0 + 0.65 * int(has_meme) + 0.65 * int(has_insight) + 0.45 * int(has_cult))
                                )
                                pair_pressure *= attention_drive
                                if has_cache or has_model:
                                    pair_pressure *= 1.0 + (0.18 * cell.imprint) + (0.12 * cell.prediction)
                                if cell.surprise > 0.45:
                                    pair_pressure *= 1.0 + (0.20 * self.goblin_surprise_scale)
                                if species == "lover":
                                    pair_pressure *= 1.85
                                if cell.bond >= self.goblin_pairing_lock_threshold:
                                    pair_pressure *= 1.25
                                if cell.pair_lock >= self.goblin_pairing_lock_threshold:
                                    pair_pressure *= 1.45
                                if cell.love > 0.0:
                                    pair_pressure *= 1.45
                                if random.random() < pair_pressure:
                                    partner_x, partner_y, partner = random.choice(nearby_goblins)
                                    if isinstance(partner, Cell):
                                        p_mania = partner.mania if isinstance(partner, Cell) else 0.0
                                        partner_key = (plane_id, partner_x, partner_y)
                                        partner_lock = getattr(partner, "pair_lock", 0.0)
                                        partner_species = getattr(partner, "species", "wild")
                                        random.shuffle(neighbor_cells)
                                        event_counts["goblin_pairs"] += 1
                                        event_counts["goblin_romances"] += 1
                                        event_counts["goblin_pairing_frenzies"] += 1
                                        event_counts["goblin_pair_affiliations"] += 1
                                        cell.fervor = min(1.0, cell.fervor + 0.26 * self.goblin_fervor_scale)
                                        partner_boost = 0.20 * self.goblin_fervor_scale
                                        pending_fervor[partner_key] = min(1.0, pending_fervor.get(partner_key, 0.0) + partner_boost)
                                        if p_mania > 0.35:
                                            cell.mania = min(1.0, cell.mania + 0.08)
                                            pending_fervor[partner_key] = min(1.0, pending_fervor.get(partner_key, 0.0) + 0.12 * self.goblin_fervor_scale)
                                        if has_cache and cell.imprint > 0.30:
                                            event_counts["cache_courtships"] += 1
                                            cell.energy = min(3.0, cell.energy + 0.04)
                                            pending_pair_lock[partner_key] = min(
                                                1.0,
                                                pending_pair_lock.get(partner_key, 0.0) + 0.08 * self.cache_pressure_scale,
                                            )
                                        if has_model and cell.prediction > 0.32:
                                            event_counts["prediction_swerves"] += 1
                                            cell.focus = min(1.0, cell.focus + 0.08 * self.model_projection_scale)
                                            cell.mania = max(0.0, cell.mania - 0.04)
                                        if (
                                            has_insight
                                            and has_meme
                                            and partner is not None
                                            and (cell.pair_lock + 0.3) >= self.goblin_pairing_lock_threshold
                                            and (partner_lock + 0.3) >= self.goblin_pairing_lock_threshold
                                        ):
                                            event_counts["goblin_pair_lock_surges"] += 1
                                        pair_intensity = 0.24 * (0.8 + 0.2 * species_romance_scale) * self.goblin_pair_bond_gain_scale
                                        bond_target = min(1.0, cell.bond + pair_intensity)
                                        cell.bond = bond_target
                                        pending_bond[(plane_id, x, y)] = min(1.0, pending_bond.get((plane_id, x, y), 0.0) + pair_intensity)
                                        pending_bond[partner_key] = min(1.0, pending_bond.get(partner_key, 0.0) + pair_intensity)
                                        lock_intensity = 0.24 * (0.65 + 0.25 * species_romance_scale) * self.goblin_pair_lock_scale
                                        cell.pair_lock = min(1.0, cell.pair_lock + lock_intensity * 0.5)
                                        if hasattr(partner, "pair_lock"):
                                            partner.pair_lock = min(1.0, partner.pair_lock + lock_intensity * 0.5 * 1.05)
                                        pending_pair_lock[(plane_id, x, y)] = min(1.0, pending_pair_lock.get((plane_id, x, y), 0.0) + lock_intensity)
                                        pending_pair_lock[partner_key] = min(1.0, pending_pair_lock.get(partner_key, 0.0) + lock_intensity * 1.05)
                                        pair_spawn_as_meme = (species in {"weaver", "rager"}) or (partner_species in {"weaver"}) or has_meme
                                        for nx, ny, spot in neighbor_cells:
                                            if spot is None and next_grid[ny][nx] is None:
                                                spawn_meme = pair_spawn_as_meme and random.random() < 0.7
                                                if has_model and has_insight and cell.love > 0.2 and random.random() < 0.22:
                                                    spawned_cell = Cell(
                                                        kind="model",
                                                        age=0,
                                                        energy=0.86,
                                                        flavor="pair_projection",
                                                        focus=min(1.0, cell.focus + 0.25),
                                                        coherence=max(0.35, partner.coherence if isinstance(partner, Cell) else 0.35),
                                                    )
                                                    event_counts["model_births"] += 1
                                                elif species == "sage" and random.random() < 0.4:
                                                    spawned_cell = Cell(kind="insight", age=0, energy=0.7, flavor="pair_insight", meme=0.35)
                                                    event_counts["insight_births"] += 1
                                                    event_counts["goblin_innovation_surges"] += 1
                                                elif spawn_meme:
                                                    spawned_cell = Cell(
                                                        kind="meme",
                                                        age=0,
                                                        energy=0.85,
                                                        flavor="pair_ritual",
                                                        meme=0.9,
                                                    )
                                                    event_counts["meme_births"] += 1
                                                elif has_meme and has_insight:
                                                    spawned_cell = Cell(
                                                        kind="axiom",
                                                        age=0,
                                                        energy=0.8,
                                                        flavor="pair_axiom",
                                                        meme=0.55,
                                                    )
                                                    event_counts["axiom_formations"] += 1
                                                elif has_cult and random.random() < 0.45:
                                                    spawned_cell = Cell(
                                                        kind="cult",
                                                        age=0,
                                                        energy=0.72,
                                                        flavor="pair_cult",
                                                    )
                                                    event_counts["goblin_cult_births"] += 1
                                                else:
                                                    spawned_cell = Cell(
                                                        kind="meme",
                                                        age=0,
                                                        energy=0.85,
                                                        flavor="pair_ritual",
                                                        meme=0.7,
                                                    )
                                                    event_counts["meme_births"] += 1
                                                pending_spawns.append(
                                                    (
                                                        plane_id,
                                                        nx,
                                                        ny,
                                                        spawned_cell,
                                                    )
                                                )
                                                break

                                crazy_threshold = self.goblin_pairing_crazy_threshold
                                pair_crazy_roll = (
                                    0.10
                                    * self.goblin_obsession_scale
                                    * self.goblin_pair_crazy_scale
                                    * (1.0 + 0.25 * (cell.bond + cell.pair_lock))
                                )
                                if species == "weaver":
                                    pair_crazy_roll *= 1.2
                                if has_model and random.random() < 0.15:
                                    pair_crazy_roll *= 1.3
                                if cell.bond >= crazy_threshold and cell.pair_lock >= crazy_threshold and cell.love > 0.0 and random.random() < pair_crazy_roll:
                                    event_counts["goblin_crazy_pairs"] += 1
                                    cell.mania = min(1.0, cell.mania + 0.22 * self.goblin_overclock_scale)
                                    cell.fervor = min(1.0, cell.fervor + 0.18 * self.goblin_fervor_scale)
                                    if has_insight and random.random() < 0.6:
                                        random.shuffle(neighbor_cells)
                                        for nx, ny, spot in neighbor_cells:
                                            if spot is None and next_grid[ny][nx] is None:
                                                pending_spawns.append(
                                                    (
                                                        plane_id,
                                                        nx,
                                                        ny,
                                                        Cell(
                                                            kind="insight",
                                                            age=0,
                                                            energy=0.72,
                                                            flavor="crazed_pairing",
                                                            meme=0.94,
                                                        ),
                                                    )
                                                )
                                                event_counts["insight_births"] += 1
                                                break
                                    elif random.random() < 0.3:
                                        random.shuffle(neighbor_cells)
                                        for nx, ny, spot in neighbor_cells:
                                            if spot is None and next_grid[ny][nx] is None:
                                                pending_spawns.append(
                                                    (
                                                        plane_id,
                                                        nx,
                                                        ny,
                                                        Cell(
                                                            kind="meme",
                                                            age=0,
                                                            energy=0.8,
                                                            flavor="crazed_pairing",
                                                            meme=0.98,
                                                        ),
                                                    )
                                                )
                                                event_counts["meme_births"] += 1
                                                break

                            if cell.energy > 2.2 and cell.age % 3 == 0 and random.random() < 0.18 * self.goblin_feed_probability_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (
                                                plane_id,
                                                nx,
                                                ny,
                                                self._make_goblin(
                                                    plane_id=plane_id,
                                                    neighbor_cells=neighbor_cells,
                                                    age=0,
                                                    energy=0.9 + random.random() * 0.4,
                                                    flavor="spawn",
                                                    source_species=cell.species,
                                                ),
                                            )
                                        )
                                        cell.energy -= 0.95
                                        event_counts["goblin_breeds"] += 1
                                        break

                            if cell.fervor > 0.8 and cell.love > 0.2 and random.random() < 0.09 * self.goblin_fervor_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append((plane_id, nx, ny, Cell(kind="ritual", age=0, energy=1.0, flavor="mania_ritual")))
                                        event_counts["rituals"] += 1
                                        event_counts["goblin_frenzies"] += 1
                                        break

                        if cell.kind == "cache":
                            # Cache is durable memory: it accumulates insight and can radiate redundancy pressure.
                            event_counts["cache_stimuli"] += 1
                            cell.energy += 0.04 + (0.025 * local_diversity)
                            cell.meme = min(1.0, cell.meme + (0.03 * self.meme_spawn_scale))
                            if has_insight and random.random() < 0.06 * self.insight_learn_scale:
                                cell.meme = min(1.0, cell.meme + 0.20)
                                if random.random() < 0.35:
                                    event_counts["proof_cascades"] += 1
                                    nx = (x + random.choice([-1, 1])) % self.width
                                    ny = (y + random.choice([-1, 1])) % self.height
                                    pending_spawns.append(
                                        (
                                            plane_id,
                                            nx,
                                            ny,
                                            Cell(kind="proof", age=0, energy=0.9, flavor="cache_to_proof", coherence=0.35, meme=cell.meme),
                                        )
                                    )
                            if has_proof and random.random() < 0.04 * self.proof_stability_scale:
                                event_counts["proof_stabilizations"] += 1
                                cell.energy = min(2.6, cell.energy + 0.12)
                            if has_bug and random.random() < 0.08 * self.bug_parasite_scale:
                                event_counts["bug_infests"] += 1
                                if random.random() < 0.5:
                                    event_counts["cache_depletion"] += 1
                                    for nx, ny, _ in cache_neighbors:
                                        pending_kills.append((plane_id, nx, ny))
                                        break
                                else:
                                    cell.kind = "bug"
                                    event_counts["bug_swarm"] += 1
                            if local_diversity >= 5 and random.random() < 0.03 * self.cache_pressure_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append((plane_id, nx, ny, Cell(kind="cache", age=0, energy=1.05, flavor="cache_diverge")))
                                        event_counts["cache_births"] += 1
                                        break
                            if has_meme and random.random() < 0.10 * self.meme_conversion_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append((plane_id, nx, ny, Cell(kind="proof", age=0, energy=0.8, flavor="meme_reflex")))
                                        break
                            if cell.energy < 0.25:
                                cell = None
                            if cell is None:
                                continue

                        if cell.kind == "proof":
                            # Proof is stabilizing doctrine: lowers volatility and can project coherent fields.
                            event_counts["proof_radiance"] += 1
                            cell.coherence = min(1.0, cell.coherence + 0.09)
                            cell.focus = min(1.0, cell.focus + 0.04)
                            if has_insight:
                                cell.energy += 0.07 * self.insight_learn_scale
                            if has_cache and random.random() < 0.10 * self.proof_stability_scale:
                                random.shuffle(cache_neighbors)
                                if cache_neighbors and random.random() < 0.4:
                                    event_counts["proof_radiance"] += 1
                                    random.shuffle(neighbor_cells)
                                    for nx, ny, spot in neighbor_cells:
                                        if spot is None and next_grid[ny][nx] is None:
                                            pending_spawns.append((plane_id, nx, ny, Cell(kind="proof", age=0, energy=0.78, flavor="proof_fork")))
                                            break
                            if has_meme and random.random() < 0.20 * self.meme_conversion_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (
                                                plane_id,
                                                nx,
                                                ny,
                                                Cell(kind="axiom", age=0, energy=0.68, flavor="proof_crystallization"),
                                            )
                                        )
                                        event_counts["axiom_formations"] += 1
                                        break
                            if has_anomaly and random.random() < 0.12 * self.insight_paradox_scale:
                                event_counts["proof_cascades"] += 1
                                if random.random() < 0.4:
                                    cell.kind = "anomaly"
                            if cell.energy < 0.22:
                                cell = None

                        if cell is None:
                            continue

                        if cell.kind == "bug":
                            # Bug is a parasitic intelligence: it seeks high-energy hosts and can swarm.
                            event_counts["bug_swarm"] += 1
                            cell.energy -= 0.03
                            if random.random() < 0.06 * self.bug_parasite_scale and bug_neighbors:
                                random.shuffle(bug_neighbors)
                                bx, by, _ = bug_neighbors[0]
                                if random.random() < 0.5:
                                    pending_kills.append((plane_id, bx, by))
                                event_counts["bug_infests"] += 1
                            for nx, ny, prey in neighbor_cells:
                                if prey is None:
                                    continue
                                if random.random() < 0.05 * self.bug_parasite_scale:
                                    pending_damage[(plane_id, nx, ny)] = pending_damage.get((plane_id, nx, ny), 0.0) - (0.06 + cfg.life_cost * 0.2)
                                    event_counts["bug_explosions"] += 1
                            if len(bug_neighbors) >= 2 and random.random() < 0.20 * self.bug_parasite_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append((plane_id, nx, ny, Cell(kind="bug", age=0, energy=0.68, flavor="bug_bloom", focus=0.1)))
                                        event_counts["bug_births"] += 1
                                        break
                            if random.random() < 0.05 * self.bug_parasite_scale:
                                # Swarm pulse: local destabilization.
                                event_counts["bug_explosions"] += 1
                                for nx, ny, _ in neighbor_cells:
                                    if random.random() < 0.35:
                                        pending_damage[(plane_id, nx, ny)] = pending_damage.get((plane_id, nx, ny), 0.0) - 0.22
                                        if random.random() < 0.22:
                                            pending_kills.append((plane_id, nx, ny))
                            if cell.energy < 0.18 and random.random() < 0.5:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is not None and spot.kind == "proof" and random.random() < 0.4:
                                        pending_kills.append((plane_id, nx, ny))
                                        event_counts["proof_stabilizations"] += 1
                                        break
                                if random.random() < 0.3:
                                    cell = None
                            if cell is None:
                                continue

                        if cell.kind == "model":
                            # Model cells are meta-cognitive attractors; they integrate neighboring signal and
                            # can emit short insight bursts or recursive projections.
                            event_counts["model_projections"] += 1
                            if has_insight:
                                cell.coherence = min(1.0, cell.coherence + 0.17)
                                cell.focus = min(1.0, cell.focus + 0.12 * self.model_projection_scale)
                            else:
                                cell.coherence = max(0.0, cell.coherence - 0.03 * self.cognition_decay_scale)
                            if has_meme:
                                cell.focus = min(1.0, cell.focus + 0.08 * self.meme_conversion_scale)
                            if has_axiom and random.random() < 0.30 * self.meme_broadcast_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (plane_id, nx, ny, Cell(kind="insight", age=0, energy=0.72, flavor="model_echo", meme=min(1.0, cell.focus + 0.1)))
                                        )
                                        event_counts["insight_births"] += 1
                                        break
                            if cell.focus > 0.7 and random.random() < 0.08 * self.oracle_projection_scale and local_diversity >= 2:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (
                                                plane_id,
                                                nx,
                                                ny,
                                                Cell(
                                                    kind="oracle",
                                                    age=0,
                                                    energy=1.2,
                                                    flavor="modeled_awakening",
                                                    focus=0.85,
                                                    coherence=min(1.0, cell.coherence + 0.1),
                                                ),
                                            )
                                        )
                                        event_counts["oracle_awakenings"] += 1
                                        break
                            if has_anomaly and random.random() < 0.06 * self.insight_paradox_scale:
                                event_counts["model_fractures"] += 1
                                if random.random() < 0.5:
                                    cell.kind = "anomaly"
                                else:
                                    pending_damage[(plane_id, x, y)] = pending_damage.get((plane_id, x, y), 0.0) - 0.22
                            if random.random() < 0.02 * self.cognition_decay_scale:
                                event_counts["model_coherence_decay"] += 1
                                cell.energy -= 0.15
                                if cell.coherence < 0.25:
                                    cell = None
                            if cell is None:
                                continue

                        # Dwarf-like imprinting for goblins: repeated social/epistemic pressure carves local memory.
                        # Imprint fuels later ritualized cognition and den-like spawn behavior.
                        if cell.kind == "goblin":
                            # Predictive loop: expectation vs observed epistemic intensity.
                            observed = (
                                (0.28 if has_insight else 0.0)
                                + (0.19 if has_model else 0.0)
                                + (0.12 if has_meme else 0.0)
                                + (0.08 if has_cult else 0.0)
                                + (0.08 * min(1.0, local_diversity / 6))
                            )
                            observed = min(1.0, observed)
                            expected = max(0.0, min(1.0, cell.prediction))
                            surprise = abs(observed - expected)
                            # Prediction learns quickly from mismatch, so local volatility can force
                            # non-local responses when expectation is repeatedly violated.
                            cell.prediction = max(0.0, min(1.0, (0.55 * cell.prediction) + (0.45 * observed)))
                            cell.surprise = max(0.0, min(1.0, surprise))
                            event_counts["prediction_updates"] += 1
                            if cell.surprise > (0.18 * self.goblin_surprise_scale):
                                event_counts["surprise_spikes"] += 1
                                if random.random() < 0.26 * self.goblin_surprise_scale:
                                    event_counts["cognitive_resonances"] += 1
                                    if random.random() < 0.5 and has_anomaly:
                                        pending_damage[(plane_id, x, y)] = pending_damage.get((plane_id, x, y), 0.0) - 0.12
                                    if random.random() < 0.6:
                                        cell.mania = min(1.0, cell.mania + 0.07)
                                        cell.fervor = min(1.0, cell.fervor + 0.04)
                                if cell.surprise > 0.35 and random.random() < 0.24 * self.goblin_surprise_scale:
                                    random.shuffle(neighbor_cells)
                                    for nx, ny, spot in neighbor_cells:
                                        if spot is None and next_grid[ny][nx] is None:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind="trace",
                                                        age=0,
                                                        energy=0.72,
                                                        flavor="surprise_trace",
                                                        meme=0.75,
                                                        coherence=min(1.0, cell.coherence + 0.15),
                                                        attention=cell.attention * 0.7,
                                                    ),
                                                )
                                            )
                                            event_counts["trace_deposits"] += 1
                                            break
                            nearby_goblin_pressure = 0
                            if neighbor_cells:
                                nearby_goblin_pressure = len(
                                    [
                                        1
                                        for _nx, _ny, n in neighbor_cells
                                        if n is not None and n.kind == "goblin"
                                    ]
                                )
                            imprint_gain = (
                                0.015
                                + (0.012 * nearby_goblin_pressure)
                                + (0.024 * cell.attention)
                            ) * self.goblin_imprint_scale * (0.8 + 0.2 * local_diversity)
                            if has_anomaly:
                                imprint_gain *= 0.78
                            cell.imprint = min(1.0, cell.imprint + imprint_gain)
                            event_counts["imprint_growths"] += 1
                            if cell.imprint > 0.60 and nearby_goblin_pressure >= 2 and random.random() < 0.05 * self.goblin_imprint_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (
                                                plane_id,
                                                nx,
                                                ny,
                                                Cell(
                                                    kind="cache",
                                                    age=0,
                                                    energy=0.88,
                                                    flavor="imprint_hive",
                                                ),
                                            )
                                        )
                                        event_counts["cache_births"] += 1
                                        event_counts["imprint_hives"] += 1
                                        break
                            if (
                                cell.imprint > 0.28
                                and nearby_goblin_pressure >= 1
                                and (has_cache or has_model or (has_insight and cell.prediction > 0.42))
                                and random.random() < 0.030 * self.goblin_imprint_scale * (1.0 + 0.25 * self.cache_pressure_scale)
                            ):
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        recruit = self._make_goblin(
                                            plane_id=plane_id,
                                            neighbor_cells=neighbor_cells,
                                            age=0,
                                            energy=0.74 + random.random() * 0.28,
                                            flavor="memory_recruit",
                                            source_species=cell.species,
                                        )
                                        recruit.attention = min(1.0, cell.attention + 0.18)
                                        recruit.imprint = min(1.0, cell.imprint * 0.55)
                                        recruit.prediction = min(1.0, cell.prediction + 0.10)
                                        pending_spawns.append((plane_id, nx, ny, recruit))
                                        event_counts["memory_recruitments"] += 1
                                        event_counts["goblin_breeds"] += 1
                                        break
                            if cell.imprint > 0.90 and random.random() < 0.05 * self.goblin_imprint_scale:
                                if has_insight and random.random() < 0.6:
                                    pending_spawns.append(
                                        (
                                            plane_id,
                                            x,
                                            y,
                                            Cell(
                                                kind="insight",
                                                age=0,
                                                energy=cell.energy * 0.66,
                                                flavor="imprint_echo",
                                                meme=min(1.0, cell.attention + 0.18),
                                            ),
                                        )
                                )
                                event_counts["insight_births"] += 1
                            if nearby_goblin_pressure >= 1:
                                cell.imprint = max(0.0, cell.imprint - (0.008 * self.goblin_imprint_decay_scale))
                            else:
                                cell.imprint = max(0.0, cell.imprint - (0.004 * self.goblin_imprint_decay_scale))
                            if cell.surprise > 0.70 and random.random() < (0.05 * self.goblin_surprise_scale):
                                cell.imprint = min(1.0, cell.imprint + 0.06)
                                event_counts["imprint_growths"] += 1
                                event_counts["cognitive_resonances"] += 1

                        if cell.kind == "trace":
                            # Trace cells are short-lived cognitive residues, slowly feeding insight back to
                            # nearby organisms or collapsing into noise when overwhelmed.
                            event_counts["trace_decay"] += 1
                            cell.energy -= 0.10 * self.insight_decay_scale
                            cell.meme = min(1.0, cell.meme + 0.12)
                            if has_insight and random.random() < 0.12 * self.insight_learn_scale:
                                event_counts["insight_reads"] += 1
                                for nx, ny, spot in neighbor_cells:
                                    if spot is not None and spot.kind == "goblin":
                                        key = (plane_id, nx, ny)
                                        pending_fervor[key] = min(1.0, pending_fervor.get(key, 0.0) + 0.08)
                                        pending_prediction[key] = min(1.0, pending_prediction.get(key, 0.0) + 0.18)
                                        break
                            if has_meme and random.random() < 0.22 * self.meme_pressure_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (
                                                plane_id,
                                                nx,
                                                ny,
                                                Cell(kind="insight", age=0, energy=0.6, flavor="trace_etch", meme=0.7),
                                            )
                                        )
                                        break
                            if random.random() < 0.06 * self.goblin_trace_scale:
                                cell.kind = "anomaly"
                            if cell.energy <= 0.18:
                                cell = None

                        if cell is None:
                            continue

                        if cell.kind == "oracle":
                            # Oracles are mature cognitive artifacts: they stabilize neighbors and expose paradoxes.
                            event_counts["oracle_broadcasts"] += 1
                            if has_meme:
                                cell.coherence = min(1.0, cell.coherence + 0.14)
                            cell.focus = min(1.0, cell.focus + 0.10)
                            if has_insight and random.random() < 0.12 * self.insight_learn_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append((plane_id, nx, ny, Cell(kind="model", age=0, energy=1.0, flavor="oracle_projection", focus=0.7)))
                                        event_counts["model_births"] += 1
                                        break
                            if has_meme and random.random() < 0.10 * self.meme_broadcast_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is not None and spot.kind != "anomaly" and random.random() < 0.35:
                                        if random.random() < 0.45:
                                            pending_fervor[(plane_id, nx, ny)] = min(1.0, pending_fervor.get((plane_id, nx, ny), 0.0) + 0.10)
                                        break
                            if has_anomaly:
                                # Oracles can locally quarantine anomalies into feedback noise rather than collapse.
                                for nx, ny, spot in neighbor_cells:
                                    if spot is not None and spot.kind == "anomaly" and random.random() < 0.25:
                                        pending_kills.append((plane_id, nx, ny))
                                        event_counts["oracle_broadcasts"] += 1
                                        break
                            if has_model and random.random() < 0.06 * self.oracle_projection_scale:
                                cell.coherence = min(1.0, cell.coherence + 0.08)
                            if cell.coherence < 0.2:
                                event_counts["model_fractures"] += 1
                                cell = None
                            if cell is None:
                                continue

                        if cell.kind == "norn_maker" and cell.energy > 1.8 and cell.age % 4 == 0:
                            # Rarely print new life by tissue-molding.
                            if random.random() < 0.36:
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        pending_spawns.append((plane_id, nx, ny, Cell("norn", age=0, energy=0.8 + random.random(), flavor="nurtured")))
                                        cell.energy -= 1.0
                                        event_counts["norn_makers"] += 1
                                        break

                        if has_insight and cell.kind in {"life", "norn", "drone", "manufacturer", "norn_maker", "drone_mother"}:
                            # Nearby insight can trigger unexpected local transitions.
                            if random.random() < (0.015 * self.insight_transmute_scale * max(1, local_diversity)):
                                transmutation_map = {
                                    "life": [("echo", 0.24), ("drone", 0.20), ("norn", 0.20), ("insight", 0.20), ("axiom", 0.06), ("cult", 0.10)],
                                    "norn": [("goblin", 0.28), ("manufacturer", 0.16), ("norn_maker", 0.12), ("insight", 0.24), ("axiom", 0.08), ("cult", 0.12)],
                                    "drone": [("goblin", 0.14), ("echo", 0.18), ("insight", 0.24), ("life", 0.24), ("axiom", 0.10), ("cult", 0.10)],
                                    "manufacturer": [("drone", 0.20), ("norn_maker", 0.30), ("insight", 0.28), ("axiom", 0.12), ("cult", 0.10)],
                                    "norn_maker": [("insight", 0.25), ("manufacturer", 0.34), ("norn", 0.23), ("axiom", 0.07), ("cult", 0.11)],
                                    "drone_mother": [("insight", 0.32), ("egg", 0.20), ("drone", 0.18), ("life", 0.15), ("axiom", 0.06), ("cult", 0.09)],
                                }
                                target_map = transmutation_map.get(cell.kind)
                                if target_map:
                                    cell = Cell(
                                        kind=self._choose_weighted(target_map),
                                        age=0,
                                        energy=max(0.6, cell.energy * 0.92),
                                        flavor="insight_aware",
                                        meme=cell.meme + (0.1 * self.insight_learn_scale),
                                    )
                                    event_counts["insight_cascades"] += 1

                        if has_meme and cell.kind in {"life", "norn", "drone", "manufacturer", "norn_maker", "drone_mother"}:
                            # Meme resonance induces occasional ideological drift.
                            if random.random() < (0.020 * self.meme_conversion_scale * max(1, local_diversity)):
                                drift_map = {
                                    "life": [("meme", 0.24), ("insight", 0.20), ("goblin", 0.12), ("life", 0.28), ("axiom", 0.08), ("cult", 0.08)],
                                    "norn": [("meme", 0.30), ("insight", 0.18), ("goblin", 0.12), ("norn", 0.27), ("axiom", 0.07), ("cult", 0.06)],
                                    "drone": [("meme", 0.28), ("insight", 0.16), ("goblin", 0.12), ("drone", 0.34), ("axiom", 0.05), ("cult", 0.05)],
                                    "manufacturer": [("meme", 0.38), ("insight", 0.12), ("goblin", 0.08), ("manufacturer", 0.29), ("axiom", 0.06), ("cult", 0.07)],
                                }
                                drift = drift_map.get(cell.kind)
                                if drift:
                                    cell = Cell(
                                        kind=self._choose_weighted(drift),
                                        age=0,
                                        energy=max(0.65, cell.energy * 0.9),
                                        flavor="meme_drift",
                                        meme=min(1.0, cell.meme + 0.2 * self.meme_conversion_scale),
                                    )
                                    event_counts["meme_attunements"] += 1

                        if has_anomaly and cell.kind == "shard":
                            # Insight paradox: anomalies accelerate local shard instability.
                            if random.random() < 0.12 * self.insight_paradox_scale:
                                event_counts["anomaly_cascades"] += 1
                                pending_damage[(plane_id, x, y)] = pending_damage.get((plane_id, x, y), 0.0) - (cfg.shard_decay_penalty * 2.8)

                        if cell.kind == "insight":
                            # Insight nodes act as memetic catalysts: small growth from nearby intelligence, then decay.
                            if has_insight and local_diversity >= 3:
                                cell.energy += 0.18
                                event_counts["insight_reads"] += 1
                            cell.energy -= 0.16 * self.insight_decay_scale
                            cell.meme = min(1.0, cell.meme + (0.06 * self.meme_pressure_scale))
                            if random.random() < 0.09 * self.insight_cascade_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        if random.random() < 0.60:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind="insight",
                                                        age=0,
                                                        energy=0.7,
                                                        flavor="cascaded",
                                                    ),
                                                )
                                            )
                                            event_counts["insight_cascades"] += 1
                                            event_counts["insight_reads"] += 1
                                        break
                            if has_anomaly:
                                event_counts["insight_stabilizations"] += 1
                                if random.random() < 0.50:
                                    cell.energy += 0.2
                            if random.random() < 0.05 * self.insight_paradox_scale and local_diversity >= 4:
                                # Insights that attract contradictions occasionally become anomalies.
                                cell.kind = "anomaly"
                                event_counts["insight_stabilizations"] += 1
                            if has_meme and random.random() < 0.10 * self.meme_conversion_scale:
                                # Meme coupling can push insight into broader propagation.
                                cell.meme = min(1.2, cell.meme + 0.35)
                            if (has_meme and has_cult and random.random() < 0.05 * self.insight_learn_scale):
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (
                                                plane_id,
                                                nx,
                                                ny,
                                                Cell(
                                                    kind="axiom",
                                                    age=0,
                                                    energy=0.75,
                                                    flavor="axiom_from_insight",
                                                    meme=min(1.0, cell.meme + 0.35),
                                                ),
                                            )
                                        )
                                        event_counts["axiom_formations"] += 1
                                        break
                            if has_cult and has_axiom and random.random() < 0.03 * self.insight_learn_scale:
                                # Cult loops with axioms tend to crystallize into additional cult structure.
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (
                                                plane_id,
                                                nx,
                                                ny,
                                                Cell(
                                                    kind="cult",
                                                    age=0,
                                                    energy=0.82,
                                                    flavor="crystalized_cult",
                                                ),
                                            )
                                        )
                                        event_counts["goblin_cult_births"] += 1
                                        break

                        if cell.kind == "meme":
                            # Meme spores transmit ideology and can destabilize or ignite anomalies.
                            cell.meme += 0.18 * self.meme_broadcast_scale
                            cell.energy -= 0.12 * self.meme_decay_scale
                            if has_axiom and random.random() < 0.05 * self.meme_conversion_scale and cell.meme > 0.4:
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (
                                                plane_id,
                                                nx,
                                                ny,
                                                Cell(
                                                    kind="axiom",
                                                    age=0,
                                                    energy=0.95,
                                                    flavor="meme_to_axiom",
                                                    meme=min(1.0, cell.meme),
                                                ),
                                            )
                                        )
                                        event_counts["axiom_formations"] += 1
                                        break
                            if has_cult and random.random() < 0.06 * self.meme_conversion_scale and cell.meme > 0.35:
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (
                                                plane_id,
                                                nx,
                                                ny,
                                                Cell(
                                                    kind="cult",
                                                    age=0,
                                                    energy=0.75,
                                                    flavor="meme_to_cult",
                                                ),
                                            )
                                        )
                                        event_counts["goblin_cult_births"] += 1
                                        break
                            if random.random() < 0.15 * self.meme_broadcast_scale and cell.meme > 0.35:
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        if random.random() < 0.5:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(
                                                        kind="meme",
                                                        age=0,
                                                        energy=0.8,
                                                        flavor="broadcast",
                                                        meme=min(1.0, cell.meme * 0.7),
                                                    ),
                                                )
                                            )
                                            event_counts["meme_broadcasts"] += 1
                                        else:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(kind="insight", age=0, energy=0.6, flavor="meme_to_insight"),
                                                )
                                            )
                                            event_counts["meme_attunements"] += 1
                                        break
                            if has_anomaly and random.random() < 0.12 * self.insight_paradox_scale:
                                if random.random() < 0.6:
                                    pending_damage[(plane_id, x, y)] = pending_damage.get((plane_id, x, y), 0.0) - 0.22
                                else:
                                    cell.kind = "anomaly"
                                    event_counts["anomaly_cascades"] += 1
                            if cell.meme > 0.9 and random.random() < 0.03 * self.meme_conversion_scale:
                                if random.random() < 0.5:
                                    cell.kind = "insight"
                                    event_counts["meme_attunements"] += 1

                        if cell.kind == "anomaly":
                            event_counts["anomaly_ticks"] += 1
                            cell.energy -= 0.32 * self.insight_decay_scale
                            for nx, ny, neighbor in neighbor_cells:
                                if neighbor is not None and random.random() < 0.18:
                                    pending_damage[(plane_id, nx, ny)] = pending_damage.get((plane_id, nx, ny), 0.0) - (cfg.shard_decay_penalty * 2.1 + 0.08)
                                    if random.random() < 0.12:
                                        pending_kills.append((plane_id, nx, ny))
                                        event_counts["anomaly_cascades"] += 1
                            if random.random() < 0.04:
                                pending_kills.append((plane_id, x, y))
                                event_counts["anomaly_cascades"] += 1

                        if cell.kind == "drone_mother" and cell.energy > 2.0 and cell.age % 3 == 0:
                            # Drone-mothers build local brood-lattice structure.
                            if random.random() < 0.32:
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        spawn_kind = "egg" if random.random() < 0.7 else "drone"
                                        pending_spawns.append((plane_id, nx, ny, Cell(spawn_kind, age=0, energy=1.0 + random.random() * 0.5, flavor="hive")))
                                        cell.energy -= 1.1
                                        event_counts["drone_mothers"] += 1
                                        break

                        if cell.kind == "cult":
                            # Cult clusters can convert social pressure into recruitment and doctrinal artifacts.
                            event_counts["goblin_cults"] += 1
                            nearby_goblins = [
                                (nx, ny, neighbor)
                                for nx, ny, neighbor in neighbor_cells
                                if neighbor is not None and neighbor.kind == "goblin"
                            ]
                            if nearby_goblins:
                                for _ in range(min(2, len(nearby_goblins))):
                                    if random.random() < 0.08 * self.goblin_cult_scale:
                                        _, _, cultist = random.choice(nearby_goblins)
                                        if isinstance(cultist, Cell):
                                            neighbor_species = getattr(cultist, "species", "wild")
                                        else:
                                            neighbor_species = "wild"
                                        random.shuffle(neighbor_cells)
                                        for nx, ny, spot in neighbor_cells:
                                            if spot is None and next_grid[ny][nx] is None:
                                                pending_spawns.append(
                                                    (
                                                        plane_id,
                                                        nx,
                                                        ny,
                                                        self._make_goblin(
                                                            plane_id=plane_id,
                                                            neighbor_cells=neighbor_cells,
                                                            age=0,
                                                            energy=0.35 + random.random() * 0.15,
                                                            flavor="cult_brood",
                                                            source_species=neighbor_species,
                                                        ),
                                                    )
                                                )
                                                break

                            if (has_meme or has_insight) and random.random() < 0.12 * self.goblin_cult_scale:
                                spawned = Cell(kind="meme", age=0, energy=0.75, flavor="cult_signal", meme=0.9)
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        pending_spawns.append((plane_id, nx, ny, spawned))
                                        event_counts["meme_births"] += 1
                                        break
                            if has_insight and random.random() < 0.06 * self.goblin_axiom_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (plane_id, nx, ny, Cell(kind="axiom", age=0, energy=1.0, flavor="cult_axiom"))
                                        )
                                        event_counts["axiom_formations"] += 1
                                        break
                            if has_anomaly and random.random() < 0.10 * self.insight_paradox_scale:
                                event_counts["goblin_cult_births"] += 1
                                cell = None
                            if random.random() < 0.01 * self.goblin_species_ascend_scale:
                                event_counts["axiom_decay"] += 1
                                cell = None

                        if cell is None:
                            continue

                        if cell.kind == "ritual":
                            # Ritual loci amplify social feedback when enough stress, memes, and insight cluster.
                            event_counts["rituals"] += 1
                            cell.energy -= 0.08 * self.insight_decay_scale
                            for nx, ny, spot in neighbor_cells:
                                if (
                                    spot is not None
                                    and spot.kind == "goblin"
                                    and random.random() < 0.18 * self.goblin_fervor_scale
                                ):
                                    key = (plane_id, nx, ny)
                                    pending_fervor[key] = min(1.0, pending_fervor.get(key, 0.0) + 0.14)
                                    event_counts["ritual_stimuli"] += 1
                            if has_meme and random.random() < 0.30 * self.meme_broadcast_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append((plane_id, nx, ny, Cell(kind="meme", age=0, energy=0.68, flavor="ritual_echo", meme=0.8)))
                                        event_counts["meme_births"] += 1
                                        event_counts["ritual_stimuli"] += 1
                                        break
                            if has_insight and random.random() < 0.15 * self.insight_learn_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, spot in neighbor_cells:
                                    if spot is None and next_grid[ny][nx] is None:
                                        pending_spawns.append((plane_id, nx, ny, Cell(kind="axiom", age=0, energy=0.9, flavor="ritual_axiom")))
                                        event_counts["axiom_formations"] += 1
                                        event_counts["ritual_stimuli"] += 1
                                        break
                            if has_anomaly and random.random() < 0.10:
                                event_counts["anomaly_cascades"] += 1
                                cell.energy -= 0.4
                                if random.random() < 0.5:
                                    cell.kind = "anomaly"
                            if cell.age > 60 and random.random() < 0.08:
                                event_counts["axiom_decay"] += 1
                                cell = None

                        if cell is None:
                            continue

                        if cell is not None and cell.kind == "axiom":
                            # Axiom fields act like local proof artifacts: they stabilize neighbors,
                            # then occasionally decompose into memes or insight.
                            axiom_neighbors = [
                                (nx, ny, neighbor)
                                for nx, ny, neighbor in neighbor_cells
                                if neighbor is not None and neighbor.kind == "goblin"
                            ]
                            event_counts["axiom_sparks"] += 1
                            cell.meme = min(1.0, cell.meme + 0.15)
                            cell.energy += 0.06
                            if random.random() < 0.24 * self.meme_pressure_scale and axiom_neighbors:
                                random.shuffle(axiom_neighbors)
                                _, _, disciple = axiom_neighbors[0]
                                if isinstance(disciple, Cell) and disciple.kind == "goblin":
                                    disciple.mania = min(1.0, disciple.mania + 0.08)
                            if has_meme and random.random() < 0.18 * self.meme_broadcast_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        if random.random() < 0.5:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(kind="meme", age=0, energy=0.95, flavor="axiom_bloom", meme=0.8),
                                                )
                                            )
                                        else:
                                            pending_spawns.append(
                                                (
                                                    plane_id,
                                                    nx,
                                                    ny,
                                                    Cell(kind="insight", age=0, energy=0.7, flavor="axiom_echo", meme=0.25),
                                                )
                                            )
                                        event_counts["meme_births"] += 1
                                        break
                            if has_insight and random.random() < 0.16 * self.insight_learn_scale:
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        pending_spawns.append(
                                            (
                                                plane_id,
                                                nx,
                                                ny,
                                                Cell(kind="goblin", age=0, energy=0.9, flavor="axiom_ward", species="sage"),
                                            )
                                        )
                                        event_counts["axiom_formations"] += 1
                                        break
                            if has_anomaly and random.random() < 0.07 * self.insight_transmute_scale:
                                event_counts["insight_stabilizations"] += 1
                                for _, _, nearby in neighbor_cells:
                                    if nearby is not None and nearby.kind == "anomaly":
                                        nearby.kind = "insight"
                                        break
                            if cell.age > 70 and random.random() < 0.10:
                                event_counts["axiom_decay"] += 1
                                cell = None

                        if cell.kind == "shard":
                            # shard hazards decay local neighbors and persist with instability.
                            cell.energy -= cfg.shard_decay_penalty
                            for nx, ny, neighbor in neighbor_cells:
                                if neighbor is not None and random.random() < 0.045:
                                    key = (plane_id, nx, ny)
                                    if neighbor.kind in {"shard", "manufacturer", "norn", "norn_maker", "life", "egg", "drone", "drone_mother", "echo"}:
                                        if random.random() < 0.20:
                                            pending_kills.append(key)
                                            event_counts["shard_culls"] += 1
                                        else:
                                            pending_damage[key] = pending_damage.get(key, 0.0) - (cfg.shard_decay_penalty * 1.4)
                                            event_counts["energy_hits"] += 1
                                            event_counts["shard_corruptions"] += 1
                                    else:
                                        pending_damage[key] = pending_damage.get(key, 0.0) - (cfg.shard_decay_penalty * 0.7)

                        if cell.kind == "echo":
                            # Echo kinds can broadcast and duplicate into nearby empties.
                            if random.random() < cfg.echo_propagate_chance:
                                random.shuffle(neighbor_cells)
                                for nx, ny, neighbor in neighbor_cells:
                                    if neighbor is None and next_grid[ny][nx] is None:
                                        pending_spawns.append((plane_id, nx, ny, Cell("echo", age=0, energy=1.0, flavor="echo_bloom")))
                                        event_counts["echo_blooms"] += 1
                                        break

                        if cell.kind == "manufacturer":
                            # manufacturing: spend energy to fabricate an egg/drone.
                            event_counts["manufacture_attempts"] += 1
                            if cell.energy > cfg.manufacturer_spawn_cost and random.random() < cfg.manufacturer_spawn_energy:
                                neighbors = [
                                    (x + dx, y + dy)
                                    for dx in (-1, 0, 1)
                                    for dy in (-1, 0, 1)
                                    if not (dx == 0 and dy == 0)
                                ]
                                random.shuffle(neighbors)
                                for nx, ny in neighbors:
                                    nx %= self.width
                                    ny %= self.height
                                    if grid[ny][nx] is None and next_grid[ny][nx] is None:
                                        manufacture = Cell(
                                            kind="egg",
                                            age=0,
                                            energy=cfg.manufacturer_birth_bonus + random.random(),
                                            flavor="manufactured",
                                        )
                                        pending_spawns.append((plane_id, nx, ny, manufacture))
                                        cell.energy -= cfg.manufacturer_spawn_cost
                                        event_counts["manufacture_success"] += 1
                                        break

                        if cell.kind == "egg":
                            if cell.age >= cfg.egg_hatch_turns and random.random() < 0.9:
                                new_kind = self._choose_weighted(
                                    cfg.evolution_map.get("egg", [("life", 1.0)])
                                )
                                cell = Cell(
                                    kind=new_kind,
                                    age=0,
                                    energy=max(1.0, cell.energy * 0.7),
                                )
                                event_counts["hatches"] += 1
                            if random.random() < cfg.mutation_rate * 0.15 and plane_id == "MIRAGE":
                                cell.energy *= 1.15

                        if cell.kind in cfg.evolution_map and random.random() < cfg.mutation_rate:
                            evolved = self._choose_weighted(cfg.evolution_map[cell.kind])
                            if evolved != cell.kind:
                                cell = Cell(kind=evolved, age=max(0, cell.age // 2), energy=max(0.9, cell.energy * 0.9))
                                event_counts["mutations"] += 1

                        # Gateway checks by shape
                        if cooldown_grid[y][x] <= 0:
                            for rule in self.gates:
                                if rule.from_plane != plane_id:
                                    continue
                                event_counts["gate_checks"] += 1
                                gate_roll = random.random()
                                shape_matches = self._match_gate(plane_id, grid, x, y, rule)
                                if shape_matches:
                                    event_counts["gate_shape_matches"] += 1
                                    key = f"gate_rule_shape_match::{rule.name}"
                                    event_counts[key] = event_counts.get(key, 0) + 1
                                if (
                                    gate_roll < rule.chance * (1.0 - cfg.gate_risk_penalty)
                                    and shape_matches
                                ):
                                    gates.append((plane_id, x, y, rule.to_plane, Cell(rule.to_kind, age=0, energy=max(1.5, cell.energy), flavor=rule.name), rule.effects_enabled, rule.placement_search_radius))
                                    event_counts["gate_transfers"] += 1
                                    key = f"gate_rule_transfer::{rule.name}"
                                    event_counts[key] = event_counts.get(key, 0) + 1
                                    cooldown_grid[y][x] = cfg.gate_cooldown
                                    if rule.consume and rule.effects_enabled:
                                        cell = None  # remove anchor and let source die into void
                                        event_counts["gate_source_consumed"] += 1
                                        key = f"gate_rule_source_consumed::{rule.name}"
                                        event_counts[key] = event_counts.get(key, 0) + 1
                                    break
                        else:
                            event_counts["gate_rejections"] += 1

                        if cell is None:
                            continue

                        if cell.energy <= 0:
                            continue
                        # Copy survived cell.
                        next_grid[y][x] = cell
                    else:
                        # Death transitions: no survival.
                        event_counts["deaths"] += 1
                        # Sometimes dying living matter leaves a residual egg / shard.
                        if random.random() < 0.12 and current.kind in {"norn", "manufacturer", "drone"}:
                            next_grid[y][x] = Cell("egg", age=0, energy=0.7)
                        # else remains empty.
                        if random.random() < 0.02:
                            next_grid[y][x] = Cell("shard", age=0, energy=0.6)

        # Apply environmental effects from shard noise before special spawns.
        for plane_id, x, y in pending_kills:
            if 0 <= x < self.width and 0 <= y < self.height:
                next_grids[plane_id][y][x] = None
        for (plane_id, x, y), damage in pending_damage.items():
            if 0 <= x < self.width and 0 <= y < self.height:
                cell = next_grids[plane_id][y][x]
                if cell is not None:
                    cell.energy += damage
                    if cell.energy <= 0:
                        next_grids[plane_id][y][x] = None

        for (plane_id, x, y), fervor_delta in pending_fervor.items():
            if 0 <= x < self.width and 0 <= y < self.height:
                cell = next_grids[plane_id][y][x]
                if cell is not None and cell.kind == "goblin":
                    cell.fervor = min(1.0, cell.fervor + fervor_delta)

        for (plane_id, x, y), bond_delta in pending_bond.items():
            if 0 <= x < self.width and 0 <= y < self.height:
                cell = next_grids[plane_id][y][x]
                if cell is not None and cell.kind == "goblin":
                    cell.bond = min(1.0, cell.bond + bond_delta)

        for (plane_id, x, y), lock_delta in pending_pair_lock.items():
            if 0 <= x < self.width and 0 <= y < self.height:
                cell = next_grids[plane_id][y][x]
                if cell is not None and cell.kind == "goblin":
                    cell.pair_lock = min(1.0, cell.pair_lock + lock_delta)

        for (plane_id, x, y), prediction_delta in pending_prediction.items():
            if 0 <= x < self.width and 0 <= y < self.height:
                cell = next_grids[plane_id][y][x]
                if cell is not None and cell.kind == "goblin":
                    cell.prediction = min(1.0, cell.prediction + prediction_delta)

        # Apply same-plane manufacturing spawns.
        for plane_id, nx, ny, cell in pending_spawns:
            grid = next_grids[plane_id]
            if grid[ny][nx] is None:
                grid[ny][nx] = cell

        # Apply gateway teleports. Gate anchors already removed from source at creation.
        for source_plane, x, y, target_plane, cell, effects_enabled, placement_search_radius in gates:
            if target_plane not in next_grids:
                continue
            # Teleport with slight drift to nearby coordinate.
            tx = (x + random.choice((-1, 0, 1))) % self.width
            ty = (y + random.choice((-1, 0, 1))) % self.height
            if not effects_enabled:
                event_counts["gate_effects_suppressed"] += 1
                key = f"gate_rule_suppressed::{cell.flavor}"
                event_counts[key] = event_counts.get(key, 0) + 1
                continue
            target_grid = next_grids[target_plane]
            gate_name = cell.flavor
            if target_grid[ty][tx] is None:
                cell.flavor = f"{cell.flavor}_from_{source_plane}"
                target_grid[ty][tx] = cell
                event_counts["gate_placements"] += 1
                key = f"gate_rule_placement::{gate_name}"
                event_counts[key] = event_counts.get(key, 0) + 1
                key = f"gate_rule_placement_target::{gate_name}::{target_plane}"
                event_counts[key] = event_counts.get(key, 0) + 1
            else:
                rescued = None
                radius = max(0, int(placement_search_radius))
                if radius:
                    offsets = [
                        (dx, dy)
                        for dy in range(-radius, radius + 1)
                        for dx in range(-radius, radius + 1)
                        if dx != 0 or dy != 0
                    ]
                    offsets.sort(
                        key=lambda offset: (
                            abs(offset[0]) + abs(offset[1]),
                            offset[1],
                            offset[0],
                        )
                    )
                    for dx, dy in offsets:
                        rx = (tx + dx) % self.width
                        ry = (ty + dy) % self.height
                        if target_grid[ry][rx] is None:
                            rescued = (rx, ry)
                            break
                if rescued is None:
                    event_counts["gate_target_occupied"] += 1
                    key = f"gate_rule_target_occupied::{gate_name}"
                    event_counts[key] = event_counts.get(key, 0) + 1
                else:
                    rx, ry = rescued
                    cell.flavor = f"{cell.flavor}_from_{source_plane}"
                    target_grid[ry][rx] = cell
                    event_counts["gate_placements"] += 1
                    event_counts["gate_rescued_placements"] += 1
                    key = f"gate_rule_placement::{gate_name}"
                    event_counts[key] = event_counts.get(key, 0) + 1
                    key = f"gate_rule_placement_target::{gate_name}::{target_plane}"
                    event_counts[key] = event_counts.get(key, 0) + 1
                    key = f"gate_rule_rescue::{gate_name}"
                    event_counts[key] = event_counts.get(key, 0) + 1

        # Commit this tick.
        self.grids = next_grids
        stats = self.stats()
        # Complexity must observe current-tick gate placements, not the prior tick.
        self.last_events = event_counts
        complexity, complexity_metrics = self._compute_complexity(stats)
        pair_lock_total = 0.0
        pair_lock_count = 0
        pair_lock_max = 0.0
        bond_total = 0.0
        bond_count = 0
        bond_max = 0.0
        for plane_grid in self.grids.values():
            for row in plane_grid:
                for cell in row:
                    if cell is None or cell.kind != "goblin":
                        continue
                    pair_lock_total += cell.pair_lock
                    pair_lock_count += 1
                    pair_lock_max = max(pair_lock_max, cell.pair_lock)
                    bond_total += cell.bond
                    bond_count += 1
                    bond_max = max(bond_max, cell.bond)

        if pair_lock_count > 0:
            complexity_metrics["pair_lock_density"] = pair_lock_total / pair_lock_count
            complexity_metrics["pair_lock_max"] = pair_lock_max
        else:
            complexity_metrics["pair_lock_density"] = 0.0
            complexity_metrics["pair_lock_max"] = 0.0
        if bond_count > 0:
            complexity_metrics["pair_bond_density"] = bond_total / bond_count
            complexity_metrics["pair_bond_max"] = bond_max
        else:
            complexity_metrics["pair_bond_density"] = 0.0
            complexity_metrics["pair_bond_max"] = 0.0
        # Track attention/imprint/prediction complexity pressures from a social-ecology perspective.
        total_attention = 0.0
        total_imprint = 0.0
        total_prediction = 0.0
        total_surprise = 0.0
        high_attention_cells = 0
        attentive_cells = 0
        high_surprise_cells = 0
        predictive_cells = 0
        total_cells_for_metric = 0
        for plane_grid in self.grids.values():
            for row in plane_grid:
                for cell in row:
                    if cell is None:
                        continue
                    total_cells_for_metric += 1
                    total_attention += cell.attention
                    total_imprint += cell.imprint
                    total_prediction += cell.prediction
                    total_surprise += cell.surprise
                    if cell.attention > 0.55:
                        high_attention_cells += 1
                    if cell.attention > 0.2:
                        attentive_cells += 1
                    if cell.surprise > 0.45:
                        high_surprise_cells += 1
                    if cell.prediction > 0.72:
                        predictive_cells += 1
        if total_cells_for_metric > 0:
            avg_attention = total_attention / total_cells_for_metric
            avg_imprint = total_imprint / total_cells_for_metric
            avg_prediction = total_prediction / total_cells_for_metric
            avg_surprise = total_surprise / total_cells_for_metric
            high_attention_density = high_attention_cells / total_cells_for_metric
            attentive_density = attentive_cells / total_cells_for_metric
            surprise_density = high_surprise_cells / total_cells_for_metric
            predictive_confidence = predictive_cells / total_cells_for_metric
        else:
            avg_attention = 0.0
            avg_imprint = 0.0
            avg_prediction = 0.0
            avg_surprise = 0.0
            high_attention_density = 0.0
            attentive_density = 0.0
            surprise_density = 0.0
            predictive_confidence = 0.0
        complexity_metrics["avg_attention"] = avg_attention
        complexity_metrics["avg_imprint"] = avg_imprint
        complexity_metrics["high_attention_density"] = high_attention_density
        complexity_metrics["attentive_density"] = attentive_density
        complexity_metrics["avg_prediction"] = avg_prediction
        complexity_metrics["avg_surprise"] = avg_surprise
        complexity_metrics["surprise_density"] = surprise_density
        complexity_metrics["predictive_confidence"] = predictive_confidence
        # Inject a social cognition term into complexity if attention becomes sticky and widespread.
        complexity += (
            0.15 * avg_attention
            + 0.10 * avg_imprint
            + 0.08 * high_attention_density
            + 0.06 * avg_prediction
            + 0.06 * avg_surprise
            + 0.05 * predictive_confidence
            + 0.04 * surprise_density
        )
        self.last_events = event_counts
        self.last_metrics = {"complexity": complexity, **complexity_metrics}
        self.complexity_history.append(complexity)
        self._last_counts = stats
        return stats

    def event_counts(self) -> Dict[str, int]:
        return dict(self.last_events)

    def latest_metrics(self) -> Dict[str, float]:
        return dict(self.last_metrics)

    def last_complexity(self) -> float:
        return float(self.last_metrics.get("complexity", 0.0))

    def stats(self) -> Dict[str, Dict[str, int]]:
        snapshot: Dict[str, Dict[str, int]] = {}
        for plane_id, grid in self.grids.items():
            counts: Dict[str, int] = {}
            for row in grid:
                for cell in row:
                    if cell is None:
                        continue
                    counts[cell.kind] = counts.get(cell.kind, 0) + 1
                    counts["total"] = counts.get("total", 0) + 1
            counts.setdefault("total", 0)
            snapshot[plane_id] = counts
        return snapshot

    def render(self, plane_id: str) -> str:
        grid = self.grids[plane_id]
        lines = [f"--- {plane_id} --- turn {self.tick_count}"]
        for y in range(self.height):
            line = []
            for x in range(self.width):
                cell = grid[y][x]
                if cell is None:
                    line.append(CHAR_FOR_KIND["empty"])
                else:
                    line.append(CHAR_FOR_KIND.get(cell.kind, "?"))
            lines.append("".join(line))
        return "\n".join(lines)


def summarize(stats: Dict[str, Dict[str, int]]) -> str:
    parts = []
    for plane_id in sorted(stats):
        counts = stats[plane_id]
        parts.append(f"{plane_id}: total={counts.get('total', 0)}")
    return " | ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Experimental multi-plane artificial life sandbox.")
    parser.add_argument("--width", type=int, default=52)
    parser.add_argument("--height", type=int, default=24)
    parser.add_argument("--steps", type=int, default=120)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--density", type=float, default=0.22)
    parser.add_argument("--render", action="store_true", help="Render one frame each tick")
    parser.add_argument("--tick-interval", type=int, default=10, help="How often to print summary when --render is off.")
    parser.add_argument("--events", action="store_true", help="Print event metrics each summary tick.")
    parser.add_argument("--complexity", action="store_true", help="Print complexity metrics each summary tick.")
    parser.add_argument(
        "--plane",
        default="GENESIS",
        choices=["GENESIS", "FORGE", "ECHOSPHERE", "MIRAGE"],
        help="Plane to render when --render is on.",
    )
    args = parser.parse_args()

    universe = LifeUniverse(args.width, args.height, seed=args.seed, seed_density=args.density)
    print("Starting ALife run")
    print(f"seed={args.seed}, steps={args.steps}, plane={args.plane}")
    print(summarize(universe.stats()))
    for _ in range(args.steps):
        stats = universe.step()
        if args.render or universe.tick_count % max(1, args.tick_interval) == 0:
            print(universe.render(args.plane))
            print(summarize(stats))
            if args.complexity:
                print(f"complexity={universe.last_complexity():.4f} metrics={universe.latest_metrics()}")
            if args.events:
                print(f"events={universe.event_counts()}")
            print()


if __name__ == "__main__":
    main()
