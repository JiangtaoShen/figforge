"""The application main window — wires the canvas, panels, menus and actions."""
from __future__ import annotations

import json
import os
import time
import uuid

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt

from . import constants, fonts
from .icons import build_icons
from .canvas.items import (BaseItem, FigureItem, LabelItem, LineItem,
                           TextBoxItem)
from .canvas.scene import PageScene
from .canvas.view import CanvasView
from .commands import AddItemCommand, DeleteItemsCommand, FuncCommand
from .fileio import exporters, importers, project
from .ui.layers_panel import LayersPanel
from .ui.properties_panel import PropertiesPanel
from . import i18n
from .i18n import tr

_IMPORT_FILTER_KEY = (
    "All supported (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.gif *.webp "
    "*.pdf *.svg *.eps *.ps);;Raster (*.png *.jpg *.jpeg *.tif *.tiff *.bmp "
    "*.gif *.webp);;Vector (*.pdf *.svg *.eps *.ps);;All files (*.*)"
)


class ExportDialog(QtWidgets.QDialog):
    """Export options: DPI / transparency (raster only) + crop-to-content."""

    def __init__(self, parent, raster=True, allow_transparent=True):
        super().__init__(parent)
        self.setWindowTitle(tr("Export Settings"))
        form = QtWidgets.QFormLayout(self)
        self.cmb_dpi = None
        self.chk_transparent = None
        if raster:
            self.cmb_dpi = QtWidgets.QComboBox()
            for d in constants.DPI_CHOICES:
                self.cmb_dpi.addItem(f"{d} DPI", d)
            self.cmb_dpi.setCurrentText(f"{constants.DEFAULT_DPI} DPI")
            form.addRow(tr("Resolution"), self.cmb_dpi)
            if allow_transparent:
                self.chk_transparent = QtWidgets.QCheckBox(
                    tr("Transparent background"))
                form.addRow("", self.chk_transparent)
        self.chk_crop = QtWidgets.QCheckBox(tr("Crop to content"))
        form.addRow("", self.chk_crop)
        self.spin_margin = QtWidgets.QDoubleSpinBox()
        self.spin_margin.setRange(0.0, 50.0)
        self.spin_margin.setDecimals(1)
        self.spin_margin.setSingleStep(0.5)
        self.spin_margin.setSuffix(" mm")
        self.spin_margin.setValue(1.0)
        self.spin_margin.setEnabled(False)
        self.chk_crop.toggled.connect(self.spin_margin.setEnabled)
        form.addRow(tr("Content margin"), self.spin_margin)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def dpi(self) -> int:
        return self.cmb_dpi.currentData() if self.cmb_dpi else constants.DEFAULT_DPI

    def transparent(self) -> bool:
        return bool(self.chk_transparent and self.chk_transparent.isChecked())

    def crop_margin_pt(self) -> float | None:
        if not self.chk_crop.isChecked():
            return None
        return constants.mm_to_pt(self.spin_margin.value())


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.scene = PageScene()
        self.undo_stack = QtGui.QUndoStack(self)
        self.scene.undo_stack = self.undo_stack
        self.view = CanvasView(self.scene)
        self.setCentralWidget(self.view)

        self.current_path: str | None = None
        self._tempdir: str | None = None
        self._extra_dirty = False
        self._suspend = False
        self._fig_count = 0
        self._label_count = 0
        self._tb_count = 0
        self._line_count = 0
        self._clipboard = []
        self._paste_count = 0
        self._syncing_size = False

        self._build_docks()
        self._build_actions()
        self._build_menus()
        self._build_toolbars()
        self._build_statusbar()

        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.scene.sceneEdited.connect(self._on_scene_edited)
        self.scene.ctrlDuplicate.connect(self._ctrl_duplicate)
        self.undo_stack.cleanChanged.connect(lambda *_: self._update_title())
        self.view.zoomChanged.connect(self._on_zoom)
        self.view.cursorMoved.connect(self._on_cursor)
        self.view.filesDropped.connect(self.on_files_dropped)
        self.view.nudge.connect(self.nudge_selected)
        self.view.contextMenu.connect(self._show_context_menu)

        self.resize(1280, 840)
        self._update_title()
        QtCore.QTimer.singleShot(0, self.view.fit_page)

        self._last_autosave_idx = -1
        self._autosave_timer = QtCore.QTimer(self)
        self._autosave_timer.setInterval(constants.AUTOSAVE_INTERVAL_MS)
        self._autosave_timer.timeout.connect(self._do_autosave)
        self._autosave_timer.start()
        QtCore.QTimer.singleShot(0, self._offer_restore)

    # ------------------------------------------------------------------ docks
    def _build_docks(self):
        self.properties = PropertiesPanel(self)
        d1 = QtWidgets.QDockWidget(tr("Properties"), self)
        d1.setWidget(self.properties)
        d1.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea
                           | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, d1)

        self.layers = LayersPanel(self)
        d2 = QtWidgets.QDockWidget(tr("Layers"), self)
        d2.setWidget(self.layers)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, d2)

    # --------------------------------------------------------------- actions
    def _act(self, text, slot, shortcut=None, tip=None, icon=None):
        a = QtGui.QAction(text, self)
        if icon is not None:
            a.setIcon(icon)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(shortcut)
        tip_text = tip or text
        sc = a.shortcut().toString()
        if sc:
            tip_text = f"{tip_text}  ({sc})"
        a.setToolTip(tip_text)        # shown on hover (icon-only toolbar)
        a.setStatusTip(tip or text)
        return a

    def _build_actions(self):
        QKS = QtGui.QKeySequence
        self.a_new = self._act(tr("New"), self.new_project, QKS.StandardKey.New)
        self.a_open = self._act(tr("Open…"), self.open_project, QKS.StandardKey.Open)
        self.a_save = self._act(tr("Save"), self.save_project, QKS.StandardKey.Save)
        self.a_save_as = self._act(tr("Save As…"), self.save_project_as, QKS.StandardKey.SaveAs)
        self.a_import = self._act(tr("Import Images…"), self.import_figures, "Ctrl+I")
        self.a_exp_pdf = self._act(tr("Export PDF (vector)…"), self.export_pdf)
        self.a_exp_png = self._act(tr("Export PNG (high-res)…"), self.export_png)
        self.a_exp_tiff = self._act(tr("Export TIFF…"), self.export_tiff)
        self.a_quit = self._act(tr("Quit"), self.close, QKS.StandardKey.Quit)

        self.a_undo = self.undo_stack.createUndoAction(self, tr("Undo"))
        self.a_undo.setShortcut(QKS.StandardKey.Undo)
        self.a_redo = self.undo_stack.createRedoAction(self, tr("Redo"))
        self.a_redo.setShortcut(QKS.StandardKey.Redo)
        self.a_delete = self._act(tr("Delete"), self.delete_selected, QKS.StandardKey.Delete)
        self.a_select_all = self._act(tr("Select All"), self.select_all, QKS.StandardKey.SelectAll)
        self.a_duplicate = self._act(tr("Duplicate"), self.duplicate_selected, "Ctrl+D")
        self.a_copy = self._act(tr("Copy"), self.copy_selected, QKS.StandardKey.Copy)
        self.a_cut = self._act(tr("Cut"), self.cut_selected, QKS.StandardKey.Cut)
        self.a_paste = self._act(tr("Paste"), self.paste, QKS.StandardKey.Paste)

        self.a_add_label = self._act(tr("Add Text Label"), self.add_label, "T")
        self.a_add_textbox = self._act(tr("Add Text Box"), self.add_textbox)
        self.a_add_line = self._act(tr("Add Line"), self.add_line)
        self.a_crop = self._act(tr("Crop Image…"), self.crop_selected, "C")
        self.a_grid_arrange = self._act(tr("Arrange in Grid…"), self.arrange_grid, "Ctrl+G")
        self.a_rot_l = self._act(tr("Rotate Left 90°"), lambda: self.rotate_selected(-90))
        self.a_rot_r = self._act(tr("Rotate Right 90°"), lambda: self.rotate_selected(90))
        self.a_rot_reset = self._act(tr("Reset Rotation"), self.reset_rotation)
        self.a_bind_size = self._act(tr("Bind Size (same size)"), self.bind_sizes)
        self.a_unbind_size = self._act(tr("Unbind Size"), self.unbind_sizes)
        self.a_lock = self._act(tr("Lock"), self.lock_selected, "Ctrl+L")
        self.a_unlock_all = self._act(tr("Unlock All"), self.unlock_all, "Ctrl+Shift+L")

        self.a_al_left = self._act(tr("Align Left"), lambda: self.align("left"))
        self.a_al_hc = self._act(tr("Align Center"), lambda: self.align("hcenter"))
        self.a_al_right = self._act(tr("Align Right"), lambda: self.align("right"))
        self.a_al_top = self._act(tr("Align Top"), lambda: self.align("top"))
        self.a_al_vm = self._act(tr("Align Middle"), lambda: self.align("vmiddle"))
        self.a_al_bottom = self._act(tr("Align Bottom"), lambda: self.align("bottom"))
        self.a_dist_h = self._act(tr("Distribute Horizontally"), lambda: self.distribute("h"))
        self.a_dist_v = self._act(tr("Distribute Vertically"), lambda: self.distribute("v"))

        self.a_front = self._act(tr("Bring to Front"), lambda: self.change_z("front"))
        self.a_up = self._act(tr("Bring Forward"), lambda: self.change_z("up"))
        self.a_down = self._act(tr("Send Backward"), lambda: self.change_z("down"))
        self.a_back = self._act(tr("Send to Back"), lambda: self.change_z("back"))

        self.a_zoom_in = self._act(tr("Zoom In"), self.view.zoom_in, QKS.StandardKey.ZoomIn)
        self.a_zoom_out = self._act(tr("Zoom Out"), self.view.zoom_out, QKS.StandardKey.ZoomOut)
        self.a_fit = self._act(tr("Fit Page"), self.view.fit_page, "Ctrl+0")
        self.a_reset_zoom = self._act(tr("Actual Size 100%"), self.view.reset_zoom)

        # attach line-art icons (also appear next to the menu items)
        ic = build_icons(self.palette().color(QtGui.QPalette.ColorRole.WindowText))
        for act, key in (
            (self.a_import, "import"), (self.a_add_label, "text"),
            (self.a_add_textbox, "textbox"), (self.a_add_line, "line"),
            (self.a_crop, "crop"), (self.a_grid_arrange, "grid_arrange"),
            (self.a_lock, "lock"),
            (self.a_rot_l, "rotate_left"), (self.a_rot_r, "rotate_right"),
            (self.a_al_left, "align_left"), (self.a_al_hc, "align_hcenter"),
            (self.a_al_right, "align_right"), (self.a_al_top, "align_top"),
            (self.a_al_vm, "align_vmiddle"), (self.a_al_bottom, "align_bottom"),
            (self.a_front, "front"), (self.a_up, "forward"),
            (self.a_down, "backward"), (self.a_back, "back"),
            (self.a_exp_pdf, "export_pdf"), (self.a_exp_png, "export_png"),
        ):
            act.setIcon(ic[key])

    def _build_menus(self):
        mb = self.menuBar()
        m = mb.addMenu(tr("File"))
        m.addActions([self.a_new, self.a_open])
        self.m_recent = m.addMenu(tr("Open Recent"))
        self.m_recent.setToolTipsVisible(True)
        self.m_recent.aboutToShow.connect(self._rebuild_recent_menu)
        m.addActions([self.a_save, self.a_save_as])
        m.addSeparator()
        m.addAction(self.a_import)
        m.addSeparator()
        m.addActions([self.a_exp_pdf, self.a_exp_png, self.a_exp_tiff])
        m.addSeparator()
        m.addAction(self.a_quit)

        m = mb.addMenu(tr("Edit"))
        m.addActions([self.a_undo, self.a_redo])
        m.addSeparator()
        m.addActions([self.a_copy, self.a_cut, self.a_paste])
        m.addSeparator()
        m.addActions([self.a_duplicate, self.a_delete, self.a_select_all])

        m = mb.addMenu(tr("Object"))
        m.addAction(self.a_add_label)
        m.addAction(self.a_add_textbox)
        m.addAction(self.a_add_line)
        m.addAction(self.a_crop)
        m.addSeparator()
        m.addAction(self.a_grid_arrange)
        m.addSeparator()
        m.addAction(self.a_lock)
        m.addAction(self.a_unlock_all)
        m.addSeparator()
        m.addAction(self.a_bind_size)
        m.addAction(self.a_unbind_size)
        m.addSeparator()
        sub = m.addMenu(tr("Align"))
        sub.addActions([self.a_al_left, self.a_al_hc, self.a_al_right])
        sub.addSeparator()
        sub.addActions([self.a_al_top, self.a_al_vm, self.a_al_bottom])
        sub.addSeparator()
        sub.addActions([self.a_dist_h, self.a_dist_v])
        sub = m.addMenu(tr("Order"))
        sub.addActions([self.a_front, self.a_up, self.a_down, self.a_back])
        sub = m.addMenu(tr("Rotate"))
        sub.addActions([self.a_rot_l, self.a_rot_r, self.a_rot_reset])

        m = mb.addMenu(tr("View"))
        m.addActions([self.a_zoom_in, self.a_zoom_out, self.a_fit, self.a_reset_zoom])

        m = mb.addMenu(tr("Language"))
        grp = QtGui.QActionGroup(self)
        for code, label in i18n.available():
            a = QtGui.QAction(label, self, checkable=True)
            a.setChecked(code == i18n.language())
            a.triggered.connect(lambda _=False, c=code: self._set_language(c))
            grp.addAction(a)
            m.addAction(a)

        m = mb.addMenu(tr("Help"))
        m.addAction(self._act(tr("User Guide"), self.show_help))
        m.addAction(self._act(tr("About"), self.show_about))

    def _build_toolbars(self):
        tb = self.addToolBar(tr("Main Toolbar"))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        tb.setIconSize(QtCore.QSize(22, 22))
        tb.addAction(self.a_import)
        tb.addAction(self.a_add_label)
        tb.addAction(self.a_add_textbox)
        tb.addAction(self.a_add_line)
        tb.addSeparator()
        tb.addActions([self.a_al_left, self.a_al_hc, self.a_al_right,
                       self.a_al_top, self.a_al_vm, self.a_al_bottom])
        tb.addAction(self.a_grid_arrange)
        tb.addSeparator()
        tb.addActions([self.a_front, self.a_up, self.a_down, self.a_back])
        tb.addSeparator()
        tb.addActions([self.a_rot_l, self.a_rot_r, self.a_crop])
        tb.addSeparator()
        tb.addActions([self.a_exp_pdf, self.a_exp_png])

        # page / grid toolbar
        pb = self.addToolBar(tr("Page"))
        pb.addWidget(QtWidgets.QLabel(tr(" Paper ")))
        self.cmb_page = QtWidgets.QComboBox()
        self.cmb_page.addItems(list(constants.PAGE_SIZES.keys()))
        pb.addWidget(self.cmb_page)
        self.cmb_orient = QtWidgets.QComboBox()
        self.cmb_orient.addItems([tr("Portrait"), tr("Landscape")])
        pb.addWidget(self.cmb_orient)
        self.cmb_page.currentIndexChanged.connect(self._page_changed)
        self.cmb_orient.currentIndexChanged.connect(self._page_changed)
        pb.addSeparator()
        self.chk_grid = QtWidgets.QCheckBox(tr("Grid"))
        self.chk_grid.setToolTip(tr("Dynamic grid: finer as you zoom in; snapping follows it."))
        self.chk_snap = QtWidgets.QCheckBox(tr("Smart Snap"))
        self.chk_snap.setChecked(True)
        pb.addWidget(self.chk_grid)
        pb.addWidget(self.chk_snap)
        self.chk_grid.toggled.connect(self._grid_changed)
        self.chk_snap.toggled.connect(
            lambda on: setattr(self.scene, "snap_enabled", on))

    def _build_statusbar(self):
        sb = self.statusBar()
        self.lbl_pos = QtWidgets.QLabel("X: -  Y: -")
        self.lbl_page = QtWidgets.QLabel("")
        self.lbl_zoom = QtWidgets.QLabel(tr("Zoom {0}%").format(100))
        sb.addWidget(self.lbl_pos)
        sb.addPermanentWidget(self.lbl_page)
        sb.addPermanentWidget(self.lbl_zoom)
        self._update_page_label()

    # --------------------------------------------------------------- helpers
    def _push(self, cmd):
        self.undo_stack.push(cmd)

    def _default_label_font(self) -> str:
        fams = fonts.available_families()
        return "Arial" if "Arial" in fams else fams[0]

    def _register_new_item(self, item):
        if isinstance(item, BaseItem):
            item.geometryChanged.connect(self._update_line_anchors)
        if isinstance(item, FigureItem):
            item.geometryChanged.connect(lambda it=item: self._sync_size_group(it))

    def _update_line_anchors(self):
        for it in self.scene.iter_items():
            if isinstance(it, LineItem):
                it.update_anchors(self.scene)

    def _selected(self):
        return [it for it in self.scene.iter_items() if it.isSelected()]

    def _select_only(self, items):
        self.scene.clearSelection()
        for it in items:
            it.setSelected(True)

    # ----------------------------------------------------------------- import
    def import_figures(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, tr("Import images"), "", tr(_IMPORT_FILTER_KEY))
        if paths:
            self.add_figures_from_paths(paths)

    def on_files_dropped(self, paths, scene_pos):
        """Files dragged from Explorer onto the canvas."""
        self.add_figures_from_paths(paths, at_scene_pos=scene_pos)

    def add_figures_from_paths(self, paths, at_scene_pos=None):
        new_items = []
        self.undo_stack.beginMacro(tr("Import Images…"))
        for path in paths:
            try:
                page_index = 0
                if path.lower().endswith(".pdf"):
                    n = importers.pdf_page_count(path)
                    if n > 1:
                        val, ok = QtWidgets.QInputDialog.getInt(
                            self, tr("Choose Page"),
                            tr("{0} has {1} pages. Which page to import?").format(
                                os.path.basename(path), n),
                            1, 1, n)
                        if not ok:
                            continue
                        page_index = val - 1
                source = importers.load_source(path, page_index)
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, tr("Import Failed"), f"{os.path.basename(path)}\n\n{e}")
                continue
            self._fig_count += 1
            item = FigureItem(source, name=f"{tr('Image')} {self._fig_count}")
            self._fit_initial(item, len(new_items), at_scene_pos)
            item.setZValue(self.scene.next_z())
            self._register_new_item(item)
            self._push(AddItemCommand(self.scene, item))
            new_items.append(item)
        self.undo_stack.endMacro()
        if new_items:
            self._select_only(new_items)
        return new_items

    def _fit_initial(self, item: FigureItem, index: int, at_scene_pos=None):
        w, h = item._src_w, item._src_h
        maxw, maxh = self.scene.page_w * 0.8, self.scene.page_h * 0.8
        if w > maxw or h > maxh:
            s = min(maxw / w, maxh / h)
            w, h = w * s, h * s
        off = (index % 6) * constants.mm_to_pt(5)
        if at_scene_pos is not None:                 # drop at the cursor
            x = at_scene_pos.x() - w / 2 + off
            y = at_scene_pos.y() - h / 2 + off
        else:                                        # cascade near top-left
            x = self.scene.page_w * 0.1 + off
            y = self.scene.page_h * 0.1 + off
        item.set_geometry(x, y, w, h)

    # ----------------------------------------------------------------- labels
    def add_label(self):
        self._label_count += 1
        item = LabelItem(text="a", family=self._default_label_font(),
                         size_pt=14.0, bold=True)
        item.set_name(f"{tr('Label')} {self._label_count}")
        center = self.view.mapToScene(self.view.viewport().rect().center())
        item.setZValue(self.scene.next_z())
        item.set_geometry(center.x(), center.y(), *item.size())
        self._register_new_item(item)
        self._push(AddItemCommand(self.scene, item))
        self._select_only([item])
        self.view.setFocus()
        item.start_inline_edit(select_all=True)   # type straight away

    def add_textbox(self):
        self._tb_count += 1
        item = TextBoxItem(text=tr("Text Box"), family=self._default_label_font())
        item.set_name(f"{tr('Text Box')} {self._tb_count}")
        center = self.view.mapToScene(self.view.viewport().rect().center())
        w, h = item.size()
        item.setZValue(self.scene.next_z())
        item.set_geometry(center.x() - w / 2, center.y() - h / 2, w, h)
        self._register_new_item(item)
        self._push(AddItemCommand(self.scene, item))
        self._select_only([item])
        self.view.setFocus()
        item.start_inline_edit(select_all=True)   # type straight away

    def add_line(self):
        self._line_count += 1
        item = LineItem()
        item.set_name(f"{tr('Line')} {self._line_count}")
        center = self.view.mapToScene(self.view.viewport().rect().center())
        item.setZValue(self.scene.next_z())
        item.setPos(center.x() - 60, center.y())
        self._register_new_item(item)
        self._push(AddItemCommand(self.scene, item))
        self._select_only([item])

    # --------------------------------------------------------- rotate / crop
    def _rotate_to(self, target_fn, text):
        figs = [it for it in self._selected()
                if isinstance(it, (FigureItem, TextBoxItem))]
        if not figs:
            return
        self.undo_stack.beginMacro(text)
        for it in figs:
            old = it.get_state()
            new = (old[0], old[1], old[2], old[3], target_fn(old[4]))
            if new == old:
                continue
            self._push(FuncCommand(text,
                                   lambda it=it, s=new: it.set_state(s),
                                   lambda it=it, s=old: it.set_state(s)))
        self.undo_stack.endMacro()

    def rotate_selected(self, delta):
        self._rotate_to(lambda r: (r + delta) % 360, tr("Modify rotation"))

    def reset_rotation(self):
        self._rotate_to(lambda r: 0.0, tr("Reset Rotation"))

    def crop_selected(self):
        figs = [it for it in self._selected() if isinstance(it, FigureItem)]
        if len(figs) != 1:
            QtWidgets.QMessageBox.information(
                self, tr("Crop"), tr("Please select a single image to crop."))
            return
        it = figs[0]
        from .ui.crop_dialog import CropDialog
        dlg = CropDialog(self, it._pixmap, it.crop)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        old, new = it.crop, dlg.get_crop()
        if new == old:
            return
        self._push(FuncCommand(tr("Crop"),
                               lambda: it.set_crop(new),
                               lambda: it.set_crop(old)))

    # ------------------------------------------------------------- edit / z
    def delete_selected(self):
        items = self._selected()
        if items:
            self._push(DeleteItemsCommand(self.scene, items))

    def select_all(self):
        for it in self.scene.iter_items():
            it.setSelected(True)

    def duplicate_selected(self):
        items = self._selected()
        if not items:
            return
        off = constants.mm_to_pt(4)
        dups = []
        self.undo_stack.beginMacro(tr("Duplicate"))
        for it in items:
            dup = self._clone_item(it)
            if dup is None:
                continue
            dup.setZValue(self.scene.next_z())
            if isinstance(it, LineItem):
                dup.setPos(it.pos().x() + off, it.pos().y() + off)
            else:
                x, y, w, h = it.get_geometry()
                dup.set_state((x + off, y + off, w, h, it.rotation()))
            self._register_new_item(dup)
            self._push(AddItemCommand(self.scene, dup))
            dups.append(dup)
        self.undo_stack.endMacro()
        if dups:
            self._select_only(dups)

    def _clone_item(self, it):
        if isinstance(it, FigureItem):
            self._fig_count += 1
            dup = FigureItem(importers.load_source(it._source_path, it._page_index),
                             name=f"{tr('Image')} {self._fig_count}")
            dup.aspect_locked = it.aspect_locked
            dup.crop = it.crop
            return dup
        if isinstance(it, TextBoxItem):
            self._tb_count += 1
            dup = TextBoxItem(text=it.text, family=it.family, size_pt=it.size_pt,
                              bold=it.bold, italic=it.italic,
                              color=QtGui.QColor(it.color))
            dup.align = it.align
            dup.border, dup.border_width = it.border, it.border_width
            dup.border_color = QtGui.QColor(it.border_color)
            dup.fill = it.fill
            dup.fill_color = QtGui.QColor(it.fill_color)
            dup.fill_opacity = it.fill_opacity
            dup.corner_radius = it.corner_radius
            dup.pad_left, dup.pad_top = it.pad_left, it.pad_top
            dup.pad_right, dup.pad_bottom = it.pad_right, it.pad_bottom
            dup.set_name(f"{tr('Text Box')} {self._tb_count}")
            return dup
        if isinstance(it, LineItem):
            self._line_count += 1
            dup = LineItem(p1=QtCore.QPointF(it.p1), p2=QtCore.QPointF(it.p2),
                           color=QtGui.QColor(it.color), width_pt=it.width_pt,
                           dashed=it.dashed, arrow=it.arrow)
            dup.anchor1 = dict(it.anchor1) if it.anchor1 else None
            dup.anchor2 = dict(it.anchor2) if it.anchor2 else None
            dup.set_name(f"{tr('Line')} {self._line_count}")
            return dup
        if isinstance(it, LabelItem):
            self._label_count += 1
            dup = LabelItem(text=it.text, family=it.family, size_pt=it.size_pt,
                            bold=it.bold, italic=it.italic,
                            color=QtGui.QColor(it.color))
            dup.align = it.align
            dup._recompute()
            dup.set_name(f"{tr('Label')} {self._label_count}")
            return dup
        return None

    def _place_copies(self, sources, off, select_copies):
        dups = []
        for it in sources:
            dup = self._clone_item(it)
            if dup is None:
                continue
            dup.setZValue(self.scene.next_z())
            if off == 0:
                dup.set_state(it.get_state())
            elif isinstance(it, LineItem):
                dup.setPos(it.pos().x() + off, it.pos().y() + off)
            else:
                x, y, w, h, rot = it.get_state()
                dup.set_state((x + off, y + off, w, h, rot))
            self._register_new_item(dup)
            self._push(AddItemCommand(self.scene, dup))
            dups.append(dup)
        if dups and select_copies:
            self._select_only(dups)
        return dups

    def copy_selected(self):
        sel = self._selected()
        if sel:
            self._clipboard = list(sel)
            self._paste_count = 0

    def cut_selected(self):
        sel = self._selected()
        if not sel:
            return
        self._clipboard = list(sel)
        self._paste_count = 0
        self.delete_selected()

    def paste(self):
        if not self._clipboard:
            return
        self._paste_count += 1
        off = constants.mm_to_pt(4) * self._paste_count
        self.undo_stack.beginMacro(tr("Paste"))
        self._place_copies(self._clipboard, off, select_copies=True)
        self.undo_stack.endMacro()

    def _ctrl_duplicate(self):
        sel = self._selected()
        if not sel:
            return
        self.undo_stack.beginMacro(tr("Drag-duplicate"))
        self._place_copies(sel, 0, select_copies=False)
        self.undo_stack.endMacro()

    def nudge_selected(self, dx, dy):
        items = self._selected()
        if not items:
            return

        def shift(ddx, ddy):
            with self.scene.no_snap():
                for it in items:
                    it.setPos(it.pos().x() + ddx, it.pos().y() + ddy)

        self._push(FuncCommand(tr("Move"),
                               lambda: shift(dx, dy),
                               lambda: shift(-dx, -dy)))

    # ------------------------------------------------------------- size bind
    def bind_sizes(self):
        figs = [it for it in self._selected() if isinstance(it, FigureItem)]
        if len(figs) < 2:
            return
        w, h = figs[0].size()
        gid = uuid.uuid4().hex
        before = [(it, it.size_group, it.get_state()) for it in figs]

        def do():
            for it in figs:
                it.size_group = gid
                x, y, _, _, rot = it.get_state()
                it.set_state((x, y, w, h, rot))

        def undo():
            for it, g, st in before:
                it.size_group = g
                it.set_state(st)

        self._push(FuncCommand(tr("Bind Size"), do, undo))

    def unbind_sizes(self):
        figs = [it for it in self._selected()
                if isinstance(it, FigureItem) and it.size_group]
        if not figs:
            return
        before = [(it, it.size_group) for it in figs]

        def do():
            for it in figs:
                it.size_group = None

        def undo():
            for it, g in before:
                it.size_group = g

        self._push(FuncCommand(tr("Unbind Size"), do, undo))

    def _sync_size_group(self, item):
        gid = getattr(item, "size_group", None)
        if not gid or self._syncing_size:
            return
        w, h = item.size()
        self._syncing_size = True
        try:
            for it in self.scene.iter_items():
                if (isinstance(it, FigureItem) and it is not item
                        and it.size_group == gid and (it._w, it._h) != (w, h)):
                    x, y, _, _, rot = it.get_state()
                    it.set_state((x, y, w, h, rot))
        finally:
            self._syncing_size = False

    # ---------------------------------------------------------- grid arrange
    def arrange_grid(self):
        figs = [it for it in self._selected() if isinstance(it, FigureItem)]
        if len(figs) < 2:
            QtWidgets.QMessageBox.information(
                self, tr("Arrange in Grid"),
                tr("Select at least two images to arrange."))
            return
        from .ui.arrange_dialog import ArrangeGridDialog
        dlg = ArrangeGridDialog(self, len(figs))
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        _rows, cols, hgap, vgap, same = dlg.values()
        ordered = self._grid_order(figs)
        old = {it: it.get_state() for it in ordered}
        x0 = min(st[0] for st in old.values())
        y0 = min(st[1] for st in old.values())
        if same:
            w0, h0 = ordered[0].size()
            sizes = {it: (w0, h0) for it in ordered}
        else:
            sizes = {it: it.size() for it in ordered}
        cellw = max(w for w, _ in sizes.values())
        cellh = max(h for _, h in sizes.values())
        new = {}
        for i, it in enumerate(ordered):
            r, c = divmod(i, cols)
            w, h = sizes[it]
            new[it] = (x0 + c * (cellw + hgap), y0 + r * (cellh + vgap),
                       w, h, old[it][4])

        def apply(states):
            with self.scene.no_snap():
                for it in ordered:
                    it.set_state(states[it])

        self._push(FuncCommand(tr("Arrange in Grid"),
                               lambda: apply(new), lambda: apply(old)))

    def _grid_order(self, figs):
        """Row-major order inferred from the panels' current positions."""
        maxh = max(it.size()[1] for it in figs)
        rows: list[tuple[float, list]] = []
        for it in sorted(figs, key=lambda i: i.pos().y()):
            if rows and it.pos().y() - rows[-1][0] <= maxh * 0.5:
                rows[-1][1].append(it)
            else:
                rows.append((it.pos().y(), [it]))
        ordered = []
        for _, row in rows:
            ordered.extend(sorted(row, key=lambda i: i.pos().x()))
        return ordered

    # ---------------------------------------------------------- lock / unlock
    def lock_selected(self):
        items = self._selected()
        if not items:
            return
        self._push(FuncCommand(
            tr("Lock"),
            lambda: [it.set_locked(True) for it in items],
            lambda: [it.set_locked(False) for it in items]))

    def unlock_all(self):
        items = [it for it in self.scene.iter_items() if it.locked]
        if not items:
            return
        self._push(FuncCommand(
            tr("Unlock All"),
            lambda: [it.set_locked(False) for it in items],
            lambda: [it.set_locked(True) for it in items]))

    def _show_context_menu(self, global_pos):
        menu = QtWidgets.QMenu(self)
        sel = self._selected()
        figs = [it for it in sel if isinstance(it, FigureItem)]
        if len(figs) >= 2:
            menu.addAction(self.a_grid_arrange)
            menu.addAction(self.a_bind_size)
        if any(it.size_group for it in figs):
            menu.addAction(self.a_unbind_size)
        if sel:
            if not menu.isEmpty():
                menu.addSeparator()
            menu.addAction(self.a_copy)
            menu.addAction(self.a_duplicate)
            menu.addAction(self.a_delete)
            menu.addAction(self.a_lock)
        if self._clipboard:
            menu.addAction(self.a_paste)
        if any(it.locked for it in self.scene.iter_items()):
            menu.addSeparator()
            menu.addAction(self.a_unlock_all)
        if not menu.isEmpty():
            menu.exec(global_pos)

    def change_z(self, mode):
        sel = self._selected()
        if not sel:
            return
        order = self.scene.iter_items()
        old = {it: it.zValue() for it in order}
        selset = set(sel)
        if mode == "front":
            z = self.scene._z_counter
            for it in sel:
                z += 1
                it.setZValue(z)
            self.scene._z_counter = z
        elif mode == "back":
            minz = min(old.values())
            for k, it in enumerate(sel):
                it.setZValue(minz - len(sel) + k)
        else:
            lst = order[:]
            if mode == "up":
                for i in range(len(lst) - 2, -1, -1):
                    if lst[i] in selset and lst[i + 1] not in selset:
                        lst[i], lst[i + 1] = lst[i + 1], lst[i]
            else:
                for i in range(1, len(lst)):
                    if lst[i] in selset and lst[i - 1] not in selset:
                        lst[i], lst[i - 1] = lst[i - 1], lst[i]
            for idx, it in enumerate(lst):
                it.setZValue(idx + 1)
            self.scene._z_counter = max(self.scene._z_counter, len(lst) + 1)
        new = {it: it.zValue() for it in order}
        self._push(FuncCommand(tr("Reorder"),
                               lambda: [it.setZValue(new[it]) for it in order],
                               lambda: [it.setZValue(old[it]) for it in order]))
        self.layers.refresh()

    # -------------------------------------------------------- align/distribute
    def _with_geometry_undo(self, text, mutate):
        items = [it for it in self._selected() if isinstance(it, BaseItem)]
        if not items:
            return
        old = {it: it.get_geometry() for it in items}
        with self.scene.no_snap():
            mutate(items)
        new = {it: it.get_geometry() for it in items}
        if new == old:
            return

        def apply(geoms):
            with self.scene.no_snap():
                for it in items:
                    it.set_geometry(*geoms[it])

        self._push(FuncCommand(text,
                               lambda: apply(new), lambda: apply(old)))

    def align(self, mode):
        def mut(items):
            if len(items) >= 2:
                b = items[0].scene_rect()
                for it in items[1:]:
                    b = b.united(it.scene_rect())
            else:
                b = self.scene.page_rect()
            for it in items:
                x, y, w, h = it.get_geometry()
                if mode == "left":
                    x = b.left()
                elif mode == "hcenter":
                    x = b.center().x() - w / 2
                elif mode == "right":
                    x = b.right() - w
                elif mode == "top":
                    y = b.top()
                elif mode == "vmiddle":
                    y = b.center().y() - h / 2
                elif mode == "bottom":
                    y = b.bottom() - h
                it.set_geometry(x, y, w, h)
        self._with_geometry_undo(tr("Align"), mut)

    def distribute(self, axis):
        def mut(items):
            if len(items) < 3:
                return
            key = (lambda it: it.scene_rect().center().x()) if axis == "h" \
                else (lambda it: it.scene_rect().center().y())
            items.sort(key=key)
            first, last = key(items[0]), key(items[-1])
            step = (last - first) / (len(items) - 1)
            for i, it in enumerate(items):
                x, y, w, h = it.get_geometry()
                c = first + step * i
                if axis == "h":
                    x = c - w / 2
                else:
                    y = c - h / 2
                it.set_geometry(x, y, w, h)
        self._with_geometry_undo(tr("Distribute"), mut)

    # ------------------------------------------------------------ page / grid
    def _page_changed(self, *_):
        page = self.cmb_page.currentText()
        orient = constants.PORTRAIT if self.cmb_orient.currentIndex() == 0 else constants.LANDSCAPE
        self.scene.set_page(page, orient)
        self._update_page_label()
        self.view.fit_page()

    def _grid_changed(self, *_):
        self.scene.set_grid(visible=self.chk_grid.isChecked())
        self.scene.snap_to_grid = self.chk_grid.isChecked()
        self._on_zoom(self.view._zoom * 100.0)

    def _update_page_label(self):
        self.lbl_page.setText(
            f"{self.scene.page_name} · {tr(self.scene.orientation)} · "
            f"{self.scene.page_w * constants.MM_PER_PT:.0f}×"
            f"{self.scene.page_h * constants.MM_PER_PT:.0f} mm")

    # --------------------------------------------------------------- signals
    def on_selection_changed(self):
        if self._suspend:
            return
        sel = self.scene.selectedItems()
        self.properties.set_selection(sel)
        self.layers.sync_from_scene()

    def _on_scene_edited(self):
        if self._suspend:
            return
        self.layers.refresh()
        self._update_title()

    def _on_cursor(self, x, y):
        self.lbl_pos.setText(
            f"X: {x * constants.MM_PER_PT:6.1f} mm   Y: {y * constants.MM_PER_PT:6.1f} mm")

    def _on_zoom(self, percent):
        txt = tr("Zoom {0}%").format(round(percent))
        if self.scene.grid_visible:
            txt += "  ·  " + tr("Grid {0} mm").format(
                f"{self.scene.dynamic_grid_mm():g}")
        self.lbl_zoom.setText(txt)

    # ------------------------------------------------------------- dirty/title
    def _is_dirty(self) -> bool:
        return self._extra_dirty or not self.undo_stack.isClean()

    def _update_title(self):
        name = os.path.basename(self.current_path) if self.current_path else tr("Untitled")
        star = "*" if self._is_dirty() else ""
        self.setWindowTitle(f"{star}{name} — {tr('FigForge — Academic Figure Layout')}")

    def _set_language(self, lang):
        if lang == i18n.language():
            return
        i18n.save_language(lang)
        r = QtWidgets.QMessageBox.question(
            self, tr("Language changed"),
            tr("The language will switch after restarting. Restart now?"),
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No)
        if r == QtWidgets.QMessageBox.StandardButton.Yes:
            self._restart()

    def _restart(self):
        import sys
        if not self._confirm_discard():
            return
        try:
            self.undo_stack.cleanChanged.disconnect()
        except (RuntimeError, TypeError):
            pass
        self._autosave_timer.stop()
        self._clear_autosave()
        project.cleanup_tempdir(self._tempdir)
        self._tempdir = None
        args = [] if getattr(sys, "frozen", False) else sys.argv
        QtCore.QProcess.startDetached(sys.executable, args)
        QtWidgets.QApplication.quit()

    def _confirm_discard(self) -> bool:
        if not self._is_dirty():
            return True
        r = QtWidgets.QMessageBox.question(
            self, tr("Unsaved"), tr("The project has unsaved changes. Save them?"),
            QtWidgets.QMessageBox.StandardButton.Save
            | QtWidgets.QMessageBox.StandardButton.Discard
            | QtWidgets.QMessageBox.StandardButton.Cancel)
        if r == QtWidgets.QMessageBox.StandardButton.Save:
            return self.save_project()
        return r == QtWidgets.QMessageBox.StandardButton.Discard

    # --------------------------------------------------------------- file ops
    def new_project(self):
        if not self._confirm_discard():
            return
        self._suspend = True
        self.scene.clear()
        self.scene._z_counter = 1.0
        self._suspend = False
        self.scene.set_page(constants.DEFAULT_PAGE, constants.PORTRAIT)
        project.cleanup_tempdir(self._tempdir)
        self._tempdir = None
        self.current_path = None
        self._fig_count = self._label_count = self._tb_count = self._line_count = 0
        self.undo_stack.clear()
        self.undo_stack.setClean()
        self._extra_dirty = False
        self._clear_autosave()
        self._sync_page_controls()
        self.layers.refresh()
        self.on_selection_changed()
        self.view.fit_page()
        self._update_title()

    def open_project(self):
        if not self._confirm_discard():
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, tr("Open Project"), "", tr("FigForge Project (*.ffp)"))
        if not path:
            return
        self._load_project_path(path)

    def open_recent(self, path):
        if not self._confirm_discard():
            return
        if not os.path.isfile(path):
            QtWidgets.QMessageBox.warning(
                self, tr("Open Failed"), tr("File not found: {0}").format(path))
            self._remove_recent(path)
            return
        self._load_project_path(path)

    def _load_project_path(self, path):
        try:
            config, items, tempdir = project.load_project(path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("Open Failed"), str(e))
            return
        self._apply_loaded_project(config, items, tempdir)
        self.current_path = path
        self._extra_dirty = False
        self._clear_autosave()
        self._add_recent(path)
        self._update_title()

    def _apply_loaded_project(self, config, items, tempdir):
        self._suspend = True
        self.scene.clear()
        self.scene._z_counter = 1.0
        pg = config["page"]
        self.scene.set_page(pg.get("name", constants.DEFAULT_PAGE),
                            pg.get("orientation", constants.PORTRAIT))
        gr = config["grid"]
        self.scene.set_grid(mm=gr.get("mm", constants.DEFAULT_GRID_MM),
                            visible=gr.get("visible", False))
        maxz = 0.0
        for it in items:
            self.scene.addItem(it)
            self._register_new_item(it)
            maxz = max(maxz, it.zValue())
        self.scene._z_counter = maxz + 1
        self._suspend = False
        self._update_line_anchors()              # re-pin loaded connectors

        project.cleanup_tempdir(self._tempdir)
        self._tempdir = tempdir
        self._fig_count = sum(1 for it in items if isinstance(it, FigureItem))
        self._label_count = sum(1 for it in items if isinstance(it, LabelItem))
        self._tb_count = sum(1 for it in items if isinstance(it, TextBoxItem))
        self._line_count = sum(1 for it in items if isinstance(it, LineItem))
        self.undo_stack.clear()
        self.undo_stack.setClean()
        self._sync_page_controls()
        self.layers.refresh()
        self.on_selection_changed()
        self.view.fit_page()

    def save_project(self) -> bool:
        if not self.current_path:
            return self.save_project_as()
        try:
            project.save_project(self.current_path, self.scene)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("Save Failed"), str(e))
            return False
        self.undo_stack.setClean()
        self._extra_dirty = False
        self._clear_autosave()                # the file is safe on disk now
        self._add_recent(self.current_path)
        self._update_title()
        return True

    # ------------------------------------------------- autosave / recovery
    @staticmethod
    def _autosave_dir() -> str:
        d = os.environ.get("FIGFORGE_AUTOSAVE_DIR")
        if not d:
            base = QtCore.QStandardPaths.writableLocation(
                QtCore.QStandardPaths.StandardLocation.AppDataLocation)
            d = os.path.join(base, "autosave")
        os.makedirs(d, exist_ok=True)
        return d

    def _autosave_paths(self) -> tuple[str, str]:
        d = self._autosave_dir()
        return os.path.join(d, "autosave.ffp"), os.path.join(d, "autosave.json")

    def _do_autosave(self):
        """Timer tick: snapshot only when there is unsaved, new work."""
        if not self._is_dirty() or not self.scene.iter_items():
            return
        idx = self.undo_stack.index()
        if idx == self._last_autosave_idx:
            return
        try:
            self.rescue_autosave()
            self._last_autosave_idx = idx
        except Exception:
            pass                     # autosave must never disturb editing

    def rescue_autosave(self):
        """Write a crash-recovery snapshot immediately (also called by the
        global exception hook)."""
        if not self.scene.iter_items():
            return
        ffp, meta = self._autosave_paths()
        project.save_project(ffp, self.scene)
        with open(meta, "w", encoding="utf-8") as fh:
            json.dump({"original_path": self.current_path or "",
                       "saved_at": time.strftime("%Y-%m-%d %H:%M")}, fh)

    def _clear_autosave(self):
        for p in self._autosave_paths():
            try:
                os.remove(p)
            except OSError:
                pass
        self._last_autosave_idx = -1

    def _pending_autosave(self):
        ffp, meta = self._autosave_paths()
        if not os.path.isfile(ffp):
            return None
        info = {}
        try:
            with open(meta, "r", encoding="utf-8") as fh:
                info = json.load(fh)
        except Exception:
            pass
        return ffp, info

    def _offer_restore(self):
        """On startup: a leftover autosave means the last session crashed."""
        pending = self._pending_autosave()
        if pending is None:
            return
        _ffp, info = pending
        when = info.get("saved_at") or "?"
        r = QtWidgets.QMessageBox.question(
            self, tr("Recovered work found"),
            tr("FigForge did not close properly last time. Restore the "
               "automatically saved work from {0}?").format(when),
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No)
        if r == QtWidgets.QMessageBox.StandardButton.Yes:
            self._restore_autosave()
        else:
            self._clear_autosave()

    def _restore_autosave(self) -> bool:
        pending = self._pending_autosave()
        if pending is None:
            return False
        ffp, info = pending
        try:
            config, items, tempdir = project.load_project(ffp)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("Open Failed"), str(e))
            self._clear_autosave()
            return False
        self._apply_loaded_project(config, items, tempdir)
        self.current_path = info.get("original_path") or None
        self._extra_dirty = True                 # recovered ⇒ needs saving
        self._clear_autosave()
        self._update_title()
        self.statusBar().showMessage(
            tr("Recovered unsaved work — remember to save it."), 8000)
        return True

    # ------------------------------------------------------------ recent files
    _MAX_RECENT = 8

    @staticmethod
    def _settings() -> QtCore.QSettings:
        return QtCore.QSettings("FigForge", "FigForge")

    def _recent_files(self) -> list[str]:
        val = self._settings().value("recent_files") or []
        if isinstance(val, str):
            val = [val]
        return [p for p in val if p]

    def _add_recent(self, path):
        path = os.path.abspath(path)
        key = os.path.normcase(path)
        lst = [p for p in self._recent_files() if os.path.normcase(p) != key]
        lst.insert(0, path)
        self._settings().setValue("recent_files", lst[:self._MAX_RECENT])

    def _remove_recent(self, path):
        key = os.path.normcase(path)
        lst = [p for p in self._recent_files() if os.path.normcase(p) != key]
        self._settings().setValue("recent_files", lst)

    def _rebuild_recent_menu(self):
        self.m_recent.clear()
        files = self._recent_files()
        if not files:
            a = self.m_recent.addAction(tr("(empty)"))
            a.setEnabled(False)
            return
        for i, p in enumerate(files, 1):
            a = self.m_recent.addAction(f"&{i}  {os.path.basename(p)}")
            a.setToolTip(p)
            a.triggered.connect(lambda _=False, path=p: self.open_recent(path))
        self.m_recent.addSeparator()
        self.m_recent.addAction(
            tr("Clear Menu"),
            lambda: self._settings().setValue("recent_files", []))

    def save_project_as(self) -> bool:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, tr("Save As"), tr("Untitled") + constants.PROJECT_EXT,
            tr("FigForge Project (*.ffp)"))
        if not path:
            return False
        if not path.lower().endswith(constants.PROJECT_EXT):
            path += constants.PROJECT_EXT
        self.current_path = path
        return self.save_project()

    def _sync_page_controls(self):
        for w in (self.cmb_page, self.cmb_orient, self.chk_grid):
            w.blockSignals(True)
        self.cmb_page.setCurrentText(self.scene.page_name)
        self.cmb_orient.setCurrentIndex(0 if self.scene.orientation == constants.PORTRAIT else 1)
        self.chk_grid.setChecked(self.scene.grid_visible)
        for w in (self.cmb_page, self.cmb_orient, self.chk_grid):
            w.blockSignals(False)
        self.scene.snap_to_grid = self.scene.grid_visible
        self._update_page_label()

    # ----------------------------------------------------------------- export
    def _has_items(self) -> bool:
        if not self.scene.iter_items():
            QtWidgets.QMessageBox.information(
                self, tr("Info"), tr("The page is empty — import an image first."))
            return False
        return True

    def export_pdf(self):
        if not self._has_items():
            return
        dlg = ExportDialog(self, raster=False)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, tr("Export PDF"), "figure.pdf", tr("PDF (*.pdf)"))
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            exporters.export_pdf(self.scene, path, white_bg=True,
                                 crop_margin_pt=dlg.crop_margin_pt())
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("Export Failed"), str(e))
            return
        self.statusBar().showMessage(tr("Exported vector PDF: {0}").format(path), 6000)

    def export_png(self):
        if not self._has_items():
            return
        dlg = ExportDialog(self, raster=True, allow_transparent=True)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, tr("Export PNG"), "figure.png", tr("PNG (*.png)"))
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            exporters.export_png(self.scene, path, dpi=dlg.dpi(),
                                 transparent=dlg.transparent(),
                                 crop_margin_pt=dlg.crop_margin_pt())
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("Export Failed"), str(e))
            return
        self.statusBar().showMessage(
            tr("Exported {0} DPI PNG: {1}").format(dlg.dpi(), path), 6000)

    def export_tiff(self):
        if not self._has_items():
            return
        dlg = ExportDialog(self, raster=True, allow_transparent=False)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, tr("Export TIFF"), "figure.tiff", tr("TIFF (*.tiff *.tif)"))
        if not path:
            return
        if not path.lower().endswith((".tif", ".tiff")):
            path += ".tiff"
        try:
            exporters.export_tiff(self.scene, path, dpi=dlg.dpi(),
                                  crop_margin_pt=dlg.crop_margin_pt())
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, tr("Export Failed"), str(e))
            return
        self.statusBar().showMessage(
            tr("Exported {0} DPI TIFF: {1}").format(dlg.dpi(), path), 6000)

    # ------------------------------------------------------------------ help
    def show_help(self):
        QtWidgets.QMessageBox.information(self, tr("User Guide"), tr("USER_GUIDE"))

    def show_about(self):
        from . import __version__
        QtWidgets.QMessageBox.about(
            self, tr("About") + " FigForge",
            f"<b>{tr('FigForge — Academic Figure Layout')}</b> v{__version__}<br><br>"
            + tr("ABOUT_BODY"))

    # ------------------------------------------------------------------ close
    def closeEvent(self, event):
        if self._confirm_discard():
            try:
                self.undo_stack.cleanChanged.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._autosave_timer.stop()
            self._clear_autosave()          # clean exit ⇒ nothing to recover
            project.cleanup_tempdir(self._tempdir)
            event.accept()
        else:
            event.ignore()
