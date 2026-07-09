"""Font resolution for exported text — Windows, macOS and Linux.

On screen we render text with Qt (by family name). On export we want the
PDF to look identical, so we embed the *actual* font file when we can find
it, and fall back to a metrically-similar PDF base-14 font otherwise.

Font files are located by scanning the platform's font directories once
(recursively; Linux nests fonts in subfolders) into a basename -> path
index, so the same family table works on every OS.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from functools import lru_cache


# ---- platform font directories ---------------------------------------------
def _font_dirs() -> list[str]:
    home = os.path.expanduser("~")
    if sys.platform.startswith("win"):
        return [
            os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
            # per-user installed fonts (Win 10+)
            os.path.join(os.environ.get("LOCALAPPDATA", ""),
                         "Microsoft", "Windows", "Fonts"),
        ]
    if sys.platform == "darwin":
        return ["/System/Library/Fonts", "/Library/Fonts",
                os.path.join(home, "Library", "Fonts")]
    return ["/usr/share/fonts", "/usr/local/share/fonts",
            os.path.join(home, ".fonts"),
            os.path.join(home, ".local", "share", "fonts")]


@lru_cache(maxsize=1)
def _font_index() -> dict[str, str]:
    """Lower-case file name -> full path for every font file found."""
    idx: dict[str, str] = {}
    for d in _font_dirs():
        if not d or not os.path.isdir(d):
            continue
        for root, _dirs, files in os.walk(d):
            for fn in files:
                if fn.lower().endswith((".ttf", ".ttc", ".otf")):
                    idx.setdefault(fn.lower(), os.path.join(root, fn))
    return idx


def _find(*names: str) -> str | None:
    idx = _font_index()
    for n in names:
        p = idx.get(n.lower())
        if p:
            return p
    return None


# ---- curated families --------------------------------------------------------
# family -> (regular, bold, italic, bold_italic); each style lists candidate
# file names across platforms (Windows names, macOS "Arial Bold.ttf" style,
# Linux Liberation/DejaVu/Noto). Families whose regular file is missing on
# this machine are simply hidden from the font dropdown.
_FAMILY_FILES: dict[str, tuple[tuple[str, ...], ...]] = {
    "Arial": (("arial.ttf",),
              ("arialbd.ttf", "arial bold.ttf"),
              ("ariali.ttf", "arial italic.ttf"),
              ("arialbi.ttf", "arial bold italic.ttf")),
    "Times New Roman": (("times.ttf", "times new roman.ttf"),
                        ("timesbd.ttf", "times new roman bold.ttf"),
                        ("timesi.ttf", "times new roman italic.ttf"),
                        ("timesbi.ttf", "times new roman bold italic.ttf")),
    "Courier New": (("cour.ttf", "courier new.ttf"),
                    ("courbd.ttf", "courier new bold.ttf"),
                    ("couri.ttf", "courier new italic.ttf"),
                    ("courbi.ttf", "courier new bold italic.ttf")),
    "Calibri": (("calibri.ttf",), ("calibrib.ttf",),
                ("calibrii.ttf",), ("calibriz.ttf",)),
    "Cambria": (("cambria.ttc",), ("cambriab.ttf",),
                ("cambriai.ttf",), ("cambriaz.ttf",)),
    "Georgia": (("georgia.ttf",), ("georgiab.ttf",),
                ("georgiai.ttf",), ("georgiaz.ttf",)),
    "Verdana": (("verdana.ttf",), ("verdanab.ttf",),
                ("verdanai.ttf",), ("verdanaz.ttf",)),
    "Tahoma": (("tahoma.ttf",), ("tahomabd.ttf",),
               ("tahoma.ttf",), ("tahomabd.ttf",)),
    "Segoe UI": (("segoeui.ttf",), ("segoeuib.ttf",),
                 ("segoeuii.ttf",), ("segoeuiz.ttf",)),
    "Consolas": (("consola.ttf",), ("consolab.ttf",),
                 ("consolai.ttf",), ("consolaz.ttf",)),
    "Arial Narrow": (("arialn.ttf",), ("arialnb.ttf",),
                     ("arialni.ttf",), ("arialnbi.ttf",)),
    # Linux staples
    "DejaVu Sans": (("dejavusans.ttf",), ("dejavusans-bold.ttf",),
                    ("dejavusans-oblique.ttf",), ("dejavusans-boldoblique.ttf",)),
    "Liberation Sans": (("liberationsans-regular.ttf",),
                        ("liberationsans-bold.ttf",),
                        ("liberationsans-italic.ttf",),
                        ("liberationsans-bolditalic.ttf",)),
    "Liberation Serif": (("liberationserif-regular.ttf",),
                         ("liberationserif-bold.ttf",),
                         ("liberationserif-italic.ttf",),
                         ("liberationserif-bolditalic.ttf",)),
    "Noto Sans": (("notosans-regular.ttf",), ("notosans-bold.ttf",),
                  ("notosans-italic.ttf",), ("notosans-bolditalic.ttf",)),
    # Chinese families (cover CJK + Latin)
    "Microsoft YaHei": (("msyh.ttc",), ("msyhbd.ttc",),
                        ("msyh.ttc",), ("msyhbd.ttc",)),
    "SimSun": (("simsun.ttc",),) * 4,
    "SimHei": (("simhei.ttf",),) * 4,
    "KaiTi": (("simkai.ttf",),) * 4,
    "PingFang SC": (("pingfang.ttc",),) * 4,
    "Songti SC": (("songti.ttc",),) * 4,
    "Noto Sans CJK SC": (("notosanscjk-regular.ttc",
                          "notosanscjksc-regular.otf",
                          "notosanscjk-sc-regular.otf",
                          "notosanssc-regular.otf",
                          "notosanssc-regular.ttf"),) * 4,
    "WenQuanYi Micro Hei": (("wqy-microhei.ttc",),) * 4,
}

# Fallback CJK fonts used on export when the chosen Latin font lacks glyphs.
_CJK_REGULAR = (
    # Windows
    "msyh.ttc", "simhei.ttf", "simsun.ttc", "deng.ttf", "simkai.ttf",
    # macOS
    "pingfang.ttc", "hiragino sans gb.ttc", "stheiti light.ttc",
    "stheiti medium.ttc", "songti.ttc",
    # Linux — TrueType-flavoured first (PyMuPDF can subset those on export;
    # Noto CJK is CFF and gets embedded whole)
    "wqy-microhei.ttc", "wqy-zenhei.ttc", "droidsansfallbackfull.ttf",
    "notosanssc-regular.ttf", "notosanscjk-regular.ttc",
    "notosanscjksc-regular.otf", "notosanscjk-sc-regular.otf",
    "notosanssc-regular.otf",
)
_CJK_BOLD = ("msyhbd.ttc", "simhei.ttf", "notosanscjk-bold.ttc",
             "notosanscjksc-bold.otf", "wqy-zenhei.ttc") + _CJK_REGULAR
_CJK_FAMILIES = {"Microsoft YaHei", "SimSun", "SimHei", "KaiTi",
                 "PingFang SC", "Songti SC", "Noto Sans CJK SC",
                 "WenQuanYi Micro Hei"}


def _has_cjk(text: str) -> bool:
    for ch in text:
        o = ord(ch)
        if (0x3000 <= o <= 0x30ff or 0x3400 <= o <= 0x4dbf
                or 0x4e00 <= o <= 0x9fff or 0xac00 <= o <= 0xd7af
                or 0xf900 <= o <= 0xfaff or 0xff00 <= o <= 0xffef):
            return True
    return False


def _cjk_fontfile(bold: bool) -> str | None:
    return _find(*(_CJK_BOLD if bold else _CJK_REGULAR))


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
    out = [fam for fam, styles in _FAMILY_FILES.items() if _find(*styles[0])]
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
    """Pick a font file to embed (preferred) or a base-14 builtin fallback.

    If `text` contains CJK characters, fall back to a Chinese font so the
    glyphs actually render (base-14 / Latin fonts export them blank).
    """
    if text and family not in _CJK_FAMILIES and _has_cjk(text):
        cjk = _cjk_fontfile(bold)
        if cjk:
            return ResolvedFont(fontname="FCJK" + ("B" if bold else ""),
                                fontfile=cjk)
    idx = _style_index(bold, italic)
    styles = _FAMILY_FILES.get(family)
    if styles:
        path = _find(*styles[idx]) or _find(*styles[0])
        if path:
            safe = "".join(ch for ch in family if ch.isalnum())
            return ResolvedFont(
                fontname="F" + safe + ("B" if bold else "") + ("I" if italic else ""),
                fontfile=path)
    base = _BASE14.get(family, _DEFAULT_BASE14)
    return ResolvedFont(fontname=base[idx], fontfile=None)
