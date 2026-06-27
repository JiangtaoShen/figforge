"""Font resolution for label text.

On screen we render labels with Qt (by family name). On export we want the
PDF to look identical, so we embed the *actual* TrueType file when we can find
it, and fall back to a metrically-similar PDF base-14 font otherwise.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

_WINDIR = os.environ.get("WINDIR", r"C:\Windows")
_FONTDIR = os.path.join(_WINDIR, "Fonts")

# family -> (regular, bold, italic, bold_italic) filenames inside %WINDIR%\Fonts
_WIN_FONT_FILES = {
    "Arial":            ("arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
    "Times New Roman":  ("times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"),
    "Courier New":      ("cour.ttf", "courbd.ttf", "couri.ttf", "courbi.ttf"),
    "Calibri":          ("calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf"),
    "Cambria":          ("cambria.ttc", "cambriab.ttf", "cambriai.ttf", "cambriaz.ttf"),
    "Georgia":          ("georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf"),
    "Verdana":          ("verdana.ttf", "verdanab.ttf", "verdanai.ttf", "verdanaz.ttf"),
    "Tahoma":           ("tahoma.ttf", "tahomabd.ttf", "tahoma.ttf", "tahomabd.ttf"),
    "Segoe UI":         ("segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
    "Consolas":         ("consola.ttf", "consolab.ttf", "consolai.ttf", "consolaz.ttf"),
    "Arial Narrow":     ("arialn.ttf", "arialnb.ttf", "arialni.ttf", "arialnbi.ttf"),
    # Chinese families (cover CJK + Latin)
    "Microsoft YaHei":  ("msyh.ttc", "msyhbd.ttc", "msyh.ttc", "msyhbd.ttc"),
    "SimSun":           ("simsun.ttc", "simsun.ttc", "simsun.ttc", "simsun.ttc"),
    "SimHei":           ("simhei.ttf", "simhei.ttf", "simhei.ttf", "simhei.ttf"),
    "KaiTi":            ("simkai.ttf", "simkai.ttf", "simkai.ttf", "simkai.ttf"),
}

# Fallback CJK fonts used on export when the chosen Latin font lacks glyphs.
_CJK_REGULAR = ("msyh.ttc", "simhei.ttf", "simsun.ttc", "Deng.ttf", "simkai.ttf")
_CJK_BOLD = ("msyhbd.ttc", "simhei.ttf", "simsun.ttc")
_CJK_FAMILIES = {"Microsoft YaHei", "SimSun", "SimHei", "KaiTi"}


def _has_cjk(text: str) -> bool:
    for ch in text:
        o = ord(ch)
        if (0x3000 <= o <= 0x30ff or 0x3400 <= o <= 0x4dbf
                or 0x4e00 <= o <= 0x9fff or 0xac00 <= o <= 0xd7af
                or 0xf900 <= o <= 0xfaff or 0xff00 <= o <= 0xffef):
            return True
    return False


def _cjk_fontfile(bold: bool):
    for n in (_CJK_BOLD if bold else ()) + _CJK_REGULAR:
        p = os.path.join(_FONTDIR, n)
        if os.path.isfile(p):
            return p
    return None

# PDF base-14 fallbacks: family -> (regular, bold, italic, bold_italic)
_BASE14 = {
    "Arial":           ("helv", "hebo", "heit", "hebi"),
    "Helvetica":       ("helv", "hebo", "heit", "hebi"),
    "Times New Roman": ("times", "tibo", "tiit", "tibi"),
    "Times":           ("times", "tibo", "tiit", "tibi"),
    "Courier New":     ("cour", "cobo", "coit", "cobi"),
    "Courier":         ("cour", "cobo", "coit", "cobi"),
}
_DEFAULT_BASE14 = ("helv", "hebo", "heit", "hebi")


def _style_index(bold: bool, italic: bool) -> int:
    return (1 if bold else 0) + (2 if italic else 0)


def available_families() -> list[str]:
    """Families that actually exist on this machine (regular file present)."""
    out = []
    for fam, files in _WIN_FONT_FILES.items():
        if os.path.isfile(os.path.join(_FONTDIR, files[0])):
            out.append(fam)
    # Always expose the logical base-14 names as a safe fallback.
    for fam in ("Helvetica", "Times", "Courier"):
        if fam not in out:
            out.append(fam)
    return out


@dataclass
class ResolvedFont:
    """How to draw a label in the exported PDF."""
    fontname: str            # name handed to PyMuPDF
    fontfile: str | None     # path to embed, or None for a base-14 builtin


def resolve_export_font(family: str, bold: bool, italic: bool,
                        text: str = "") -> ResolvedFont:
    """Pick a TTF to embed (preferred) or a base-14 builtin fallback.

    If `text` contains CJK characters, fall back to a Chinese font so the
    glyphs actually render (base-14 / Latin TTFs export them blank).
    """
    if text and family not in _CJK_FAMILIES and _has_cjk(text):
        cjk = _cjk_fontfile(bold)
        if cjk:
            return ResolvedFont(fontname="FCJK" + ("B" if bold else ""), fontfile=cjk)
    idx = _style_index(bold, italic)
    files = _WIN_FONT_FILES.get(family)
    if files:
        path = os.path.join(_FONTDIR, files[idx])
        if not os.path.isfile(path):                    # style variant missing
            path = os.path.join(_FONTDIR, files[0])
        if os.path.isfile(path):
            safe = family.replace(" ", "") + ("B" if bold else "") + ("I" if italic else "")
            return ResolvedFont(fontname="F" + safe, fontfile=path)
    base = _BASE14.get(family, _DEFAULT_BASE14)
    return ResolvedFont(fontname=base[idx], fontfile=None)
