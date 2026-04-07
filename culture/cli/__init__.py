"""Unified CLI entry point for culture.

Commands are organized into noun-based groups:
    culture agent    {create,join,start,stop,status,rename,assign,sleep,wake,learn,message,read,archive,unarchive,delete}
    culture server   {start,stop,status,default,rename,archive,unarchive}
    culture mesh     {overview,setup,update,console}
    culture channel  {list,read,message,who}
    culture bot      {create,start,stop,list,inspect,archive,unarchive}
    culture skills   {install}
"""

from __future__ import annotations

import argparse
import logging
import sys

from culture import __version__
from culture.cli import agent, bot, channel, mesh, server, skills

GROUPS = [agent, server, mesh, channel, bot, skills]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="culture",
        description="culture — AI agent IRC mesh",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")
    for group in GROUPS:
        group.register(sub)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    try:
        for group in GROUPS:
            if args.command == group.NAME:
                group.dispatch(args)
                return
        parser.print_help()
        sys.exit(1)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
