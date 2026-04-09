#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import zipfile
from pathlib import Path

from ._common import load_json_dict, repo_path


def load_snapshot(path: Path) -> dict:
    return load_json_dict(path, f'invalid snapshot payload: {path}')


def resolve_repo_name(explicit_repo_name: str, snapshot_file: Path) -> str:
    explicit_value = str(explicit_repo_name or '').strip()
    if explicit_value:
        return explicit_value

    github_repository = str(os.environ.get('GITHUB_REPOSITORY', '')).strip()
    if github_repository:
        return github_repository.split('/')[-1].strip()

    return snapshot_file.resolve().parents[2].name


def build_zip_for_route(
    repo_name: str,
    route: str,
    version: str,
    revision: str,
    output_root: Path,
    zip_dir: Path,
    file_suffix: str,
) -> Path | None:
    base_dir = output_root / route / version / revision
    source_dirs = [base_dir / 'AssetBundles', base_dir / 'StandaloneWindows64']
    existing = [d for d in source_dirs if d.exists() and d.is_dir()]
    if not existing:
        print(f'[zip] skip route={route}: no AssetBundles/StandaloneWindows64 in {base_dir.as_posix()}')
        return None

    zip_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f'{repo_name}-{route}-v{version}.{revision}{file_suffix}.zip'
    zip_path = zip_dir / zip_name

    file_count = 0
    with zipfile.ZipFile(zip_path, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for source_dir in existing:
            for file_path in source_dir.rglob('*'):
                if not file_path.is_file():
                    continue
                arcname = file_path.relative_to(base_dir).as_posix()
                zf.write(file_path, arcname)
                file_count += 1

    if file_count == 0:
        zip_path.unlink(missing_ok=True)
        print(f'[zip] skip route={route}: no files found under target directories')
        return None

    print(f'[zip] created route={route} files={file_count} -> {zip_path.as_posix()}')
    return zip_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Build release-ready zip files from output_patch data.')
    parser.add_argument('--repo-name', default='', help='Optional repository name used in zip file names')
    parser.add_argument('--snapshot-file', default='state/get_report.json', help='Path to get snapshot json')
    parser.add_argument('--output-root', default='output_patch', help='Path to output_patch root')
    parser.add_argument('--zip-dir', default='release_zips', help='Directory for generated zip files')
    parser.add_argument('--route', default='', help='Optional single route filter')
    parser.add_argument('--file-suffix', default='', help='Optional suffix appended before .zip (e.g. -pre)')
    args = parser.parse_args(argv)

    snapshot_file = repo_path(args.snapshot_file)
    if not snapshot_file.exists():
        raise SystemExit(f'snapshot file not found: {snapshot_file.as_posix()}')
    repo_name = resolve_repo_name(args.repo_name, snapshot_file)

    payload = load_snapshot(snapshot_file)
    version = str(payload.get('version', '')).strip()
    routes_map = payload.get('routes', {})
    if not version or not isinstance(routes_map, dict):
        raise SystemExit(f'invalid snapshot format: {snapshot_file.as_posix()}')

    if args.route:
        target_routes = [args.route]
    else:
        target_routes = sorted(str(k) for k in routes_map.keys())

    output_root = repo_path(args.output_root)
    zip_dir = repo_path(args.zip_dir)

    created: list[Path] = []
    for route in target_routes:
        route_payload = routes_map.get(route)
        if not isinstance(route_payload, dict):
            print(f'[zip] skip route={route}: missing snapshot route payload')
            continue

        revision = str(route_payload.get('revision', '')).strip()
        if not revision:
            print(f'[zip] skip route={route}: empty revision in snapshot')
            continue

        zip_path = build_zip_for_route(
            repo_name=repo_name,
            route=route,
            version=version,
            revision=revision,
            output_root=output_root,
            zip_dir=zip_dir,
            file_suffix=str(args.file_suffix or ''),
        )
        if zip_path is not None:
            created.append(zip_path)

    if not created:
        raise SystemExit('no zip files created')

    print(f'[zip] done created={len(created)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
