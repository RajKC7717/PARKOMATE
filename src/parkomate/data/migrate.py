"""Versioned schema migrations.

Migrations are SQL files in ``parkomate/data/migrations`` named ``NNNN_description.sql``.
They are applied in ascending order, each in its own transaction, and recorded in
``schema_version``. Applied migrations must never be edited - add a new file instead.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

from parkomate.core.clock import to_iso
from parkomate.core.errors import DatabaseError
from parkomate.data.db import Database

log = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str


def discover_migrations() -> list[Migration]:
    """All bundled migrations sorted by version. Raises on gaps or duplicates."""
    found: list[Migration] = []
    for entry in resources.files("parkomate.data.migrations").iterdir():
        match = _NAME_RE.match(entry.name)
        if match:
            found.append(
                Migration(int(match.group(1)), match.group(2), entry.read_text(encoding="utf-8"))
            )
    found.sort(key=lambda m: m.version)
    expected = list(range(1, len(found) + 1))
    if [m.version for m in found] != expected:
        raise DatabaseError(
            f"migration versions must be 1..n without gaps, got {[m.version for m in found]}"
        )
    return found


def current_version(db: Database) -> int:
    db.execute_script(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        " version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL);"
    )
    value = db.scalar("SELECT MAX(version) FROM schema_version")
    return int(value) if value is not None else 0


def migrate(db: Database, *, backup_dir: Path | None = None) -> int:
    """Bring ``db`` to the newest schema. Returns the resulting version.

    When ``backup_dir`` is given and an existing database needs upgrading, an online backup
    is taken first.
    """
    migrations = discover_migrations()
    version = current_version(db)
    latest = migrations[-1].version if migrations else 0
    if version > latest:
        raise DatabaseError(
            f"database schema v{version} is newer than this application (v{latest}); "
            "install the newer application version"
        )
    pending = [m for m in migrations if m.version > version]
    if pending and version > 0 and backup_dir is not None:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        target = backup_dir / f"parkomate-v{version}-{stamp}.db"
        log.info("backing up database before migration to %s", target)
        db.backup_to(target)
    for migration in pending:
        log.info("applying migration %04d_%s", migration.version, migration.name)
        now = to_iso(datetime.now(UTC))
        name = migration.name.replace("'", "''")
        db.execute_script(
            f"{migration.sql}\n"
            f"INSERT INTO schema_version (version, name, applied_at) "
            f"VALUES ({migration.version}, '{name}', '{now}');"
        )
    return latest
