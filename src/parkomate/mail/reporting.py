"""Session close -> report files -> e-mail queued in the outbox."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from parkomate.config.settings import Settings
from parkomate.core.models import OutboxItem, SessionSummary
from parkomate.data import Repositories
from parkomate.mail.compose import compose_session_email
from parkomate.mail.outbox import OutboxService
from parkomate.reports.exporter import ReportExporter
from parkomate.reports.summary import build_session_summary

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class QueuedReport:
    session_id: int
    summary: SessionSummary
    report_paths: list[Path] = field(default_factory=list)
    outbox_item: OutboxItem | None = None
    """``None`` when e-mail is disabled (reports are still written to disk)."""


class SessionReporter:
    def __init__(
        self,
        repos: Repositories,
        exporter: ReportExporter,
        outbox: OutboxService,
        settings: Callable[[], Settings],
    ) -> None:
        self._repos = repos
        self._exporter = exporter
        self._outbox = outbox
        self._settings = settings

    def queue_session_report(self, session_id: int) -> QueuedReport:
        """Write the report files and queue the summary e-mail (no send attempt here)."""
        settings = self._settings()
        summary = build_session_summary(self._repos, session_id)
        paths = self._exporter.export_session(session_id)
        item: OutboxItem | None = None
        if settings.email.enabled:
            message = compose_session_email(
                summary,
                paths,
                settings=settings.email,
                station_id=summary.session.station_id,
                lang=settings.reports.language,
            )
            item = self._outbox.enqueue(message, session_id)
        else:
            log.info("e-mail disabled - session %d report kept on disk only", session_id)
        return QueuedReport(session_id, summary, paths, item)
