"""A light, modern visual theme applied globally at startup.

This is a purely cosmetic layer: the base Qt style is switched to *Fusion*
(cleaner and identical on Windows/macOS/Linux) and a single Qt Style Sheet
refines colours, spacing and rounded corners. No widget logic changes — call
``apply(app)`` once and everything is restyled; delete the call to revert.
"""
from __future__ import annotations

import os

from PySide6 import QtWidgets

# ---- palette ---------------------------------------------------------------
BG = "#f4f5f7"          # window / desktop chrome
SURFACE = "#ffffff"     # panels, inputs, lists
BORDER = "#d8dce1"      # neutral separators
BORDER_STRONG = "#c7ccd3"
TEXT = "#1c1e21"        # primary text
MUTED = "#5c6470"       # secondary text / group titles
ACCENT = "#2f6fed"      # primary blue (matches the canvas selection colour)
ACCENT_TEXT = "#1c4bb5"
SEL_BG = "#e4edfd"      # light selection fill
HOVER = "#eef1f5"

# absolute path to the combobox chevron (QSS needs forward slashes); resolved
# at import so it works both from source and inside a PyInstaller bundle
chevron = os.path.join(os.path.dirname(__file__), "resources",
                       "chevron_down.svg").replace("\\", "/")

STYLESHEET = f"""
QWidget {{
    color: {TEXT};
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", system-ui;
    font-size: 12px;
}}
QMainWindow, QDialog {{ background: {BG}; }}
QMessageBox, QInputDialog {{ background: {BG}; }}

/* ---- menu bar / menus ---- */
QMenuBar {{ background: {BG}; padding: 2px 4px; }}
QMenuBar::item {{ background: transparent; padding: 4px 10px; border-radius: 5px; }}
QMenuBar::item:selected {{ background: {SEL_BG}; color: {ACCENT_TEXT}; }}
QMenu {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px; padding: 5px; }}
QMenu::item {{ padding: 5px 26px 5px 12px; border-radius: 5px; }}
QMenu::item:selected {{ background: {SEL_BG}; color: {ACCENT_TEXT}; }}
QMenu::separator {{ height: 1px; background: #e8eaee; margin: 5px 8px; }}

/* ---- toolbars ---- */
QToolBar {{ background: {BG}; border: none; padding: 4px 5px; spacing: 2px; }}
QToolBar::separator {{ width: 1px; background: #dbdfe4; margin: 5px 6px; }}
QToolButton {{ background: transparent; border: 1px solid transparent;
               border-radius: 6px; padding: 3px; }}
QToolButton:hover {{ background: {HOVER}; border-color: #dde1e7; }}
QToolButton:pressed {{ background: #dde5f1; }}
QToolButton:checked {{ background: {SEL_BG}; border-color: #b9d0f7; }}

/* ---- dock widgets ---- */
QDockWidget {{ font-weight: 600; color: #3a4150; titlebar-close-icon: url(none);
               titlebar-normal-icon: url(none); }}
QDockWidget::title {{ background: #edf0f3; padding: 6px 9px;
                      border-bottom: 1px solid #e0e3e8; }}

/* ---- group boxes (properties dock) ---- */
QGroupBox {{ background: {SURFACE}; border: 1px solid #e3e6ea; border-radius: 9px;
             margin-top: 15px; padding: 11px 11px 9px 11px; font-weight: 600; }}
QGroupBox::title {{ subcontrol-origin: margin; subcontrol-position: top left;
                    left: 11px; top: 2px; padding: 0 5px; color: {MUTED}; }}

/* ---- text inputs / spin / combo ---- */
QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {{
    background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: 6px;
    padding: 3px 7px; min-height: 21px;
    selection-background-color: {ACCENT}; selection-color: #ffffff; }}
QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus,
QComboBox:on {{ border: 1px solid {ACCENT}; }}
QLineEdit:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled {{
    background: #f1f2f4; color: #a3a8b0; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right;
                        width: 20px; border: none; }}
QComboBox::down-arrow {{ image: url("{chevron}"); width: 11px; height: 8px; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 3px; outline: none;
    selection-background-color: {SEL_BG}; selection-color: {ACCENT_TEXT}; }}

/* ---- push buttons ---- */
QPushButton {{ background: {SURFACE}; border: 1px solid {BORDER_STRONG};
               border-radius: 6px; padding: 4px 13px; min-height: 21px; }}
QPushButton:hover {{ background: #f6f8fb; border-color: #b7bec8; }}
QPushButton:pressed {{ background: #eceff3; }}
QPushButton:disabled {{ color: #a3a8b0; background: #f1f2f4; }}
QDialogButtonBox QPushButton {{ min-width: 76px; }}
QDialogButtonBox QPushButton:default {{ background: {ACCENT}; border-color: {ACCENT};
                                        color: #ffffff; }}
QDialogButtonBox QPushButton:default:hover {{ background: #2861d8; }}

/* ---- checkboxes (indicator drawn natively by Fusion — clean checkmark) ---- */
QCheckBox {{ spacing: 6px; }}

/* ---- list (layers) ---- */
QListWidget {{ background: {SURFACE}; border: 1px solid #dfe3e8; border-radius: 7px;
               outline: none; padding: 3px; }}
QListWidget::item {{ padding: 3px 5px; border-radius: 5px; }}
QListWidget::item:hover {{ background: #f0f3f7; }}
QListWidget::item:selected {{ background: {SEL_BG}; color: {ACCENT_TEXT}; }}

/* ---- canvas / scroll containers ---- */
QGraphicsView {{ border: 1px solid #cfd4da; }}
QScrollArea {{ border: none; background: {BG}; }}

/* ---- scrollbars ---- */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #c4cad3; border-radius: 5px; min-height: 30px;
                               margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #c4cad3; border-radius: 5px; min-width: 30px;
                                 margin: 2px; }}
QScrollBar::handle:hover {{ background: #adb5c0; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ---- status bar ---- */
QStatusBar {{ background: {BG}; border-top: 1px solid #e2e5ea; color: {MUTED}; }}
QStatusBar QLabel {{ color: {MUTED}; }}
QStatusBar::item {{ border: none; }}

/* ---- tooltips ---- */
QToolTip {{ background: #2b2f36; color: #ffffff; border: none;
            padding: 4px 8px; border-radius: 5px; }}
"""


def apply(app: QtWidgets.QApplication) -> None:
    """Switch to the Fusion base style + apply the FigForge stylesheet."""
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
