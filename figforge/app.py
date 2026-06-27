"""Application bootstrap."""
from __future__ import annotations

import sys

from PySide6 import QtWidgets

from . import constants
from .main_window import MainWindow


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(constants.APP_NAME)
    app.setOrganizationName(constants.ORG_NAME)
    app.setApplicationDisplayName(constants.APP_TITLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
