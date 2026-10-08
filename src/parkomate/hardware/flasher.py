"""Flashing and chip identification through esptool's public Python API (esptool 5).

* ``chip_info`` - enter the ROM bootloader, read the factory MAC from eFuse and the chip
  description, hard-reset. Works on blank boards (no firmware needed).
* ``flash`` - detect chip → stub → (faster baud) → attach flash → ``write_flash`` from RAM
  (esptool verifies every image's MD5 after writing) → hard reset.

Progress comes from esptool's logger hook (``TemplateLogger.progress_bar``) and is mapped
to one 0-100 % bar across all images.

Errors: a board that cannot be put into download mode → ``HW_HOLD_BOOT`` (the screen tells
the operator to hold BOOT); port missing / busy → ``HW_NO_PORT`` / ``HW_PORT_BUSY``; the
port vanishing mid-write → ``HW_COM_DISCONNECTED``; a write/verify failure the board
survived → ``FlashResult(success=False, error_code=HW_FLASH_FAILED)``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import Any

from parkomate.config.settings import Settings
from parkomate.core.errors import ErrorCode, HardwareError
from parkomate.core.interfaces import ProgressCallback
from parkomate.core.models import FlashResult
from parkomate.hardware.firmware import FirmwareImage, wipe_bytes
from parkomate.hardware.link import PortGuard, map_serial_open_error

log = logging.getLogger(__name__)

_CONNECT_MODES = {
    "default_reset": "default-reset",
    "no_reset": "no-reset",
    "usb_reset": "usb-reset",
}
_BOOT_HINTS = ("failed to connect", "wrong boot mode", "download mode", "no serial data")
_PORT_HINTS = ("could not open port", "could not configure port")


@dataclass(frozen=True, slots=True)
class ChipInfo:
    mac: str
    description: str


def _esptool_api() -> ModuleType:
    import esptool.cmds

    return esptool.cmds


class ProgressMapper:
    """Turns esptool's per-image progress into one monotonic 0-100 % value."""

    def __init__(self, sizes: Sequence[int], callback: ProgressCallback) -> None:
        total = sum(sizes) or 1
        self._weights = [size / total for size in sizes] or [1.0]
        self._callback = callback
        self._index = 0
        self._last_fraction = 0.0
        self._last_percent = -1

    def update(self, current: int, total: int) -> None:
        if total <= 0:
            return
        fraction = min(1.0, max(0.0, current / total))
        if fraction + 0.2 < self._last_fraction and self._index < len(self._weights) - 1:
            self._index += 1  # esptool restarted the bar: next image
        self._last_fraction = fraction
        done = sum(self._weights[: self._index]) + self._weights[self._index] * fraction
        percent = min(99, int(done * 100))  # 100 only after verify + reset
        if percent > self._last_percent:
            self._last_percent = percent
            self._callback(percent)

    def finish(self) -> None:
        self._callback(100)


def _make_logger(mapper: ProgressMapper) -> Any:
    from esptool.logger import TemplateLogger

    class _ProgressLogger(TemplateLogger):  # type: ignore[misc]
        def print(self, *args: Any, **kwargs: Any) -> None:
            log.debug("esptool: %s", " ".join(str(a) for a in args))

        def note(self, message: str) -> None:
            log.debug("esptool note: %s", message)

        def warning(self, message: str) -> None:
            log.info("esptool warning: %s", message)

        def error(self, message: str) -> None:
            log.info("esptool error: %s", message)

        def stage(self, finish: bool = False) -> None:
            pass

        def progress_bar(
            self,
            cur_iter: int,
            total_iters: int,
            prefix: str = "",
            suffix: str = "",
            bar_length: int = 30,
        ) -> None:
            mapper.update(cur_iter, total_iters)

        def set_verbosity(self, verbosity: Any) -> None:
            pass

    return _ProgressLogger()


class _LoggerScope:
    """Install the progress logger for one esptool operation, then restore the old one."""

    def __init__(self, mapper: ProgressMapper | None) -> None:
        self._mapper = mapper
        self._previous: Any = None
        self._installed = False

    def __enter__(self) -> None:
        try:
            from esp_pylib.logger import EspLog
            from esptool.logger import log as esptool_log

            self._previous = EspLog.instance
            esptool_log.set_logger(_make_logger(self._mapper or ProgressMapper([1], _noop)))
            self._installed = True
        except Exception:  # logging is a convenience; never block flashing on it
            log.warning("esptool progress hook unavailable", exc_info=True)

    def __exit__(self, *_exc: object) -> None:
        if self._installed:
            from esp_pylib.logger import EspLog

            EspLog.instance = self._previous


def _noop(_value: int) -> None:
    return None


def _serial_errors() -> tuple[type[BaseException], ...]:
    import serial

    return (serial.SerialException, OSError)


def _message(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


class EsptoolFlasher:
    def __init__(
        self,
        settings: Callable[[], Settings],
        guard: PortGuard,
        *,
        api: Any = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._guard = guard
        self._api = api
        self._monotonic = monotonic

    @property
    def api(self) -> Any:
        if self._api is None:
            self._api = _esptool_api()
        return self._api

    def _connect(self, port: str) -> Any:
        mode = _CONNECT_MODES[self._settings().programming.connect_mode]
        try:
            return self.api.detect_chip(port=port, baud=115200, connect_mode=mode,
                                        connect_attempts=3)
        except Exception as exc:
            raise self._map_connect_error(exc, port) from exc

    def _map_connect_error(self, exc: BaseException, port: str) -> HardwareError:
        text = str(exc).lower()
        if any(hint in text for hint in _PORT_HINTS):
            return map_serial_open_error(exc, port)
        if any(hint in text for hint in _BOOT_HINTS):
            return HardwareError(
                f"board did not enter download mode: {exc}",
                code=ErrorCode.HW_HOLD_BOOT,
                context={"port": port},
            )
        if isinstance(exc, _serial_errors()):
            return HardwareError(f"serial error: {_message(exc)}",
                                 code=ErrorCode.HW_COM_DISCONNECTED, context={"port": port})
        return HardwareError(f"esptool: {_message(exc)}", code=ErrorCode.HW_DEVICE_ERROR,
                             context={"port": port})

    @staticmethod
    def _close(esp: Any) -> None:
        try:
            esp._port.close()  # noqa: SLF001 - esptool exposes no public close
        except Exception:
            log.debug("closing esptool port failed", exc_info=True)

    def chip_info(self, port: str) -> ChipInfo:
        with self._guard, _LoggerScope(None):
            esp = self._connect(port)
            try:
                raw = esp.read_mac("BASE_MAC")
                description = str(esp.get_chip_description())
                self.api.reset_chip(esp, "hard-reset")
            except Exception as exc:
                raise self._map_connect_error(exc, port) from exc
            finally:
                self._close(esp)
        mac = ":".join(f"{int(b):02X}" for b in raw)
        return ChipInfo(mac=mac, description=description)

    def flash(
        self, port: str, images: Sequence[FirmwareImage], progress: ProgressCallback
    ) -> FlashResult:
        if not images:
            raise HardwareError("firmware not loaded", code=ErrorCode.FW_NOT_LOADED)
        settings = self._settings().programming
        started = self._monotonic()
        mapper = ProgressMapper([len(i.data) for i in images], progress)
        progress(0)
        payload: list[tuple[int, bytes]] = []
        written = 0
        with self._guard, _LoggerScope(mapper):
            esp = self._connect(port)
            try:
                esp = self.api.run_stub(esp)
                if settings.flash_baud != 115200:
                    esp.change_baud(settings.flash_baud)
                self.api.attach_flash(esp)
                # esptool needs immutable bytes: the only copies, wiped right after.
                payload = [(i.offset, bytes(i.data)) for i in sorted(images, key=lambda x: x.offset)]
                self.api.write_flash(esp, payload, compress=True, erase_all=settings.erase_all)
                written = sum(len(data) for _, data in payload)
                self.api.reset_chip(esp, "hard-reset")
            except _serial_errors() as exc:
                raise HardwareError(
                    f"serial port lost while flashing: {_message(exc)}",
                    code=ErrorCode.HW_COM_DISCONNECTED,
                    context={"port": port},
                ) from exc
            except Exception as exc:
                log.warning("flash failed: %s", _message(exc))
                return FlashResult(
                    success=False,
                    error_code=ErrorCode.HW_FLASH_FAILED,
                    message=_message(exc)[:500],
                    duration_s=round(self._monotonic() - started, 2),
                )
            finally:
                for _, data in payload:
                    wipe_bytes(data)
                payload.clear()
                self._close(esp)
        mapper.finish()
        return FlashResult(
            success=True,
            duration_s=round(self._monotonic() - started, 2),
            bytes_written=written,
        )
