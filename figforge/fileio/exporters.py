"""Export the page to PDF (vector preserved), PNG and TIFF (high DPI).

One source of truth: we build the page once with PyMuPDF — vector sub-figures
are placed with ``show_pdf_page`` (stay vector), raster sub-figures are embedded
at full resolution, and labels become real PDF text.  PNG/TIFF are then
rasterised from that exact same page, so every format matches pixel-for-pixel.
"""
from __future__ import annotations

import fitz


class FontRegistry:
    """Embed each TrueType file at most once per page."""

    def __init__(self):
        self._per_page: dict[int, set] = {}

    def ensure(self, page, resolved) -> str:
        if resolved.fontfile is None:
            return resolved.fontname            # base-14 builtin
        seen = self._per_page.setdefault(id(page), set())
        if resolved.fontname not in seen:
            page.insert_font(fontname=resolved.fontname, fontfile=resolved.fontfile)
            seen.add(resolved.fontname)
        return resolved.fontname


def build_document(scene, white_bg: bool = True):
    """Return (doc, keep_open). Caller must save then close both."""
    out = fitz.open()
    page = out.new_page(width=scene.page_w, height=scene.page_h)
    if white_bg:
        page.draw_rect(fitz.Rect(0, 0, scene.page_w, scene.page_h),
                       color=(1, 1, 1), fill=(1, 1, 1), width=0)
    fontreg = FontRegistry()
    keep_open: list = []
    for item in scene.iter_items():          # ascending z: back to front
        item.render_to_pdf(page, fontreg, keep_open)
    return out, keep_open


def _close(out, keep_open):
    for d in keep_open:
        try:
            d.close()
        except Exception:
            pass
    out.close()


def export_pdf(scene, path: str, white_bg: bool = True):
    out, keep = build_document(scene, white_bg=white_bg)
    try:
        out.save(path, garbage=4, deflate=True, clean=True)
    finally:
        _close(out, keep)


def export_png(scene, path: str, dpi: int = 600, transparent: bool = False):
    out, keep = build_document(scene, white_bg=not transparent)
    try:
        pix = out[0].get_pixmap(dpi=dpi, alpha=transparent)
        pix.save(path)
    finally:
        _close(out, keep)


def export_tiff(scene, path: str, dpi: int = 600):
    from PIL import Image
    out, keep = build_document(scene, white_bg=True)
    try:
        pix = out[0].get_pixmap(dpi=dpi, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        img.save(path, dpi=(dpi, dpi), compression="tiff_lzw")
    finally:
        _close(out, keep)
