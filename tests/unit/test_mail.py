"""Mail: composition, SMTP transport, outbox queue/retry/resend/purge."""

from __future__ import annotations

import smtplib
from datetime import timedelta
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest

from parkomate.config.secrets import MemorySecretStore
from parkomate.config.settings import EmailSettings, Settings
from parkomate.core.clock import FakeClock
from parkomate.core.enums import OutboxStatus, SessionEndReason
from parkomate.core.errors import ErrorCode, MailError, PermissionDeniedError, SecretMissingError
from parkomate.core.models import Operator
from parkomate.data import Repositories
from parkomate.data.records import ProductionRecords
from parkomate.mail.compose import compose_session_email
from parkomate.mail.mailers import (
    OAuth2SmtpMailer,
    SmtpMailer,
    create_mailer,
    xoauth2_string,
)
from parkomate.mail.outbox import OutboxService
from parkomate.mail.reporting import SessionReporter
from parkomate.reports.exporter import ReportExporter

EMAIL = EmailSettings(
    enabled=True,
    recipients=["qa@parkomate.example"],
    sender="station@parkomate.example",
    host="smtp.example.com",
    max_attempts=3,
    retry_base_s=60,
    retry_max_s=100,
)


class FakeMailer:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.fail_with: Exception | None = None

    def send(self, message: EmailMessage) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append(message)


class FakeSMTP:
    def __init__(self, fail_login: bool = False, fail_send: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.fail_login = fail_login
        self.fail_send = fail_send

    def __enter__(self) -> FakeSMTP:
        return self

    def __exit__(self, *exc: object) -> None:
        self.calls.append("quit")

    def ehlo(self) -> None:
        self.calls.append("ehlo")

    def starttls(self, context: Any) -> None:
        self.calls.append("starttls")

    def login(self, user: str, password: str) -> None:
        if self.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
        self.calls.append(f"login:{user}:{password}")

    def auth(self, mechanism: str, authobject: Any, initial_response_ok: bool = True) -> None:
        self.calls.append(f"auth:{mechanism}:{authobject()}")

    def send_message(self, message: EmailMessage) -> None:
        if self.fail_send is not None:
            raise self.fail_send
        self.calls.append(f"send:{message['To']}")


def _message(subject: str = "Report") -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = "old@parkomate.example"
    message["To"] = "old-recipient@parkomate.example"
    message.set_content("body")
    return message


@pytest.fixture
def email_settings() -> dict[str, EmailSettings]:
    return {"value": EMAIL}


@pytest.fixture
def outbox(
    repos: Repositories, tmp_path: Path, email_settings: dict[str, EmailSettings]
) -> tuple[OutboxService, FakeMailer]:
    mailer = FakeMailer()
    service = OutboxService(
        repos, tmp_path / "outbox", mailer, lambda: email_settings["value"], lambda: 30
    )
    return service, mailer


# ------------------------------------------------------------------ outbox


def test_enqueue_persists_before_any_send(outbox: tuple[OutboxService, FakeMailer]) -> None:
    service, mailer = outbox
    item = service.enqueue(_message(), None)
    assert item.status is OutboxStatus.PENDING
    assert item.payload_path is not None and Path(item.payload_path).read_bytes()
    assert mailer.sent == []


def test_send_uses_current_recipients(outbox: tuple[OutboxService, FakeMailer]) -> None:
    service, mailer = outbox
    item = service.enqueue(_message(), None)
    report = service.process_due()
    assert (report.sent, report.failed) == (1, 0)
    assert mailer.sent[0]["To"] == "qa@parkomate.example"
    assert mailer.sent[0]["From"] == "station@parkomate.example"
    assert service.list_items(OutboxStatus.SENT)[0].id == item.id
    assert service.send_item(item.id)  # already sent -> True, not re-sent
    assert len(mailer.sent) == 1


def test_failures_back_off_then_give_up(
    outbox: tuple[OutboxService, FakeMailer], repos: Repositories, clock: FakeClock
) -> None:
    service, mailer = outbox
    mailer.fail_with = MailError("smtp down")
    item = service.enqueue(_message(), None)
    assert service.process_due().failed == 1
    first = repos.outbox.require(item.id)
    assert first.status is OutboxStatus.PENDING and first.attempts == 1
    assert first.next_attempt_at == clock.now() + timedelta(seconds=60)
    assert first.last_error is not None and first.last_error.startswith("MAIL_FAILED")
    assert service.process_due().failed == 0  # not due yet
    clock.advance(seconds=60)
    service.process_due()
    second = repos.outbox.require(item.id)
    assert second.next_attempt_at == clock.now() + timedelta(seconds=100)  # capped
    clock.advance(seconds=100)
    service.process_due()
    final = repos.outbox.require(item.id)
    assert final.status is OutboxStatus.FAILED and final.attempts == 3
    assert final.next_attempt_at is None
    assert service.counts()[OutboxStatus.FAILED] == 1
    assert service.backoff_seconds(1) == 60 and service.backoff_seconds(5) == 100


def test_os_errors_also_retry(
    outbox: tuple[OutboxService, FakeMailer], repos: Repositories
) -> None:
    service, mailer = outbox
    mailer.fail_with = OSError("network unreachable")
    item = service.enqueue(_message(), None)
    assert not service.send_item(item.id)
    assert repos.outbox.require(item.id).attempts == 1


def test_missing_payload_is_a_failed_attempt(
    outbox: tuple[OutboxService, FakeMailer], repos: Repositories
) -> None:
    service, _ = outbox
    item = service.enqueue(_message(), None)
    Path(item.payload_path or "").unlink()
    assert not service.send_item(item.id)
    repos.outbox.set_payload_path(item.id, None)
    assert not service.send_item(item.id)
    assert not service.send_item(12345)


def test_resend_admin_only(
    outbox: tuple[OutboxService, FakeMailer],
    repos: Repositories,
    admin: Operator,
    operator: Operator,
) -> None:
    service, mailer = outbox
    mailer.fail_with = MailError("down")
    item = service.enqueue(_message(), None)
    for _ in range(3):
        repos.outbox.mark_attempt_failed(item.id, "x", next_attempt_at=None, give_up=True)
    with pytest.raises(PermissionDeniedError):
        service.resend(operator, item.id)
    mailer.fail_with = None
    assert service.resend(admin, item.id)
    assert repos.outbox.require(item.id).status is OutboxStatus.SENT
    assert repos.audit.list_entries(action="outbox.resend")[0].details == {"item_id": item.id}


def test_disabled_email_skips_sending(
    outbox: tuple[OutboxService, FakeMailer], email_settings: dict[str, EmailSettings]
) -> None:
    service, mailer = outbox
    service.enqueue(_message(), None)
    email_settings["value"] = EmailSettings()
    assert service.process_due().skipped
    assert mailer.sent == []


def test_purge_old_sent_payloads(
    outbox: tuple[OutboxService, FakeMailer], repos: Repositories, clock: FakeClock
) -> None:
    service, _ = outbox
    old = service.enqueue(_message("old"), None)
    service.process_due()
    clock.advance(days=31)
    recent = service.enqueue(_message("recent"), None)
    service.process_due()
    pending = service.enqueue(_message("pending"), None)
    assert service.purge() == 1
    assert not Path(old.payload_path or "").exists()
    assert repos.outbox.require(old.id).payload_path is None  # row kept
    assert Path(recent.payload_path or "").exists()
    assert Path(pending.payload_path or "").exists()


# ------------------------------------------------------------------ SMTP transport


def _smtp_mailer(
    settings: EmailSettings, smtp: FakeSMTP, secrets: MemorySecretStore | None = None
) -> SmtpMailer:
    return SmtpMailer(
        lambda: settings,
        secrets or MemorySecretStore({"smtp_password": "pw"}),
        smtp_factory=lambda _s, _ctx: smtp,  # type: ignore[arg-type,return-value]
    )


def test_smtp_starttls_login_send() -> None:
    smtp = FakeSMTP()
    _smtp_mailer(EMAIL, smtp).send(_message())
    assert smtp.calls == [
        "ehlo",
        "starttls",
        "ehlo",
        "login:station@parkomate.example:pw",
        "send:old-recipient@parkomate.example",
        "quit",
    ]


def test_smtp_relay_without_tls_never_sends_password() -> None:
    smtp = FakeSMTP()
    _smtp_mailer(EMAIL.model_copy(update={"security": "none"}), smtp).send(_message())
    assert not any(call.startswith(("login", "starttls")) for call in smtp.calls)


def test_smtp_errors_are_typed() -> None:
    with pytest.raises(MailError, match="authentication"):
        _smtp_mailer(EMAIL, FakeSMTP(fail_login=True)).send(_message())
    with pytest.raises(MailError, match="delivery failed"):
        _smtp_mailer(EMAIL, FakeSMTP(fail_send=smtplib.SMTPServerDisconnected("gone"))).send(
            _message()
        )
    refused = smtplib.SMTPRecipientsRefused({"x@y.z": (550, b"no")})
    with pytest.raises(MailError, match="refused"):
        _smtp_mailer(EMAIL, FakeSMTP(fail_send=refused)).send(_message())
    with pytest.raises(SecretMissingError):
        _smtp_mailer(EMAIL, FakeSMTP(), MemorySecretStore()).send(_message())
    with pytest.raises(MailError) as info:
        _smtp_mailer(EmailSettings(), FakeSMTP()).send(_message())
    assert info.value.code is ErrorCode.MAIL_NOT_CONFIGURED


def test_oauth2_xoauth2() -> None:
    assert xoauth2_string("a@b.c", "tok") == "user=a@b.c\x01auth=Bearer tok\x01\x01"
    smtp = FakeSMTP()
    settings = EMAIL.model_copy(update={"auth_method": "oauth2"})
    mailer = OAuth2SmtpMailer(
        lambda: settings,
        MemorySecretStore({"smtp_oauth_token": "tok"}),
        smtp_factory=lambda _s, _ctx: smtp,  # type: ignore[arg-type,return-value]
    )
    mailer.send(_message())
    assert "auth:XOAUTH2:user=station@parkomate.example\x01auth=Bearer tok\x01\x01" in smtp.calls


def test_create_mailer_switches_on_auth_method(monkeypatch: pytest.MonkeyPatch) -> None:
    used: list[str] = []
    monkeypatch.setattr(SmtpMailer, "send", lambda self, m: used.append(type(self).__name__))
    monkeypatch.setattr(OAuth2SmtpMailer, "send", lambda self, m: used.append("oauth"))
    current = {"value": EMAIL}
    mailer = create_mailer(lambda: current["value"], MemorySecretStore())
    mailer.send(_message())
    current["value"] = EMAIL.model_copy(update={"auth_method": "oauth2"})
    mailer.send(_message())
    assert used == ["SmtpMailer", "oauth"]


# ------------------------------------------------------------------ session e-mail


def test_session_report_queued_with_attachment(
    open_session: ProductionRecords, tmp_path: Path, repos: Repositories
) -> None:
    settings = Settings(email=EMAIL)
    mailer = FakeMailer()
    outbox = OutboxService(repos, tmp_path / "outbox", mailer, lambda: settings.email, lambda: 30)
    exporter = ReportExporter(repos, tmp_path / "reports", lambda: settings.reports, lambda: "S1")
    reporter = SessionReporter(repos, exporter, outbox, lambda: settings)
    session = open_session.end_session(SessionEndReason.LOGOUT)
    queued = reporter.queue_session_report(session.id)
    assert queued.outbox_item is not None and len(queued.report_paths) == 1
    assert mailer.sent == []  # queued only
    outbox.process_due()
    message = mailer.sent[0]
    assert message["Subject"].startswith("[Parkomate] Station ST-TEST - session")
    attachments = list(message.iter_attachments())
    assert attachments[0].get_filename() == queued.report_paths[0].name
    body = message.get_body(preferencelist=("plain",))
    assert body is not None and "Devices started" in body.get_content()
    html = message.get_body(preferencelist=("html",))
    assert html is not None and "<table" in html.get_content()


def test_session_report_without_email(
    open_session: ProductionRecords, tmp_path: Path, repos: Repositories
) -> None:
    settings = Settings()
    outbox = OutboxService(repos, tmp_path / "o", FakeMailer(), lambda: settings.email, lambda: 1)
    exporter = ReportExporter(repos, tmp_path / "r", lambda: settings.reports, lambda: "S1")
    reporter = SessionReporter(repos, exporter, outbox, lambda: settings)
    session = open_session.end_session(SessionEndReason.LOGOUT)
    queued = reporter.queue_session_report(session.id)
    assert queued.outbox_item is None and queued.report_paths[0].exists()


def test_compose_marathi(open_session: ProductionRecords, tmp_path: Path) -> None:
    summary = open_session.current_session_summary()
    attachment = tmp_path / "r.csv"
    attachment.write_text("a,b", encoding="utf-8")
    message = compose_session_email(
        summary, [attachment], settings=EMAIL, station_id="S1", lang="mr"
    )
    plain = message.get_body(preferencelist=("plain",))
    assert plain is not None and "सुरू केलेली डिव्हाइसेस" in plain.get_content()
    assert next(message.iter_attachments()).get_content_type() == "text/csv"
