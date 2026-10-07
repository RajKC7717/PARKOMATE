"""Mailer interface, SMTP / OAuth2 transports, durable outbox with retry (owner: Yugant)."""

from parkomate.mail.compose import compose_session_email
from parkomate.mail.mailers import (
    KeyringTokenProvider,
    Mailer,
    OAuth2SmtpMailer,
    SmtpMailer,
    TokenProvider,
    create_mailer,
)
from parkomate.mail.outbox import OutboxService, SendReport
from parkomate.mail.reporting import QueuedReport, SessionReporter

__all__ = [
    "KeyringTokenProvider",
    "Mailer",
    "OAuth2SmtpMailer",
    "OutboxService",
    "QueuedReport",
    "SendReport",
    "SessionReporter",
    "SmtpMailer",
    "TokenProvider",
    "compose_session_email",
    "create_mailer",
]
