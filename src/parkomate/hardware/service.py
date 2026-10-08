"""RealHardwareService - the bench implementation of ``HardwareService`` (owner: Aditya).

Composition:

    PortScanner      serial ports, ESP32 bridges first, unplug detection
    DeviceLink       text protocol to the running firmware (PING / READ_SENSOR / GET_ID ...)
    EsptoolFlasher   MAC + chip via the ROM bootloader; flashing from RAM
    ServerClient     whitelist + firmware download (TLS, token from the keyring, retries)
    FirmwareStore    firmware in RAM only, zeroed on shutdown
    HttpMeasurementListener   measuring device JSON over Wi-Fi/LAN
    CameraService    USB QR camera + preview frames

Every method may block and runs on the UI's hardware worker thread (one at a time), except
:meth:`get_preview_frame`, which returns immediately. Every failure is a typed
``ParkomateError``.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable

from parkomate.config.secrets import SecretStore
from parkomate.config.settings import Settings
from parkomate.core.errors import ErrorCode, HardwareError
from parkomate.core.interfaces import ProgressCallback
from parkomate.core.mac import normalise_mac
from parkomate.core.models import (
    FirmwareInfo,
    FlashResult,
    Measurement,
    PortInfo,
    PreviewFrame,
    SensorReading,
    WhitelistResult,
)
from parkomate.hardware.camera import CameraService
from parkomate.hardware.firmware import FirmwareStore
from parkomate.hardware.flasher import EsptoolFlasher
from parkomate.hardware.link import DeviceLink, PortGuard
from parkomate.hardware.measurement import HttpMeasurementListener, MeasurementTransport
from parkomate.hardware.ports import PortScanner
from parkomate.hardware.server import ServerClient

log = logging.getLogger(__name__)


class RealHardwareService:
    def __init__(
        self,
        settings: Callable[[], Settings],
        secrets: SecretStore,
        *,
        scanner: PortScanner | None = None,
        link: DeviceLink | None = None,
        flasher: EsptoolFlasher | None = None,
        server: ServerClient | None = None,
        measurement: MeasurementTransport | None = None,
        camera: CameraService | None = None,
    ) -> None:
        self._settings = settings
        guard = link.guard if link is not None else PortGuard()
        self._scanner = scanner or PortScanner()
        self._link = link or DeviceLink(settings, guard=guard)
        self._flasher = flasher or EsptoolFlasher(settings, guard)
        self._server = server or ServerClient(settings, secrets)
        self._measurement = measurement or HttpMeasurementListener(settings)
        self._camera = camera or CameraService(settings)
        self._store = FirmwareStore()
        self._lock = threading.RLock()
        self._port: str | None = None
        self._chip = ""

    # ------------------------------------------------------------------ serial port
    def list_ports(self) -> list[PortInfo]:
        return self._scanner.list_ports()

    def connect(self, port: str) -> None:
        if not self._scanner.exists(port):
            raise HardwareError(
                f"port {port} not found", code=ErrorCode.HW_NO_PORT, params={"port": port}
            )
        with self._lock:
            if port != self._port:
                self._chip = ""
            self._port = port
            self._link.attach(port)

    def disconnect(self) -> None:
        with self._lock:
            self._link.detach()
            self._port = None
            self._chip = ""

    def is_connected(self) -> bool:
        port = self._port
        return port is not None and self._scanner.exists(port)

    def _require_port(self) -> str:
        port = self._port
        if port is None or not self._scanner.exists(port):
            raise HardwareError("board not connected", code=ErrorCode.HW_COM_DISCONNECTED)
        return port

    # ------------------------------------------------------------------ identity
    def read_mac(self) -> str:
        port = self._require_port()
        if self._settings().serial.mac_source == "link":
            return normalise_mac(self._link.get_mac())
        self._link.close()  # the ROM bootloader needs the port
        info = self._flasher.chip_info(port)
        self._chip = info.description
        self._link.expect_boot()  # the chip was hard-reset
        return normalise_mac(info.mac)

    def chip_name(self) -> str:
        return self._chip

    # ------------------------------------------------------------------ server
    def check_whitelist(self, mac: str) -> WhitelistResult:
        return self._server.check_whitelist(mac)

    def fetch_firmware(self) -> FirmwareInfo:
        info, images = self._server.fetch_firmware()
        self._store.replace(info, images)
        return info

    def firmware_info(self) -> FirmwareInfo | None:
        return self._store.info

    # ------------------------------------------------------------------ programming
    def flash(self, progress_cb: ProgressCallback) -> FlashResult:
        port = self._require_port()
        images = self._store.images()
        if not images:
            raise HardwareError("firmware not loaded", code=ErrorCode.FW_NOT_LOADED)
        self._link.close()  # the flasher owns the port while writing
        result = self._flasher.flash(port, images, progress_cb)
        if result.success:
            self._link.expect_boot()
        return result

    # ------------------------------------------------------------------ device link
    def ping(self) -> bool:
        self._require_port()
        return self._link.ping()

    def read_sensor(self) -> SensorReading:
        self._require_port()
        return self._link.read_sensor()

    def get_device_id(self) -> str:
        self._require_port()
        return self._link.get_id()

    def set_device_id(self, device_id: str) -> bool:
        self._require_port()
        return self._link.set_id(device_id)

    # ------------------------------------------------------------------ measurement
    def measure(self, timeout_s: float) -> Measurement:
        return self._measurement.measure(timeout_s)

    def measure_ambient(self) -> float:
        return self._measurement.measure_ambient(self._settings().measurement.ambient_timeout_s)

    # ------------------------------------------------------------------ camera
    def open_camera(self) -> None:
        self._camera.open()

    def read_qr(self, timeout_s: float) -> str | None:
        return self._camera.read_qr(timeout_s)

    def get_preview_frame(self) -> PreviewFrame | None:
        return self._camera.get_preview_frame()

    def close_camera(self) -> None:
        self._camera.close()

    # ------------------------------------------------------------------ lifecycle
    def shutdown(self) -> None:
        self._store.clear()
        for step in (self._link.detach, self._camera.close, self._measurement.stop):
            try:
                step()
            except Exception:
                log.exception("hardware shutdown step failed")
        self._port = None
