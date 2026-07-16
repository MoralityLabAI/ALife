"""Typed, versioned gameplay-event records for the ALife simulator.

The recorder is deliberately observational.  It consumes inert entity IDs,
before/after state snapshots, and the simulator's exact cause audit.  It never
draws randomness or changes transition-rule inputs.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence, TextIO, TypedDict


EVENT_SCHEMA = "alife.chronicle.event.v1"
EVENT_TYPES = frozenset(
    {
        "birth",
        "brood_expansion",
        "death",
        "echo_bloom",
        "gate_transfer",
        "gate_transfer_attempt",
        "goblin_conversion",
        "goblin_love",
        "goblin_pair",
        "goblin_rage",
        "goblin_romance",
        "goblin_sublineage_shift",
        "insight_drift",
        "kind_transition",
        "meme_attachment",
        "norn_making",
        "shard_culling",
        "world_initialized",
    }
)
ENTITY_ID_PATTERN = re.compile(r"e[0-9]{8,}")


class EventEntity(TypedDict, total=False):
    id: str
    role: str
    kind: str
    species: str | None


class CauseLink(TypedDict, total=False):
    type: str
    entity_ids: list[str]
    event_sequence: int


class ChronicleEvent(TypedDict):
    schema: str
    episode_id: str
    world_id: str
    sequence: int
    tick: int
    event_type: str
    plane: str
    region: str
    position: list[int]
    entities: list[EventEntity]
    cause_chain: list[CauseLink]
    details: dict[str, Any]


@dataclass(frozen=True)
class EntityState:
    entity_id: str
    plane: str
    position: tuple[int, ...]
    kind: str
    species: str | None
    age: int
    energy: float
    flavor: str
    love: float
    mania: float
    meme: float
    bond: float
    pair_lock: float
    parent_ids: tuple[str, ...]

    def as_entity(self, role: str = "subject") -> EventEntity:
        return {
            "id": self.entity_id,
            "role": role,
            "kind": self.kind,
            "species": self.species,
        }


def stable_entity_id(value: int | str) -> str:
    if isinstance(value, str):
        if not value:
            raise ValueError("entity ID must not be empty")
        return value
    if value <= 0:
        raise ValueError("entity ID must be positive")
    return f"e{value:08d}"


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def canonical_jsonl(events: Iterable[Mapping[str, Any]]) -> bytes:
    return "".join(canonical_json(event) + "\n" for event in events).encode("utf-8")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate_event(event: Mapping[str, Any]) -> list[str]:
    """Validate the event schema without adding a runtime schema dependency."""

    errors: list[str] = []
    required = {
        "schema",
        "episode_id",
        "world_id",
        "sequence",
        "tick",
        "event_type",
        "plane",
        "region",
        "position",
        "entities",
        "cause_chain",
        "details",
    }
    missing = sorted(required - set(event))
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
        return errors
    if event.get("schema") != EVENT_SCHEMA:
        errors.append(f"schema must be {EVENT_SCHEMA}")
    for key in ("episode_id", "world_id", "event_type", "plane", "region"):
        if not isinstance(event.get(key), str) or not event.get(key):
            errors.append(f"{key} must be a non-empty string")
    for key in ("sequence", "tick"):
        if not _is_int(event.get(key)) or int(event[key]) < 0:
            errors.append(f"{key} must be a non-negative integer")
    if event.get("event_type") not in EVENT_TYPES:
        errors.append(f"event_type must be one of {sorted(EVENT_TYPES)}")
    position = event.get("position")
    if not isinstance(position, list) or not position or not all(_is_int(item) for item in position):
        errors.append("position must be a non-empty list of integers")
    entities = event.get("entities")
    if not isinstance(entities, list):
        errors.append("entities must be a list")
    else:
        seen: set[tuple[str, str]] = set()
        for index, entity in enumerate(entities):
            if not isinstance(entity, Mapping):
                errors.append(f"entities[{index}] must be an object")
                continue
            entity_id = entity.get("id")
            role = entity.get("role")
            if not isinstance(entity_id, str) or not entity_id:
                errors.append(f"entities[{index}].id must be a non-empty string")
            elif ENTITY_ID_PATTERN.fullmatch(entity_id) is None:
                errors.append(f"entities[{index}].id must match e########")
            if not isinstance(role, str) or not role:
                errors.append(f"entities[{index}].role must be a non-empty string")
            if not isinstance(entity.get("kind"), str) or not entity.get("kind"):
                errors.append(f"entities[{index}].kind must be a non-empty string")
            if entity.get("species") is not None and not isinstance(entity.get("species"), str):
                errors.append(f"entities[{index}].species must be null or a string")
            pair = (str(entity_id), str(role))
            if pair in seen:
                errors.append(f"duplicate entity-role pair: {pair}")
            seen.add(pair)
    cause_chain = event.get("cause_chain")
    if not isinstance(cause_chain, list):
        errors.append("cause_chain must be a list")
    else:
        for index, link in enumerate(cause_chain):
            if not isinstance(link, Mapping) or not isinstance(link.get("type"), str):
                errors.append(f"cause_chain[{index}] must contain a string type")
                continue
            entity_ids = link.get("entity_ids")
            if not isinstance(entity_ids, list) or not all(
                isinstance(entity_id, str)
                and ENTITY_ID_PATTERN.fullmatch(entity_id) is not None
                for entity_id in entity_ids
            ):
                errors.append(
                    f"cause_chain[{index}].entity_ids must contain stable entity IDs"
                )
            event_sequence = link.get("event_sequence")
            if event_sequence is not None and (
                not _is_int(event_sequence)
                or event_sequence < 0
                or not _is_int(event.get("sequence"))
                or event_sequence >= int(event["sequence"])
            ):
                errors.append(
                    f"cause_chain[{index}].event_sequence must reference a prior event"
                )
    details = event.get("details")
    if not isinstance(details, Mapping):
        errors.append("details must be an object")
    else:
        try:
            json.dumps(details, allow_nan=False)
        except (TypeError, ValueError):
            errors.append("details must be finite JSON data")
        if event.get("event_type") in {"birth", "death"} and (
            not isinstance(details.get("kind"), str) or not details.get("kind")
        ):
            errors.append("birth/death details.kind must be a non-empty string")
        if event.get("event_type") in {"gate_transfer", "gate_transfer_attempt"}:
            gate_required = {
                "gate",
                "outcome",
                "target_plane",
                "target_position",
                "anchor_offset",
                "anchor_position",
                "cooldown_before",
                "cooldown_after",
            }
            missing_gate = sorted(gate_required - set(details))
            if missing_gate:
                errors.append(
                    "gate details missing fields: " + ", ".join(missing_gate)
                )
            outcome = details.get("outcome")
            successful = {"placed", "rescued_placement"}
            if event.get("event_type") == "gate_transfer" and outcome not in successful:
                errors.append("gate_transfer must describe a successful placement")
            if event.get("event_type") == "gate_transfer_attempt" and outcome in successful:
                errors.append("successful gate placement must use gate_transfer")
            for key in ("cooldown_before", "cooldown_after"):
                if not _is_int(details.get(key)) or int(details[key]) < 0:
                    errors.append(f"gate details.{key} must be a non-negative integer")
    return errors


def validate_stream(events: Sequence[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    episode_ids: set[str] = set()
    world_ids: set[str] = set()
    previous_tick = -1
    for index, event in enumerate(events):
        for error in validate_event(event):
            errors.append(f"event[{index}]: {error}")
        if event.get("sequence") != index:
            errors.append(f"event[{index}]: sequence must equal zero-based JSONL order")
        tick = event.get("tick")
        if _is_int(tick) and tick < previous_tick:
            errors.append(f"event[{index}]: tick order regressed")
        if _is_int(tick):
            previous_tick = tick
        if isinstance(event.get("episode_id"), str):
            episode_ids.add(str(event["episode_id"]))
        if isinstance(event.get("world_id"), str):
            world_ids.add(str(event["world_id"]))
    if len(episode_ids) > 1:
        errors.append("stream contains multiple episode IDs")
    if len(world_ids) > 1:
        errors.append("stream contains multiple world IDs")
    return errors


def read_events(
    source: str | Path | TextIO | Iterable[str] | Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(source, (str, Path)):
        with Path(source).open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    if hasattr(source, "read"):
        return [json.loads(line) for line in source if line.strip()]  # type: ignore[arg-type]
    result: list[dict[str, Any]] = []
    for item in source:
        if isinstance(item, str):
            if item.strip():
                result.append(json.loads(item))
        else:
            result.append(dict(item))
    return result


def iter_events(path: str | Path) -> Iterator[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


class EventBuilder:
    def __init__(self, episode_id: str, world_id: str) -> None:
        self.episode_id = episode_id
        self.world_id = world_id
        self.events: list[ChronicleEvent] = []

    def emit(
        self,
        *,
        tick: int,
        event_type: str,
        plane: str,
        region: str,
        position: Sequence[int],
        entities: Sequence[Mapping[str, Any]],
        cause_chain: Sequence[Mapping[str, Any]] = (),
        details: Mapping[str, Any] | None = None,
    ) -> ChronicleEvent:
        event: ChronicleEvent = {
            "schema": EVENT_SCHEMA,
            "episode_id": self.episode_id,
            "world_id": self.world_id,
            "sequence": len(self.events),
            "tick": int(tick),
            "event_type": event_type,
            "plane": plane,
            "region": region,
            "position": [int(value) for value in position],
            "entities": [dict(value) for value in entities],  # type: ignore[typeddict-item]
            "cause_chain": [dict(value) for value in cause_chain],  # type: ignore[typeddict-item]
            "details": dict(details or {}),
        }
        errors = validate_event(event)
        if errors:
            raise ValueError("invalid chronicle event: " + "; ".join(errors))
        self.events.append(event)
        return event


def _snapshot_universe(universe: Any) -> dict[str, EntityState]:
    snapshot: dict[str, EntityState] = {}
    for plane, grid in universe.grids.items():
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                if cell is None:
                    continue
                entity_id = stable_entity_id(cell.entity_id)
                if entity_id in snapshot:
                    raise RuntimeError(f"duplicate entity ID in universe: {entity_id}")
                snapshot[entity_id] = EntityState(
                    entity_id=entity_id,
                    plane=plane,
                    position=(x, y),
                    kind=cell.kind,
                    species=cell.species if cell.kind == "goblin" else None,
                    age=int(cell.age),
                    energy=float(cell.energy),
                    flavor=str(cell.flavor),
                    love=float(cell.love),
                    mania=float(cell.mania),
                    meme=float(cell.meme),
                    bond=float(cell.bond),
                    pair_lock=float(cell.pair_lock),
                    parent_ids=tuple(stable_entity_id(value) for value in cell.parent_ids),
                )
    return snapshot


def _region(position: Sequence[int], shape: Sequence[int]) -> str:
    if len(position) == 2 and len(shape) == 2:
        x_band = "x_low" if position[0] < shape[0] / 2 else "x_high"
        y_band = "y_low" if position[1] < shape[1] / 2 else "y_high"
        return f"{x_band}_{y_band}"
    return "lattice"


def _entities_by_position(states: Mapping[str, EntityState]) -> dict[tuple[str, tuple[int, ...]], EntityState]:
    return {(state.plane, state.position): state for state in states.values()}


class ChronicleRecorder(EventBuilder):
    """Observe a :class:`alife.LifeUniverse` and emit canonical event records."""

    def __init__(
        self,
        universe: Any,
        *,
        episode_id: str,
        world_id: str,
        include_initial: bool = True,
    ) -> None:
        super().__init__(episode_id, world_id)
        self.universe = universe
        self.shape = (int(universe.width), int(universe.height))
        self._state = _snapshot_universe(universe)
        if include_initial:
            for entity_id in sorted(self._state):
                state = self._state[entity_id]
                self._emit_birth(state, tick=0, cause="initial_seed")

    def _emit_birth(
        self,
        state: EntityState,
        *,
        tick: int,
        cause: str,
        cause_event_sequence: int | None = None,
        parent_states: Mapping[str, EntityState] | None = None,
    ) -> None:
        parent_entities = []
        lineage_lookup = parent_states if parent_states is not None else self._state
        for parent_id in state.parent_ids:
            parent = lineage_lookup.get(parent_id)
            parent_entities.append(
                parent.as_entity("parent")
                if parent is not None
                else {"id": parent_id, "role": "parent", "kind": "unknown", "species": None}
            )
        cause_link: CauseLink = {
            "type": cause,
            "entity_ids": list(state.parent_ids),
        }
        if cause_event_sequence is not None:
            cause_link["event_sequence"] = cause_event_sequence
        birth = self.emit(
            tick=tick,
            event_type="birth",
            plane=state.plane,
            region=_region(state.position, self.shape),
            position=state.position,
            entities=[state.as_entity(), *parent_entities],
            cause_chain=[cause_link],
            details={
                "kind": state.kind,
                "species": state.species,
                "flavor": state.flavor,
                "parent_ids": list(state.parent_ids),
            },
        )
        mechanism = {
            "nurtured": "norn_making",
            "hive": "brood_expansion",
            "cult_brood": "brood_expansion",
            "echo_bloom": "echo_bloom",
            "conversion": "goblin_conversion",
        }.get(state.flavor)
        if mechanism is not None:
            self.emit(
                tick=tick,
                event_type=mechanism,
                plane=state.plane,
                region=_region(state.position, self.shape),
                position=state.position,
                entities=[state.as_entity("created"), *parent_entities],
                cause_chain=[
                    {
                        "type": "birth",
                        "event_sequence": birth["sequence"],
                        "entity_ids": [state.entity_id],
                    }
                ],
                details={"kind": state.kind, "flavor": state.flavor},
            )

    def _nearby_memes(
        self, state: EntityState, before: Mapping[str, EntityState]
    ) -> list[EntityState]:
        memes: list[EntityState] = []
        width, height = self.shape
        for candidate in before.values():
            if candidate.plane != state.plane or candidate.kind != "meme":
                continue
            dx = min(abs(candidate.position[0] - state.position[0]), width - abs(candidate.position[0] - state.position[0]))
            dy = min(abs(candidate.position[1] - state.position[1]), height - abs(candidate.position[1] - state.position[1]))
            if max(dx, dy) <= 1 and (dx or dy):
                memes.append(candidate)
        return sorted(memes, key=lambda item: item.entity_id)

    def step(self) -> Any:
        before = self._state
        result = self.universe.step()
        after = _snapshot_universe(self.universe)
        tick = int(self.universe.tick_count)
        audits = list(self.universe.chronicle_audit())

        death_causes: dict[str, list[CauseLink]] = {}
        birth_cause_sequences: dict[str, int] = {}
        for audit in audits:
            entities = audit.get("entities", [])
            ids = [stable_entity_id(entity["id"]) for entity in entities]
            normalized_entities: list[EventEntity] = []
            for entity in entities:
                normalized_entities.append(
                    {
                        "id": stable_entity_id(entity["id"]),
                        "role": str(entity["role"]),
                        "kind": str(entity["kind"]),
                        "species": entity.get("species"),
                    }
                )
            position = [int(value) for value in audit["position"]]
            emitted_audit = self.emit(
                tick=tick,
                event_type=str(audit["event_type"]),
                plane=str(audit["plane"]),
                region=_region(position, self.shape),
                position=position,
                entities=normalized_entities,
                cause_chain=[{"type": str(audit["cause"]), "entity_ids": ids}],
                details=dict(audit.get("details", {})),
            )
            event_type = str(audit["event_type"])
            if event_type == "shard_culling":
                targets = [
                    stable_entity_id(entity["id"])
                    for entity in entities
                    if entity.get("role") == "target"
                ]
                shards = [
                    stable_entity_id(entity["id"])
                    for entity in entities
                    if entity.get("role") == "shard"
                ]
                for target in targets:
                    death_causes.setdefault(target, []).append(
                        {
                            "type": event_type,
                            "entity_ids": shards,
                            "event_sequence": emitted_audit["sequence"],
                        }
                    )
            if event_type in {"gate_transfer", "gate_transfer_attempt"}:
                sources = [
                    stable_entity_id(entity["id"])
                    for entity in entities
                    if entity.get("role") == "source"
                ]
                for source in sources:
                    death_causes.setdefault(source, []).append(
                        {
                            "type": event_type,
                            "entity_ids": ids,
                            "event_sequence": emitted_audit["sequence"],
                        }
                    )
                if event_type == "gate_transfer":
                    for entity in entities:
                        if entity.get("role") == "created":
                            birth_cause_sequences[
                                stable_entity_id(entity["id"])
                            ] = emitted_audit["sequence"]

        for entity_id in sorted(set(before) - set(after)):
            state = before[entity_id]
            causes = death_causes.get(
                entity_id,
                [{"type": "survival_or_energy_rule", "entity_ids": []}],
            )
            self.emit(
                tick=tick,
                event_type="death",
                plane=state.plane,
                region=_region(state.position, self.shape),
                position=state.position,
                entities=[state.as_entity()],
                cause_chain=causes,
                details={"kind": state.kind, "species": state.species, "age": state.age},
            )

        lineage_lookup = dict(before)
        lineage_lookup.update(after)
        self._state = after
        for entity_id in sorted(set(after) - set(before)):
            state = after[entity_id]
            cause = "cellular_birth"
            if state.flavor.endswith(tuple(f"_from_{plane}" for plane in self.universe.planes)):
                cause = "gate_transfer"
            self._emit_birth(
                state,
                tick=tick,
                cause=cause,
                cause_event_sequence=birth_cause_sequences.get(entity_id),
                parent_states=lineage_lookup,
            )

        for entity_id in sorted(set(before) & set(after)):
            old = before[entity_id]
            new = after[entity_id]
            if old.kind != new.kind:
                is_insight_drift = (
                    old.kind == "insight"
                    or new.kind == "insight"
                    or new.flavor in {"insight_aware", "meme_drift", "meme_to_insight"}
                )
                self.emit(
                    tick=tick,
                    event_type="insight_drift" if is_insight_drift else "kind_transition",
                    plane=new.plane,
                    region=_region(new.position, self.shape),
                    position=new.position,
                    entities=[new.as_entity()],
                    cause_chain=[
                        {
                            "type": new.flavor or "in_place_transition",
                            "entity_ids": [entity_id],
                        }
                    ],
                    details={"from_kind": old.kind, "to_kind": new.kind, "flavor": new.flavor},
                )
            if old.kind == "goblin" and new.kind == "goblin" and new.meme > old.meme:
                nearby_memes = self._nearby_memes(old, before)
                if nearby_memes:
                    self.emit(
                        tick=tick,
                        event_type="meme_attachment",
                        plane=new.plane,
                        region=_region(new.position, self.shape),
                        position=new.position,
                        entities=[new.as_entity(), *[meme.as_entity("meme_source") for meme in nearby_memes]],
                        cause_chain=[
                            {
                                "type": "adjacent_meme",
                                "entity_ids": [meme.entity_id for meme in nearby_memes],
                            }
                        ],
                        details={"meme_before": old.meme, "meme_after": new.meme},
                    )

        errors = validate_stream(self.events)
        if errors:
            raise RuntimeError("chronicle stream invalid: " + "; ".join(errors[:5]))
        return result
