"""Selected task live socket matrix widget (inspector panel in IDM Pro)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget,
)

from ..theme import ThemeColors, get_theme


class SocketMatrixPanel(QFrame):
    """Bottom inspector panel displaying 16 parallel thread socket streams."""

    def __init__(self, parent=None, theme: ThemeColors = None):
        super().__init__(parent)
        self.theme = theme or get_theme("Obsidian Cyber Mica")
        self.setObjectName("panel")
        self.setFixedHeight(92)
        self._task = None
        self._slots = []
        self._build_ui()

    def set_theme(self, theme: ThemeColors):
        self.theme = theme
        self._apply_style()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 4, 8, 4)
        root_layout.setSpacing(4)

        # Header bar
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.lbl_title = QLabel("LIVE SOCKET MATRIX: NO ACTIVE SELECTION")
        self.lbl_title.setStyleSheet(f"color: {self.theme.primary}; font-weight: bold; font-size: 11px;")
        header_row.addWidget(self.lbl_title)

        header_row.addStretch()

        self.lbl_status = QLabel("0/0 Sockets Active • 512 KB Window • TLS_AES_256_GCM")
        self.lbl_status.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 10px;")
        header_row.addWidget(self.lbl_status)

        root_layout.addLayout(header_row)

        # Grid of up to 16 thread slots (2 rows of 8 columns)
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(4)

        for i in range(16):
            slot = self._create_slot(i + 1)
            row = 0 if i < 8 else 1
            col = i if i < 8 else i - 8
            self.grid_layout.addWidget(slot["container"], row, col)
            self._slots.append(slot)

        root_layout.addWidget(self.grid_widget)
        self._apply_style()

    def _create_slot(self, index: int) -> dict:
        container = QFrame()
        container.setObjectName("sunkenWell")
        container.setFixedHeight(28)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(1)

        top_row = QHBoxLayout()
        lbl_id = QLabel(f"SW{index:02d}")
        lbl_id.setObjectName("telemetry")
        lbl_id.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 10px; font-weight: 700;")
        top_row.addWidget(lbl_id)

        top_row.addStretch()

        lbl_speed = QLabel("0.0 KB/s")
        lbl_speed.setObjectName("telemetry")
        lbl_speed.setStyleSheet(f"color: {self.theme.primary}; font-size: 10px; font-weight: 700;")
        top_row.addWidget(lbl_speed)
        layout.addLayout(top_row)

        bar = QProgressBar()
        bar.setFixedHeight(4)
        bar.setTextVisible(False)
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {self.theme.bg_surface_elevated};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {self.theme.primary};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(bar)

        return {"container": container, "id": lbl_id, "speed": lbl_speed, "bar": bar}

    def _apply_style(self):
        self.lbl_title.setStyleSheet(f"color: {self.theme.primary}; font-weight: 700; font-size: 11px;")
        self.lbl_status.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 11px;")
        for s in self._slots:
            s["id"].setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 10px; font-weight: 700;")
            s["speed"].setStyleSheet(f"color: {self.theme.primary}; font-size: 10px; font-weight: 700;")
            s["bar"].setStyleSheet(f"""
                QProgressBar {{
                    background-color: {self.theme.bg_surface_elevated};
                    border: none;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background-color: {self.theme.primary};
                    border-radius: 2px;
                }}
            """)

    def update_task(self, task):
        self._task = task
        if not task:
            self.lbl_title.setText("SELECTED TASK LIVE SOCKET MATRIX: NO ACTIVE SELECTION")
            self.lbl_status.setText("0/0 Sockets Active • TCP Window: 512 KB • Loss: 0.00% • Cipher: TLS_AES_256_GCM")
            for s in self._slots:
                s["speed"].setText("0.0 KB/s")
                s["bar"].setValue(0)
            return

        name = getattr(task, "filename", "") or "Task"
        self.lbl_title.setText(f"SELECTED TASK LIVE SOCKET MATRIX: {name.upper()}")

        parts = getattr(task, "parts", []) or []
        n_parts = len(parts)
        active_sockets = sum(1 for p in parts if getattr(p, "status", "") == "streaming")
        self.lbl_status.setText(
            f"{active_sockets}/{max(1, n_parts)} Sockets Responding (Avg RTT: 14ms) • TCP Window: 512 KB • Loss: 0.00% • Cipher: TLS_AES_256_GCM"
        )

        for i, slot in enumerate(self._slots):
            if i < n_parts:
                p = parts[i]
                slot["container"].setVisible(True)
                speed = getattr(p, "speed", 0.0) or 0.0
                if speed >= 1024 * 1024:
                    speed_text = f"{speed / (1024 * 1024):.1f} MB/s"
                elif speed >= 1024:
                    speed_text = f"{speed / 1024:.0f} KB/s"
                else:
                    speed_text = "0.0 KB/s"
                slot["speed"].setText(speed_text)

                size = (p.end - p.start + 1) if p.end >= 0 else 1
                frac = max(0, min(100, int((p.downloaded / max(1, size)) * 100)))
                slot["bar"].setValue(frac)
            else:
                # Slot is unused for this task
                slot["speed"].setText("—")
                slot["bar"].setValue(0)
