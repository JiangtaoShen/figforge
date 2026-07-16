"""Record the README demo GIF by scripting a real FigForge window.

Opens a visible window for ~30 s, performs import -> arrange-in-grid ->
labels -> annotation, grabbing a frame after each step, then writes
docs/demo.gif (960 px wide).

Run:  py scripts/make_demo_gif.py
"""
from __future__ import annotations

import io as _io
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["FIGFORGE_NO_UPDATE_CHECK"] = "1"
os.environ["FIGFORGE_AUTOSAVE_DIR"] = tempfile.mkdtemp(prefix="ff_gif_")

from PIL import Image  # noqa: E402
from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from make_sample import grid_geometry, make_panel_pdfs  # noqa: E402

app = QtWidgets.QApplication([])

from figforge import constants, i18n  # noqa: E402

i18n.set_language("en")                      # README audience

from figforge.canvas.items import LabelItem, LineItem, TextBoxItem  # noqa: E402
from figforge.main_window import MainWindow  # noqa: E402

mm = constants.mm_to_pt

win = MainWindow()
win._skip_restore = True
win._autosave_timer.stop()
win.move(60, 60)
win.show()

frames: list[Image.Image] = []
durations: list[int] = []


def snap(hold_ms: int = 80, n: int = 1) -> None:
    for _ in range(3):
        app.processEvents()
    pm = win.grab()
    buf = QtCore.QBuffer()
    buf.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    pm.toImage().save(buf, "PNG")
    img = Image.open(_io.BytesIO(bytes(buf.data()))).convert("RGB")
    img.thumbnail((960, 10_000), Image.LANCZOS)
    for _ in range(n):
        frames.append(img)
        durations.append(hold_ms)


def tween(items_states, steps=22, hold_ms=45):
    """items_states: [(item, from_state, to_state)]; animate + snap frames."""
    win.scene.snap_enabled = False
    for k in range(1, steps + 1):
        t = k / steps
        e = t * t * (3 - 2 * t)                    # smoothstep
        for it, a, b in items_states:
            st = tuple(av + (bv - av) * e for av, bv in zip(a, b))
            it.set_state(st)
        snap(hold_ms)
    win.scene.snap_enabled = True


# 1) empty page
snap(600, 2)

# 2) panels appear near the top-left (import)
paths = make_panel_pdfs(os.path.join(tempfile.mkdtemp(prefix="ff_gifassets_")))
figs = win.add_figures_from_paths(paths)
win.scene.clearSelection()
for f in figs:
    f.setSelected(True)
snap(900, 2)

# 3) fly into the 2x2 grid
rects = grid_geometry()
moves = []
for f, (x, y, w, h) in zip(figs, rects):
    a = f.get_state()
    moves.append((f, a, (x, y, w, h, 0.0)))
tween(moves)
win.scene.clearSelection()
snap(800, 2)

# 4) panel labels a-d pop in
for label, (x, y, _w, _h) in zip("abcd", rects):
    lab = LabelItem(text=label, family="Arial", size_pt=14.0, bold=True)
    lab.set_name(f"Label {label}")
    lab.set_geometry(x - mm(1), y - mm(7), *lab.size())
    lab.setZValue(win.scene.next_z())
    win._register_new_item(lab)
    win.scene.addItem(lab)
    snap(260)
snap(700, 2)

# 5) rounded annotation box + arrow
tb = TextBoxItem(text="Group 2 vs 4: p < 0.05 (n = 42)",
                 family="Arial", size_pt=8.0)
tb.set_name("Text Box 1")
tb.corner_radius = mm(1.5)
tb.border_width = 0.8
tb.pad_left = tb.pad_right = tb.pad_top = tb.pad_bottom = mm(1.2)
x4, y4, w4, h4 = rects[3]
tb.set_geometry(x4 + w4 * 0.10, y4 + h4 + mm(12), mm(58), mm(9))
tb.setZValue(win.scene.next_z())
win._register_new_item(tb)
win.scene.addItem(tb)
tb.setSelected(True)
snap(900, 2)

ln = LineItem(color=QtGui.QColor(40, 40, 40), width_pt=0.9, arrow="end")
ln.set_name("Line 1")
ln.setZValue(win.scene.next_z())
win._register_new_item(ln)
win.scene.addItem(ln)
ln.setPos(0, 0)
ln.p1 = QtCore.QPointF(tb.pos().x() + mm(29), tb.pos().y())
ln.p2 = QtCore.QPointF(x4 + w4 * 0.82, y4 + h4 * 0.55)
ln.anchor1 = {"uid": tb.uid, "node": "n"}
ln.update_anchors(win.scene)
win.scene.clearSelection()
snap(900, 2)

# 6) final hold
snap(2400, 2)

# ---- assemble --------------------------------------------------------------
out = os.path.join(ROOT, "docs", "demo.gif")
ref = frames[len(frames) // 2].convert("P", palette=Image.Palette.ADAPTIVE,
                                        colors=160)
pal = [f.convert("RGB").quantize(palette=ref, dither=Image.Dither.NONE)
       for f in frames]
pal[0].save(out, save_all=True, append_images=pal[1:], duration=durations,
            loop=0, optimize=True)
print("frames:", len(frames), "->", out,
      f"{os.path.getsize(out) / 1024 / 1024:.2f} MB")

win.undo_stack.cleanChanged.disconnect()
win._clear_autosave()
app.quit()
