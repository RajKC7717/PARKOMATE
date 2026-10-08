"""Parkomate server API: MAC whitelist and firmware download.

Assumed API (to be confirmed with the client - see DECISIONS.md):

``POST {base_url}{whitelist_path}``  JSON ``{"mac": "AA:..", "station_id": "..."}``
    200 ``{"allowed": true|false, "reason": "..."}`` - 404 = not registered (denied)

``GET {base_url}{firmware_path}``
    * ``application/octet-stream``: one application image; headers ``X-Firmware-Name``,
      ``X-Firmware-Version``, ``X-Firmware-SHA256`` (hex).
    * ``application/json``: manifest ``{"name", "version", "images": [{"name", "url",
      "sha256", "offset"?}]}`` - each image downloaded and verified; offsets default to the
      ``programming.*_offset`` settings by image name.

Authentication: ``Authorization: Bearer <token>`` from the keyring (``server.api_token_ref``).
TLS is verified (optionally with a company CA bundle). Network errors and HTTP 5xx are
retried with exponential back-off; 401/403 → ``API_UNAUTHORISED``; anything malformed →
``API_BAD_RESPONSE``; a hash mismatch → ``FW_HASH_MISMATCH``.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin

import httpx

from parkomate import __version__
from parkomate.config.secrets import SecretStore, require_secret
from parkomate.config.settings import Settings
from parkomate.core.errors import ErrorCode, ServerError
from parkomate.core.models import FirmwareInfo, WhitelistResult
from parkomate.hardware.firmware import FirmwareImage, combined_sha256, zero

log = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 16 * 1024 * 1024  # largest ESP32 flash
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


class ServerClient:
    def __init__(
        self,
        settings: Callable[[], Settings],
        secrets: SecretStore,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._secrets = secrets
        self._transport = transport
        self._sleep = sleep

    # ------------------------------------------------------------------ plumbing
    def _client(self) -> httpx.Client:
        settings = self._settings()
        server = settings.server
        verify: bool | str = (server.ca_bundle or True) if server.verify_tls else False
        token = require_secret(self._secrets, server.api_token_ref)
        return httpx.Client(
            base_url=server.base_url,
            timeout=httpx.Timeout(settings.timeouts.api_s),
            verify=verify,
            transport=self._transport,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": f"ParkomateStation/{__version__}",
                "X-Station-Id": settings.station.station_id,
            },
            follow_redirects=True,
        )

    def _send(self, client: httpx.Client, request: httpx.Request, *, stream: bool = False
              ) -> httpx.Response:
        retries = self._settings().server.retries
        attempt = 0
        while True:
            attempt += 1
            try:
                response = client.send(request, stream=stream)
            except httpx.TransportError as exc:
                if attempt <= retries:
                    self._backoff(attempt, str(exc))
                    continue
                raise ServerError(
                    f"server unreachable: {type(exc).__name__}: {exc}",
                    code=ErrorCode.API_UNREACHABLE,
                    context={"url": str(request.url)},
                ) from exc
            if response.status_code >= 500 and attempt <= retries:
                response.close()
                self._backoff(attempt, f"HTTP {response.status_code}")
                continue
            if response.status_code in (401, 403):
                response.close()
                raise ServerError(
                    f"server refused the station token (HTTP {response.status_code})",
                    code=ErrorCode.API_UNAUTHORISED,
                    context={"url": str(request.url)},
                )
            return response

    def _backoff(self, attempt: int, why: str) -> None:
        delay = min(0.5 * 2 ** (attempt - 1), 8.0)
        log.warning("server request failed (%s) - retry %d in %.1f s", why, attempt, delay)
        self._sleep(delay)

    @staticmethod
    def _bad(message: str, **context: Any) -> ServerError:
        return ServerError(message, code=ErrorCode.API_BAD_RESPONSE, context=context)

    # ------------------------------------------------------------------ whitelist
    def check_whitelist(self, mac: str) -> WhitelistResult:
        settings = self._settings()
        with self._client() as client:
            request = client.build_request(
                "POST",
                settings.server.whitelist_path,
                json={"mac": mac, "station_id": settings.station.station_id},
            )
            response = self._send(client, request)
        now = datetime.now(UTC)
        if response.status_code == 404:
            return WhitelistResult(mac_address=mac, allowed=False, reason="not registered",
                                   checked_at=now)
        if response.status_code != 200:
            raise self._bad(f"whitelist answered HTTP {response.status_code}",
                            status=response.status_code)
        try:
            body = response.json()
            allowed = body["allowed"]
        except (ValueError, KeyError, TypeError) as exc:
            raise self._bad("whitelist reply is not the expected JSON") from exc
        if not isinstance(allowed, bool):
            raise self._bad("whitelist 'allowed' is not true/false")
        reason = body.get("reason")
        return WhitelistResult(
            mac_address=mac,
            allowed=allowed,
            reason=str(reason) if reason else None,
            checked_at=now,
        )

    # ------------------------------------------------------------------ firmware
    def fetch_firmware(self) -> tuple[FirmwareInfo, list[FirmwareImage]]:
        """Download into RAM and verify. Returns metadata + images (never touches disk)."""
        settings = self._settings()
        images: list[FirmwareImage] = []
        try:
            with self._client() as client:
                request = client.build_request(
                    "GET",
                    settings.server.firmware_path,
                    headers={"Accept": "application/octet-stream, application/json"},
                )
                response = self._send(client, request, stream=True)
                try:
                    content_type = response.headers.get("content-type", "")
                    if response.status_code != 200:
                        raise self._bad(f"firmware answered HTTP {response.status_code}",
                                        status=response.status_code)
                    if content_type.startswith("application/json"):
                        response.read()
                        name, version = self._manifest(client, response, images)
                    else:
                        name, version = self._single(response, images)
                finally:
                    response.close()
        except BaseException:
            for image in images:
                zero(image.data)
            raise
        info = FirmwareInfo(
            name=name,
            version=version,
            sha256=combined_sha256(images),
            size=sum(len(i.data) for i in images),
            hash_verified=True,
        )
        log.info("firmware %s %s loaded into RAM (%d image(s), %d bytes)",
                 name, version, len(images), info.size)
        return info, images

    def _single(self, response: httpx.Response, images: list[FirmwareImage]) -> tuple[str, str]:
        headers = response.headers
        expected = headers.get("x-firmware-sha256", "")
        version = headers.get("x-firmware-version", "")
        name = headers.get("x-firmware-name", "") or _filename(headers) or "firmware.bin"
        if not _HEX64.match(expected) or not version:
            raise self._bad("firmware headers X-Firmware-Version / X-Firmware-SHA256 missing")
        offset = self._settings().programming.app_offset
        images.append(self._download_body(response, "app", offset, expected))
        return name, version

    def _manifest(
        self, client: httpx.Client, response: httpx.Response, images: list[FirmwareImage]
    ) -> tuple[str, str]:
        try:
            manifest = response.json()
            name = str(manifest["name"])
            version = str(manifest["version"])
            entries = list(manifest["images"])
        except (ValueError, KeyError, TypeError) as exc:
            raise self._bad("firmware manifest is not the expected JSON") from exc
        if not entries:
            raise self._bad("firmware manifest lists no images")
        programming = self._settings().programming
        for entry in entries:
            try:
                image_name = str(entry["name"])
                url = str(entry["url"])
                expected = str(entry["sha256"])
            except (KeyError, TypeError) as exc:
                raise self._bad("manifest image entry incomplete") from exc
            offset = entry.get("offset")
            if offset is None:
                offset = programming.offset_for(image_name)
            if not isinstance(offset, int) or offset < 0:
                raise self._bad(f"no flash offset for image {image_name!r}")
            if not _HEX64.match(expected):
                raise self._bad(f"bad sha256 for image {image_name!r}")
            target = urljoin(str(response.url), url)
            request = client.build_request("GET", target,
                                           headers={"Accept": "application/octet-stream"})
            image_response = self._send(client, request, stream=True)
            try:
                if image_response.status_code != 200:
                    raise self._bad(f"image {image_name!r} answered HTTP "
                                    f"{image_response.status_code}")
                images.append(self._download_body(image_response, image_name, offset, expected))
            finally:
                image_response.close()
        offsets = [i.offset for i in images]
        if len(set(offsets)) != len(offsets):
            raise self._bad("two firmware images share a flash offset")
        return name, version

    def _download_body(
        self, response: httpx.Response, name: str, offset: int, expected: str
    ) -> FirmwareImage:
        length = response.headers.get("content-length")
        size = int(length) if length and length.isdigit() else None
        if size is not None and size > MAX_IMAGE_BYTES:
            raise self._bad(f"image {name!r} too large ({size} bytes)")
        # Pre-allocate when the size is known so the buffer is never reallocated (a
        # reallocation would leave a stale, un-zeroed copy behind).
        data = bytearray(size) if size is not None else bytearray()
        received = 0
        digest = hashlib.sha256()
        try:
            for chunk in response.iter_bytes():
                if size is not None:
                    if received + len(chunk) > size:
                        raise self._bad(f"image {name!r} longer than announced")
                    data[received : received + len(chunk)] = chunk
                else:
                    if received + len(chunk) > MAX_IMAGE_BYTES:
                        raise self._bad(f"image {name!r} too large")
                    data.extend(chunk)
                digest.update(chunk)
                received += len(chunk)
        except httpx.TransportError as exc:
            zero(data)
            raise ServerError(f"firmware download interrupted: {exc}",
                              code=ErrorCode.API_UNREACHABLE) from exc
        except BaseException:
            zero(data)
            raise
        if size is not None and received != size:
            zero(data)
            raise self._bad(f"image {name!r} shorter than announced")
        actual = digest.hexdigest()
        if actual.lower() != expected.lower():
            zero(data)
            raise ServerError(
                f"firmware image {name!r} hash mismatch",
                code=ErrorCode.FW_HASH_MISMATCH,
                context={"image": name, "expected": expected, "actual": actual},
            )
        return FirmwareImage(name=name, offset=offset, data=data, sha256=actual)


def _filename(headers: httpx.Headers) -> str | None:
    disposition = headers.get("content-disposition", "")
    match = re.search(r'filename="?([^";]+)"?', disposition)
    return match.group(1) if match else None
