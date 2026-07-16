# Bundled sample project + update-check logic.
import os
import sys
import tempfile
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("FIGFORGE_AUTOSAVE_DIR",
                      tempfile.mkdtemp(prefix="ff_su_"))
os.environ["FIGFORGE_NO_UPDATE_CHECK"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from figforge.main_window import MainWindow  # noqa: E402
from figforge.canvas.items import (FigureItem, LabelItem, LineItem,  # noqa: E402
                                   TextBoxItem)
from figforge import update_check  # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name
          + ((" -- " + extra) if (extra and not cond) else ""))


# ------------------------------------------------------------ sample project
sample = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "figforge", "resources", "sample.ffp")
check("sample.ffp is bundled", os.path.isfile(sample)
      and os.path.getsize(sample) < 200_000, sample)

win = MainWindow()
win.open_sample()
items = win.scene.iter_items()
figs = [i for i in items if isinstance(i, FigureItem)]
labs = [i for i in items if isinstance(i, LabelItem)]
tbs = [i for i in items if isinstance(i, TextBoxItem)]
lines = [i for i in items if isinstance(i, LineItem)]
check("sample: 4 panels", len(figs) == 4, str(len(figs)))
check("sample: labels a-d", sorted(l.text for l in labs) == ["a", "b", "c", "d"])
check("sample: rounded annotation box", len(tbs) == 1
      and tbs[0].corner_radius > 0)
check("sample: connector arrow anchored", len(lines) == 1
      and lines[0].arrow == "end" and lines[0].anchor1)
check("sample: panels are vector", all(f._source_kind == "vector" for f in figs))
check("sample opens untitled + clean", win.current_path is None
      and not win._is_dirty())

# the sample must round-trip through export
import figforge.fileio.exporters as exporters  # noqa: E402
import fitz  # noqa: E402

pdf = tempfile.mktemp(suffix=".pdf")
exporters.export_pdf(win.scene, pdf)
doc = fitz.open(pdf)
txt = doc[0].get_text()
flat = "".join(txt.split())      # PDF spacing reconstruction varies
check("sample exports (labels + annotation in PDF)",
      all(ch in flat for ch in "abcd") and "n=42" in flat and "*" in flat,
      txt[:80])
doc.close()
os.unlink(pdf)

# --------------------------------------------------------- version comparing
pv = update_check.parse_version
check("parse plain", pv("0.3.1") == (0, 3, 1))
check("parse v-prefix + prerelease", pv("v0.4.0-rc1") == (0, 4, 0))
check("parse short/malformed", pv("v1.2") == (1, 2, 0) and pv("junk") == (0, 0, 0))
new = update_check.is_newer
check("is_newer basics", new("v0.4.0", "0.3.1") and not new("v0.3.1", "0.3.1")
      and not new("v0.3.0", "0.3.1") and new("1.0.0", "0.9.9"))

# ------------------------------------------------- checker with fake network
calls = {}


class _FakeResp:
    def __init__(self, payload):
        self._p = payload

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


import urllib.request  # noqa: E402

orig_open = urllib.request.urlopen
urllib.request.urlopen = lambda req, timeout=0: _FakeResp(
    b'{"tag_name": "v9.9.9"}')
got = []
chk = update_check.UpdateChecker()
chk.updateAvailable.connect(lambda tag: got.append(tag))
chk.check("0.3.1")
for _ in range(300):
    app.processEvents()
    if got:
        break
    time.sleep(0.01)
urllib.request.urlopen = orig_open
check("checker emits updateAvailable for newer tag", got == ["v9.9.9"], str(got))

# auto-check is fully gated in tests (env + offscreen)
win._auto_update_check()
check("auto-check gated in tests", not hasattr(win, "_upd")
      and not win.lbl_update.isVisible())

win.undo_stack.cleanChanged.disconnect()
n_fail = sum(1 for ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} passed")
sys.exit(1 if n_fail else 0)
