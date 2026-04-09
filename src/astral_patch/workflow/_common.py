#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..paths import resolve_repo_path


def load_json_dict(path: Path, invalid_message: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(payload, dict):
        raise ValueError(invalid_message)
    return payload


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def sort_revision_key(value: str) -> tuple[int, int | str]:
    if value.isdigit():
        return (0, int(value))
    return (1, value)


def repo_path(value: str | Path) -> Path:
    return resolve_repo_path(value)


def optional_repo_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return repo_path(raw)
