"""Canvas items: resizable/rotatable figure panels and editable text labels.

Geometry convention
-------------------
``pos()`` is the item's top-left corner (of the *unrotated* frame) in scene
coordinates (== PDF points).  Local content occupies ``QRectF(0,0,w,h)``.
Rotation is applied about the frame centre (transform origin == centre).
Scene units map 1:1 onto PyMuPDF page coordinates.

Export keeps everything vector / full-resolution:
* plain raster (no rotation/crop)  -> ``Page.insert_image`` (full res)
* rotated / cropped / vector source -> ``Page.show_pdf_page`` (rotate + clip),
  rasters first wrapped in a 1-page PDF so the image stays embedded full-res.
"""
from __future__ import annotations

import math
import uuid

import fitz
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QPointF, QRectF, Qt, Signal

from .. import constants, fonts
from ..fileio.importers import LoadedSource, load_source

_HANDLES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")
_CURSORS = {
    "nw": Qt.CursorShape.SizeFDiagCursor, "se": Qt.CursorShape.SizeFDiagCursor,
    "ne": Qt.CursorShape.SizeBDiagCursor, "sw": Qt.CursorShape.SizeBDiagCursor,
    "n": Qt.CursorShape.SizeVerCursor, "s": Qt.CursorShape.SizeVerCursor,
    "e": Qt.CursorShape.SizeHorCursor, "w": Qt.CursorShape.SizeHorCursor,
}
# opposite point that stays pinned while dragging a given handle
_OPPOSITE = {
    "nw": lambda w, h: (w, h), "ne": lambda w, h: (0, h),
    "se": lambda w, h: (0, 0), "sw": lambda w, h: (w, 0),
    "e": lambda w, h: (0, h / 2), "w": lambda w, h: (w, h / 2),
    "s": lambda w, h: (w / 2, 0), "n": lambda w, h: (w / 2, h),
}
_SIGN = {"nw": (-1, -1), "ne": (1, -1), "se": (1, 1), "sw": (-1, 1),
         "e": (1, 0), "w": (-1, 0), "s": (0, 1), "n": (0, -1)}

_PAD = 24.0
_ROT_PAD = 74.0
_ROT_OFFSET_PX = 22.0
_SEL_COLOR = QtGui.QColor(40, 120, 235)

# Direction PyMuPDF's show_pdf_page rotates relative to Qt's setRotation.
# (verified against Qt rendering in the test-suite)
EXPORT_ROT_SIGN = -1


def _rgb(c: QtGui.QColor):
    return (c.red() / 255, c.green() / 255, c.blue() / 255)


def _place(page, src, x, y, w, h, angle, clip=None):
    """Show single-page PDF `src` at (x,y,w,h) on `page`, rotated about centre.

    ``clip`` optionally restricts to a sub-rect of the source page (used by
    text boxes whose text canvas is taller than the visible frame)."""
    if abs(angle) < 1e-6:
        page.show_pdf_page(fitz.Rect(x, y, x + w, y + h), src, 0,
                           keep_proportion=False, clip=clip)
        return
    ang = round(angle)
    th = math.radians(ang)
    c, s = abs(math.cos(th)), abs(math.sin(th))
    ew, eh = w * c + h * s, w * s + h * c          # rotated bounding box
    cx, cy = x + w / 2, y + h / 2
    page.show_pdf_page(fitz.Rect(cx - ew / 2, cy - eh / 2, cx + ew / 2, cy + eh / 2),
                       src, 0, rotate=int(EXPORT_ROT_SIGN * ang) % 360, clip=clip)


class _TextEditorItem(QtWidgets.QGraphicsTextItem):
    """Transient in-place text editor (child of the edited item).

    Shows a real caret on the canvas; commits on focus-out, Escape or
    Ctrl+Enter. Created/destroyed by InlineTextEdit.start/finish_inline_edit.
    """

    def __init__(self, host):
        super().__init__(host)
        self._host = host

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        if self._host is not None:            # host may be torn down already
            self._host.finish_inline_edit()

    def keyPressEvent(self, event):
        if self._host is not None and (
                event.key() == Qt.Key.Key_Escape or (
                    event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                    and event.modifiers() & Qt.KeyboardModifier.ControlModifier)):
            event.accept()
            self._host.finish_inline_edit()
            return
        super().keyPressEvent(event)


class InlineTextEdit:
    """Mixin for text items: in-place editing with a caret on the canvas."""

    EDIT_WRAP = True          # wrap to the frame width (text boxes)

    def _edit_pads(self) -> tuple[float, float, float]:
        """(left, top, right) insets for the in-place editor."""
        p = float(getattr(self, "PAD", 0.0))
        return (p, p, p)

    def _sync_editor_width(self):
        ed = getattr(self, "_editor", None)
        if ed is not None and self.EDIT_WRAP:
            pl, _, pr = self._edit_pads()
            ed.setTextWidth(max(10.0, self._w - pl - pr))

    def start_inline_edit(self, select_all=False):
        if getattr(self, "_editor", None) is not None:
            return
        ed = _TextEditorItem(self)
        ed.setFont(self.font())
        ed.setDefaultTextColor(QtGui.QColor(self.color))
        doc = ed.document()
        doc.setDocumentMargin(0.0)
        opt = doc.defaultTextOption()
        opt.setAlignment({"left": Qt.AlignmentFlag.AlignLeft,
                          "center": Qt.AlignmentFlag.AlignHCenter,
                          "right": Qt.AlignmentFlag.AlignRight}[self.align])
        opt.setWrapMode(QtGui.QTextOption.WrapMode.WordWrap if self.EDIT_WRAP
                        else QtGui.QTextOption.WrapMode.NoWrap)
        doc.setDefaultTextOption(opt)
        ed.setPlainText(self.text)
        pl, pt_, pr = self._edit_pads()
        ed.setPos(pl, pt_)
        if self.EDIT_WRAP:
            ed.setTextWidth(max(10.0, self._w - pl - pr))
            self.geometryChanged.connect(self._sync_editor_width)
        ed.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        cur = ed.textCursor()
        if select_all:
            cur.select(QtGui.QTextCursor.SelectionType.Document)
        else:
            cur.movePosition(QtGui.QTextCursor.MoveOperation.End)
        ed.setTextCursor(cur)
        self._editor = ed
        self.update()             # host stops painting its own text
        ed.setFocus(Qt.FocusReason.OtherFocusReason)

    def finish_inline_edit(self, commit: bool = True):
        """End editing. ``commit=False`` discards the in-flight text — used
        when the host item is being removed from the scene, where committing
        would mutate the scene / undo stack re-entrantly (crashes on macOS)."""
        ed = getattr(self, "_editor", None)
        if ed is None:
            return
        self._editor = None
        if self.EDIT_WRAP:
            try:
                self.geometryChanged.disconnect(self._sync_editor_width)
            except (RuntimeError, TypeError):
                pass
        new = ed.toPlainText()
        sc = self.scene()
        # Tear the editor down safely. deleteLater() keeps it alive until the
        # event loop drains, during which the host may already be destroyed
        # (e.g. scene.clear() deletes the host right after this returns), so
        # sever the back-reference and stop input first — otherwise a pending
        # macOS focus/IME callback dereferences a dead host (use-after-free).
        ed._host = None
        ed.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        ed.clearFocus()
        ed.setParentItem(None)
        if ed.scene() is not None:
            ed.scene().removeItem(ed)
        ed.deleteLater()
        old = self.text
        if commit and new != old:
            if sc is not None and getattr(sc, "push_text_undo", None) is not None:
                sc.push_text_undo(self, old, new)
            else:
                self.set_text(new)
        self.update()

    def mouseDoubleClickEvent(self, event):
        self.start_inline_edit()
        event.accept()


class CanvasItem(QtWidgets.QGraphicsObject):
    """Base for every selectable page object (rectangular items and lines)."""

    geometryChanged = Signal()

    def __init__(self):
        super().__init__()
        self._name = "Item"
        self.uid = uuid.uuid4().hex
        self.locked = False
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._ctrl_drag = False        # Ctrl-drag duplicates
        self._ctrl_done = False
        self._sel_at_press = False     # for Ctrl-click deselect

    def name(self):
        return self._name

    def set_name(self, name):
        self._name = name

    def set_locked(self, on: bool):
        """Locked items cannot be selected or moved on the canvas."""
        self.locked = bool(on)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable,
                     not self.locked)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable,
                     not self.locked)
        if self.locked:
            self.setSelected(False)
        self.update()
        sc = self.scene()
        if sc is not None and hasattr(sc, "sceneEdited"):
            sc.sceneEdited.emit()

    def content_scene_rect(self) -> QRectF:
        """Scene-space bbox of the *content* only (no handle padding)."""
        return self.sceneBoundingRect()


class BaseItem(CanvasItem):
    """Common selection / move / resize / rotate behaviour for rect items."""

    def __init__(self, resizable: bool = True):
        super().__init__()
        self._w = 100.0
        self._h = 100.0
        self.aspect_locked = True
        self.resizable = resizable
        self._resizing: str | None = None
        self._rotating = False
        self._resize_w0 = self._resize_h0 = 0.0
        self._pinned_scene = QPointF()
        self._state_at_press: tuple | None = None

    # ---- geometry --------------------------------------------------------
    def size(self):
        return self._w, self._h

    def scene_rect(self) -> QRectF:
        return QRectF(self.pos().x(), self.pos().y(), self._w, self._h)

    def content_scene_rect(self) -> QRectF:
        # maps the unrotated content frame; correct for rotated items too
        return self.mapToScene(QRectF(0, 0, self._w, self._h)).boundingRect()

    def get_geometry(self):
        return (self.pos().x(), self.pos().y(), self._w, self._h)

    def get_state(self):
        return (self.pos().x(), self.pos().y(), self._w, self._h, self.rotation())

    def set_state(self, s):
        x, y, w, h, rot = s
        w = max(w, constants.MIN_ITEM_PT)
        h = max(h, constants.MIN_ITEM_PT)
        self.prepareGeometryChange()
        self._w, self._h = w, h
        self.setTransformOriginPoint(w / 2, h / 2)
        self.setRotation(rot)
        self.setPos(x, y)
        self.update()
        self.geometryChanged.emit()

    def set_geometry(self, x, y, w, h):
        self.set_state((x, y, w, h, self.rotation()))

    def set_rotation_deg(self, deg: float):
        self.setTransformOriginPoint(self._w / 2, self._h / 2)
        self.setRotation(deg)
        self.geometryChanged.emit()

    def name(self):
        return self._name

    def set_name(self, name):
        self._name = name

    def boundingRect(self) -> QRectF:
        top = _PAD + (_ROT_PAD if self.resizable else 0)
        return QRectF(-_PAD, -top, self._w + 2 * _PAD, self._h + top + _PAD)

    def shape(self) -> QtGui.QPainterPath:
        path = QtGui.QPainterPath()
        path.addRect(QRectF(0, 0, self._w, self._h))
        if self.isSelected() and self.resizable:
            hs = self._handle_size()
            for cx, cy in self._handle_centers().values():
                path.addRect(QRectF(cx - hs / 2, cy - hs / 2, hs, hs))
            rc = self._rot_center()
            path.addEllipse(rc, hs, hs)
        return path

    # ---- screen-constant handles ----------------------------------------
    def _eff_scale(self) -> float:
        sc = self.scene()
        if sc and sc.views():
            m = sc.views()[0].transform().m11()
            if m > 0:
                return max(0.4, min(m, 4.0))
        return 1.0

    def _handle_size(self):
        return constants.HANDLE_PX / self._eff_scale()

    def _handle_centers(self):
        w, h = self._w, self._h
        return {"nw": (0, 0), "n": (w / 2, 0), "ne": (w, 0), "e": (w, h / 2),
                "se": (w, h), "s": (w / 2, h), "sw": (0, h), "w": (0, h / 2)}

    def anchor_nodes(self) -> dict:
        """Scene positions of the 8 edge/corner nodes plus the centre."""
        nodes = dict(self._handle_centers())
        nodes["c"] = (self._w / 2, self._h / 2)
        return {k: self.mapToScene(QPointF(x, y)) for k, (x, y) in nodes.items()}

    def _rot_center(self) -> QPointF:
        return QPointF(self._w / 2, -_ROT_OFFSET_PX / self._eff_scale())

    def _handle_at(self, p):
        hs = self._handle_size()
        for name, (cx, cy) in self._handle_centers().items():
            if QRectF(cx - hs / 2, cy - hs / 2, hs, hs).contains(p):
                return name
        return None

    def _rot_handle_at(self, p):
        rc = self._rot_center()
        hs = self._handle_size()
        return QRectF(rc.x() - hs, rc.y() - hs, 2 * hs, 2 * hs).contains(p)

    # ---- painting --------------------------------------------------------
    def paint(self, painter, option, widget=None):
        self.paint_content(painter)
        if not self.isSelected():
            return
        scale = self._eff_scale()
        pen = QtGui.QPen(_SEL_COLOR, 1.0 / scale)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(0, 0, self._w, self._h))
        if not self.resizable:
            return
        hs = self._handle_size()
        rc = self._rot_center()
        painter.drawLine(QPointF(self._w / 2, 0), rc)
        painter.setBrush(QtGui.QColor("white"))
        painter.drawEllipse(rc, hs / 2, hs / 2)
        for cx, cy in self._handle_centers().values():
            painter.drawRect(QRectF(cx - hs / 2, cy - hs / 2, hs, hs))

    def paint_content(self, painter):
        pass

    # ---- mouse -----------------------------------------------------------
    def mousePressEvent(self, event):
        self._state_at_press = self.get_state()
        self._sel_at_press = self.isSelected()
        if (self.resizable and self.isSelected()
                and event.button() == Qt.MouseButton.LeftButton):
            if self._rot_handle_at(event.pos()):
                self._rotating = True
                self.setTransformOriginPoint(self._w / 2, self._h / 2)
                event.accept()
                return
            handle = self._handle_at(event.pos())
            if handle:
                self._resizing = handle
                self._resize_w0, self._resize_h0 = self._w, self._h
                fx, fy = _OPPOSITE[handle](self._w, self._h)
                self._pinned_scene = self.mapToScene(QPointF(fx, fy))
                event.accept()
                return
        self._ctrl_drag = (bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                           and event.button() == Qt.MouseButton.LeftButton)
        self._ctrl_done = False
        super().mousePressEvent(event)
        if self._ctrl_drag:
            self.setSelected(True)

    def mouseMoveEvent(self, event):
        if self._rotating:
            self._do_rotate(event.scenePos(), event.modifiers())
            event.accept()
            return
        if self._resizing:
            self._do_resize(event.scenePos(), event.modifiers())
            event.accept()
            return
        if self._ctrl_drag and not self._ctrl_done:
            self._ctrl_done = True
            sc = self.scene()
            if sc and hasattr(sc, "ctrlDuplicate"):
                sc.ctrlDuplicate.emit()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        active = self._resizing or self._rotating
        ctrl_click = self._ctrl_drag and not self._ctrl_done
        self._resizing = None
        self._rotating = False
        self._ctrl_drag = False
        sc = self.scene()
        if sc and hasattr(sc, "clear_guides"):
            sc.clear_guides()
        if not active:
            super().mouseReleaseEvent(event)
        else:
            event.accept()
        if self._state_at_press is not None:
            new = self.get_state()
            if new != self._state_at_press and sc and hasattr(sc, "push_state_undo"):
                sc.push_state_undo(self, self._state_at_press, new)
            elif ctrl_click and new == self._state_at_press and self._sel_at_press:
                self.setSelected(False)      # Ctrl-click toggles selection off
        self._state_at_press = None

    def hoverMoveEvent(self, event):
        if self.isSelected() and self.resizable:
            if self._rot_handle_at(event.pos()):
                self.setCursor(Qt.CursorShape.PointingHandCursor)
            else:
                h = self._handle_at(event.pos())
                self.setCursor(_CURSORS[h] if h else Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverMoveEvent(event)

    def _do_rotate(self, scene_pos, modifiers):
        c = self.mapToScene(QPointF(self._w / 2, self._h / 2))
        ang = math.degrees(math.atan2(scene_pos.y() - c.y(),
                                      scene_pos.x() - c.x())) + 90.0
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            ang = round(ang / 15.0) * 15.0
        else:
            for k in (0, 90, 180, 270, 360):
                if abs(((ang - k + 180) % 360) - 180) < 2.0:
                    ang = k
                    break
        self.setRotation(ang % 360)
        self.geometryChanged.emit()

    def _do_resize(self, scene_pos, modifiers):
        handle = self._resizing
        w0, h0 = self._resize_w0, self._resize_h0
        lc = self.mapFromScene(scene_pos)
        fx, fy = _OPPOSITE[handle](self._w, self._h)
        ext = lc - QPointF(fx, fy)
        sx, sy = _SIGN[handle]
        raw_w = ext.x() * sx if sx else w0
        raw_h = ext.y() * sy if sy else h0
        keep = self.aspect_locked
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            keep = not keep
        mn = constants.MIN_ITEM_PT

        if keep and w0 > 0 and h0 > 0:
            if handle in ("e", "w"):
                s = max(abs(raw_w), mn) / w0
            elif handle in ("n", "s"):
                s = max(abs(raw_h), mn) / h0
            else:
                s = max(abs(raw_w) / w0, abs(raw_h) / h0, mn / w0, mn / h0)
            nw, nh = w0 * s, h0 * s
        else:
            if handle in ("e", "w"):
                nw, nh = max(raw_w, mn), h0
            elif handle in ("n", "s"):
                nw, nh = w0, max(raw_h, mn)
            else:
                nw, nh = max(raw_w, mn), max(raw_h, mn)

        self.prepareGeometryChange()
        self._w, self._h = nw, nh
        self.setTransformOriginPoint(nw / 2, nh / 2)
        fnx, fny = _OPPOSITE[handle](nw, nh)
        delta = self._pinned_scene - self.mapToScene(QPointF(fnx, fny))
        self.setPos(self.pos() + delta)
        self.update()
        self.geometryChanged.emit()

    # ---- snapping during move -------------------------------------------
    def itemChange(self, change, value):
        if (change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionChange
                and not self._resizing and not self._rotating
                and abs(self.rotation()) < 1e-6):
            sc = self.scene()
            if sc and hasattr(sc, "snap_position"):
                return sc.snap_position(self, value)
        elif change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.geometryChanged.emit()
        return super().itemChange(change, value)

    # ---- (de)serialization ----------------------------------------------
    def base_dict(self):
        x, y, w, h = self.get_geometry()
        return {"uid": self.uid, "x": x, "y": y, "w": w, "h": h,
                "rotation": self.rotation(), "z": self.zValue(),
                "name": self._name, "aspect_locked": self.aspect_locked,
                "locked": self.locked}

    def apply_base_dict(self, d):
        self.uid = d.get("uid", self.uid)
        self.set_name(d.get("name", self._name))
        self.aspect_locked = d.get("aspect_locked", True)
        self.setZValue(d.get("z", 0))
        self.set_state((d["x"], d["y"], d["w"], d["h"], d.get("rotation", 0.0)))
        self.set_locked(d.get("locked", False))


class FigureItem(BaseItem):
    """An imported sub-figure (raster embedded full-res, or vector)."""

    def __init__(self, source: LoadedSource, name: str = "Figure"):
        super().__init__(resizable=True)
        self._name = name
        self.aspect_locked = True
        self._source_path = source.path
        self._source_kind = source.kind
        self._page_index = source.page_index
        self._src_w = source.width_pt
        self._src_h = source.height_pt
        self._pixmap = source.preview
        self._vec_bytes = source.vec_pdf_bytes
        self._asset_name: str | None = None
        self.crop = (0.0, 0.0, 1.0, 1.0)          # normalized l,t,r,b
        self.size_group = None                    # id shared by size-locked figures
        self._w = source.width_pt
        self._h = source.height_pt

    def source_aspect(self):
        cx0, cy0, cx1, cy1 = self.crop
        cw = max((cx1 - cx0) * self._src_w, 1e-3)
        ch = max((cy1 - cy0) * self._src_h, 1e-3)
        return cw / ch

    def set_crop(self, crop):
        self.crop = tuple(crop)
        self.update()
        self.geometryChanged.emit()

    def is_cropped(self):
        return self.crop != (0.0, 0.0, 1.0, 1.0)

    def paint_content(self, painter):
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        pm = self._pixmap
        if pm and not pm.isNull():
            pw, ph = pm.width(), pm.height()
            cx0, cy0, cx1, cy1 = self.crop
            src = QRectF(cx0 * pw, cy0 * ph, (cx1 - cx0) * pw, (cy1 - cy0) * ph)
            painter.drawPixmap(QRectF(0, 0, self._w, self._h), pm, src)
        else:
            painter.fillRect(QRectF(0, 0, self._w, self._h), QtGui.QColor(230, 230, 230))

    # ---- export ----------------------------------------------------------
    def render_to_pdf(self, page, fontreg, keep_open):
        x, y, w, h = self.get_geometry()
        angle = self.rotation()
        cropped = self.is_cropped()

        # fast path: plain raster, no rotation/crop -> embed at full resolution
        if self._source_kind == "raster" and abs(angle) < 1e-6 and not cropped:
            page.insert_image(fitz.Rect(x, y, x + w, y + h),
                              filename=self._source_path, keep_proportion=False)
            return

        # (a) source doc + page + clip rectangle in the source's own coordinates
        if self._source_kind == "raster":
            tmp = fitz.open()
            tp = tmp.new_page(width=self._src_w, height=self._src_h)
            tp.insert_image(tp.rect, filename=self._source_path, keep_proportion=False)
            base, pno = tmp, 0
            bx0, by0, bw, bh = 0.0, 0.0, self._src_w, self._src_h
            keep_open.append(tmp)
        else:
            base = fitz.open("pdf", self._vec_bytes)
            pno = self._page_index
            pr = base[pno].rect
            bx0, by0, bw, bh = pr.x0, pr.y0, pr.width, pr.height
            keep_open.append(base)

        clip = None
        if cropped:
            cx0, cy0, cx1, cy1 = self.crop
            clip = fitz.Rect(bx0 + cx0 * bw, by0 + cy0 * bh,
                             bx0 + cx1 * bw, by0 + cy1 * bh)

        # (b) bake the (cropped) content, stretched to fill, into a w x h page.
        #     keep_proportion=False reproduces the editor's "fill the frame".
        inter = fitz.open()
        ip = inter.new_page(width=w, height=h)
        ip.show_pdf_page(ip.rect, base, pno, clip=clip, keep_proportion=False)
        keep_open.append(inter)

        # (c) place onto the target page, rotating about the centre.
        _place(page, inter, x, y, w, h, angle)

    def to_dict(self):
        d = self.base_dict()
        d.update({"type": "figure", "asset": self._asset_name,
                  "source_kind": self._source_kind, "page_index": self._page_index,
                  "crop": list(self.crop), "size_group": self.size_group})
        return d

    @classmethod
    def from_dict(cls, d, asset_path):
        source = load_source(asset_path, d.get("page_index", 0))
        item = cls(source, name=d.get("name", "Figure"))
        item.crop = tuple(d.get("crop", (0.0, 0.0, 1.0, 1.0)))
        item.size_group = d.get("size_group")
        item.apply_base_dict(d)
        return item


class LabelItem(InlineTextEdit, BaseItem):
    """An editable text label (panel letter, caption, annotation)."""

    EDIT_WRAP = False         # labels auto-size, no wrapping frame

    def __init__(self, text="a", family="Arial", size_pt=12.0, bold=True,
                 italic=False, color=None):
        super().__init__(resizable=False)
        self._name = "Label"
        self._editor = None
        self.text = text
        self.family = family
        self.size_pt = size_pt
        self.bold = bold
        self.italic = italic
        self.color = color or QtGui.QColor("black")
        self.align = "left"
        self._recompute()

    def font(self):
        f = QtGui.QFont(self.family)
        # pixel size == scene units == PDF points, so on-screen text matches
        # the exported PDF (point-size would be inflated by screen DPI).
        f.setPixelSize(max(1, round(self.size_pt)))
        f.setBold(self.bold)
        f.setItalic(self.italic)
        return f

    def _recompute(self):
        fm = QtGui.QFontMetricsF(self.font())
        flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        br = fm.boundingRect(QRectF(0, 0, 1e5, 1e5), flags, self.text or " ")
        self.prepareGeometryChange()
        self._w = max(br.width() + 2.0, 6.0)
        self._h = max(br.height() + 2.0, 6.0)
        self.setTransformOriginPoint(self._w / 2, self._h / 2)
        self.update()
        self.geometryChanged.emit()

    def set_text(self, text):
        self.text = text
        self._recompute()

    def apply_style(self, **kw):
        for k in ("family", "size_pt", "bold", "italic", "color", "align"):
            if k in kw and kw[k] is not None:
                setattr(self, k, kw[k])
        self._recompute()

    def paint_content(self, painter):
        if self._editor is not None:      # the in-place editor draws the text
            return
        painter.setFont(self.font())
        painter.setPen(QtGui.QPen(self.color))
        align = Qt.AlignmentFlag.AlignLeft if self.align == "left" else Qt.AlignmentFlag.AlignHCenter
        painter.drawText(QRectF(0, 0, self._w, self._h),
                         int(align | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextDontClip),
                         self.text)

    # ---- export ----------------------------------------------------------
    def render_to_pdf(self, page, fontreg, keep_open):
        x, y, w, h = self.get_geometry()
        rf = fonts.resolve_export_font(self.family, self.bold, self.italic, self.text)
        fontname = fontreg.ensure(page, rf)
        ff = fitz.Font(fontfile=rf.fontfile) if rf.fontfile else fitz.Font(fontname=rf.fontname)
        fs = self.size_pt
        ascender = ff.ascender
        line_h = (ff.ascender - ff.descender) * fs
        color = (self.color.red() / 255, self.color.green() / 255, self.color.blue() / 255)
        rot = int(round(self.rotation())) % 360
        morph = None
        if rot:
            pivot = fitz.Point(x, y)
            morph = (pivot, fitz.Matrix(EXPORT_ROT_SIGN * rot))
        for i, line in enumerate(self.text.split("\n")):
            lx = x
            if self.align == "center":
                lx = x + (w - ff.text_length(line, fs)) / 2
            point = fitz.Point(lx, y + ascender * fs + i * line_h)
            page.insert_text(point, line, fontname=fontname, fontsize=fs,
                             color=color, morph=morph)

    def to_dict(self):
        d = self.base_dict()
        d.update({"type": "label", "text": self.text, "family": self.family,
                  "size_pt": self.size_pt, "bold": self.bold, "italic": self.italic,
                  "color": self.color.name(), "align": self.align})
        return d

    @classmethod
    def from_dict(cls, d):
        item = cls(text=d.get("text", ""), family=d.get("family", "Arial"),
                   size_pt=d.get("size_pt", 12.0), bold=d.get("bold", True),
                   italic=d.get("italic", False),
                   color=QtGui.QColor(d.get("color", "#000000")))
        item.align = d.get("align", "left")
        item._recompute()
        item.apply_base_dict(d)
        return item


class TextBoxItem(InlineTextEdit, BaseItem):
    """A resizable text frame: wrapped text with optional border / fill."""

    PAD = 4.0
    grid_snap_exempt = True      # annotations move freely, no grid snapping

    def __init__(self, text="Text", family="Arial", size_pt=4.0,
                 bold=False, italic=False, color=None, w=170.0, h=90.0):
        super().__init__(resizable=True)
        self._name = "Text Box"
        self._editor = None
        self.aspect_locked = False
        self.text = text
        self.family = family
        self.size_pt = size_pt
        self.bold = bold
        self.italic = italic
        self.color = color or QtGui.QColor("black")
        self.align = "left"
        self.border = True
        self.border_color = QtGui.QColor(70, 70, 70)
        self.border_width = 0.5
        self.fill = False
        self.fill_color = QtGui.QColor("white")
        self.fill_opacity = 1.0
        self.corner_radius = 0.0          # 0 = rectangle, >0 = rounded (pt)
        self.pad_left = self.PAD          # text-to-frame insets (pt)
        self.pad_top = self.PAD
        self.pad_right = self.PAD
        self.pad_bottom = self.PAD
        self._adj_radius = False
        self._radius_at_press = 0.0
        self._w, self._h = w, h

    def font(self):
        f = QtGui.QFont(self.family)
        # pixel size == scene units == PDF points, so on-screen text matches
        # the exported PDF (point-size would be inflated by screen DPI).
        f.setPixelSize(max(1, round(self.size_pt)))
        f.setBold(self.bold)
        f.setItalic(self.italic)
        return f

    def _qalign(self):
        return {"left": Qt.AlignmentFlag.AlignLeft,
                "center": Qt.AlignmentFlag.AlignHCenter,
                "right": Qt.AlignmentFlag.AlignRight}[self.align]

    def _eff_radius(self) -> float:
        """Corner radius clamped so the arcs always fit the frame."""
        if self.corner_radius <= 0:
            return 0.0
        return min(self.corner_radius, self._w / 2, self._h / 2)

    def set_corner_radius(self, r: float):
        self.corner_radius = max(0.0, float(r))
        self.update()
        self.geometryChanged.emit()

    def paint_content(self, painter):
        rect = QRectF(0, 0, self._w, self._h)
        r = self._eff_radius()
        if self.fill:
            col = QtGui.QColor(self.fill_color)
            col.setAlphaF(max(0.0, min(1.0, self.fill_opacity)))
            if r > 0:
                path = QtGui.QPainterPath()
                path.addRoundedRect(rect, r, r)
                painter.fillPath(path, col)
            else:
                painter.fillRect(rect, col)
        if self.border and self.border_width > 0:
            painter.setPen(QtGui.QPen(self.border_color, self.border_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            d = self.border_width / 2
            if r > 0:
                rr = max(r - d, 0.0)
                painter.drawRoundedRect(rect.adjusted(d, d, -d, -d), rr, rr)
            else:
                painter.drawRect(rect.adjusted(d, d, -d, -d))
        if self._editor is not None:      # the in-place editor draws the text
            return
        painter.setFont(self.font())
        painter.setPen(QtGui.QPen(self.color))
        inner = rect.adjusted(self.pad_left, self.pad_top,
                              -self.pad_right, -self.pad_bottom)
        painter.drawText(inner, int(self._qalign() | Qt.AlignmentFlag.AlignTop
                                    | Qt.TextFlag.TextWordWrap), self.text)

    def set_text(self, text):
        self.text = text
        self.update()
        self.geometryChanged.emit()

    def apply_style(self, **kw):
        for k in ("text", "family", "size_pt", "bold", "italic", "color",
                  "align", "border", "border_color", "border_width",
                  "fill", "fill_color", "fill_opacity", "corner_radius",
                  "pad_left", "pad_top", "pad_right", "pad_bottom"):
            if k in kw and kw[k] is not None:
                setattr(self, k, kw[k])
        self.update()
        self.geometryChanged.emit()

    def _edit_pads(self) -> tuple[float, float, float]:
        return (self.pad_left, self.pad_top, self.pad_right)

    # ---- corner-radius handle (PowerPoint-style diamond) ------------------
    def _radius_handle_pos(self) -> QPointF:
        return QPointF(self._eff_radius(), 0.0)

    def _radius_handle_at(self, pos) -> bool:
        if self.corner_radius <= 0 or not self.isSelected():
            return False
        hs = self._handle_size()
        c = self._radius_handle_pos()
        if c.x() < hs * 1.5:          # too close to the nw resize handle
            return False
        return QRectF(c.x() - hs * 0.9, c.y() - hs * 0.9,
                      hs * 1.8, hs * 1.8).contains(pos)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if not self.isSelected() or self.corner_radius <= 0:
            return
        hs = self._handle_size()
        c = self._radius_handle_pos()
        poly = QtGui.QPolygonF([
            QPointF(c.x(), c.y() - hs * 0.75),
            QPointF(c.x() + hs * 0.75, c.y()),
            QPointF(c.x(), c.y() + hs * 0.75),
            QPointF(c.x() - hs * 0.75, c.y()),
        ])
        painter.setPen(QtGui.QPen(_SEL_COLOR, 1.0 / self._eff_scale()))
        painter.setBrush(QtGui.QColor(255, 193, 44))
        painter.drawPolygon(poly)

    def shape(self) -> QtGui.QPainterPath:
        path = super().shape()
        if self.isSelected() and self.corner_radius > 0:
            hs = self._handle_size()
            c = self._radius_handle_pos()
            path.addRect(QRectF(c.x() - hs, c.y() - hs, 2 * hs, 2 * hs))
        return path

    def hoverMoveEvent(self, event):
        if self._radius_handle_at(event.pos()):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
            return
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and self._radius_handle_at(event.pos())):
            self._adj_radius = True
            self._radius_at_press = self.corner_radius
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._adj_radius:
            r = event.pos().x()
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                step = constants.mm_to_pt(1.0)     # snap to whole millimetres
                r = round(r / step) * step
            self.set_corner_radius(max(0.0, min(r, self._w / 2, self._h / 2)))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._adj_radius:
            self._adj_radius = False
            sc = self.scene()
            if (sc is not None and hasattr(sc, "push_radius_undo")
                    and self.corner_radius != self._radius_at_press):
                sc.push_radius_undo(self, self._radius_at_press,
                                    self.corner_radius)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def render_to_pdf(self, page, fontreg, keep_open):
        x, y, w, h = self.get_geometry()
        rf = fonts.resolve_export_font(self.family, self.bold, self.italic, self.text)
        align = {"left": 0, "center": 1, "right": 2}[self.align]
        text = self.text if self.text and self.text.strip() else ""

        def build(page_h):
            """Draw frame + text on a w x page_h page.
            Returns (doc, deficit); deficit > 0 means the text did not fit."""
            doc = fitz.open()
            ip = doc.new_page(width=w, height=page_h)
            r = self._eff_radius()
            if self.fill:
                # float radius = fraction of the shorter side (circular arcs)
                rad = min(r / max(min(w, h), 1e-6), 0.5) if r > 0 else None
                ip.draw_rect(fitz.Rect(0, 0, w, h), color=None,
                             fill=_rgb(self.fill_color),
                             fill_opacity=max(0.0, min(1.0, self.fill_opacity)),
                             radius=rad)
            if self.border and self.border_width > 0:
                d = self.border_width / 2
                br = fitz.Rect(d, d, w - d, h - d)
                rr = max(r - d, 0.0)
                rad = (min(rr / max(min(br.width, br.height), 1e-6), 0.5)
                       if rr > 0 else None)
                ip.draw_rect(br, color=_rgb(self.border_color),
                             width=self.border_width, radius=rad)
            deficit = 0.0
            if text:
                inner = fitz.Rect(self.pad_left, self.pad_top,
                                  w - self.pad_right, page_h - self.pad_bottom)
                if inner.width > 1 and inner.height > 1:
                    rc = ip.insert_textbox(inner, text, fontname=rf.fontname,
                                           fontfile=rf.fontfile,
                                           fontsize=self.size_pt,
                                           color=_rgb(self.color), align=align)
                    deficit = -rc if rc < 0 else 0.0
                else:                    # frame smaller than the padding
                    deficit = self.pad_top + self.pad_bottom + 1.5 * self.size_pt
            return doc, deficit

        # insert_textbox writes NOTHING when the whole text does not fit,
        # while the editor clips at the frame. So retry on a taller canvas
        # until the text fits, then clip back to the frame on placement.
        inter, deficit = build(h)
        page_h, tries = h, 0
        while deficit > 0 and tries < 4:
            inter.close()
            page_h += deficit + 2 * self.size_pt + self.pad_top + self.pad_bottom
            inter, deficit = build(page_h)
            tries += 1
        keep_open.append(inter)
        _place(page, inter, x, y, w, h, self.rotation(),
               clip=fitz.Rect(0, 0, w, h))

    def to_dict(self):
        d = self.base_dict()
        d.update({"type": "textbox", "text": self.text, "family": self.family,
                  "size_pt": self.size_pt, "bold": self.bold, "italic": self.italic,
                  "color": self.color.name(), "align": self.align,
                  "border": self.border, "border_color": self.border_color.name(),
                  "border_width": self.border_width, "fill": self.fill,
                  "fill_color": self.fill_color.name(),
                  "fill_opacity": self.fill_opacity,
                  "corner_radius": self.corner_radius,
                  "pad_left": self.pad_left, "pad_top": self.pad_top,
                  "pad_right": self.pad_right, "pad_bottom": self.pad_bottom})
        return d

    @classmethod
    def from_dict(cls, d):
        item = cls(text=d.get("text", ""), family=d.get("family", "Arial"),
                   size_pt=d.get("size_pt", 11.0), bold=d.get("bold", False),
                   italic=d.get("italic", False),
                   color=QtGui.QColor(d.get("color", "#000000")))
        item.align = d.get("align", "left")
        item.border = d.get("border", True)
        item.border_color = QtGui.QColor(d.get("border_color", "#464646"))
        item.border_width = d.get("border_width", 1.0)
        item.fill = d.get("fill", False)
        item.fill_color = QtGui.QColor(d.get("fill_color", "#ffffff"))
        item.fill_opacity = d.get("fill_opacity", 1.0)
        item.corner_radius = d.get("corner_radius", 0.0)
        item.pad_left = d.get("pad_left", cls.PAD)
        item.pad_top = d.get("pad_top", cls.PAD)
        item.pad_right = d.get("pad_right", cls.PAD)
        item.pad_bottom = d.get("pad_bottom", cls.PAD)
        item.apply_base_dict(d)
        return item


class LineItem(CanvasItem):
    """A straight line / arrow annotation with draggable endpoints."""

    grid_snap_exempt = True      # annotations move freely, no grid snapping

    def __init__(self, p1=None, p2=None, color=None, width_pt=0.5,
                 dashed=False, arrow="none"):
        super().__init__()
        self._name = "Line"
        self.p1 = p1 if p1 is not None else QPointF(0, 0)
        self.p2 = p2 if p2 is not None else QPointF(120, 0)
        self.color = color or QtGui.QColor(40, 40, 40)
        self.width_pt = width_pt
        self.dashed = dashed
        self.arrow = arrow                       # 'none' | 'end' | 'both'
        self.anchor1 = None                      # {"uid":.., "node":..} or None
        self.anchor2 = None
        self._drag = None
        self._state_at_press = None

    def _eff_scale(self):
        sc = self.scene()
        if sc and sc.views():
            m = sc.views()[0].transform().m11()
            if m > 0:
                return max(0.4, min(m, 4.0))
        return 1.0

    def _hs(self):
        return constants.HANDLE_PX / self._eff_scale()

    def boundingRect(self):
        r = QRectF(self.p1, self.p2).normalized()
        m = _PAD + self.width_pt
        return r.adjusted(-m, -m, m, m)

    def content_scene_rect(self) -> QRectF:
        m = self.width_pt / 2
        if self.arrow != "none":
            m += 4.0 + 3.0 * self.width_pt        # arrowhead length
        r = QRectF(self.p1, self.p2).normalized().adjusted(-m, -m, m, m)
        return self.mapToScene(r).boundingRect()

    def shape(self):
        path = QtGui.QPainterPath()
        path.moveTo(self.p1)
        path.lineTo(self.p2)
        stroker = QtGui.QPainterPathStroker()
        stroker.setWidth(max(self.width_pt, 10.0 / self._eff_scale()))
        out = stroker.createStroke(path)
        if self.isSelected():
            hs = self._hs()
            for pt in (self.p1, self.p2):
                out.addRect(QRectF(pt.x() - hs / 2, pt.y() - hs / 2, hs, hs))
        return out

    def _handle_at(self, pos):
        hs = self._hs() * 1.4
        for name, pt in (("p1", self.p1), ("p2", self.p2)):
            if QRectF(pt.x() - hs / 2, pt.y() - hs / 2, hs, hs).contains(pos):
                return name
        return None

    def _arrow_poly(self, tip, frm):
        dx, dy = tip.x() - frm.x(), tip.y() - frm.y()
        n = math.hypot(dx, dy) or 1.0
        dx, dy = dx / n, dy / n
        L = 4.0 + 3.0 * self.width_pt
        W = L * 0.55
        bx, by = tip.x() - dx * L, tip.y() - dy * L
        px, py = -dy, dx
        return QtGui.QPolygonF([
            QPointF(tip.x(), tip.y()),
            QPointF(bx + px * W, by + py * W),
            QPointF(bx - px * W, by - py * W)])

    def _fill_poly(self, painter, poly):
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.color)
        painter.drawPolygon(poly)
        painter.restore()

    def paint(self, painter, option, widget=None):
        pen = QtGui.QPen(self.color, self.width_pt)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        if self.dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(self.p1, self.p2)
        if self.arrow in ("end", "both"):
            self._fill_poly(painter, self._arrow_poly(self.p2, self.p1))
        if self.arrow == "both":
            self._fill_poly(painter, self._arrow_poly(self.p1, self.p2))
        if self.isSelected():
            painter.setPen(QtGui.QPen(_SEL_COLOR, 1.0 / self._eff_scale()))
            hs = self._hs()
            for pt, anc in ((self.p1, self.anchor1), (self.p2, self.anchor2)):
                if anc:                          # anchored -> filled dot
                    painter.setBrush(_SEL_COLOR)
                    painter.drawEllipse(pt, hs * 0.7, hs * 0.7)
                else:                            # free -> white square
                    painter.setBrush(QtGui.QColor("white"))
                    painter.drawRect(QRectF(pt.x() - hs / 2, pt.y() - hs / 2, hs, hs))

    def mousePressEvent(self, event):
        self._state_at_press = self.get_state()
        self._sel_at_press = self.isSelected()
        if self.isSelected() and event.button() == Qt.MouseButton.LeftButton:
            h = self._handle_at(event.pos())
            if h:
                self._drag = h
                event.accept()
                return
        self._ctrl_drag = (bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                           and event.button() == Qt.MouseButton.LeftButton)
        self._ctrl_done = False
        super().mousePressEvent(event)
        if self._ctrl_drag:
            self.setSelected(True)

    def mouseMoveEvent(self, event):
        if self._drag:
            self.prepareGeometryChange()
            scene = self.scene()
            hit = self._nearest_node(self.mapToScene(event.pos()), scene) if scene else None
            if hit:
                uid, node, npos = hit
                local, anchor = self.mapFromScene(npos), {"uid": uid, "node": node}
            else:
                local, anchor = event.pos(), None
            if self._drag == "p1":
                self.p1, self.anchor1 = local, anchor
            else:
                self.p2, self.anchor2 = local, anchor
            self.update()
            self.geometryChanged.emit()
            event.accept()
            return
        if self._ctrl_drag and not self._ctrl_done:
            self._ctrl_done = True
            sc = self.scene()
            if sc and hasattr(sc, "ctrlDuplicate"):
                sc.ctrlDuplicate.emit()
        super().mouseMoveEvent(event)

    def _nearest_node(self, scene_pt, scene):
        thr = constants.ANCHOR_THRESHOLD_PX / max(scene._view_scale(), 0.01)
        best = None
        for it in scene.items():
            if not isinstance(it, BaseItem):
                continue
            for node, npos in it.anchor_nodes().items():
                d = npos - scene_pt
                dist = math.hypot(d.x(), d.y())
                if dist <= thr and (best is None or dist < best[0]):
                    best = (dist, it.uid, node, npos)
        return (best[1], best[2], best[3]) if best else None

    def update_anchors(self, scene):
        changed = False
        for which in ("p1", "p2"):
            anchor = self.anchor1 if which == "p1" else self.anchor2
            if not anchor:
                continue
            target = scene.find_item(anchor.get("uid"))
            if target is None or not hasattr(target, "anchor_nodes"):
                continue
            npos = target.anchor_nodes().get(anchor.get("node"))
            if npos is None:
                continue
            local = self.mapFromScene(npos)
            if which == "p1" and self.p1 != local:
                self.p1, changed = local, True
            elif which == "p2" and self.p2 != local:
                self.p2, changed = local, True
        if changed:
            self.prepareGeometryChange()
            self.update()
            self.geometryChanged.emit()

    def mouseReleaseEvent(self, event):
        was = self._drag
        ctrl_click = self._ctrl_drag and not self._ctrl_done
        self._drag = None
        self._ctrl_drag = False
        if not was:
            super().mouseReleaseEvent(event)
        else:
            event.accept()
        sc = self.scene()
        if self._state_at_press is not None:
            new = self.get_state()
            if (new != self._state_at_press and sc
                    and hasattr(sc, "push_state_undo")):
                sc.push_state_undo(self, self._state_at_press, new)
            elif ctrl_click and new == self._state_at_press and self._sel_at_press:
                self.setSelected(False)      # Ctrl-click toggles selection off
        self._state_at_press = None

    def hoverMoveEvent(self, event):
        if self.isSelected() and self._handle_at(event.pos()):
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def itemChange(self, change, value):
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            sc = self.scene()
            if sc and (self.anchor1 or self.anchor2):
                self.update_anchors(sc)
            self.geometryChanged.emit()
        return super().itemChange(change, value)

    def get_state(self):
        return (self.pos().x(), self.pos().y(),
                self.p1.x(), self.p1.y(), self.p2.x(), self.p2.y(),
                self.anchor1, self.anchor2)

    def set_state(self, s):
        self.prepareGeometryChange()
        self.setPos(s[0], s[1])
        self.p1 = QPointF(s[2], s[3])
        self.p2 = QPointF(s[4], s[5])
        if len(s) > 6:
            self.anchor1, self.anchor2 = s[6], s[7]
        self.update()
        self.geometryChanged.emit()

    def apply_style(self, **kw):
        for k in ("color", "width_pt", "dashed", "arrow"):
            if k in kw and kw[k] is not None:
                setattr(self, k, kw[k])
        self.prepareGeometryChange()
        self.update()
        self.geometryChanged.emit()

    def render_to_pdf(self, page, fontreg, keep_open):
        a = self.mapToScene(self.p1)
        b = self.mapToScene(self.p2)
        shape = page.new_shape()
        shape.draw_line(fitz.Point(a.x(), a.y()), fitz.Point(b.x(), b.y()))
        dashes = "[4 3] 0" if self.dashed else None
        shape.finish(color=_rgb(self.color), width=self.width_pt, dashes=dashes,
                     lineCap=1, lineJoin=1)
        for poly, on in ((self._arrow_poly(self.p2, self.p1),
                          self.arrow in ("end", "both")),
                         (self._arrow_poly(self.p1, self.p2),
                          self.arrow == "both")):
            if not on:
                continue
            pts = [self.mapToScene(p) for p in poly]
            shape.draw_polyline([fitz.Point(p.x(), p.y()) for p in pts])
            shape.finish(color=_rgb(self.color), fill=_rgb(self.color), closePath=True)
        shape.commit()

    def to_dict(self):
        return {"type": "line", "uid": self.uid,
                "x": self.pos().x(), "y": self.pos().y(),
                "p1": [self.p1.x(), self.p1.y()], "p2": [self.p2.x(), self.p2.y()],
                "z": self.zValue(), "name": self._name,
                "color": self.color.name(), "width_pt": self.width_pt,
                "dashed": self.dashed, "arrow": self.arrow,
                "anchor1": self.anchor1, "anchor2": self.anchor2,
                "locked": self.locked}

    @classmethod
    def from_dict(cls, d):
        item = cls(p1=QPointF(*d.get("p1", [0, 0])),
                   p2=QPointF(*d.get("p2", [120, 0])),
                   color=QtGui.QColor(d.get("color", "#282828")),
                   width_pt=d.get("width_pt", 0.5),
                   dashed=d.get("dashed", False),
                   arrow=d.get("arrow", "none"))
        item.uid = d.get("uid", item.uid)
        item.set_name(d.get("name", "Line"))
        item.setZValue(d.get("z", 0))
        item.setPos(d.get("x", 0), d.get("y", 0))
        item.anchor1 = d.get("anchor1")
        item.anchor2 = d.get("anchor2")
        item.set_locked(d.get("locked", False))
        return item
