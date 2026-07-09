# Cross-platform font resolution + PDF font subsetting.
# The "this machine" section adapts to the OS the suite runs on (CI runs it
# on Windows, macOS and Ubuntu); the simulated-Linux section runs everywhere.
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from figforge import fonts  # noqa: E402
from figforge.canvas.scene import PageScene  # noqa: E402
from figforge.canvas.items import TextBoxItem, LabelItem  # noqa: E402
from figforge.fileio import exporters  # noqa: E402
import fitz  # noqa: E402

results = []


def check(name, cond, extra=""):
    results.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name
          + ((" -- " + extra) if (extra and not cond) else ""))


# ------------------------------------------------------------- this machine
fams = fonts.available_families()
check("families available", len(fams) >= 3, str(fams))
check("base-14 names always offered",
      all(f in fams for f in ("Helvetica", "Times", "Courier")))
rf = fonts.resolve_export_font("Nonexistent Family", False, True)
check("unknown family -> base14 italic", rf.fontfile is None and rf.fontname == "heit")
rf = fonts.resolve_export_font("Helvetica", True, False, "latin")
check("Helvetica -> base14 bold", rf.fontfile is None and rf.fontname == "hebo")

if sys.platform.startswith("win"):
    check("win: Arial + YaHei available",
          "Arial" in fams and "Microsoft YaHei" in fams, str(fams))
    rf = fonts.resolve_export_font("Arial", False, False, "abc")
    check("win: Arial resolves to file",
          rf.fontfile and rf.fontfile.lower().endswith("arial.ttf"), str(rf))
elif sys.platform == "darwin":
    rf = fonts.resolve_export_font("Arial", False, False, "abc")
    check("mac: Arial resolves to a file (Supplemental)",
          rf.fontfile is not None, str(rf))
else:
    # CI installs fonts-dejavu-core on Ubuntu
    check("linux: DejaVu Sans found", "DejaVu Sans" in fams, str(fams))
    rf = fonts.resolve_export_font("DejaVu Sans", False, False, "abc")
    check("linux: DejaVu resolves to file", rf.fontfile is not None, str(rf))

cjk_file = fonts._cjk_fontfile(False)
# Windows/macOS ship CJK fonts; CI installs fonts-noto-cjk on Ubuntu.
check("CJK fallback font found on this machine", cjk_file is not None,
      f"platform={sys.platform}")
if cjk_file:
    rf = fonts.resolve_export_font("Arial", True, False, "中文")
    check("CJK fallback used for Chinese text",
          rf.fontfile is not None and "cjk" in rf.fontname.lower(), str(rf))

# ------------------------------------- simulated Linux-like font environment
fake = tempfile.mkdtemp(prefix="ff_fonts_")
os.makedirs(os.path.join(fake, "truetype", "noto"), exist_ok=True)
open(os.path.join(fake, "DejaVuSans.ttf"), "wb").write(b"x")
open(os.path.join(fake, "truetype", "noto", "NotoSansCJKsc-Regular.otf"),
     "wb").write(b"x")
orig_dirs = fonts._font_dirs
fonts._font_dirs = lambda: [fake]
fonts._font_index.cache_clear()
try:
    fams2 = fonts.available_families()
    check("fake env: DejaVu + Noto CJK found, Arial hidden",
          "DejaVu Sans" in fams2 and "Noto Sans CJK SC" in fams2
          and "Arial" not in fams2, str(fams2))
    check("fake env: base14 names still offered",
          all(f in fams2 for f in ("Helvetica", "Times", "Courier")))
    rf = fonts.resolve_export_font("Arial", False, False, "abc")
    check("fake env: Arial latin -> base14",
          rf.fontfile is None and rf.fontname == "helv")
    rf = fonts.resolve_export_font("Arial", False, False, "中文标注")
    check("fake env: CJK falls back to Noto (recursive scan)",
          rf.fontfile
          and rf.fontfile.lower().endswith("notosanscjksc-regular.otf"), str(rf))
    rf = fonts.resolve_export_font("DejaVu Sans", True, False, "abc")
    check("fake env: missing bold falls back to regular file",
          rf.fontfile and rf.fontfile.lower().endswith("dejavusans.ttf"), str(rf))
finally:
    fonts._font_dirs = orig_dirs
    fonts._font_index.cache_clear()

# --------------------------------------------------- font subsetting on export
if cjk_file:
    sc = PageScene()
    tb = TextBoxItem(text="子集化测试：只嵌入用到的字形。", size_pt=8.0)
    tb.set_geometry(80, 80, 200, 60)
    sc.addItem(tb)
    lab = LabelItem(text="图a 标注", size_pt=12.0)
    lab.set_geometry(80, 160, *lab.size())
    sc.addItem(lab)

    p_sub = tempfile.mktemp(suffix=".pdf")
    exporters.export_pdf(sc, p_sub)
    size_sub = os.path.getsize(p_sub)

    out, keep = exporters.build_document(sc)      # same page, no subsetting
    p_raw = tempfile.mktemp(suffix=".pdf")
    out.save(p_raw, garbage=4, deflate=True, clean=True)
    exporters._close(out, keep)
    size_raw = os.path.getsize(p_raw)

    doc = fitz.open(p_sub)
    txt = doc[0].get_text()
    doc.close()
    check("subset: chinese text intact", "子集化测试" in txt and "标注" in txt)
    check("subset: dramatically smaller",
          size_sub < size_raw / 5 and size_sub < 1_500_000,
          f"subset={size_sub / 1024:.0f}KB raw={size_raw / 1024:.0f}KB")
    print(f"      (sizes: subsetted {size_sub / 1024:.0f} KB"
          f" vs raw {size_raw / 1024 / 1024:.1f} MB)")
    os.unlink(p_sub)
    os.unlink(p_raw)
else:
    print("      (no CJK font on this machine - subsetting section skipped)")

n_fail = sum(1 for ok in results if not ok)
print(f"\n{len(results) - n_fail}/{len(results)} passed")
sys.exit(1 if n_fail else 0)
