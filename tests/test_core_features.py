# Headless verification for this optimization round:
# grid arrange, lock/unlock, crop-to-content export, i18n, recent files, Esc.
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name
          + ((" -- " + extra) if (extra and not cond) else ""))


from PIL import Image  # noqa: E402

tmp = tempfile.mkdtemp(prefix="ff_test_")
paths = []
for i, col in enumerate([(255, 0, 0), (0, 160, 0), (0, 0, 255),
                         (200, 200, 0), (0, 200, 200)]):
    p = os.path.join(tmp, f"im{i}.png")
    Image.new("RGB", (300, 200), col).save(p, dpi=(150, 150))
    paths.append(p)

from figforge.main_window import MainWindow, ExportDialog  # noqa: E402
from figforge.canvas.items import FigureItem, LineItem  # noqa: E402
from figforge.canvas.scene import PageScene  # noqa: E402
from figforge.fileio import exporters, importers, project  # noqa: E402
from figforge import constants, i18n  # noqa: E402

win = MainWindow()
items = win.add_figures_from_paths(paths)
check("import 5 figures", len(items) == 5)

# ---------------------------------------------------------------- grid arrange
import figforge.ui.arrange_dialog as ad  # noqa: E402


class FakeDlg:
    def __init__(self, parent, count):
        pass

    def exec(self):
        return QtWidgets.QDialog.DialogCode.Accepted

    def values(self):
        return (2, 3, constants.mm_to_pt(2), constants.mm_to_pt(2), True)


orig_dlg = ad.ArrangeGridDialog
ad.ArrangeGridDialog = FakeDlg
for it in items:
    it.setSelected(True)
win.arrange_grid()
ad.ArrangeGridDialog = orig_dlg

ws = {round(it.size()[0], 3) for it in items}
hs = {round(it.size()[1], 3) for it in items}
check("grid: uniform size", len(ws) == 1 and len(hs) == 1, f"{ws} {hs}")
xs = sorted({it.pos().x() for it in items})
ys = sorted({it.pos().y() for it in items})
check("grid: 3 distinct columns", len(xs) == 3, str(xs))
check("grid: 2 distinct rows", len(ys) == 2, str(ys))
w0, h0 = items[0].size()
gap = constants.mm_to_pt(2)
check("grid: column pitch", abs((xs[1] - xs[0]) - (w0 + gap)) < 1e-6
      and abs((xs[2] - xs[1]) - (w0 + gap)) < 1e-6,
      f"{[xs[1] - xs[0], xs[2] - xs[1]]} vs {w0 + gap}")
check("grid: row pitch", abs((ys[1] - ys[0]) - (h0 + gap)) < 1e-6,
      f"{ys[1] - ys[0]} vs {h0 + gap}")

win.undo_stack.undo()
xs2 = sorted({round(it.pos().x(), 2) for it in items})
check("grid: undo restores positions", xs2 != xs, str(xs2))
win.undo_stack.redo()

# ------------------------------------------------------------------------ lock
it0 = items[0]
win.scene.clearSelection()
it0.setSelected(True)
win.lock_selected()
GF = QtWidgets.QGraphicsItem.GraphicsItemFlag
check("lock: flag set", it0.locked)
check("lock: not selectable", not (it0.flags() & GF.ItemIsSelectable))
check("lock: not movable", not (it0.flags() & GF.ItemIsMovable))
check("lock: deselected", not it0.isSelected())
it0.setSelected(True)
check("lock: setSelected ignored", not it0.isSelected())
win.layers.refresh()
row_texts = [win.layers.list.item(i).text() for i in range(win.layers.list.count())]
check("lock: layers shows padlock", any(t.startswith("\U0001F512") for t in row_texts),
      str(row_texts))
win.undo_stack.undo()
check("lock: undo unlocks", not it0.locked and bool(it0.flags() & GF.ItemIsMovable))
win.undo_stack.redo()
check("lock: redo locks", it0.locked)
win.unlock_all()
check("unlock all", not any(x.locked for x in win.scene.iter_items()))

# --------------------------------------------------- project roundtrip w/ lock
it0.set_locked(True)
line = LineItem()
line.set_name("L1")
win.scene.addItem(line)
line.set_locked(True)
proj = os.path.join(tmp, "t.ffp")
project.save_project(proj, win.scene)
cfg, loaded, td = project.load_project(proj)
lf = [x for x in loaded if isinstance(x, FigureItem) and x.locked]
ll = [x for x in loaded if isinstance(x, LineItem)]
check("project: locked figure persists", len(lf) == 1, str(len(lf)))
check("project: locked line persists", len(ll) == 1 and ll[0].locked)
check("project: line default name kept", ll[0].name() == "L1")
project.cleanup_tempdir(td)
line.set_locked(False)
win.scene.removeItem(line)
it0.set_locked(False)

# ------------------------------------------------- content rect + crop export
sc = PageScene()
src = importers.load_source(paths[0])
fig = FigureItem(src, name="f")
fig.set_geometry(100, 150, 200, 120)
sc.addItem(fig)
r = sc.content_rect()
check("content_rect", r is not None and abs(r.left() - 100) < 1e-6
      and abs(r.top() - 150) < 1e-6 and abs(r.width() - 200) < 1e-6
      and abs(r.height() - 120) < 1e-6, str(r))

import fitz  # noqa: E402

m = constants.mm_to_pt(1)
pdf_path = os.path.join(tmp, "crop.pdf")
exporters.export_pdf(sc, pdf_path, crop_margin_pt=m)
doc = fitz.open(pdf_path)
pr = doc[0].rect
check("crop pdf: page size == content + margin",
      abs(pr.width - (200 + 2 * m)) < 0.5 and abs(pr.height - (120 + 2 * m)) < 0.5,
      str(pr))
doc.close()

pdf2 = os.path.join(tmp, "full.pdf")
exporters.export_pdf(sc, pdf2)
doc = fitz.open(pdf2)
pr2 = doc[0].rect
check("no-crop pdf: full page",
      abs(pr2.width - sc.page_w) < 0.5 and abs(pr2.height - sc.page_h) < 0.5, str(pr2))
doc.close()

png_path = os.path.join(tmp, "crop.png")
exporters.export_png(sc, png_path, dpi=300, crop_margin_pt=m)
im = Image.open(png_path)
exp_w = round((200 + 2 * m) / 72 * 300)
exp_h = round((120 + 2 * m) / 72 * 300)
check("crop png: pixel size", abs(im.width - exp_w) <= 2 and abs(im.height - exp_h) <= 2,
      f"{im.size} vs {(exp_w, exp_h)}")
im.close()

ln = LineItem(p1=QtCore.QPointF(0, 0), p2=QtCore.QPointF(50, 0))
ln.setPos(400, 500)
sc.addItem(ln)
r2 = sc.content_rect()
check("content_rect includes line", r2.right() > 440 and r2.bottom() > 490, str(r2))

# rotated figure bbox grows
fig.set_state((100, 150, 200, 120, 30.0))
r3 = sc.content_rect()
check("content_rect: rotation grows bbox", r3.width() > 200 or r3.left() < 100, str(r3))
fig.set_state((100, 150, 200, 120, 0.0))

# ------------------------------------------------------------------------ i18n
new_keys = [
    "Arrange in Grid…", "Arrange in Grid", "Rows", "Columns",
    "Horizontal gap", "Vertical gap", "Lock", "Unlock All",
    "Open Recent", "Clear Menu", "(empty)", "Crop to content", "Content margin",
    "Add object", "Delete objects", "Move / Resize",
    "Unsupported file type: {0}", "File not found: {0}",
    "Select at least two images to arrange.",
    "Make all panels the same size as the first panel",
    "Panels are placed row by row in their current order (top-left first).",
    "Importing EPS/PS requires Ghostscript (gswin64c). Install "
    "Ghostscript, or convert the file to PDF/SVG first.",
]
missing = [k for k in new_keys if k not in i18n._ZH]
check("i18n: zh has all new keys", not missing, str(missing))

from figforge.commands import AddItemCommand, DeleteItemsCommand, GeometryCommand  # noqa: E402

i18n.set_language("en")
check("cmd text en", AddItemCommand(sc, fig).text() == "Add object",
      AddItemCommand(sc, fig).text())
check("cmd del en", DeleteItemsCommand(sc, [fig]).text() == "Delete objects")
check("cmd geom en", GeometryCommand(fig, None, None).text() == "Move / Resize")
i18n.set_language("zh")
check("cmd text zh", AddItemCommand(sc, fig).text() == "添加对象",
      AddItemCommand(sc, fig).text())
i18n.set_language("en")

# --------------------------------------------------------------- export dialog
d = ExportDialog(win, raster=False)
check("export dlg (pdf): no dpi widget, default dpi",
      d.cmb_dpi is None and d.dpi() == constants.DEFAULT_DPI)
check("export dlg: crop off by default", d.crop_margin_pt() is None)
d.chk_crop.setChecked(True)
d.spin_margin.setValue(2.0)
check("export dlg: crop margin value",
      abs(d.crop_margin_pt() - constants.mm_to_pt(2.0)) < 1e-9)
d2 = ExportDialog(win, raster=True, allow_transparent=False)
check("export dlg (tiff): dpi yes, transparent no",
      d2.cmb_dpi is not None and d2.chk_transparent is None and not d2.transparent())

# ---------------------------------------------------------------- recent files
s = QtCore.QSettings("FigForge", "FigForge")
saved = s.value("recent_files")
win._settings().setValue("recent_files", [])
ra, rb = os.path.join(tmp, "a.ffp"), os.path.join(tmp, "b.ffp")
win._add_recent(ra)
win._add_recent(rb)
win._add_recent(ra)
lst = win._recent_files()
check("recent: dedupe + newest first",
      [os.path.basename(p) for p in lst] == ["a.ffp", "b.ffp"], str(lst))
win._remove_recent(rb)
check("recent: remove", [os.path.basename(p) for p in win._recent_files()] == ["a.ffp"])
win._rebuild_recent_menu()
acts = [a.text() for a in win.m_recent.actions()]
check("recent: menu rebuilt", any("a.ffp" in t for t in acts), str(acts))
if saved is None:
    s.remove("recent_files")
else:
    s.setValue("recent_files", saved)

# -------------------------------------------------------------------- esc key
for x in win.scene.iter_items():
    x.setSelected(True)
ev = QtGui.QKeyEvent(QtCore.QEvent.Type.KeyPress, QtCore.Qt.Key.Key_Escape,
                     QtCore.Qt.KeyboardModifier.NoModifier)
win.view.keyPressEvent(ev)
check("esc clears selection", not win.scene.selectedItems())

n_fail = sum(1 for _, ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} passed")
win.undo_stack.cleanChanged.disconnect()   # avoid teardown-order noise
sys.exit(1 if n_fail else 0)
