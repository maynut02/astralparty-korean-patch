from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _path_endswith(path: Path, suffix: Path) -> bool:
    suffix_parts = suffix.parts
    if not suffix_parts:
        return False
    if len(path.parts) < len(suffix_parts):
        return False
    return tuple(path.parts[-len(suffix_parts):]) == suffix_parts


def _replace_path_suffix(path: Path, old_suffix: Path, new_suffix: Path) -> Path:
    if not _path_endswith(path, old_suffix):
        return new_suffix
    prefix_parts = path.parts[:-len(old_suffix.parts)]
    return Path(*prefix_parts) / new_suffix


def resolve_snapshot_file(
    path: Path,
    default_snapshot_file: str,
    legacy_snapshot_file: str | None = None,
) -> Path:
    if path.exists():
        return path

    default_path = Path(default_snapshot_file)
    if legacy_snapshot_file and (path == default_path or _path_endswith(path, default_path)):
        legacy_path = _replace_path_suffix(path, default_path, Path(legacy_snapshot_file))
        if legacy_path.exists():
            return legacy_path

    return path


def load_snapshot_payload(snapshot_file: Path) -> dict[str, Any]:
    if not snapshot_file.exists():
        raise FileNotFoundError(f"Snapshot file not found: {snapshot_file}")

    payload = json.loads(snapshot_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid snapshot JSON: {snapshot_file}")
    return payload


def resolve_route_scope(payload: dict[str, Any], route: str, snapshot_file: Path) -> tuple[str, str]:
    version = str(payload.get("version", "")).strip()
    routes = payload.get("routes", {})
    if not isinstance(routes, dict):
        raise ValueError(f"Invalid snapshot routes in: {snapshot_file}")

    route_info = routes.get(route, {})
    if not isinstance(route_info, dict):
        route_info = {}
    revision = str(route_info.get("revision", "")).strip()

    if not version or not revision:
        raise ValueError(f"Snapshot missing version/revision for route '{route}': {snapshot_file}")

    return version, revision


def find_bundle_name_in_report(
    report_path: Path,
    *,
    asset_type: str,
    asset_name: str,
    not_found_message: str,
) -> str:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid report.json: {report_path}")

    records = payload.get("records", [])
    if not isinstance(records, list):
        raise ValueError("Invalid report.json: records must be a list")

    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("asset_type") == asset_type and record.get("asset_name") == asset_name:
            bundle_name = str(record.get("bundle_name") or "").strip()
            if bundle_name:
                return bundle_name

    raise ValueError(not_found_message)
