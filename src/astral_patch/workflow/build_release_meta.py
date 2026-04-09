#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta, timezone

from ._common import load_json_dict, repo_path, sort_revision_key


def build_release_body(
    finished_at_kst: str,
    version: str,
    routes: dict,
    route_filter: str,
) -> str:
    lines: list[str] = []
    lines.append('### Release Date')
    lines.append(f'- {finished_at_kst}')
    lines.append('')
    lines.append('### Version')
    lines.append('|route|version|revision|')
    lines.append('|-----|-------|--------|')

    if route_filter:
        route_names = [route_filter]
    else:
        route_names = sorted(str(name) for name in routes.keys())

    for route in route_names:
        route_payload = routes.get(route, {})
        if not isinstance(route_payload, dict):
            continue
        revision = str(route_payload.get('revision', '')).strip()
        if not revision:
            continue
        lines.append(f'|{route}|{version}|{revision}|')

    return '\n'.join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Write release metadata(tag/title/body) to GITHUB_OUTPUT')
    parser.add_argument('--snapshot-file', required=True)
    parser.add_argument('--route', default='')
    parser.add_argument('--tag-suffix', default='')
    parser.add_argument('--github-output', default='')
    args = parser.parse_args(argv)

    snapshot_path = repo_path(args.snapshot_file)
    if not snapshot_path.exists():
        raise SystemExit(f'snapshot file not found: {snapshot_path.as_posix()}')

    payload = load_json_dict(snapshot_path, 'invalid snapshot payload')

    version = str(payload.get('version', '')).strip()
    routes = payload.get('routes', {})
    if not version or not isinstance(routes, dict):
        raise SystemExit('invalid snapshot format')

    route_input = str(args.route).strip()
    revision = ''

    if route_input:
        route_payload = routes.get(route_input)
        if isinstance(route_payload, dict):
            revision = str(route_payload.get('revision', '')).strip()
    else:
        preferred = routes.get('INT_STEAM')
        if isinstance(preferred, dict):
            revision = str(preferred.get('revision', '')).strip()
        if not revision:
            candidates = []
            for route_payload in routes.values():
                if not isinstance(route_payload, dict):
                    continue
                raw = str(route_payload.get('revision', '')).strip()
                if raw:
                    candidates.append(raw)
            if candidates:
                revision = sorted(candidates, key=sort_revision_key)[-1]

    if not revision:
        raise SystemExit('failed to resolve revision from snapshot')

    tag_suffix = str(args.tag_suffix or '').strip()
    tag = f'v{version}.{revision}{tag_suffix}'
    kst = timezone(timedelta(hours=9))
    finished_at_kst = datetime.now(timezone.utc).astimezone(kst).strftime('%Y-%m-%d %H:%M:%S')
    body = build_release_body(
        finished_at_kst=finished_at_kst,
        version=version,
        routes=routes,
        route_filter=route_input,
    )

    output_path = str(args.github_output).strip() or os.environ.get('GITHUB_OUTPUT', '')
    if not output_path:
        raise SystemExit('github output path is required')
    output_path = str(repo_path(output_path))

    with open(output_path, 'a', encoding='utf-8') as fh:
        fh.write(f'tag={tag}\n')
        fh.write(f'title={tag}\n')
        fh.write('body<<EOF\n')
        fh.write(body + '\n')
        fh.write('EOF\n')

    print(f'[release-meta] tag={tag}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
