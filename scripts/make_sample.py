"""Generate the bundled sample project (figforge/resources/sample.ffp).

Draws four small vector sub-figures with PyMuPDF (no extra deps), lays
them out as a labelled 2x2 Nature-style panel figure with a rounded
annotation box and a connector arrow, and saves the .ffp.

Run:  py scripts/make_sample.py
Also imported by scripts/make_demo_gif.py for the README GIF.
"""
from __future__ import annotations

import os
import sys

import fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RED, GREEN, AMBER, BLUE = (0.925, 0.365, 0.341), (0.204, 0.698, 0.482), \
    (0.953, 0.706, 0.227), (0.231, 0.455, 0.929)
GRAY = (0.45, 0.45, 0.45)

W, H = 240.0, 180.0          # panel page size (pt) — 4:3


def _axes(page, m=26.0):
    """L-shaped axes with ticks; returns the plot rect."""
    x0, y0, x1, y1 = m, 14.0, W - 10.0, H - m
    sh = page.new_shape()
    sh.draw_line((x0, y0), (x0, y1))
    sh.draw_line((x0, y1), (x1, y1))
    for i in range(1, 5):
        x = x0 + (x1 - x0) * i / 5
        sh.draw_line((x, y1), (x, y1 + 3))
        y = y1 - (y1 - y0) * i / 5
        sh.draw_line((x0, y), (x0 - 3, y))
    sh.finish(color=GRAY, width=1.0, closePath=False)
    sh.commit()
    return x0, y0, x1, y1


def _panel_lines(page):
    x0, y0, x1, y1 = _axes(page)
    pts_r = [0.70, 0.58, 0.62, 0.44, 0.36, 0.24, 0.16]
    pts_b = [0.85, 0.78, 0.72, 0.62, 0.56, 0.46, 0.40]
    for pts, col in ((pts_b, BLUE), (pts_r, RED)):
        sh = page.new_shape()
        xy = [(x0 + (x1 - x0) * i / (len(pts) - 1), y0 + (y1 - y0) * p)
              for i, p in enumerate(pts)]
        for a, b in zip(xy, xy[1:]):
            sh.draw_line(a, b)
        sh.finish(color=col, width=2.2, lineCap=1, lineJoin=1, closePath=False)
        sh.commit()
        sh = page.new_shape()
        for x, y in xy:
            sh.draw_circle((x, y), 2.4)
        sh.finish(color=(1, 1, 1), fill=col, width=0.8)
        sh.commit()


def _panel_heatmap(page):
    n, m0 = 6, 18.0
    cw = (W - 2 * m0) / n
    ch = (H - 2 * m0) / n
    vals = [[((i * 3 + j * 5 + (i * j) % 4) % 9) / 9 for j in range(n)]
            for i in range(n)]
    sh = page.new_shape()
    for i in range(n):
        for j in range(n):
            v = vals[i][j]
            col = (1 - 0.80 * v, 1 - 0.30 * v, 1 - 0.52 * v)   # white->green
            sh.draw_rect(fitz.Rect(m0 + j * cw + 0.6, m0 + i * ch + 0.6,
                                   m0 + (j + 1) * cw - 0.6,
                                   m0 + (i + 1) * ch - 0.6))
            sh.finish(color=None, fill=col)
    sh.commit()


def _panel_scatter(page):
    x0, y0, x1, y1 = _axes(page)
    pw, ph = x1 - x0, y1 - y0
    red = [(0.18, 0.78), (0.25, 0.66), (0.32, 0.74), (0.22, 0.58),
           (0.38, 0.62), (0.30, 0.86), (0.15, 0.68), (0.42, 0.72),
           (0.35, 0.55), (0.27, 0.80)]
    blue = [(0.62, 0.34), (0.70, 0.26), (0.78, 0.36), (0.66, 0.18),
            (0.84, 0.24), (0.74, 0.44), (0.88, 0.32), (0.60, 0.42),
            (0.80, 0.14), (0.70, 0.35)]
    for pts, col in ((red, RED), (blue, BLUE)):
        sh = page.new_shape()
        for fx, fy in pts:
            sh.draw_circle((x0 + fx * pw, y0 + fy * ph), 3.0)
        sh.finish(color=(1, 1, 1), fill=col, width=0.7)
        sh.commit()


def _panel_bars(page):
    x0, y0, x1, y1 = _axes(page)
    pw = x1 - x0
    heights = [0.38, 0.62, 0.30, 0.82]
    cols = [AMBER, GREEN, RED, BLUE]
    n = len(heights)
    bw = pw / (n * 1.7)
    gap = (pw - n * bw) / (n + 1)
    tops = []
    for i, (h, col) in enumerate(zip(heights, cols)):
        bx = x0 + gap + i * (bw + gap)
        top = y1 - (y1 - y0) * h
        sh = page.new_shape()
        sh.draw_rect(fitz.Rect(bx, top, bx + bw, y1))
        sh.finish(color=None, fill=col)
        sh.commit()
        tops.append((bx + bw / 2, top))
    # significance bracket between bar 2 and bar 4, with a star
    bx2, t2 = tops[1]
    bx4, t4 = tops[3]
    yb = min(t2, t4) - 12
    sh = page.new_shape()
    sh.draw_line((bx2, t2 - 4), (bx2, yb))
    sh.draw_line((bx2, yb), (bx4, yb))
    sh.draw_line((bx4, yb), (bx4, t4 - 4))
    sh.finish(color=(0.2, 0.2, 0.2), width=1.0, closePath=False)
    sh.commit()
    page.insert_text(fitz.Point((bx2 + bx4) / 2 - 3, yb - 4), "*",
                     fontsize=14, fontname="helv", color=(0.1, 0.1, 0.1))


def make_panel_pdfs(outdir: str) -> list[str]:
    """Write the four vector sub-figure PDFs; returns their paths."""
    os.makedirs(outdir, exist_ok=True)
    panels = [("panel_lines", _panel_lines), ("panel_heatmap", _panel_heatmap),
              ("panel_scatter", _panel_scatter), ("panel_bars", _panel_bars)]
    paths = []
    for name, draw in panels:
        doc = fitz.open()
        page = doc.new_page(width=W, height=H)
        draw(page)
        p = os.path.join(outdir, f"{name}.pdf")
        doc.save(p, deflate=True)
        doc.close()
        paths.append(p)
    return paths


def grid_geometry():
    """Panel rects (pt) for a 2x2 grid on A4 portrait, plus label offsets."""
    from figforge import constants
    mm = constants.mm_to_pt
    margin, gap, top = mm(15), mm(8), mm(30)
    pw = (mm(210) - 2 * margin - gap) / 2
    ph = pw * H / W
    rects = []
    for r in range(2):
        for c in range(2):
            rects.append((margin + c * (pw + gap), top + r * (ph + gap + mm(6)),
                          pw, ph))
    return rects


def build_sample(out_path: str, assets_dir: str) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets, QtGui
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    from figforge import constants
    from figforge.canvas.scene import PageScene
    from figforge.canvas.items import (FigureItem, LabelItem, LineItem,
                                       TextBoxItem)
    from figforge.fileio import importers, project

    mm = constants.mm_to_pt
    paths = make_panel_pdfs(assets_dir)
    scene = PageScene()

    rects = grid_geometry()
    z = 1.0
    figs = []
    for i, (p, (x, y, w, h)) in enumerate(zip(paths, rects), 1):
        it = FigureItem(importers.load_source(p), name=f"Image {i}")
        it.set_geometry(x, y, w, h)
        it.setZValue(z)
        z += 1
        scene.addItem(it)
        figs.append(it)

    for label, (x, y, _w, _h) in zip("abcd", rects):
        lab = LabelItem(text=label, family="Arial", size_pt=14.0, bold=True)
        lab.set_name(f"Label {label}")
        lab.set_geometry(x - mm(1), y - mm(7), *lab.size())
        lab.setZValue(z)
        z += 1
        scene.addItem(lab)

    tb = TextBoxItem(text="Group 2 vs 4: p < 0.05 (n = 42)",
                     family="Arial", size_pt=8.0)
    tb.set_name("Text Box 1")
    tb.corner_radius = mm(1.5)
    tb.border_width = 0.8
    tb.pad_left = tb.pad_right = tb.pad_top = tb.pad_bottom = mm(1.2)
    x4, y4, w4, h4 = rects[3]
    tb.set_geometry(x4 + w4 * 0.10, y4 + h4 + mm(12), mm(58), mm(9))
    tb.setZValue(z)
    z += 1
    scene.addItem(tb)

    ln = LineItem(color=QtGui.QColor(40, 40, 40), width_pt=0.9, arrow="end")
    ln.set_name("Line 1")
    ln.setZValue(z)
    scene.addItem(ln)
    ln.setPos(0, 0)
    from PySide6.QtCore import QPointF
    ln.p1 = QPointF(tb.pos().x() + mm(29), tb.pos().y())          # box top
    ln.p2 = QPointF(x4 + w4 * 0.82, y4 + h4 * 0.55)               # blue bar in d
    ln.anchor1 = {"uid": tb.uid, "node": "n"}
    ln.update_anchors(scene)

    project.save_project(out_path, scene)
    print("wrote", out_path, os.path.getsize(out_path), "bytes")


if __name__ == "__main__":
    build_sample(os.path.join(ROOT, "figforge", "resources", "sample.ffp"),
                 os.path.join(ROOT, "scripts", "_sample_assets"))
