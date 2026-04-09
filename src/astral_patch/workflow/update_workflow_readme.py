#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ._common import load_json_dict, repo_path


KST = timezone(timedelta(hours=9))


def load_json(path: Path) -> dict[str, Any]:
    return load_json_dict(path, f'invalid json payload: {path.as_posix()}')


def to_kst_text(value: str, fallback: str = '-') -> str:
    raw = str(value or '').strip()
    if not raw:
        return fallback

    dt: datetime | None = None
    try:
        dt = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        dt = None

    if dt is None:
        return raw

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).strftime('%Y-%m-%d %H:%M:%S')


def report_link(path_text: str) -> str:
    path_value = str(path_text or '').strip()
    if not path_value:
        return '-'
    if not path_value.startswith('/'):
        path_value = '/' + path_value
    return f'[report]({path_value})'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Rewrite workflow branch README summary')
    parser.add_argument('--workflow-root', default='.workflow-data')
    args = parser.parse_args(argv)

    wf_root = repo_path(args.workflow_root)
    readme_path = wf_root / 'README.md'
    state_dir = wf_root / 'state'

    check_path = state_dir / 'get_check.json'
    get_path = state_dir / 'get_report.json'
    last_str_sync_path = state_dir / 'last_str_sync_report.json'
    lang_path = state_dir / 'lang_report.json'
    str_path = state_dir / 'str_report.json'

    check_payload: dict[str, Any] = load_json(check_path) if check_path.exists() else {}
    get_payload: dict[str, Any] = load_json(get_path) if get_path.exists() else {}
    str_snapshot_payload: dict[str, Any]
    if last_str_sync_path.exists():
        str_snapshot_payload = load_json(last_str_sync_path)
    else:
        str_snapshot_payload = get_payload

    lang_payload: dict[str, Any] = load_json(lang_path) if lang_path.exists() else {}
    str_payload: dict[str, Any] = load_json(str_path) if str_path.exists() else {}

    check_finished = to_kst_text(check_payload.get('checked_at', ''))
    check_result = 'changed' if bool(check_payload.get('has_changes', False)) else 'unchanged'
    last_str_sync_date = to_kst_text(str_snapshot_payload.get('generated_at', ''))
    str_sync_routes = str_snapshot_payload.get('routes', {})
    str_sync_version = str(str_snapshot_payload.get('version', '')).strip()

    lines: list[str] = []

    lines.append('## Latest Data Check')
    lines.append('### Finished at')
    lines.append(f'- {check_finished}')
    lines.append('### Result')
    lines.append(f'- {check_result}')
    lines.append('')

    lines.append('## Latest Data Sync')
    lines.append('### Date')
    lines.append(f'- {last_str_sync_date}')
    lines.append('')

    lines.append('### Version')
    lines.append('|route|version|revision|report|')
    lines.append('|-----|-------|--------|------|')

    if isinstance(str_sync_routes, dict) and str_sync_routes:
        for route in sorted(str_sync_routes.keys()):
            item = str_sync_routes.get(route, {})
            if not isinstance(item, dict):
                continue
            version = str_sync_version or str(item.get('version', '')).strip() or '-'
            revision = str(item.get('revision', '')).strip() or '-'
            report = report_link(str(item.get('report_path', '')).strip())
            lines.append(f'|{route}|{version}|{revision}|{report}|')
    else:
        lines.append('|-|-|-|-|')

    lines.append('')
    lines.append('### Data Sync')
    lines.append('|type|batch_id|report|')
    lines.append('|----|--------|------|')

    lang_batch = '-'
    if isinstance(lang_payload, dict):
        db_apply = lang_payload.get('db_apply', {})
        if isinstance(db_apply, dict):
            lang_batch = str(db_apply.get('batch_id', '')).strip() or '-'

    str_batch = '-'
    if isinstance(str_payload, dict):
        db_apply = str_payload.get('db_apply', {})
        if isinstance(db_apply, dict):
            str_batch = str(db_apply.get('batch_id', '')).strip() or '-'

    lines.append(f'|Lang|{lang_batch}|{report_link("state/lang_report.json")}|')
    lines.append(f'|STR|{str_batch}|{report_link("state/str_report.json")}|')

    readme_path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')
    print(f'[readme] updated: {readme_path.as_posix()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
