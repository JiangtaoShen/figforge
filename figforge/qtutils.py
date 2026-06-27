"""Small Qt helpers — mostly image-buffer conversions."""
from __future__ import annotations

from PySide6 import QtGui


def qimage_from_fitz(pix) -> QtGui.QImage:
    """Convert a PyMuPDF Pixmap into a QImage (copied, owns its buffer)."""
    if pix.alpha:
        fmt = QtGui.QImage.Format.Format_RGBA8888
    else:
        fmt = QtGui.QImage.Format.Format_RGB888
    img = QtGui.QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
    return img.copy()  # detach from the PyMuPDF-owned buffer


def qimage_from_pil(im) -> QtGui.QImage:
    """Convert a PIL.Image into a QImage."""
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    data = im.tobytes("raw", im.mode)
    if im.mode == "RGB":
        fmt = QtGui.QImage.Format.Format_RGB888
        stride = im.width * 3
    else:
        fmt = QtGui.QImage.Format.Format_RGBA8888
        stride = im.width * 4
    img = QtGui.QImage(data, im.width, im.height, stride, fmt)
    return img.copy()
