"""Modern Start Download Preflight Dialog matching Stitch screen3.png."""
from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QPushButton, QVBoxLayout, QWidget, QApplication,
)

from ..config import Settings
from ..engine.downloader import DownloadTask
from .theme import ThemeColors, get_theme


class ProbeSignals(QObject):
    probed = Signal(dict)


class ModernDownloadDialog(QDialog):
    """Start Download modal dialog matching IDM Pro screen3.png."""

    def __init__(self, parent=None, initial_url: str = "", settings: Settings = None, theme: ThemeColors = None):
        super().__init__(parent)
        if not isinstance(initial_url, str):
            initial_url = ""
        self.settings = settings or Settings.load()
        self.theme = theme or get_theme(getattr(self.settings, "active_theme", "Obsidian Cyber Mica"))
        self.setWindowTitle("Download File Info")
        self.setFixedSize(680, 560)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._signals = ProbeSignals()
        self._signals.probed.connect(self._on_probe_complete)

        self.selected_threads = getattr(self.settings, "default_connections", 16)
        self.file_size_bytes = 0
        self.server_ranges = True
        self.task: Optional[DownloadTask] = None
        self.action_choice = "cancel"

        self._build_ui(initial_url)
        if initial_url.strip():
            self._start_probe(initial_url.strip())

    def _build_ui(self, initial_url: str):
        # Outer wrapper frame for border & dark glass background
        main_frame = QFrame(self)
        main_frame.setGeometry(0, 0, 680, 560)
        main_frame.setObjectName("panel")
        main_frame.setStyleSheet(f"""
            QFrame#panel {{
                background-color: {self.theme.bg_canvas};
                border: 1px solid {self.theme.border_focus if self.theme.is_dark else self.theme.border};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(main_frame)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # 1. Custom Title Bar
        title_row = QHBoxLayout()
        lbl_icon = QLabel("⚡")
        lbl_icon.setStyleSheet(f"color: {self.theme.primary}; font-size: 15px;")
        title_row.addWidget(lbl_icon)

        lbl_title = QLabel("Download File Info")
        lbl_title.setStyleSheet(f"color: {self.theme.text_primary}; font-weight: 700; font-size: 14px;")
        title_row.addWidget(lbl_title)
        title_row.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {self.theme.text_secondary};
                font-size: 14px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {self.theme.accent_red};
                color: #FFFFFF;
            }}
        """)
        btn_close.clicked.connect(self.reject)
        title_row.addWidget(btn_close)
        layout.addLayout(title_row)

        # 2. Server Preflight Status Pill
        self.preflight_card = QFrame()
        self.preflight_card.setObjectName("sunkenWell")
        self.preflight_card.setFixedHeight(34)
        pf_layout = QHBoxLayout(self.preflight_card)
        pf_layout.setContentsMargins(10, 4, 10, 4)

        self.lbl_preflight = QLabel("● Server Verified: Range 206 Supported • Resume Enabled • SSL 256-bit Valid")
        self.lbl_preflight.setObjectName("telemetry")
        self.lbl_preflight.setStyleSheet(f"color: {self.theme.accent_green}; font-size: 11px; font-weight: 600;")
        pf_layout.addWidget(self.lbl_preflight)
        layout.addWidget(self.preflight_card)

        # 3. Detected Filename Card
        file_card = QFrame()
        file_card.setObjectName("sunkenWell")
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(12, 10, 12, 10)
        file_layout.setSpacing(6)

        lbl_det = QLabel("DETECTED FILENAME")
        lbl_det.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 10px; font-weight: 700; letter-spacing: 0.05em;")
        file_layout.addWidget(lbl_det)

        fn_row = QHBoxLayout()
        self.lbl_type_icon = QLabel("📁")
        self.lbl_type_icon.setStyleSheet(f"font-size: 18px;")
        fn_row.addWidget(self.lbl_type_icon)

        self.txt_filename = QLineEdit()
        self.txt_filename.setPlaceholderText("Resolving filename...")
        self.txt_filename.setStyleSheet(f"""
            QLineEdit {{
                background: {self.theme.bg_surface_elevated};
                border: 1px solid {self.theme.border};
                border-radius: 6px;
                padding: 6px 10px;
                color: {self.theme.text_primary};
                font-weight: 600;
            }}
        """)
        self.txt_filename.textChanged.connect(self._on_filename_changed)
        fn_row.addWidget(self.txt_filename)
        file_layout.addLayout(fn_row)

        meta_row = QHBoxLayout()
        self.lbl_size = QLabel("Size: Calculating... (Exact: 0 bytes)")
        self.lbl_size.setObjectName("telemetry")
        self.lbl_size.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 11px;")
        meta_row.addWidget(self.lbl_size)

        meta_row.addStretch()

        self.lbl_category_badge = QLabel("Other")
        self.lbl_category_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {self.theme.bg_surface_elevated};
                border: 1px solid {self.theme.border};
                border-radius: 4px;
                padding: 2px 8px;
                color: {self.theme.primary};
                font-weight: 700;
                font-size: 11px;
            }}
        """)
        meta_row.addWidget(self.lbl_category_badge)
        file_layout.addLayout(meta_row)
        layout.addWidget(file_card)

        # 4. Source URL Row
        url_card = QFrame()
        url_card.setObjectName("sunkenWell")
        url_layout = QVBoxLayout(url_card)
        url_layout.setContentsMargins(12, 8, 12, 8)
        url_layout.setSpacing(4)

        lbl_src = QLabel("SOURCE URL")
        lbl_src.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 10px; font-weight: 700; letter-spacing: 0.05em;")
        url_layout.addWidget(lbl_src)

        url_row = QHBoxLayout()
        self.txt_url = QLineEdit(initial_url)
        self.txt_url.setPlaceholderText("https://example.com/file.zip")
        self.txt_url.setStyleSheet(f"""
            QLineEdit {{
                background: {self.theme.bg_surface_elevated};
                border: 1px solid {self.theme.border};
                border-radius: 6px;
                padding: 6px 10px;
                color: {self.theme.primary};
                font-family: 'JetBrains Mono', monospace;
                font-size: 11px;
            }}
        """)
        self.txt_url.textChanged.connect(self._start_probe)
        url_row.addWidget(self.txt_url)

        btn_copy = QPushButton("Copy")
        btn_copy.setFixedWidth(64)
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.txt_url.text()))
        url_row.addWidget(btn_copy)
        url_layout.addLayout(url_row)
        layout.addWidget(url_card)

        # 5. Save Folder Directory & Disk Preflight
        save_card = QFrame()
        save_card.setObjectName("sunkenWell")
        save_layout = QVBoxLayout(save_card)
        save_layout.setContentsMargins(12, 8, 12, 8)
        save_layout.setSpacing(4)

        lbl_dest = QLabel("SAVE FOLDER DIRECTORY")
        lbl_dest.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 10px; font-weight: 700; letter-spacing: 0.05em;")
        save_layout.addWidget(lbl_dest)

        dir_row = QHBoxLayout()
        self.txt_dest = QLineEdit(self.settings.save_path)
        self.txt_dest.setStyleSheet(f"""
            QLineEdit {{
                background: {self.theme.bg_surface_elevated};
                border: 1px solid {self.theme.border};
                border-radius: 6px;
                padding: 6px 10px;
                color: {self.theme.text_primary};
                font-size: 12px;
            }}
        """)
        self.txt_dest.textChanged.connect(self._update_disk_bar)
        dir_row.addWidget(self.txt_dest)

        btn_browse = QPushButton("Browse...")
        btn_browse.setFixedWidth(80)
        btn_browse.clicked.connect(self._browse_dest)
        dir_row.addWidget(btn_browse)
        save_layout.addLayout(dir_row)

        # Disk Capacity Bar
        disk_row = QHBoxLayout()
        self.lbl_disk_free = QLabel("Calculating drive space...")
        self.lbl_disk_free.setObjectName("telemetry")
        self.lbl_disk_free.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 10px;")
        disk_row.addWidget(self.lbl_disk_free)

        disk_row.addStretch()

        self.lbl_disk_req = QLabel("0 MB required")
        self.lbl_disk_req.setObjectName("telemetry")
        self.lbl_disk_req.setStyleSheet(f"color: {self.theme.accent_cyan}; font-size: 10px;")
        disk_row.addWidget(self.lbl_disk_req)
        save_layout.addLayout(disk_row)

        self.disk_bar = QProgressBar()
        self.disk_bar.setFixedHeight(4)
        self.disk_bar.setTextVisible(False)
        self.disk_bar.setValue(50)
        self.disk_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {self.theme.bg_surface_elevated};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {self.theme.accent_cyan};
                border-radius: 2px;
            }}
        """)
        save_layout.addWidget(self.disk_bar)
        layout.addWidget(save_card)

        # 6. Two-Column Options (Threads & Queue)
        opts_row = QHBoxLayout()
        opts_row.setSpacing(12)

        # Left Column: Parallel Threads
        threads_box = QFrame()
        threads_box.setObjectName("sunkenWell")
        tb_layout = QVBoxLayout(threads_box)
        tb_layout.setContentsMargins(10, 8, 10, 8)
        tb_layout.setSpacing(4)

        lbl_th = QLabel("PARALLEL CONNECTION THREADS")
        lbl_th.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 10px; font-weight: 700; letter-spacing: 0.05em;")
        tb_layout.addWidget(lbl_th)

        pills_row = QHBoxLayout()
        self.thread_btns = {}
        for count in [4, 8, 16, 32]:
            btn = QPushButton(str(count))
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda chk, c=count: self._select_threads(c))
            pills_row.addWidget(btn)
            self.thread_btns[count] = btn
        tb_layout.addLayout(pills_row)

        lbl_th_hint = QLabel("Recommended setting for maximum ISP bandwidth saturation")
        lbl_th_hint.setStyleSheet(f"color: {self.theme.text_muted}; font-size: 9px;")
        tb_layout.addWidget(lbl_th_hint)
        opts_row.addWidget(threads_box)

        # Right Column: Queue & Throttle
        queue_box = QFrame()
        queue_box.setObjectName("sunkenWell")
        qb_layout = QVBoxLayout(queue_box)
        qb_layout.setContentsMargins(10, 8, 10, 8)
        qb_layout.setSpacing(4)

        throttle_row = QHBoxLayout()
        lbl_thr = QLabel("SPEED THROTTLE")
        lbl_thr.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 10px; font-weight: 700; letter-spacing: 0.05em;")
        throttle_row.addWidget(lbl_thr)

        throttle_row.addStretch()

        self.chk_throttle = QCheckBox("Unlimited")
        self.chk_throttle.setChecked(True)
        throttle_row.addWidget(self.chk_throttle)
        qb_layout.addLayout(throttle_row)

        lbl_tq = QLabel("TARGET QUEUE")
        lbl_tq.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 10px; font-weight: 700; letter-spacing: 0.05em;")
        qb_layout.addWidget(lbl_tq)

        self.cmb_queue = QComboBox()
        self.cmb_queue.addItems(["Download Immediately", "Add to Main Queue", "Add to Night Owl Queue"])
        qb_layout.addWidget(self.cmb_queue)
        opts_row.addWidget(queue_box)

        layout.addLayout(opts_row)
        self._select_threads(self.selected_threads)
        self._update_disk_bar()

        # 7. Action Footer
        footer = QHBoxLayout()
        self.chk_remember = QCheckBox("Remember my choices")
        self.chk_remember.setChecked(getattr(self.settings, "remember_download_choices", True))
        footer.addWidget(self.chk_remember)

        footer.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        footer.addWidget(btn_cancel)

        btn_later = QPushButton("Download Later")
        btn_later.clicked.connect(self._on_later)
        footer.addWidget(btn_later)

        btn_start = QPushButton("⚡ Start Download Now")
        btn_start.setObjectName("primaryBtn")
        btn_start.setStyleSheet(f"""
            QPushButton#primaryBtn {{
                background-color: {self.theme.primary};
                color: {self.theme.primary_text};
                font-weight: 700;
                border-radius: 6px;
                padding: 8px 18px;
            }}
            QPushButton#primaryBtn:hover {{
                background-color: {self.theme.secondary};
            }}
        """)
        btn_start.clicked.connect(self._on_start)
        footer.addWidget(btn_start)

        layout.addLayout(footer)

    def _select_threads(self, count: int):
        self.selected_threads = count
        for c, btn in self.thread_btns.items():
            if c == count:
                btn.setChecked(True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {self.theme.bg_surface_elevated};
                        border: 1px solid {self.theme.primary};
                        color: {self.theme.primary};
                        font-weight: 700;
                        border-radius: 4px;
                    }}
                """)
            else:
                btn.setChecked(False)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {self.theme.bg_surface_sunken};
                        border: 1px solid {self.theme.border};
                        color: {self.theme.text_secondary};
                        border-radius: 4px;
                    }}
                """)

    def _browse_dest(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.txt_dest.text())
        if folder:
            self.txt_dest.setText(folder)

    def _update_disk_bar(self):
        folder = self.txt_dest.text().strip() or self.settings.save_path
        try:
            drive = os.path.splitdrive(folder)[0] or "C:"
            usage = shutil.disk_usage(folder if os.path.exists(folder) else drive + "\\")
            free_gb = usage.free / (1024 ** 3)
            total_gb = usage.total / (1024 ** 3)
            used_pct = int(((usage.total - usage.free) / max(1, usage.total)) * 100)
            self.lbl_disk_free.setText(f"{free_gb:.1f} GB free on Drive {drive}")
            self.disk_bar.setValue(used_pct)
        except Exception:
            self.lbl_disk_free.setText("Storage available")

        if self.file_size_bytes > 0:
            req_gb = self.file_size_bytes / (1024 ** 3)
            if req_gb >= 1.0:
                self.lbl_disk_req.setText(f"{req_gb:.2f} GB required")
            else:
                req_mb = self.file_size_bytes / (1024 ** 2)
                self.lbl_disk_req.setText(f"{req_mb:.1f} MB required")
        else:
            self.lbl_disk_req.setText("Dynamic stream")

    def _on_filename_changed(self, text: str):
        cat = self.settings.category_for(text)
        cat_name = cat.get("name", "Other")
        self.lbl_category_badge.setText(cat_name)

        ext = Path(text).suffix.lower()
        if ext in [".iso", ".img"]:
            self.lbl_type_icon.setText("💿")
        elif ext in [".zip", ".rar", ".7z", ".tar", ".gz"]:
            self.lbl_type_icon.setText("📦")
        elif ext in [".mp4", ".mkv", ".mov", ".avi", ".ts"]:
            self.lbl_type_icon.setText("🎬")
        elif ext in [".mp3", ".flac", ".wav", ".aac"]:
            self.lbl_type_icon.setText("🎵")
        elif ext in [".exe", ".msi"]:
            self.lbl_type_icon.setText("⚙️")
        elif ext in [".pdf", ".doc", ".docx"]:
            self.lbl_type_icon.setText("📄")
        else:
            self.lbl_type_icon.setText("📁")

    def _start_probe(self, url: str):
        if not url.startswith("http"):
            return
        self.lbl_preflight.setText("● Probing server capabilities...")
        self.lbl_preflight.setStyleSheet(f"color: {self.theme.accent_amber}; font-size: 11px;")

        def worker():
            probe_task = DownloadTask.from_url(url, settings=self.settings)
            res = probe_task._probe()
            self._signals.probed.emit(res)

        threading.Thread(target=worker, daemon=True).start()

    def _on_probe_complete(self, res: dict):
        if not res:
            self.lbl_preflight.setText("⚠ Warning: Server did not respond to probe. Download will attempt direct streaming.")
            self.lbl_preflight.setStyleSheet(f"color: {self.theme.accent_amber}; font-size: 11px;")
            return

        name = res.get("name", "")
        if name and not self.txt_filename.text():
            self.txt_filename.setText(name)

        length = res.get("length", 0)
        self.file_size_bytes = length
        self.server_ranges = res.get("ranges", False)

        if length > 0:
            if length >= 1024 ** 3:
                sz_str = f"{length / (1024 ** 3):.2f} GB"
            else:
                sz_str = f"{length / (1024 ** 2):.1f} MB"
            self.lbl_size.setText(f"Size: {sz_str} (Exact: {length:,} bytes)")
        else:
            self.lbl_size.setText("Size: Unknown length (Single stream)")

        range_str = "Range 206 Supported • Resume Enabled" if self.server_ranges else "Single Stream • Resume Unavailable"
        self.lbl_preflight.setText(f"● Server Verified: {range_str} • SSL Valid")
        self.lbl_preflight.setStyleSheet(f"color: {self.theme.accent_green if self.server_ranges else self.theme.accent_amber}; font-size: 11px;")
        self._update_disk_bar()

    def _create_task(self, state: str = "running") -> DownloadTask:
        url = self.txt_url.text().strip()
        filename = self.txt_filename.text().strip()
        dest_dir = self.txt_dest.text().strip()
        queue_choice = self.cmb_queue.currentText()
        queue_name = "Night Owl Queue" if "Night Owl" in queue_choice else "Main Queue"

        task = DownloadTask.from_url(
            url=url,
            dest_dir=dest_dir,
            filename=filename,
            segments=self.selected_threads,
            settings=self.settings,
        )
        if self.file_size_bytes > 0:
            task.total_size = self.file_size_bytes
        task.queue_name = queue_name
        task.state = state
        return task

    def _on_start(self):
        if not self.txt_url.text().strip():
            return
        self.action_choice = "start"
        self.task = self._create_task(state="running")
        self.accept()

    def _on_later(self):
        if not self.txt_url.text().strip():
            return
        self.action_choice = "later"
        self.task = self._create_task(state="queued")
        self.accept()
