"""MAC address normalisation (shared by hardware and records)."""

from __future__ import annotations

import re

from parkomate.core.errors import InputError

_MAC_HEX = re.compile(r"^[0-9A-F]{12}$")


def normalise_mac(mac: str) -> str:
    """``24-6f-28-aa-bb-cc`` / ``246F28AABBCC`` -> ``24:6F:28:AA:BB:CC``."""
    compact = re.sub(r"[\s:\-.]", "", mac).upper()
    if not _MAC_HEX.match(compact):
        raise InputError(f"invalid MAC address {mac!r}", params={"value": mac})
    return ":".join(compact[i : i + 2] for i in range(0, 12, 2))
