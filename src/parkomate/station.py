"""Station facade: the operations the UI performs around a session.

* :meth:`Station.startup` - crash recovery, queue reports of recovered sessions, purge old
  e-mail payloads. Run once before the login screen.
* :meth:`Station.login` - authenticate, open a session (language remembered per operator).
* :meth:`Station.logout` - close the session (unfinished device -> abandoned), write the
  reports and queue the summary e-mail. Sending happens separately
  (:meth:`Station.send_pending`) so a slow mail server never blocks the UI.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from parkomate.auth.service import AuthService
from parkomate.config.settings import Settings
from parkomate.core.enums import SessionEndReason
from parkomate.core.errors import ParkomateError
from parkomate.core.models import Operator, Session, SessionSummary
from parkomate.data import Repositories
from parkomate.data.records import ProductionRecords
from parkomate.data.recovery import RecoveryResult, recover_unclosed_sessions
from parkomate.mail.outbox import OutboxService, SendReport
from parkomate.mail.reporting import QueuedReport, SessionReporter

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StartupResult:
    recovery: RecoveryResult
    queued_reports: list[QueuedReport] = field(default_factory=list)
    report_errors: list[ParkomateError] = field(default_factory=list)
    purged_payloads: int = 0


@dataclass(frozen=True, slots=True)
class LoginResult:
    operator: Operator
    session: Session
    language: str


@dataclass(frozen=True, slots=True)
class LogoutResult:
    session: Session
    summary: SessionSummary
    queued: QueuedReport | None = None
    report_error: ParkomateError | None = None
    """Set when report files / e-mail could not be prepared (data is still in the DB)."""


class Station:
    def __init__(
        self,
        repos: Repositories,
        records: ProductionRecords,
        auth: AuthService,
        reporter: SessionReporter,
        outbox: OutboxService,
        settings: Callable[[], Settings],
    ) -> None:
        self._repos = repos
        self._records = records
        self._auth = auth
        self._reporter = reporter
        self._outbox = outbox
        self._settings = settings

    @property
    def records(self) -> ProductionRecords:
        return self._records

    @property
    def auth(self) -> AuthService:
        return self._auth

    @property
    def outbox(self) -> OutboxService:
        return self._outbox

    def startup(self) -> StartupResult:
        recovery = recover_unclosed_sessions(self._repos)
        queued: list[QueuedReport] = []
        errors: list[ParkomateError] = []
        for session_id in recovery.session_ids:
            try:
                queued.append(self._reporter.queue_session_report(session_id))
            except ParkomateError as exc:
                log.exception("could not queue report of recovered session %d", session_id)
                errors.append(exc)
        purged = self._outbox.purge()
        return StartupResult(recovery, queued, errors, purged)

    def login(self, operator_code: str, password: str) -> LoginResult:
        operator = self._auth.authenticate(operator_code, password)
        language = operator.language or self._settings().station.language
        self._records.station_id = self._settings().station.station_id
        session = self._records.start_session(operator, language=language)
        return LoginResult(operator, session, language)

    def logout(self, reason: SessionEndReason = SessionEndReason.LOGOUT) -> LogoutResult:
        operator = self._records.require_operator()
        session = self._records.end_session(reason)
        self._auth.record_logout(operator, reason)
        try:
            queued = self._reporter.queue_session_report(session.id)
        except ParkomateError as exc:
            log.exception("report for session %d could not be prepared", session.id)
            summary = self._records.session_summary(session.id)
            return LogoutResult(session, summary, None, exc)
        return LogoutResult(session, queued.summary, queued)

    def send_pending(self) -> SendReport:
        """Send due e-mails (call from a worker thread)."""
        return self._outbox.process_due()
