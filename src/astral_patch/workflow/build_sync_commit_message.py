#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from ._common import load_json_dict, repo_path, sort_revision_key


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build commit message for workflow branch sync commit')
    parser.add_argument('--snapshot-file', default='state/get_report.json')
    args = parser.parse_args(argv)

    snapshot = repo_path(args.snapshot_file)
    version = 'unknown'
    revision = 'unknown'

    if snapshot.exists():
        payload = load_json_dict(snapshot, 'invalid snapshot payload')
        version = str(payload.get('version', '')).strip() or version
        routes = payload.get('routes', {})
        if isinstance(routes, dict):
            preferred = routes.get('INT_STEAM')
            if isinstance(preferred, dict):
                revision = str(preferred.get('revision', '')).strip() or revision

            if revision == 'unknown':
                candidates = []
                for route_payload in routes.values():
                    if not isinstance(route_payload, dict):
                        continue
                    raw = str(route_payload.get('revision', '')).strip()
                    if raw:
                        candidates.append(raw)
                if candidates:
                    revision = sorted(candidates, key=sort_revision_key)[-1]

    kst = timezone(timedelta(hours=9))
    stamp = datetime.now(timezone.utc).astimezone(kst).strftime('%Y-%m-%d %H:%M:%S')
    print(f'workflow: sync data v{version}.{revision} [{stamp}]')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
