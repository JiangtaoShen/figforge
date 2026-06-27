"""Import sub-figures of many kinds into a common in-memory representation.

Raster images keep their original file (embedded at full resolution on export).
Vector sources (PDF / SVG / EPS / PS) are turned into PDF bytes so they can be
placed as true vector content on export via ``Page.show_pdf_page``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

import fitz  # PyMuPDF
from PySide6 import QtCore, QtGui

from ..qtutils import qimage_from_fitz, qimage_from_pil

RASTER_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
VECTOR_EXTS = {".pdf", ".svg", ".eps", ".ps"}
ALL_EXTS = RASTER_EXTS | VECTOR_EXTS

PREVIEW_MAX_PX = 1600  # cap the long edge of on-screen previews


@dataclass
class LoadedSource:
    path: str                       # the file currently backing this source
    kind: str                       # 'raster' | 'vector'
    width_pt: float
    height_pt: float
    preview: QtGui.QPixmap
    page_index: int = 0             # for multi-page PDFs
    page_count: int = 1
    vec_pdf_bytes: bytes | None = None  # vector source rendered as a PDF


def classify(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in RASTER_EXTS:
        return "raster"
    if ext in VECTOR_EXTS:
        return "vector"
    return "unknown"


def pdf_page_count(path: str) -> int:
    try:
        with fitz.open(path) as doc:
            return doc.page_count
    except Exception:
        return 1


# --------------------------------------------------------------------------- #
# raster
# --------------------------------------------------------------------------- #
def _load_raster(path: str) -> LoadedSource:
    img = QtGui.QImage(path)
    if img.isNull():
        # fall back to Pillow (handles exotic TIFF/`webp` better)
        from PIL import Image
        with Image.open(path) as im:
            im.load()
            dpi = im.info.get("dpi", (96, 96))
            dpi_x = dpi[0] or 96
            dpi_y = (dpi[1] if len(dpi) > 1 else dpi[0]) or 96
            w_px, h_px = im.size
            img = qimage_from_pil(im)
    else:
        w_px, h_px = img.width(), img.height()
        dpi_x = img.dotsPerMeterX() * 0.0254 or 96
        dpi_y = img.dotsPerMeterY() * 0.0254 or 96

    width_pt = w_px / dpi_x * 72.0
    height_pt = h_px / dpi_y * 72.0

    preview = img
    longest = max(img.width(), img.height())
    if longest > PREVIEW_MAX_PX:
        scale = PREVIEW_MAX_PX / longest
        preview = img.scaled(
            int(img.width() * scale), int(img.height() * scale),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
    return LoadedSource(
        path=path, kind="raster",
        width_pt=width_pt, height_pt=height_pt,
        preview=QtGui.QPixmap.fromImage(preview),
    )


# --------------------------------------------------------------------------- #
# vector
# --------------------------------------------------------------------------- #
def _eps_to_pdf_bytes(path: str) -> bytes:
    gs = shutil.which("gswin64c") or shutil.which("gswin32c") or shutil.which("gs")
    if not gs:
        raise RuntimeError(
            "导入 EPS/PS 需要安装 Ghostscript（命令 gswin64c）。\n"
            "请安装 Ghostscript，或先把文件转换为 PDF/SVG 后再导入。"
        )
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.close()
    try:
        subprocess.run(
            [gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER",
             "-sDEVICE=pdfwrite", "-dEPSCrop",
             "-sOutputFile=" + tmp.name, path],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        with open(tmp.name, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def _render_pdf_preview(doc: "fitz.Document", page_index: int) -> tuple[QtGui.QPixmap, float, float]:
    page = doc[page_index]
    rect = page.rect
    w_pt, h_pt = rect.width, rect.height
    longest = max(w_pt, h_pt) or 1.0
    scale = min(PREVIEW_MAX_PX / longest, 4.0)
    scale = max(scale, 0.1)
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=True)
    pm = QtGui.QPixmap.fromImage(qimage_from_fitz(pix))
    return pm, w_pt, h_pt


def _load_vector(path: str, page_index: int) -> LoadedSource:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        with open(path, "rb") as fh:
            pdf_bytes = fh.read()
        doc = fitz.open("pdf", pdf_bytes)
        page_count = doc.page_count
        page_index = max(0, min(page_index, page_count - 1))
        preview, w_pt, h_pt = _render_pdf_preview(doc, page_index)
        doc.close()
        return LoadedSource(path=path, kind="vector", width_pt=w_pt, height_pt=h_pt,
                            preview=preview, page_index=page_index,
                            page_count=page_count, vec_pdf_bytes=pdf_bytes)

    # svg / eps / ps  ->  single-page PDF bytes
    if ext == ".svg":
        with fitz.open(path) as d:
            pdf_bytes = d.convert_to_pdf()
    else:  # .eps / .ps
        pdf_bytes = _eps_to_pdf_bytes(path)

    doc = fitz.open("pdf", pdf_bytes)
    preview, w_pt, h_pt = _render_pdf_preview(doc, 0)
    doc.close()
    return LoadedSource(path=path, kind="vector", width_pt=w_pt, height_pt=h_pt,
                        preview=preview, page_index=0, page_count=1,
                        vec_pdf_bytes=pdf_bytes)


def load_source(path: str, page_index: int = 0) -> LoadedSource:
    """Load any supported file into a LoadedSource (raises on failure)."""
    kind = classify(path)
    if kind == "raster":
        return _load_raster(path)
    if kind == "vector":
        return _load_vector(path, page_index)
    raise ValueError(f"不支持的文件类型：{os.path.splitext(path)[1]}")
