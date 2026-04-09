#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil

from ._common import repo_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Extract route report path from shard snapshot and copy report file')
    parser.add_argument('--snapshot-file', required=True)
    parser.add_argument('--route', required=True)
    parser.add_argument('--output-file', required=True)
    args = parser.parse_args(argv)

    snapshot_file = repo_path(args.snapshot_file)
    if not snapshot_file.exists():
        raise SystemExit(f'snapshot file not found: {snapshot_file.as_posix()}')

    payload = json.loads(snapshot_file.read_text(encoding='utf-8'))
    routes = payload.get('routes', {})
    if not isinstance(routes, dict) or args.route not in routes:
        raise SystemExit(f'route not found in snapshot: {args.route}')

    route_payload = routes[args.route]
    if not isinstance(route_payload, dict):
        raise SystemExit(f'invalid route payload in snapshot: {args.route}')

    report_path = repo_path(str(route_payload.get('report_path', '')).strip())
    if not report_path.exists():
        raise SystemExit(f'report_path missing: {report_path.as_posix()}')

    output_file = repo_path(args.output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(report_path, output_file)
    print(f'[artifact] copied report -> {output_file.as_posix()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
