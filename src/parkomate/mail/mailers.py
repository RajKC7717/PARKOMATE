"""Mail transports.

* :class:`Mailer` - the interface the outbox uses.
* :class:`SmtpMailer` - SMTP with STARTTLS or implicit TLS, password from the keyring.
* :class:`OAuth2SmtpMailer` - SMTP XOAUTH2 (Microsoft 365 / Gmail). Token acquisition is a
  placeholder: see the class docstring.

Security ``"none"`` means a plain, unauthenticated relay on the local network: the password
is never sent over an unencrypted connection.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage
from typing import Protocol

from parkomate.config.secrets import SecretStore, require_secret
from parkomate.config.settings import EmailSettings
from parkomate.core.errors import ErrorCode, MailError

log = logging.getLogger(__name__)


class Mailer(Protocol):
    def send(self, message: EmailMessage) -> None:
        """Deliver ``message`` or raise a ``ParkomateError`` (normally ``MailError``)."""
        ...


SmtpFactory = Callable[[EmailSettings, ssl.SSLContext], smtplib.SMTP]


def _default_factory(settings: EmailSettings, context: ssl.SSLContext) -> smtplib.SMTP:
    if settings.security == "ssl":
        return smtplib.SMTP_SSL(
            settings.host, settings.port, timeout=settings.timeout_s, context=context
        )
    return smtplib.SMTP(settings.host, settings.port, timeout=settings.timeout_s)


class SmtpMailer:
    """SMTP with username/password (password read from the keyring at send time)."""

    def __init__(
        self,
        settings: Callable[[], EmailSettings],
        secrets: SecretStore,
        *,
        smtp_factory: SmtpFactory | None = None,
    ) -> None:
        self._settings = settings
        self._secrets = secrets
        self._factory = smtp_factory or _default_factory

    def send(self, message: EmailMessage) -> None:
        settings = self._settings()
        if not settings.enabled or not settings.host:
            raise MailError("e-mail is disabled or has no host", code=ErrorCode.MAIL_NOT_CONFIGURED)
        context = ssl.create_default_context()
        try:
            with self._factory(settings, context) as smtp:
                smtp.ehlo()
                if settings.security == "starttls":
                    smtp.starttls(context=context)
                    smtp.ehlo()
                if settings.security != "none":
                    self._authenticate(smtp, settings)
                smtp.send_message(message)
        except smtplib.SMTPAuthenticationError as exc:
            raise MailError(
                f"SMTP authentication failed ({exc.smtp_code})",
                context={"host": settings.host, "smtp_code": exc.smtp_code},
            ) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise MailError(
                "all recipients refused", context={"recipients": list(exc.recipients)}
            ) from exc
        except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
            raise MailError(
                f"SMTP delivery failed: {type(exc).__name__}: {exc}",
                context={"host": settings.host, "port": settings.port},
            ) from exc
        log.info("e-mail %r sent via %s", message.get("Subject", ""), settings.host)

    def _authenticate(self, smtp: smtplib.SMTP, settings: EmailSettings) -> None:
        password = require_secret(self._secrets, settings.password_ref)
        smtp.login(settings.login, password)


class TokenProvider(Protocol):
    def access_token(self) -> str:
        """A currently valid OAuth2 access token with the SMTP.Send scope."""
        ...


class KeyringTokenProvider:
    """Reads an access token that an administrator stored in the keyring.

    TODO(oauth): replace with a real token flow before Microsoft disables SMTP basic auth by
    default (end of December 2026). Recommended: MSAL ``ConfidentialClientApplication`` with
    the client-credentials grant for Microsoft 365 (``https://outlook.office365.com/.default``),
    or Google's service-account flow for Gmail, with the refresh token / client secret kept in
    the keyring and the access token refreshed ~5 minutes before expiry.
    """

    def __init__(self, secrets: SecretStore, settings: Callable[[], EmailSettings]) -> None:
        self._secrets = secrets
        self._settings = settings

    def access_token(self) -> str:
        return require_secret(self._secrets, self._settings().oauth_token_ref)


def xoauth2_string(user: str, token: str) -> str:
    """SASL XOAUTH2 initial client response (before base64, which smtplib adds)."""
    return f"user={user}\x01auth=Bearer {token}\x01\x01"


class OAuth2SmtpMailer(SmtpMailer):
    """SMTP with SASL XOAUTH2 (Microsoft 365, Gmail).

    The transport part is complete; only token *acquisition* is a placeholder - see
    :class:`KeyringTokenProvider`. Plug a real :class:`TokenProvider` in via ``tokens``.
    """

    def __init__(
        self,
        settings: Callable[[], EmailSettings],
        secrets: SecretStore,
        *,
        tokens: TokenProvider | None = None,
        smtp_factory: SmtpFactory | None = None,
    ) -> None:
        super().__init__(settings, secrets, smtp_factory=smtp_factory)
        self._tokens = tokens or KeyringTokenProvider(secrets, settings)

    def _authenticate(self, smtp: smtplib.SMTP, settings: EmailSettings) -> None:
        token = self._tokens.access_token()
        auth_string = xoauth2_string(settings.login, token)
        smtp.auth("XOAUTH2", lambda challenge=None: auth_string, initial_response_ok=True)


def create_mailer(settings: Callable[[], EmailSettings], secrets: SecretStore) -> Mailer:
    """Mailer for the configured ``email.auth_method`` (re-evaluated on every send)."""
    password = SmtpMailer(settings, secrets)
    oauth = OAuth2SmtpMailer(settings, secrets)

    class _Switching:
        def send(self, message: EmailMessage) -> None:
            chosen: Mailer = oauth if settings().auth_method == "oauth2" else password
            chosen.send(message)

    return _Switching()
