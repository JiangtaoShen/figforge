"""Layers dock — the object list with selection sync and z-order controls."""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from ..canvas.items import FigureItem


class LayersPanel(QtWidgets.QWidget):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self._syncing = False
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        self.list = QtWidgets.QListWidget()
        self.list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.itemSelectionChanged.connect(self._on_list_selection)
        lay.addWidget(self.list, 1)

        bar = QtWidgets.QHBoxLayout()
        for text, tip, slot in (
            ("⤒", "置于顶层", lambda: self.main.change_z("front")),
            ("↑", "上移一层", lambda: self.main.change_z("up")),
            ("↓", "下移一层", lambda: self.main.change_z("down")),
            ("⤓", "置于底层", lambda: self.main.change_z("back")),
            ("🗑", "删除", self.main.delete_selected),
        ):
            b = QtWidgets.QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            bar.addWidget(b)
        bar.addStretch(1)
        lay.addLayout(bar)

    def refresh(self):
        self._syncing = True
        self.list.clear()
        for it in reversed(self.main.scene.iter_items()):   # top layer first
            label = ("🖼 " if isinstance(it, FigureItem) else "T ") + it.name()
            row = QtWidgets.QListWidgetItem(label)
            row.setData(QtCore.Qt.ItemDataRole.UserRole, it)
            row.setSelected(it.isSelected())
            self.list.addItem(row)
        self._syncing = False

    def sync_from_scene(self):
        if self._syncing:
            return
        self._syncing = True
        sel = set(self.main.scene.selectedItems())
        for i in range(self.list.count()):
            row = self.list.item(i)
            row.setSelected(row.data(QtCore.Qt.ItemDataRole.UserRole) in sel)
        self._syncing = False

    def _on_list_selection(self):
        if self._syncing:
            return
        self._syncing = True
        chosen = {row.data(QtCore.Qt.ItemDataRole.UserRole)
                  for row in self.list.selectedItems()}
        for it in self.main.scene.iter_items():
            it.setSelected(it in chosen)
        self._syncing = False
