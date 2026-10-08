"""Database, migrations, repositories and the production records API (owner: Yugant)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from parkomate.core.clock import Clock
from parkomate.data.db import Database
from parkomate.data.migrate import migrate as run_migrations
from parkomate.data.repositories import (
    AuditRepo,
    CheckResultRepo,
    CounterRepo,
    DeviceRepo,
    OperatorRepo,
    OutboxRepo,
    SessionRepo,
    TransitionRepo,
)


@dataclass(frozen=True, slots=True)
class Repositories:
    """All repositories sharing one :class:`Database` and clock."""

    db: Database
    clock: Clock
    operators: OperatorRepo
    sessions: SessionRepo
    devices: DeviceRepo
    checks: CheckResultRepo
    counters: CounterRepo
    outbox: OutboxRepo
    audit: AuditRepo
    transitions: TransitionRepo

    @classmethod
    def create(cls, db: Database, clock: Clock) -> Repositories:
        return cls(
            db=db,
            clock=clock,
            operators=OperatorRepo(db, clock),
            sessions=SessionRepo(db, clock),
            devices=DeviceRepo(db, clock),
            checks=CheckResultRepo(db, clock),
            counters=CounterRepo(db, clock),
            outbox=OutboxRepo(db, clock),
            audit=AuditRepo(db, clock),
            transitions=TransitionRepo(db, clock),
        )


def open_database(path: Path | str, *, backup_dir: Path | None = None) -> Database:
    """Open (creating if needed) and migrate the database."""
    db = Database(path)
    run_migrations(db, backup_dir=backup_dir)
    return db


__all__ = ["Database", "Repositories", "open_database", "run_migrations"]
