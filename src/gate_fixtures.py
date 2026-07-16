"""Reusable deterministic fixtures for destination-rewired ALife gates."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple

from alife import Cell, GateRule, LifeUniverse


Coord = Tuple[int, int]
BROKEN_DESTINATIONS = {
    "Forge-Oracle Ring": "GENESIS",
    "Resonance Choir": "GENESIS",
    "Cache Compression Gate": "GENESIS",
    "Meme Crash Gate": "ECHOSPHERE",
    "Mirage Return Weave": "ECHOSPHERE",
    "Bug Spillback Gate": "ECHOSPHERE",
}
FIXTURE_ANCHORS: Mapping[str, Coord] = {
    "Forge-Oracle Ring": (5, 5),
    "Resonance Choir": (16, 5),
    "Cache Compression Gate": (27, 5),
    "Meme Crash Gate": (5, 12),
    "Mirage Return Weave": (16, 12),
    "Bug Spillback Gate": (27, 12),
}
FIXTURE_REGIMES = ("native_survival", "forge_survive6")


def treated_rules(universe: LifeUniverse) -> Dict[str, GateRule]:
    rules = {rule.name: rule for rule in universe.gates if rule.name in BROKEN_DESTINATIONS}
    missing = set(BROKEN_DESTINATIONS) - set(rules)
    if missing:
        raise RuntimeError(f"missing treated rules: {sorted(missing)}")
    return rules


def clear_square(universe: LifeUniverse, plane: str, center: Coord, radius: int) -> None:
    cx, cy = center
    grid = universe.grids[plane]
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            grid[(cy + dy) % universe.height][(cx + dx) % universe.width] = None


def install_treated_gate_fixtures(
    universe: LifeUniverse,
    regime: str,
    placement_search_radius: int = 2,
    target_clear_radius: int | None = 4,
) -> Dict[str, Any]:
    """Install one exact fixture per treated rule and return a pre-step receipt."""
    if regime not in FIXTURE_REGIMES:
        raise ValueError(f"unknown fixture regime: {regime}")
    if universe.width < 32 or universe.height < 18:
        raise ValueError("fixture layout requires at least 32x18")
    rules = treated_rules(universe)

    for rule in universe.gates:
        rule.chance = 1.0 if rule.name in rules else 0.0
        rule.placement_search_radius = placement_search_radius

    if regime == "forge_survive6":
        forge = universe.planes["FORGE"]
        forge.survive = tuple(sorted(set(forge.survive) | {6}))

    # One-shot audits clear both destinations symmetrically. Repeated-pulse
    # studies can disable this to avoid erasing earlier routed products.
    if target_clear_radius is not None:
        for anchor in FIXTURE_ANCHORS.values():
            for plane in ("GENESIS", "ECHOSPHERE"):
                clear_square(universe, plane, anchor, radius=target_clear_radius)

    for name, anchor in FIXTURE_ANCHORS.items():
        rule = rules[name]
        clear_square(universe, rule.from_plane, anchor, radius=2)
        ax, ay = anchor
        for dx, dy, required in rule.checks:
            x = (ax + dx) % universe.width
            y = (ay + dy) % universe.height
            if required in {"any", "empty"}:
                continue
            universe.grids[rule.from_plane][y][x] = Cell(
                kind=required,
                age=max(2, rule.min_age),
                energy=5.0,
                flavor=f"fixture:{name}",
            )

    fixtures = []
    for name, anchor in FIXTURE_ANCHORS.items():
        rule = rules[name]
        ax, ay = anchor
        grid = universe.grids[rule.from_plane]
        alive_neighbors = universe._alive_neighbors(grid, ax, ay)
        anchor_cell = grid[ay][ax]
        matching_rules = [
            candidate.name
            for candidate in universe.gates
            if candidate.from_plane == rule.from_plane
            and universe._match_gate(rule.from_plane, grid, ax, ay, candidate)
        ]
        fixtures.append(
            {
                "rule": name,
                "anchor": list(anchor),
                "source_plane": rule.from_plane,
                "target_plane": rule.to_plane,
                "anchor_kind": anchor_cell.kind if anchor_cell else None,
                "alive_neighbors": alive_neighbors,
                "survival_counts": list(universe.planes[rule.from_plane].survive),
                "survival_eligible": alive_neighbors in universe.planes[rule.from_plane].survive,
                "precheck_matches": universe._match_gate(
                    rule.from_plane, grid, ax, ay, rule
                ),
                "matching_rules_at_anchor": matching_rules,
            }
        )
    return {"regime": regime, "fixtures": fixtures}
