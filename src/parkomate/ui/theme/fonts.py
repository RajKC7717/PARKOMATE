"""Bundled fonts: Noto Sans (Latin), Noto Sans Devanagari (Marathi), Noto Sans Symbols 2
(✓ ✕). All SIL Open Font License (assets/fonts/OFL.txt)."""

from __future__ import annotations

import logging
from importlib import resources

from PySide6.QtGui import QFont, QFontDatabase

from parkomate.ui.theme.tokens import SIZES

log = logging.getLogger(__name__)

FONT_FILES = (
    "NotoSans-Regular.ttf",
    "NotoSans-Bold.ttf",
    "NotoSansDevanagari-Regular.ttf",
    "NotoSansDevanagari-Bold.ttf",
    "NotoSansSymbols2-Regular.ttf",
)
# Latin first, then Devanagari for Marathi, then symbols (✓ ✕) - Qt falls back in this order.
FAMILIES = ["Noto Sans", "Noto Sans Devanagari", "Noto Sans Symbols 2"]

_loaded: list[str] = []


def load_fonts() -> list[str]:
    """Register the bundled fonts with Qt (idempotent). Returns the loaded families."""
    if _loaded:
        return list(_loaded)
    folder = resources.files("parkomate.ui.assets").joinpath("fonts")
    for name in FONT_FILES:
        data = folder.joinpath(name).read_bytes()
        font_id = QFontDatabase.addApplicationFontFromData(data)
        if font_id < 0:
            log.warning("could not load bundled font %s", name)
            continue
        for family in QFontDatabase.applicationFontFamilies(font_id):
            if family not in _loaded:
                _loaded.append(family)
    # Qt shapes '·', '°' etc. inside Marathi text with the Devanagari font, which lacks them.
    # Substitutes make Qt fall back per glyph (otherwise they show as empty boxes, especially
    # once a stylesheet is applied).
    QFont.insertSubstitutions("Noto Sans Devanagari", ["Noto Sans", "Noto Sans Symbols 2"])
    QFont.insertSubstitutions("Noto Sans", ["Noto Sans Devanagari", "Noto Sans Symbols 2"])
    return list(_loaded)


def app_font() -> QFont:
    """Base UI font: Noto Sans with Devanagari fallback, 18 px."""
    font = QFont()
    font.setFamilies(FAMILIES)
    font.setPixelSize(SIZES.font_base)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def font(px: int, *, bold: bool = False) -> QFont:
    f = app_font()
    f.setPixelSize(px)
    f.setBold(bold)
    return f
