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


class BaseItem(QtWidgets.QGraphicsObject):
    """Common selection / move / resize / rotate behaviour."""

    geometryChanged = Signal()

    def __init__(self, resizable: bool = True):
        super().__init__()
        self._w = 100.0
        self._h = 100.0
        self._name = "Item"
        self.aspect_locked = True
        self.resizable = resizable
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
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
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._rotating:
            self._do_rotate(event.scenePos(), event.modifiers())
            event.accept()
            return
        if self._resizing:
            self._do_resize(event.scenePos(), event.modifiers())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        active = self._resizing or self._rotating
        self._resizing = None
        self._rotating = False
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
        return {"x": x, "y": y, "w": w, "h": h, "rotation": self.rotation(),
                "z": self.zValue(), "name": self._name,
                "aspect_locked": self.aspect_locked}

    def apply_base_dict(self, d):
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
        if abs(angle) < 1e-6:
            page.show_pdf_page(fitz.Rect(x, y, x + w, y + h), inter, 0,
                               keep_proportion=False)
        else:
            ang = round(angle)
            th = math.radians(ang)
            c, s = abs(math.cos(th)), abs(math.sin(th))
            ew, eh = w * c + h * s, w * s + h * c   # rotated bounding box
            cx, cy = x + w / 2, y + h / 2
            rect = fitz.Rect(cx - ew / 2, cy - eh / 2, cx + ew / 2, cy + eh / 2)
            page.show_pdf_page(rect, inter, 0, rotate=int(EXPORT_ROT_SIGN * ang) % 360)

    def to_dict(self):
        d = self.base_dict()
        d.update({"type": "figure", "asset": self._asset_name,
                  "source_kind": self._source_kind, "page_index": self._page_index,
                  "crop": list(self.crop)})
        return d

    @classmethod
    def from_dict(cls, d, asset_path):
        source = load_source(asset_path, d.get("page_index", 0))
        item = cls(source, name=d.get("name", "Figure"))
        item.crop = tuple(d.get("crop", (0.0, 0.0, 1.0, 1.0)))
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
        f.setPointSizeF(self.size_pt)
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
        rf = fonts.resolve_export_font(self.family, self.bold, self.italic)
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
