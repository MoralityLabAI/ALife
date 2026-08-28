"""Command-line runner for fresh reconstructed worlds and exact retained replay."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .analysis import derive_episode_analysis
from .archive import load_retained_record
from .environment import run_world
from .types import condition_registry, default_config
from .verifiers import verify_episode
from .versions import run_versioned_world


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--version", choices=("V2", "V3", "V6", "V7", "V8", "V9"), default="V2")
    parser.add_argument("--condition", help="V2/V3 condition id or versioned experiment cell")
    parser.add_argument(
        "--retained-replay",
        action="store_true",
        help="load an exact retained record instead of running the reconstruction",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.retained_replay:
        result = load_retained_record(
            args.version,
            args.seed,
            condition_id=args.condition,
        )
    elif args.version in {"V6", "V7", "V8", "V9"}:
        result = run_versioned_world(args.version, args.seed, args.condition)
    else:
        condition_id = args.condition or "F10"
        episode = run_world(default_config(), condition_registry()[condition_id], args.seed)
        result = {
            "analysis": derive_episode_analysis(episode),
            "episode": episode,
            "schema": "alife.stegohive.reconstructed_record.v1",
            "verifier": verify_episode(episode),
        }
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
