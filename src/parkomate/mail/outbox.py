"""Durable e-mail outbox.

Rule: **a report is queued before any send is attempted**, so a failing network, server or
password never loses it.

* :meth:`OutboxService.enqueue` writes the complete MIME message (``.eml``) to the outbox
  folder and inserts a ``pending`` row.
* :meth:`OutboxService.process_due` sends every pending item whose retry time has come
  (called after session close, at start-up and periodically by the UI).
* Failures back off exponentially (``retry_base_s * 2^(attempt-1)``, capped at
  ``retry_max_s``); after ``max_attempts`` the item becomes ``failed`` and waits for an
  admin "Resend".
* Recipients and sender are taken from the *current* settings at send time, so fixing a
  wrong address and pressing Resend works.
* :meth:`OutboxService.purge` deletes payload files of items sent more than
  ``retention_days`` ago (rows are kept).
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

from parkomate.auth.service import require_admin
from parkomate.config.settings import EmailSettings
from parkomate.core.enums import OutboxStatus
from parkomate.core.errors import ErrorCode, MailError, ParkomateError
from parkomate.core.models import Operator, OutboxItem
from parkomate.data import Repositories
from parkomate.mail.mailers import Mailer

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SendReport:
    sent: int = 0
    failed: int = 0
    skipped: bool = False  # e-mail disabled


class OutboxService:
    def __init__(
        self,
        repos: Repositories,
        outbox_dir: Path,
        mailer: Mailer,
        settings: Callable[[], EmailSettings],
        retention_days: Callable[[], int],
    ) -> None:
        self._repos = repos
        self._dir = outbox_dir
        self._mailer = mailer
        self._settings = settings
        self._retention_days = retention_days
        self._send_lock = threading.Lock()

    # ------------------------------------------------------------------ queue
    def enqueue(self, message: EmailMessage, session_id: int | None) -> OutboxItem:
        """Persist ``message`` and add a pending outbox row."""
        self._dir.mkdir(parents=True, exist_ok=True)
        stamp = self._repos.clock.now().strftime("%Y%m%dT%H%M%SZ")
        path = self._dir / f"{stamp}_s{session_id or 0}_{uuid.uuid4().hex[:8]}.eml"
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(message.as_bytes(policy=policy.SMTP))
        tmp.replace(path)
        item = self._repos.outbox.add(session_id, str(message.get("Subject", "")), str(path))
        log.info("e-mail queued (outbox item %d, session %s)", item.id, session_id)
        return item

    def list_items(self, status: OutboxStatus | None = None) -> list[OutboxItem]:
        return self._repos.outbox.list_items(status=status)

    def counts(self) -> dict[OutboxStatus, int]:
        return self._repos.outbox.count_by_status()

    # ------------------------------------------------------------------ sending
    def backoff_seconds(self, attempts: int) -> float:
        settings = self._settings()
        return float(min(settings.retry_base_s * 2 ** max(0, attempts - 1), settings.retry_max_s))

    def process_due(self) -> SendReport:
        """Send every pending item that is due. Never raises."""
        if not self._settings().enabled:
            return SendReport(skipped=True)
        sent = failed = 0
        for item in self._repos.outbox.due(self._repos.clock.now()):
            if self.send_item(item.id):
                sent += 1
            else:
                failed += 1
        return SendReport(sent=sent, failed=failed)

    def send_item(self, item_id: int) -> bool:
        """Try to send one item now. Returns True when sent. Never raises."""
        with self._send_lock:
            try:
                item = self._repos.outbox.require(item_id)
            except ParkomateError:
                log.exception("outbox item %d vanished", item_id)
                return False
            if item.status is OutboxStatus.SENT:
                return True
            try:
                message = self._load(item)
                self._mailer.send(message)
            except (ParkomateError, OSError) as exc:
                self._record_failure(item, exc)
                return False
            self._repos.outbox.mark_sent(item.id)
            log.info("outbox item %d sent", item.id)
            return True

    def resend(self, actor: Operator, item_id: int) -> bool:
        """Admin action: put a (failed or pending) item back in the queue and send now."""
        require_admin(actor)
        self._repos.outbox.reset_for_resend(item_id)
        self._repos.audit.record(actor.id, "outbox.resend", {"item_id": item_id})
        return self.send_item(item_id)

    def _load(self, item: OutboxItem) -> EmailMessage:
        if not item.payload_path:
            raise MailError("payload missing", code=ErrorCode.MAIL_FAILED)
        raw = Path(item.payload_path).read_bytes()
        message = BytesParser(policy=policy.default).parsebytes(raw)
        if not isinstance(message, EmailMessage):  # pragma: no cover - policy.default guarantees
            raise MailError("payload is not an e-mail message")
        settings = self._settings()
        if settings.recipients:
            del message["To"]
            message["To"] = ", ".join(settings.recipients)
        if settings.sender:
            del message["From"]
            message["From"] = settings.sender
        return message

    def _record_failure(self, item: OutboxItem, exc: Exception) -> None:
        settings = self._settings()
        attempts = item.attempts + 1
        give_up = attempts >= settings.max_attempts
        next_at = (
            None
            if give_up
            else self._repos.clock.now() + timedelta(seconds=self.backoff_seconds(attempts))
        )
        code = exc.code.value if isinstance(exc, ParkomateError) else ErrorCode.MAIL_FAILED.value
        error_text = f"{code}: {exc}"
        self._repos.outbox.mark_attempt_failed(
            item.id, error_text, next_attempt_at=next_at, give_up=give_up
        )
        log.error(
            "e-mail send failed (outbox item %d, attempt %d%s)",
            item.id,
            attempts,
            ", giving up" if give_up else "",
            extra={"error_code": code, "context": {"outbox_id": item.id, "attempt": attempts}},
        )

    # ------------------------------------------------------------------ retention
    def purge(self) -> int:
        """Delete payload files of items sent more than ``retention_days`` ago."""
        cutoff = self._repos.clock.now() - timedelta(days=self._retention_days())
        removed = 0
        for item in self._repos.outbox.sent_with_payload_before(cutoff):
            if item.payload_path:
                try:
                    Path(item.payload_path).unlink(missing_ok=True)
                except OSError:
                    log.exception("cannot delete outbox payload %s", item.payload_path)
                    continue
            self._repos.outbox.set_payload_path(item.id, None)
            removed += 1
        if removed:
            log.info("purged %d sent e-mail payload(s) older than %s", removed, cutoff.date())
        return removed
