"""Secret storage.

Secrets (SMTP password, OAuth token, API token) are kept in the OS keyring - on Windows that
is the Credential Manager. ``settings.toml`` only stores the entry *name* (``*_ref`` keys).
"""

from __future__ import annotations

import logging
import threading
from typing import Protocol

from parkomate.core.errors import SecretMissingError

log = logging.getLogger(__name__)

KEYRING_SERVICE = "ParkomateStation"


class SecretStore(Protocol):
    def get(self, name: str) -> str | None: ...

    def set(self, name: str, value: str) -> None: ...

    def delete(self, name: str) -> None: ...


class KeyringSecretStore:
    """Secrets in the OS keyring under service ``ParkomateStation``."""

    def __init__(self, service: str = KEYRING_SERVICE) -> None:
        self._service = service

    def get(self, name: str) -> str | None:
        import keyring
        import keyring.errors

        try:
            value: str | None = keyring.get_password(self._service, name)
        except keyring.errors.KeyringError:
            log.exception("keyring read failed for entry %r", name)
            return None
        return value

    def set(self, name: str, value: str) -> None:
        import keyring

        keyring.set_password(self._service, name, value)

    def delete(self, name: str) -> None:
        import keyring
        import keyring.errors

        try:
            keyring.delete_password(self._service, name)
        except keyring.errors.PasswordDeleteError:
            log.debug("keyring entry %r did not exist", name)


class MemorySecretStore:
    """In-memory store for tests and development."""

    def __init__(self, initial: dict[str, str] | None = None) -> None:
        self._values = dict(initial or {})
        self._lock = threading.Lock()

    def get(self, name: str) -> str | None:
        with self._lock:
            return self._values.get(name)

    def set(self, name: str, value: str) -> None:
        with self._lock:
            self._values[name] = value

    def delete(self, name: str) -> None:
        with self._lock:
            self._values.pop(name, None)


def require_secret(store: SecretStore, name: str) -> str:
    """Return the secret ``name`` or raise ``SecretMissingError`` (never logs the value)."""
    value = store.get(name)
    if not value:
        raise SecretMissingError(f"keyring entry {name!r} is missing", params={"name": name})
    return value
