import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt, QPointF, QRectF
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from figforge.main_window import MainWindow
from figforge.canvas.items import TextBoxItem
from figforge.canvas.scene import PageScene
from figforge.fileio import exporters, project
from figforge import constants
import fitz

results = []
def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ((" -- " + extra) if (extra and not cond) else ""))

MM = constants.mm_to_pt

# ------------------------------------------------------------ model basics
tb = TextBoxItem(text="R", size_pt=10.0)
tb.set_geometry(100, 100, 80, 60)
check("default is rectangle", tb.corner_radius == 0.0 and tb._eff_radius() == 0.0)
tb.set_corner_radius(15.0)
check("radius set", tb.corner_radius == 15.0 and tb._eff_radius() == 15.0)
tb.set_corner_radius(500.0)
check("eff radius clamped to half min side", tb._eff_radius() == 30.0)
tb.set_corner_radius(15.0)

# handle hit-testing (needs selection)
sc0 = PageScene(); sc0.addItem(tb); tb.setSelected(True)
hs = tb._handle_size()
check("diamond hit at (r,0)", tb._radius_handle_at(QPointF(15.0, 0.0)))
check("miss far away", not tb._radius_handle_at(QPointF(50.0, 20.0)))
tb.set_corner_radius(0.0)
check("no diamond when rectangle", not tb._radius_handle_at(QPointF(0.0, 0.0)))
tb.set_corner_radius(15.0)

# simulated drag on the diamond
ev = QtWidgets.QGraphicsSceneMouseEvent(QtCore.QEvent.Type.GraphicsSceneMousePress)
ev.setPos(QPointF(15.0, 0.0)); ev.setButton(Qt.MouseButton.LeftButton)
ev.setModifiers(Qt.KeyboardModifier.NoModifier)
tb.mousePressEvent(ev)
check("press grabs diamond", tb._adj_radius)
mv = QtWidgets.QGraphicsSceneMouseEvent(QtCore.QEvent.Type.GraphicsSceneMouseMove)
mv.setPos(QPointF(22.0, 3.0)); mv.setModifiers(Qt.KeyboardModifier.NoModifier)
tb.mouseMoveEvent(mv)
check("drag sets radius from x", abs(tb.corner_radius - 22.0) < 1e-9, str(tb.corner_radius))
rl = QtWidgets.QGraphicsSceneMouseEvent(QtCore.QEvent.Type.GraphicsSceneMouseRelease)
rl.setPos(QPointF(22.0, 3.0)); rl.setButton(Qt.MouseButton.LeftButton)
tb.mouseReleaseEvent(rl)
check("release ends drag", not tb._adj_radius)
sc0.removeItem(tb)

# ------------------------------------------------------- panel integration
win = MainWindow()
win.scene.addItem(tb)
tb.set_corner_radius(0.0)
win.scene.clearSelection(); tb.setSelected(True)
pan = win.properties
check("panel shows Rectangle", pan.cmb_shape.currentIndex() == 0)
pan.cmb_shape.setCurrentIndex(1)          # -> rounded, default 2 mm
check("combo to rounded sets 2 mm", abs(tb.corner_radius - MM(2.0)) < 1e-6,
      str(tb.corner_radius))
pan.spin_radius.setValue(4.0); pan._apply_frame()
check("radius spin applies 4 mm", abs(tb.corner_radius - MM(4.0)) < 1e-6)
win.undo_stack.undo()
check("undo radius spin", abs(tb.corner_radius - MM(2.0)) < 1e-6)
pan.cmb_shape.setCurrentIndex(0)
check("combo to rectangle -> 0", tb.corner_radius == 0.0)
win.undo_stack.undo()
check("undo back to rounded", abs(tb.corner_radius - MM(2.0)) < 1e-6)

# scene undo hook for the diamond
win.scene.push_radius_undo(tb, tb.corner_radius, 12.0)
check("push_radius_undo applies", tb.corner_radius == 12.0)
win.undo_stack.undo()
check("push_radius_undo undoes", abs(tb.corner_radius - MM(2.0)) < 1e-6)

# --------------------------------------------------- project + clone round
tb.set_corner_radius(9.0)
tb.fill = True; tb.fill_opacity = 0.7
d = tb.to_dict()
tb2 = TextBoxItem.from_dict(d)
check("dict roundtrip keeps radius", tb2.corner_radius == 9.0)
tmp = tempfile.mkdtemp(prefix="ff_rr_")
proj = os.path.join(tmp, "r.ffp")
project.save_project(proj, win.scene)
cfg, loaded, td = project.load_project(proj)
lt = [x for x in loaded if isinstance(x, TextBoxItem)]
check("project roundtrip keeps radius", lt and lt[0].corner_radius == 9.0)
project.cleanup_tempdir(td)
dup = win._clone_item(tb)
check("clone keeps radius + opacity", dup.corner_radius == 9.0
      and abs(dup.fill_opacity - 0.7) < 1e-9)

# ------------------------------------------------------------- export check
_keep_scenes = []
def render_box(radius):
    sc = PageScene()
    _keep_scenes.append(sc)   # pin: avoid GC-order teardown noise
    b = TextBoxItem(text="R", size_pt=10.0)
    b.border = True; b.border_width = 1.0
    b.fill = True; b.fill_color = QtGui.QColor(120, 170, 255)
    b.set_geometry(100, 100, 80, 60)
    b.corner_radius = radius
    sc.addItem(b)
    p = os.path.join(tmp, f"r{int(radius)}.pdf")
    exporters.export_pdf(sc, p)
    doc = fitz.open(p)
    txt = doc[0].get_text().strip()
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(4, 4))
    def px(sx, sy):
        return pix.pixel(int(sx * 4), int(sy * 4))[:3]
    corner = px(101.5, 101.5)       # just inside the sharp corner
    edge_mid = px(140, 100.6)       # top edge midpoint (border)
    inside = px(140, 130)           # centre (fill)
    doc.close()
    return txt, corner, edge_mid, inside

txt_r, corner_r, edge_r, inside_r = render_box(15.0)
txt_s, corner_s, edge_s, inside_s = render_box(0.0)
check("rounded: text exported", "R" in txt_r, txt_r)
check("rounded: corner is page white (cut away)", all(c > 240 for c in corner_r),
      str(corner_r))
check("square: corner is filled/bordered", any(c < 240 for c in corner_s),
      str(corner_s))
check("rounded: border on edge midpoint", sum(edge_r) < 450, str(edge_r))
check("both: fill inside", inside_r[2] > 200 and inside_s[2] > 200,
      f"{inside_r} {inside_s}")

# rotated rounded export doesn't crash and keeps text
sc = PageScene()
b = TextBoxItem(text="Rot", size_pt=8.0)
b.set_geometry(150, 150, 90, 50)
b.corner_radius = 10.0
sc.addItem(b)
b.set_state((150, 150, 90, 50, 30.0))
p = os.path.join(tmp, "rot.pdf")
exporters.export_pdf(sc, p)
doc = fitz.open(p)
check("rotated rounded exports", "Rot" in doc[0].get_text())
doc.close()

win.undo_stack.cleanChanged.disconnect()
n_fail = sum(1 for ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} passed")
sys.exit(1 if n_fail else 0)
