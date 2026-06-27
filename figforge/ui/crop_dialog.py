"""A small modal dialog to crop a figure by dragging a rectangle over it."""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QPointF, QRectF, Qt

_HANDLES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")
_MIN = 8.0


class _CropRect(QtWidgets.QGraphicsObject):
    def __init__(self, bounds: QRectF, rect: QRectF):
        super().__init__()
        self.bounds = bounds
        self.rect = QRectF(rect)
        self.setAcceptHoverEvents(True)
        self._mode = None
        self._start = QPointF()
        self._orig = QRectF()

    def _scale(self):
        if self.scene() and self.scene().views():
            m = self.scene().views()[0].transform().m11()
            if m > 0:
                return m
        return 1.0

    def _hs(self):
        return 7.0 / self._scale()

    def boundingRect(self):
        p = self._hs() + 2
        return self.rect.adjusted(-p, -p, p, p)

    def _centers(self):
        r = self.rect
        return {"nw": r.topLeft(), "n": QPointF(r.center().x(), r.top()),
                "ne": r.topRight(), "e": QPointF(r.right(), r.center().y()),
                "se": r.bottomRight(), "s": QPointF(r.center().x(), r.bottom()),
                "sw": r.bottomLeft(), "w": QPointF(r.left(), r.center().y())}

    def _handle_at(self, p):
        hs = self._hs()
        for name, c in self._centers().items():
            if QRectF(c.x() - hs, c.y() - hs, 2 * hs, 2 * hs).contains(p):
                return name
        return None

    def paint(self, painter, option, widget=None):
        sc = self._scale()
        pen = QtGui.QPen(QtGui.QColor(40, 120, 235), 1.5 / sc)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect)
        # rule of thirds
        thin = QtGui.QPen(QtGui.QColor(255, 255, 255, 160), 0.6 / sc)
        painter.setPen(thin)
        for i in (1, 2):
            x = self.rect.left() + self.rect.width() * i / 3
            y = self.rect.top() + self.rect.height() * i / 3
            painter.drawLine(QPointF(x, self.rect.top()), QPointF(x, self.rect.bottom()))
            painter.drawLine(QPointF(self.rect.left(), y), QPointF(self.rect.right(), y))
        hs = self._hs()
        painter.setPen(QtGui.QPen(QtGui.QColor(40, 120, 235), 1.0 / sc))
        painter.setBrush(QtGui.QColor("white"))
        for c in self._centers().values():
            painter.drawRect(QRectF(c.x() - hs / 2, c.y() - hs / 2, hs, hs))

    def hoverMoveEvent(self, event):
        h = self._handle_at(event.pos())
        cur = {"nw": Qt.CursorShape.SizeFDiagCursor, "se": Qt.CursorShape.SizeFDiagCursor,
               "ne": Qt.CursorShape.SizeBDiagCursor, "sw": Qt.CursorShape.SizeBDiagCursor,
               "n": Qt.CursorShape.SizeVerCursor, "s": Qt.CursorShape.SizeVerCursor,
               "e": Qt.CursorShape.SizeHorCursor, "w": Qt.CursorShape.SizeHorCursor}
        self.setCursor(cur.get(h, Qt.CursorShape.SizeAllCursor
                               if self.rect.contains(event.pos()) else Qt.CursorShape.ArrowCursor))
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        self._start = event.pos()
        self._orig = QRectF(self.rect)
        self._mode = self._handle_at(event.pos())
        if self._mode is None and self.rect.contains(event.pos()):
            self._mode = "move"
        event.accept()

    def mouseMoveEvent(self, event):
        if not self._mode:
            return
        d = event.pos() - self._start
        r = QRectF(self._orig)
        if self._mode == "move":
            r.translate(d)
            if r.left() < self.bounds.left():
                r.moveLeft(self.bounds.left())
            if r.top() < self.bounds.top():
                r.moveTop(self.bounds.top())
            if r.right() > self.bounds.right():
                r.moveRight(self.bounds.right())
            if r.bottom() > self.bounds.bottom():
                r.moveBottom(self.bounds.bottom())
        else:
            left, top, right, bottom = r.left(), r.top(), r.right(), r.bottom()
            if "w" in self._mode:
                left = min(max(left + d.x(), self.bounds.left()), right - _MIN)
            if "e" in self._mode:
                right = max(min(right + d.x(), self.bounds.right()), left + _MIN)
            if "n" in self._mode:
                top = min(max(top + d.y(), self.bounds.top()), bottom - _MIN)
            if "s" in self._mode:
                bottom = max(min(bottom + d.y(), self.bounds.bottom()), top + _MIN)
            r = QRectF(left, top, right - left, bottom - top)
        self.prepareGeometryChange()
        self.rect = r
        if self.scene():
            self.scene().invalidate()
        self.update()
        event.accept()

    def mouseReleaseEvent(self, event):
        self._mode = None
        event.accept()


class _CropScene(QtWidgets.QGraphicsScene):
    def __init__(self, pixmap: QtGui.QPixmap, crop_item: _CropRect):
        super().__init__()
        self.pixmap = pixmap
        self.crop_item = crop_item
        self.setBackgroundBrush(QtGui.QColor(60, 62, 66))

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        painter.drawPixmap(QPointF(0, 0), self.pixmap)

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        b = self.crop_item.bounds
        c = self.crop_item.rect
        painter.setBrush(QtGui.QColor(0, 0, 0, 120))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(QRectF(b.left(), b.top(), b.width(), c.top() - b.top()))
        painter.drawRect(QRectF(b.left(), c.bottom(), b.width(), b.bottom() - c.bottom()))
        painter.drawRect(QRectF(b.left(), c.top(), c.left() - b.left(), c.height()))
        painter.drawRect(QRectF(c.right(), c.top(), b.right() - c.right(), c.height()))


class CropDialog(QtWidgets.QDialog):
    def __init__(self, parent, pixmap: QtGui.QPixmap, crop):
        super().__init__(parent)
        self.setWindowTitle("裁剪图片")
        self.resize(620, 560)
        pw, ph = pixmap.width(), pixmap.height()
        self.bounds = QRectF(0, 0, pw, ph)
        cx0, cy0, cx1, cy1 = crop
        rect = QRectF(cx0 * pw, cy0 * ph, (cx1 - cx0) * pw, (cy1 - cy0) * ph)
        self.crop_item = _CropRect(self.bounds, rect)
        self.scene = _CropScene(pixmap, self.crop_item)
        self.scene.setSceneRect(self.bounds)
        self.scene.addItem(self.crop_item)

        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)

        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(QtWidgets.QLabel("拖动方框选择保留区域："))
        lay.addWidget(self.view, 1)
        bb = QtWidgets.QDialogButtonBox()
        reset = bb.addButton("重置", QtWidgets.QDialogButtonBox.ButtonRole.ResetRole)
        bb.addButton(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        bb.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        reset.clicked.connect(self._reset)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def showEvent(self, event):
        super().showEvent(event)
        self.view.fitInView(self.bounds, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.view.fitInView(self.bounds, Qt.AspectRatioMode.KeepAspectRatio)

    def _reset(self):
        self.crop_item.prepareGeometryChange()
        self.crop_item.rect = QRectF(self.bounds)
        self.scene.invalidate()
        self.crop_item.update()

    def get_crop(self):
        r = self.crop_item.rect
        bw, bh = self.bounds.width(), self.bounds.height()
        return (max(0.0, r.left() / bw), max(0.0, r.top() / bh),
                min(1.0, r.right() / bw), min(1.0, r.bottom() / bh))
