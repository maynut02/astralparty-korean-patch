#!/usr/bin/env python3
from __future__ import annotations

import argparse

from ._common import repo_path


ALLOWED = {'.git', 'output_get', 'state', 'README.md'}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Validate workflow branch minimal layout')
    parser.add_argument('--workflow-root', default='.workflow-data')
    args = parser.parse_args(argv)

    root = repo_path(args.workflow_root)
    if not root.exists():
        raise SystemExit(f'workflow root not found: {root.as_posix()}')

    names = {p.name for p in root.iterdir()}
    unexpected = sorted(name for name in names if name not in ALLOWED)
    missing = sorted(name for name in ('output_get', 'state', 'README.md') if name not in names)

    if unexpected:
        raise SystemExit(f'unexpected items in workflow root: {unexpected}')
    if missing:
        raise SystemExit(f'missing required items in workflow root: {missing}')

    print('[layout] workflow root layout is valid')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
