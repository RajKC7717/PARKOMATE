"""Serial port discovery. Known ESP32 USB-UART bridges are ranked first."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

from parkomate.core.models import PortInfo

ESPRESSIF_VID = 0x303A

KNOWN_BRIDGES: dict[tuple[int, int], str] = {
    (0x10C4, 0xEA60): "Silicon Labs CP210x",
    (0x10C4, 0xEA70): "Silicon Labs CP2105",
    (0x10C4, 0xEA71): "Silicon Labs CP2108",
    (0x1A86, 0x7523): "WCH CH340",
    (0x1A86, 0x7522): "WCH CH340K",
    (0x1A86, 0x5523): "WCH CH341",
    (0x1A86, 0x55D3): "WCH CH343",
    (0x1A86, 0x55D4): "WCH CH9102",
    (0x0403, 0x6001): "FTDI FT232R",
    (0x0403, 0x6010): "FTDI FT2232",
    (0x0403, 0x6014): "FTDI FT232H",
    (0x0403, 0x6015): "FTDI FT-X",
}
"""USB-UART bridges used on ESP32 boards. Any Espressif VID (0x303A) - the native USB of
ESP32-S2/S3/C3/C6 - also counts."""

Comports = Callable[[], Iterable[Any]]


def is_esp_candidate(vid: int | None, pid: int | None) -> bool:
    if vid is None or pid is None:
        return False
    return vid == ESPRESSIF_VID or (vid, pid) in KNOWN_BRIDGES


def _natural_key(name: str) -> tuple[str, int]:
    match = re.match(r"^(.*?)(\d+)$", name)
    if match:
        return match.group(1).upper(), int(match.group(2))
    return name.upper(), -1


def _default_comports() -> Iterable[Any]:
    from serial.tools import list_ports

    return list_ports.comports()


class PortScanner:
    """Wraps ``serial.tools.list_ports.comports`` (injectable for tests)."""

    def __init__(self, comports: Comports | None = None) -> None:
        self._comports = comports or _default_comports

    def list_ports(self) -> list[PortInfo]:
        ports = [
            PortInfo(
                name=str(port.device),
                description=str(port.description or ""),
                vid=port.vid,
                pid=port.pid,
                serial_number=port.serial_number,
                is_esp_candidate=is_esp_candidate(port.vid, port.pid),
            )
            for port in self._comports()
        ]
        return sorted(ports, key=lambda p: (not p.is_esp_candidate, _natural_key(p.name)))

    def exists(self, name: str) -> bool:
        return any(str(port.device) == name for port in self._comports())
