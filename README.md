# FigForge

<img src="figforge/resources/icon.png" width="96" align="right" alt="FigForge icon">

**English** | [简体中文](README.zh-CN.md)

A lightweight, **vector-preserving** layout tool for academic figures — a trimmed-down
"graphic design" app focused on one job: arranging several sub-figures into a Nature-style
multi-panel figure on an A4 / Letter page, labelling panels by hand, and exporting
**print-ready PDF (vectors preserved)** and **high-resolution PNG / TIFF**.

Vector sub-figures (PDF / SVG / EPS) stay **true vectors** in the exported PDF (infinite
resolution); raster sub-figures are embedded at their **original resolution**; text labels
become **real vector PDF text**. PDF and PNG come from the same source, so what you see is
what you get.

## Run

```bat
py -m pip install -r requirements.txt
py run.py
```

Requires Python 3.10+, PySide6, PyMuPDF, Pillow. (Importing EPS/PS additionally needs Ghostscript.)

## Features

- **Canvas**: A4 / Letter, portrait / landscape.
- **Import sub-figures**: PNG, JPG, TIFF, BMP, GIF, WebP (raster); PDF, SVG, EPS, PS (vector).
  Pick the page of a multi-page PDF. **Drag files straight from Explorer into the window** —
  they land at the cursor.
- **Layout**: move by dragging; resize from the handles (keeps aspect by default, hold Shift to
  toggle); rotate (drag the rotation handle — Shift for 15° steps, snaps to 0/90/180/270 — or type
  an exact angle); crop (visual box with rule-of-thirds); enter exact millimetre values in the
  properties panel; smart-guide snapping + optional grid; align / distribute; z-order; duplicate.
- **Labels / text**: add text labels by hand with common fonts (Arial, Times New Roman, Calibri…),
  size, bold / italic, colour, alignment; double-click for multi-line editing.
  **No auto-numbering — fully under your control.**
- **Export**:
  - **PDF** — vectors preserved, best for printing.
  - **PNG** — 150 / 300 / 600 / 1200 DPI, optional transparent background.
  - **TIFF** — high DPI, LZW compression.
- **Project file `.ffp`** — a ZIP bundle carrying all assets, so projects survive moving machines
  or originals being relocated.
- Full undo / redo.

## Shortcuts

| Action | Key |
|---|---|
| Import images | Ctrl+I |
| Add text label | T |
| Save / Save As | Ctrl+S / Ctrl+Shift+S |
| Undo / Redo | Ctrl+Z / Ctrl+Y |
| Duplicate / Delete / Select all | Ctrl+D / Del / Ctrl+A |
| Crop selected figure | C |
| Fit page / Zoom in / Zoom out | Ctrl+0 / Ctrl++ / Ctrl+- |
| Zoom (Ctrl+wheel), Pan (Space-drag or middle-drag) | |

## Build a standalone .exe (optional)

```bat
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --windowed --name FigForge run.py
```

The app appears under `dist\FigForge\`; double-click `FigForge.exe`. When moving it to another
machine, copy the **whole `FigForge` folder** (the `_internal` folder holds the runtime).

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
    items.py          figure / label items (move, resize, rotate, crop, export)
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
