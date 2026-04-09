#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._common import load_json_dict, optional_repo_path, repo_path, to_int


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def load_snapshot(path: Path) -> dict[str, Any]:
    return load_json_dict(path, f'invalid snapshot json: {path.as_posix()}')


def merge_route_payload(current: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current)

    cur_revision = str(merged.get('revision', '')).strip()
    in_revision = str(incoming.get('revision', '')).strip()
    if in_revision:
        merged['revision'] = in_revision if not cur_revision or cur_revision != in_revision else cur_revision

    cur_report_path = str(merged.get('report_path', '')).strip()
    in_report_path = str(incoming.get('report_path', '')).strip()
    if in_report_path:
        merged['report_path'] = in_report_path
    elif cur_report_path:
        merged['report_path'] = cur_report_path

    merged['failed_count'] = to_int(merged.get('failed_count', 0)) + to_int(incoming.get('failed_count', 0))

    cur_error = str(merged.get('error', '')).strip()
    in_error = str(incoming.get('error', '')).strip()
    if in_error:
        merged['error'] = in_error
    elif cur_error:
        merged['error'] = cur_error

    return merged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Merge shard-level get_report snapshots into one state/get_report.json')
    parser.add_argument('--input-dir', required=True, help='Directory containing get_report.<ROUTE>.<SHARD>.json files')
    parser.add_argument('--output-file', required=True, help='Merged output file path')
    parser.add_argument('--version', default='', help='Optional forced version value')
    parser.add_argument('--base-file', default='', help='Optional existing state/get_report.json to preserve unchanged routes')
    args = parser.parse_args(argv)

    input_dir = repo_path(args.input_dir)
    if not input_dir.exists():
        raise SystemExit(f'input dir not found: {input_dir.as_posix()}')

    files = sorted(input_dir.glob('get_report.*.json'))

    merged_routes: dict[str, dict[str, Any]] = {}
    detected_version = ''

    base_file = optional_repo_path(args.base_file)
    if base_file and base_file.exists():
        base_payload = load_snapshot(base_file)
        detected_version = str(base_payload.get('version', '')).strip()
        base_routes = base_payload.get('routes', {})
        if isinstance(base_routes, dict):
            for route, route_payload in base_routes.items():
                if isinstance(route, str) and isinstance(route_payload, dict):
                    merged_routes[route] = dict(route_payload)

    if not files and not merged_routes:
        raise SystemExit(f'no get_report.*.json files found in: {input_dir.as_posix()}')

    for file_path in files:
        payload = load_snapshot(file_path)
        version = str(payload.get('version', '')).strip()
        if version and not detected_version:
            detected_version = version

        routes = payload.get('routes', {})
        if not isinstance(routes, dict):
            continue

        for route, route_payload in routes.items():
            if not isinstance(route, str) or not isinstance(route_payload, dict):
                continue
            if route not in merged_routes:
                merged_routes[route] = dict(route_payload)
            else:
                merged_routes[route] = merge_route_payload(merged_routes[route], route_payload)

    final_version = (args.version or detected_version).strip()
    if not final_version:
        raise SystemExit('unable to determine version from inputs')

    if not merged_routes:
        raise SystemExit('no route payloads found while merging snapshots')

    for route, payload in merged_routes.items():
        revision = str(payload.get('revision', '')).strip()
        if revision:
            payload['report_path'] = f'output_get/{route}/{final_version}/{revision}/report.json'

    output_payload = {
        'generated_at': utc_now_iso(),
        'version': final_version,
        'routes': {k: merged_routes[k] for k in sorted(merged_routes.keys())},
    }

    output_file = repo_path(args.output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(output_payload, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"[merge-snapshot] merged_files={len(files)} routes={len(merged_routes)} -> {output_file.as_posix()}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
