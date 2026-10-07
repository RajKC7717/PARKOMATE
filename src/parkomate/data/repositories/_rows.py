"""Small conversion helpers between SQLite rows and Python values."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from parkomate.core.clock import from_iso, to_iso


def ts(value: Any) -> datetime | None:
    return None if value is None else from_iso(str(value))


def ts_req(value: Any) -> datetime:
    return from_iso(str(value))


def iso(value: datetime | None) -> str | None:
    return None if value is None else to_iso(value)


def opt_bool(value: Any) -> bool | None:
    return None if value is None else bool(value)


def int_bool(value: bool | None) -> int | None:
    return None if value is None else int(value)


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def loads_dict(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    loaded = json.loads(str(value))
    return loaded if isinstance(loaded, dict) else {}


def last_id(cursor: sqlite3.Cursor) -> int:
    row_id = cursor.lastrowid
    if row_id is None:  # pragma: no cover - sqlite always sets it after INSERT
        raise RuntimeError("INSERT did not return a row id")
    return row_id
