"""Composition root: builds every service once and wires them together.

The UI receives an :class:`AppContext` and never constructs services itself. The full build
(Prompt 3) adds the real HardwareService / WorkflowService here, selected by
``dev.use_mock_hardware`` or the ``--mock`` flag.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from parkomate.app_paths import AppPaths
from parkomate.auth.service import AuthService
from parkomate.config.manager import SettingsManager
from parkomate.config.secrets import KeyringSecretStore, SecretStore
from parkomate.config.settings import Settings
from parkomate.core.clock import Clock, SystemClock
from parkomate.core.errors import SettingsError
from parkomate.core.events import EventBus, SettingsReloaded
from parkomate.core.interfaces import HardwareService, WorkflowService
from parkomate.data import Database, Repositories, open_database
from parkomate.data.records import ProductionRecords
from parkomate.hardware.mocks import (
    MockHardwareService,
    resolve_delay_scale,
    resolve_scenario,
    resolve_seed,
)
from parkomate.i18n import set_language
from parkomate.logging_setup import setup_logging
from parkomate.mail.mailers import create_mailer
from parkomate.mail.outbox import OutboxService
from parkomate.mail.reporting import SessionReporter
from parkomate.reports.exporter import ReportExporter
from parkomate.station import Station
from parkomate.workflow.stub import StubWorkflowService

log = logging.getLogger(__name__)


@dataclass(slots=True)
class AppContext:
    paths: AppPaths
    settings_manager: SettingsManager
    db: Database
    repos: Repositories
    bus: EventBus
    records: ProductionRecords
    auth: AuthService
    exporter: ReportExporter
    outbox: OutboxService
    reporter: SessionReporter
    station: Station
    hardware: HardwareService
    workflow: WorkflowService
    secrets: SecretStore
    using_mocks: bool

    @property
    def settings(self) -> Settings:
        return self.settings_manager.current

    def close(self) -> None:
        """Release hardware (zeroes the firmware buffer) and close the database."""
        try:
            self.hardware.shutdown()
        except Exception:
            log.exception("hardware shutdown failed")
        self.db.close()


def create_hardware(settings: Settings, *, mock: bool | None) -> tuple[HardwareService, bool]:
    use_mock = settings.dev.use_mock_hardware if mock is None else mock
    if not use_mock:
        raise SettingsError(
            "the real hardware service is part of the full build; use mocks for now",
            problems=[("dev.use_mock_hardware", "real hardware is not available yet - set true")],
        )
    service = MockHardwareService(
        resolve_scenario(settings.dev.mock_scenario),
        delay_scale=resolve_delay_scale(settings.dev.mock_delay_scale),
        seed=resolve_seed(),
    )
    log.info("using MOCK hardware (scenario %s)", service.scenario.value)
    return service, True


def build_context(
    paths: AppPaths | None = None,
    *,
    mock: bool | None = None,
    secrets: SecretStore | None = None,
    clock: Clock | None = None,
    hardware: HardwareService | None = None,
    configure_logging: bool = True,
) -> AppContext:
    """Create every service. Raises :class:`SettingsError` for an invalid settings file."""
    paths = (paths or AppPaths.default()).ensure()
    manager = SettingsManager(paths.settings_file)
    settings = manager.load()
    if configure_logging:
        setup_logging(paths.logs_dir, settings.logging)
    set_language(settings.station.language)

    db = open_database(paths.database_file, backup_dir=paths.backups_dir)
    repos = Repositories.create(db, clock or SystemClock())
    manager.set_audit(repos.audit)
    bus = EventBus()
    records = ProductionRecords(repos, station_id=settings.station.station_id, bus=bus)

    def current() -> Settings:
        return manager.current

    def on_settings(new: Settings, changed: tuple[str, ...]) -> None:
        records.station_id = new.station.station_id
        bus.publish(SettingsReloaded(changed))

    manager.add_listener(on_settings)

    auth = AuthService(repos, lambda: current().auth)
    exporter = ReportExporter(
        repos,
        paths.reports_dir,
        lambda: current().reports,
        lambda: current().station.station_id,
    )
    secret_store = secrets or KeyringSecretStore()
    mailer = create_mailer(lambda: current().email, secret_store)
    outbox = OutboxService(
        repos, paths.outbox_dir, mailer, lambda: current().email, lambda: current().retention_days
    )
    reporter = SessionReporter(repos, exporter, outbox, current)
    station = Station(repos, records, auth, reporter, outbox, current)
    if hardware is None:
        hardware, using_mocks = create_hardware(settings, mock=mock)
    else:
        using_mocks = isinstance(hardware, MockHardwareService)
    workflow = StubWorkflowService(records, current, bus)
    return AppContext(
        paths=paths,
        settings_manager=manager,
        db=db,
        repos=repos,
        bus=bus,
        records=records,
        auth=auth,
        exporter=exporter,
        outbox=outbox,
        reporter=reporter,
        station=station,
        hardware=hardware,
        workflow=workflow,
        secrets=secret_store,
        using_mocks=using_mocks,
    )
