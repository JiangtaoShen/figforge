# FigForge

<img src="figforge/resources/icon.png" width="96" align="right" alt="FigForge icon">

**English** | [简体中文](README.zh-CN.md)

[![CI](https://github.com/JiangtaoShen/figforge/actions/workflows/ci.yml/badge.svg)](https://github.com/JiangtaoShen/figforge/actions/workflows/ci.yml)

**[⬇ Download for Windows](https://github.com/JiangtaoShen/figforge/releases/latest)** — no Python needed. Pick either the **installer** (`…-setup.exe`: Start-Menu entry, uninstaller, double-click `.ffp` files to open them) or the **portable zip** (unzip and run `FigForge.exe`).

A lightweight, **vector-preserving** layout tool for academic figures — a trimmed-down
"graphic design" app focused on one job: arranging several sub-figures into a Nature-style
multi-panel figure on an A4 / Letter page, labelling panels by hand, and exporting
**print-ready PDF (vectors preserved)** and **high-resolution PNG / TIFF**.

Vector sub-figures (PDF / SVG / EPS) stay **true vectors** in the exported PDF (infinite
resolution); raster sub-figures are embedded at their **original resolution**; text labels
become **real vector PDF text**. PDF and PNG come from the same source, so what you see is
what you get.

## Run

Windows:

```bat
py -m pip install -r requirements.txt
py run.py
```

macOS / Linux:

```bash
python3 -m pip install -r requirements.txt
python3 run.py
```

Requires Python 3.10+ (PySide6, PyMuPDF, Pillow, fontTools). Fonts are resolved from the
system font folders on **Windows, macOS and Linux** alike; exported PDFs embed **subsetted**
font files (only the glyphs you used), so files with Chinese text stay small.
(Importing EPS/PS additionally needs Ghostscript: `gswin64c` on Windows, `gs` elsewhere.)

## Features

- **Canvas**: A4 / Letter, portrait / landscape.
- **Import sub-figures**: PNG, JPG, TIFF, BMP, GIF, WebP (raster); PDF, SVG, EPS, PS (vector).
  Pick the page of a multi-page PDF. **Drag files straight from Explorer into the window** —
  they land at the cursor.
- **Layout**: move by dragging; resize from the handles (keeps aspect by default, hold Shift to
  toggle); rotate (drag the rotation handle — Shift for 15° steps, snaps to 0/90/180/270 — or type
  an exact angle); crop (visual box with rule-of-thirds); enter exact millimetre values in the
  properties panel; smart-guide snapping + a **dynamic Visio-style grid** (finer gridlines appear
  as you zoom in, 1-2-5 mm steps; grid snapping follows the visible step); align / distribute; z-order;
  copy / paste (Ctrl+C / Ctrl+V), **Ctrl-drag to duplicate**, and duplicate (Ctrl+D).
  Arrow keys nudge the selection (**Ctrl+arrows** for fine steps).
- **Arrange in Grid**: select several panels → Object → **Arrange in Grid** (Ctrl+G) — rows /
  columns / gaps in mm, optionally making every panel the same size, in one step.
- **Same-size binding**: Ctrl-click several images to select them, right-click → **Bind Size** —
  resizing any one then keeps all bound images exactly the same size.
- **Lock**: lock finished objects (Ctrl+L) so they can't be moved by accident; locked items show
  a 🔒 in the Layers panel; **Unlock All** (Ctrl+Shift+L) releases them.
- **Labels / text**: add text labels by hand with common fonts including Chinese
  (Arial, Times New Roman, Calibri, Microsoft YaHei, SimSun…), size, bold / italic, colour,
  alignment; **double-click to edit right on the canvas** (a caret appears in place — no popup
  dialog; Esc or clicking elsewhere finishes). Chinese text automatically uses a Chinese
  font on export. **No auto-numbering — fully under your control.**
- **Annotations**: **text boxes** (wrapping text frame — rectangle or **rounded rectangle**, with
  the corner radius adjusted by dragging the diamond handle right on the box; **per-side text
  padding** (left/right/top/bottom, in mm); optional border and fill with adjustable
  **background opacity**, rotatable) and **lines / arrows** (solid or dashed, end or both-end
  arrowheads). Line endpoints **snap to text-box / object nodes and stay attached** — move the box
  and the connected end follows while the other end stays put. Both export as vectors.
  Text boxes and lines ignore grid snapping, so annotations can be placed freely.
- **Export**:
  - **PDF** — vectors preserved, best for printing.
  - **PNG** — 150 / 300 / 600 / 1200 DPI, optional transparent background.
  - **TIFF** — high DPI, LZW compression.
  - **Crop to content** — optionally trim the export to the content bounding box plus a chosen
    margin, so the figure ships without the surrounding page whitespace.
- **Project file `.ffp`** — a ZIP bundle carrying all assets, so projects survive moving machines
  or originals being relocated.
- **Languages**: English and 简体中文, switchable from the **Language** menu (the choice is
  remembered; a fresh install defaults to English).
- **Autosave & crash recovery**: unsaved work is snapshotted every 2 minutes; if FigForge (or
  the machine) dies, the next launch offers to restore it. Internal errors are logged and
  trigger an immediate rescue snapshot instead of losing your layout.
- Full undo / redo.

## Shortcuts

| Action | Key |
|---|---|
| Import images | Ctrl+I |
| Add text label | T |
| Save / Save As | Ctrl+S / Ctrl+Shift+S |
| Undo / Redo | Ctrl+Z / Ctrl+Y |
| Copy / Cut / Paste | Ctrl+C / Ctrl+X / Ctrl+V |
| Duplicate / Delete / Select all | Ctrl+D / Del / Ctrl+A |
| Nudge / Fine nudge | Arrows / Ctrl+Arrows |
| Crop selected figure | C |
| Arrange in grid | Ctrl+G |
| Lock / Unlock all | Ctrl+L / Ctrl+Shift+L |
| Deselect | Esc |
| Fit page / Zoom in / Zoom out | Ctrl+0 / Ctrl++ / Ctrl+- |
| Zoom (Ctrl+wheel), Pan (Space-drag or middle-drag) | |

## Build a standalone app (optional)

Use a **clean virtual environment** so only the libraries FigForge needs get bundled
(otherwise PyInstaller drags in everything living in your global Python):

```bat
py -m venv C:\ffb
C:\ffb\Scripts\python -m pip install -r requirements.txt pyinstaller
C:\ffb\Scripts\python -m PyInstaller --noconfirm --windowed ^
    --icon figforge/resources/icon.ico --add-data "figforge/resources;figforge/resources" ^
    --exclude-module tkinter --name FigForge run.py
```

The app appears under `dist\FigForge\` (~250 MB); double-click `FigForge.exe`. When moving it
to another machine, copy the **whole `FigForge` folder** (the `_internal` folder holds the
runtime). The same commands with `python3` produce a native bundle on macOS / Linux.

To also build the Windows **installer** (Start-Menu entry, uninstaller, `.ffp` association),
install [Inno Setup 6](https://jrsoftware.org/isinfo.php) and run:

```bat
iscc /DMyAppVersion=0.3.0 installer\FigForge.iss
```

Release tags (`v*`) build and attach both the zip and the installer automatically via CI.

## Project layout

```
figforge/
  constants.py        units / page sizes / defaults
  fonts.py            font resolution (embeds real TTFs on export)
  qtutils.py          QImage conversion helpers
  fileio/
    importers.py      import many formats -> preview + vector data
    exporters.py      export PDF (vector) / PNG / TIFF (one source of truth)
    project.py        .ffp project load/save (ZIP-bundled assets)
  canvas/
    items.py          figure / label / text-box / line items (move, resize, rotate, crop, export)
    scene.py          page, grid, smart-guide snapping
    view.py           zoom / pan / drag-and-drop
  ui/
    properties_panel.py   geometry + label styling + rotate / crop
    layers_panel.py       object list + z-order
    crop_dialog.py        visual crop dialog
  main_window.py      menus / toolbars / file & export / align / undo
  app.py              entry point
run.py
```

## How vector preservation works

Editing is done with Qt's `QGraphicsScene` (1 scene unit = 1 PDF point). Export is a separate
PyMuPDF pipeline that is the single source of truth: vector sub-figures are placed with
`show_pdf_page` (stay vector), rasters are embedded full-res, labels are written as PDF text;
rotation/crop go through an intermediate page so they remain vector too. PNG/TIFF are then
rasterised from that exact PDF, so every format matches pixel-for-pixel.
