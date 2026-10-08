"""High-level report exports used by session close, e-mail and the admin Reports screen."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from parkomate.config.settings import ReportsSettings
from parkomate.core.clock import local_iso, to_local
from parkomate.core.errors import ReportError
from parkomate.data import Repositories
from parkomate.reports.data import collect_report_data
from parkomate.reports.layout import DEVICE_INFO_FIELDS, build_device_tables, build_session_tables
from parkomate.reports.writers import write_csv_tables, write_stacked_workbook, write_workbook

log = logging.getLogger(__name__)

ReportFormat = Literal["xlsx", "csv", "both"]


class ReportExporter:
    def __init__(
        self,
        repos: Repositories,
        reports_dir: Path,
        settings: Callable[[], ReportsSettings],
        station_id: Callable[[], str],
    ) -> None:
        self._repos = repos
        self._reports_dir = reports_dir
        self._settings = settings
        self._station_id = station_id

    @property
    def reports_dir(self) -> Path:
        return self._reports_dir

    def export_sessions(
        self,
        session_ids: Sequence[int],
        *,
        fmt: ReportFormat | None = None,
        language: str | None = None,
        out_dir: Path | None = None,
        stem: str | None = None,
    ) -> list[Path]:
        """Write the Summary/Devices/Checks/Rejections report for ``session_ids``."""
        if not session_ids:
            raise ReportError("no sessions selected")
        settings = self._settings()
        fmt = fmt or settings.format
        lang = language or settings.language
        directory = out_dir or self._reports_dir
        for session_id in session_ids:
            self._repos.sessions.require(session_id)  # NotFoundError for unknown sessions
        stem = stem or self._default_stem(session_ids)
        try:
            data = collect_report_data(
                self._repos, session_ids, language=lang, station_id=self._station_id()
            )
            tables = build_session_tables(data)
            paths: list[Path] = []
            if fmt in ("xlsx", "both"):
                paths.append(write_workbook(tables, directory / f"{stem}.xlsx", lang))
            if fmt in ("csv", "both"):
                paths.extend(write_csv_tables(tables, directory, stem, lang))
        except ReportError:
            raise
        except Exception as exc:
            raise ReportError(
                f"report export failed: {exc}", context={"sessions": list(session_ids)}
            ) from exc
        log.info("report written: %s", ", ".join(p.name for p in paths))
        return paths

    def export_session(self, session_id: int, **kwargs: Any) -> list[Path]:
        return self.export_sessions([session_id], **kwargs)

    def export_range(
        self,
        started_from: datetime,
        started_to: datetime,
        *,
        fmt: ReportFormat | None = None,
        language: str | None = None,
        out_dir: Path | None = None,
    ) -> list[Path]:
        """All sessions that started in ``[started_from, started_to)``, oldest first."""
        sessions = self._repos.sessions.list_sessions(
            started_from=started_from, started_to=started_to, limit=100_000
        )
        if not sessions:
            raise ReportError("no sessions in the selected range")
        ids = [s.id for s in reversed(sessions)]
        stem = (
            f"sessions_{self._station_id()}_{to_local(started_from):%Y%m%d}"
            f"-{to_local(started_to):%Y%m%d}"
        )
        return self.export_sessions(ids, fmt=fmt, language=language, out_dir=out_dir, stem=stem)

    def device_report(self, device_row_id: int, *, language: str | None = None) -> dict[str, Any]:
        """Structured (JSON-friendly) report for one device."""
        lang = language or self._settings().language
        device = self._repos.devices.require(device_row_id)
        checks = self._repos.checks.list_for_device(device_row_id)
        info = {
            key.removeprefix("report.col."): get(device, lang) for key, get in DEVICE_INFO_FIELDS
        }
        return {
            "device": info,
            "checks": [
                {
                    "stage": c.stage.value,
                    "check_code": c.check_code.value,
                    "value_num": c.value_num,
                    "value_text": c.value_text,
                    "unit": c.unit,
                    "limit_low": c.limit_low,
                    "limit_high": c.limit_high,
                    "passed": c.passed,
                    "operator_marked": c.operator_marked,
                    "time": local_iso(c.created_at),
                }
                for c in checks
            ],
            "transitions": [
                {
                    "from": t.from_stage.value if t.from_stage else None,
                    "to": t.to_stage.value,
                    "time": local_iso(t.created_at),
                }
                for t in self._repos.transitions.list_for_device(device_row_id)
            ],
            "counter_events": [
                {"event": e.event.value, "time": local_iso(e.created_at)}
                for e in self._repos.counters.list_for_device(device_row_id)
            ],
        }

    def export_device(
        self, device_row_id: int, *, language: str | None = None, out_dir: Path | None = None
    ) -> Path:
        """Excel sheet for one device (info block + every check result)."""
        lang = language or self._settings().language
        device = self._repos.devices.require(device_row_id)
        checks = self._repos.checks.list_for_device(device_row_id)
        tables = build_device_tables(device, checks, lang)
        name = device.device_id or device.mac_address.replace(":", "")
        path = (out_dir or self._reports_dir) / f"device_{device.id}_{_safe(name)}.xlsx"
        try:
            return write_stacked_workbook(tables, path, lang, tables[0].title)
        except Exception as exc:
            raise ReportError(f"device report failed: {exc}") from exc

    def _default_stem(self, session_ids: Sequence[int]) -> str:
        first = self._repos.sessions.require(session_ids[0])
        stamp = to_local(first.started_at).strftime("%Y%m%d-%H%M")
        ids = (
            str(session_ids[0]) if len(session_ids) == 1 else f"{session_ids[0]}-{session_ids[-1]}"
        )
        return f"session-{ids}_{_safe(self._station_id())}_{stamp}"


def _safe(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text)[:40]
