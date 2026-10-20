"""Modern, high-contrast theme engine for IDM Pro.

High-contrast readability, single-font QSS syntax for Qt 6 compatibility,
and proper padding/spacing to prevent button and text clipping.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication


@dataclass
class ThemeColors:
    name: str
    is_dark: bool
    bg_canvas: str          # Level 0 background
    bg_surface: str         # Level 1 card / panel
    bg_surface_elevated: str# Level 2 hover / active
    bg_surface_sunken: str  # Inset input wells / tracks
    border: str             # Border stroke (crisp, high visibility)
    border_focus: str       # Focus border glow
    primary: str            # Cyber emerald / cyan
    primary_text: str       # Text color on primary button
    secondary: str          # Laser cyan / cobalt
    text_primary: str       # High emphasis text (pure white/black)
    text_secondary: str     # Medium emphasis text (silver/slate)
    text_muted: str         # Subtle secondary text
    accent_green: str       # Success / active
    accent_amber: str       # Warning / merging
    accent_cyan: str        # Streaming
    accent_purple: str      # Quota / rules
    accent_red: str         # Error / delete


THEMES: Dict[str, ThemeColors] = {
    "Obsidian Cyber Mica": ThemeColors(
        name="Obsidian Cyber Mica",
        is_dark=True,
        bg_canvas="#0B0E14",
        bg_surface="#131822",
        bg_surface_elevated="#1E2433",
        bg_surface_sunken="#080B10",
        border="#2A3447",
        border_focus="#00FF9D",
        primary="#00FF9D",
        primary_text="#0B0E14",
        secondary="#00F0FF",
        text_primary="#FFFFFF",
        text_secondary="#CBD5E1",
        text_muted="#94A3B8",
        accent_green="#00FF9D",
        accent_amber="#F59E0B",
        accent_cyan="#00F0FF",
        accent_purple="#A855F7",
        accent_red="#EF4444",
    ),
    "Electric Cyan Protocol": ThemeColors(
        name="Electric Cyan Protocol",
        is_dark=True,
        bg_canvas="#070C14",
        bg_surface="#0F1726",
        bg_surface_elevated="#182438",
        bg_surface_sunken="#05080E",
        border="#22344D",
        border_focus="#00E5FF",
        primary="#00E5FF",
        primary_text="#070C14",
        secondary="#38BDF8",
        text_primary="#FFFFFF",
        text_secondary="#CBD5E1",
        text_muted="#94A3B8",
        accent_green="#00FF9D",
        accent_amber="#FBBF24",
        accent_cyan="#00E5FF",
        accent_purple="#818CF8",
        accent_red="#F87171",
    ),
    "Titanium Midnight": ThemeColors(
        name="Titanium Midnight",
        is_dark=True,
        bg_canvas="#0E1015",
        bg_surface="#16181F",
        bg_surface_elevated="#232630",
        bg_surface_sunken="#090A0D",
        border="#323642",
        border_focus="#FFFFFF",
        primary="#FFFFFF",
        primary_text="#0E1015",
        secondary="#A1A1AA",
        text_primary="#FFFFFF",
        text_secondary="#D4D4D8",
        text_muted="#A1A1AA",
        accent_green="#4ADE80",
        accent_amber="#F59E0B",
        accent_cyan="#38BDF8",
        accent_purple="#C084FC",
        accent_red="#FB7185",
    ),
    "Aurora Glow": ThemeColors(
        name="Aurora Glow",
        is_dark=True,
        bg_canvas="#0F0A18",
        bg_surface="#191128",
        bg_surface_elevated="#271C3D",
        bg_surface_sunken="#0A0610",
        border="#3D295C",
        border_focus="#C084FC",
        primary="#C084FC",
        primary_text="#0F0A18",
        secondary="#F472B6",
        text_primary="#FFFFFF",
        text_secondary="#E9D5FF",
        text_muted="#A855F7",
        accent_green="#34D399",
        accent_amber="#FBBF24",
        accent_cyan="#22D3EE",
        accent_purple="#C084FC",
        accent_red="#F43F5E",
    ),
    "Clean Frost (Light)": ThemeColors(
        name="Clean Frost (Light)",
        is_dark=False,
        bg_canvas="#F1F5F9",
        bg_surface="#FFFFFF",
        bg_surface_elevated="#E2E8F0",
        bg_surface_sunken="#F8FAFC",
        border="#CBD5E1",
        border_focus="#059669",
        primary="#059669",
        primary_text="#FFFFFF",
        secondary="#0284C7",
        text_primary="#0F172A",
        text_secondary="#334155",
        text_muted="#64748B",
        accent_green="#059669",
        accent_amber="#D97706",
        accent_cyan="#0284C7",
        accent_purple="#7C3AED",
        accent_red="#DC2626",
    ),
}


def get_theme(name: str) -> ThemeColors:
    return THEMES.get(name, THEMES["Obsidian Cyber Mica"])


def generate_qss(theme: ThemeColors) -> str:
    """Generate high-contrast, robust Qt stylesheet for the chosen theme."""
    return f"""
    * {{
        font-family: 'Segoe UI';
        font-size: 12px;
        color: {theme.text_primary};
    }}

    QMainWindow, QDialog {{
        background-color: {theme.bg_canvas};
    }}

    QWidget#canvas {{
        background-color: {theme.bg_canvas};
    }}

    /* Card Panels & Containers */
    QFrame#panel, QWidget#panel, QFrame.card, QWidget.card {{
        background-color: {theme.bg_surface};
        border: 1px solid {theme.border};
        border-radius: 6px;
    }}

    QFrame#sunkenWell, QWidget#sunkenWell {{
        background-color: {theme.bg_surface_sunken};
        border: 1px solid {theme.border};
        border-radius: 4px;
    }}

    /* Headers & Labels */
    QLabel {{
        background: transparent;
        color: {theme.text_primary};
    }}
    QLabel#appTitle {{
        font-size: 15px;
        font-weight: bold;
        color: {theme.text_primary};
    }}
    QLabel#versionBadge {{
        font-size: 10px;
        font-weight: bold;
        color: {theme.primary};
        background-color: {theme.bg_surface_elevated};
        border: 1px solid {theme.border};
        border-radius: 4px;
        padding: 2px 6px;
    }}
    QLabel#telemetry {{
        font-family: 'Consolas';
        font-weight: bold;
        color: {theme.text_primary};
    }}

    /* Search Bar */
    QLineEdit#searchBar {{
        background-color: {theme.bg_surface_sunken};
        border: 1px solid {theme.border};
        border-radius: 4px;
        padding: 4px 10px;
        color: {theme.text_primary};
        font-size: 12px;
    }}
    QLineEdit#searchBar:focus {{
        border: 1px solid {theme.border_focus};
    }}

    /* Buttons */
    QPushButton {{
        background-color: {theme.bg_surface_elevated};
        color: {theme.text_primary};
        border: 1px solid {theme.border};
        border-radius: 4px;
        padding: 4px 10px;
        font-weight: 600;
        min-height: 22px;
    }}
    QPushButton:hover {{
        background-color: {theme.border};
        border-color: {theme.border_focus};
        color: {theme.primary};
    }}
    QPushButton:pressed {{
        background-color: {theme.bg_surface_sunken};
    }}

    /* Primary Accent Action Button */
    QPushButton#primaryBtn {{
        background-color: {theme.primary};
        color: {theme.primary_text};
        font-weight: bold;
        border: 1px solid {theme.primary};
        border-radius: 4px;
        padding: 5px 14px;
    }}
    QPushButton#primaryBtn:hover {{
        background-color: {theme.secondary};
        border-color: {theme.secondary};
    }}

    /* Custom Window Controls (Frameless Modern Header) */
    QPushButton#winCtrlMin, QPushButton#winCtrlMax {{
        background: transparent;
        border: none;
        border-radius: 4px;
        color: {theme.text_secondary};
        font-size: 13px;
        font-weight: bold;
        padding: 0;
        margin: 0;
    }}
    QPushButton#winCtrlMin:hover, QPushButton#winCtrlMax:hover {{
        background-color: {theme.bg_surface_elevated};
        color: {theme.text_primary};
    }}
    QPushButton#winCtrlClose {{
        background: transparent;
        border: none;
        border-radius: 4px;
        color: {theme.text_secondary};
        font-size: 13px;
        font-weight: bold;
        padding: 0;
        margin: 0;
    }}
    QPushButton#winCtrlClose:hover {{
        background-color: #E81123;
        color: #FFFFFF;
    }}

    /* Table Operations Action Buttons */
    QPushButton.opAction {{
        background-color: {theme.bg_surface_elevated};
        color: {theme.text_primary};
        border: 1px solid {theme.border};
        border-radius: 4px;
        padding: 3px 8px;
        font-size: 11px;
        font-weight: bold;
        min-height: 22px;
    }}
    QPushButton.opAction:hover {{
        background-color: {theme.primary};
        color: {theme.primary_text};
        border-color: {theme.primary};
    }}

    QPushButton.opDelete {{
        background-color: {theme.bg_surface_elevated};
        color: {theme.text_secondary};
        border: 1px solid {theme.border};
        border-radius: 4px;
        padding: 3px 8px;
        font-size: 11px;
        font-weight: bold;
        min-height: 22px;
    }}
    QPushButton.opDelete:hover {{
        background-color: {theme.accent_red};
        color: #FFFFFF;
        border-color: {theme.accent_red};
    }}

    /* Navigation Sidebar */
    QTreeWidget#navRail, QListWidget#navRail {{
        background-color: {theme.bg_surface};
        border: 1px solid {theme.border};
        border-radius: 6px;
        padding: 4px;
    }}
    QTreeWidget#navRail::item, QListWidget#navRail::item {{
        padding: 6px 8px;
        border-radius: 4px;
        color: {theme.text_secondary};
        font-weight: 500;
    }}
    QTreeWidget#navRail::item:hover, QListWidget#navRail::item:hover {{
        background-color: {theme.bg_surface_elevated};
        color: {theme.text_primary};
    }}
    QTreeWidget#navRail::item:selected, QListWidget#navRail::item:selected {{
        background-color: {theme.bg_surface_elevated};
        color: {theme.primary};
        border-left: 3px solid {theme.primary};
        font-weight: bold;
    }}

    /* Main Table */
    QTableWidget#downloadTable {{
        background-color: {theme.bg_surface};
        border: 1px solid {theme.border};
        border-radius: 6px;
        gridline-color: {theme.border};
        selection-background-color: {theme.bg_surface_elevated};
        selection-color: {theme.text_primary};
    }}
    QTableWidget#downloadTable::item {{
        padding: 4px 6px;
        border-bottom: 1px solid {theme.border};
    }}
    QTableWidget#downloadTable::item:selected {{
        background-color: {theme.bg_surface_elevated};
    }}
    QHeaderView::section {{
        background-color: {theme.bg_surface_sunken};
        color: {theme.text_secondary};
        font-weight: bold;
        font-size: 11px;
        border: none;
        border-bottom: 1px solid {theme.border};
        border-right: 1px solid {theme.border};
        padding: 6px 8px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}

    /* Inputs */
    QLineEdit, QSpinBox, QComboBox {{
        background-color: {theme.bg_surface_sunken};
        border: 1px solid {theme.border};
        border-radius: 4px;
        padding: 4px 8px;
        color: {theme.text_primary};
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
        border: 1px solid {theme.border_focus};
    }}
    QComboBox::drop-down {{
        border: none;
        padding-right: 6px;
    }}

    /* Checkboxes */
    QCheckBox {{
        spacing: 6px;
        color: {theme.text_primary};
    }}
    QCheckBox::indicator {{
        width: 15px;
        height: 15px;
        border: 1px solid {theme.border};
        border-radius: 3px;
        background: {theme.bg_surface_sunken};
    }}
    QCheckBox::indicator:checked {{
        background: {theme.primary};
        border-color: {theme.primary};
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background: {theme.bg_canvas};
        width: 8px;
        margin: 0;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {theme.border};
        min-height: 24px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {theme.text_muted};
    }}
    QScrollBar:horizontal {{
        background: {theme.bg_canvas};
        height: 8px;
        margin: 0;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {theme.border};
        min-width: 24px;
        border-radius: 4px;
    }}
    """


def apply_theme_to_app(app: QApplication, theme_name: str = "Obsidian Cyber Mica") -> ThemeColors:
    theme = get_theme(theme_name)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(generate_qss(theme))
    
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(theme.bg_canvas))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(theme.text_primary))
    palette.setColor(QPalette.ColorRole.Base, QColor(theme.bg_surface_sunken))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme.bg_surface))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme.bg_surface_elevated))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme.text_primary))
    palette.setColor(QPalette.ColorRole.Text, QColor(theme.text_primary))
    palette.setColor(QPalette.ColorRole.Button, QColor(theme.bg_surface_elevated))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme.text_primary))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.primary))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(theme.primary_text))
    app.setPalette(palette)
    return theme
