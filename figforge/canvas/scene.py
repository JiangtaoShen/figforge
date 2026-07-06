"""The page scene: draws the page + grid, handles snapping and undo hooks."""
from __future__ import annotations

from contextlib import contextmanager

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QPointF, QRectF, Qt, Signal

from .. import constants
from ..commands import FuncCommand, GeometryCommand
from ..i18n import tr
from .items import BaseItem, CanvasItem

_DESK = QtGui.QColor(74, 76, 82)
_PAGE = QtGui.QColor("white")
_PAGE_BORDER = QtGui.QColor(150, 150, 150)
_GRID = QtGui.QColor(220, 224, 230)
_GUIDE = QtGui.QColor(255, 40, 170)


class PageScene(QtWidgets.QGraphicsScene):
    sceneEdited = Signal()
    ctrlDuplicate = Signal()        # Ctrl-drag on an item requests a copy

    def __init__(self, page=constants.DEFAULT_PAGE, orientation=constants.PORTRAIT):
        super().__init__()
        self.undo_stack: QtGui.QUndoStack | None = None
        self.page_name = page
        self.orientation = orientation
        self.page_w, self.page_h = constants.page_rect_pt(page, orientation)
        self.grid_mm = constants.DEFAULT_GRID_MM
        self.grid_visible = False
        self.snap_enabled = True
        self.snap_to_grid = False
        self._guides: list[tuple[str, float]] = []
        self._z_counter = 1.0
        self.setBackgroundBrush(_DESK)
        self._update_scene_rect()

    # ---- page ------------------------------------------------------------
    def set_page(self, page: str, orientation: str):
        self.page_name, self.orientation = page, orientation
        self.page_w, self.page_h = constants.page_rect_pt(page, orientation)
        self._update_scene_rect()
        self.update()
        self.sceneEdited.emit()

    def _update_scene_rect(self):
        m = max(self.page_w, self.page_h) * 0.35
        self.setSceneRect(-m, -m, self.page_w + 2 * m, self.page_h + 2 * m)

    def page_rect(self) -> QRectF:
        return QRectF(0, 0, self.page_w, self.page_h)

    def content_rect(self) -> QRectF | None:
        """Union of all item content bboxes, clipped to the page (or None)."""
        rect: QRectF | None = None
        for it in self.iter_items():
            r = it.content_scene_rect()
            rect = QRectF(r) if rect is None else rect.united(r)
        if rect is None:
            return None
        rect = rect.intersected(self.page_rect())
        if rect.isEmpty():
            return None
        return rect

    # ---- item registry / z-order ----------------------------------------
    def next_z(self) -> float:
        self._z_counter += 1.0
        return self._z_counter

    def register_item(self, item):
        if item.scene() is not self:
            self.addItem(item)
        self.sceneEdited.emit()

    def unregister_item(self, item):
        if item.scene() is self:
            self.removeItem(item)
        self.sceneEdited.emit()

    def iter_items(self) -> list[CanvasItem]:
        items = [it for it in self.items() if isinstance(it, CanvasItem)]
        items.sort(key=lambda it: it.zValue())
        return items

    def find_item(self, uid):
        for it in self.items():
            if isinstance(it, CanvasItem) and getattr(it, "uid", None) == uid:
                return it
        return None

    def push_geometry_undo(self, item, old, new):
        if self.undo_stack is not None:
            self.undo_stack.push(GeometryCommand(item, old, new))

    def push_state_undo(self, item, old, new):
        """Undo for move / resize / rotate (full 5-tuple state)."""
        if self.undo_stack is not None:
            self.undo_stack.push(FuncCommand(
                tr("Move / Resize / Rotate"),
                lambda: item.set_state(new),
                lambda: item.set_state(old)))

    # ---- grid / snap settings -------------------------------------------
    def set_grid(self, mm: float | None = None, visible: bool | None = None):
        if mm is not None:
            self.grid_mm = max(0.5, mm)
        if visible is not None:
            self.grid_visible = visible
        self.update()

    # ---- snapping --------------------------------------------------------
    @contextmanager
    def no_snap(self):
        """Suspend smart/grid snapping while applying programmatic geometry
        (exact coordinates, grid arrange, undo/redo) so it isn't hijacked."""
        se, sg = self.snap_enabled, self.snap_to_grid
        self.snap_enabled = self.snap_to_grid = False
        try:
            yield
        finally:
            self.snap_enabled, self.snap_to_grid = se, sg

    def _view_scale(self) -> float:
        if self.views():
            m = self.views()[0].transform().m11()
            if m > 0:
                return m
        return 1.0

    def snap_position(self, item, proposed: QPointF) -> QPointF:
        if not self.snap_enabled and not self.snap_to_grid:
            return proposed
        w, h = item.size()
        left, top = proposed.x(), proposed.y()
        thr = constants.SNAP_THRESHOLD_PX / self._view_scale()
        guides: list[tuple[str, float]] = []
        dx = dy = 0.0

        if self.snap_enabled:
            xs_targets, ys_targets = self._snap_targets(item)
            cand_x = {"l": left, "c": left + w / 2, "r": left + w}
            cand_y = {"t": top, "m": top + h / 2, "b": top + h}
            best = None
            for cv in cand_x.values():
                for t in xs_targets:
                    diff = t - cv
                    if abs(diff) <= thr and (best is None or abs(diff) < abs(best[0])):
                        best = (diff, t)
            if best:
                dx = best[0]
                guides.append(("v", best[1]))
            best = None
            for cv in cand_y.values():
                for t in ys_targets:
                    diff = t - cv
                    if abs(diff) <= thr and (best is None or abs(diff) < abs(best[0])):
                        best = (diff, t)
            if best:
                dy = best[0]
                guides.append(("h", best[1]))

        if self.snap_to_grid:
            step = constants.mm_to_pt(self.grid_mm)
            if dx == 0.0:
                dx = round(left / step) * step - left
            if dy == 0.0:
                dy = round(top / step) * step - top

        self._set_guides(guides)
        return QPointF(left + dx, top + dy)

    def _snap_targets(self, moving) -> tuple[list[float], list[float]]:
        xs = [0.0, self.page_w / 2, self.page_w]
        ys = [0.0, self.page_h / 2, self.page_h]
        for it in self.items():
            if it is moving or not isinstance(it, BaseItem):
                continue
            r = it.scene_rect()
            xs += [r.left(), r.center().x(), r.right()]
            ys += [r.top(), r.center().y(), r.bottom()]
        return xs, ys

    def _set_guides(self, guides):
        if guides != self._guides:
            self._guides = guides
            self.invalidate(self.sceneRect(),
                            QtWidgets.QGraphicsScene.SceneLayer.ForegroundLayer)

    def clear_guides(self):
        self._set_guides([])

    # ---- painting --------------------------------------------------------
    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        page = self.page_rect()
        # drop shadow
        painter.fillRect(page.adjusted(4, 4, 4, 4), QtGui.QColor(0, 0, 0, 60))
        painter.fillRect(page, _PAGE)
        if self.grid_visible:
            step = constants.mm_to_pt(self.grid_mm)
            pen = QtGui.QPen(_GRID, 0)
            painter.setPen(pen)
            x = step
            while x < self.page_w:
                painter.drawLine(QPointF(x, 0), QPointF(x, self.page_h))
                x += step
            y = step
            while y < self.page_h:
                painter.drawLine(QPointF(0, y), QPointF(self.page_w, y))
                y += step
        painter.setPen(QtGui.QPen(_PAGE_BORDER, 0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(page)

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        if not self._guides:
            return
        pen = QtGui.QPen(_GUIDE, 0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        for kind, v in self._guides:
            if kind == "v":
                painter.drawLine(QPointF(v, 0), QPointF(v, self.page_h))
            else:
                painter.drawLine(QPointF(0, v), QPointF(self.page_w, v))
