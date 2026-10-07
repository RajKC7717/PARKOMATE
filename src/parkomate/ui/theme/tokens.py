"""Design tokens: every colour, size and spacing the UI uses, in one place.

Rules (see CLAUDE.md):
* light, neutral background; ONE accent colour for actions;
* green / red / amber are reserved for status and never used decoratively;
* status is never shown by colour alone (icon + word + colour);
* text contrast >= WCAG AA everywhere, >= AAA (7:1) for status text
  (checked by ``tests/ui/test_theme.py``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Colors:
    bg: str = "#F2F4F7"
    surface: str = "#FFFFFF"
    surface_alt: str = "#F8F9FB"
    border: str = "#C9CED6"
    border_strong: str = "#667085"
    text: str = "#101828"
    text_muted: str = "#475467"
    # The one action colour.
    accent: str = "#1849A9"
    accent_hover: str = "#123A88"
    accent_pressed: str = "#0E2E6B"
    accent_soft: str = "#E7EEFB"
    on_accent: str = "#FFFFFF"
    # Keyboard focus ring (amber-700, >= 3:1 against white and bg).
    focus: str = "#B54708"
    # Status - pass / fail / warning / info (soft background + strong foreground + solid).
    pass_bg: str = "#E3F4E9"
    pass_fg: str = "#0A4D2B"
    pass_solid: str = "#0B5D35"
    fail_bg: str = "#FDE9E7"
    fail_fg: str = "#86170F"
    fail_solid: str = "#9C1A10"
    warn_bg: str = "#FFF1DB"
    warn_fg: str = "#6B3A00"
    info_bg: str = "#E7EEFB"
    info_fg: str = "#123A88"
    on_status_solid: str = "#FFFFFF"
    disabled_bg: str = "#E4E7EC"
    disabled_fg: str = "#475467"


@dataclass(frozen=True, slots=True)
class Sizes:
    font_base: int = 18
    font_small: int = 15
    font_h2: int = 22
    font_h1: int = 28
    font_value: int = 32
    font_value_large: int = 40
    font_takeover: int = 56
    font_box_letter: int = 160
    button_height: int = 56
    check_row_height: int = 68
    radius: int = 10
    space_xs: int = 4
    space_s: int = 8
    space_m: int = 16
    space_l: int = 24
    space_xl: int = 32
    focus_width: int = 3
    min_window_width: int = 1366
    min_window_height: int = 768


COLORS = Colors()
SIZES = Sizes()


def relative_luminance(hex_color: str) -> float:
    """WCAG 2.x relative luminance of ``#RRGGBB``."""
    value = hex_color.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two ``#RRGGBB`` colours (1..21)."""
    a = relative_luminance(foreground)
    b = relative_luminance(background)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)
