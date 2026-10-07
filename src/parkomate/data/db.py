"""SQLite connection wrapper.

* WAL journal, foreign keys ON, ``synchronous=NORMAL`` (durable across app crashes; a power
  cut can lose at most the last transaction), busy timeout 5 s.
* One shared connection guarded by a re-entrant lock, so the GUI thread and workers can both
  use it safely.
* :meth:`Database.transaction` nests: the outermost call opens ``BEGIN IMMEDIATE``; inner
  calls use SAVEPOINTs, so a failing inner block rolls back only its own work.
* Every ``sqlite3.Error`` is re-raised as :class:`~parkomate.core.errors.DatabaseError`.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from parkomate.core.errors import DatabaseError

log = logging.getLogger(__name__)

Params = Sequence[Any] | dict[str, Any]


class Database:
    def __init__(self, path: Path | str) -> None:
        self._path = str(path)
        if self._path != ":memory:":
            Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        try:
            self._conn = sqlite3.connect(
                self._path, isolation_level=None, check_same_thread=False, timeout=5.0
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA busy_timeout = 5000")
            if self._path != ":memory:":
                self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.Error as exc:
            raise DatabaseError(f"cannot open database {self._path}: {exc}") from exc
        self._lock = threading.RLock()
        self._depth = 0

    @property
    def path(self) -> str:
        return self._path

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run the block atomically. Nested calls become savepoints."""
        with self._lock:
            depth = self._depth
            savepoint = f"sp_{depth}"
            try:
                self._conn.execute("BEGIN IMMEDIATE" if depth == 0 else f"SAVEPOINT {savepoint}")
            except sqlite3.Error as exc:
                raise DatabaseError(f"cannot begin transaction: {exc}") from exc
            self._depth += 1
            try:
                yield self._conn
            except BaseException as exc:
                self._depth -= 1
                self._rollback(depth, savepoint)
                if isinstance(exc, sqlite3.Error):
                    raise DatabaseError(
                        f"database error: {exc}", context={"sqlite": str(exc)}
                    ) from exc
                raise
            else:
                self._depth -= 1
                try:
                    self._conn.execute("COMMIT" if depth == 0 else f"RELEASE {savepoint}")
                except sqlite3.Error as exc:
                    self._rollback(depth, savepoint)
                    raise DatabaseError(f"commit failed: {exc}") from exc

    def _rollback(self, depth: int, savepoint: str) -> None:
        try:
            if depth == 0:
                self._conn.execute("ROLLBACK")
            else:
                self._conn.execute(f"ROLLBACK TO {savepoint}")
                self._conn.execute(f"RELEASE {savepoint}")
        except sqlite3.Error:
            log.exception("rollback failed")

    def query(self, sql: str, params: Params = ()) -> list[sqlite3.Row]:
        with self._lock:
            try:
                return self._conn.execute(sql, params).fetchall()
            except sqlite3.Error as exc:
                raise DatabaseError(f"query failed: {exc}", context={"sql": sql}) from exc

    def query_one(self, sql: str, params: Params = ()) -> sqlite3.Row | None:
        with self._lock:
            try:
                row: sqlite3.Row | None = self._conn.execute(sql, params).fetchone()
            except sqlite3.Error as exc:
                raise DatabaseError(f"query failed: {exc}", context={"sql": sql}) from exc
            return row

    def scalar(self, sql: str, params: Params = ()) -> Any:
        row = self.query_one(sql, params)
        return None if row is None else row[0]

    def execute_script(self, script: str) -> None:
        """Run a multi-statement script as one transaction (used by migrations)."""
        with self._lock:
            if self._depth:
                raise DatabaseError("execute_script cannot run inside a transaction")
            try:
                self._conn.executescript(f"BEGIN IMMEDIATE;\n{script}\nCOMMIT;")
            except sqlite3.Error as exc:
                if self._conn.in_transaction:
                    self._conn.execute("ROLLBACK")
                raise DatabaseError(f"script failed: {exc}") from exc

    def backup_to(self, target: Path) -> None:
        """Online copy of the whole database (safe while in use)."""
        with self._lock:
            target.parent.mkdir(parents=True, exist_ok=True)
            dest = sqlite3.connect(str(target))
            try:
                self._conn.backup(dest)
            except sqlite3.Error as exc:
                raise DatabaseError(f"backup failed: {exc}") from exc
            finally:
                dest.close()

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                log.exception("closing the database failed")
