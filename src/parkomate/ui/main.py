"""Start the station UI: ``python -m parkomate [--mock] [--kiosk]``."""

from __future__ import annotations

import logging
import sys
from types import TracebackType

from PySide6.QtCore import QLockFile
from PySide6.QtWidgets import QApplication

from parkomate.app import AppContext, build_context
from parkomate.app_paths import AppPaths
from parkomate.core.errors import ErrorCode, ParkomateError, SettingsError
from parkomate.i18n import set_language
from parkomate.ui.theme.fonts import app_font, load_fonts
from parkomate.ui.theme.qss import build_stylesheet

log = logging.getLogger(__name__)


def create_application(argv: list[str] | None = None) -> QApplication:
    """QApplication with bundled fonts and the station stylesheet (idempotent)."""
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication(argv if argv is not None else sys.argv[:1])
    app.setApplicationName("Parkomate Station")
    app.setOrganizationName("Parkomate")
    load_fonts()
    app.setFont(app_font())
    app.setStyleSheet(build_stylesheet())
    return app


def _log_unhandled(
    exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None
) -> None:
    """Exceptions escaping a Qt slot are logged (errors.jsonl) instead of being lost."""
    log.critical(
        "unhandled exception in the UI",
        exc_info=(exc_type, exc, tb),
        extra={"error_code": "UNEXPECTED"},
    )


def run_ui(*, mock: bool | None = None, kiosk: bool = False) -> int:
    app = create_application()
    sys.excepthook = _log_unhandled
    paths = AppPaths.default().ensure()

    lock = QLockFile(str(paths.root / "station.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        from parkomate.ui.views.pages import FatalView

        set_language("en")
        error = ParkomateError("already running", code=ErrorCode.ALREADY_RUNNING)
        view = FatalView(error, str(paths.root))
        view.show()
        log.error("another Parkomate Station is already running on this PC")
        return app.exec() or 3

    try:
        ctx: AppContext = build_context(paths, mock=mock)
    except (SettingsError, ParkomateError) as exc:
        from parkomate.ui.views.pages import FatalView

        view = FatalView(exc, str(paths.settings_file))
        view.showMaximized()
        code = app.exec()
        lock.unlock()
        return code or 2

    from parkomate.ui.main_window import MainWindow
    from parkomate.ui.viewmodels.station import StationController

    controller = StationController(ctx)
    window = MainWindow(controller, kiosk=kiosk or ctx.settings.ui.kiosk)
    window.show_station()
    controller.start()
    try:
        return app.exec()
    finally:
        controller.shutdown()
        lock.unlock()
