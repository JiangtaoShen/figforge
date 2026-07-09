import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import QPointF, QRectF
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from figforge.canvas.scene import PageScene, _grid_major_mm
from figforge.canvas.items import FigureItem, TextBoxItem
from figforge.main_window import MainWindow
from figforge.fileio import importers
from figforge import constants
from PIL import Image

results = []
def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ((" -- " + extra) if (extra and not cond) else ""))

sc = PageScene()

# -------------------------------------------------- step selection per zoom
expect = {0.25: 20.0, 0.5: 10.0, 1.0: 5.0, 2.0: 2.0, 4.0: 1.0,
          8.0: 0.5, 20.0: 0.2, 40.0: 0.1}
got = {s: sc.dynamic_grid_mm(s) for s in expect}
check("dynamic steps follow zoom (1-2-5 series)", got == expect, str(got))

# major (decade) grouping
majors = {0.1: 1.0, 0.2: 1.0, 0.5: 1.0, 1.0: 10.0, 2.0: 10.0,
          5.0: 10.0, 10.0: 100.0, 20.0: 100.0, 50.0: 100.0}
gm = {m: _grid_major_mm(m) for m in majors}
check("major decade lines", gm == majors, str(gm))

# on-screen pitch always >= GRID_MIN_PX
ok = all(constants.mm_to_pt(sc.dynamic_grid_mm(s)) * s >= constants.GRID_MIN_PX - 1e-6
         for s in (0.1, 0.33, 0.5, 0.77, 1, 1.5, 2, 3, 4, 6, 8, 12, 16, 25, 40))
check("pitch never below GRID_MIN_PX", ok)

# ------------------------------------------------ snapping follows the view
win = MainWindow()
tmp = tempfile.mkdtemp(prefix="ff_gr_")
p = os.path.join(tmp, "a.png")
Image.new("RGB", (300, 200), (120, 60, 60)).save(p, dpi=(150, 150))
fig = FigureItem(importers.load_source(p), name="f")
fig.set_geometry(100.0, 100.0, 144.0, 96.0)
win.scene.addItem(fig)
win.chk_grid.setChecked(True)                 # grid on -> snap_to_grid on
win.scene.snap_enabled = False                # isolate grid snapping
win.view.resetTransform()
win.view.scale(4.0, 4.0)                      # 400% -> 1 mm grid
step4 = constants.mm_to_pt(win.scene.dynamic_grid_mm())
check("zoomed-in step is 1 mm", abs(step4 - constants.mm_to_pt(1.0)) < 1e-9,
      str(step4))
got4 = win.scene.snap_position(fig, QPointF(285.1, 285.1))
def off(v, st):
    r = v % st
    return min(r, st - r)
check("snap uses 1 mm at 400%", off(got4.x(), step4) < 1e-6
      and abs(got4.x() - 285.1) < step4 / 2 + 1e-6, str(got4))
win.view.resetTransform()                     # 100% -> 5 mm grid
step1 = constants.mm_to_pt(win.scene.dynamic_grid_mm())
check("zoomed-out step is 5 mm", abs(step1 - constants.mm_to_pt(5.0)) < 1e-9)
got1 = win.scene.snap_position(fig, QPointF(285.1, 285.1))
check("snap uses 5 mm at 100%", off(got1.x(), step1) < 1e-6, str(got1))
# text box still exempt
box = TextBoxItem(text="t"); box.set_geometry(300, 300, 100, 40)
win.scene.addItem(box)
prop = QPointF(301.3, 297.7)
check("textbox still grid-exempt", win.scene.snap_position(box, prop) == prop)
win.scene.snap_enabled = True

# ------------------------------------------------ rendering density check
def grid_cols(scale_px, src_pt):
    """Render (0,0,src_pt,src_pt) of the page at given px size; count grid columns."""
    img = QtGui.QImage(scale_px, scale_px, QtGui.QImage.Format.Format_RGB32)
    img.fill(QtGui.QColor("white"))
    pt = QtGui.QPainter(img)
    win.scene.render(pt, QRectF(0, 0, scale_px, scale_px),
                     QRectF(10, 10, src_pt, src_pt))
    pt.end()
    ys = list(range(0, scale_px, 7))
    cols = 0
    in_run = False
    for x in range(scale_px):
        hits = 0
        for y in ys:
            c = img.pixelColor(x, y)
            r, g, b = c.red(), c.green(), c.blue()
            if 180 < r < 250 and b > r and abs(g - r) < 16:
                hits += 1
        # a vertical gridline matches on nearly every sampled row; a row that
        # happens to sit on a horizontal gridline adds only one hit per column
        hit = hits >= 0.6 * len(ys)
        if hit and not in_run:
            cols += 1
        in_run = hit
    return cols

n_zoom4 = grid_cols(400, 100.0)    # 4x zoom: 1 mm grid -> ~35 lines / 100 pt
n_zoom1 = grid_cols(100, 100.0)    # 1x zoom: 5 mm grid -> ~7 lines / 100 pt
check("grid densifies when zoomed (rendered)", n_zoom4 >= 3 * max(n_zoom1, 1),
      f"4x:{n_zoom4} 1x:{n_zoom1}")
check("plausible line counts", 30 <= n_zoom4 <= 40 and 5 <= n_zoom1 <= 9,
      f"4x:{n_zoom4} 1x:{n_zoom1}")

# status label shows the step
win._on_zoom(400.0)
check("status shows grid step", "mm" in win.lbl_zoom.text(), win.lbl_zoom.text())

win.undo_stack.cleanChanged.disconnect()
n_fail = sum(1 for ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} passed")
sys.exit(1 if n_fail else 0)
