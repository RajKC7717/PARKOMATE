"""Append-only audit log (who did what, when)."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any

from parkomate.core.clock import Clock
from parkomate.core.models import AuditEntry
from parkomate.data.db import Database
from parkomate.data.repositories._rows import dumps, iso, last_id, loads_dict, ts_req


def _to_model(row: sqlite3.Row) -> AuditEntry:
    return AuditEntry(
        id=row["id"],
        operator_id=row["operator_id"],
        action=row["action"],
        details=loads_dict(row["details_json"]),
        created_at=ts_req(row["created_at"]),
    )


class AuditRepo:
    """Implements :class:`parkomate.config.manager.AuditSink`."""

    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def record(
        self, operator_id: int | None, action: str, details: Mapping[str, Any] | None = None
    ) -> AuditEntry:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO audit_log (operator_id, action, details_json, created_at)"
                " VALUES (?, ?, ?, ?)",
                (operator_id, action, dumps(dict(details or {})), iso(self._clock.now())),
            )
            row = conn.execute(
                "SELECT * FROM audit_log WHERE id = ?", (last_id(cursor),)
            ).fetchone()
        return _to_model(row)

    def list_entries(self, *, action: str | None = None, limit: int = 200) -> list[AuditEntry]:
        if action is None:
            rows = self._db.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))
        else:
            rows = self._db.query(
                "SELECT * FROM audit_log WHERE action = ? ORDER BY id DESC LIMIT ?",
                (action, limit),
            )
        return [_to_model(row) for row in rows]
