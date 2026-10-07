"""THE report layout - every sheet, column, header, width and value in one place.

The final report format is still to be confirmed with the client, so all layout decisions
live here. The Excel and CSV writers only render the :class:`Table` objects this module
builds; changing a column means editing one list below.

Headers come from the i18n catalogue (``report.*`` keys) in the report language.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from parkomate.core.clock import local_iso
from parkomate.core.enums import (
    PRODUCTION_STAGES,
    CheckCode,
    CheckKind,
    Stage,
)
from parkomate.core.models import CheckResult, Device, SessionSummary
from parkomate.i18n import tr, tr_message
from parkomate.reports.data import (
    CheckRowContext,
    DeviceRowContext,
    RejectionRowContext,
    ReportData,
)


class Kind(StrEnum):
    TEXT = "text"
    INTEGER = "integer"
    NUMBER = "number"
    PERCENT = "percent"
    RESULT = "result"  # bool | None -> PASS / FAIL / empty, coloured in Excel


@dataclass(frozen=True, slots=True)
class Table:
    """A rendered sheet: translated headers plus typed cell values."""

    key: str  # stable id: summary / devices / checks / rejections / device
    title: str  # translated sheet name
    headers: list[str]
    kinds: list[Kind]
    widths: list[int]
    rows: list[list[Any]] = field(default_factory=list)
    freeze_first_column: bool = False


@dataclass(frozen=True, slots=True)
class Column[R]:
    header_key: str
    width: int
    kind: Kind
    get: Callable[[R, str], Any]
    header_params: dict[str, Any] = field(default_factory=dict)


# ----------------------------------------------------------------------------- helpers


def _dt(value: datetime | None) -> str:
    return local_iso(value)


def _stage_text(stage: Stage | None, lang: str) -> str:
    if stage is None:
        return ""
    return f"{stage.letter} - {tr(lang, stage.label_key)}"


def _check_name(code: CheckCode | None, lang: str) -> str:
    return "" if code is None else tr(lang, code.label_key)


def _reject_reason(device: Device, lang: str) -> str:
    if device.reject_reason_key:
        return tr_message(lang, device.reject_reason_key, device.reject_reason_params)
    return device.reject_reason or ""


def _duration_s(device: Device) -> float | None:
    if device.finished_at is None:
        return None
    return round((device.finished_at - device.started_at).total_seconds(), 1)


def _check_value(check: CheckResult | None) -> Any:
    if check is None:
        return None
    if check.value_num is not None:
        return check.value_num
    return check.value_text


def _limits_text(check: CheckResult | None) -> str:
    if check is None or (check.limit_low is None and check.limit_high is None):
        return ""
    low = "" if check.limit_low is None else f"{check.limit_low:g}"
    high = "" if check.limit_high is None else f"{check.limit_high:g}"
    if low and high:
        return f"{low} - {high}"
    return f"<= {high}" if high else f">= {low}"


def result_text(value: bool | None, lang: str) -> str:
    if value is None:
        return ""
    return tr(lang, "report.result.pass" if value else "report.result.fail")


def yes_no(value: bool, lang: str) -> str:
    return tr(lang, "common.yes" if value else "common.no")


# ----------------------------------------------------------------------------- summary


@dataclass(frozen=True, slots=True)
class SummaryField:
    label_key: str
    kind: Kind
    get: Callable[[SessionSummary, str, str], Any]  # (summary, lang, station_id)
    label_params: dict[str, Any] = field(default_factory=dict)


def _ambient_text(summary: SessionSummary, lang: str) -> str:
    parts = [
        f"{reading.value_c:.1f} °C ({tr(lang, reading.reason.label_key)}, "
        f"{_dt(reading.measured_at)})"
        for reading in summary.ambient_readings
    ]
    return "; ".join(parts)


def _end_reason(summary: SessionSummary, lang: str) -> str:
    reason = summary.session.end_reason
    return "" if reason is None else tr(lang, reason.label_key)


def _rejected_at(stage: Stage) -> Callable[[SessionSummary, str, str], Any]:
    def get(summary: SessionSummary, _lang: str, _station: str) -> Any:
        return summary.rejected_by_stage.get(stage, 0)

    return get


SUMMARY_FIELDS: list[SummaryField] = [
    SummaryField("report.summary.session_id", Kind.INTEGER, lambda s, _l, _st: s.session.id),
    SummaryField("report.summary.station", Kind.TEXT, lambda s, _l, _st: s.session.station_id),
    SummaryField(
        "report.summary.operator",
        Kind.TEXT,
        lambda s, _l, _st: f"{s.operator_code} - {s.operator_name}",
    ),
    SummaryField("report.summary.started", Kind.TEXT, lambda s, _l, _st: _dt(s.session.started_at)),
    SummaryField("report.summary.ended", Kind.TEXT, lambda s, _l, _st: _dt(s.session.ended_at)),
    SummaryField("report.summary.end_reason", Kind.TEXT, lambda s, lang, _st: _end_reason(s, lang)),
    SummaryField(
        "report.summary.firmware_name", Kind.TEXT, lambda s, _l, _st: s.session.firmware_name or ""
    ),
    SummaryField(
        "report.summary.firmware_version",
        Kind.TEXT,
        lambda s, _l, _st: s.session.firmware_version or "",
    ),
    SummaryField(
        "report.summary.firmware_sha256",
        Kind.TEXT,
        lambda s, _l, _st: s.session.firmware_sha256 or "",
    ),
    SummaryField(
        "report.summary.ambient_initial",
        Kind.NUMBER,
        lambda s, _l, _st: s.session.ambient_c_initial,
    ),
    SummaryField(
        "report.summary.ambient_readings", Kind.TEXT, lambda s, lang, _st: _ambient_text(s, lang)
    ),
    SummaryField("report.summary.total_devices", Kind.INTEGER, lambda s, _l, _st: s.total_devices),
    SummaryField("report.summary.complete", Kind.INTEGER, lambda s, _l, _st: s.complete),
    SummaryField(
        "report.summary.rejected_total", Kind.INTEGER, lambda s, _l, _st: s.rejected_total
    ),
    *[
        SummaryField(
            "report.summary.rejected_stage",
            Kind.INTEGER,
            _rejected_at(stage),
            {"letter": stage.letter, "stage_key": stage.label_key},
        )
        for stage in PRODUCTION_STAGES
    ],
    SummaryField("report.summary.abandoned", Kind.INTEGER, lambda s, _l, _st: s.abandoned),
    SummaryField("report.summary.in_progress", Kind.INTEGER, lambda s, _l, _st: s.in_progress),
    SummaryField(
        "report.summary.upload_success", Kind.INTEGER, lambda s, _l, _st: s.upload_success
    ),
    SummaryField(
        "report.summary.upload_failure", Kind.INTEGER, lambda s, _l, _st: s.upload_failure
    ),
    SummaryField(
        "report.summary.failures_adjusted", Kind.INTEGER, lambda s, _l, _st: s.failures_adjusted
    ),
    SummaryField(
        "report.summary.net_upload_failure", Kind.INTEGER, lambda s, _l, _st: s.net_upload_failure
    ),
    SummaryField(
        "report.summary.counter_resets", Kind.INTEGER, lambda s, _l, _st: s.counter_resets
    ),
    SummaryField(
        "report.summary.first_pass_yield", Kind.PERCENT, lambda s, _l, _st: s.first_pass_yield
    ),
]


def summary_label(field_: SummaryField, lang: str) -> str:
    return tr_message(lang, field_.label_key, field_.label_params)


def build_summary_table(data: ReportData) -> Table:
    lang = data.language
    headers = [tr(lang, "report.col.field")] + [
        tr(lang, "report.col.session_n", id=s.session.id) for s in data.summaries
    ]
    rows: list[list[Any]] = []
    for field_ in SUMMARY_FIELDS:
        rows.append(
            [summary_label(field_, lang)]
            + [field_.get(s, lang, data.station_id) for s in data.summaries]
        )
    kinds = [Kind.TEXT] + [Kind.TEXT] * len(data.summaries)
    widths = [34] + [44] * len(data.summaries)
    return Table(
        key="summary",
        title=tr(lang, "report.sheet.summary"),
        headers=headers,
        kinds=kinds,
        widths=widths,
        rows=rows,
        freeze_first_column=True,
    )


# ----------------------------------------------------------------------------- devices

DEVICE_COLUMNS: list[Column[DeviceRowContext]] = [
    Column("report.col.row_id", 9, Kind.INTEGER, lambda r, _l: r.device.id),
    Column("report.col.session_id", 9, Kind.INTEGER, lambda r, _l: r.device.session_id),
    Column("report.col.device_id", 16, Kind.TEXT, lambda r, _l: r.device.device_id or ""),
    Column("report.col.mac", 19, Kind.TEXT, lambda r, _l: r.device.mac_address),
    Column(
        "report.col.firmware_version", 12, Kind.TEXT, lambda r, _l: r.device.firmware_version or ""
    ),
    Column("report.col.started", 26, Kind.TEXT, lambda r, _l: _dt(r.device.started_at)),
    Column("report.col.finished", 26, Kind.TEXT, lambda r, _l: _dt(r.device.finished_at)),
    Column("report.col.duration_s", 11, Kind.NUMBER, lambda r, _l: _duration_s(r.device)),
    Column("report.col.status", 14, Kind.TEXT, lambda r, lang: tr(lang, r.device.status.label_key)),
    Column(
        "report.col.programming_attempts",
        11,
        Kind.INTEGER,
        lambda r, _l: r.device.programming_attempts,
    ),
    Column("report.col.upload_failures", 11, Kind.INTEGER, lambda r, _l: r.upload_failures),
    Column(
        "report.col.id_method",
        12,
        Kind.TEXT,
        lambda r, lang: (
            tr(lang, r.device.id_entry_method.label_key) if r.device.id_entry_method else ""
        ),
    ),
    Column(
        "report.col.reject_stage",
        18,
        Kind.TEXT,
        lambda r, lang: _stage_text(r.device.reject_stage, lang),
    ),
    Column(
        "report.col.reject_check",
        24,
        Kind.TEXT,
        lambda r, lang: _check_name(r.device.reject_check_code, lang),
    ),
    Column(
        "report.col.reject_reason", 48, Kind.TEXT, lambda r, lang: _reject_reason(r.device, lang)
    ),
]


def device_sheet_checks(max_reading_index: int) -> list[CheckCode]:
    """Check columns of the Devices sheet, in production order."""
    readings = [CheckCode.reading(i) for i in range(1, max_reading_index + 1)]
    return [
        CheckCode.A_WHITELIST,
        CheckCode.A_UPLOAD,
        CheckCode.B1_COMM,
        *readings,
        CheckCode.B2_SENSOR_OK,
        CheckCode.B2_INDICATOR_OK,
        CheckCode.B3_V_A,
        CheckCode.B3_V_B,
        CheckCode.B3_V_C,
        CheckCode.B3_T_REG,
        CheckCode.B3_T_AMB,
        CheckCode.C1,
        CheckCode.C2,
        CheckCode.C3,
        CheckCode.C4,
        CheckCode.C_QR_READ,
        CheckCode.C_ID_SYNC,
        CheckCode.D1,
        CheckCode.D2,
        CheckCode.D3,
        CheckCode.D4,
    ]


def _check_columns(code: CheckCode) -> list[Column[DeviceRowContext]]:
    """Value (+ limits for measured checks) + result columns for one check."""
    params = {"check_key": code.label_key}
    kind = code.meta.kind
    columns: list[Column[DeviceRowContext]] = []
    if kind in (CheckKind.MEASURED, CheckKind.INFO, CheckKind.AUTOMATIC):
        value_kind = Kind.NUMBER if code.meta.unit or kind is CheckKind.INFO else Kind.TEXT
        columns.append(
            Column(
                "report.col.check_value",
                14,
                value_kind,
                lambda r, _l: _check_value(r.latest.get(code)),
                params,
            )
        )
    if kind is CheckKind.MEASURED:
        columns.append(
            Column(
                "report.col.check_limits",
                14,
                Kind.TEXT,
                lambda r, _l: _limits_text(r.latest.get(code)),
                params,
            )
        )
    if kind is not CheckKind.INFO:
        columns.append(
            Column(
                "report.col.check_result",
                12,
                Kind.RESULT,
                lambda r, _l: r.latest[code].passed if code in r.latest else None,
                params,
            )
        )
    return columns


def build_devices_table(data: ReportData) -> Table:
    columns = list(DEVICE_COLUMNS)
    for code in device_sheet_checks(data.max_reading_index):
        columns.extend(_check_columns(code))
    return _table("devices", "report.sheet.devices", columns, data.devices, data.language)


# ----------------------------------------------------------------------------- checks

CHECK_COLUMNS: list[Column[CheckRowContext]] = [
    Column("report.col.row_id", 9, Kind.INTEGER, lambda r, _l: r.device.id),
    Column("report.col.device_id", 16, Kind.TEXT, lambda r, _l: r.device.device_id or ""),
    Column("report.col.mac", 19, Kind.TEXT, lambda r, _l: r.device.mac_address),
    Column("report.col.stage", 18, Kind.TEXT, lambda r, lang: _stage_text(r.check.stage, lang)),
    Column("report.col.check_code", 16, Kind.TEXT, lambda r, _l: r.check.check_code.value),
    Column(
        "report.col.check_name",
        30,
        Kind.TEXT,
        lambda r, lang: _check_name(r.check.check_code, lang),
    ),
    Column("report.col.value", 16, Kind.TEXT, lambda r, _l: _check_value(r.check)),
    Column("report.col.unit", 7, Kind.TEXT, lambda r, _l: r.check.unit or ""),
    Column("report.col.limit_low", 10, Kind.NUMBER, lambda r, _l: r.check.limit_low),
    Column("report.col.limit_high", 10, Kind.NUMBER, lambda r, _l: r.check.limit_high),
    Column("report.col.result", 10, Kind.RESULT, lambda r, _l: r.check.passed),
    Column(
        "report.col.operator_marked",
        11,
        Kind.TEXT,
        lambda r, lang: yes_no(r.check.operator_marked, lang),
    ),
    Column("report.col.time", 26, Kind.TEXT, lambda r, _l: _dt(r.check.created_at)),
]


def build_checks_table(data: ReportData) -> Table:
    return _table("checks", "report.sheet.checks", CHECK_COLUMNS, data.checks, data.language)


# ----------------------------------------------------------------------------- rejections

REJECTION_COLUMNS: list[Column[RejectionRowContext]] = [
    Column("report.col.row_id", 9, Kind.INTEGER, lambda r, _l: r.device.id),
    Column("report.col.session_id", 9, Kind.INTEGER, lambda r, _l: r.device.session_id),
    Column("report.col.device_id", 16, Kind.TEXT, lambda r, _l: r.device.device_id or ""),
    Column("report.col.mac", 19, Kind.TEXT, lambda r, _l: r.device.mac_address),
    Column(
        "report.col.reject_stage",
        18,
        Kind.TEXT,
        lambda r, lang: _stage_text(r.device.reject_stage, lang),
    ),
    Column(
        "report.col.reject_box",
        8,
        Kind.TEXT,
        lambda r, _l: r.device.reject_stage.letter if r.device.reject_stage else "",
    ),
    Column(
        "report.col.reject_check",
        26,
        Kind.TEXT,
        lambda r, lang: _check_name(r.device.reject_check_code, lang),
    ),
    Column("report.col.value", 14, Kind.TEXT, lambda r, _l: _check_value(r.failed_check)),
    Column(
        "report.col.unit",
        7,
        Kind.TEXT,
        lambda r, _l: (r.failed_check.unit or "") if r.failed_check else "",
    ),
    Column("report.col.limits", 14, Kind.TEXT, lambda r, _l: _limits_text(r.failed_check)),
    Column(
        "report.col.reject_reason", 52, Kind.TEXT, lambda r, lang: _reject_reason(r.device, lang)
    ),
    Column("report.col.time", 26, Kind.TEXT, lambda r, _l: _dt(r.device.finished_at)),
]


def build_rejections_table(data: ReportData) -> Table:
    return _table(
        "rejections", "report.sheet.rejections", REJECTION_COLUMNS, data.rejections, data.language
    )


# ----------------------------------------------------------------------------- assembly


def _table[R](
    key: str,
    title_key: str,
    columns: Sequence[Column[R]],
    contexts: Sequence[R],
    lang: str,
) -> Table:
    return Table(
        key=key,
        title=tr(lang, title_key),
        headers=[tr_message(lang, c.header_key, c.header_params) for c in columns],
        kinds=[c.kind for c in columns],
        widths=[c.width for c in columns],
        rows=[[c.get(ctx, lang) for c in columns] for ctx in contexts],
    )


def build_session_tables(data: ReportData) -> list[Table]:
    """The four sheets in order: Summary, Devices, Checks, Rejections."""
    return [
        build_summary_table(data),
        build_devices_table(data),
        build_checks_table(data),
        build_rejections_table(data),
    ]


# ----------------------------------------------------------------------------- one device

DEVICE_INFO_FIELDS: list[tuple[str, Callable[[Device, str], Any]]] = [
    ("report.col.row_id", lambda d, _l: d.id),
    ("report.col.session_id", lambda d, _l: d.session_id),
    ("report.col.device_id", lambda d, _l: d.device_id or ""),
    ("report.col.mac", lambda d, _l: d.mac_address),
    ("report.col.firmware_version", lambda d, _l: d.firmware_version or ""),
    ("report.col.status", lambda d, lang: tr(lang, d.status.label_key)),
    ("report.col.started", lambda d, _l: _dt(d.started_at)),
    ("report.col.finished", lambda d, _l: _dt(d.finished_at)),
    ("report.col.duration_s", lambda d, _l: _duration_s(d)),
    ("report.col.programming_attempts", lambda d, _l: d.programming_attempts),
    (
        "report.col.id_method",
        lambda d, lang: tr(lang, d.id_entry_method.label_key) if d.id_entry_method else "",
    ),
    ("report.col.reject_stage", lambda d, lang: _stage_text(d.reject_stage, lang)),
    ("report.col.reject_check", lambda d, lang: _check_name(d.reject_check_code, lang)),
    ("report.col.reject_reason", _reject_reason),
]

DEVICE_CHECK_COLUMNS: list[Column[CheckRowContext]] = [
    c
    for c in CHECK_COLUMNS
    if c.header_key not in ("report.col.row_id", "report.col.device_id", "report.col.mac")
]


def build_device_tables(device: Device, checks: Sequence[CheckResult], lang: str) -> list[Table]:
    """Info block (field/value) and the device's checks table."""
    info = Table(
        key="device",
        title=tr(lang, "report.sheet.device"),
        headers=[tr(lang, "report.col.field"), tr(lang, "report.col.value")],
        kinds=[Kind.TEXT, Kind.TEXT],
        widths=[30, 44],
        rows=[[tr(lang, key), get(device, lang)] for key, get in DEVICE_INFO_FIELDS],
    )
    contexts = [CheckRowContext(device, check) for check in checks]
    table = _table("device_checks", "report.sheet.checks", DEVICE_CHECK_COLUMNS, contexts, lang)
    return [info, table]
