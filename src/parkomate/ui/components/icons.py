"""Simple line icons drawn with QPainter (no icon fonts, no emoji - identical on every PC)."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from parkomate.ui.theme.tokens import COLORS

ICON_NAMES = (
    "check",
    "cross",
    "warn",
    "info",
    "clock",
    "pcb",
    "screw",
    "sticker",
    "qr",
    "sensor",
    "indicator",
    "connector",
    "box",
    "plug",
    "chip",
    "cloud",
    "thermo",
    "bolt",
    "camera",
    "user",
    "list",
    "lock",
)


def paint_icon(painter: QPainter, name: str, rect: QRectF, color: QColor) -> None:
    """Draw icon ``name`` inside ``rect`` with stroke ``color``."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = min(rect.width(), rect.height())
    x0 = rect.x() + (rect.width() - s) / 2
    y0 = rect.y() + (rect.height() - s) / 2
    pen = QPen(
        color,
        max(2.0, s / 11),
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    def p(x: float, y: float) -> QPointF:
        return QPointF(x0 + x * s, y0 + y * s)

    def r(x: float, y: float, w: float, h: float) -> QRectF:
        return QRectF(x0 + x * s, y0 + y * s, w * s, h * s)

    if name == "check":
        path = QPainterPath(p(0.18, 0.52))
        path.lineTo(p(0.42, 0.76))
        path.lineTo(p(0.84, 0.26))
        painter.drawPath(path)
    elif name == "cross":
        painter.drawLine(p(0.22, 0.22), p(0.78, 0.78))
        painter.drawLine(p(0.78, 0.22), p(0.22, 0.78))
    elif name == "warn":
        path = QPainterPath(p(0.5, 0.1))
        path.lineTo(p(0.92, 0.86))
        path.lineTo(p(0.08, 0.86))
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(p(0.5, 0.36), p(0.5, 0.6))
        painter.drawPoint(p(0.5, 0.74))
    elif name == "info":
        painter.drawEllipse(r(0.1, 0.1, 0.8, 0.8))
        painter.drawLine(p(0.5, 0.45), p(0.5, 0.72))
        painter.drawPoint(p(0.5, 0.3))
    elif name == "clock":
        painter.drawEllipse(r(0.1, 0.1, 0.8, 0.8))
        painter.drawLine(p(0.5, 0.5), p(0.5, 0.26))
        painter.drawLine(p(0.5, 0.5), p(0.68, 0.6))
    elif name == "pcb":
        painter.drawRoundedRect(r(0.1, 0.2, 0.8, 0.6), s * 0.06, s * 0.06)
        painter.drawRect(r(0.38, 0.38, 0.24, 0.24))
        for x in (0.2, 0.8):
            painter.drawPoint(p(x, 0.3))
            painter.drawPoint(p(x, 0.7))
    elif name == "screw":
        painter.drawEllipse(r(0.25, 0.08, 0.5, 0.3))
        painter.drawLine(p(0.38, 0.23), p(0.62, 0.23))
        painter.drawLine(p(0.5, 0.38), p(0.5, 0.92))
        for y in (0.5, 0.64, 0.78):
            painter.drawLine(p(0.4, y), p(0.6, y + 0.06))
    elif name == "sticker":
        path = QPainterPath(p(0.15, 0.15))
        path.lineTo(p(0.85, 0.15))
        path.lineTo(p(0.85, 0.62))
        path.lineTo(p(0.62, 0.85))
        path.lineTo(p(0.15, 0.85))
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(p(0.62, 0.85), p(0.62, 0.62))
        painter.drawLine(p(0.62, 0.62), p(0.85, 0.62))
    elif name == "qr":
        for x, y in ((0.12, 0.12), (0.58, 0.12), (0.12, 0.58)):
            painter.drawRect(r(x, y, 0.3, 0.3))
        painter.drawPoint(p(0.65, 0.65))
        painter.drawPoint(p(0.82, 0.82))
        painter.drawPoint(p(0.65, 0.84))
        painter.drawPoint(p(0.84, 0.64))
    elif name == "sensor":
        painter.drawRoundedRect(r(0.3, 0.45, 0.4, 0.4), s * 0.05, s * 0.05)
        for k in (0.18, 0.3):
            painter.drawArc(
                r(0.5 - k - 0.1, 0.42 - k - 0.1, 2 * (k + 0.1), 2 * (k + 0.1)), 40 * 16, 100 * 16
            )
    elif name == "indicator":
        painter.drawEllipse(r(0.28, 0.12, 0.44, 0.44))
        painter.drawLine(p(0.4, 0.62), p(0.6, 0.62))
        painter.drawLine(p(0.42, 0.74), p(0.58, 0.74))
        painter.drawLine(p(0.45, 0.86), p(0.55, 0.86))
    elif name == "connector":
        painter.drawRect(r(0.18, 0.3, 0.64, 0.4))
        for x in (0.32, 0.5, 0.68):
            painter.drawLine(p(x, 0.12), p(x, 0.3))
        painter.drawLine(p(0.5, 0.7), p(0.5, 0.9))
    elif name == "box":
        path = QPainterPath(p(0.5, 0.1))
        path.lineTo(p(0.9, 0.3))
        path.lineTo(p(0.9, 0.72))
        path.lineTo(p(0.5, 0.92))
        path.lineTo(p(0.1, 0.72))
        path.lineTo(p(0.1, 0.3))
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(p(0.1, 0.3), p(0.5, 0.5))
        painter.drawLine(p(0.9, 0.3), p(0.5, 0.5))
        painter.drawLine(p(0.5, 0.5), p(0.5, 0.92))
    elif name == "plug":
        painter.drawRoundedRect(r(0.25, 0.32, 0.5, 0.36), s * 0.06, s * 0.06)
        painter.drawLine(p(0.38, 0.12), p(0.38, 0.32))
        painter.drawLine(p(0.62, 0.12), p(0.62, 0.32))
        painter.drawLine(p(0.5, 0.68), p(0.5, 0.92))
    elif name == "chip":
        painter.drawRect(r(0.25, 0.25, 0.5, 0.5))
        for k in (0.36, 0.5, 0.64):
            painter.drawLine(p(k, 0.1), p(k, 0.25))
            painter.drawLine(p(k, 0.75), p(k, 0.9))
            painter.drawLine(p(0.1, k), p(0.25, k))
            painter.drawLine(p(0.75, k), p(0.9, k))
    elif name == "cloud":
        path = QPainterPath(p(0.24, 0.74))
        path.arcTo(r(0.06, 0.4, 0.34, 0.34), 270, -180)
        path.arcTo(r(0.24, 0.2, 0.42, 0.42), 180, -150)
        path.arcTo(r(0.58, 0.4, 0.34, 0.34), 90, -180)
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "thermo":
        painter.drawLine(p(0.44, 0.15), p(0.44, 0.62))
        painter.drawLine(p(0.56, 0.15), p(0.56, 0.62))
        painter.drawArc(r(0.44, 0.08, 0.12, 0.14), 0, 180 * 16)
        painter.drawEllipse(r(0.34, 0.6, 0.32, 0.32))
    elif name == "bolt":
        path = QPainterPath(p(0.58, 0.08))
        path.lineTo(p(0.26, 0.54))
        path.lineTo(p(0.48, 0.54))
        path.lineTo(p(0.4, 0.92))
        path.lineTo(p(0.74, 0.44))
        path.lineTo(p(0.52, 0.44))
        path.closeSubpath()
        painter.drawPath(path)
    elif name == "camera":
        painter.drawRoundedRect(r(0.1, 0.3, 0.8, 0.52), s * 0.06, s * 0.06)
        painter.drawEllipse(r(0.36, 0.4, 0.28, 0.28))
        painter.drawLine(p(0.32, 0.3), p(0.38, 0.18))
        painter.drawLine(p(0.38, 0.18), p(0.62, 0.18))
        painter.drawLine(p(0.62, 0.18), p(0.68, 0.3))
    elif name == "user":
        painter.drawEllipse(r(0.34, 0.12, 0.32, 0.32))
        painter.drawArc(r(0.16, 0.52, 0.68, 0.7), 0, 180 * 16)
    elif name == "list":
        for y in (0.25, 0.5, 0.75):
            painter.drawPoint(p(0.18, y))
            painter.drawLine(p(0.32, y), p(0.84, y))
    elif name == "lock":
        painter.drawRoundedRect(r(0.2, 0.44, 0.6, 0.44), s * 0.05, s * 0.05)
        painter.drawArc(r(0.32, 0.14, 0.36, 0.5), 0, 180 * 16)
    else:  # unknown name: a neutral dot rather than nothing
        painter.drawEllipse(r(0.4, 0.4, 0.2, 0.2))
    painter.restore()


class Icon(QWidget):
    """A fixed-size icon. Decorative: excluded from the accessibility tree by default."""

    def __init__(
        self, name: str, size: int = 32, color: str | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._name = name
        self._color = QColor(color or COLORS.text)
        self.setFixedSize(QSize(size, size))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_icon(self, name: str, color: str | None = None) -> None:
        self._name = name
        if color is not None:
            self._color = QColor(color)
        self.update()

    def name(self) -> str:
        return self._name

    def paintEvent(self, _event: object) -> None:
        painter = QPainter(self)
        paint_icon(painter, self._name, QRectF(self.rect()).adjusted(2, 2, -2, -2), self._color)
        painter.end()
