"""Counter events. Counters are computed from these rows, never stored as numbers."""

from __future__ import annotations

import sqlite3

from parkomate.core.clock import Clock
from parkomate.core.enums import CounterEvent
from parkomate.core.models import CounterEventRecord
from parkomate.data.db import Database
from parkomate.data.repositories._rows import iso, last_id, ts_req

_COLUMNS = "id, session_id, device_row_id, event, operator_id, created_at"


def _to_model(row: sqlite3.Row) -> CounterEventRecord:
    return CounterEventRecord(
        id=row["id"],
        session_id=row["session_id"],
        device_row_id=row["device_row_id"],
        event=CounterEvent(row["event"]),
        operator_id=row["operator_id"],
        created_at=ts_req(row["created_at"]),
    )


class CounterRepo:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def add(
        self,
        session_id: int,
        event: CounterEvent,
        operator_id: int,
        device_row_id: int | None = None,
    ) -> CounterEventRecord:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO counter_events (session_id, device_row_id, event, operator_id,"
                " created_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, device_row_id, event.value, operator_id, iso(self._clock.now())),
            )
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM counter_events WHERE id = ?",
                (last_id(cursor),),
            ).fetchone()
        return _to_model(row)

    def list_for_session(self, session_id: int) -> list[CounterEventRecord]:
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM counter_events WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        return [_to_model(row) for row in rows]

    def list_for_device(self, device_row_id: int) -> list[CounterEventRecord]:
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM counter_events WHERE device_row_id = ? ORDER BY id",
            (device_row_id,),
        )
        return [_to_model(row) for row in rows]

    def last_reset(self, session_id: int) -> CounterEventRecord | None:
        row = self._db.query_one(
            f"SELECT {_COLUMNS} FROM counter_events"
            " WHERE session_id = ? AND event = 'reset' ORDER BY id DESC LIMIT 1",
            (session_id,),
        )
        return None if row is None else _to_model(row)

    def totals(self, session_id: int, *, after_id: int = 0) -> dict[CounterEvent, int]:
        """Count of each event type in the session with ``id > after_id``."""
        rows = self._db.query(
            "SELECT event, COUNT(*) AS n FROM counter_events"
            " WHERE session_id = ? AND id > ? GROUP BY event",
            (session_id, after_id),
        )
        totals = dict.fromkeys(CounterEvent, 0)
        for row in rows:
            totals[CounterEvent(row["event"])] = int(row["n"])
        return totals
