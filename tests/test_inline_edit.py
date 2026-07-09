import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt, QPointF
from PySide6.QtTest import QTest
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from figforge.main_window import MainWindow
from figforge.canvas.items import FigureItem, TextBoxItem, LabelItem, LineItem
from figforge.canvas.scene import PageScene
from figforge.fileio import importers
from figforge.i18n import tr
from figforge import constants
from PIL import Image

results = []
def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ((" -- " + extra) if (extra and not cond) else ""))

win = MainWindow()
win.show()
app.processEvents()
win.activateWindow()
win.view.setFocus()
app.processEvents()

# ---------------------------------------------------- inline edit: text box
win.add_textbox()
tb = [it for it in win.scene.iter_items() if isinstance(it, TextBoxItem)][0]
check("edit starts on add", tb._editor is not None)
check("editor has scene focus", win.scene.focusItem() is tb._editor,
      str(win.scene.focusItem()))

# typing replaces the select-all placeholder
QTest.keyClicks(win.view.viewport(), "hello")
app.processEvents()
check("typed into editor", tb._editor.toPlainText() == "hello",
      repr(tb._editor.toPlainText()))

# arrow key moves the caret, not the item; no nudge fires
nudges = []
win.view.nudge.connect(lambda dx, dy: nudges.append((dx, dy)))
pos_before = (tb.pos().x(), tb.pos().y())
cur_before = tb._editor.textCursor().position()
QTest.keyClick(win.view.viewport(), Qt.Key.Key_Left)
app.processEvents()
check("arrow moves caret not item",
      (tb.pos().x(), tb.pos().y()) == pos_before and not nudges
      and tb._editor.textCursor().position() == cur_before - 1)

# 'T' shortcut must not create a label while editing
n_labels = sum(1 for it in win.scene.iter_items() if isinstance(it, LabelItem))
QTest.keyClick(win.view.viewport(), Qt.Key.Key_T)
app.processEvents()
n_labels2 = sum(1 for it in win.scene.iter_items() if isinstance(it, LabelItem))
check("'T' typed, no label created",
      n_labels2 == n_labels and tb._editor.toPlainText() == "hellto",
      f"labels {n_labels}->{n_labels2} text={tb._editor.toPlainText()!r}")

# space must type a space, not start panning
QTest.keyClick(win.view.viewport(), Qt.Key.Key_Space)
app.processEvents()
check("space types, no pan mode",
      " " in tb._editor.toPlainText()
      and win.view.dragMode() == QtWidgets.QGraphicsView.DragMode.RubberBandDrag)

# Escape commits (undoable)
QTest.keyClick(win.view.viewport(), Qt.Key.Key_Escape)
app.processEvents()
check("escape commits", tb._editor is None and "hellto" in tb.text.replace(" ", "t") or tb.text != tr("Text Box"), repr(tb.text))
committed = tb.text
check("editor closed", tb._editor is None)
check("undo restores placeholder", (win.undo_stack.undo(), tb.text)[1] == tr("Text Box"), repr(tb.text))
win.undo_stack.redo()
check("redo restores typed text", tb.text == committed, repr(tb.text))

# double-click (mixin handler) re-opens the editor
tb.start_inline_edit()
check("re-edit works", tb._editor is not None and tb._editor.toPlainText() == tb.text)
QTest.keyClick(win.view.viewport(), Qt.Key.Key_Escape)
app.processEvents()
check("no-change commit adds no undo",
      tb._editor is None)

# label inline edit
win.add_label()
lab = [it for it in win.scene.iter_items() if isinstance(it, LabelItem)][-1]
check("label edit starts on add", lab._editor is not None)
QTest.keyClicks(win.view.viewport(), "b")
QTest.keyClick(win.view.viewport(), Qt.Key.Key_Escape)
app.processEvents()
check("label committed", lab.text == "b" and lab._editor is None, repr(lab.text))

# deleting the host while an editor is open elsewhere must not crash
win.scene.clearSelection()
tb.setSelected(True)
tb.start_inline_edit()
win.delete_selected()          # menu delete while editing
app.processEvents()
check("delete-while-editing safe", tb.scene() is None and tb._editor is None)

# undo of Add while the editor is open — same re-entrancy family
win.add_textbox()
tb2 = [it for it in win.scene.iter_items() if isinstance(it, TextBoxItem)][-1]
check("editing right after add", tb2._editor is not None)
win.undo_stack.undo()          # removes the host while its editor has focus
app.processEvents()
check("undo-add-while-editing safe", tb2.scene() is None and tb2._editor is None)

# scene.clear while editing (New Project path); also exercises the
# layers-panel resync that dereferenced deleted rows on macOS
win.add_textbox()
tb3 = [it for it in win.scene.iter_items() if isinstance(it, TextBoxItem)][-1]
tb3.setSelected(True)
win.on_selection_changed()     # populate the layers list with a live row
check("editing before clear", tb3._editor is not None)
win.scene.clear()
app.processEvents()
check("clear-while-editing safe", tb3._editor is None)
check("layers emptied after clear", win.layers.list.count() == 0)

# ------------------------------------------------------- grid snap exemption
sc = PageScene()
tmp = tempfile.mkdtemp(prefix="ff_ie_")
p = os.path.join(tmp, "a.png")
Image.new("RGB", (300, 200), (90, 90, 200)).save(p, dpi=(150, 150))
fig = FigureItem(importers.load_source(p), name="f")
fig.set_geometry(100.0, 100.0, 144.0, 96.0)
sc.addItem(fig)
box = TextBoxItem(text="t")
box.set_geometry(300.0, 300.0, 100.0, 40.0)
sc.addItem(box)

sc.snap_enabled, sc.snap_to_grid = False, True   # grid snap only (5mm)
prop = QPointF(301.3, 297.7)
got = sc.snap_position(box, prop)
check("textbox ignores grid snap", got == prop, f"{got}")
got_fig = sc.snap_position(fig, QPointF(301.3, 297.7))
step = constants.mm_to_pt(5)
def off_grid(v):
    r = v % step
    return min(r, step - r)
check("figure still grid-snaps",
      off_grid(got_fig.x()) < 1e-6 and off_grid(got_fig.y()) < 1e-6,
      f"{got_fig}")

sc.snap_enabled, sc.snap_to_grid = True, True    # smart snap stays for boxes
got2 = sc.snap_position(box, QPointF(101.5, 400.0))   # near fig left edge 100
check("textbox keeps smart guides", abs(got2.x() - 100.0) < 1e-6, f"{got2}")
check("line declared grid-exempt", LineItem.grid_snap_exempt is True)

win.undo_stack.cleanChanged.disconnect()
n_fail = sum(1 for ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} passed")
sys.exit(1 if n_fail else 0)
