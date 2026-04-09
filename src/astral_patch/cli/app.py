from __future__ import annotations

import argparse
from typing import Callable

from . import assets_get, assets_lang, assets_patch, assets_str


CommandMain = Callable[[list[str] | None], int]


COMMANDS: dict[str, tuple[str, CommandMain]] = {
    "get": ("Download, inspect, and snapshot target assets.", assets_get.main),
    "lang": ("Sync language TextAsset data into the database.", assets_lang.main),
    "patch": ("Patch bundles and build output_patch inputs.", assets_patch.main),
    "str": ("Sync STR protobuf data into the database.", assets_str.main),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astral-patch",
        description="Unified CLI for Astral Party Korean patch automation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, (help_text, _) in COMMANDS.items():
        subparsers.add_parser(name, help=help_text)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args, remaining = parser.parse_known_args(argv)
    _, command_main = COMMANDS[args.command]
    return command_main(remaining)


if __name__ == "__main__":
    raise SystemExit(main())
