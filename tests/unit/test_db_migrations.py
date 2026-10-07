from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import parkomate.data.migrate as migrate_module
from parkomate.core.errors import DatabaseError
from parkomate.data import Database, open_database
from parkomate.data.migrate import Migration, current_version, discover_migrations, migrate

TABLES = {
    "operators",
    "sessions",
    "ambient_readings",
    "devices",
    "check_results",
    "counter_events",
    "email_outbox",
    "audit_log",
    "schema_version",
}


def _tables(db: Database) -> set[str]:
    return {r[0] for r in db.query("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_fresh_database_is_fully_migrated(tmp_path: Path) -> None:
    db = open_database(tmp_path / "a.db")
    assert _tables(db) >= TABLES
    assert current_version(db) == discover_migrations()[-1].version
    assert db.scalar("PRAGMA foreign_keys") == 1
    assert str(db.scalar("PRAGMA journal_mode")).lower() == "wal"
    db.close()


def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db = open_database(tmp_path / "a.db")
    version = migrate(db)
    assert migrate(db) == version
    assert db.scalar("SELECT COUNT(*) FROM schema_version") == version
    db.close()


def test_upgrade_takes_backup_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = open_database(tmp_path / "a.db")
    original = discover_migrations()
    extra = Migration(len(original) + 1, "add_test", "CREATE TABLE extra_test (id INTEGER);")
    monkeypatch.setattr(migrate_module, "discover_migrations", lambda: [*original, extra])
    backups = tmp_path / "backups"
    assert migrate(db, backup_dir=backups) == extra.version
    assert "extra_test" in _tables(db)
    assert len(list(backups.glob("parkomate-v*.db"))) == 1
    db.close()


def test_failed_migration_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = open_database(tmp_path / "a.db")
    original = discover_migrations()
    broken = Migration(
        len(original) + 1, "broken", "CREATE TABLE half_done (id INTEGER);\nNOT VALID SQL;"
    )
    monkeypatch.setattr(migrate_module, "discover_migrations", lambda: [*original, broken])
    with pytest.raises(DatabaseError):
        migrate(db)
    assert "half_done" not in _tables(db)
    assert current_version(db) == len(original)
    db.close()


def test_newer_database_is_refused(tmp_path: Path) -> None:
    db = open_database(tmp_path / "a.db")
    db.execute_script(
        "INSERT INTO schema_version VALUES (99, 'future', '2030-01-01T00:00:00+00:00');"
    )
    with pytest.raises(DatabaseError, match="newer"):
        migrate(db)
    db.close()


def test_discover_rejects_gaps(monkeypatch: pytest.MonkeyPatch) -> None:
    class Entry:
        def __init__(self, name: str) -> None:
            self.name = name

        def read_text(self, encoding: str) -> str:
            return ""

    class Files:
        def iterdir(self) -> list[Entry]:
            return [Entry("0001_a.sql"), Entry("0003_c.sql"), Entry("README.txt")]

    monkeypatch.setattr(migrate_module.resources, "files", lambda _pkg: Files())
    with pytest.raises(DatabaseError, match="gaps"):
        discover_migrations()


def test_nested_transaction_rolls_back_only_inner(db: Database) -> None:
    db.execute_script("CREATE TABLE t (v INTEGER);")
    with db.transaction() as conn:
        conn.execute("INSERT INTO t VALUES (1)")
        with pytest.raises(RuntimeError), db.transaction() as inner:
            inner.execute("INSERT INTO t VALUES (2)")
            raise RuntimeError("inner failure")
        conn.execute("INSERT INTO t VALUES (3)")
    assert [r[0] for r in db.query("SELECT v FROM t ORDER BY v")] == [1, 3]


def test_outer_failure_rolls_back_everything(db: Database) -> None:
    db.execute_script("CREATE TABLE t (v INTEGER);")
    with pytest.raises(ValueError), db.transaction() as conn:
        conn.execute("INSERT INTO t VALUES (1)")
        with db.transaction() as inner:
            inner.execute("INSERT INTO t VALUES (2)")
        raise ValueError("outer failure")
    assert db.scalar("SELECT COUNT(*) FROM t") == 0


def test_sqlite_errors_become_database_error(db: Database) -> None:
    with pytest.raises(DatabaseError), db.transaction() as conn:
        conn.execute("INSERT INTO nope VALUES (1)")
    with pytest.raises(DatabaseError):
        db.query("SELECT * FROM nope")
    with pytest.raises(DatabaseError):
        db.query_one("SELECT * FROM nope")
    with pytest.raises(DatabaseError):
        db.execute_script("NOT SQL")


def test_execute_script_refused_inside_transaction(db: Database) -> None:
    with db.transaction(), pytest.raises(DatabaseError):
        db.execute_script("SELECT 1;")


def test_append_only_tables(db: Database) -> None:
    db.execute_script(
        "INSERT INTO audit_log (action, details_json, created_at)"
        " VALUES ('x', '{}', '2026-01-01T00:00:00+00:00');"
    )
    for statement in ("UPDATE audit_log SET action = 'y'", "DELETE FROM audit_log"):
        with pytest.raises(DatabaseError, match="append-only"), db.transaction() as conn:
            conn.execute(statement)


def test_backup_to_copies_database(db: Database, tmp_path: Path) -> None:
    target = tmp_path / "copy" / "backup.db"
    db.backup_to(target)
    copy = sqlite3.connect(target)
    names = {r[0] for r in copy.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    copy.close()
    assert names >= TABLES


def test_in_memory_database() -> None:
    db = open_database(":memory:")
    assert db.path == ":memory:"
    assert _tables(db) >= TABLES
    db.close()
