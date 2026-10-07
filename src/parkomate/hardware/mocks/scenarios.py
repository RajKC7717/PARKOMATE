"""Mock scenarios: which failure the simulated bench produces."""

from __future__ import annotations

import os
from enum import StrEnum

from parkomate.core.errors import SettingsError

ENV_SCENARIO = "PARKOMATE_MOCK_SCENARIO"
ENV_DELAY = "PARKOMATE_MOCK_DELAY"
ENV_SEED = "PARKOMATE_MOCK_SEED"


class MockScenario(StrEnum):
    """Every board on the simulated bench behaves according to the scenario.

    Scenarios that model a *transient* problem fail only the first time per board, so the
    recovery path (retry / try again / scan again) can be demonstrated.
    """

    ALL_PASS = "all_pass"
    UPLOAD_FAILS_THEN_SUCCEEDS = "upload_fails_then_succeeds"  # 1st flash fails, retry passes
    UPLOAD_ALWAYS_FAILS = "upload_always_fails"  # every flash fails -> reject after max retries
    WHITELIST_DENIED = "whitelist_denied"  # server refuses the MAC
    V_C_OUT_OF_RANGE = "v_c_out_of_range"  # Point C reads 3.21 V
    TEMP_TOO_HIGH = "temp_too_high"  # regulator 4.6 °C above ambient
    MEASUREMENT_TIMEOUT = "measurement_timeout"  # 1st measurement times out, retry passes
    QR_UNREADABLE = "qr_unreadable"  # 1st QR scan sees nothing, rescan passes
    ID_DIFFERS = "id_differs"  # board holds factory ID -> write QR ID -> confirmed
    ID_WRITE_FAILS = "id_write_fails"  # write acknowledged but read-back differs -> reject
    COM_DISCONNECT_MID_FLASH = "com_disconnect_mid_flash"  # port lost at 40 % on 1st flash
    COMM_FAIL = "comm_fail"  # ping gets no answer -> reject at Testing
    CAMERA_MISSING = "camera_missing"  # no camera -> CAM_NOT_FOUND
    MIXED = "mixed"  # random scenario per board (60 % all-pass) for realistic demos

    @classmethod
    def parse(cls, value: str) -> MockScenario:
        normalised = value.strip().lower().replace("-", "_")
        try:
            return cls(normalised)
        except ValueError as exc:
            valid = ", ".join(s.value for s in cls)
            raise SettingsError(
                f"unknown mock scenario {value!r}; valid: {valid}",
                problems=[(f"dev.mock_scenario / {ENV_SCENARIO}", f"unknown value {value!r}")],
            ) from exc


def resolve_scenario(configured: str) -> MockScenario:
    """Environment variable ``PARKOMATE_MOCK_SCENARIO`` wins over ``dev.mock_scenario``."""
    return MockScenario.parse(os.environ.get(ENV_SCENARIO) or configured)


def resolve_delay_scale(configured: float) -> float:
    raw = os.environ.get(ENV_DELAY)
    if raw is None:
        return configured
    try:
        value = float(raw)
    except ValueError as exc:
        raise SettingsError(
            f"{ENV_DELAY} must be a number, got {raw!r}",
            problems=[(ENV_DELAY, f"not a number: {raw!r}")],
        ) from exc
    return max(0.0, value)


def resolve_seed() -> int | None:
    raw = os.environ.get(ENV_SEED)
    return int(raw) if raw and raw.lstrip("-").isdigit() else None
