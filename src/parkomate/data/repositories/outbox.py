"""E-mail outbox (reports waiting to be sent)."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from parkomate.core.clock import Clock
from parkomate.core.enums import OutboxStatus
from parkomate.core.errors import NotFoundError
from parkomate.core.models import OutboxItem
from parkomate.data.db import Database
from parkomate.data.repositories._rows import iso, last_id, ts, ts_req

_COLUMNS = (
    "id, session_id, status, attempts, last_error, payload_path, subject, created_at, sent_at, "
    "next_attempt_at"
)


def _to_model(row: sqlite3.Row) -> OutboxItem:
    return OutboxItem(
        id=row["id"],
        session_id=row["session_id"],
        status=OutboxStatus(row["status"]),
        attempts=row["attempts"],
        last_error=row["last_error"],
        payload_path=row["payload_path"],
        subject=row["subject"],
        created_at=ts_req(row["created_at"]),
        sent_at=ts(row["sent_at"]),
        next_attempt_at=ts(row["next_attempt_at"]),
    )


class OutboxRepo:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def add(self, session_id: int | None, subject: str, payload_path: str | None) -> OutboxItem:
        now = iso(self._clock.now())
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO email_outbox (session_id, status, subject, payload_path, created_at,"
                " next_attempt_at) VALUES (?, 'pending', ?, ?, ?, ?)",
                (session_id, subject, payload_path, now, now),
            )
            return self.require(last_id(cursor))

    def get(self, item_id: int) -> OutboxItem | None:
        row = self._db.query_one(f"SELECT {_COLUMNS} FROM email_outbox WHERE id = ?", (item_id,))
        return None if row is None else _to_model(row)

    def require(self, item_id: int) -> OutboxItem:
        item = self.get(item_id)
        if item is None:
            raise NotFoundError(f"outbox item {item_id} not found")
        return item

    def list_items(
        self, *, status: OutboxStatus | None = None, limit: int = 200
    ) -> list[OutboxItem]:
        if status is None:
            rows = self._db.query(
                f"SELECT {_COLUMNS} FROM email_outbox ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        else:
            rows = self._db.query(
                f"SELECT {_COLUMNS} FROM email_outbox WHERE status = ? ORDER BY id DESC LIMIT ?",
                (status.value, limit),
            )
        return [_to_model(row) for row in rows]

    def due(self, now: datetime) -> list[OutboxItem]:
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM email_outbox WHERE status = 'pending'"
            " AND (next_attempt_at IS NULL OR next_attempt_at <= ?) ORDER BY id",
            (iso(now),),
        )
        return [_to_model(row) for row in rows]

    def set_payload_path(self, item_id: int, payload_path: str | None) -> None:
        self._update(item_id, "payload_path = ?", (payload_path,))

    def mark_sent(self, item_id: int) -> None:
        self._update(
            item_id,
            "status = 'sent', attempts = attempts + 1, sent_at = ?, last_error = NULL,"
            " next_attempt_at = NULL",
            (iso(self._clock.now()),),
        )

    def mark_attempt_failed(
        self, item_id: int, error: str, *, next_attempt_at: datetime | None, give_up: bool
    ) -> None:
        status = OutboxStatus.FAILED if give_up else OutboxStatus.PENDING
        self._update(
            item_id,
            "status = ?, attempts = attempts + 1, last_error = ?, next_attempt_at = ?",
            (status.value, error[:2000], iso(next_attempt_at)),
        )

    def reset_for_resend(self, item_id: int) -> None:
        """Admin "Resend": back to pending, due now, attempt counter restarted."""
        self._update(
            item_id,
            "status = 'pending', attempts = 0, next_attempt_at = ?",
            (iso(self._clock.now()),),
        )

    def sent_with_payload_before(self, cutoff: datetime) -> list[OutboxItem]:
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM email_outbox WHERE status = 'sent'"
            " AND payload_path IS NOT NULL AND sent_at < ? ORDER BY id",
            (iso(cutoff),),
        )
        return [_to_model(row) for row in rows]

    def count_by_status(self) -> dict[OutboxStatus, int]:
        rows = self._db.query("SELECT status, COUNT(*) AS n FROM email_outbox GROUP BY status")
        counts = dict.fromkeys(OutboxStatus, 0)
        for row in rows:
            counts[OutboxStatus(row["status"])] = int(row["n"])
        return counts

    def _update(self, item_id: int, assignments: str, params: tuple[object, ...]) -> None:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE email_outbox SET {assignments} WHERE id = ?",
                (*params, item_id),
            )
            if cursor.rowcount != 1:
                raise NotFoundError(f"outbox item {item_id} not found")
