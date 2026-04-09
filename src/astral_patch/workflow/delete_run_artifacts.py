#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from typing import Any


def api_request(method: str, url: str, token: str) -> tuple[int, Any]:
    req = urllib.request.Request(
        url,
        method=method,
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'astralparty-korean-patch-actions',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = int(resp.getcode())
            body = resp.read().decode('utf-8', errors='replace')
            if body.strip():
                return status, json.loads(body)
            return status, None
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace') if e.fp else ''
        if body.strip():
            try:
                return int(e.code), json.loads(body)
            except Exception:
                return int(e.code), body
        return int(e.code), None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Delete all artifacts for a GitHub Actions run')
    parser.add_argument('--repo', required=True, help='owner/repo')
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--token', default='')
    args = parser.parse_args(argv)

    token = str(args.token).strip() or os.environ.get('GITHUB_TOKEN', '').strip()
    if not token:
        raise SystemExit('missing token (use --token or GITHUB_TOKEN)')

    repo = str(args.repo).strip()
    run_id = str(args.run_id).strip()
    if '/' not in repo:
        raise SystemExit('invalid repo format, expected owner/repo')

    artifacts: list[dict[str, Any]] = []
    page = 1
    while True:
        list_url = f'https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100&page={page}'
        status, payload = api_request('GET', list_url, token)
        if status != 200:
            raise SystemExit(f'failed to list artifacts: status={status} payload={payload}')

        items = payload.get('artifacts', []) if isinstance(payload, dict) else []
        if not isinstance(items, list) or not items:
            break
        for item in items:
            if isinstance(item, dict):
                artifacts.append(item)
        if len(items) < 100:
            break
        page += 1

    if not artifacts:
        print('[artifact-cleanup] no artifacts found for this run')
        return 0

    deleted = 0
    skipped = 0
    for item in artifacts:
        artifact_id = item.get('id')
        name = str(item.get('name', ''))
        if not artifact_id:
            skipped += 1
            continue

        delete_url = f'https://api.github.com/repos/{repo}/actions/artifacts/{artifact_id}'
        status, payload = api_request('DELETE', delete_url, token)
        if status in (204, 404):
            deleted += 1
            print(f'[artifact-cleanup] deleted name={name} id={artifact_id} status={status}')
        else:
            skipped += 1
            print(f'[artifact-cleanup] failed name={name} id={artifact_id} status={status} payload={payload}')

    print(f'[artifact-cleanup] total={len(artifacts)} deleted={deleted} skipped={skipped}')
    if skipped:
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
