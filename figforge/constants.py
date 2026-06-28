"""Global constants and unit helpers.

The whole application works internally in PDF *points* (1 pt = 1/72 inch).
The graphics scene uses 1 unit == 1 point, which maps 1:1 onto PyMuPDF page
coordinates (origin top-left, y downwards) so export geometry is trivial.
"""
from __future__ import annotations

# ---- units -----------------------------------------------------------------
PT_PER_INCH = 72.0
MM_PER_INCH = 25.4
PT_PER_MM = PT_PER_INCH / MM_PER_INCH      # 2.834645...
MM_PER_PT = MM_PER_INCH / PT_PER_INCH      # 0.352777...


def mm_to_pt(mm: float) -> float:
    return mm * PT_PER_MM


def pt_to_mm(pt: float) -> float:
    return pt * MM_PER_PT


def pt_to_in(pt: float) -> float:
    return pt / PT_PER_INCH


# ---- page sizes (points, portrait: width x height) -------------------------
PAGE_SIZES = {
    "A4": (595.276, 841.890),     # 210 x 297 mm
    "Letter": (612.0, 792.0),     # 8.5 x 11 in
}
DEFAULT_PAGE = "A4"

PORTRAIT = "Portrait"
LANDSCAPE = "Landscape"
ORIENTATIONS = (PORTRAIT, LANDSCAPE)


def page_rect_pt(name: str, orientation: str) -> tuple[float, float]:
    """Return (width_pt, height_pt) for a page name + orientation."""
    w, h = PAGE_SIZES.get(name, PAGE_SIZES[DEFAULT_PAGE])
    if orientation == LANDSCAPE:
        return h, w
    return w, h


# ---- export ----------------------------------------------------------------
DPI_CHOICES = [150, 300, 600, 1200]
DEFAULT_DPI = 600

# ---- editing ---------------------------------------------------------------
DEFAULT_GRID_MM = 5.0
SNAP_THRESHOLD_PX = 7.0       # snap distance measured in on-screen pixels
ANCHOR_THRESHOLD_PX = 11.0    # line-endpoint -> object-node snap distance
MIN_ITEM_PT = 4.0            # smallest allowed item dimension
HANDLE_PX = 8.0             # resize-handle size in on-screen pixels
NUDGE_MM = 1.0             # arrow-key move step
NUDGE_FINE_MM = 0.2        # Ctrl+arrow fine move step

# ---- project ---------------------------------------------------------------
PROJECT_EXT = ".ffp"
PROJECT_FORMAT_VERSION = 1

# ---- branding --------------------------------------------------------------
APP_NAME = "FigForge"
APP_TITLE = "FigForge · 论文图排版"
ORG_NAME = "FigForge"
