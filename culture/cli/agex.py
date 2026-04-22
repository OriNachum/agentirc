"""Stub for `culture agex` — replaced by the real passthrough in Task 5."""

from __future__ import annotations

import argparse
import sys

NAME = "agex"


def register(subparsers: "argparse._SubParsersAction") -> None:
    subparsers.add_parser(NAME, help="Agex passthrough (see Task 5)")


def dispatch(_args: argparse.Namespace) -> None:  # pragma: no cover
    print("agex passthrough not yet implemented", file=sys.stderr)
    sys.exit(1)
