"""High-contrast, space-optimized Main Window for IDM Pro matching Stitch designs."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog,
    QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QPushButton,
    QSplitter, QTableWidget, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from ..config import Settings
from ..core.queue import DownloadQueue
from ..core.scheduler import Scheduler
from ..engine.downloader import DownloadTask
from .download_dialog import ModernDownloadDialog
from .settings_dialog import ModernSettingsDialog
from .theme import ThemeColors, apply_theme_to_app, get_theme
from .widgets.segmented_bar import ModernSegmentedProgressBar
from .widgets.socket_matrix import SocketMatrixPanel
from .widgets.sparkline import ThroughputSparkline


class Signals(QObject):
    update = Signal(object)
    status = Signal(str)


class HeaderBar(QFrame):
    """Modern command header supporting window dragging and double-click to maximize."""

    def __init__(self, main_win, parent=None):
        super().__init__(parent)
        self.main_win = main_win
        self.setObjectName("panel")
        self.setFixedHeight(48)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            wh = self.main_win.windowHandle()
            if wh:
                wh.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.main_win._toggle_maximize()
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    """Ultra-modern, high-contrast desktop download manager UI."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("IDM Pro v5.0 — High Speed Download Accelerator")
        self.resize(1280, 800)
        self.setMinimumSize(1040, 640)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self.settings = Settings.load()
        self.current_theme = get_theme(getattr(self.settings, "active_theme", "Obsidian Cyber Mica"))

        self.sig = Signals()
        self.sig.update.connect(self._on_task_update)
        self.sig.status.connect(self._flash_status)

        self.queue = DownloadQueue(self.settings, on_change=self._task_changed)
        self.scheduler = Scheduler(self.settings, on_apply=self._sched_apply)
        self.scheduler.start()

        self._rows = {}          # id(task) -> row
        self._row_task = {}      # row -> task
        self._filter = "All Downloads"
        self._search_query = ""
        self._selected_task: Optional[DownloadTask] = None
        self._last_clipboard = ""

        # Build UI & Apply Theme
        self._build_ui()
        self._apply_current_theme()

        # Update Timer (500ms for high-frequency telemetry)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

        self._refresh_table()

    def _apply_current_theme(self):
        apply_theme_to_app(QApplication.instance(), self.current_theme.name)
        if hasattr(self, "socket_matrix"):
            self.socket_matrix.set_theme(self.current_theme)
        if hasattr(self, "sparkline"):
            self.sparkline.set_theme(self.current_theme)
        for r in range(self.table.rowCount()):
            cell_widget = self.table.cellWidget(r, 1)
            if cell_widget and hasattr(cell_widget, "bar"):
                cell_widget.bar.set_theme(self.current_theme)
        self._update_window_frame_style()

    def _build_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("canvas")
        central_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCentralWidget(central_widget)

        self.outer_layout = QVBoxLayout(central_widget)
        self.outer_layout.setContentsMargins(4, 4, 4, 4)
        self.outer_layout.setSpacing(0)

        # Main window frame container
        self.main_frame = QFrame()
        self.main_frame.setObjectName("mainFrame")
        self.outer_layout.addWidget(self.main_frame)
        self._update_window_frame_style()

        root_layout = QVBoxLayout(self.main_frame)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(6)

        # 1. Compact, Single-Tier Command Header (Height strictly 48px)
        header_widget = self._build_header()
        root_layout.addWidget(header_widget, 0)

        # 2. Main Work Area (Splitter: Left Nav Rail + Center Table) takes 100% remaining space
        work_splitter = QSplitter(Qt.Orientation.Horizontal)
        work_splitter.setHandleWidth(4)

        # Left Acrylic Rail
        self.nav_rail = self._build_sidebar()
        work_splitter.addWidget(self.nav_rail)

        # Center Main View (Table + Sub-headers + Bottom Inspector Drawer)
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(4)

        # Sub-header bar
        center_layout.addWidget(self._build_table_controls(), 0)

        # High-Density Table (dominant central view)
        self.table = self._build_table()
        center_layout.addWidget(self.table, 1)

        # Bottom Inspector Panel (Live Socket Matrix)
        self.socket_matrix = SocketMatrixPanel(theme=self.current_theme)
        self.socket_matrix.setFixedHeight(96)
        center_layout.addWidget(self.socket_matrix, 0)

        work_splitter.addWidget(center_container)
        work_splitter.setStretchFactor(0, 0)
        work_splitter.setStretchFactor(1, 1)
        work_splitter.setSizes([210, 1070])
        root_layout.addWidget(work_splitter, 1)

        # 3. Bottom Status Bar
        root_layout.addWidget(self._build_bottom_bar(), 0)

    # --- UI Sub-builders ---
    def _build_header(self) -> QWidget:
        container = HeaderBar(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 4, 6, 4)
        layout.setSpacing(8)

        # Left: Brand & Badges
        lbl_logo = QLabel("⚡")
        lbl_logo.setStyleSheet(f"color: {self.current_theme.primary}; font-size: 16px; font-weight: bold;")
        layout.addWidget(lbl_logo)

        lbl_title = QLabel("IDM PRO")
        lbl_title.setObjectName("appTitle")
        layout.addWidget(lbl_title)

        lbl_ver = QLabel("v5.0")
        lbl_ver.setObjectName("versionBadge")
        layout.addWidget(lbl_ver)

        layout.addSpacing(8)

        # Navigation Tabs
        for tab_name in ["Queue", "Scheduler", "Explorer"]:
            btn_tab = QPushButton(tab_name)
            btn_tab.setFixedHeight(26)
            if tab_name == "Queue":
                btn_tab.setStyleSheet(f"background-color: {self.current_theme.bg_surface_elevated}; color: {self.current_theme.primary}; font-weight: bold;")
            else:
                btn_tab.setStyleSheet(f"background: transparent; border: none; color: {self.current_theme.text_secondary};")
                if tab_name == "Scheduler":
                    btn_tab.clicked.connect(self._open_settings)
            layout.addWidget(btn_tab)

        layout.addSpacing(6)

        # Search Bar
        self.txt_filter = QLineEdit()
        self.txt_filter.setObjectName("searchBar")
        self.txt_filter.setPlaceholderText("Search [Ctrl+F]...")
        self.txt_filter.setFixedWidth(140)
        self.txt_filter.textChanged.connect(self._on_search_text)
        layout.addWidget(self.txt_filter)

        # Primary Actions
        btn_add = QPushButton("+ Add URL")
        btn_add.setObjectName("primaryBtn")
        btn_add.setFixedHeight(28)
        btn_add.clicked.connect(lambda: self._action_add_url())
        layout.addWidget(btn_add)

        btn_resume_all = QPushButton("Resume All")
        btn_resume_all.setFixedHeight(28)
        btn_resume_all.clicked.connect(self._action_resume_all)
        layout.addWidget(btn_resume_all)

        btn_pause_all = QPushButton("Pause All")
        btn_pause_all.setFixedHeight(28)
        btn_pause_all.clicked.connect(self._action_pause_all)
        layout.addWidget(btn_pause_all)

        self.btn_speed_limit = QPushButton(f"Limit: {self._get_limit_str()}")
        self.btn_speed_limit.setFixedHeight(28)
        self.btn_speed_limit.clicked.connect(self._toggle_speed_limit)
        layout.addWidget(self.btn_speed_limit)

        btn_settings = QPushButton("Settings")
        btn_settings.setFixedHeight(28)
        btn_settings.clicked.connect(self._open_settings)
        layout.addWidget(btn_settings)

        layout.addStretch()

        # Right: Live Throughput Telemetry HUD
        hud_box = QFrame()
        hud_box.setObjectName("sunkenWell")
        hud_box.setFixedHeight(30)
        hud_box.setMinimumWidth(210)
        hud_layout = QHBoxLayout(hud_box)
        hud_layout.setContentsMargins(8, 2, 8, 2)
        hud_layout.setSpacing(6)

        self.lbl_speed_hud = QLabel("0.0 MB/s")
        self.lbl_speed_hud.setObjectName("telemetry")
        self.lbl_speed_hud.setStyleSheet(f"color: {self.current_theme.primary}; font-size: 13px; font-weight: bold;")
        hud_layout.addWidget(self.lbl_speed_hud)

        self.sparkline = ThroughputSparkline(theme=self.current_theme)
        hud_layout.addWidget(self.sparkline)

        self.lbl_threads_hud = QLabel("0 threads")
        self.lbl_threads_hud.setStyleSheet(f"color: {self.current_theme.text_secondary}; font-size: 11px;")
        hud_layout.addWidget(self.lbl_threads_hud)

        layout.addWidget(hud_box)

        # Window Controls Divider
        win_sep = QFrame()
        win_sep.setFrameShape(QFrame.Shape.VLine)
        win_sep.setStyleSheet(f"color: {self.current_theme.border}; max-height: 18px;")
        layout.addWidget(win_sep)

        # Custom Window Controls (Minimize, Maximize/Restore, Close)
        win_ctrls = QHBoxLayout()
        win_ctrls.setSpacing(3)
        win_ctrls.setContentsMargins(2, 0, 0, 0)

        self.btn_min = QPushButton("─")
        self.btn_min.setObjectName("winCtrlMin")
        self.btn_min.setFixedSize(30, 26)
        self.btn_min.setToolTip("Minimize")
        self.btn_min.clicked.connect(self.showMinimized)
        win_ctrls.addWidget(self.btn_min)

        self.btn_max = QPushButton("□")
        self.btn_max.setObjectName("winCtrlMax")
        self.btn_max.setFixedSize(30, 26)
        self.btn_max.setToolTip("Maximize")
        self.btn_max.clicked.connect(self._toggle_maximize)
        win_ctrls.addWidget(self.btn_max)

        self.btn_close = QPushButton("✕")
        self.btn_close.setObjectName("winCtrlClose")
        self.btn_close.setFixedSize(34, 26)
        self.btn_close.setToolTip("Close")
        self.btn_close.clicked.connect(self.close)
        win_ctrls.addWidget(self.btn_close)

        layout.addLayout(win_ctrls)
        return container

    def _build_sidebar(self) -> QWidget:
        container = QFrame()
        container.setObjectName("panel")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Engine Core indicator
        core_box = QFrame()
        core_box.setObjectName("sunkenWell")
        cb_layout = QHBoxLayout(core_box)
        cb_layout.setContentsMargins(8, 5, 8, 5)
        lbl_core = QLabel("⚡ 16 Threads Engine Active")
        lbl_core.setStyleSheet(f"color: {self.current_theme.primary}; font-size: 11px; font-weight: bold;")
        cb_layout.addWidget(lbl_core)
        layout.addWidget(core_box)

        # Tree View for Navigation & Categories
        self.tree = QTreeWidget()
        self.tree.setObjectName("navRail")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(12)
        self.tree.itemClicked.connect(self._on_tree_item_clicked)

        # 1. Status Monitors
        root_status = QTreeWidgetItem(self.tree, ["STATUS MONITORS"])
        root_status.setFlags(root_status.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.item_all = QTreeWidgetItem(root_status, ["All Downloads (0)"])
        self.item_active = QTreeWidgetItem(root_status, ["Active (0)"])
        self.item_finished = QTreeWidgetItem(root_status, ["Finished (0)"])
        self.item_paused = QTreeWidgetItem(root_status, ["Paused (0)"])
        root_status.setExpanded(True)

        # 2. File Categories
        root_cat = QTreeWidgetItem(self.tree, ["CATEGORIES"])
        root_cat.setFlags(root_cat.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.cat_items = {}
        for cat in ["Video", "Music", "Compressed", "Programs", "Documents"]:
            ci = QTreeWidgetItem(root_cat, [f"{cat} (0)"])
            self.cat_items[cat] = ci
        root_cat.setExpanded(True)

        # 3. Execution Queues
        root_q = QTreeWidgetItem(self.tree, ["QUEUES"])
        root_q.setFlags(root_q.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.item_main_q = QTreeWidgetItem(root_q, ["Main Queue"])
        self.item_night_q = QTreeWidgetItem(root_q, ["Night Owl Queue"])
        root_q.setExpanded(True)

        layout.addWidget(self.tree, 1)

        # Bottom Quota Card
        quota_card = QFrame()
        quota_card.setObjectName("sunkenWell")
        qc_layout = QVBoxLayout(quota_card)
        qc_layout.setContentsMargins(8, 6, 8, 6)
        qc_layout.setSpacing(3)

        self.lbl_quota_text = QLabel("Monthly: 0 / 200 GB")
        self.lbl_quota_text.setStyleSheet(f"color: {self.current_theme.primary}; font-size: 11px; font-weight: bold;")
        qc_layout.addWidget(self.lbl_quota_text)

        self.quota_bar = ModernSegmentedProgressBar(theme=self.current_theme)
        self.quota_bar.setFixedHeight(8)
        qc_layout.addWidget(self.quota_bar)

        layout.addWidget(quota_card, 0)
        return container

    def _build_table_controls(self) -> QWidget:
        container = QFrame()
        container.setObjectName("panel")
        container.setFixedHeight(30)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(10)

        lbl_mode = QLabel("Queue Tasks:")
        lbl_mode.setStyleSheet(f"color: {self.current_theme.text_secondary}; font-weight: bold; font-size: 11px;")
        layout.addWidget(lbl_mode)

        layout.addStretch()

        lbl_sort = QLabel("Sort:")
        lbl_sort.setStyleSheet(f"color: {self.current_theme.text_muted}; font-size: 11px;")
        layout.addWidget(lbl_sort)

        self.cmb_sort = QComboBox()
        self.cmb_sort.addItems(["Throughput ↓", "Progress %", "File Size", "Added Time"])
        self.cmb_sort.currentIndexChanged.connect(lambda: self._refresh_table())
        layout.addWidget(self.cmb_sort)

        lbl_slices = QLabel("16-Segment Physical Slices View")
        lbl_slices.setStyleSheet(f"color: {self.current_theme.accent_cyan}; font-size: 10px; font-weight: bold;")
        layout.addWidget(lbl_slices)

        return container

    def _build_table(self) -> QTableWidget:
        table = QTableWidget(0, 5)
        table.setObjectName("downloadTable")
        table.setHorizontalHeaderLabels([
            "FILE NAME & SOURCE",
            "STATUS & SEGMENT BUFFER",
            "SIZE & PROGRESS",
            "SPEED & ETA",
            "OPERATIONS",
        ])
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(54)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(0, 310)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(2, 160)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(3, 140)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(4, 210)

        table.itemSelectionChanged.connect(self._on_table_selection)
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self._show_context_menu)
        return table

    def _build_bottom_bar(self) -> QWidget:
        container = QFrame()
        container.setObjectName("panel")
        container.setFixedHeight(24)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        self.lbl_status_global = QLabel("Ready • Buffer Health: 100% • Limit: Unlimited")
        self.lbl_status_global.setStyleSheet(f"color: {self.current_theme.text_secondary}; font-size: 11px;")
        layout.addWidget(self.lbl_status_global)

        layout.addStretch()

        lbl_port = QLabel("TCP Turbo: ON • Port 6881 Open")
        lbl_port.setStyleSheet(f"color: {self.current_theme.primary}; font-size: 11px; font-weight: bold;")
        layout.addWidget(lbl_port)

        return container

    # --- Table Row Rendering ---
    def _refresh_table(self):
        tasks = self._get_filtered_tasks()
        self.table.setRowCount(len(tasks))
        self._rows.clear()
        self._row_task.clear()

        for row, task in enumerate(tasks):
            self._rows[id(task)] = row
            self._row_task[row] = task
            self._populate_row(row, task)

        self._update_sidebar_counts()

    def _get_filtered_tasks(self) -> list:
        tasks = list(self.queue.tasks)

        if self._search_query:
            q = self._search_query.lower()
            tasks = [t for t in tasks if q in t.filename.lower() or q in t.url.lower()]

        f = self._filter
        if f.startswith("Active"):
            tasks = [t for t in tasks if t.state in ("running", "merging")]
        elif f.startswith("Finished"):
            tasks = [t for t in tasks if t.state == "completed"]
        elif f.startswith("Paused"):
            tasks = [t for t in tasks if t.state in ("paused", "queued")]
        elif f.startswith("Main Queue"):
            tasks = [t for t in tasks if getattr(t, "queue_name", "Main Queue") == "Main Queue"]
        elif f.startswith("Night Owl"):
            tasks = [t for t in tasks if getattr(t, "queue_name", "Main Queue") == "Night Owl Queue"]
        elif any(f.startswith(c) for c in ["Video", "Music", "Compressed", "Programs", "Documents"]):
            cat_name = f.split(" ")[0]
            tasks = [t for t in tasks if t.category.lower() == cat_name.lower()]

        sort_mode = self.cmb_sort.currentText() if hasattr(self, "cmb_sort") else "Throughput ↓"
        if "Throughput" in sort_mode:
            tasks.sort(key=lambda x: getattr(x, "speed", 0.0), reverse=True)
        elif "Progress" in sort_mode:
            tasks.sort(key=lambda x: getattr(x, "progress", 0.0), reverse=True)
        elif "File Size" in sort_mode:
            tasks.sort(key=lambda x: getattr(x, "total_size", 0), reverse=True)
        elif "Added Time" in sort_mode:
            tasks.sort(key=lambda x: getattr(x, "created", 0.0), reverse=True)

        return tasks

    def _populate_row(self, row: int, task: DownloadTask):
        w0 = self.table.cellWidget(row, 0)
        if w0 is not None and getattr(w0, "_task_id", None) == id(task):
            self._update_row_widgets(row, task)
        else:
            self._create_row_widgets(row, task)
            self._update_row_widgets(row, task)

    def _create_row_widgets(self, row: int, task: DownloadTask):
        # Col 0: File Name & Source
        w0 = QWidget()
        w0.setObjectName("cellCol0")
        w0._task_id = id(task)
        l0 = QHBoxLayout(w0)
        l0.setContentsMargins(8, 4, 8, 4)
        l0.setSpacing(10)

        ext = Path(task.filename or task.url).suffix.upper().replace(".", "") or "FILE"
        lbl_badge = QLabel(ext[:4])
        lbl_badge.setObjectName("versionBadge")
        lbl_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {self.current_theme.bg_surface_elevated};
                border: 1px solid {self.current_theme.border};
                border-radius: 4px;
                padding: 2px 5px;
                color: {self.current_theme.primary};
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        l0.addWidget(lbl_badge)

        col_name = QVBoxLayout()
        col_name.setSpacing(2)
        lbl_fn = QLabel(task.filename or Path(task.url).name or "Download")
        lbl_fn.setStyleSheet("font-weight: bold; font-size: 13px; color: #FFFFFF;")
        col_name.addWidget(lbl_fn)

        lbl_url = QLabel(task.url[:45] + ("..." if len(task.url) > 45 else ""))
        lbl_url.setStyleSheet(f"font-size: 11px; color: {self.current_theme.text_muted};")
        col_name.addWidget(lbl_url)
        l0.addLayout(col_name)

        w0.lbl_badge = lbl_badge
        w0.lbl_fn = lbl_fn
        w0.lbl_url = lbl_url
        self.table.setCellWidget(row, 0, w0)

        # Col 1: Status & Multi-thread Buffer Array
        w1 = QWidget()
        w1.setObjectName("cellCol1")
        w1._task_id = id(task)
        l1 = QVBoxLayout(w1)
        l1.setContentsMargins(6, 4, 6, 4)
        l1.setSpacing(3)

        st_row = QHBoxLayout()
        lbl_st = QLabel("Queued")
        lbl_st.setStyleSheet(f"color: {self.current_theme.text_secondary}; font-size: 11px; font-weight: bold;")
        st_row.addWidget(lbl_st)
        st_row.addStretch()

        lbl_pct = QLabel("0.0%")
        lbl_pct.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: bold;")
        st_row.addWidget(lbl_pct)
        l1.addLayout(st_row)

        bar = ModernSegmentedProgressBar(theme=self.current_theme)
        bar.set_task(task)
        l1.addWidget(bar)

        w1.lbl_st = lbl_st
        w1.lbl_pct = lbl_pct
        w1.bar = bar
        w1.last_state = None
        self.table.setCellWidget(row, 1, w1)

        # Col 2: Size & Progress
        w2 = QWidget()
        w2.setObjectName("cellCol2")
        w2._task_id = id(task)
        l2 = QVBoxLayout(w2)
        l2.setContentsMargins(6, 4, 6, 4)
        l2.setSpacing(2)

        lbl_sz = QLabel("0 B / Unknown")
        lbl_sz.setStyleSheet("font-weight: bold; font-size: 12px; color: #FFFFFF;")
        l2.addWidget(lbl_sz)

        lbl_save = QLabel(f"Folder: {Path(task.dest_dir).name or 'Downloads'}")
        lbl_save.setStyleSheet(f"font-size: 11px; color: {self.current_theme.text_secondary};")
        l2.addWidget(lbl_save)

        w2.lbl_sz = lbl_sz
        w2.lbl_save = lbl_save
        self.table.setCellWidget(row, 2, w2)

        # Col 3: Speed & ETA
        w3 = QWidget()
        w3.setObjectName("cellCol3")
        w3._task_id = id(task)
        l3 = QVBoxLayout(w3)
        l3.setContentsMargins(6, 4, 6, 4)
        l3.setSpacing(2)

        lbl_sp = QLabel("0 KB/s")
        lbl_sp.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {self.current_theme.text_muted};")
        l3.addWidget(lbl_sp)

        lbl_eta = QLabel("ETA: —")
        lbl_eta.setStyleSheet(f"font-size: 11px; color: {self.current_theme.text_secondary};")
        l3.addWidget(lbl_eta)

        w3.lbl_sp = lbl_sp
        w3.lbl_eta = lbl_eta
        self.table.setCellWidget(row, 3, w3)

        # Col 4: High-Contrast, Explicit OPERATIONS Action Buttons
        w4 = QWidget()
        w4.setObjectName("cellCol4")
        w4._task_id = id(task)
        l4 = QHBoxLayout(w4)
        l4.setContentsMargins(4, 8, 4, 8)
        l4.setSpacing(6)

        btn_act = QPushButton("Pause")
        btn_act.setProperty("class", "opAction")
        btn_act.setFixedWidth(60)
        btn_act.clicked.connect(lambda chk, t=task: self._on_op_action(t))
        l4.addWidget(btn_act)

        btn_folder = QPushButton("Folder")
        btn_folder.setProperty("class", "opAction")
        btn_folder.setFixedWidth(54)
        btn_folder.clicked.connect(lambda chk, t=task: self._action_open_folder(t))
        l4.addWidget(btn_folder)

        btn_del = QPushButton("Delete")
        btn_del.setProperty("class", "opDelete")
        btn_del.setFixedWidth(54)
        btn_del.clicked.connect(lambda chk, t=task: self._action_delete(t))
        l4.addWidget(btn_del)

        w4.btn_act = btn_act
        w4.btn_folder = btn_folder
        w4.btn_del = btn_del
        w4.last_state = None
        self.table.setCellWidget(row, 4, w4)

    def _update_row_widgets(self, row: int, task: DownloadTask):
        w0 = self.table.cellWidget(row, 0)
        w1 = self.table.cellWidget(row, 1)
        w2 = self.table.cellWidget(row, 2)
        w3 = self.table.cellWidget(row, 3)
        w4 = self.table.cellWidget(row, 4)

        if not (w0 and w1 and w2 and w3 and w4 and hasattr(w0, "lbl_fn")):
            self._create_row_widgets(row, task)
            w0 = self.table.cellWidget(row, 0)
            w1 = self.table.cellWidget(row, 1)
            w2 = self.table.cellWidget(row, 2)
            w3 = self.table.cellWidget(row, 3)
            w4 = self.table.cellWidget(row, 4)

        # Col 0: File Name & Source (Only update when actually changed to prevent flashing)
        cur_fn = task.filename or Path(task.url).name or "Download"
        if w0.lbl_fn.text() != cur_fn:
            w0.lbl_fn.setText(cur_fn)
            ext = Path(cur_fn).suffix.upper().replace(".", "") or "FILE"
            w0.lbl_badge.setText(ext[:4])

        url_short = task.url[:45] + ("..." if len(task.url) > 45 else "")
        if w0.lbl_url.text() != url_short:
            w0.lbl_url.setText(url_short)

        # Col 1: Status & Segment Buffer
        pct_val = max(0.0, min(100.0, task.progress))
        w1.lbl_pct.setText(f"{pct_val:.1f}%")

        if task.state == "running":
            state_str = f"Downloading ({len(task.parts or [])} segments)"
            col = self.current_theme.accent_green
        elif task.state == "merging":
            state_str = "Merging Segments"
            col = self.current_theme.accent_amber
        elif task.state == "completed":
            state_str = "100% Completed"
            col = self.current_theme.accent_green
        elif task.state == "paused":
            state_str = "Paused"
            col = self.current_theme.text_muted
        else:
            state_str = f"Error: {task.error or 'Failed'}"
            col = self.current_theme.accent_red

        if getattr(w1, "last_state", None) != task.state or w1.lbl_st.text() != state_str:
            w1.lbl_st.setText(state_str)
            w1.lbl_st.setStyleSheet(f"color: {col}; font-size: 11px; font-weight: bold;")
            w1.last_state = task.state

        w1.bar.set_task(task)

        # Col 2: Size & Progress
        dl_str = self._format_size(task.downloaded)
        tot_str = self._format_size(task.total_size) if task.total_size else "Unknown"
        w2.lbl_sz.setText(f"{dl_str} / {tot_str}")

        dest_name = f"Folder: {Path(task.dest_dir).name or 'Downloads'}"
        if w2.lbl_save.text() != dest_name:
            w2.lbl_save.setText(dest_name)

        # Col 3: Speed & ETA
        if task.speed >= 1024 * 1024:
            speed_str = f"{task.speed / (1024 * 1024):.1f} MB/s"
        elif task.speed > 0:
            speed_str = f"{task.speed / 1024:.0f} KB/s"
        else:
            speed_str = "0 KB/s"
        w3.lbl_sp.setText(speed_str)
        w3.lbl_sp.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {self.current_theme.primary if task.speed > 0 else self.current_theme.text_muted};")
        w3.lbl_eta.setText(f"ETA: {self._calc_eta(task)}")

        # Col 4: Action button update only if state changed
        if getattr(w4, "last_state", None) != task.state:
            w4.last_state = task.state
            if task.state in ("running", "merging"):
                w4.btn_act.setText("Pause")
            elif task.state == "completed":
                w4.btn_act.setText("Open")
            else:
                w4.btn_act.setText("Resume")

    def _on_op_action(self, task: DownloadTask):
        if task.state in ("running", "merging"):
            self._action_pause(task)
        elif task.state == "completed":
            self._action_open_file(task)
        else:
            self._action_resume(task)

    def _update_sidebar_counts(self):
        tasks = self.queue.tasks
        total = len(tasks)
        active = sum(1 for t in tasks if t.state in ("running", "merging"))
        finished = sum(1 for t in tasks if t.state == "completed")
        paused = sum(1 for t in tasks if t.state in ("paused", "queued"))

        self.item_all.setText(0, f"All Downloads ({total})")
        self.item_active.setText(0, f"Active ({active})")
        self.item_finished.setText(0, f"Finished ({finished})")
        self.item_paused.setText(0, f"Paused ({paused})")

        for cat, item in self.cat_items.items():
            cnt = sum(1 for t in tasks if t.category.lower() == cat.lower())
            item.setText(0, f"{cat} ({cnt})")

        used_bytes = sum(t.downloaded for t in tasks)
        used_gb = used_bytes / (1024 ** 3)
        self.lbl_quota_text.setText(f"Monthly: {used_gb:.1f} / 200 GB")

    def _tick(self):
        total_speed = 0.0
        active_tasks = 0
        total_threads = 0

        for r, task in self._row_task.items():
            if task.state in ("running", "merging"):
                total_speed += getattr(task, "speed", 0.0)
                active_tasks += 1
                total_threads += len(getattr(task, "parts", []))
            self._update_row_widgets(r, task)

        if total_speed >= 1024 * 1024:
            sp_text = f"↓ {total_speed / (1024 * 1024):.1f} MB/s"
        else:
            sp_text = f"↓ {total_speed / 1024:.0f} KB/s"
        self.lbl_speed_hud.setText(sp_text)
        self.sparkline.add_sample(total_speed)
        self.lbl_threads_hud.setText(f"{total_threads} threads")

        self.lbl_status_global.setText(
            f"Global Throughput: {sp_text.replace('↓ ', '')} • Active Conns: {total_threads} • Limit: {self._get_limit_str()}"
        )

        if self._selected_task:
            self.socket_matrix.update_task(self._selected_task)

        if getattr(self.settings, "clipboard_monitoring", True):
            cb_text = QApplication.clipboard().text().strip()
            if cb_text != self._last_clipboard and cb_text.startswith("http") and any(cb_text.endswith(ext) for ext in [".zip", ".rar", ".iso", ".exe", ".msi", ".mp4", ".mkv", ".tar.gz"]):
                self._last_clipboard = cb_text
                self._prompt_clipboard_download(cb_text)

    def _on_table_selection(self):
        selected_rows = self.table.selectedIndexes()
        if not selected_rows:
            self._selected_task = None
            self.socket_matrix.update_task(None)
            return
        row = selected_rows[0].row()
        task = self._row_task.get(row)
        self._selected_task = task
        self.socket_matrix.update_task(task)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, col: int):
        self._filter = item.text(0)
        self._refresh_table()

    def _on_search_text(self, text: str):
        self._search_query = text.strip()
        self._refresh_table()

    # --- Actions ---
    def _action_add_url(self, prefill_url: str = ""):
        if not isinstance(prefill_url, str) or not prefill_url:
            cb_text = QApplication.clipboard().text().strip()
            if cb_text.startswith("http://") or cb_text.startswith("https://") or cb_text.startswith("ftp://"):
                prefill_url = cb_text
            else:
                prefill_url = ""

        dlg = ModernDownloadDialog(self, initial_url=prefill_url, settings=self.settings, theme=self.current_theme)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.task:
            self.queue.add(dlg.task)
            self._refresh_table()

    def _prompt_clipboard_download(self, url: str):
        ans = QMessageBox.question(
            self,
            "Download Link Detected",
            f"Download detected from clipboard:\n\n{url}\n\nStart download?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            self._action_add_url(prefill_url=url)

    def _action_resume(self, task: DownloadTask):
        self.queue.resume(task)
        self._refresh_table()

    def _action_pause(self, task: DownloadTask):
        self.queue.pause(task)
        self._refresh_table()

    def _action_resume_all(self):
        for t in self.queue.tasks:
            if t.state in ("paused", "queued", "error"):
                self.queue.resume(t)
        self._refresh_table()

    def _action_pause_all(self):
        for t in self.queue.tasks:
            if t.state in ("running", "merging"):
                self.queue.pause(t)
        self._refresh_table()

    def _action_delete(self, task: DownloadTask):
        res = QMessageBox.question(
            self, "Confirm Delete",
            f"Remove download '{task.filename or task.url}' from queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.queue.remove(task, delete_files=False)
            self._refresh_table()

    def _action_open_file(self, task: DownloadTask):
        if task.file_path and os.path.exists(task.file_path):
            os.startfile(task.file_path)

    def _action_open_folder(self, task: DownloadTask):
        folder = task.dest_dir or self.settings.save_path
        if os.path.exists(folder):
            os.startfile(folder)

    def _toggle_speed_limit(self):
        self.settings.speed_limiter = not self.settings.speed_limiter
        if self.settings.speed_limiter and not self.settings.speed_limit_kbps:
            self.settings.speed_limit_kbps = 50 * 1024
        self.settings.save()
        self.btn_speed_limit.setText(f"Limit: {self._get_limit_str()}")

    def _get_limit_str(self) -> str:
        if not self.settings.speed_limiter or not self.settings.speed_limit_kbps:
            return "Unlimited"
        return f"{self.settings.speed_limit_kbps // 1024} MB/s"

    def _open_settings(self):
        dlg = ModernSettingsDialog(self, settings=self.settings, on_theme_change=self._on_live_theme_change)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_current_theme()
            self._refresh_table()

    def _on_live_theme_change(self, theme_name: str):
        self.current_theme = get_theme(theme_name)
        self.settings.active_theme = theme_name
        self._apply_current_theme()

    def _show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        task = self._row_task.get(row)
        if not task:
            return

        menu = QMenu(self)
        if task.state in ("running", "merging"):
            act_pause = menu.addAction("Pause")
            act_pause.triggered.connect(lambda: self._action_pause(task))
        else:
            act_resume = menu.addAction("Resume")
            act_resume.triggered.connect(lambda: self._action_resume(task))

        menu.addSeparator()
        if task.file_path and os.path.exists(task.file_path):
            act_open = menu.addAction("Open File")
            act_open.triggered.connect(lambda: self._action_open_file(task))
        act_folder = menu.addAction("Open Folder")
        act_folder.triggered.connect(lambda: self._action_open_folder(task))

        menu.addSeparator()
        act_copy = menu.addAction("Copy Download Link")
        act_copy.triggered.connect(lambda: QApplication.clipboard().setText(task.url))
        act_del = menu.addAction("Delete")
        act_del.triggered.connect(lambda: self._action_delete(task))

        menu.exec(self.table.mapToGlobal(pos))

    # --- Callbacks ---
    def _on_task_update(self, task):
        row = self._rows.get(id(task))
        if row is not None:
            self._update_row_widgets(row, task)

    def _task_changed(self, task):
        self.sig.update.emit(task)

    def _flash_status(self, msg: str):
        self.lbl_status_global.setText(msg)

    def _sched_apply(self, action: str, limit_kbps: int):
        if action == "start_all":
            self._action_resume_all()
        elif action == "stop_all":
            self._action_pause_all()
        elif action == "limit_speed":
            self.settings.speed_limiter = True
            self.settings.speed_limit_kbps = limit_kbps
            self.settings.save()

    def _format_size(self, b: int) -> str:
        if b >= 1024 ** 3:
            return f"{b / (1024 ** 3):.2f} GB"
        if b >= 1024 ** 2:
            return f"{b / (1024 ** 2):.1f} MB"
        if b >= 1024:
            return f"{b / 1024:.0f} KB"
        return f"{b} B"

    def _calc_eta(self, task: DownloadTask) -> str:
        if task.state == "completed":
            return "Done"
        if task.state == "paused":
            return "—"
        if not task.speed or not task.total_size:
            return "—"
        rem = max(0, task.total_size - task.downloaded)
        secs = int(rem / max(task.speed, 1))
        if secs >= 3600:
            return f"{secs // 3600}h {(secs % 3600) // 60}m"
        return f"{secs // 60:02d}m {secs % 60:02d}s"

    # --- Frameless Window Management & Drag/Resize ---
    def _toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _update_window_frame_style(self):
        if not hasattr(self, "main_frame") or not hasattr(self, "outer_layout"):
            return
        t = self.current_theme
        if self.isMaximized():
            self.outer_layout.setContentsMargins(0, 0, 0, 0)
            self.main_frame.setStyleSheet(f"""
                QFrame#mainFrame {{
                    background-color: {t.bg_canvas};
                    border: none;
                    border-radius: 0px;
                }}
            """)
        else:
            self.outer_layout.setContentsMargins(4, 4, 4, 4)
            self.main_frame.setStyleSheet(f"""
                QFrame#mainFrame {{
                    background-color: {t.bg_canvas};
                    border: 1px solid {t.border_focus if t.is_dark else t.border};
                    border-radius: 8px;
                }}
            """)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if hasattr(self, "btn_max"):
                if self.isMaximized():
                    self.btn_max.setText("❐")
                    self.btn_max.setToolTip("Restore")
                else:
                    self.btn_max.setText("□")
                    self.btn_max.setToolTip("Maximize")
            self._update_window_frame_style()
        super().changeEvent(event)

    def _get_edge_at(self, pos: QPoint):
        margin = 6
        w = self.width()
        h = self.height()
        x = pos.x()
        y = pos.y()

        top = y < margin
        bottom = y > h - margin
        left = x < margin
        right = x > w - margin

        if top and left:
            return Qt.Edge.TopEdge | Qt.Edge.LeftEdge
        if top and right:
            return Qt.Edge.TopEdge | Qt.Edge.RightEdge
        if bottom and left:
            return Qt.Edge.BottomEdge | Qt.Edge.LeftEdge
        if bottom and right:
            return Qt.Edge.BottomEdge | Qt.Edge.RightEdge
        if top:
            return Qt.Edge.TopEdge
        if bottom:
            return Qt.Edge.BottomEdge
        if left:
            return Qt.Edge.LeftEdge
        if right:
            return Qt.Edge.RightEdge
        return None

    def _cursor_for_edge(self, edge):
        if edge in (Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.Edge.BottomEdge | Qt.Edge.RightEdge):
            return Qt.CursorShape.SizeFDiagCursor
        if edge in (Qt.Edge.TopEdge | Qt.Edge.RightEdge, Qt.Edge.BottomEdge | Qt.Edge.LeftEdge):
            return Qt.CursorShape.SizeBDiagCursor
        if edge in (Qt.Edge.LeftEdge, Qt.Edge.RightEdge):
            return Qt.CursorShape.SizeHorCursor
        if edge in (Qt.Edge.TopEdge, Qt.Edge.BottomEdge):
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def mouseMoveEvent(self, event):
        if not self.isMaximized():
            edge = self._get_edge_at(event.position().toPoint())
            if edge is not None:
                self.setCursor(self._cursor_for_edge(edge))
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.isMaximized():
            edge = self._get_edge_at(event.position().toPoint())
            if edge is not None:
                wh = self.windowHandle()
                if wh:
                    wh.startSystemResize(edge)
                    return
        super().mousePressEvent(event)
