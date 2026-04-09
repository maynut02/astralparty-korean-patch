#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ._common import load_json_dict, repo_path, to_int


SUM_FIELDS = (
    'processed_bundle_count',
    'downloaded_bundle_count',
    'exported_bundle_count',
    'matched_asset_count',
    'skipped_bundle_count',
    'copied_reported_bundle_count',
)


def load_report(path: Path) -> dict[str, Any]:
    return load_json_dict(path, f'invalid report json: {path.as_posix()}')


def merge_summary(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)

    # keep stable identity fields from base; fill if missing
    for key in ('route', 'version', 'source_revision', 'run_at', 'source_url', 'report_path'):
        if not str(merged.get(key, '')).strip() and str(incoming.get(key, '')).strip():
            merged[key] = incoming[key]

    # non-sharded totals should stay route-global, pick max observed
    merged['current_bundle_count'] = max(to_int(merged.get('current_bundle_count', 0)), to_int(incoming.get('current_bundle_count', 0)))
    merged['added_bundle_count'] = max(to_int(merged.get('added_bundle_count', 0)), to_int(incoming.get('added_bundle_count', 0)))

    # sharded counters should be summed
    for field in SUM_FIELDS:
        merged[field] = to_int(merged.get(field, 0)) + to_int(incoming.get(field, 0))

    merged['interrupted'] = bool(merged.get('interrupted', False)) or bool(incoming.get('interrupted', False))
    merged['catalog_diff_enabled'] = False

    # merge list fields
    for field in ('failed_bundles', 'warnings', 'bundle_copy_errors'):
        merged_list = merged.get(field, [])
        incoming_list = incoming.get(field, [])
        if not isinstance(merged_list, list):
            merged_list = []
        if not isinstance(incoming_list, list):
            incoming_list = []
        merged[field] = merged_list + incoming_list

    return merged


def merge_reports_for_group(report_files: list[Path]) -> dict[str, Any]:
    merged_summary: dict[str, Any] | None = None
    merged_records: list[dict[str, Any]] = []

    for report_file in sorted(report_files):
        payload = load_report(report_file)
        summary = payload.get('summary', {})
        records = payload.get('records', [])
        if not isinstance(summary, dict):
            continue

        if merged_summary is None:
            merged_summary = dict(summary)
            # reset summed fields from first shard to avoid double counting later
            for field in SUM_FIELDS:
                merged_summary[field] = to_int(summary.get(field, 0))
            merged_summary['current_bundle_count'] = to_int(summary.get('current_bundle_count', 0))
            merged_summary['added_bundle_count'] = to_int(summary.get('added_bundle_count', 0))
            if not isinstance(merged_summary.get('failed_bundles'), list):
                merged_summary['failed_bundles'] = []
            if not isinstance(merged_summary.get('warnings'), list):
                merged_summary['warnings'] = []
            if not isinstance(merged_summary.get('bundle_copy_errors'), list):
                merged_summary['bundle_copy_errors'] = []
        else:
            merged_summary = merge_summary(merged_summary, summary)

        if isinstance(records, list):
            merged_records.extend(item for item in records if isinstance(item, dict))

    if merged_summary is None:
        raise ValueError('no valid reports to merge')

    return {'summary': merged_summary, 'records': merged_records}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Merge shard report files into route-level report.json')
    parser.add_argument('--reports-dir', required=True, help='Directory containing report.<ROUTE>.<SHARD>.json files')
    parser.add_argument('--output-root', default='output_get', help='output_get root path')
    args = parser.parse_args(argv)

    reports_dir = repo_path(args.reports_dir)
    if not reports_dir.exists():
        raise SystemExit(f'reports dir not found: {reports_dir.as_posix()}')

    report_files = sorted(reports_dir.glob('report.*.json'))
    if not report_files:
        print('[merge-report] no shard report files found; skip')
        return 0

    groups: dict[tuple[str, str, str], list[Path]] = {}

    for report_file in report_files:
        payload = load_report(report_file)
        summary = payload.get('summary', {})
        if not isinstance(summary, dict):
            continue
        route = str(summary.get('route', '')).strip()
        version = str(summary.get('version', '')).strip()
        revision = str(summary.get('source_revision', '')).strip()
        if not route or not version or not revision:
            continue
        groups.setdefault((route, version, revision), []).append(report_file)

    if not groups:
        print('[merge-report] no mergeable report groups found; skip')
        return 0

    output_root = repo_path(args.output_root)
    merged_count = 0

    for (route, version, revision), files in sorted(groups.items()):
        merged_payload = merge_reports_for_group(files)
        out_path = output_root / route / version / revision / 'report.json'
        out_path.parent.mkdir(parents=True, exist_ok=True)

        merged_payload['summary']['route'] = route
        merged_payload['summary']['version'] = version
        merged_payload['summary']['source_revision'] = revision
        merged_payload['summary']['report_path'] = out_path.as_posix()

        out_path.write_text(json.dumps(merged_payload, ensure_ascii=False, indent=2), encoding='utf-8')
        merged_count += 1
        print(f'[merge-report] route={route} revision={revision} shards={len(files)} -> {out_path.as_posix()}')

    print(f'[merge-report] done merged={merged_count}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
