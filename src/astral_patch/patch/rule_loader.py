from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from ..paths import find_repo_root


RULES_PACKAGE = "astral_patch.patch.rules"


def _override_rules_dir() -> Path:
    return find_repo_root() / "rules"


def available_rule_names() -> list[str]:
    names: set[str] = set()

    override_dir = _override_rules_dir()
    if override_dir.exists():
        names.update(path.stem for path in override_dir.glob("*.json"))

    package_root = resources.files(RULES_PACKAGE)
    names.update(item.stem for item in package_root.iterdir() if item.is_file() and item.suffix == ".json")
    return sorted(names)


def load_rule_payload(route: str) -> dict[str, Any]:
    route_name = route.strip().lower()
    if not route_name:
        raise ValueError("Route must be non-empty")

    override_path = _override_rules_dir() / f"{route_name}.json"
    if override_path.exists():
        payload = json.loads(override_path.read_text(encoding="utf-8").lstrip("\ufeff"))
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid rule JSON: {override_path.as_posix()}")
        return payload

    package_root = resources.files(RULES_PACKAGE)
    rule_file = package_root / f"{route_name}.json"
    if not rule_file.is_file():
        raise FileNotFoundError(f"Rule file not found for route: {route}")

    payload = json.loads(rule_file.read_text(encoding="utf-8").lstrip("\ufeff"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid bundled rule JSON: {route_name}.json")
    return payload
