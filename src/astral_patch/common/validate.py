from __future__ import annotations

import re


def validate_table_name(table_name: str) -> str:
    candidate = table_name.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", candidate):
        raise ValueError(f"Invalid table name: {table_name}")
    return candidate
