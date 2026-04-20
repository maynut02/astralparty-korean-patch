#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from ._common import optional_repo_path, repo_path
from ..config import HOTADDRESS_ROUTE_PARAM_BY_ROUTE


HOST_BY_PREFIX = {
    'INT_': 'selist.feimogames.com',
    'CN_': 'se-web-cn.feimogames.com',
}
INTERNAL_PREFIX = '{App.WebServerConfig.Path}/'


def resolve_hotaddress_route_param(route: str) -> str:
    return HOTADDRESS_ROUTE_PARAM_BY_ROUTE.get(route, route)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={'User-Agent': 'astral-assets-gha/0.1'})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode('utf-8'))
    if not isinstance(payload, dict):
        raise RuntimeError(f'invalid json payload: {url}')
    return payload


def resolve_host(route: str) -> str:
    for prefix, host in HOST_BY_PREFIX.items():
        if route.startswith(prefix):
            return host
    raise RuntimeError(f'unsupported route prefix: {route}')


def load_previous_snapshot(path_value: str) -> dict[str, Any]:
    path_str = str(path_value or '').strip()
    if not path_str:
        return {}

    path = Path(path_str)
    if not path.exists():
        return {}

    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        return {}
    return payload


def get_previous_route_revision(payload: dict[str, Any], route: str) -> tuple[str, str]:
    version = str(payload.get('version', '')).strip()
    routes = payload.get('routes', {})
    if not isinstance(routes, dict):
        return version, ''
    route_payload = routes.get(route, {})
    if not isinstance(route_payload, dict):
        return version, ''
    revision = str(route_payload.get('revision', '')).strip()
    return version, revision


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build route/shard matrix for assets-get workflow job')
    parser.add_argument('--version', required=True)
    parser.add_argument('--routes', required=True, help='Comma-separated route list')
    parser.add_argument('--per-shard', type=int, default=500)
    parser.add_argument('--max-shards', type=int, default=20)
    parser.add_argument('--previous-snapshot', default='', help='Previous state/get_report.json path')
    parser.add_argument('--check-output', default='', help='Path to write current check result json')
    parser.add_argument('--github-output', default='', help='Path to $GITHUB_OUTPUT')
    args = parser.parse_args(argv)

    version = str(args.version).strip()
    routes = [item.strip() for item in str(args.routes).split(',') if item.strip()]
    per_shard = max(1, int(args.per_shard))
    max_shards = max(1, int(args.max_shards))
    if not routes:
        raise SystemExit('no routes provided')

    previous_snapshot_path = optional_repo_path(args.previous_snapshot)
    previous_snapshot = load_previous_snapshot(previous_snapshot_path.as_posix() if previous_snapshot_path else '')

    include: list[dict[str, Any]] = []
    route_meta: dict[str, dict[str, Any]] = {}
    has_changes = False
    int_steam_changed = False

    for route in routes:
        host = resolve_host(route)
        route_param = resolve_hotaddress_route_param(route)
        get_url = (
            f'http://{host}:7878/api/hotaddress/get'
            f'?route={urllib.parse.quote(route_param)}&version={urllib.parse.quote(version)}'
        )
        get_payload = fetch_json(get_url)
        source_url = str(get_payload.get('sourceUrl', '')).rstrip('/')
        if not source_url:
            raise RuntimeError(f'missing sourceUrl for route={route}')
        source_revision = source_url.split('/')[-1].strip()
        if not source_revision:
            raise RuntimeError(f'unable to parse revision from sourceUrl for route={route}: {source_url}')

        prev_version, prev_revision = get_previous_route_revision(previous_snapshot, route)
        changed = not (prev_version == version and prev_revision == source_revision)

        if changed:
            has_changes = True
            if route == 'INT_STEAM':
                int_steam_changed = True

            catalog_url = f'{source_url}/catalog_{version}.json'
            catalog_payload = fetch_json(catalog_url)

            bundles = set()
            for raw in catalog_payload.get('m_InternalIds', []):
                if not isinstance(raw, str):
                    continue
                normalized = raw.replace('\\', '/').strip()
                if not normalized.startswith(INTERNAL_PREFIX):
                    continue
                suffix = normalized[len(INTERNAL_PREFIX):].strip('/')
                if suffix:
                    bundles.add(suffix)

            bundle_count = len(bundles)
            shard_count = min(max_shards, max(1, math.ceil(bundle_count / per_shard)))

            for shard_index in range(shard_count):
                include.append(
                    {
                        'route': route,
                        'shard_index': shard_index,
                        'shard_no': shard_index + 1,
                        'shard_count': shard_count,
                    }
                )
        else:
            bundle_count = 0
            shard_count = 0

        route_meta[route] = {
            'bundle_count': bundle_count,
            'shard_count': shard_count,
            'changed': changed,
            'version': version,
            'revision': source_revision,
            'report_path': f'output_get/{route}/{version}/{source_revision}/report.json',
        }

        print(
            f'[plan] route={route} revision={source_revision} changed={changed} '
            f'bundles={bundle_count} shard_count={shard_count}'
        )

    matrix = {'include': include}
    print(f'[plan] total_jobs={len(include)} per_shard={per_shard} max_shards={max_shards}')

    output_path = str(args.github_output).strip() or os.environ.get('GITHUB_OUTPUT', '')
    if not output_path:
        raise SystemExit('github output path is required')

    with open(output_path, 'a', encoding='utf-8') as f:
        f.write(f"matrix={json.dumps(matrix, separators=(',', ':'))}\n")
        f.write(f'version={version}\n')
        f.write(f"route_meta={json.dumps(route_meta, separators=(',', ':'))}\n")
        f.write(f"has_changes={'true' if has_changes else 'false'}\n")
        f.write(f"int_steam_changed={'true' if int_steam_changed else 'false'}\n")

    check_output = str(args.check_output).strip()
    if check_output:
        check_payload = {
            'checked_at': utc_now_iso(),
            'version': version,
            'routes': route_meta,
            'has_changes': has_changes,
            'int_steam_changed': int_steam_changed,
        }
        check_path = repo_path(check_output)
        check_path.parent.mkdir(parents=True, exist_ok=True)
        check_path.write_text(json.dumps(check_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'[plan] check output -> {check_path.as_posix()}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
