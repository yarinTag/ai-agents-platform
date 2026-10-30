"""Shared SQLite JSON-column decoding with legacy failure semantics."""
import json
from typing import Any, Dict


def decode_json_columns(row, *columns: str) -> Dict[str, Any]:
    """Copy a row and decode truthy JSON cells; retain null/invalid values.

    Several persisted interfaces intentionally expose malformed legacy content
    unchanged. This helper must not normalize invalid JSON to an empty value.
    """
    values = dict(row)
    for column in columns:
        if values.get(column):
            try:
                values[column] = json.loads(values[column])
            except Exception:
                pass
    return values
