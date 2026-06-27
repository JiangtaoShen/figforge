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
}

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


def resolve_export_font(family: str, bold: bool, italic: bool) -> ResolvedFont:
    """Pick a TTF to embed (preferred) or a base-14 builtin fallback."""
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
