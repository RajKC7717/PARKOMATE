"""Where the station keeps its data.

Default data directory:

* Windows: ``%PROGRAMDATA%\Parkomate`` (shared by every Windows user of the bench PC)
* Linux/macOS (development): ``~/.parkomate``

Override with the ``PARKOMATE_DATA_DIR`` environment variable (tests and development).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

ENV_DATA_DIR = "PARKOMATE_DATA_DIR"
ENV_SETTINGS = "PARKOMATE_SETTINGS"


def default_data_dir() -> Path:
    override = os.environ.get(ENV_DATA_DIR)
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("PROGRAMDATA") or r"C:\ProgramData"
        return Path(base) / "Parkomate"
    return Path.home() / ".parkomate"


@dataclass(frozen=True, slots=True)
class AppPaths:
    """All file locations, derived from one root directory."""

    root: Path

    @classmethod
    def default(cls) -> AppPaths:
        return cls(default_data_dir())

    @property
    def settings_file(self) -> Path:
        override = os.environ.get(ENV_SETTINGS)
        return Path(override).expanduser() if override else self.root / "settings.toml"

    @property
    def database_file(self) -> Path:
        return self.root / "parkomate.db"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports"

    @property
    def outbox_dir(self) -> Path:
        return self.root / "outbox"

    @property
    def backups_dir(self) -> Path:
        return self.root / "backups"

    def ensure(self) -> AppPaths:
        """Create every directory (idempotent) and return self."""
        for path in (self.root, self.logs_dir, self.reports_dir, self.outbox_dir,
                     self.backups_dir):
            path.mkdir(parents=True, exist_ok=True)
        return self
