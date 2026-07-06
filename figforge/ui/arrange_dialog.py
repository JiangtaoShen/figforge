"""Arrange-in-grid dialog: rows / columns / spacing / uniform sizing."""
from __future__ import annotations

import math

from PySide6 import QtWidgets

from .. import constants
from ..i18n import tr


class ArrangeGridDialog(QtWidgets.QDialog):
    """Ask for the grid shape used by MainWindow.arrange_grid()."""

    def __init__(self, parent, count: int):
        super().__init__(parent)
        self.setWindowTitle(tr("Arrange in Grid"))
        self._count = count

        cols = max(1, math.ceil(math.sqrt(count)))
        rows = max(1, math.ceil(count / cols))

        form = QtWidgets.QFormLayout(self)
        self.spin_rows = QtWidgets.QSpinBox()
        self.spin_rows.setRange(1, count)
        self.spin_rows.setValue(rows)
        self.spin_cols = QtWidgets.QSpinBox()
        self.spin_cols.setRange(1, count)
        self.spin_cols.setValue(cols)
        form.addRow(tr("Rows"), self.spin_rows)
        form.addRow(tr("Columns"), self.spin_cols)

        def _mm_spin(val):
            s = QtWidgets.QDoubleSpinBox()
            s.setRange(0.0, 200.0)
            s.setDecimals(1)
            s.setSingleStep(0.5)
            s.setSuffix(" mm")
            s.setValue(val)
            return s

        self.spin_hgap = _mm_spin(2.0)
        self.spin_vgap = _mm_spin(2.0)
        form.addRow(tr("Horizontal gap"), self.spin_hgap)
        form.addRow(tr("Vertical gap"), self.spin_vgap)

        self.chk_same = QtWidgets.QCheckBox(
            tr("Make all panels the same size as the first panel"))
        form.addRow("", self.chk_same)

        hint = QtWidgets.QLabel(
            tr("Panels are placed row by row in their current order "
               "(top-left first)."))
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666; font-size:11px;")
        form.addRow(hint)

        # keep rows x cols large enough for every panel
        self.spin_rows.valueChanged.connect(lambda *_: self._fix("rows"))
        self.spin_cols.valueChanged.connect(lambda *_: self._fix("cols"))

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _fix(self, changed: str):
        rows, cols = self.spin_rows.value(), self.spin_cols.value()
        if rows * cols >= self._count:
            return
        if changed == "rows":
            other, spin = rows, self.spin_cols
        else:
            other, spin = cols, self.spin_rows
        spin.blockSignals(True)
        spin.setValue(math.ceil(self._count / other))
        spin.blockSignals(False)

    def values(self):
        """(rows, cols, hgap_pt, vgap_pt, same_size)"""
        rows, cols = self.spin_rows.value(), self.spin_cols.value()
        if rows * cols < self._count:
            rows = math.ceil(self._count / cols)
        return (rows, cols,
                constants.mm_to_pt(self.spin_hgap.value()),
                constants.mm_to_pt(self.spin_vgap.value()),
                self.chk_same.isChecked())
