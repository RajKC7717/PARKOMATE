"""Pure validation rules - no Qt, no hardware, no database. Every function is deterministic.

* Limits are **inclusive**: ``low <= value <= high``.
* Values (and limits) are rounded **half-up on their decimal representation** to
  ``limits.decimals`` before comparing, so binary floating point never decides a verdict
  (3.245 V → 3.25 V at 2 decimals).
* A missing value is a failure with its own reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from parkomate.config.settings import LimitsSettings
from parkomate.core.enums import CheckCode
from parkomate.core.models import Measurement

VOLTAGE_POINTS: tuple[tuple[str, CheckCode], ...] = (
    ("a", CheckCode.B3_V_A),
    ("b", CheckCode.B3_V_B),
    ("c", CheckCode.B3_V_C),
)


def quantize(value: float, decimals: int) -> Decimal:
    """Round half-up on the decimal representation (3.245 -> 3.25 at 2 decimals)."""
    return Decimal(repr(float(value))).quantize(
        Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP
    )


def within(value: float, low: float, high: float, decimals: int) -> bool:
    """Inclusive limit check after rounding value and limits to ``decimals``."""
    rounded = quantize(value, decimals)
    return quantize(low, decimals) <= rounded <= quantize(high, decimals)


@dataclass(frozen=True, slots=True)
class Verdict:
    """Outcome of one rule: pass/fail, the (rounded) value, the limits and the reason."""

    check_code: CheckCode
    passed: bool
    value: float | None = None
    unit: str | None = None
    low: float | None = None
    high: float | None = None
    reason_key: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    detail: str | None = None


def check_range(
    code: CheckCode, raw: float | None, low: float, high: float, decimals: int, unit: str
) -> Verdict:
    """Inclusive range check (voltages)."""
    if raw is None:
        return Verdict(
            code,
            False,
            unit=unit,
            low=low,
            high=high,
            reason_key="reject.reason.value_missing",
            params={"check_key": code.label_key},
        )
    value = float(quantize(raw, decimals))
    passed = within(raw, low, high, decimals)
    params = {
        "check_key": code.label_key,
        "value": f"{value:.{decimals}f}",
        "unit": unit,
        "low": f"{low:.{decimals}f}",
        "high": f"{high:.{decimals}f}",
    }
    return Verdict(
        code,
        passed,
        value=value,
        unit=unit,
        low=low,
        high=high,
        reason_key=None if passed else "reject.reason.out_of_range",
        params=params,
    )


def check_regulator(
    t_reg: float | None, ambient: float | None, margin: float, decimals: int
) -> Verdict:
    """Regulator temperature must not exceed ``ambient + margin`` (rise compared rounded)."""
    code = CheckCode.B3_T_REG
    if t_reg is None or ambient is None:
        return Verdict(
            code,
            False,
            value=None if t_reg is None else float(quantize(t_reg, decimals)),
            unit="°C",
            reason_key=(
                "reject.reason.value_missing" if t_reg is None
                else "reject.reason.ambient_missing"
            ),
            params={"check_key": code.label_key},
        )
    rise = quantize(t_reg - ambient, decimals)
    limit = float(quantize(ambient + margin, decimals))
    value = float(quantize(t_reg, decimals))
    passed = rise <= quantize(margin, decimals)
    params = {
        "check_key": code.label_key,
        "value": f"{value:.{decimals}f}",
        "ambient": f"{ambient:.1f}",
        "margin": f"{margin:g}",
        "limit": f"{limit:.{decimals}f}",
        "rise": f"{float(rise):.{decimals}f}",
    }
    return Verdict(
        code,
        passed,
        value=value,
        unit="°C",
        high=limit,
        reason_key=None if passed else "reject.reason.temp_too_high",
        params=params,
        detail=f"rise {float(rise):.{decimals}f} °C over ambient {ambient:.1f} °C",
    )


def measurement_verdicts(
    measurement: Measurement, limits: LimitsSettings, ambient: float | None
) -> list[Verdict]:
    """V_A, V_B, V_C then T_REG, in that order."""
    verdicts = [
        check_range(code, getattr(measurement, f"v_{point}"), *limits.voltage_range(point),
                    limits.decimals, "V")
        for point, code in VOLTAGE_POINTS
    ]
    verdicts.append(
        check_regulator(measurement.t_reg_c, ambient, limits.temp_margin_c, limits.decimals)
    )
    return verdicts


def id_format_ok(value: str, pattern: str) -> bool:
    """A device ID (from the QR or typed) must match the configured pattern completely."""
    return re.fullmatch(pattern, value.strip()) is not None


def ids_match(qr_id: str, device_id: str | None) -> bool:
    """Exact, case-sensitive comparison after trimming whitespace."""
    return device_id is not None and qr_id.strip() == device_id.strip() and bool(qr_id.strip())
