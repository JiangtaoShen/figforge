# Autosave / crash recovery: snapshot when dirty, restore after a crash,
# cleared on save / new / clean exit; exception hook logs + rescues.
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("FIGFORGE_AUTOSAVE_DIR",
                      tempfile.mkdtemp(prefix="ff_as_"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtGui, QtWidgets  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from figforge import app as app_mod  # noqa: E402
from figforge.main_window import MainWindow  # noqa: E402
from figforge.canvas.items import TextBoxItem  # noqa: E402
from figforge.commands import AddItemCommand  # noqa: E402
from PIL import Image  # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name
          + ((" -- " + extra) if (extra and not cond) else ""))


def add_box(win, text):
    box = TextBoxItem(text=text, size_pt=6.0)
    box.set_geometry(80, 80, 120, 60)
    win._register_new_item(box)
    win.undo_stack.push(AddItemCommand(win.scene, box))
    return box


tmp = tempfile.mkdtemp(prefix="ff_as_data_")

# ------------------------------------------------------------ snapshotting
win = MainWindow()
win._clear_autosave()
win._do_autosave()
check("clean session: no snapshot", win._pending_autosave() is None)

add_box(win, "recover me")
check("dirty after add", win._is_dirty())

calls = []
import figforge.main_window as mw  # noqa: E402
orig_save = mw.project.save_project
mw.project.save_project = lambda *a, **k: (calls.append(1), orig_save(*a, **k))[1]
win._do_autosave()
check("snapshot written when dirty", win._pending_autosave() is not None
      and len(calls) == 1)
win._do_autosave()
check("no rewrite without new edits", len(calls) == 1)
add_box(win, "second")
win._do_autosave()
check("rewrites after further edits", len(calls) == 2)
mw.project.save_project = orig_save

ffp, info = win._pending_autosave()
check("meta records unsaved project", info.get("original_path") == ""
      and info.get("saved_at"), str(info))

# --------------------------------------------------- restore after a crash
# simulate a crash: win simply abandoned (no clean exit); new session starts
win2 = MainWindow()
check("new session sees pending autosave", win2._pending_autosave() is not None)
ok = win2._restore_autosave()
boxes = [it for it in win2.scene.iter_items() if isinstance(it, TextBoxItem)]
texts = {b.text for b in boxes}
check("restore loads the work", ok and {"recover me", "second"} <= texts,
      str(texts))
check("restored session is dirty (needs saving)", win2._is_dirty())
check("restored has no file path", win2.current_path is None)
check("autosave consumed after restore", win2._pending_autosave() is None)

# ------------------------------------------------------- clearing lifecycle
win2.rescue_autosave()
check("rescue writes immediately", win2._pending_autosave() is not None)
proj = os.path.join(tmp, "saved.ffp")
win2.current_path = proj
check("manual save clears autosave", win2.save_project()
      and win2._pending_autosave() is None)

win2.rescue_autosave()
win2.undo_stack.setClean()
win2._extra_dirty = False
win2.new_project()
check("new project clears autosave", win2._pending_autosave() is None)

win2.rescue_autosave() if win2.scene.iter_items() else None
add_box(win2, "for close")
win2.rescue_autosave()
win2.undo_stack.setClean()
ev = QtGui.QCloseEvent()
win2.closeEvent(ev)
check("clean close clears autosave", ev.isAccepted()
      and win2._pending_autosave() is None)

# ------------------------------------------------------------ excepthook
win3 = MainWindow()
add_box(win3, "hook rescue")
shown = []
orig_crit = QtWidgets.QMessageBox.critical
QtWidgets.QMessageBox.critical = lambda *a, **k: shown.append(a[2] if len(a) > 2 else "")
orig_hook = sys.excepthook
try:
    app_mod.install_excepthook(win3)
    try:
        raise ValueError("boom for test")
    except ValueError:
        sys.excepthook(*sys.exc_info())
finally:
    QtWidgets.QMessageBox.critical = orig_crit
    sys.excepthook = orig_hook

log = os.path.join(win3._autosave_dir(), "error.log")
check("hook writes traceback log", os.path.isfile(log)
      and "boom for test" in open(log, encoding="utf-8").read())
check("hook rescues the work", win3._pending_autosave() is not None)
check("hook informs the user", len(shown) == 1 and "error.log" in shown[0],
      str(shown))
win3._clear_autosave()

for w in (win, win2, win3):
    try:
        w.undo_stack.cleanChanged.disconnect()
    except (RuntimeError, TypeError):
        pass

n_fail = sum(1 for ok_ in results if not ok_)
print(f"\n{len(results) - n_fail}/{len(results)} passed")
sys.exit(1 if n_fail else 0)
