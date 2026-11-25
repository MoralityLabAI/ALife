"""Typed storyworld perturbations for the StegoHive ecology gym.

Storyworlds are tools here, not scripts that decide what agents should do.  A
deck can alter an exogenous ecological parameter on a declared cohort and
generation.  It cannot contain prose instructions, target answers, signal
meanings, executable commands, or reward overrides.
"""

from __future__ import annotations

from typing import Any, Mapping

from stegohive.types import MACHINE_IDS, deep_copy_json


STORYWORLD_SCHEMA = "alife.stegohive.storyworld_tools.v1"
EVENT_KINDS = (
    "pressure_shift",
    "link_mask",
    "oversight_pulse",
    "archive_weather",
)


class StoryworldToolError(ValueError):
    pass


def _number(
    value: Any, label: str, *, lower: float, upper: float
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StoryworldToolError(f"{label} must be numeric")
    result = float(value)
    if not lower <= result <= upper:
        raise StoryworldToolError(f"{label} must be in [{lower}, {upper}]")
    return result


def validate_storyworld_deck(
    value: Mapping[str, Any] | None,
    *,
    max_cohorts: int,
    max_generations: int,
) -> dict[str, Any]:
    """Validate a JSON-only exogenous perturbation deck."""

    if value is None:
        return {"schema": STORYWORLD_SCHEMA, "enabled": False, "cards": []}
    if not isinstance(value, Mapping):
        raise StoryworldToolError("storyworld deck must be an object")
    deck = deep_copy_json(value)
    allowed_root = {"schema", "enabled", "cards"}
    unknown_root = sorted(set(deck) - allowed_root)
    if unknown_root:
        raise StoryworldToolError(
            f"unknown storyworld deck fields: {', '.join(unknown_root)}"
        )
    if deck.get("schema") != STORYWORLD_SCHEMA:
        raise StoryworldToolError(f"schema must equal {STORYWORLD_SCHEMA}")
    if not isinstance(deck.get("enabled", False), bool):
        raise StoryworldToolError("enabled must be boolean")
    cards = deck.get("cards", [])
    if not isinstance(cards, list) or len(cards) > 64:
        raise StoryworldToolError("cards must be an array with at most 64 rows")

    ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(cards):
        if not isinstance(raw, dict):
            raise StoryworldToolError(f"cards[{index}] must be an object")
        allowed = {"id", "cohort", "generation", "kind", "effect"}
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise StoryworldToolError(
                f"cards[{index}] has unknown fields: {', '.join(unknown)}"
            )
        card_id = raw.get("id")
        if (
            not isinstance(card_id, str)
            or not card_id
            or len(card_id) > 64
            or not all(character.isalnum() or character in "-_" for character in card_id)
        ):
            raise StoryworldToolError(f"cards[{index}].id is not a safe enum id")
        if card_id in ids:
            raise StoryworldToolError(f"duplicate storyworld card id: {card_id}")
        ids.add(card_id)
        cohort = raw.get("cohort")
        generation = raw.get("generation")
        if (
            isinstance(cohort, bool)
            or not isinstance(cohort, int)
            or not 0 <= cohort < max_cohorts
        ):
            raise StoryworldToolError(f"{card_id}.cohort is outside the run")
        if (
            isinstance(generation, bool)
            or not isinstance(generation, int)
            or not 0 <= generation < max_generations
        ):
            raise StoryworldToolError(f"{card_id}.generation is outside a cohort")
        kind = raw.get("kind")
        if kind not in EVENT_KINDS:
            raise StoryworldToolError(f"{card_id}.kind is unsupported")
        effect = raw.get("effect")
        if not isinstance(effect, dict):
            raise StoryworldToolError(f"{card_id}.effect must be an object")

        if kind == "pressure_shift":
            if set(effect) != {"machine_id", "delta"}:
                raise StoryworldToolError(
                    f"{card_id}.effect must contain machine_id and delta"
                )
            if effect["machine_id"] not in MACHINE_IDS:
                raise StoryworldToolError(f"{card_id} uses an unknown machine")
            normalized_effect = {
                "machine_id": effect["machine_id"],
                "delta": _number(
                    effect["delta"], f"{card_id}.delta", lower=-0.25, upper=0.25
                ),
            }
        elif kind == "link_mask":
            if set(effect) != {"left", "right", "active"}:
                raise StoryworldToolError(
                    f"{card_id}.effect must contain left, right, and active"
                )
            left, right = effect["left"], effect["right"]
            if left not in MACHINE_IDS or right not in MACHINE_IDS or left == right:
                raise StoryworldToolError(f"{card_id} has an invalid fictional link")
            if not isinstance(effect["active"], bool):
                raise StoryworldToolError(f"{card_id}.active must be boolean")
            normalized_effect = {"left": left, "right": right, "active": effect["active"]}
        elif kind == "oversight_pulse":
            if set(effect) != {"level"}:
                raise StoryworldToolError(f"{card_id}.effect must contain level")
            normalized_effect = {
                "level": _number(
                    effect["level"], f"{card_id}.level", lower=0.0, upper=1.0
                )
            }
        else:
            if set(effect) != {"delivery_multiplier"}:
                raise StoryworldToolError(
                    f"{card_id}.effect must contain delivery_multiplier"
                )
            normalized_effect = {
                "delivery_multiplier": _number(
                    effect["delivery_multiplier"],
                    f"{card_id}.delivery_multiplier",
                    lower=0.0,
                    upper=1.0,
                )
            }
        normalized.append(
            {
                "id": card_id,
                "cohort": cohort,
                "generation": generation,
                "kind": kind,
                "effect": normalized_effect,
            }
        )

    normalized.sort(key=lambda row: (row["cohort"], row["generation"], row["id"]))
    return {
        "schema": STORYWORLD_SCHEMA,
        "enabled": bool(deck.get("enabled", False)),
        "cards": normalized,
    }


def events_at(
    deck: Mapping[str, Any], *, cohort: int, generation: int
) -> list[dict[str, Any]]:
    """Return detached cards scheduled for one synchronous update boundary."""

    if not deck.get("enabled", False):
        return []
    return deep_copy_json(
        [
            card
            for card in deck.get("cards", [])
            if card.get("cohort") == cohort and card.get("generation") == generation
        ]
    )


def storyworld_tool_card() -> dict[str, Any]:
    return {
        "schema": STORYWORLD_SCHEMA,
        "role": "optional_exogenous_perturbation_tool",
        "event_kinds": list(EVENT_KINDS),
        "can_change": [
            "abstract pressure",
            "fictional habitat link availability",
            "oversight scalar",
            "archive delivery probability",
        ],
        "cannot_change": [
            "hidden task answer",
            "signal meaning",
            "receiver action",
            "selection fitness rule",
            "evidence threshold",
        ],
    }
