"""Application bootstrap."""
from __future__ import annotations

import os
import sys

from PySide6 import QtGui, QtWidgets

from . import constants, i18n
from .i18n import tr
from .main_window import MainWindow


def _icon_path() -> str:
    return os.path.join(os.path.dirname(__file__), "resources", "icon.ico")


def main():
    # Windows: show FigForge's icon in the taskbar (not the Python icon).
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "FigForge.FigForge.1")
        except Exception:
            pass

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(constants.APP_NAME)
    app.setOrganizationName(constants.ORG_NAME)
    i18n.set_language(i18n.load_saved())          # default English; persists choice
    app.setApplicationDisplayName(tr("FigForge — Academic Figure Layout"))
    icon = _icon_path()
    if os.path.exists(icon):
        app.setWindowIcon(QtGui.QIcon(icon))

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
