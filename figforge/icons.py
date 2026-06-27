"""Toolbar icons drawn with QPainter (no external files; theme-coloured).

``build_icons(color)`` returns a dict of name -> QIcon, rendered as crisp
line-art so they bundle cleanly and scale to any toolbar size.
"""
from __future__ import annotations

import math

from PySide6 import QtGui
from PySide6.QtCore import QPointF, QRectF, Qt

_SZ = 64
_PDF_TAG = QtGui.QColor(214, 73, 66)
_PNG_TAG = QtGui.QColor(46, 160, 96)


# --- primitives ------------------------------------------------------------
def _line(p, x1, y1, x2, y2):
    p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _bar(p, color, x, y, w, h, r=2.5):
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawRoundedRect(QRectF(x, y, w, h), r, r)
    p.restore()


def _arrowhead(p, color, tip, dx, dy, size=12.0):
    n = math.hypot(dx, dy) or 1.0
    dx, dy = dx / n, dy / n
    px, py = -dy, dx
    bx, by = tip[0] - dx * size, tip[1] - dy * size
    poly = QtGui.QPolygonF([
        QPointF(tip[0], tip[1]),
        QPointF(bx + px * size * 0.6, by + py * size * 0.6),
        QPointF(bx - px * size * 0.6, by - py * size * 0.6),
    ])
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawPolygon(poly)
    p.restore()


def _arrow_up(p, color, cx, top, bottom):
    _line(p, cx, bottom, cx, top + 5)
    _arrowhead(p, color, (cx, top), 0, -1)


def _arrow_down(p, color, cx, top, bottom):
    _line(p, cx, top, cx, bottom - 5)
    _arrowhead(p, color, (cx, bottom), 0, 1)


# --- glyphs ----------------------------------------------------------------
def _import(p, color):
    p.drawRoundedRect(QRectF(13, 17, 32, 26), 3, 3)
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    p.drawEllipse(QPointF(22, 26), 3.2, 3.2)
    p.restore()
    p.drawPolyline(QtGui.QPolygonF([QPointF(15, 41), QPointF(25, 31),
                                    QPointF(32, 37), QPointF(43, 28)]))
    _line(p, 48, 43, 48, 54)
    _line(p, 42.5, 48.5, 53.5, 48.5)


def _text(p, color):
    _line(p, 18, 18, 46, 18)
    _line(p, 32, 18, 32, 47)


def _align_left(p, color):
    _line(p, 14, 12, 14, 52)
    _bar(p, color, 14, 20, 34, 9)
    _bar(p, color, 14, 35, 24, 9)


def _align_hcenter(p, color):
    _line(p, 32, 10, 32, 54)
    _bar(p, color, 15, 20, 34, 9)
    _bar(p, color, 20, 35, 24, 9)


def _align_right(p, color):
    _line(p, 50, 12, 50, 52)
    _bar(p, color, 16, 20, 34, 9)
    _bar(p, color, 26, 35, 24, 9)


def _align_top(p, color):
    _line(p, 12, 14, 52, 14)
    _bar(p, color, 20, 14, 9, 34)
    _bar(p, color, 35, 14, 9, 24)


def _align_vmiddle(p, color):
    _line(p, 10, 32, 54, 32)
    _bar(p, color, 20, 15, 9, 34)
    _bar(p, color, 35, 20, 9, 24)


def _align_bottom(p, color):
    _line(p, 12, 50, 52, 50)
    _bar(p, color, 20, 16, 9, 34)
    _bar(p, color, 35, 26, 9, 24)


def _front(p, color):
    _line(p, 16, 14, 48, 14)
    _arrow_up(p, color, 32, 20, 50)


def _forward(p, color):
    _arrow_up(p, color, 32, 16, 50)


def _backward(p, color):
    _arrow_down(p, color, 32, 14, 48)


def _back(p, color):
    _line(p, 16, 50, 48, 50)
    _arrow_down(p, color, 32, 14, 44)


def _rotate(p, color, cw):
    rect = QRectF(17, 17, 30, 30)
    cx, cy, r = 32, 32, 15
    if not cw:                       # counter-clockwise (rotate left)
        p.drawArc(rect, 70 * 16, 250 * 16)
        th = math.radians(70)
        pt = (cx + r * math.cos(th), cy - r * math.sin(th))
        _arrowhead(p, color, pt, -math.sin(th), -math.cos(th))
    else:                            # clockwise (rotate right)
        p.drawArc(rect, 110 * 16, -250 * 16)
        th = math.radians(110)
        pt = (cx + r * math.cos(th), cy - r * math.sin(th))
        _arrowhead(p, color, pt, math.sin(th), math.cos(th))


def _rotate_left(p, color):
    _rotate(p, color, False)


def _rotate_right(p, color):
    _rotate(p, color, True)


def _crop(p, color):
    _line(p, 22, 22, 47, 22)
    _line(p, 22, 22, 22, 47)
    _line(p, 42, 42, 17, 42)
    _line(p, 42, 42, 42, 17)


def _export(p, color, tag):
    _line(p, 14, 40, 14, 50)
    _line(p, 14, 50, 50, 50)
    _line(p, 50, 40, 50, 50)
    _line(p, 32, 13, 32, 38)
    _arrowhead(p, color, (32, 39), 0, 1, 13)
    _bar(p, tag, 39, 9, 15, 15, 3)


def _export_pdf(p, color):
    _export(p, color, _PDF_TAG)


def _export_png(p, color):
    _export(p, color, _PNG_TAG)


_DRAW = {
    "import": _import, "text": _text,
    "align_left": _align_left, "align_hcenter": _align_hcenter,
    "align_right": _align_right, "align_top": _align_top,
    "align_vmiddle": _align_vmiddle, "align_bottom": _align_bottom,
    "front": _front, "forward": _forward, "backward": _backward, "back": _back,
    "rotate_left": _rotate_left, "rotate_right": _rotate_right,
    "crop": _crop, "export_pdf": _export_pdf, "export_png": _export_png,
}


def build_icons(color: QtGui.QColor) -> dict[str, QtGui.QIcon]:
    icons = {}
    for name, fn in _DRAW.items():
        pm = QtGui.QPixmap(_SZ, _SZ)
        pm.fill(Qt.GlobalColor.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        pen = QtGui.QPen(color)
        pen.setWidthF(5.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        fn(p, color)
        p.end()
        icons[name] = QtGui.QIcon(pm)
    return icons
