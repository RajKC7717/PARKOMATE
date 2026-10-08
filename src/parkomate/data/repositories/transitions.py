"""Stage transitions (append-only): every move of a device between stages."""

from __future__ import annotations

import sqlite3

from parkomate.core.clock import Clock
from parkomate.core.enums import Stage
from parkomate.core.models import StageTransition
from parkomate.data.db import Database
from parkomate.data.repositories._rows import iso, last_id, ts_req

_COLUMNS = "id, device_row_id, from_stage, to_stage, created_at"


def _to_model(row: sqlite3.Row) -> StageTransition:
    return StageTransition(
        id=row["id"],
        device_row_id=row["device_row_id"],
        from_stage=Stage(row["from_stage"]) if row["from_stage"] else None,
        to_stage=Stage(row["to_stage"]),
        created_at=ts_req(row["created_at"]),
    )


class TransitionRepo:
    def __init__(self, db: Database, clock: Clock) -> None:
        self._db = db
        self._clock = clock

    def add(self, device_row_id: int, from_stage: Stage | None, to_stage: Stage) -> StageTransition:
        with self._db.transaction() as conn:
            cursor = conn.execute(
                "INSERT INTO stage_transitions (device_row_id, from_stage, to_stage, created_at)"
                " VALUES (?, ?, ?, ?)",
                (
                    device_row_id,
                    from_stage.value if from_stage else None,
                    to_stage.value,
                    iso(self._clock.now()),
                ),
            )
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM stage_transitions WHERE id = ?",
                (last_id(cursor),),
            ).fetchone()
        return _to_model(row)

    def list_for_device(self, device_row_id: int) -> list[StageTransition]:
        rows = self._db.query(
            f"SELECT {_COLUMNS} FROM stage_transitions WHERE device_row_id = ? ORDER BY id",
            (device_row_id,),
        )
        return [_to_model(row) for row in rows]
