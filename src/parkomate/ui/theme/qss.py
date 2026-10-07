"""The application stylesheet, generated from the design tokens.

Widgets opt into styles with dynamic properties, e.g. ``variant="primary"`` on a button or
``role="h1"`` on a label, so no colour is hard-coded in a view.
"""

from __future__ import annotations

from parkomate.ui.theme.tokens import COLORS, SIZES, Colors, Sizes


def build_stylesheet(c: Colors = COLORS, s: Sizes = SIZES) -> str:
    return f"""
/* Font family and the 18 px base size come from QApplication.setFont(); setting a font-size
   here would override every widget's setFont(). */
* {{
    color: {c.text};
}}
QMainWindow, QWidget#Root, QWidget#Page {{
    background: {c.bg};
}}
QToolTip {{
    background: {c.text};
    color: {c.surface};
    border: none;
    padding: 6px 8px;
    font-size: {s.font_small}px;
}}

/* ---------- cards & text roles ---------- */
QFrame[card="true"] {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: {s.radius}px;
}}
QLabel[role="h1"] {{ font-size: {s.font_h1}px; font-weight: 700; }}
QLabel[role="h2"] {{ font-size: {s.font_h2}px; font-weight: 700; }}
QLabel[role="muted"] {{ color: {c.text_muted}; }}
QLabel[role="small"] {{ font-size: {s.font_small}px; color: {c.text_muted}; }}
QLabel[role="value"] {{ font-size: {s.font_value}px; font-weight: 700; }}
QLabel[role="value_large"] {{ font-size: {s.font_value_large}px; font-weight: 700; }}
QLabel[role="hint"] {{
    font-size: {s.font_small}px;
    color: {c.text_muted};
}}

/* ---------- buttons ---------- */
QPushButton {{
    min-height: {s.button_height}px;
    padding: 0 {s.space_l}px;
    border-radius: {s.radius}px;
    font-weight: 600;
    background: {c.surface};
    border: 2px solid {c.border_strong};
    color: {c.text};
}}
QPushButton:hover {{ background: {c.surface_alt}; }}
QPushButton:pressed {{ background: {c.accent_soft}; }}
QPushButton:focus {{ border: {s.focus_width}px solid {c.focus}; }}
QPushButton:disabled {{
    background: {c.disabled_bg};
    color: {c.disabled_fg};
    border: 2px solid {c.disabled_bg};
}}
QPushButton[variant="primary"] {{
    background: {c.accent};
    color: {c.on_accent};
    border: 2px solid {c.accent};
    font-size: {s.font_h2}px;
}}
QPushButton[variant="primary"]:hover {{ background: {c.accent_hover}; }}
QPushButton[variant="primary"]:pressed {{ background: {c.accent_pressed}; }}
QPushButton[variant="primary"]:focus {{ border: {s.focus_width}px solid {c.focus}; }}
QPushButton[variant="primary"]:disabled {{
    background: {c.disabled_bg};
    color: {c.disabled_fg};
    border: 2px solid {c.disabled_bg};
}}
QPushButton[variant="danger"] {{
    color: {c.fail_fg};
    border: 2px solid {c.fail_fg};
}}
QPushButton[variant="pass"] {{
    color: {c.pass_fg};
    border: 2px solid {c.pass_fg};
}}
QPushButton[variant="pass"]:checked {{
    background: {c.pass_solid};
    color: {c.on_status_solid};
    border: 2px solid {c.pass_solid};
}}
QPushButton[variant="danger"]:checked {{
    background: {c.fail_solid};
    color: {c.on_status_solid};
    border: 2px solid {c.fail_solid};
}}
QPushButton[variant="pass"]:disabled, QPushButton[variant="danger"]:disabled {{
    background: {c.disabled_bg};
    color: {c.disabled_fg};
    border: 2px solid {c.disabled_bg};
}}
QPushButton[variant="pass"]:checked:disabled {{
    background: {c.pass_solid};
    color: {c.on_status_solid};
    border: 2px solid {c.pass_solid};
}}
QPushButton[variant="danger"]:checked:disabled {{
    background: {c.fail_solid};
    color: {c.on_status_solid};
    border: 2px solid {c.fail_solid};
}}
QPushButton#TopButton {{ padding: 0 14px; }}
QPushButton[variant="link"] {{
    min-height: 32px;
    border: none;
    background: transparent;
    color: {c.accent};
    text-decoration: underline;
    font-weight: 400;
    font-size: {s.font_small}px;
    padding: 0 4px;
}}
QPushButton[variant="link"]:focus {{ border: 2px solid {c.focus}; }}
QPushButton[variant="toggle"] {{
    min-height: 44px;
    padding: 0 {s.space_m}px;
    font-weight: 600;
}}
QPushButton[variant="toggle"]:checked {{
    background: {c.accent};
    color: {c.on_accent};
    border: 2px solid {c.accent};
}}
QPushButton[variant="takeover"] {{
    background: {c.surface};
    color: {c.fail_fg};
    border: 3px solid {c.surface};
    font-size: {s.font_h1}px;
    min-height: 72px;
    padding: 0 48px;
}}
QPushButton[variant="takeover"]:focus {{ border: 4px solid {c.text}; }}

/* ---------- inputs ---------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
    min-height: 44px;
    padding: 0 {s.space_s}px;
    border: 2px solid {c.border_strong};
    border-radius: 8px;
    background: {c.surface};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
    border: {s.focus_width}px solid {c.focus};
}}
QLineEdit[invalid="true"], QComboBox[invalid="true"], QSpinBox[invalid="true"],
QDoubleSpinBox[invalid="true"] {{
    border: {s.focus_width}px solid {c.fail_fg};
}}
QComboBox QAbstractItemView {{
    background: {c.surface};
    selection-background-color: {c.accent_soft};
    selection-color: {c.text};
}}
QCheckBox {{ spacing: 12px; min-height: 40px; }}
QCheckBox::indicator {{ width: 28px; height: 28px; }}
QCheckBox:focus {{ color: {c.focus}; }}
QProgressBar {{
    min-height: 30px;
    border: 2px solid {c.border_strong};
    border-radius: 8px;
    background: {c.surface_alt};
    text-align: center;
    font-weight: 700;
}}
QProgressBar::chunk {{ background: {c.accent}; border-radius: 6px; }}

/* ---------- tables & lists ---------- */
QTableWidget, QListWidget, QPlainTextEdit {{
    background: {c.surface};
    border: 1px solid {c.border};
    border-radius: 8px;
    gridline-color: {c.border};
    selection-background-color: {c.accent_soft};
    selection-color: {c.text};
}}
QTableWidget:focus, QListWidget:focus, QPlainTextEdit:focus {{
    border: {s.focus_width}px solid {c.focus};
}}
QHeaderView::section {{
    background: {c.surface_alt};
    border: none;
    border-bottom: 1px solid {c.border};
    padding: 8px;
    font-weight: 700;
    font-size: {s.font_small}px;
}}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    min-height: 48px;
    padding: 0 {s.space_l}px;
    background: transparent;
    border-bottom: 3px solid transparent;
    font-weight: 600;
    color: {c.text_muted};
}}
QTabBar::tab:selected {{ color: {c.accent}; border-bottom: 3px solid {c.accent}; }}
QTabBar::tab:focus {{ color: {c.focus}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea#CardScroll, QScrollArea#CardScroll > QWidget, QWidget#CardInner {{
    background: transparent;
}}

/* ---------- stage stepper ---------- */
QLabel[step="current"] {{
    background: {c.accent};
    color: {c.on_accent};
    border-radius: 8px;
}}
QLabel[step="done"] {{ color: {c.pass_fg}; }}
QLabel[step="todo"] {{ color: {c.text_muted}; }}
QLabel[step="rejected"] {{
    background: {c.fail_solid};
    color: {c.on_status_solid};
    border-radius: 8px;
}}

/* ---------- top bar ---------- */
QFrame#TopBar {{ background: {c.surface}; border-bottom: 1px solid {c.border}; }}
QFrame#InfoStrip {{ background: {c.surface_alt}; border-bottom: 1px solid {c.border}; }}
QFrame#BottomBar {{ background: {c.surface}; border-top: 1px solid {c.border}; }}
QFrame#Drawer {{ background: {c.surface}; border-left: 2px solid {c.border_strong}; }}

/* ---------- status surfaces ---------- */
QFrame[tone="pass"] {{ background: {c.pass_bg}; border: 2px solid {c.pass_fg}; border-radius: {s.radius}px; }}
QFrame[tone="fail"] {{ background: {c.fail_bg}; border: 2px solid {c.fail_fg}; border-radius: {s.radius}px; }}
QFrame[tone="warn"] {{ background: {c.warn_bg}; border: 2px solid {c.warn_fg}; border-radius: {s.radius}px; }}
QFrame[tone="info"] {{ background: {c.info_bg}; border: 2px solid {c.info_fg}; border-radius: {s.radius}px; }}
QFrame[tone="pending"] {{ background: {c.surface_alt}; border: 2px solid {c.border}; border-radius: {s.radius}px; }}
QLabel[status="pass"] {{ color: {c.pass_fg}; font-weight: 700; }}
QLabel[status="fail"] {{ color: {c.fail_fg}; font-weight: 700; }}
QLabel[status="warn"] {{ color: {c.warn_fg}; font-weight: 700; }}
QLabel[status="info"] {{ color: {c.info_fg}; font-weight: 700; }}
QLabel[status="pending"] {{ color: {c.text_muted}; font-weight: 700; }}
QFrame#RejectTakeover {{ background: {c.fail_solid}; }}
QFrame#RejectTakeover QLabel {{ color: {c.on_status_solid}; }}
QFrame#SuccessToast {{ background: {c.pass_solid}; border-radius: {s.radius}px; }}
QFrame#SuccessToast QLabel {{ color: {c.on_status_solid}; font-size: {s.font_h1}px; font-weight: 700; }}
"""
