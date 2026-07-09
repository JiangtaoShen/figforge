import os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
from figforge import i18n
from figforge.ui.arrange_dialog import ArrangeGridDialog

# real dialog, en
d = ArrangeGridDialog(None, 7)
r, c, hg, vg, same = d.values()
assert r * c >= 7, (r, c)
assert abs(hg - vg) < 1e-9 and hg > 5.6, (hg, vg)
# rows*cols auto-fix when user shrinks columns
d.spin_cols.setValue(2)
r, c, *_ = d.values()
assert r * c >= 7, (r, c)
print("dialog en OK", r, c)

# zh UI full boot
i18n.set_language("zh")
from figforge.main_window import MainWindow
w = MainWindow()
assert w.a_grid_arrange.text() == "网格排版…", w.a_grid_arrange.text()
assert w.a_lock.text() == "锁定"
assert w.m_recent.title() == "最近打开"
d2 = ArrangeGridDialog(None, 4)
assert d2.windowTitle() == "网格排版"
w.undo_stack.cleanChanged.disconnect()
print("zh UI OK")
