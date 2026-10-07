"""Check results (append-only; every attempt is kept)."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from parkomate.core.clock import Clock
from parkomate.core.enums import CheckCode, Stage
from parkomate.core.models import CheckResult
from parkomate.data.db import Database
from parkomate.data.repositories._rows import int_bool, iso, last_id, opt_bool, ts_req

_COLUMNS = (
    "id, device_row_id, stage, check_code, value_text, value_num, unit, limit_low, limit_high, "
    "passed, operator_marked, created_at"
)


def _to_model(row: sqlite3.Row) -> CheckResult:
    return CheckResult(
        id=row["id"],
        device_row_id=row["device_row_id"],
        stage=Stage(row["stage"]),
        check_code=CheckCode(row["check_code"]),
        value_text=row["value_text"],
        value_num=row["value_num"],
        unit=row["unit"],
        limit_low=row["limit_low"],
        limit_high=row["limit_high"],
        passed=opt_bool(row["passed"]),
        operator_marked=bool(row["operator_marked"]),
        created_at=ts_req(row["created_at"]),
    )


class CheckResultRepo:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def add(
        self,
        device_row_id: int,
        stage: Stage,
        check_code: CheckCode,
        *,
        value_text: str | None = None,
        value_num: float | None = None,
        unit: str | None = None,
        limit_low: float | None = None,
        limit_high: float | None = None,
        passed: bool | None = None,
        operator_marked: bool = False,
    ) -> CheckResult:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO check_results (device_row_id, stage, check_code, value_text,"
                " value_num, unit, limit_low, limit_high, passed, operator_marked, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    device_row_id,
                    stage.value,
                    check_code.value,
                    value_text,
                    value_num,
                    unit,
                    limit_low,
                    limit_high,
                    int_bool(passed),
                    int(operator_marked),
                    iso(self._clock.now()),
                ),
            )
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM check_results WHERE id = ?",
                (last_id(cursor),),
            ).fetchone()
        return _to_model(row)

    def list_for_device(self, device_row_id: int) -> list[CheckResult]:
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM check_results WHERE device_row_id = ? ORDER BY id",
            (device_row_id,),
        )
        return [_to_model(row) for row in rows]

    def list_for_devices(self, device_row_ids: Sequence[int]) -> list[CheckResult]:
        if not device_row_ids:
            return []
        marks = ",".join("?" for _ in device_row_ids)
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM check_results"
            f" WHERE device_row_id IN ({marks}) ORDER BY device_row_id, id",
            tuple(device_row_ids),
        )
        return [_to_model(row) for row in rows]

    def latest_by_code(self, device_row_id: int) -> dict[CheckCode, CheckResult]:
        """Most recent result per check code (later attempts override earlier ones)."""
        latest: dict[CheckCode, CheckResult] = {}
        for result in self.list_for_device(device_row_id):
            latest[result.check_code] = result
        return latest
