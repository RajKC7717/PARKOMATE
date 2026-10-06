"""Typed errors.

Every failure that can reach an operator is a :class:`ParkomateError` carrying an
:class:`ErrorCode`. The code decides the severity and the i18n keys the UI shows:

* ``error.<code>.title``  - short headline ("Board not connected")
* ``error.<code>.cause``  - one-line cause
* ``error.<code>.action`` - fix steps, one per line (the UI numbers them)

``str(err)`` is the technical message for logs only; it is never shown as UI text.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, ClassVar

from parkomate.core.enums import Severity


class ErrorCode(StrEnum):
    # Hardware / serial (Aditya)
    HW_COM_DISCONNECTED = "HW_COM_DISCONNECTED"
    HW_NO_PORT = "HW_NO_PORT"
    HW_PORT_BUSY = "HW_PORT_BUSY"
    HW_TIMEOUT = "HW_TIMEOUT"
    HW_DEVICE_ERROR = "HW_DEVICE_ERROR"
    HW_FLASH_FAILED = "HW_FLASH_FAILED"
    HW_HOLD_BOOT = "HW_HOLD_BOOT"
    # Server API (Aditya)
    API_UNREACHABLE = "API_UNREACHABLE"
    API_UNAUTHORISED = "API_UNAUTHORISED"
    API_BAD_RESPONSE = "API_BAD_RESPONSE"
    WHITELIST_DENIED = "WHITELIST_DENIED"
    FW_HASH_MISMATCH = "FW_HASH_MISMATCH"
    FW_NOT_LOADED = "FW_NOT_LOADED"
    # Measurement device (Aditya)
    MEAS_TIMEOUT = "MEAS_TIMEOUT"
    MEAS_BAD_DATA = "MEAS_BAD_DATA"
    # Camera / identity (Aditya + Piyush)
    CAM_NOT_FOUND = "CAM_NOT_FOUND"
    QR_UNREADABLE = "QR_UNREADABLE"
    QR_BAD_FORMAT = "QR_BAD_FORMAT"
    ID_WRITE_FAILED = "ID_WRITE_FAILED"
    # Backend (Yugant)
    MAIL_FAILED = "MAIL_FAILED"
    MAIL_NOT_CONFIGURED = "MAIL_NOT_CONFIGURED"
    DB_ERROR = "DB_ERROR"
    SETTINGS_INVALID = "SETTINGS_INVALID"
    SECRET_MISSING = "SECRET_MISSING"
    REPORT_FAILED = "REPORT_FAILED"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_LOCKED = "AUTH_LOCKED"
    AUTH_INACTIVE = "AUTH_INACTIVE"
    AUTH_WEAK_PASSWORD = "AUTH_WEAK_PASSWORD"
    AUTH_DUPLICATE_OPERATOR = "AUTH_DUPLICATE_OPERATOR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INVALID_STATE = "INVALID_STATE"
    NOT_FOUND = "NOT_FOUND"
    UNEXPECTED = "UNEXPECTED"

    @property
    def severity(self) -> Severity:
        return _SEVERITY.get(self, Severity.ERROR)

    @property
    def i18n_base(self) -> str:
        return f"error.{self.value.lower()}"

    @property
    def title_key(self) -> str:
        return f"{self.i18n_base}.title"

    @property
    def cause_key(self) -> str:
        return f"{self.i18n_base}.cause"

    @property
    def action_key(self) -> str:
        return f"{self.i18n_base}.action"


_SEVERITY: dict[ErrorCode, Severity] = {
    ErrorCode.HW_COM_DISCONNECTED: Severity.ERROR,
    ErrorCode.HW_NO_PORT: Severity.WARNING,
    ErrorCode.HW_PORT_BUSY: Severity.WARNING,
    ErrorCode.HW_TIMEOUT: Severity.WARNING,
    ErrorCode.HW_DEVICE_ERROR: Severity.ERROR,
    ErrorCode.HW_FLASH_FAILED: Severity.ERROR,
    ErrorCode.HW_HOLD_BOOT: Severity.WARNING,
    ErrorCode.API_UNREACHABLE: Severity.ERROR,
    ErrorCode.API_UNAUTHORISED: Severity.CRITICAL,
    ErrorCode.API_BAD_RESPONSE: Severity.ERROR,
    ErrorCode.WHITELIST_DENIED: Severity.WARNING,
    ErrorCode.FW_HASH_MISMATCH: Severity.CRITICAL,
    ErrorCode.FW_NOT_LOADED: Severity.ERROR,
    ErrorCode.MEAS_TIMEOUT: Severity.WARNING,
    ErrorCode.MEAS_BAD_DATA: Severity.ERROR,
    ErrorCode.CAM_NOT_FOUND: Severity.ERROR,
    ErrorCode.QR_UNREADABLE: Severity.WARNING,
    ErrorCode.QR_BAD_FORMAT: Severity.WARNING,
    ErrorCode.ID_WRITE_FAILED: Severity.ERROR,
    ErrorCode.MAIL_FAILED: Severity.WARNING,
    ErrorCode.MAIL_NOT_CONFIGURED: Severity.WARNING,
    ErrorCode.DB_ERROR: Severity.CRITICAL,
    ErrorCode.SETTINGS_INVALID: Severity.CRITICAL,
    ErrorCode.SECRET_MISSING: Severity.ERROR,
    ErrorCode.REPORT_FAILED: Severity.ERROR,
    ErrorCode.AUTH_INVALID_CREDENTIALS: Severity.WARNING,
    ErrorCode.AUTH_LOCKED: Severity.WARNING,
    ErrorCode.AUTH_INACTIVE: Severity.WARNING,
    ErrorCode.AUTH_WEAK_PASSWORD: Severity.WARNING,
    ErrorCode.AUTH_DUPLICATE_OPERATOR: Severity.WARNING,
    ErrorCode.PERMISSION_DENIED: Severity.WARNING,
    ErrorCode.INVALID_STATE: Severity.ERROR,
    ErrorCode.NOT_FOUND: Severity.ERROR,
    ErrorCode.UNEXPECTED: Severity.CRITICAL,
}


class ParkomateError(Exception):
    """Base class for every error the application raises on purpose.

    Args:
        message: technical description for logs (English, never shown to operators).
        code: overrides the class default code.
        params: values substituted into the i18n title/cause/action texts.
        context: extra structured data written to ``errors.jsonl`` (never secrets).
    """

    default_code: ClassVar[ErrorCode] = ErrorCode.UNEXPECTED

    def __init__(
        self,
        message: str = "",
        *,
        code: ErrorCode | None = None,
        params: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self.code: ErrorCode = code or self.default_code
        self.params: dict[str, Any] = dict(params or {})
        self.context: dict[str, Any] = dict(context or {})
        super().__init__(message or self.code.value)

    @property
    def message(self) -> str:
        return str(self)

    @property
    def severity(self) -> Severity:
        return self.code.severity

    @property
    def title_key(self) -> str:
        return self.code.title_key

    @property
    def cause_key(self) -> str:
        return self.code.cause_key

    @property
    def action_key(self) -> str:
        return self.code.action_key

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code.value!r}, message={self.message!r})"


class HardwareError(ParkomateError):
    default_code = ErrorCode.HW_DEVICE_ERROR


class ServerError(ParkomateError):
    default_code = ErrorCode.API_UNREACHABLE


class MeasurementError(ParkomateError):
    default_code = ErrorCode.MEAS_TIMEOUT


class CameraError(ParkomateError):
    default_code = ErrorCode.CAM_NOT_FOUND


class MailError(ParkomateError):
    default_code = ErrorCode.MAIL_FAILED


class DatabaseError(ParkomateError):
    default_code = ErrorCode.DB_ERROR


class SettingsError(ParkomateError):
    """Settings file missing, unreadable or invalid.

    ``problems`` lists ``(dotted.key, problem)`` pairs so the start-up message can name
    the exact key.
    """

    default_code = ErrorCode.SETTINGS_INVALID

    def __init__(
        self,
        message: str = "",
        *,
        problems: list[tuple[str, str]] | None = None,
        code: ErrorCode | None = None,
        params: Mapping[str, Any] | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self.problems: list[tuple[str, str]] = list(problems or [])
        super().__init__(message, code=code, params=params, context=context)


class SecretMissingError(ParkomateError):
    default_code = ErrorCode.SECRET_MISSING


class ReportError(ParkomateError):
    default_code = ErrorCode.REPORT_FAILED


class AuthError(ParkomateError):
    default_code = ErrorCode.AUTH_INVALID_CREDENTIALS


class PermissionDeniedError(ParkomateError):
    default_code = ErrorCode.PERMISSION_DENIED


class RecordStateError(ParkomateError):
    """An operation is not allowed in the current record state (e.g. completing a rejected
    device)."""

    default_code = ErrorCode.INVALID_STATE


class NotFoundError(ParkomateError):
    default_code = ErrorCode.NOT_FOUND
