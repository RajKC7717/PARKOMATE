"""Devices (one row per physical board that entered the line)."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from parkomate.core.clock import Clock
from parkomate.core.enums import CheckCode, DeviceStatus, IdEntryMethod, Stage
from parkomate.core.errors import NotFoundError
from parkomate.core.models import Device
from parkomate.data.db import Database
from parkomate.data.repositories._rows import dumps, iso, last_id, loads_dict, ts, ts_req

_COLUMNS = (
    "id, session_id, device_id, mac_address, firmware_version, started_at, finished_at, status, "
    "reject_stage, reject_check_code, reject_reason, reject_reason_key, reject_reason_params, "
    "programming_attempts, id_entry_method"
)


def _to_model(row: sqlite3.Row) -> Device:
    return Device(
        id=row["id"],
        session_id=row["session_id"],
        device_id=row["device_id"],
        mac_address=row["mac_address"],
        firmware_version=row["firmware_version"],
        started_at=ts_req(row["started_at"]),
        finished_at=ts(row["finished_at"]),
        status=DeviceStatus(row["status"]),
        reject_stage=Stage(row["reject_stage"]) if row["reject_stage"] else None,
        reject_check_code=CheckCode(row["reject_check_code"]) if row["reject_check_code"] else None,
        reject_reason=row["reject_reason"],
        reject_reason_key=row["reject_reason_key"],
        reject_reason_params=loads_dict(row["reject_reason_params"]),
        programming_attempts=row["programming_attempts"],
        id_entry_method=IdEntryMethod(row["id_entry_method"]) if row["id_entry_method"] else None,
    )


class DeviceRepo:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def create(
        self, session_id: int, mac_address: str, firmware_version: str | None = None
    ) -> Device:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO devices (session_id, mac_address, firmware_version, started_at)"
                " VALUES (?, ?, ?, ?)",
                (session_id, mac_address, firmware_version, iso(self._clock.now())),
            )
            return self.require(last_id(cursor))

    def get(self, device_row_id: int) -> Device | None:
        row = self._db.query_one(f"SELECT {_COLUMNS} FROM devices WHERE id = ?", (device_row_id,))
        return None if row is None else _to_model(row)

    def require(self, device_row_id: int) -> Device:
        device = self.get(device_row_id)
        if device is None:
            raise NotFoundError(f"device row {device_row_id} not found")
        return device

    def list_for_session(self, session_id: int) -> list[Device]:
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM devices WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        return [_to_model(row) for row in rows]

    def list_for_sessions(self, session_ids: Sequence[int]) -> list[Device]:
        if not session_ids:
            return []
        marks = ",".join("?" for _ in session_ids)
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM devices WHERE session_id IN ({marks}) ORDER BY session_id, id",
            tuple(session_ids),
        )
        return [_to_model(row) for row in rows]

    def active_for_session(self, session_id: int) -> Device | None:
        row = self._db.query_one(
            f"SELECT {_COLUMNS} FROM devices WHERE session_id = ? AND status = 'in_progress'",
            (session_id,),
        )
        return None if row is None else _to_model(row)

    def search(self, text: str, limit: int = 100) -> list[Device]:
        """Devices whose QR ID or MAC contains ``text`` (case-insensitive), newest first."""
        pattern = f"%{text.strip()}%"
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM devices"
            " WHERE device_id LIKE ? OR mac_address LIKE ? ORDER BY id DESC LIMIT ?",
            (pattern, pattern, limit),
        )
        return [_to_model(row) for row in rows]

    def set_device_id(self, device_row_id: int, device_id: str, method: IdEntryMethod) -> None:
        self._update(device_row_id, "device_id = ?, id_entry_method = ?", (device_id, method.value))

    def set_firmware_version(self, device_row_id: int, version: str) -> None:
        self._update(device_row_id, "firmware_version = ?", (version,))

    def increment_programming_attempts(self, device_row_id: int) -> None:
        self._update(device_row_id, "programming_attempts = programming_attempts + 1", ())

    def finish(self, device_row_id: int, status: DeviceStatus, finished_at: datetime) -> None:
        """Set a terminal non-reject status (complete / abandoned)."""
        if status not in (DeviceStatus.COMPLETE, DeviceStatus.ABANDONED):
            raise ValueError(f"use reject() for status {status}")
        self._update(
            device_row_id,
            "status = ?, finished_at = ?",
            (status.value, iso(finished_at)),
            only_in_progress=True,
        )

    def reject(
        self,
        device_row_id: int,
        *,
        stage: Stage,
        check_code: CheckCode,
        reason: str,
        reason_key: str,
        reason_params: dict[str, Any],
        finished_at: datetime,
    ) -> None:
        self._update(
            device_row_id,
            "status = 'rejected', finished_at = ?, reject_stage = ?, reject_check_code = ?,"
            " reject_reason = ?, reject_reason_key = ?, reject_reason_params = ?",
            (
                iso(finished_at),
                stage.value,
                check_code.value,
                reason,
                reason_key,
                dumps(reason_params),
            ),
            only_in_progress=True,
        )

    def abandon_in_session(self, session_id: int, finished_at: datetime) -> list[int]:
        """Mark every in-progress device of the session abandoned; returns their row ids."""
        with self._db.transaction() as conn:
            rows = conn.execute(
                "SELECT id FROM devices WHERE session_id = ? AND status = 'in_progress'",
                (session_id,),
            ).fetchall()
            ids = [int(row["id"]) for row in rows]
            conn.execute(
                "UPDATE devices SET status = 'abandoned', finished_at = ?"
                " WHERE session_id = ? AND status = 'in_progress'",
                (iso(finished_at), session_id),
            )
        return ids

    def _update(
        self,
        device_row_id: int,
        assignments: str,
        params: tuple[object, ...],
        *,
        only_in_progress: bool = False,
    ) -> None:
        guard = " AND status = 'in_progress'" if only_in_progress else ""
        with self._db.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE devices SET {assignments} WHERE id = ?{guard}",
                (*params, device_row_id),
            )
            if cursor.rowcount != 1:
                raise NotFoundError(f"device row {device_row_id} not found or already finished")
