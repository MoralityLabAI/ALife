#!/usr/bin/env python3
"""Verify one adventure task/trace/environment triple or list verifiers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from adventure_verifiers.campaign import verifier_catalog
from adventure_verifiers.verifiers import verify_adventure


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", type=Path, nargs="?")
    parser.add_argument("trace", type=Path, nargs="?")
    parser.add_argument("environment", type=Path, nargs="?")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.list:
        result = verifier_catalog()
    else:
        if not all((args.task, args.trace, args.environment)):
            parser.error("task, trace, and environment are required unless --list is used")
        task = json.loads(args.task.read_text(encoding="utf-8-sig"))
        trace = json.loads(args.trace.read_text(encoding="utf-8-sig"))
        environment = json.loads(args.environment.read_text(encoding="utf-8-sig"))
        result = verify_adventure(task, trace, environment)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if not args.list:
        raise SystemExit(0 if result["accepted"] else 1)


if __name__ == "__main__":
    main()
