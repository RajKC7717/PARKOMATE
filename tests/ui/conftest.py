"""UI test fixtures: an isolated station on the mock bench, driven like an operator."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

from parkomate.hardware.mocks import MockScenario
from parkomate.i18n import set_language
from parkomate.ui.screenshots import StationDriver

DriverFactory = Callable[..., StationDriver]


@pytest.fixture
def make_driver(qapp: QApplication) -> Iterator[DriverFactory]:
    drivers: list[StationDriver] = []

    def factory(scenario: MockScenario = MockScenario.ALL_PASS, **kwargs: Any) -> StationDriver:
        driver = StationDriver(scenario=scenario, **kwargs)
        drivers.append(driver)
        return driver

    yield factory
    for driver in drivers:
        driver.close()
    set_language("en")


@pytest.fixture
def driver(make_driver: DriverFactory) -> StationDriver:
    """Logged-in admin on the Programming screen, firmware loaded, port auto-selected."""
    d = make_driver()
    d.start()
    d.login()
    d.ready_for_board()
    return d
