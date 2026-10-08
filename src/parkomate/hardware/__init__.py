"""Hardware + server integration (owner: Aditya).

* :class:`RealHardwareService` - the bench: serial ports, ESP32 link, esptool flashing,
  server API, measuring device, QR camera.
* :mod:`.mocks` - simulated bench (development, demos, tests).
* :mod:`.replay` - record a real session and replay it.
"""

from parkomate.hardware.replay import ReplayHardwareService, RecordingHardwareService
from parkomate.hardware.service import RealHardwareService

__all__ = ["RealHardwareService", "RecordingHardwareService", "ReplayHardwareService"]
