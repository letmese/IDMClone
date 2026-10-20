"""Modern Settings & Preferences page matching Stitch screen2.png."""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QSlider, QSpinBox, QStackedWidget, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..config import Settings
from .theme import THEMES, ThemeColors, get_theme


class ModernSettingsDialog(QDialog):
    """Modern Settings modal matching IDM Pro screen2.png."""

    theme_changed = Signal(str)

    def __init__(self, parent=None, settings: Settings = None, on_theme_change: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.settings = settings or Settings.load()
        self.current_theme_name = getattr(self.settings, "active_theme", "Obsidian Cyber Mica")
        self.theme = get_theme(self.current_theme_name)
        self.on_theme_change = on_theme_change

        self.setWindowTitle("Settings — IDM Pro")
        self.resize(880, 620)
        self.setMinimumSize(820, 560)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._theme_cards = {}
        self._build_ui()

    def _build_ui(self):
        # Outer shell
        main_frame = QFrame(self)
        main_frame.setGeometry(0, 0, self.width(), self.height())
        main_frame.setObjectName("panel")
        main_frame.setStyleSheet(f"""
            QFrame#panel {{
                background-color: {self.theme.bg_canvas};
                border: 1px solid {self.theme.border_focus if self.theme.is_dark else self.theme.border};
                border-radius: 12px;
            }}
        """)
        self.main_frame = main_frame

        root_layout = QVBoxLayout(main_frame)
        root_layout.setContentsMargins(18, 14, 18, 14)
        root_layout.setSpacing(10)

        # 1. Top Header Row
        header_row = QHBoxLayout()
        header_left = QHBoxLayout()
        lbl_icon = QLabel("⚙️")
        lbl_icon.setStyleSheet("font-size: 16px;")
        header_left.addWidget(lbl_icon)

        lbl_title = QLabel("Settings — IDM Pro")
        lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {self.theme.text_primary};")
        header_left.addWidget(lbl_title)

        lbl_ver = QLabel("v5.0-RELEASE")
        lbl_ver.setObjectName("versionBadge")
        header_left.addWidget(lbl_ver)
        header_row.addLayout(header_left)

        header_row.addStretch()

        self.txt_search = QLineEdit()
        self.txt_search.setObjectName("searchBar")
        self.txt_search.setPlaceholderText("Search settings (e.g. threads, proxy)...")
        self.txt_search.setFixedWidth(240)
        header_row.addWidget(self.txt_search)

        lbl_state = QLabel("● ENGINE STATE: OPTIMIZED")
        lbl_state.setObjectName("telemetry")
        lbl_state.setStyleSheet(f"color: {self.theme.accent_green}; font-size: 11px; font-weight: 700;")
        header_row.addWidget(lbl_state)

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
        header_row.addWidget(btn_close)
        root_layout.addLayout(header_row)

        lbl_sub = QLabel("Configure multi-segmented downloading engine, network proxies, speed limiter, and UI themes.")
        lbl_sub.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 11px;")
        root_layout.addWidget(lbl_sub)

        # 2. Main Body Splitter / Row
        body_row = QHBoxLayout()
        body_row.setSpacing(12)

        # Left Nav Rail
        nav_box = QFrame()
        nav_box.setObjectName("panel")
        nav_box.setFixedWidth(200)
        nav_layout = QVBoxLayout(nav_box)
        nav_layout.setContentsMargins(6, 8, 6, 8)
        nav_layout.setSpacing(4)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navRail")
        nav_items = [
            ("General", "🖥️"),
            ("Connection & Engine", "⚡"),
            ("Speed Limiter & Quota", "⏱️"),
            ("Proxy & SOCKS", "🌐"),
            ("Categories & Storage", "📁"),
            ("Site Passwords", "🔑"),
            ("Appearance & Themes", "🎨"),
        ]
        for name, icon in nav_items:
            item = QListWidgetItem(f"{icon}  {name}")
            self.nav_list.addItem(item)
        self.nav_list.currentRowChanged.connect(self._on_tab_changed)
        nav_layout.addWidget(self.nav_list)

        # Bottom info card in sidebar
        bottom_badge = QFrame()
        bottom_badge.setObjectName("sunkenWell")
        bb_layout = QVBoxLayout(bottom_badge)
        bb_layout.setContentsMargins(8, 6, 8, 6)
        lbl_bb1 = QLabel("BUFFER CACHE: 99.4%")
        lbl_bb1.setObjectName("telemetry")
        lbl_bb1.setStyleSheet(f"color: {self.theme.accent_green}; font-size: 9px; font-weight: 700;")
        bb_layout.addWidget(lbl_bb1)

        lbl_bb2 = QLabel("SEG: 206 RANGE | POOL: 32 CONN")
        lbl_bb2.setObjectName("telemetry")
        lbl_bb2.setStyleSheet(f"color: {self.theme.text_muted}; font-size: 9px;")
        bb_layout.addWidget(lbl_bb2)
        nav_layout.addWidget(bottom_badge)

        body_row.addWidget(nav_box)

        # Right Stacked Pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_general_page())
        self.stack.addWidget(self._build_connection_page())
        self.stack.addWidget(self._build_limiter_page())
        self.stack.addWidget(self._build_proxy_page())
        self.stack.addWidget(self._build_categories_page())
        self.stack.addWidget(self._build_auth_page())
        self.stack.addWidget(self._build_themes_page())
        body_row.addWidget(self.stack)

        root_layout.addLayout(body_row)

        # 3. Bottom Action Footer
        footer = QHBoxLayout()
        btn_defaults = QPushButton("↺ Restore Factory Defaults")
        btn_defaults.clicked.connect(self._restore_defaults)
        footer.addWidget(btn_defaults)

        footer.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        footer.addWidget(btn_cancel)

        btn_save = QPushButton("💾 Save & Apply Settings")
        btn_save.setObjectName("primaryBtn")
        btn_save.setStyleSheet(f"""
            QPushButton#primaryBtn {{
                background-color: {self.theme.primary};
                color: {self.theme.primary_text};
                font-weight: 700;
                border-radius: 6px;
                padding: 7px 18px;
            }}
            QPushButton#primaryBtn:hover {{
                background-color: {self.theme.secondary};
            }}
        """)
        btn_save.clicked.connect(self._save_settings)
        footer.addWidget(btn_save)

        root_layout.addLayout(footer)

        # Select Connection & Engine as active by default (matching screen2.png)
        self.nav_list.setCurrentRow(1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "main_frame"):
            self.main_frame.setGeometry(0, 0, self.width(), self.height())

    def _on_tab_changed(self, index: int):
        self.stack.setCurrentIndex(index)

    # --- Page Builders ---
    def _build_connection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        # Card: Multi-Thread Engine & Connections
        card = QFrame()
        card.setObjectName("panel")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(10)

        title_row = QHBoxLayout()
        lbl_ct = QLabel("⚡ Multi-Thread Engine & Connections")
        lbl_ct.setStyleSheet(f"color: {self.theme.primary}; font-weight: 700; font-size: 13px;")
        title_row.addWidget(lbl_ct)

        title_row.addStretch()

        lbl_badge = QLabel("CORE PIPELINE v4")
        lbl_badge.setObjectName("versionBadge")
        title_row.addWidget(lbl_badge)
        c_layout.addLayout(title_row)

        # Slider row
        lbl_sl = QLabel("Default Connections per Download")
        lbl_sl.setStyleSheet(f"color: {self.theme.text_primary}; font-weight: 600; font-size: 12px;")
        c_layout.addWidget(lbl_sl)

        slider_row = QHBoxLayout()
        self.conn_slider = QSlider(Qt.Orientation.Horizontal)
        self.conn_slider.setRange(1, 32)
        val = getattr(self.settings, "default_connections", 16)
        self.conn_slider.setValue(val)

        self.lbl_conn_val = QLabel(f"{val} Threads")
        self.lbl_conn_val.setObjectName("versionBadge")
        self.lbl_conn_val.setFixedWidth(80)
        self.lbl_conn_val.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.conn_slider.valueChanged.connect(lambda v: self.lbl_conn_val.setText(f"{v} Threads"))
        slider_row.addWidget(self.conn_slider)
        slider_row.addWidget(self.lbl_conn_val)
        c_layout.addLayout(slider_row)

        sub_slider = QHBoxLayout()
        lbl_min = QLabel("1 (Single Stream)")
        lbl_min.setStyleSheet(f"color: {self.theme.text_muted}; font-size: 10px;")
        sub_slider.addWidget(lbl_min)
        sub_slider.addStretch()
        lbl_mid = QLabel("16 (Recommended)")
        lbl_mid.setStyleSheet(f"color: {self.theme.accent_green}; font-size: 10px; font-weight: 700;")
        sub_slider.addWidget(lbl_mid)
        sub_slider.addStretch()
        lbl_max = QLabel("32 (Max Bandwidth)")
        lbl_max.setStyleSheet(f"color: {self.theme.text_muted}; font-size: 10px;")
        sub_slider.addWidget(lbl_max)
        c_layout.addLayout(sub_slider)

        # Toggle: Aggressive Segment Optimization
        self.chk_aggressive = QCheckBox("Aggressive Segment Optimization (Dynamic Range splitting)")
        self.chk_aggressive.setChecked(getattr(self.settings, "aggressive_segment_optimization", True))
        c_layout.addWidget(self.chk_aggressive)

        lbl_agg_sub = QLabel("Dynamic Range splitting for unresponsive servers and high-latency mirrors.")
        lbl_agg_sub.setStyleSheet(f"color: {self.theme.text_muted}; font-size: 10px;")
        c_layout.addWidget(lbl_agg_sub)

        # Timeout & Retries row
        inputs_row = QHBoxLayout()
        inputs_row.setSpacing(16)

        col1 = QVBoxLayout()
        col1.addWidget(QLabel("Connection Timeout"))
        self.spn_timeout = QSpinBox()
        self.spn_timeout.setRange(5, 120)
        self.spn_timeout.setSuffix(" sec")
        self.spn_timeout.setValue(getattr(self.settings, "connection_timeout", 20))
        col1.addWidget(self.spn_timeout)
        inputs_row.addLayout(col1)

        col2 = QVBoxLayout()
        col2.addWidget(QLabel("Max Retries on Failure"))
        self.spn_retries = QSpinBox()
        self.spn_retries.setRange(0, 20)
        self.spn_retries.setSuffix(" attempts")
        self.spn_retries.setValue(self.settings.retries)
        col2.addWidget(self.spn_retries)
        inputs_row.addLayout(col2)

        c_layout.addLayout(inputs_row)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_limiter_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("panel")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(10)

        lbl_title = QLabel("⏱️ Speed Limiter & Bandwidth Allocation")
        lbl_title.setStyleSheet(f"color: {self.theme.primary}; font-weight: 700; font-size: 13px;")
        c_layout.addWidget(lbl_title)

        self.chk_limiter = QCheckBox("Enable Speed Limiter (Cap overall download throughput)")
        self.chk_limiter.setChecked(self.settings.speed_limiter)
        c_layout.addWidget(self.chk_limiter)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Speed Cap:"))
        self.spn_limit_mb = QSpinBox()
        self.spn_limit_mb.setRange(1, 1000)
        self.spn_limit_mb.setSuffix(" MB/s")
        limit_mb = (self.settings.speed_limit_kbps // 1024) if self.settings.speed_limit_kbps else 50
        self.spn_limit_mb.setValue(limit_mb)
        speed_row.addWidget(self.spn_limit_mb)
        speed_row.addStretch()
        c_layout.addLayout(speed_row)

        # Quota block
        c_layout.addWidget(QLabel("Monthly / Weekly Traffic Quota"))
        self.chk_quota = QCheckBox("Enforce Traffic Quota")
        self.chk_quota.setChecked(self.settings.quota_enabled)
        c_layout.addWidget(self.chk_quota)

        quota_row = QHBoxLayout()
        self.spn_quota_gb = QSpinBox()
        self.spn_quota_gb.setRange(1, 10000)
        self.spn_quota_gb.setSuffix(" GB")
        self.spn_quota_gb.setValue(int(self.settings.quota_bytes / (1024 ** 3)) if self.settings.quota_bytes else 200)
        quota_row.addWidget(self.spn_quota_gb)

        self.cmb_quota_period = QComboBox()
        self.cmb_quota_period.addItems(["monthly", "weekly"])
        self.cmb_quota_period.setCurrentText(self.settings.quota_period)
        quota_row.addWidget(self.cmb_quota_period)
        quota_row.addStretch()
        c_layout.addLayout(quota_row)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_themes_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("panel")
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(10)

        title_row = QHBoxLayout()
        lbl_title = QLabel("🎨 Appearance & Theme Studio")
        lbl_title.setStyleSheet(f"color: {self.theme.primary}; font-weight: 700; font-size: 13px;")
        title_row.addWidget(lbl_title)
        title_row.addStretch()
        lbl_eng = QLabel("DARK ACRYLIC ENGINE")
        lbl_eng.setObjectName("versionBadge")
        title_row.addWidget(lbl_eng)
        c_layout.addLayout(title_row)

        lbl_desc = QLabel("Select a visual style. Changes apply across the entire application instantly.")
        lbl_desc.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 11px;")
        c_layout.addWidget(lbl_desc)

        # Theme preview cards grid
        grid = QGridLayout()
        grid.setSpacing(10)

        theme_list = [
            ("Obsidian Cyber Mica", "#00FF9D", "#0F141C", "Default • Emerald & Cyan"),
            ("Electric Cyan Protocol", "#00E5FF", "#0B111A", "Deep Space Navy"),
            ("Titanium Midnight", "#FFFFFF", "#121316", "Matte Dark Monochrome"),
            ("Aurora Glow", "#A855F7", "#130D1F", "Purple & Magenta Neon"),
            ("Clean Frost (Light)", "#059669", "#FFFFFF", "Crisp Acrylic Light"),
        ]

        for i, (name, accent, bg, desc) in enumerate(theme_list):
            btn_card = QPushButton()
            btn_card.setFixedHeight(74)
            btn_card.setCheckable(True)
            btn_card.setChecked(name == self.current_theme_name)
            btn_card.clicked.connect(lambda chk, n=name: self._select_theme(n))

            # Style card button
            is_active = (name == self.current_theme_name)
            border = f"2px solid {accent}" if is_active else f"1px solid {self.theme.border}"
            btn_card.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    border: {border};
                    border-radius: 8px;
                    text-align: left;
                    padding: 8px 12px;
                }}
            """)

            card_layout = QVBoxLayout(btn_card)
            card_layout.setContentsMargins(0, 0, 0, 0)
            card_layout.setSpacing(2)

            color_pip = QLabel("●  " + name)
            color_pip.setStyleSheet(f"color: {accent}; font-weight: 700; font-size: 12px;")
            card_layout.addWidget(color_pip)

            lbl_sub = QLabel(desc)
            lbl_sub.setStyleSheet("color: #94A3B8; font-size: 10px;")
            card_layout.addWidget(lbl_sub)

            row = i // 2
            col = i % 2
            grid.addWidget(btn_card, row, col)
            self._theme_cards[name] = (btn_card, accent, bg)

        c_layout.addLayout(grid)
        layout.addWidget(card)
        layout.addStretch()
        return page

    def _select_theme(self, name: str):
        self.current_theme_name = name
        for t_name, (btn, accent, bg) in self._theme_cards.items():
            if t_name == name:
                btn.setChecked(True)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg};
                        border: 2px solid {accent};
                        border-radius: 8px;
                        text-align: left;
                        padding: 8px 12px;
                    }}
                """)
            else:
                btn.setChecked(False)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {bg};
                        border: 1px solid {self.theme.border};
                        border-radius: 8px;
                        text-align: left;
                        padding: 8px 12px;
                    }}
                """)
        if self.on_theme_change:
            self.on_theme_change(name)

    def _build_general_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        card = QFrame()
        card.setObjectName("panel")
        c_layout = QVBoxLayout(card)
        c_layout.addWidget(QLabel("🖥️ General Application Settings"))

        self.chk_clipboard = QCheckBox("Monitor clipboard for downloadable URLs")
        self.chk_clipboard.setChecked(getattr(self.settings, "clipboard_monitoring", True))
        c_layout.addWidget(self.chk_clipboard)

        self.chk_sound = QCheckBox("Play notification sound when downloads finish")
        self.chk_sound.setChecked(self.settings.completion_sound)
        c_layout.addWidget(self.chk_sound)

        self.chk_shutdown = QCheckBox("Shutdown computer when all downloads complete")
        self.chk_shutdown.setChecked(self.settings.shutdown_after_queue)
        c_layout.addWidget(self.chk_shutdown)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_proxy_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        card = QFrame()
        card.setObjectName("panel")
        c_layout = QVBoxLayout(card)
        c_layout.addWidget(QLabel("🌐 Network Proxy & SOCKS Configuration"))

        self.chk_use_proxy = QCheckBox("Enable Proxy Server")
        self.chk_use_proxy.setChecked(self.settings.use_proxy)
        c_layout.addWidget(self.chk_use_proxy)

        c_layout.addWidget(QLabel("HTTP / SOCKS5 Proxy Host (e.g. socks5://127.0.0.1:9050):"))
        self.txt_http_proxy = QLineEdit(self.settings.http_proxy)
        c_layout.addWidget(self.txt_http_proxy)

        btn_tor = QPushButton("🧅 Quick Tor Preset (SOCKS5 127.0.0.1:9050)")
        btn_tor.clicked.connect(lambda: self.txt_http_proxy.setText("socks5://127.0.0.1:9050"))
        c_layout.addWidget(btn_tor)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_categories_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        card = QFrame()
        card.setObjectName("panel")
        c_layout = QVBoxLayout(card)
        c_layout.addWidget(QLabel("📁 Download Categories & Default Directories"))

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Default Save Folder:"))
        self.txt_save_path = QLineEdit(self.settings.save_path)
        path_row.addWidget(self.txt_save_path)
        btn_br = QPushButton("Browse...")
        btn_br.clicked.connect(lambda: self._browse_dir(self.txt_save_path))
        path_row.addWidget(btn_br)
        c_layout.addLayout(path_row)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _build_auth_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        card = QFrame()
        card.setObjectName("panel")
        c_layout = QVBoxLayout(card)
        c_layout.addWidget(QLabel("🔑 Site Passwords & Authorization"))
        lbl_info = QLabel("Save credentials for hosts requiring HTTP Basic or Digest authentication.")
        lbl_info.setStyleSheet(f"color: {self.theme.text_secondary}; font-size: 11px;")
        c_layout.addWidget(lbl_info)

        self.auth_table = QTableWidget(0, 3)
        self.auth_table.setHorizontalHeaderLabels(["Host", "Username", "Password"])
        self.auth_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for host, cred in self.settings.site_passwords.items():
            r = self.auth_table.rowCount()
            self.auth_table.insertRow(r)
            self.auth_table.setItem(r, 0, QTableWidgetItem(host))
            self.auth_table.setItem(r, 1, QTableWidgetItem(cred.get("user", "")))
            self.auth_table.setItem(r, 2, QTableWidgetItem(cred.get("pass", "")))
        c_layout.addWidget(self.auth_table)

        layout.addWidget(card)
        layout.addStretch()
        return page

    def _browse_dir(self, line_edit: QLineEdit):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory", line_edit.text())
        if folder:
            line_edit.setText(folder)

    def _restore_defaults(self):
        self.conn_slider.setValue(16)
        self.chk_aggressive.setChecked(True)
        self.spn_timeout.setValue(20)
        self.spn_retries.setValue(5)
        self.chk_limiter.setChecked(False)
        self.spn_limit_mb.setValue(50)
        self._select_theme("Obsidian Cyber Mica")

    def _save_settings(self):
        # Update settings object
        self.settings.default_connections = self.conn_slider.value()
        self.settings.max_connections = self.conn_slider.value()
        self.settings.aggressive_segment_optimization = self.chk_aggressive.isChecked()
        self.settings.connection_timeout = self.spn_timeout.value()
        self.settings.retries = self.spn_retries.value()
        self.settings.speed_limiter = self.chk_limiter.isChecked()
        self.settings.speed_limit_kbps = self.spn_limit_mb.value() * 1024 if self.chk_limiter.isChecked() else 0
        self.settings.quota_enabled = self.chk_quota.isChecked()
        self.settings.quota_bytes = self.spn_quota_gb.value() * (1024 ** 3)
        self.settings.quota_period = self.cmb_quota_period.currentText()
        self.settings.active_theme = self.current_theme_name
        self.settings.clipboard_monitoring = self.chk_clipboard.isChecked()
        self.settings.completion_sound = self.chk_sound.isChecked()
        self.settings.shutdown_after_queue = self.chk_shutdown.isChecked()
        self.settings.use_proxy = self.chk_use_proxy.isChecked()
        self.settings.http_proxy = self.txt_http_proxy.text().strip()
        self.settings.save_path = self.txt_save_path.text().strip()
        self.settings.save()
        self.accept()
