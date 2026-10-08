"""USB QR camera.

* Capture: OpenCV ``VideoCapture`` (DirectShow on Windows by default) in a background thread
  at ``camera.fps``; the latest frame is kept for decoding and a downscaled RGB copy for the
  UI preview (``get_preview_frame`` never blocks).
* Decode: pyzbar (ZBar) first, OpenCV's ``QRCodeDetector`` as fallback (also used when the
  ZBar DLL is missing).
* A decoded text must match ``camera.id_pattern``; if only non-matching codes are seen until
  the timeout → ``QR_BAD_FORMAT``; nothing readable → ``None``; no camera → ``CAM_NOT_FOUND``.
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
from collections.abc import Callable
from typing import Any, Protocol

from parkomate.config.settings import CameraSettings, Settings
from parkomate.core.errors import CameraError, ErrorCode
from parkomate.core.models import PreviewFrame

log = logging.getLogger(__name__)

PREVIEW_WIDTH = 640
MAX_READ_FAILURES = 30


class FrameSource(Protocol):
    """Yields BGR frames (numpy arrays) - OpenCV in production, a fake in tests."""

    def open(self) -> None: ...

    def read(self) -> Any | None: ...

    def close(self) -> None: ...


class QrDecoder(Protocol):
    def decode(self, frame: Any) -> list[str]: ...


class OpenCvFrameSource:
    def __init__(self, settings: CameraSettings) -> None:
        self._settings = settings
        self._capture: Any = None

    def _backend(self) -> int:
        import cv2

        backend = self._settings.backend
        if backend == "auto":
            return int(cv2.CAP_DSHOW) if os.name == "nt" else int(cv2.CAP_ANY)
        return int({"dshow": cv2.CAP_DSHOW, "msmf": cv2.CAP_MSMF, "any": cv2.CAP_ANY}[backend])

    def open(self) -> None:
        import cv2

        capture = cv2.VideoCapture(self._settings.index, self._backend())
        if not capture.isOpened():
            capture.release()
            raise CameraError(
                f"camera {self._settings.index} not available", code=ErrorCode.CAM_NOT_FOUND
            )
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._settings.width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._settings.height)
        capture.set(cv2.CAP_PROP_FPS, self._settings.fps)
        self._capture = capture

    def read(self) -> Any | None:
        if self._capture is None:
            return None
        ok, frame = self._capture.read()
        return frame if ok else None

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None


class ZbarOpenCvDecoder:
    """pyzbar first (fast, robust); OpenCV ``QRCodeDetector`` as fallback."""

    def __init__(self) -> None:
        self._zbar: Any = None
        self._zbar_failed = False
        self._detector: Any = None

    def _pyzbar(self) -> Any:
        if self._zbar is None and not self._zbar_failed:
            try:
                from pyzbar import pyzbar

                self._zbar = pyzbar
            except (ImportError, OSError):  # ZBar DLL missing
                log.warning("pyzbar unavailable - using OpenCV QR detector only")
                self._zbar_failed = True
        return self._zbar

    def decode(self, frame: Any) -> list[str]:
        import cv2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        texts: list[str] = []
        zbar = self._pyzbar()
        if zbar is not None:
            try:
                for symbol in zbar.decode(gray, symbols=[zbar.ZBarSymbol.QRCODE]):
                    texts.append(symbol.data.decode("utf-8", errors="replace"))
            except Exception:
                log.debug("pyzbar decode failed", exc_info=True)
        if not texts:
            if self._detector is None:
                self._detector = cv2.QRCodeDetector()
            text, _points, _ = self._detector.detectAndDecode(gray)
            if text:
                texts.append(text)
        return [t.strip() for t in dict.fromkeys(texts) if t.strip()]


class CameraService:
    def __init__(
        self,
        settings: Callable[[], Settings],
        *,
        source_factory: Callable[[CameraSettings], FrameSource] | None = None,
        decoder: QrDecoder | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._factory = source_factory or OpenCvFrameSource
        self._decoder: QrDecoder = decoder or ZbarOpenCvDecoder()
        self._monotonic = monotonic
        self._cond = threading.Condition()
        self._source: FrameSource | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._frame: Any = None
        self._seq = 0
        self._preview: PreviewFrame | None = None
        self._lost = False

    @property
    def is_open(self) -> bool:
        return self._running

    def open(self) -> None:
        if self._running:
            return
        source = self._factory(self._settings().camera)
        source.open()
        self._source = source
        self._running = True
        self._lost = False
        self._thread = threading.Thread(target=self._loop, name="camera", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._running = False
        thread = self._thread
        if thread is not None:
            thread.join(timeout=3)
        self._thread = None
        if self._source is not None:
            self._source.close()
            self._source = None
        with self._cond:
            self._frame = None
            self._preview = None
            self._cond.notify_all()

    def _loop(self) -> None:
        failures = 0
        interval = 1.0 / max(1, self._settings().camera.fps)
        while self._running and self._source is not None:
            started = self._monotonic()
            frame = self._source.read()
            if frame is None:
                failures += 1
                if failures >= MAX_READ_FAILURES:
                    log.error("camera stopped delivering frames",
                              extra={"error_code": ErrorCode.CAM_NOT_FOUND.value})
                    with self._cond:
                        self._lost = True
                        self._cond.notify_all()
                    return
                time.sleep(0.05)
                continue
            failures = 0
            preview = _to_preview(frame)
            with self._cond:
                self._frame = frame
                self._preview = preview
                self._seq += 1
                self._cond.notify_all()
            remaining = interval - (self._monotonic() - started)
            if remaining > 0:
                time.sleep(remaining)

    def get_preview_frame(self) -> PreviewFrame | None:
        with self._cond:
            return self._preview

    def read_qr(self, timeout_s: float) -> str | None:
        if not self._running:
            raise CameraError("camera is not open", code=ErrorCode.CAM_NOT_FOUND)
        pattern = re.compile(self._settings().camera.id_pattern)
        deadline = self._monotonic() + timeout_s
        seen_seq = -1
        wrong: list[str] = []
        while self._monotonic() < deadline:
            with self._cond:
                self._cond.wait_for(
                    lambda: self._seq != seen_seq or self._lost or not self._running,
                    timeout=max(0.0, min(0.3, deadline - self._monotonic())),
                )
                if self._lost or not self._running:
                    raise CameraError("camera stopped delivering frames",
                                      code=ErrorCode.CAM_NOT_FOUND)
                if self._seq == seen_seq or self._frame is None:
                    continue
                seen_seq = self._seq
                frame = self._frame
            for text in self._decoder.decode(frame):
                if pattern.fullmatch(text):
                    return text
                if text not in wrong:
                    wrong.append(text)
        if wrong:
            raise CameraError(
                "QR code does not contain a valid device ID",
                code=ErrorCode.QR_BAD_FORMAT,
                params={"value": wrong[0][:40]},
            )
        return None


def _to_preview(frame: Any) -> PreviewFrame | None:
    try:
        import cv2

        height, width = frame.shape[:2]
        if width > PREVIEW_WIDTH:
            scale = PREVIEW_WIDTH / width
            frame = cv2.resize(frame, (PREVIEW_WIDTH, max(1, int(height * scale))))
            height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return PreviewFrame(width=int(width), height=int(height), rgb=rgb.tobytes())
    except Exception:
        log.debug("preview conversion failed", exc_info=True)
        return None
