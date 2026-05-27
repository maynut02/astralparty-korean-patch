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
    tag_suffix: str,
) -> str:
    lines: list[str] = []
    if str(tag_suffix or '').strip() == '-pre':
        lines.append('> [!WARNING]')
        lines.append('> **Pre-release** 버전에서는 일부 번역되지 않은 요소가 존재할 수 있습니다.')
        lines.append('')
    lines.append('### Release Date')
    lines.append(f'- {finished_at_kst}')

    import os
    server_url = os.environ.get('GITHUB_SERVER_URL', 'https://github.com')
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    run_id = os.environ.get('GITHUB_RUN_ID', '')
    if repo and run_id:
        run_url = f"{server_url}/{repo}/actions/runs/{run_id}"
        lines.append(f'- [Action Run]({run_url})')

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

    # Identify updated routes to add "[업데이트]" tag
    updated_routes = {route_input} if route_input else set()
    if not updated_routes:
        check_path = repo_path('state/get_check.json')
        if check_path.exists():
            try:
                check_payload = load_json_dict(check_path, '')
                routes_payload = check_payload.get('routes', {})
                if isinstance(routes_payload, dict):
                    for r_name, r_info in routes_payload.items():
                        if isinstance(r_info, dict) and r_info.get('changed'):
                            updated_routes.add(r_name)
            except Exception:
                pass

    # Build Discord summary of route versions
    ROUTE_DISPLAY_NAMES = {
        'INT_STEAM': 'Steam 글로벌 버전',
        'CN_STEAM': 'Steam 중국 버전',
        'INT_ANDROID': 'Android 일본 버전',
        'CN_BILIBILI': '빌리빌리 PC 버전',
    }

    summary_lines = []
    ordered_routes = ['INT_STEAM', 'CN_STEAM', 'INT_ANDROID', 'CN_BILIBILI']
    for r_name in sorted(routes.keys()):
        if r_name not in ordered_routes:
            ordered_routes.append(r_name)

    for r_name in ordered_routes:
        route_payload = routes.get(r_name)
        if not isinstance(route_payload, dict):
            continue
        r_rev = str(route_payload.get('revision', '')).strip()
        if not r_rev:
            continue
        r_ver = str(route_payload.get('version', '')).strip() or version
        r_display = ROUTE_DISPLAY_NAMES.get(r_name, r_name)
        r_full_version = f"v{r_ver}.{r_rev}{tag_suffix}"
        update_flag = " [업데이트]" if r_name in updated_routes else ""
        summary_lines.append(f"{r_display} - {r_full_version}{update_flag}")

    routes_summary = '\n'.join(summary_lines)
    tag = f'v{version}.{revision}{tag_suffix}'
    kst = timezone(timedelta(hours=9))
    finished_at_kst = datetime.now(timezone.utc).astimezone(kst).strftime('%Y-%m-%d %H:%M:%S')
    body = build_release_body(
        finished_at_kst=finished_at_kst,
        version=version,
        routes=routes,
        route_filter=route_input,
        tag_suffix=tag_suffix,
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
        fh.write('routes_summary<<EOF\n')
        fh.write(routes_summary + '\n')
        fh.write('EOF\n')

    print(f'[release-meta] tag={tag}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
