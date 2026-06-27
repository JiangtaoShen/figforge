"""Project save / load.

A ``.ffp`` project is a ZIP bundle holding ``project.json`` plus copies of every
source image under ``assets/`` — so projects are self-contained and survive the
originals being moved or deleted.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import zipfile

from .. import constants
from ..canvas.items import FigureItem, LabelItem


def save_project(path: str, scene) -> None:
    items = scene.iter_items()
    assets: dict[str, str] = {}          # source path -> asset name
    item_dicts = []
    next_idx = 0
    for it in items:
        if isinstance(it, FigureItem):
            src = it._source_path
            if src not in assets:
                ext = os.path.splitext(src)[1] or ".bin"
                assets[src] = f"asset_{next_idx:03d}{ext}"
                next_idx += 1
            it._asset_name = assets[src]
        item_dicts.append(it.to_dict())

    manifest = {
        "format": constants.PROJECT_FORMAT_VERSION,
        "app": constants.APP_NAME,
        "page": {"name": scene.page_name, "orientation": scene.orientation},
        "grid": {"mm": scene.grid_mm, "visible": scene.grid_visible},
        "items": item_dicts,
    }

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for src, asset in assets.items():
            if os.path.isfile(src):
                zf.write(src, f"assets/{asset}")


def load_project(path: str):
    """Return (config dict, [items], tempdir). tempdir holds extracted assets
    and must stay alive for the session (needed for re-export)."""
    tempdir = tempfile.mkdtemp(prefix="figforge_")
    with zipfile.ZipFile(path, "r") as zf:
        zf.extractall(tempdir)
    with open(os.path.join(tempdir, "project.json"), "r", encoding="utf-8") as fh:
        manifest = json.load(fh)

    items = []
    for d in manifest.get("items", []):
        if d.get("type") == "figure":
            asset_path = os.path.join(tempdir, "assets", d.get("asset", ""))
            item = FigureItem.from_dict(d, asset_path)
            item._asset_name = d.get("asset")
        elif d.get("type") == "label":
            item = LabelItem.from_dict(d)
        else:
            continue
        items.append(item)

    config = {
        "page": manifest.get("page", {"name": constants.DEFAULT_PAGE,
                                      "orientation": constants.PORTRAIT}),
        "grid": manifest.get("grid", {"mm": constants.DEFAULT_GRID_MM, "visible": False}),
    }
    return config, items, tempdir


def cleanup_tempdir(tempdir: str | None):
    if tempdir and os.path.isdir(tempdir):
        shutil.rmtree(tempdir, ignore_errors=True)
