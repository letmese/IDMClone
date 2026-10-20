"""Segmented range buffer progress widget (IDM Pro physical slices)."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from ..theme import ThemeColors, get_theme


class ModernSegmentedProgressBar(QWidget):
    """Renders 8 to 32 discrete physical socket range slots with live buffer state."""

    def __init__(self, parent=None, theme: ThemeColors = None):
        super().__init__(parent)
        self._task = None
        self.theme = theme or get_theme("Obsidian Cyber Mica")
        self.setMinimumHeight(18)
        self.setMaximumHeight(22)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_theme(self, theme: ThemeColors):
        self.theme = theme
        self.update()

    def set_task(self, task):
        self._task = task
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        if w <= 4 or h <= 4:
            painter.end()
            return

        task = self._task
        t = self.theme

        # Background track
        bg_track = QColor(t.bg_surface_sunken)
        border_col = QColor(t.border)
        painter.setPen(border_col)
        painter.setBrush(bg_track)
        painter.drawRoundedRect(QRectF(1, 2, w - 2, h - 4), 4, 4)

        if not task:
            painter.end()
            return

        parts = getattr(task, "parts", None) or []
        state = getattr(task, "state", "queued")
        progress = max(0.0, min(100.0, getattr(task, "progress", 0.0)))

        # Colors based on state
        if state == "completed":
            fill_color = QColor(t.accent_green)
            stream_color = fill_color
        elif state == "merging":
            fill_color = QColor(t.accent_amber)
            stream_color = fill_color
        elif state == "paused":
            fill_color = QColor(t.text_muted)
            stream_color = fill_color
        elif state == "error":
            fill_color = QColor(t.accent_red)
            stream_color = fill_color
        else:
            fill_color = QColor(t.accent_green)
            stream_color = QColor(t.accent_cyan)

        usable_w = w - 4
        x_start = 2.0
        y_pos = 3.0
        bar_h = h - 6.0

        if parts and len(parts) > 1:
            n = len(parts)
            gap = 2.0
            seg_w = max(2.0, (usable_w - gap * (n - 1)) / n)

            for i, p in enumerate(parts):
                sx = x_start + i * (seg_w + gap)
                size = (p.end - p.start + 1) if p.end >= 0 else 1
                frac = max(0.0, min(1.0, p.downloaded / size if size > 0 else 0.0))

                # Slot background
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(t.bg_surface_elevated))
                painter.drawRoundedRect(QRectF(sx, y_pos, seg_w, bar_h), 2, 2)

                # Filled progress inside this slot
                if frac > 0.001:
                    fill_w = seg_w * frac
                    color = fill_color if p.done else stream_color
                    painter.setBrush(color)
                    painter.drawRoundedRect(QRectF(sx, y_pos, fill_w, bar_h), 2, 2)
        else:
            # Single stream
            frac = progress / 100.0
            if frac > 0:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(fill_color)
                painter.drawRoundedRect(QRectF(x_start, y_pos, usable_w * frac, bar_h), 3, 3)

        # Overlay percentage text with shadow for maximum readability
        pct_text = f"{progress:.1f}%"
        if state == "merging":
            pct_text = f"Merging ({progress:.0f}%)"
        elif state == "paused":
            pct_text = f"Paused ({progress:.0f}%)"
        elif state == "completed":
            pct_text = "100% Done"

        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(font)

        # Subtle text outline / shadow
        painter.setPen(QColor("#000000"))
        painter.drawText(QRectF(self.rect()).adjusted(1, 1, 1, 1), Qt.AlignmentFlag.AlignCenter, pct_text)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, pct_text)
        painter.end()
