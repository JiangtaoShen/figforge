"""Undo/redo commands (Qt's QUndoStack lives in QtGui on Qt6)."""
from __future__ import annotations

from PySide6 import QtGui

from .i18n import tr


class GeometryCommand(QtGui.QUndoCommand):
    def __init__(self, item, old, new, text=None):
        super().__init__(text if text is not None else tr("Move / Resize"))
        self.item, self.old, self.new = item, old, new

    def redo(self):
        self.item.set_geometry(*self.new)

    def undo(self):
        self.item.set_geometry(*self.old)


class AddItemCommand(QtGui.QUndoCommand):
    def __init__(self, scene, item, text=None):
        super().__init__(text if text is not None else tr("Add object"))
        self.scene, self.item = scene, item

    def redo(self):
        self.scene.register_item(self.item)

    def undo(self):
        self.scene.unregister_item(self.item)


class DeleteItemsCommand(QtGui.QUndoCommand):
    def __init__(self, scene, items, text=None):
        super().__init__(text if text is not None else tr("Delete objects"))
        self.scene, self.items = scene, list(items)

    def redo(self):
        for it in self.items:
            self.scene.unregister_item(it)

    def undo(self):
        for it in self.items:
            self.scene.register_item(it)


class FuncCommand(QtGui.QUndoCommand):
    """Generic command driven by two callables (apply-new / apply-old)."""

    def __init__(self, text, do_fn, undo_fn):
        super().__init__(text)
        self._do, self._undo = do_fn, undo_fn

    def redo(self):
        self._do()

    def undo(self):
        self._undo()
