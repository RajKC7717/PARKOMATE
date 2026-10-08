"""Line-based text link to the firmware running on the board.

Protocol (one command per line, ``\\n`` terminated, ASCII):

    PING            -> PONG
    READ_SENSOR     -> SENSOR <value> [unit]
    GET_ID          -> ID <id>          ("ID" alone = no ID stored)
    SET_ID <id>     -> OK
    GET_MAC         -> MAC <AA:BB:CC:DD:EE:FF>
    any command     -> ERR <code>       (device-side error)

Lines that do not answer the command (boot log, debug output) are ignored. Every command
has a timeout and a number of retries; after flashing, commands keep retrying for
``serial.boot_wait_s`` while the firmware boots.

The port is opened with DTR and RTS released so opening it never resets the board, and it
is shared with the flasher through :class:`PortGuard` - the two never hold it together.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Protocol

from parkomate.config.settings import Settings
from parkomate.core.errors import ErrorCode, HardwareError, InputError
from parkomate.core.models import SensorReading

log = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[\x21-\x7e]{1,64}$")  # printable, no spaces/newlines (no injection)


class SerialLike(Protocol):
    """The part of ``serial.Serial`` the link uses (a fake implements it in tests)."""

    is_open: bool

    def write(self, data: bytes) -> int | None: ...

    def readline(self) -> bytes: ...

    def reset_input_buffer(self) -> None: ...

    def close(self) -> None: ...


SerialFactory = Callable[[str, int, float], SerialLike]


def map_serial_open_error(exc: BaseException, port: str) -> HardwareError:
    text = str(exc).lower()
    if "access is denied" in text or "permission" in text or "busy" in text:
        code = ErrorCode.HW_PORT_BUSY
    elif "filenotfound" in text or "cannot find" in text or "no such file" in text:
        code = ErrorCode.HW_NO_PORT
    else:
        code = ErrorCode.HW_COM_DISCONNECTED
    return HardwareError(
        f"cannot open {port}: {exc}", code=code, params={"port": port}, context={"port": port}
    )


def open_pyserial(port: str, baud: int, timeout: float) -> SerialLike:
    """Open ``port`` without toggling DTR/RTS (which would reset an ESP32 board)."""
    import serial

    ser = serial.Serial()
    ser.port = port
    ser.baudrate = baud
    ser.timeout = timeout
    ser.write_timeout = 2.0
    ser.dtr = False
    ser.rts = False
    try:
        ser.open()
    except (serial.SerialException, OSError) as exc:
        raise map_serial_open_error(exc, port) from exc
    return ser  # type: ignore[no-any-return]


class PortGuard:
    """Exclusive ownership of the board's serial port (link vs. flasher)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def __enter__(self) -> PortGuard:
        self._lock.acquire()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._lock.release()


def _serial_errors() -> tuple[type[BaseException], ...]:
    try:
        import serial

        return (serial.SerialException, OSError)
    except ImportError:  # pragma: no cover
        return (OSError,)


class DeviceLink:
    READ_TIMEOUT_S = 0.1

    def __init__(
        self,
        settings: Callable[[], Settings],
        *,
        factory: SerialFactory = open_pyserial,
        guard: PortGuard | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._factory = factory
        self.guard = guard or PortGuard()
        self._monotonic = monotonic
        self._sleep = sleep
        self._port: str | None = None
        self._serial: SerialLike | None = None
        self._boot_until = 0.0

    @property
    def port(self) -> str | None:
        return self._port

    def attach(self, port: str) -> None:
        with self.guard:
            if port != self._port:
                self.close()
            self._port = port

    def detach(self) -> None:
        with self.guard:
            self.close()
            self._port = None

    def close(self) -> None:
        with self.guard:
            if self._serial is not None:
                try:
                    self._serial.close()
                except Exception:  # closing a vanished port may itself fail
                    log.debug("closing serial port failed", exc_info=True)
            self._serial = None

    def expect_boot(self) -> None:
        """The board was just reset: allow it ``serial.boot_wait_s`` to start answering."""
        self._boot_until = self._monotonic() + self._settings().serial.boot_wait_s

    def _booting(self) -> bool:
        return self._monotonic() < self._boot_until

    def _ensure_open(self) -> SerialLike:
        if self._port is None:
            raise HardwareError("no board port selected", code=ErrorCode.HW_COM_DISCONNECTED)
        if self._serial is None or not self._serial.is_open:
            self._serial = self._factory(
                self._port, self._settings().serial.baud, self.READ_TIMEOUT_S
            )
        return self._serial

    def command(
        self,
        command: str,
        expect: str,
        *,
        timeout: float | None = None,
        retries: int | None = None,
    ) -> str:
        """Send ``command``; return the payload of the first ``expect`` reply line."""
        settings = self._settings().serial
        wait = timeout if timeout is not None else settings.command_timeout_s
        tries = 1 + (retries if retries is not None else settings.command_retries)
        attempt = 0
        with self.guard:
            while True:
                attempt += 1
                try:
                    reply = self._exchange(command, expect, wait)
                except HardwareError as exc:
                    booting = self._booting() and exc.code in (
                        ErrorCode.HW_TIMEOUT,
                        ErrorCode.HW_NO_PORT,
                        ErrorCode.HW_COM_DISCONNECTED,
                    )
                    if exc.code is ErrorCode.HW_DEVICE_ERROR or not (
                        attempt < tries or booting
                    ):
                        raise
                    log.debug("retrying %s after %s", command.split()[0], exc.code.value)
                    if booting:
                        self.close()
                        self._sleep(0.3)
                    continue
                self._boot_until = 0.0
                return reply

    def _exchange(self, command: str, expect: str, wait: float) -> str:
        errors = _serial_errors()
        try:
            ser = self._ensure_open()
            ser.reset_input_buffer()
            ser.write(f"{command}\n".encode("ascii"))
            deadline = self._monotonic() + wait
            while self._monotonic() < deadline:
                raw = ser.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if line == "ERR" or line.startswith("ERR "):
                    raise HardwareError(
                        f"board answered {line!r} to {command.split()[0]}",
                        code=ErrorCode.HW_DEVICE_ERROR,
                        context={"command": command.split()[0], "reply": line},
                    )
                if line == expect:
                    return ""
                if line.startswith(expect + " "):
                    return line[len(expect) + 1 :].strip()
                log.debug("ignored line from board: %r", line[:200])
        except HardwareError:
            raise
        except errors as exc:
            self.close()
            raise HardwareError(
                f"serial link lost: {exc}",
                code=ErrorCode.HW_COM_DISCONNECTED,
                context={"port": self._port},
            ) from exc
        raise HardwareError(
            f"no {expect} reply to {command.split()[0]} within {wait:g} s",
            code=ErrorCode.HW_TIMEOUT,
            context={"command": command.split()[0]},
        )

    # ------------------------------------------------------------------ commands
    def ping(self) -> bool:
        """``False`` when the board does not answer correctly in ``timeouts.ping_s``."""
        try:
            self.command("PING", "PONG", timeout=self._settings().timeouts.ping_s)
        except HardwareError as exc:
            if exc.code is ErrorCode.HW_TIMEOUT:
                return False
            raise
        return True

    def read_sensor(self) -> SensorReading:
        payload = self.command("READ_SENSOR", "SENSOR")
        parts = payload.split()
        try:
            value = float(parts[0])
        except (IndexError, ValueError) as exc:
            raise HardwareError(
                f"bad sensor reply {payload!r}",
                code=ErrorCode.HW_DEVICE_ERROR,
                context={"reply": payload[:100]},
            ) from exc
        unit = parts[1] if len(parts) > 1 else ""
        return SensorReading(value=value, unit=unit, raw=payload, read_at=datetime.now(UTC))

    def get_id(self) -> str:
        return self.command("GET_ID", "ID")

    def set_id(self, device_id: str) -> bool:
        if not _ID_RE.match(device_id):
            raise InputError(f"device ID {device_id!r} cannot be sent to the board")
        try:
            self.command(f"SET_ID {device_id}", "OK")
        except HardwareError as exc:
            if exc.code is ErrorCode.HW_DEVICE_ERROR:
                return False
            raise
        return True

    def get_mac(self) -> str:
        return self.command("GET_MAC", "MAC")
