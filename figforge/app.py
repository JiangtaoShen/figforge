"""Application bootstrap."""
from __future__ import annotations

import os
import sys
import time
import traceback

from PySide6 import QtCore, QtGui, QtWidgets

from . import constants, i18n
from .i18n import tr
from .main_window import MainWindow


def _icon_path() -> str:
    return os.path.join(os.path.dirname(__file__), "resources", "icon.ico")


def _project_arg(argv: list[str]) -> str | None:
    """First existing .ffp path on the command line (file association)."""
    for a in argv[1:]:
        if a.lower().endswith(constants.PROJECT_EXT) and os.path.isfile(a):
            return a
    return None


def install_excepthook(win: MainWindow) -> None:
    """Log uncaught exceptions, rescue-autosave the work, tell the user —
    instead of dying silently."""
    state = {"showing": False}

    def hook(tp, val, tb):
        logfile = ""
        try:
            logfile = os.path.join(win._autosave_dir(), "error.log")
            with open(logfile, "a", encoding="utf-8") as fh:
                fh.write("\n" + "=" * 60 + "\n"
                         + time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
                traceback.print_exception(tp, val, tb, file=fh)
        except Exception:
            pass
        try:
            win.rescue_autosave()
        except Exception:
            pass
        sys.__excepthook__(tp, val, tb)          # still print to console
        if not state["showing"]:
            state["showing"] = True
            try:
                QtWidgets.QMessageBox.critical(
                    win, tr("Internal Error"),
                    tr("An internal error occurred. Your work has been "
                       "auto-saved.\nDetails were written to:\n{0}"
                       ).format(logfile))
            finally:
                state["showing"] = False

    sys.excepthook = hook


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
    install_excepthook(win)
    proj = _project_arg(sys.argv)
    if proj:                       # launched by double-clicking a .ffp file
        win._skip_restore = True   # don't fight the explicit open
        QtCore.QTimer.singleShot(0, lambda: win._load_project_path(proj))
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
