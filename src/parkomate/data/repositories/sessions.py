"""Sessions and their ambient temperature readings."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from parkomate.core.clock import Clock
from parkomate.core.enums import AmbientReason, SessionEndReason
from parkomate.core.errors import NotFoundError
from parkomate.core.models import AmbientReading, Session
from parkomate.data.db import Database
from parkomate.data.repositories._rows import iso, last_id, ts, ts_req

_COLUMNS = (
    "id, operator_id, station_id, started_at, ended_at, end_reason, firmware_name, "
    "firmware_version, firmware_sha256, ambient_c_initial, language"
)


def _to_model(row: sqlite3.Row) -> Session:
    return Session(
        id=row["id"],
        operator_id=row["operator_id"],
        station_id=row["station_id"],
        started_at=ts_req(row["started_at"]),
        ended_at=ts(row["ended_at"]),
        end_reason=SessionEndReason(row["end_reason"]) if row["end_reason"] else None,
        firmware_name=row["firmware_name"],
        firmware_version=row["firmware_version"],
        firmware_sha256=row["firmware_sha256"],
        ambient_c_initial=row["ambient_c_initial"],
        language=row["language"],
    )


def _ambient(row: sqlite3.Row) -> AmbientReading:
    return AmbientReading(
        id=row["id"],
        session_id=row["session_id"],
        value_c=row["value_c"],
        measured_at=ts_req(row["measured_at"]),
        reason=AmbientReason(row["reason"]),
    )


class SessionRepo:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def create(self, operator_id: int, station_id: str, language: str) -> Session:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO sessions (operator_id, station_id, started_at, language)"
                " VALUES (?, ?, ?, ?)",
                (operator_id, station_id, iso(self._clock.now()), language),
            )
            return self.require(last_id(cursor))

    def get(self, session_id: int) -> Session | None:
        row = self._db.query_one(f"SELECT {_COLUMNS} FROM sessions WHERE id = ?", (session_id,))
        return None if row is None else _to_model(row)

    def require(self, session_id: int) -> Session:
        session = self.get(session_id)
        if session is None:
            raise NotFoundError(f"session {session_id} not found")
        return session

    def list_sessions(
        self,
        *,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
        operator_id: int | None = None,
        limit: int = 500,
    ) -> list[Session]:
        """Sessions newest first, optionally filtered by start time range / operator."""
        clauses: list[str] = []
        params: list[object] = []
        if started_from is not None:
            clauses.append("started_at >= ?")
            params.append(iso(started_from))
        if started_to is not None:
            clauses.append("started_at < ?")
            params.append(iso(started_to))
        if operator_id is not None:
            clauses.append("operator_id = ?")
            params.append(operator_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM sessions {where} ORDER BY started_at DESC, id DESC LIMIT ?",
            (*params, limit),
        )
        return [_to_model(row) for row in rows]

    def open_sessions(self) -> list[Session]:
        rows = self._db.query(f"SELECT {_COLUMNS} FROM sessions WHERE ended_at IS NULL ORDER BY id")
        return [_to_model(row) for row in rows]

    def close(self, session_id: int, reason: SessionEndReason, ended_at: datetime) -> None:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "UPDATE sessions SET ended_at = ?, end_reason = ?"
                " WHERE id = ? AND ended_at IS NULL",
                (iso(ended_at), reason.value, session_id),
            )
            if cursor.rowcount != 1:
                raise NotFoundError(f"open session {session_id} not found")

    def set_firmware(self, session_id: int, name: str, version: str, sha256: str) -> None:
        with self._db.transaction() as conn:
            conn.execute(
                "UPDATE sessions SET firmware_name = ?, firmware_version = ?, firmware_sha256 = ?"
                " WHERE id = ?",
                (name, version, sha256, session_id),
            )

    def add_ambient(self, session_id: int, value_c: float, reason: AmbientReason) -> AmbientReading:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO ambient_readings (session_id, value_c, measured_at, reason)"
                " VALUES (?, ?, ?, ?)",
                (session_id, value_c, iso(self._clock.now()), reason.value),
            )
            if reason is AmbientReason.SESSION_START:
                conn.execute(
                    "UPDATE sessions SET ambient_c_initial = ?"
                    " WHERE id = ? AND ambient_c_initial IS NULL",
                    (value_c, session_id),
                )
            row = conn.execute(
                "SELECT * FROM ambient_readings WHERE id = ?", (last_id(cursor),)
            ).fetchone()
        return _ambient(row)

    def ambient_readings(self, session_id: int) -> list[AmbientReading]:
        rows = self._db.query(
            "SELECT * FROM ambient_readings WHERE session_id = ? ORDER BY measured_at, id",
            (session_id,),
        )
        return [_ambient(row) for row in rows]

    def latest_ambient(self, session_id: int) -> AmbientReading | None:
        row = self._db.query_one(
            "SELECT * FROM ambient_readings WHERE session_id = ?"
            " ORDER BY measured_at DESC, id DESC LIMIT 1",
            (session_id,),
        )
        return None if row is None else _ambient(row)

    def last_activity(self, session_id: int) -> datetime | None:
        """Latest timestamp written for anything in the session (crash-recovery end time)."""
        value = self._db.scalar(
            """
            SELECT MAX(t) FROM (
                SELECT started_at AS t FROM sessions WHERE id = :s
                UNION ALL SELECT started_at FROM devices WHERE session_id = :s
                UNION ALL SELECT finished_at FROM devices WHERE session_id = :s
                UNION ALL SELECT measured_at FROM ambient_readings WHERE session_id = :s
                UNION ALL SELECT created_at FROM counter_events WHERE session_id = :s
                UNION ALL SELECT c.created_at FROM check_results c
                          JOIN devices d ON d.id = c.device_row_id WHERE d.session_id = :s
            )
            """,
            {"s": session_id},
        )
        return ts(value)
