"""The canvas view: zoom, pan, drag-and-drop and cursor reporting."""
from __future__ import annotations

import os

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, Signal

from ..fileio.importers import ALL_EXTS


class CanvasView(QtWidgets.QGraphicsView):
    zoomChanged = Signal(float)          # percent
    cursorMoved = Signal(float, float)   # scene x, y (points)
    filesDropped = Signal(list, QtCore.QPointF)   # paths, scene position

    def __init__(self, scene):
        super().__init__(scene)
        self.setRenderHints(
            QtGui.QPainter.RenderHint.Antialiasing
            | QtGui.QPainter.RenderHint.SmoothPixmapTransform
            | QtGui.QPainter.RenderHint.TextAntialiasing
        )
        self.setDragMode(QtWidgets.QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QtWidgets.QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self._zoom = 1.0
        self._panning = False
        self._pan_start = QtCore.QPoint()

    # ---- drag & drop import ---------------------------------------------
    @staticmethod
    def _dropped_paths(event) -> list[str]:
        md = event.mimeData()
        if not md.hasUrls():
            return []
        out = []
        for u in md.urls():
            if u.isLocalFile():
                p = u.toLocalFile()
                if os.path.splitext(p)[1].lower() in ALL_EXTS:
                    out.append(p)
        return out

    def dragEnterEvent(self, event):
        if self._dropped_paths(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._dropped_paths(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        paths = self._dropped_paths(event)
        if paths:
            pos = self.mapToScene(event.position().toPoint())
            self.filesDropped.emit(paths, pos)
            event.acceptProposedAction()
        else:
            event.ignore()

    # ---- zoom ------------------------------------------------------------
    def _apply_zoom(self, factor: float):
        new = self._zoom * factor
        if new < 0.05 or new > 30.0:
            return
        self._zoom = new
        self.scale(factor, factor)
        self.zoomChanged.emit(self._zoom * 100.0)

    def zoom_in(self):
        self._apply_zoom(1.25)

    def zoom_out(self):
        self._apply_zoom(1 / 1.25)

    def reset_zoom(self):
        self.resetTransform()
        self._zoom = 1.0
        self.zoomChanged.emit(100.0)

    def fit_page(self):
        scene = self.scene()
        if scene is None:
            return
        self.fitInView(scene.page_rect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = self.transform().m11()
        self.zoomChanged.emit(self._zoom * 100.0)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self._apply_zoom(1.2 if event.angleDelta().y() > 0 else 1 / 1.2)
            event.accept()
        else:
            super().wheelEvent(event)

    # ---- pan (space-drag or middle button) ------------------------------
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.ScrollHandDrag)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.setDragMode(QtWidgets.QGraphicsView.DragMode.RubberBandDrag)
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            h = self.horizontalScrollBar()
            v = self.verticalScrollBar()
            h.setValue(h.value() - delta.x())
            v.setValue(v.value() - delta.y())
            event.accept()
            return
        sp = self.mapToScene(event.position().toPoint())
        self.cursorMoved.emit(sp.x(), sp.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
