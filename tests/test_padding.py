import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6 import QtWidgets
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

# defaults keep old behavior
tb = TextBoxItem(text="X", size_pt=10.0)
check("defaults are PAD=4pt each",
      (tb.pad_left, tb.pad_top, tb.pad_right, tb.pad_bottom) == (4.0, 4.0, 4.0, 4.0))
check("editor pads follow instance", tb._edit_pads() == (4.0, 4.0, 4.0))
tb.apply_style(pad_left=20.0, pad_top=15.0, pad_right=6.0, pad_bottom=2.0)
check("apply_style sets pads", (tb.pad_left, tb.pad_top, tb.pad_right,
                                tb.pad_bottom) == (20.0, 15.0, 6.0, 2.0))
check("editor pads updated", tb._edit_pads() == (20.0, 15.0, 6.0))

# dict + project roundtrip
d = tb.to_dict()
tb2 = TextBoxItem.from_dict(d)
check("dict roundtrip", (tb2.pad_left, tb2.pad_top, tb2.pad_right,
                         tb2.pad_bottom) == (20.0, 15.0, 6.0, 2.0))
old = {k: v for k, v in d.items() if not k.startswith("pad_")}
tb3 = TextBoxItem.from_dict(old)        # legacy project without pads
check("legacy project defaults to 4pt", tb3.pad_left == 4.0 and tb3.pad_bottom == 4.0)

# export: word position shifts with padding
def word_pos(pl, pt_):
    sc = PageScene()
    b = TextBoxItem(text="X", size_pt=10.0)
    b.set_geometry(100, 100, 120, 80)
    b.apply_style(pad_left=pl, pad_top=pt_)
    sc.addItem(b)
    p = tempfile.mktemp(suffix=".pdf")
    exporters.export_pdf(sc, p)
    doc = fitz.open(p)
    words = doc[0].get_text("words")
    doc.close(); os.unlink(p)
    return (words[0][0], words[0][1]) if words else (None, None)

x4, y4 = word_pos(4.0, 4.0)
x20, y16 = word_pos(20.0, 16.0)
check("pad_left shifts text right", x4 is not None and abs((x20 - x4) - 16.0) < 1.0,
      f"{x4} -> {x20}")
check("pad_top shifts text down", y4 is not None and abs((y16 - y4) - 12.0) < 1.5,
      f"{y4} -> {y16}")

# big pads + snug box still export text (retry path)
sc = PageScene()
b = TextBoxItem(text="Hello world", size_pt=4.0)
b.set_geometry(100, 100, 170, 12)
b.apply_style(pad_left=8.0, pad_top=8.0, pad_right=8.0, pad_bottom=8.0)
sc.addItem(b)
p = tempfile.mktemp(suffix=".pdf")
exporters.export_pdf(sc, p)
doc = fitz.open(p)
check("snug box + pads keeps text", "Hello" in doc[0].get_text())
doc.close(); os.unlink(p)

# panel round trip
win = MainWindow()
tb4 = TextBoxItem(text="p", size_pt=6.0)
tb4.set_geometry(50, 50, 100, 60)
win.scene.addItem(tb4)
tb4.setSelected(True)
pan = win.properties
check("panel loads pads (mm)", abs(pan.spin_pad_l.value() - 4.0 * constants.MM_PER_PT) < 0.05)
pan.spin_pad_l.setValue(3.0)   # mm
pan.spin_pad_t.setValue(1.0)
pan._apply_frame()
check("panel applies pads", abs(tb4.pad_left - MM(3.0)) < 1e-6
      and abs(tb4.pad_top - MM(1.0)) < 1e-6, f"{tb4.pad_left}")
win.undo_stack.undo()
check("undo restores pads", abs(tb4.pad_left - 4.0) < 1e-6)
win.undo_stack.redo()
check("redo reapplies", abs(tb4.pad_left - MM(3.0)) < 1e-6)

# clone keeps pads
dup = win._clone_item(tb4)
check("clone keeps pads", abs(dup.pad_left - MM(3.0)) < 1e-6
      and abs(dup.pad_top - MM(1.0)) < 1e-6)

# project save/load with pads
tmp = tempfile.mkdtemp(prefix="ff_pad_")
proj = os.path.join(tmp, "p.ffp")
project.save_project(proj, win.scene)
cfg, loaded, td = project.load_project(proj)
lt = [x for x in loaded if isinstance(x, TextBoxItem)]
check("project keeps pads", lt and abs(lt[0].pad_left - MM(3.0)) < 1e-6)
project.cleanup_tempdir(td)

# i18n
from figforge import i18n
check("i18n keys", "Padding L / R" in i18n._ZH and "Padding T / B" in i18n._ZH)

win.undo_stack.cleanChanged.disconnect()
n_fail = sum(1 for ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} passed")
sys.exit(1 if n_fail else 0)
