"""Operators (people who can log in)."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from parkomate.core.clock import Clock
from parkomate.core.enums import Role
from parkomate.core.errors import NotFoundError
from parkomate.core.models import Operator
from parkomate.data.db import Database
from parkomate.data.repositories._rows import iso, last_id, ts, ts_req

_COLUMNS = (
    "id, operator_code, full_name, role, is_active, failed_attempts, locked_until, language, "
    "created_at"
)


def _to_model(row: sqlite3.Row) -> Operator:
    return Operator(
        id=row["id"],
        operator_code=row["operator_code"],
        full_name=row["full_name"],
        role=Role(row["role"]),
        is_active=bool(row["is_active"]),
        failed_attempts=row["failed_attempts"],
        locked_until=ts(row["locked_until"]),
        language=row["language"],
        created_at=ts_req(row["created_at"]),
    )


class OperatorRepo:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def create(
        self,
        operator_code: str,
        full_name: str,
        password_hash: str,
        role: Role,
        *,
        is_active: bool = True,
        language: str | None = None,
    ) -> Operator:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO operators (operator_code, full_name, password_hash, role, is_active,"
                " language, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    operator_code,
                    full_name,
                    password_hash,
                    role.value,
                    int(is_active),
                    language,
                    iso(self._clock.now()),
                ),
            )
            return self.require(last_id(cursor))

    def get(self, operator_id: int) -> Operator | None:
        row = self._db.query_one(f"SELECT {_COLUMNS} FROM operators WHERE id = ?", (operator_id,))
        return None if row is None else _to_model(row)

    def require(self, operator_id: int) -> Operator:
        operator = self.get(operator_id)
        if operator is None:
            raise NotFoundError(f"operator {operator_id} not found")
        return operator

    def get_by_code(self, operator_code: str) -> Operator | None:
        row = self._db.query_one(
            f"SELECT {_COLUMNS} FROM operators WHERE operator_code = ?", (operator_code.strip(),)
        )
        return None if row is None else _to_model(row)

    def get_password_hash(self, operator_id: int) -> str:
        value = self._db.scalar("SELECT password_hash FROM operators WHERE id = ?", (operator_id,))
        if value is None:
            raise NotFoundError(f"operator {operator_id} not found")
        return str(value)

    def list_all(self, *, include_inactive: bool = True) -> list[Operator]:
        where = "" if include_inactive else "WHERE is_active = 1"
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM operators {where} ORDER BY operator_code COLLATE NOCASE"
        )
        return [_to_model(row) for row in rows]

    def count_active_admins(self) -> int:
        return int(
            self._db.scalar("SELECT COUNT(*) FROM operators WHERE role = 'admin' AND is_active = 1")
        )

    def set_password_hash(self, operator_id: int, password_hash: str) -> None:
        self._update(operator_id, "password_hash = ?", (password_hash,))

    def set_active(self, operator_id: int, active: bool) -> None:
        self._update(operator_id, "is_active = ?", (int(active),))

    def set_role(self, operator_id: int, role: Role) -> None:
        self._update(operator_id, "role = ?", (role.value,))

    def set_full_name(self, operator_id: int, full_name: str) -> None:
        self._update(operator_id, "full_name = ?", (full_name,))

    def set_language(self, operator_id: int, language: str | None) -> None:
        self._update(operator_id, "language = ?", (language,))

    def set_lock_state(
        self, operator_id: int, failed_attempts: int, locked_until: datetime | None
    ) -> None:
        self._update(
            operator_id,
            "failed_attempts = ?, locked_until = ?",
            (failed_attempts, iso(locked_until)),
        )

    def _update(self, operator_id: int, assignments: str, params: tuple[object, ...]) -> None:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                f"UPDATE operators SET {assignments} WHERE id = ?",
                (*params, operator_id),
            )
            if cursor.rowcount != 1:
                raise NotFoundError(f"operator {operator_id} not found")
