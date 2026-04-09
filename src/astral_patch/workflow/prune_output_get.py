#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ._common import repo_path


def parse_version(value: str) -> tuple[int, ...]:
    parts = []
    for token in value.split('.'):
        token = token.strip()
        if not token:
            parts.append(0)
            continue
        try:
            parts.append(int(token))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def parse_revision(value: str) -> int:
    value = value.strip()
    try:
        return int(value)
    except ValueError:
        return -1


def collect_scopes(route_dir: Path) -> list[tuple[tuple[int, ...], int, float, Path]]:
    scopes: list[tuple[tuple[int, ...], int, float, Path]] = []
    for version_dir in route_dir.iterdir():
        if not version_dir.is_dir():
            continue
        version_key = parse_version(version_dir.name)
        for revision_dir in version_dir.iterdir():
            if not revision_dir.is_dir():
                continue
            report_file = revision_dir / 'report.json'
            if not report_file.exists():
                continue
            revision_key = parse_revision(revision_dir.name)
            mtime_key = report_file.stat().st_mtime
            scopes.append((version_key, revision_key, mtime_key, revision_dir))
    return scopes


def prune_route(route_dir: Path, keep: int) -> list[Path]:
    scopes = collect_scopes(route_dir)
    scopes.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)

    removed: list[Path] = []
    for _, _, _, scope_dir in scopes[keep:]:
        shutil.rmtree(scope_dir, ignore_errors=True)
        removed.append(scope_dir)

    # cleanup empty version dirs
    for version_dir in route_dir.iterdir():
        if version_dir.is_dir() and not any(version_dir.iterdir()):
            version_dir.rmdir()

    return removed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Prune output_get history and keep latest N scopes per route.')
    parser.add_argument('output_get_dir', help='Path to output_get root directory')
    parser.add_argument('--keep', type=int, default=5, help='Number of latest scopes to keep per route')
    args = parser.parse_args(argv)

    root = repo_path(args.output_get_dir)
    keep = max(1, int(args.keep))

    if not root.exists():
        print(f'[prune] output_get root not found: {root}')
        return 0

    total_removed = 0
    for route_dir in sorted(root.iterdir()):
        if not route_dir.is_dir():
            continue
        removed = prune_route(route_dir, keep)
        if removed:
            print(f'[prune] route={route_dir.name} removed={len(removed)}')
            for item in removed:
                print(f'  - {item.as_posix()}')
        total_removed += len(removed)

    print(f'[prune] done removed_total={total_removed} keep={keep}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
