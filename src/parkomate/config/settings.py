"""Typed, validated station settings (``settings.toml``).

Every section is a frozen pydantic model with ``extra="forbid"``: an unknown or misspelt
key is an error, which also stops anybody from pasting a password into the file. Secrets
live in the OS keyring; the file only holds the *names* of keyring entries (``*_ref``).
"""

from __future__ import annotations

import ipaddress
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from parkomate.core.enums import MAX_SENSOR_READINGS

LanguageCode = Literal["en", "mr"]
SUPPORTED_LANGUAGES: tuple[str, ...] = ("en", "mr")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_STATION_RE = r"^[A-Za-z0-9_-]{1,32}$"
_SECRET_REF_RE = r"^[A-Za-z0-9_.-]{1,64}$"

PositiveFloat = Annotated[float, Field(gt=0)]


class _Section(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StationSettings(_Section):
    station_id: str = Field(default="STATION-01", pattern=_STATION_RE)
    language: LanguageCode = "en"
    """Default UI language; each operator's own choice is remembered separately."""


class LimitsSettings(_Section):
    """Pass limits. Every range is inclusive: ``low <= value <= high``."""

    v_a_low: float = 23.85
    v_a_high: float = 24.15
    v_b_low: float = 4.90
    v_b_high: float = 5.10
    v_c_low: float = 3.25
    v_c_high: float = 3.35
    temp_margin_c: float = Field(default=3.0, ge=0, le=50)
    """Regulator temperature may be at most ``ambient + temp_margin_c``."""
    sensor_reading_count: int = Field(default=5, ge=1, le=MAX_SENSOR_READINGS)
    decimals: int = Field(default=2, ge=0, le=6)
    """Measured values are rounded to this many decimals before comparison."""

    @model_validator(mode="after")
    def _ranges_ordered(self) -> LimitsSettings:
        for point in ("a", "b", "c"):
            low = getattr(self, f"v_{point}_low")
            high = getattr(self, f"v_{point}_high")
            if low >= high:
                raise PydanticCustomError(
                    "range_order",
                    "{low_key} ({low}) must be smaller than {high_key} ({high})",
                    {
                        "low_key": f"v_{point}_low",
                        "high_key": f"v_{point}_high",
                        "low": low,
                        "high": high,
                    },
                )
        return self

    def voltage_range(self, point: str) -> tuple[float, float]:
        """``(low, high)`` for point ``"a"``, ``"b"`` or ``"c"``."""
        return getattr(self, f"v_{point}_low"), getattr(self, f"v_{point}_high")


class TimeoutSettings(_Section):
    ping_s: PositiveFloat = 3.0
    measurement_s: PositiveFloat = 30.0
    api_s: PositiveFloat = 10.0
    qr_scan_s: PositiveFloat = 10.0


class ProgrammingSettings(_Section):
    max_retries: int = Field(default=3, ge=1, le=10)
    """Maximum upload attempts per device (first attempt included)."""


class ServerSettings(_Section):
    base_url: str = "https://api.parkomate.example"
    whitelist_path: str = "/api/v1/devices/whitelist"
    firmware_path: str = "/api/v1/firmware/latest"
    api_token_ref: str = Field(default="server_api_token", pattern=_SECRET_REF_RE)
    """Name of the keyring entry holding the API token (never the token itself)."""

    @field_validator("base_url")
    @classmethod
    def _https_only(cls, value: str) -> str:
        value = value.rstrip("/")
        if value.startswith("https://"):
            return value
        if re.match(r"^http://(localhost|127\.0\.0\.1)(:\d+)?$", value):
            return value  # local development server only
        raise PydanticCustomError(
            "https_required", "must start with https:// (plain http is only allowed for localhost)"
        )

    @field_validator("whitelist_path", "firmware_path")
    @classmethod
    def _path(cls, value: str) -> str:
        if not value.startswith("/"):
            raise PydanticCustomError("path_slash", "must start with '/'")
        return value


class MeasurementSettings(_Section):
    listen_host: str = "0.0.0.0"  # noqa: S104 - the measurement device is on the bench LAN
    listen_port: int = Field(default=8765, ge=1, le=65535)
    allowed_ip: str = "192.168.4.2"

    @field_validator("listen_host", "allowed_ip")
    @classmethod
    def _ip(cls, value: str) -> str:
        try:
            ipaddress.ip_address(value)
        except ValueError as exc:
            raise PydanticCustomError(
                "ip_invalid", "not a valid IP address: {value}", {"value": value}
            ) from exc
        return value


class CameraSettings(_Section):
    index: int = Field(default=0, ge=0, le=16)
    allow_manual_entry: bool = False
    """Allow typing the QR ID (twice) when the camera cannot read it. Flagged as manual."""
    id_pattern: str = r"^[A-Za-z0-9-]{4,32}$"
    """Regular expression a decoded / typed device ID must match."""

    @field_validator("id_pattern")
    @classmethod
    def _compiles(cls, value: str) -> str:
        try:
            re.compile(value)
        except re.error as exc:
            raise PydanticCustomError(
                "regex_invalid", "invalid regular expression: {error}", {"error": str(exc)}
            ) from exc
        return value


class EmailSettings(_Section):
    enabled: bool = False
    recipients: list[str] = Field(default_factory=list)
    sender: str = ""
    host: str = ""
    port: int = Field(default=587, ge=1, le=65535)
    security: Literal["starttls", "ssl", "none"] = "starttls"
    auth_method: Literal["password", "oauth2"] = "password"
    username: str = ""
    """Login name; empty means "same as sender"."""
    password_ref: str = Field(default="smtp_password", pattern=_SECRET_REF_RE)
    oauth_token_ref: str = Field(default="smtp_oauth_token", pattern=_SECRET_REF_RE)
    timeout_s: PositiveFloat = 30.0
    max_attempts: int = Field(default=10, ge=1, le=100)
    retry_base_s: PositiveFloat = 60.0
    retry_max_s: PositiveFloat = 3600.0
    subject_prefix: str = "[Parkomate]"

    @field_validator("recipients")
    @classmethod
    def _emails(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        bad = [item for item in cleaned if not _EMAIL_RE.match(item)]
        if bad:
            raise PydanticCustomError(
                "email_invalid", "invalid e-mail address(es): {values}", {"values": ", ".join(bad)}
            )
        return cleaned

    @field_validator("sender")
    @classmethod
    def _sender(cls, value: str) -> str:
        value = value.strip()
        if value and not _EMAIL_RE.match(value):
            raise PydanticCustomError(
                "email_invalid", "invalid e-mail address(es): {values}", {"values": value}
            )
        return value

    @model_validator(mode="after")
    def _complete_when_enabled(self) -> EmailSettings:
        if self.enabled:
            missing = [
                name
                for name, present in (
                    ("host", bool(self.host.strip())),
                    ("sender", bool(self.sender)),
                    ("recipients", bool(self.recipients)),
                )
                if not present
            ]
            if missing:
                raise PydanticCustomError(
                    "email_incomplete",
                    "e-mail is enabled but {fields} is empty",
                    {"fields": ", ".join(missing), "keys": [f"email.{m}" for m in missing]},
                )
        return self

    @property
    def login(self) -> str:
        return self.username or self.sender


class ReportsSettings(_Section):
    format: Literal["xlsx", "csv", "both"] = "xlsx"
    language: LanguageCode = "en"
    """Language of report headings and of the summary e-mail."""


class AuthSettings(_Section):
    max_failed_attempts: int = Field(default=5, ge=1, le=20)
    lockout_minutes: float = Field(default=5.0, gt=0, le=1440)
    min_password_length: int = Field(default=6, ge=4, le=64)


class UiSettings(_Section):
    kiosk: bool = False
    """Full-screen kiosk mode (no window frame)."""
    sound: bool = True
    """Short sound on reject / complete."""
    success_toast_s: PositiveFloat = 2.0


class LoggingSettings(_Section):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    max_bytes: int = Field(default=5_000_000, ge=100_000)
    backup_count: int = Field(default=5, ge=1, le=50)


class DevSettings(_Section):
    use_mock_hardware: bool = True
    """Prompt 1/2 only ship mocks. Real hardware arrives with the full build."""
    mock_scenario: str = "all_pass"
    """Overridden by the PARKOMATE_MOCK_SCENARIO environment variable."""
    mock_delay_scale: float = Field(default=1.0, ge=0, le=10)


class Settings(BaseModel):
    """The whole ``settings.toml``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retention_days: int = Field(default=90, ge=1, le=3650)
    """Sent e-mail payload files older than this are deleted (database rows are kept)."""
    station: StationSettings = Field(default_factory=StationSettings)
    limits: LimitsSettings = Field(default_factory=LimitsSettings)
    timeouts: TimeoutSettings = Field(default_factory=TimeoutSettings)
    programming: ProgrammingSettings = Field(default_factory=ProgrammingSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    measurement: MeasurementSettings = Field(default_factory=MeasurementSettings)
    camera: CameraSettings = Field(default_factory=CameraSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    reports: ReportsSettings = Field(default_factory=ReportsSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    ui: UiSettings = Field(default_factory=UiSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    dev: DevSettings = Field(default_factory=DevSettings)
