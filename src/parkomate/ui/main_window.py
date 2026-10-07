"""Main window: one stacked page per controller page."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget

from parkomate.i18n import t
from parkomate.ui.qt_i18n import language_notifier
from parkomate.ui.theme.tokens import SIZES
from parkomate.ui.viewmodels.station import Page, StationController
from parkomate.ui.views.admin import AdminView
from parkomate.ui.views.pages import LoginView, SessionEndView, StartingView
from parkomate.ui.views.shell import ProductionShell


class MainWindow(QMainWindow):
    def __init__(self, controller: StationController, *, kiosk: bool = False) -> None:
        super().__init__()
        self.c = controller
        self.setObjectName("Root")
        self.setMinimumSize(SIZES.min_window_width, SIZES.min_window_height)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.starting = StartingView()
        self.login = LoginView(controller)
        self.shell = ProductionShell(controller)
        self.session_end = SessionEndView(controller)
        self.admin = AdminView(controller)
        self.pages: dict[Page, QWidget] = {
            Page.STARTING: self.starting,
            Page.LOGIN: self.login,
            Page.PRODUCTION: self.shell,
            Page.SESSION_END: self.session_end,
            Page.ADMIN: self.admin,
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        if kiosk:
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self._kiosk = kiosk
        escape = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.admin)
        escape.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        escape.activated.connect(controller.close_admin)
        controller.page_changed.connect(self._page_changed)
        language_notifier().changed.connect(self._retitle)
        self._retitle()
        self._page_changed()

    def show_station(self) -> None:
        if self._kiosk:
            self.showFullScreen()
        else:
            self.showMaximized()

    def _retitle(self, *_args: object) -> None:
        self.setWindowTitle(t("app.window_title", station=self.c.settings.station.station_id))

    def _page_changed(self) -> None:
        page = self.c.page
        widget = self.pages[page]
        self.stack.setCurrentWidget(widget)
        if page is Page.LOGIN:
            self.login.update_view()
            self.login.focus_first()
        elif page is Page.PRODUCTION:
            self.shell.setFocus()
        elif page is Page.ADMIN:
            self.admin.refresh()
        elif page is Page.SESSION_END:
            self.session_end.update_view()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.c.shutdown()
        event.accept()
