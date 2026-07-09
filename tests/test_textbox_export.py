import os, sys, tempfile
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from figforge.canvas.scene import PageScene
from figforge.canvas.items import TextBoxItem
from figforge.fileio import exporters
import fitz

fails = 0

def run(name, text, w, h, s, rot=0.0, border=True):
    global fails
    sc = PageScene()
    tb = TextBoxItem(text=text, size_pt=s)
    tb.border = border
    tb.set_geometry(50, 50, w, h)
    sc.addItem(tb)
    if rot:
        tb.set_state((50, 50, w, h, rot))
    p = tempfile.mktemp(suffix=".pdf")
    exporters.export_pdf(sc, p)
    doc = fitz.open(p)
    got = " ".join(doc[0].get_text().split())
    # pixel check at 4x zoom
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(4, 4))
    import collections
    def dark_in(x0, y0, x1, y1):
        n = 0
        for yy in range(int(y0*4), min(int(y1*4), pix.height)):
            for xx in range(int(x0*4), min(int(x1*4), pix.width)):
                r, g, b = pix.pixel(xx, yy)[:3]
                if r < 128 and g < 128 and b < 128:
                    n += 1
        return n
    inside = dark_in(52, 52, 50+w-2, 50+h-2)
    below = dark_in(50, 50+h+3, 50+w, 50+h+40) if rot == 0 else 0
    doc.close(); os.unlink(p)
    ok_text = (not text.strip()) or (text.split()[0] in got)
    ok_pix = inside > 10
    ok_clip = below == 0
    ok = ok_text and ok_pix and ok_clip
    if not ok:
        fails += 1
    print(f"{'OK  ' if ok else 'FAIL'} {name:20s} text={ok_text} glyphs_inside={inside} leak_below={below}")

run("big box en 4pt",  "Hello world", 170, 90, 4.0)
run("snug box en 4pt", "Hello world", 170, 11, 4.0)
run("very snug h=9",   "Hello world", 170, 9, 4.0)
run("multi-line 14pt", "line one\nline two\nline three\nline four\nline five\nline six", 170, 90, 14.0)
run("big box zh",      "文本框测试", 170, 90, 4.0)
run("snug box zh",     "文本框测试", 170, 11, 4.0)
run("rotated snug",    "Hello world", 170, 11, 4.0, rot=30.0)
run("paragraph tiny",  "A rather long paragraph that wraps onto many lines when the box is narrow " * 3, 60, 20, 6.0)
run("no border snug",  "Hello world", 170, 11, 4.0, border=False)

print(f"\n{'ALL OK' if fails == 0 else str(fails) + ' FAILURES'}")
sys.exit(1 if fails else 0)
