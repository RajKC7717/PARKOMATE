"""Firmware held in RAM only.

The images live in ``bytearray`` objects that are zeroed by :meth:`FirmwareStore.clear`
(called on logout / shutdown). Nothing is ever written to disk, a temp file, a log or a
report. On Windows each buffer is additionally locked into physical memory with
``VirtualLock`` so it is not written to the page file (best effort).

Limits of this guarantee in Python (documented in TECHNICAL.md):
* ``esptool.write_flash`` only accepts immutable ``bytes``: one copy exists while flashing.
  It is wiped with :func:`wipe_bytes` right after (CPython-specific, best effort); esptool's
  own compressed chunks are freed but not zeroed.
* Network chunks arrive as small ``bytes`` objects before being copied into the
  ``bytearray``; they are freed immediately but not zeroed.
"""

from __future__ import annotations

import ctypes
import hashlib
import logging
import os
import sys
import threading
from dataclasses import dataclass

from parkomate.core.models import FirmwareInfo

log = logging.getLogger(__name__)


@dataclass(slots=True)
class FirmwareImage:
    name: str
    offset: int
    data: bytearray
    sha256: str
    locked: bool = False


def _address(buf: bytearray) -> int:
    return ctypes.addressof((ctypes.c_char * len(buf)).from_buffer(buf))


def lock_memory(buf: bytearray) -> bool:
    """Keep ``buf`` out of the page file (Windows ``VirtualLock``). Best effort."""
    if os.name != "nt" or not buf:
        return False
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        ok = bool(kernel32.VirtualLock(ctypes.c_void_p(_address(buf)), ctypes.c_size_t(len(buf))))
    except (OSError, AttributeError, ValueError):
        return False
    if not ok:
        log.debug("VirtualLock refused (working set too small) - firmware stays pageable")
    return ok


def unlock_memory(buf: bytearray) -> None:
    if os.name != "nt" or not buf:
        return
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]
        kernel32.VirtualUnlock(ctypes.c_void_p(_address(buf)), ctypes.c_size_t(len(buf)))
    except (OSError, AttributeError, ValueError):
        log.debug("VirtualUnlock failed", exc_info=True)


def zero(buf: bytearray) -> None:
    """Overwrite in place (same memory, no reallocation)."""
    if buf:
        ctypes.memset(_address(buf), 0, len(buf))


def wipe_bytes(data: bytes) -> None:
    """Best-effort zeroing of an immutable ``bytes`` copy (CPython only).

    Only for buffers this module created and nobody else references (the copy handed to
    esptool, after it returned).
    """
    if sys.implementation.name != "cpython" or len(data) < 2:
        return  # CPython shares the empty and all 1-byte bytes objects - never touch those
    header = sys.getsizeof(b"") - 1  # offset of ob_sval inside a bytes object
    ctypes.memset(id(data) + header, 0, len(data))


def combined_sha256(images: list[FirmwareImage]) -> str:
    """Digest identifying the whole firmware set (single image: that image's SHA-256)."""
    if len(images) == 1:
        return images[0].sha256
    digest = hashlib.sha256()
    for image in sorted(images, key=lambda i: i.offset):
        digest.update(image.data)
    return digest.hexdigest()


class FirmwareStore:
    """The current firmware set, replaced atomically, zeroed on clear."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._images: list[FirmwareImage] = []
        self._info: FirmwareInfo | None = None

    @property
    def info(self) -> FirmwareInfo | None:
        with self._lock:
            return self._info

    def images(self) -> list[FirmwareImage]:
        with self._lock:
            return list(self._images)

    def replace(self, info: FirmwareInfo, images: list[FirmwareImage]) -> None:
        for image in images:
            image.locked = lock_memory(image.data)
        with self._lock:
            old = self._images
            self._images = images
            self._info = info
        self._wipe(old)

    def clear(self) -> None:
        with self._lock:
            old = self._images
            self._images = []
            self._info = None
        self._wipe(old)

    @staticmethod
    def _wipe(images: list[FirmwareImage]) -> None:
        for image in images:
            zero(image.data)
            if image.locked:
                unlock_memory(image.data)
                image.locked = False
