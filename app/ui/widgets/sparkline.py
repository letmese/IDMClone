"""Real-time throughput vector sparkline widget."""
from __future__ import annotations

from collections import deque
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ..theme import ThemeColors, get_theme


class ThroughputSparkline(QWidget):
    """Draws a real-time anti-aliased network speed sparkline with vertical gradient fade."""

    def __init__(self, parent=None, max_points: int = 36, theme: ThemeColors = None):
        super().__init__(parent)
        self.max_points = max_points
        self.history = deque([0.0] * max_points, maxlen=max_points)
        self.theme = theme or get_theme("Obsidian Cyber Mica")
        self.setMinimumSize(90, 26)
        self.setMaximumHeight(32)

    def set_theme(self, theme: ThemeColors):
        self.theme = theme
        self.update()

    def add_sample(self, speed_bytes_per_sec: float):
        mbps = speed_bytes_per_sec / (1024 * 1024)
        self.history.append(mbps)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        if w < 10 or h < 8:
            painter.end()
            return

        t = self.theme
        max_val = max(max(self.history), 1.0)
        n = len(self.history)
        step = w / max(1, n - 1)

        points = []
        for i, val in enumerate(self.history):
            # inverted Y: 0 speed is at bottom (h - 2), max_val is at top (2)
            normalized = min(1.0, val / max_val)
            py = (h - 4.0) * (1.0 - normalized) + 2.0
            px = i * step
            points.append(QPointF(px, py))

        # Area gradient path
        area_path = QPainterPath()
        area_path.moveTo(0, h)
        for pt in points:
            area_path.lineTo(pt)
        area_path.lineTo(w, h)
        area_path.closeSubpath()

        grad = QLinearGradient(0, 0, 0, h)
        col = QColor(t.primary)
        col_fade = QColor(col)
        col_fade.setAlpha(80)
        col_zero = QColor(col)
        col_zero.setAlpha(0)
        grad.setColorAt(0.0, col_fade)
        grad.setColorAt(1.0, col_zero)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawPath(area_path)

        # Line path
        line_path = QPainterPath()
        line_path.moveTo(points[0])
        for pt in points[1:]:
            line_path.lineTo(pt)

        pen = QPen(col, 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(line_path)

        painter.end()
