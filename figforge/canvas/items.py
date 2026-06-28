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


def _place(page, src, x, y, w, h, angle):
    """Show single-page PDF `src` at (x,y,w,h) on `page`, rotated about centre."""
    if abs(angle) < 1e-6:
        page.show_pdf_page(fitz.Rect(x, y, x + w, y + h), src, 0,
                           keep_proportion=False)
        return
    ang = round(angle)
    th = math.radians(ang)
    c, s = abs(math.cos(th)), abs(math.sin(th))
    ew, eh = w * c + h * s, w * s + h * c          # rotated bounding box
    cx, cy = x + w / 2, y + h / 2
    page.show_pdf_page(fitz.Rect(cx - ew / 2, cy - eh / 2, cx + ew / 2, cy + eh / 2),
                       src, 0, rotate=int(EXPORT_ROT_SIGN * ang) % 360)


class CanvasItem(QtWidgets.QGraphicsObject):
    """Base for every selectable page object (rectangular items and lines)."""

    geometryChanged = Signal()

    def __init__(self):
        super().__init__()
        self._name = "Item"
        self.uid = uuid.uuid4().hex
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._ctrl_drag = False        # Ctrl-drag duplicates
        self._ctrl_done = False

    def name(self):
        return self._name

    def set_name(self, name):
        self._name = name


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
                "name": self._name, "aspect_locked": self.aspect_locked}

    def apply_base_dict(self, d):
        self.uid = d.get("uid", self.uid)
        self.set_name(d.get("name", self._name))
        self.aspect_locked = d.get("aspect_locked", True)
        self.setZValue(d.get("z", 0))
        self.set_state((d["x"], d["y"], d["w"], d["h"], d.get("rotation", 0.0)))


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


class LabelItem(BaseItem):
    """An editable text label (panel letter, caption, annotation)."""

    editRequested = Signal(object)

    def __init__(self, text="a", family="Arial", size_pt=12.0, bold=True,
                 italic=False, color=None):
        super().__init__(resizable=False)
        self._name = "Label"
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
        painter.setFont(self.font())
        painter.setPen(QtGui.QPen(self.color))
        align = Qt.AlignmentFlag.AlignLeft if self.align == "left" else Qt.AlignmentFlag.AlignHCenter
        painter.drawText(QRectF(0, 0, self._w, self._h),
                         int(align | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextDontClip),
                         self.text)

    def mouseDoubleClickEvent(self, event):
        self.editRequested.emit(self)
        event.accept()

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


class TextBoxItem(BaseItem):
    """A resizable text frame: wrapped text with optional border / fill."""

    editRequested = Signal(object)
    PAD = 4.0

    def __init__(self, text="文本框", family="Arial", size_pt=4.0,
                 bold=False, italic=False, color=None, w=170.0, h=90.0):
        super().__init__(resizable=True)
        self._name = "文本框"
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

    def paint_content(self, painter):
        rect = QRectF(0, 0, self._w, self._h)
        if self.fill:
            col = QtGui.QColor(self.fill_color)
            col.setAlphaF(max(0.0, min(1.0, self.fill_opacity)))
            painter.fillRect(rect, col)
        if self.border and self.border_width > 0:
            painter.setPen(QtGui.QPen(self.border_color, self.border_width))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            d = self.border_width / 2
            painter.drawRect(rect.adjusted(d, d, -d, -d))
        painter.setFont(self.font())
        painter.setPen(QtGui.QPen(self.color))
        inner = rect.adjusted(self.PAD, self.PAD, -self.PAD, -self.PAD)
        painter.drawText(inner, int(self._qalign() | Qt.AlignmentFlag.AlignTop
                                    | Qt.TextFlag.TextWordWrap), self.text)

    def set_text(self, text):
        self.text = text
        self.update()
        self.geometryChanged.emit()

    def apply_style(self, **kw):
        for k in ("text", "family", "size_pt", "bold", "italic", "color",
                  "align", "border", "border_color", "border_width",
                  "fill", "fill_color", "fill_opacity"):
            if k in kw and kw[k] is not None:
                setattr(self, k, kw[k])
        self.update()
        self.geometryChanged.emit()

    def mouseDoubleClickEvent(self, event):
        self.editRequested.emit(self)
        event.accept()

    def render_to_pdf(self, page, fontreg, keep_open):
        x, y, w, h = self.get_geometry()
        inter = fitz.open()
        ip = inter.new_page(width=w, height=h)
        keep_open.append(inter)
        if self.fill:
            ip.draw_rect(fitz.Rect(0, 0, w, h), color=None, fill=_rgb(self.fill_color),
                         fill_opacity=max(0.0, min(1.0, self.fill_opacity)))
        if self.border and self.border_width > 0:
            d = self.border_width / 2
            ip.draw_rect(fitz.Rect(d, d, w - d, h - d),
                         color=_rgb(self.border_color), width=self.border_width)
        rf = fonts.resolve_export_font(self.family, self.bold, self.italic, self.text)
        inner = fitz.Rect(self.PAD, self.PAD, w - self.PAD, h - self.PAD)
        align = {"left": 0, "center": 1, "right": 2}[self.align]
        ip.insert_textbox(inner, self.text, fontname=rf.fontname,
                          fontfile=rf.fontfile, fontsize=self.size_pt,
                          color=_rgb(self.color), align=align)
        _place(page, inter, x, y, w, h, self.rotation())

    def to_dict(self):
        d = self.base_dict()
        d.update({"type": "textbox", "text": self.text, "family": self.family,
                  "size_pt": self.size_pt, "bold": self.bold, "italic": self.italic,
                  "color": self.color.name(), "align": self.align,
                  "border": self.border, "border_color": self.border_color.name(),
                  "border_width": self.border_width, "fill": self.fill,
                  "fill_color": self.fill_color.name(),
                  "fill_opacity": self.fill_opacity})
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
        item.apply_base_dict(d)
        return item


class LineItem(CanvasItem):
    """A straight line / arrow annotation with draggable endpoints."""

    def __init__(self, p1=None, p2=None, color=None, width_pt=0.5,
                 dashed=False, arrow="none"):
        super().__init__()
        self._name = "线条"
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
        self._drag = None
        self._ctrl_drag = False
        if not was:
            super().mouseReleaseEvent(event)
        else:
            event.accept()
        sc = self.scene()
        if self._state_at_press is not None and sc and hasattr(sc, "push_state_undo"):
            new = self.get_state()
            if new != self._state_at_press:
                sc.push_state_undo(self, self._state_at_press, new)
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
                "anchor1": self.anchor1, "anchor2": self.anchor2}

    @classmethod
    def from_dict(cls, d):
        item = cls(p1=QPointF(*d.get("p1", [0, 0])),
                   p2=QPointF(*d.get("p2", [120, 0])),
                   color=QtGui.QColor(d.get("color", "#282828")),
                   width_pt=d.get("width_pt", 0.5),
                   dashed=d.get("dashed", False),
                   arrow=d.get("arrow", "none"))
        item.uid = d.get("uid", item.uid)
        item.set_name(d.get("name", "线条"))
        item.setZValue(d.get("z", 0))
        item.setPos(d.get("x", 0), d.get("y", 0))
        item.anchor1 = d.get("anchor1")
        item.anchor2 = d.get("anchor2")
        return item
