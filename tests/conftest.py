"""Shared fixtures for all tests."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from argon2 import PasswordHasher

# Qt must render off-screen in tests (CI, no display).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PARKOMATE_MOCK_DELAY"] = "0"
os.environ.pop("PARKOMATE_MOCK_SCENARIO", None)
os.environ.pop("PARKOMATE_SETTINGS", None)
# Safety net: nothing in the test run may ever touch the real station data folder.
os.environ["PARKOMATE_DATA_DIR"] = tempfile.mkdtemp(prefix="parkomate-tests-")

from parkomate.auth.service import AuthService
from parkomate.config.settings import Settings
from parkomate.core.clock import FakeClock
from parkomate.core.enums import Role
from parkomate.core.events import EventBus
from parkomate.core.models import Operator
from parkomate.data import Database, Repositories, open_database
from parkomate.data.records import ProductionRecords
from parkomate.i18n import set_language

PASSWORD = "secret-pass-1"


@pytest.fixture(autouse=True)
def _english() -> Iterator[None]:
    set_language("en")
    yield
    set_language("en")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = open_database(tmp_path / "test.db")
    yield database
    database.close()


@pytest.fixture
def repos(db: Database, clock: FakeClock) -> Repositories:
    return Repositories.create(db, clock)


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def fast_hasher() -> PasswordHasher:
    return PasswordHasher(time_cost=1, memory_cost=64, parallelism=1)


@pytest.fixture
def auth(repos: Repositories, settings: Settings, fast_hasher: PasswordHasher) -> AuthService:
    return AuthService(repos, lambda: settings.auth, hasher=fast_hasher)


@pytest.fixture
def admin(auth: AuthService) -> Operator:
    return auth.create_first_admin("ADM1", "Asha Admin", PASSWORD)


@pytest.fixture
def operator(auth: AuthService, admin: Operator) -> Operator:
    return auth.create_operator(admin, "OP1", "Omkar Operator", PASSWORD, Role.OPERATOR)


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def records(repos: Repositories, bus: EventBus) -> ProductionRecords:
    return ProductionRecords(repos, station_id="ST-TEST", bus=bus)


@pytest.fixture
def open_session(records: ProductionRecords, operator: Operator) -> ProductionRecords:
    """Records service with an open session for ``operator``."""
    records.start_session(operator, language="en")
    return records
