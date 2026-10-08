"""Measuring-device receiver.

The device on the bench network POSTs one JSON packet per measurement to
``http://<station>:<measurement.listen_port><measurement.path>``::

    {"station": "STATION-01", "seq": 41, "ts": "2026-10-08T10:15:02+05:30",
     "v_a": 24.01, "v_b": 5.01, "v_c": 3.31, "t_reg_c": 28.4, "t_amb_c": 27.1}

* Only packets from ``measurement.allowed_ip`` are accepted (others: HTTP 403).
* Packets are delivered only inside a *listening window* opened by :meth:`measure`
  (or :meth:`measure_ambient`); packets outside a window are acknowledged (202) and ignored,
  so a stale reading can never be attributed to the next board.
* Invalid JSON / fields → ``MEAS_BAD_DATA`` (raw payload logged, truncated); nothing in
  time → ``MEAS_TIMEOUT``; the port cannot be opened → ``MEAS_LISTEN_FAILED``.

The transport sits behind :class:`MeasurementTransport` so MQTT can be added later.
"""

from __future__ import annotations

import ipaddress
import json
import logging
import math
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from parkomate.config.settings import Settings
from parkomate.core.errors import ErrorCode, MeasurementError, ParkomateError
from parkomate.core.models import Measurement

log = logging.getLogger(__name__)

MAX_BODY = 64 * 1024


class MeasurementPacket(BaseModel):
    """Wire format. Unknown fields are ignored; numbers must be finite."""

    model_config = ConfigDict(extra="ignore")

    station: str | None = None
    seq: int | None = None
    ts: str | None = None
    v_a: float | None = None
    v_b: float | None = None
    v_c: float | None = None
    t_reg_c: float | None = None
    t_amb_c: float | None = None

    @field_validator("v_a", "v_b", "v_c", "t_reg_c", "t_amb_c")
    @classmethod
    def _finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("must be a finite number")
        return value

    def to_measurement(self) -> Measurement:
        return Measurement(
            station=self.station,
            seq=self.seq,
            v_a=self.v_a,
            v_b=self.v_b,
            v_c=self.v_c,
            t_reg_c=self.t_reg_c,
            t_amb_c=self.t_amb_c,
            received_at=datetime.now(UTC),
        )


class MeasurementTransport(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def measure(self, timeout_s: float) -> Measurement: ...

    def measure_ambient(self, timeout_s: float) -> float: ...


def parse_packet(raw: bytes) -> MeasurementPacket:
    """Decode and validate one body. Raises ``MeasurementError(MEAS_BAD_DATA)``."""
    try:
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("JSON object expected")
        return MeasurementPacket.model_validate(data)
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        log.warning(
            "bad measurement packet: %s",
            exc,
            extra={"context": {"raw": raw[:2000].decode("utf-8", errors="replace")}},
        )
        raise MeasurementError(
            "measuring device sent invalid data", code=ErrorCode.MEAS_BAD_DATA
        ) from exc


class HttpMeasurementListener:
    """HTTP POST receiver running in a background thread."""

    def __init__(
        self,
        settings: Callable[[], Settings],
        *,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._monotonic = monotonic
        self._cond = threading.Condition()
        self._window: str | None = None  # "measure" | "ambient" | None
        self._result: Measurement | ParkomateError | None = None
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def address(self) -> tuple[str, int] | None:
        if self._server is None:
            return None
        host, port = self._server.server_address[:2]
        return str(host), int(port)

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._server is not None:
            return
        settings = self._settings().measurement
        listener = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                listener._handle(self)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                log.debug("measurement http: " + format, *args)

        try:
            server = ThreadingHTTPServer((settings.listen_host, settings.listen_port), Handler)
        except OSError as exc:
            raise MeasurementError(
                f"cannot listen on port {settings.listen_port}: {exc}",
                code=ErrorCode.MEAS_LISTEN_FAILED,
                params={"port": settings.listen_port},
            ) from exc
        server.daemon_threads = True
        self._server = server
        self._thread = threading.Thread(
            target=server.serve_forever, name="measurement-listener", daemon=True
        )
        self._thread.start()
        log.info("measurement listener on %s:%d%s", *server.server_address[:2], settings.path)

    def stop(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    # ------------------------------------------------------------------ requests
    def _handle(self, request: BaseHTTPRequestHandler) -> None:
        settings = self._settings().measurement
        client = request.client_address[0]
        if request.path.split("?")[0] != settings.path:
            self._reply(request, 404, "unknown path")
            return
        if not _same_ip(client, settings.allowed_ip):
            log.warning("measurement from %s refused (allowed: %s)", client, settings.allowed_ip)
            self._reply(request, 403, "address not allowed")
            return
        length = int(request.headers.get("Content-Length") or 0)
        if length <= 0 or length > MAX_BODY:
            self._reply(request, 400, "body missing or too large")
            self._deliver(MeasurementError("empty or oversized packet",
                                           code=ErrorCode.MEAS_BAD_DATA))
            return
        raw = request.rfile.read(length)
        try:
            packet = parse_packet(raw)
        except MeasurementError as exc:
            self._reply(request, 400, "invalid measurement")
            self._deliver(exc)
            return
        used = self._deliver(packet.to_measurement())
        self._reply(request, 200 if used else 202, "used" if used else "ignored")

    def _deliver(self, item: Measurement | ParkomateError) -> bool:
        with self._cond:
            if self._window is None or self._result is not None:
                log.info("measurement packet outside a listening window - ignored")
                return False
            if (
                self._window == "ambient"
                and isinstance(item, Measurement)
                and item.t_amb_c is None
            ):
                return False  # waiting for an ambient value specifically
            self._result = item
            self._cond.notify_all()
            return True

    @staticmethod
    def _reply(request: BaseHTTPRequestHandler, status: int, message: str) -> None:
        body = json.dumps({"status": message}).encode()
        request.send_response(status)
        request.send_header("Content-Type", "application/json")
        request.send_header("Content-Length", str(len(body)))
        request.end_headers()
        request.wfile.write(body)

    # ------------------------------------------------------------------ windows
    def _wait(self, window: str, timeout_s: float) -> Measurement:
        self.start()
        with self._cond:
            self._window = window
            self._result = None
            self._cond.wait_for(lambda: self._result is not None, timeout=timeout_s)
            result = self._result
            self._window = None
            self._result = None
        if result is None:
            raise MeasurementError(
                f"no measurement within {timeout_s:g} s",
                code=ErrorCode.MEAS_TIMEOUT,
                params={"seconds": round(timeout_s)},
            )
        if isinstance(result, ParkomateError):
            raise result
        return result

    def measure(self, timeout_s: float) -> Measurement:
        return self._wait("measure", timeout_s)

    def measure_ambient(self, timeout_s: float) -> float:
        measurement = self._wait("ambient", timeout_s)
        assert measurement.t_amb_c is not None  # guaranteed by _deliver
        return measurement.t_amb_c


def _same_ip(client: str, allowed: str) -> bool:
    try:
        a = ipaddress.ip_address(client)
        b = ipaddress.ip_address(allowed)
    except ValueError:
        return False
    if isinstance(a, ipaddress.IPv6Address) and a.ipv4_mapped is not None:
        a = a.ipv4_mapped
    return a == b
