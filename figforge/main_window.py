"""The application main window — wires the canvas, panels, menus and actions."""
from __future__ import annotations

import os

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

_IMPORT_FILTER = (
    "所有支持的图片 (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.gif *.webp "
    "*.pdf *.svg *.eps *.ps);;位图 (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.gif *.webp);;"
    "矢量 (*.pdf *.svg *.eps *.ps);;所有文件 (*.*)"
)


class ExportRasterDialog(QtWidgets.QDialog):
    def __init__(self, parent, allow_transparent=True):
        super().__init__(parent)
        self.setWindowTitle("导出设置")
        form = QtWidgets.QFormLayout(self)
        self.cmb_dpi = QtWidgets.QComboBox()
        for d in constants.DPI_CHOICES:
            self.cmb_dpi.addItem(f"{d} DPI", d)
        self.cmb_dpi.setCurrentText(f"{constants.DEFAULT_DPI} DPI")
        form.addRow("分辨率", self.cmb_dpi)
        self.chk_transparent = QtWidgets.QCheckBox("透明背景")
        if allow_transparent:
            form.addRow("", self.chk_transparent)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def dpi(self) -> int:
        return self.cmb_dpi.currentData()

    def transparent(self) -> bool:
        return self.chk_transparent.isChecked()


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

        self._build_docks()
        self._build_actions()
        self._build_menus()
        self._build_toolbars()
        self._build_statusbar()

        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.scene.sceneEdited.connect(self._on_scene_edited)
        self.undo_stack.cleanChanged.connect(lambda *_: self._update_title())
        self.view.zoomChanged.connect(
            lambda p: self.lbl_zoom.setText(f"缩放 {p:.0f}%"))
        self.view.cursorMoved.connect(self._on_cursor)
        self.view.filesDropped.connect(self.on_files_dropped)

        self.resize(1280, 840)
        self._update_title()
        QtCore.QTimer.singleShot(0, self.view.fit_page)

    # ------------------------------------------------------------------ docks
    def _build_docks(self):
        self.properties = PropertiesPanel(self)
        d1 = QtWidgets.QDockWidget("属性", self)
        d1.setWidget(self.properties)
        d1.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea
                           | Qt.DockWidgetArea.LeftDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, d1)

        self.layers = LayersPanel(self)
        d2 = QtWidgets.QDockWidget("图层", self)
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
        self.a_new = self._act("新建", self.new_project, QKS.StandardKey.New)
        self.a_open = self._act("打开…", self.open_project, QKS.StandardKey.Open)
        self.a_save = self._act("保存", self.save_project, QKS.StandardKey.Save)
        self.a_save_as = self._act("另存为…", self.save_project_as, QKS.StandardKey.SaveAs)
        self.a_import = self._act("导入图片…", self.import_figures, "Ctrl+I")
        self.a_exp_pdf = self._act("导出 PDF（矢量）…", self.export_pdf)
        self.a_exp_png = self._act("导出 PNG（高分辨率）…", self.export_png)
        self.a_exp_tiff = self._act("导出 TIFF…", self.export_tiff)
        self.a_quit = self._act("退出", self.close, QKS.StandardKey.Quit)

        self.a_undo = self.undo_stack.createUndoAction(self, "撤销")
        self.a_undo.setShortcut(QKS.StandardKey.Undo)
        self.a_redo = self.undo_stack.createRedoAction(self, "重做")
        self.a_redo.setShortcut(QKS.StandardKey.Redo)
        self.a_delete = self._act("删除", self.delete_selected, QKS.StandardKey.Delete)
        self.a_select_all = self._act("全选", self.select_all, QKS.StandardKey.SelectAll)
        self.a_duplicate = self._act("复制副本", self.duplicate_selected, "Ctrl+D")

        self.a_add_label = self._act("添加文字标签", self.add_label, "T")
        self.a_add_textbox = self._act("添加文本框", self.add_textbox)
        self.a_add_line = self._act("添加线条", self.add_line)
        self.a_crop = self._act("裁剪图片…", self.crop_selected, "C")
        self.a_rot_l = self._act("向左旋转 90°", lambda: self.rotate_selected(-90))
        self.a_rot_r = self._act("向右旋转 90°", lambda: self.rotate_selected(90))
        self.a_rot_reset = self._act("重置旋转", self.reset_rotation)

        self.a_al_left = self._act("左对齐", lambda: self.align("left"))
        self.a_al_hc = self._act("水平居中", lambda: self.align("hcenter"))
        self.a_al_right = self._act("右对齐", lambda: self.align("right"))
        self.a_al_top = self._act("顶对齐", lambda: self.align("top"))
        self.a_al_vm = self._act("垂直居中", lambda: self.align("vmiddle"))
        self.a_al_bottom = self._act("底对齐", lambda: self.align("bottom"))
        self.a_dist_h = self._act("水平等距分布", lambda: self.distribute("h"))
        self.a_dist_v = self._act("垂直等距分布", lambda: self.distribute("v"))

        self.a_front = self._act("置于顶层", lambda: self.change_z("front"))
        self.a_up = self._act("上移一层", lambda: self.change_z("up"))
        self.a_down = self._act("下移一层", lambda: self.change_z("down"))
        self.a_back = self._act("置于底层", lambda: self.change_z("back"))

        self.a_zoom_in = self._act("放大", self.view.zoom_in, QKS.StandardKey.ZoomIn)
        self.a_zoom_out = self._act("缩小", self.view.zoom_out, QKS.StandardKey.ZoomOut)
        self.a_fit = self._act("适应页面", self.view.fit_page, "Ctrl+0")
        self.a_reset_zoom = self._act("实际大小 100%", self.view.reset_zoom)

        # attach line-art icons (also appear next to the menu items)
        ic = build_icons(self.palette().color(QtGui.QPalette.ColorRole.WindowText))
        for act, key in (
            (self.a_import, "import"), (self.a_add_label, "text"),
            (self.a_add_textbox, "textbox"), (self.a_add_line, "line"),
            (self.a_crop, "crop"),
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
        m = mb.addMenu("文件")
        m.addActions([self.a_new, self.a_open, self.a_save, self.a_save_as])
        m.addSeparator()
        m.addAction(self.a_import)
        m.addSeparator()
        m.addActions([self.a_exp_pdf, self.a_exp_png, self.a_exp_tiff])
        m.addSeparator()
        m.addAction(self.a_quit)

        m = mb.addMenu("编辑")
        m.addActions([self.a_undo, self.a_redo])
        m.addSeparator()
        m.addActions([self.a_duplicate, self.a_delete, self.a_select_all])

        m = mb.addMenu("对象")
        m.addAction(self.a_add_label)
        m.addAction(self.a_add_textbox)
        m.addAction(self.a_add_line)
        m.addAction(self.a_crop)
        m.addSeparator()
        sub = m.addMenu("对齐")
        sub.addActions([self.a_al_left, self.a_al_hc, self.a_al_right])
        sub.addSeparator()
        sub.addActions([self.a_al_top, self.a_al_vm, self.a_al_bottom])
        sub.addSeparator()
        sub.addActions([self.a_dist_h, self.a_dist_v])
        sub = m.addMenu("层叠顺序")
        sub.addActions([self.a_front, self.a_up, self.a_down, self.a_back])
        sub = m.addMenu("旋转")
        sub.addActions([self.a_rot_l, self.a_rot_r, self.a_rot_reset])

        m = mb.addMenu("视图")
        m.addActions([self.a_zoom_in, self.a_zoom_out, self.a_fit, self.a_reset_zoom])

        m = mb.addMenu("帮助")
        m.addAction(self._act("使用说明", self.show_help))
        m.addAction(self._act("关于", self.show_about))

    def _build_toolbars(self):
        tb = self.addToolBar("主工具栏")
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        tb.setIconSize(QtCore.QSize(22, 22))
        tb.addAction(self.a_import)
        tb.addAction(self.a_add_label)
        tb.addAction(self.a_add_textbox)
        tb.addAction(self.a_add_line)
        tb.addSeparator()
        tb.addActions([self.a_al_left, self.a_al_hc, self.a_al_right,
                       self.a_al_top, self.a_al_vm, self.a_al_bottom])
        tb.addSeparator()
        tb.addActions([self.a_front, self.a_up, self.a_down, self.a_back])
        tb.addSeparator()
        tb.addActions([self.a_rot_l, self.a_rot_r, self.a_crop])
        tb.addSeparator()
        tb.addActions([self.a_exp_pdf, self.a_exp_png])

        # page / grid toolbar
        pb = self.addToolBar("页面")
        pb.addWidget(QtWidgets.QLabel(" 纸张 "))
        self.cmb_page = QtWidgets.QComboBox()
        self.cmb_page.addItems(list(constants.PAGE_SIZES.keys()))
        pb.addWidget(self.cmb_page)
        self.cmb_orient = QtWidgets.QComboBox()
        self.cmb_orient.addItems(["纵向", "横向"])
        pb.addWidget(self.cmb_orient)
        self.cmb_page.currentIndexChanged.connect(self._page_changed)
        self.cmb_orient.currentIndexChanged.connect(self._page_changed)
        pb.addSeparator()
        self.chk_grid = QtWidgets.QCheckBox("网格")
        self.chk_snap = QtWidgets.QCheckBox("智能吸附")
        self.chk_snap.setChecked(True)
        pb.addWidget(self.chk_grid)
        pb.addWidget(self.chk_snap)
        self.cmb_grid = QtWidgets.QComboBox()
        for mm in (1, 2, 5, 10):
            self.cmb_grid.addItem(f"{mm} mm", mm)
        self.cmb_grid.setCurrentText("5 mm")
        pb.addWidget(self.cmb_grid)
        self.chk_grid.toggled.connect(self._grid_changed)
        self.chk_snap.toggled.connect(
            lambda on: setattr(self.scene, "snap_enabled", on))
        self.cmb_grid.currentIndexChanged.connect(self._grid_changed)

    def _build_statusbar(self):
        sb = self.statusBar()
        self.lbl_pos = QtWidgets.QLabel("X: -  Y: -")
        self.lbl_page = QtWidgets.QLabel("")
        self.lbl_zoom = QtWidgets.QLabel("缩放 100%")
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
        if isinstance(item, (LabelItem, TextBoxItem)):
            item.editRequested.connect(self.edit_text)

    def _selected(self):
        return [it for it in self.scene.iter_items() if it.isSelected()]

    def _select_only(self, items):
        self.scene.clearSelection()
        for it in items:
            it.setSelected(True)

    # ----------------------------------------------------------------- import
    def import_figures(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "导入图片", "", _IMPORT_FILTER)
        if paths:
            self.add_figures_from_paths(paths)

    def on_files_dropped(self, paths, scene_pos):
        """Files dragged from Explorer onto the canvas."""
        self.add_figures_from_paths(paths, at_scene_pos=scene_pos)

    def add_figures_from_paths(self, paths, at_scene_pos=None):
        new_items = []
        self.undo_stack.beginMacro("导入图片")
        for path in paths:
            try:
                page_index = 0
                if path.lower().endswith(".pdf"):
                    n = importers.pdf_page_count(path)
                    if n > 1:
                        val, ok = QtWidgets.QInputDialog.getInt(
                            self, "选择页面",
                            f"{os.path.basename(path)} 有 {n} 页，导入第几页？",
                            1, 1, n)
                        if not ok:
                            continue
                        page_index = val - 1
                source = importers.load_source(path, page_index)
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "导入失败", f"{os.path.basename(path)}\n\n{e}")
                continue
            self._fig_count += 1
            item = FigureItem(source, name=f"图片 {self._fig_count}")
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
        item.set_name(f"标签 {self._label_count}")
        center = self.view.mapToScene(self.view.viewport().rect().center())
        item.setZValue(self.scene.next_z())
        item.set_geometry(center.x(), center.y(), *item.size())
        self._register_new_item(item)
        self._push(AddItemCommand(self.scene, item))
        self._select_only([item])

    def add_textbox(self):
        self._tb_count += 1
        item = TextBoxItem(text="文本框", family=self._default_label_font())
        item.set_name(f"文本框 {self._tb_count}")
        center = self.view.mapToScene(self.view.viewport().rect().center())
        w, h = item.size()
        item.setZValue(self.scene.next_z())
        item.set_geometry(center.x() - w / 2, center.y() - h / 2, w, h)
        self._register_new_item(item)
        self._push(AddItemCommand(self.scene, item))
        self._select_only([item])

    def add_line(self):
        self._line_count += 1
        item = LineItem()
        item.set_name(f"线条 {self._line_count}")
        center = self.view.mapToScene(self.view.viewport().rect().center())
        item.setZValue(self.scene.next_z())
        item.setPos(center.x() - 60, center.y())
        self._register_new_item(item)
        self._push(AddItemCommand(self.scene, item))
        self._select_only([item])

    def edit_text(self, item):
        text, ok = QtWidgets.QInputDialog.getMultiLineText(
            self, "编辑文字", "内容：", item.text)
        if not ok:
            return
        old = item.text
        self._push(FuncCommand("编辑文字",
                               lambda: item.set_text(text),
                               lambda: item.set_text(old)))

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
        self._rotate_to(lambda r: (r + delta) % 360, "旋转")

    def reset_rotation(self):
        self._rotate_to(lambda r: 0.0, "重置旋转")

    def crop_selected(self):
        figs = [it for it in self._selected() if isinstance(it, FigureItem)]
        if len(figs) != 1:
            QtWidgets.QMessageBox.information(self, "裁剪", "请选择单个图片进行裁剪。")
            return
        it = figs[0]
        from .ui.crop_dialog import CropDialog
        dlg = CropDialog(self, it._pixmap, it.crop)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        old, new = it.crop, dlg.get_crop()
        if new == old:
            return
        self._push(FuncCommand("裁剪",
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
        self.undo_stack.beginMacro("复制副本")
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
                             name=f"图片 {self._fig_count}")
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
            dup.set_name(f"文本框 {self._tb_count}")
            return dup
        if isinstance(it, LineItem):
            self._line_count += 1
            dup = LineItem(p1=QtCore.QPointF(it.p1), p2=QtCore.QPointF(it.p2),
                           color=QtGui.QColor(it.color), width_pt=it.width_pt,
                           dashed=it.dashed, arrow=it.arrow)
            dup.set_name(f"线条 {self._line_count}")
            return dup
        if isinstance(it, LabelItem):
            self._label_count += 1
            dup = LabelItem(text=it.text, family=it.family, size_pt=it.size_pt,
                            bold=it.bold, italic=it.italic,
                            color=QtGui.QColor(it.color))
            dup.align = it.align
            dup._recompute()
            dup.set_name(f"标签 {self._label_count}")
            return dup
        return None

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
        self._push(FuncCommand("调整层叠",
                               lambda: [it.setZValue(new[it]) for it in order],
                               lambda: [it.setZValue(old[it]) for it in order]))
        self.layers.refresh()

    # -------------------------------------------------------- align/distribute
    def _with_geometry_undo(self, text, mutate):
        items = [it for it in self._selected() if isinstance(it, BaseItem)]
        if not items:
            return
        old = {it: it.get_geometry() for it in items}
        mutate(items)
        new = {it: it.get_geometry() for it in items}
        if new == old:
            return
        self._push(FuncCommand(text,
                               lambda: [it.set_geometry(*new[it]) for it in items],
                               lambda: [it.set_geometry(*old[it]) for it in items]))

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
        self._with_geometry_undo("对齐", mut)

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
        self._with_geometry_undo("分布", mut)

    # ------------------------------------------------------------ page / grid
    def _page_changed(self, *_):
        page = self.cmb_page.currentText()
        orient = constants.PORTRAIT if self.cmb_orient.currentIndex() == 0 else constants.LANDSCAPE
        self.scene.set_page(page, orient)
        self._update_page_label()
        self.view.fit_page()

    def _grid_changed(self, *_):
        self.scene.set_grid(mm=self.cmb_grid.currentData(),
                            visible=self.chk_grid.isChecked())
        self.scene.snap_to_grid = self.chk_grid.isChecked()

    def _update_page_label(self):
        self.lbl_page.setText(
            f"{self.scene.page_name} · {self.scene.orientation} · "
            f"{self.scene.page_w * constants.MM_PER_PT:.0f}×"
            f"{self.scene.page_h * constants.MM_PER_PT:.0f} mm")

    # --------------------------------------------------------------- signals
    def on_selection_changed(self):
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

    # ------------------------------------------------------------- dirty/title
    def _is_dirty(self) -> bool:
        return self._extra_dirty or not self.undo_stack.isClean()

    def _update_title(self):
        name = os.path.basename(self.current_path) if self.current_path else "未命名"
        star = "*" if self._is_dirty() else ""
        self.setWindowTitle(f"{star}{name} — {constants.APP_TITLE}")

    def _confirm_discard(self) -> bool:
        if not self._is_dirty():
            return True
        r = QtWidgets.QMessageBox.question(
            self, "未保存", "当前项目有未保存的更改，是否保存？",
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
        self._sync_page_controls()
        self.layers.refresh()
        self.on_selection_changed()
        self.view.fit_page()
        self._update_title()

    def open_project(self):
        if not self._confirm_discard():
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "打开项目", "", f"FigForge 项目 (*{constants.PROJECT_EXT})")
        if not path:
            return
        try:
            config, items, tempdir = project.load_project(path)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "打开失败", str(e))
            return
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

        project.cleanup_tempdir(self._tempdir)
        self._tempdir = tempdir
        self.current_path = path
        self._fig_count = sum(1 for it in items if isinstance(it, FigureItem))
        self._label_count = sum(1 for it in items if isinstance(it, LabelItem))
        self._tb_count = sum(1 for it in items if isinstance(it, TextBoxItem))
        self._line_count = sum(1 for it in items if isinstance(it, LineItem))
        self.undo_stack.clear()
        self.undo_stack.setClean()
        self._extra_dirty = False
        self._sync_page_controls()
        self.layers.refresh()
        self.on_selection_changed()
        self.view.fit_page()
        self._update_title()

    def save_project(self) -> bool:
        if not self.current_path:
            return self.save_project_as()
        try:
            project.save_project(self.current_path, self.scene)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "保存失败", str(e))
            return False
        self.undo_stack.setClean()
        self._extra_dirty = False
        self._update_title()
        return True

    def save_project_as(self) -> bool:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "另存为", "未命名" + constants.PROJECT_EXT,
            f"FigForge 项目 (*{constants.PROJECT_EXT})")
        if not path:
            return False
        if not path.lower().endswith(constants.PROJECT_EXT):
            path += constants.PROJECT_EXT
        self.current_path = path
        return self.save_project()

    def _sync_page_controls(self):
        for w in (self.cmb_page, self.cmb_orient, self.chk_grid, self.cmb_grid):
            w.blockSignals(True)
        self.cmb_page.setCurrentText(self.scene.page_name)
        self.cmb_orient.setCurrentIndex(0 if self.scene.orientation == constants.PORTRAIT else 1)
        self.chk_grid.setChecked(self.scene.grid_visible)
        self.cmb_grid.setCurrentText(f"{int(self.scene.grid_mm)} mm")
        for w in (self.cmb_page, self.cmb_orient, self.chk_grid, self.cmb_grid):
            w.blockSignals(False)
        self._update_page_label()

    # ----------------------------------------------------------------- export
    def _has_items(self) -> bool:
        if not self.scene.iter_items():
            QtWidgets.QMessageBox.information(self, "提示", "页面是空的，先导入图片吧。")
            return False
        return True

    def export_pdf(self):
        if not self._has_items():
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出 PDF", "figure.pdf", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            exporters.export_pdf(self.scene, path, white_bg=True)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "导出失败", str(e))
            return
        self.statusBar().showMessage(f"已导出矢量 PDF：{path}", 6000)

    def export_png(self):
        if not self._has_items():
            return
        dlg = ExportRasterDialog(self, allow_transparent=True)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出 PNG", "figure.png", "PNG (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            exporters.export_png(self.scene, path, dpi=dlg.dpi(),
                                 transparent=dlg.transparent())
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "导出失败", str(e))
            return
        self.statusBar().showMessage(f"已导出 {dlg.dpi()} DPI PNG：{path}", 6000)

    def export_tiff(self):
        if not self._has_items():
            return
        dlg = ExportRasterDialog(self, allow_transparent=False)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "导出 TIFF", "figure.tiff", "TIFF (*.tiff *.tif)")
        if not path:
            return
        if not path.lower().endswith((".tif", ".tiff")):
            path += ".tiff"
        try:
            exporters.export_tiff(self.scene, path, dpi=dlg.dpi())
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "导出失败", str(e))
            return
        self.statusBar().showMessage(f"已导出 {dlg.dpi()} DPI TIFF：{path}", 6000)

    # ------------------------------------------------------------------ help
    def show_help(self):
        QtWidgets.QMessageBox.information(
            self, "使用说明",
            "1. 文件 → 导入图片：支持 PNG/JPG/TIFF/PDF/SVG/EPS 等。\n"
            "2. 拖动移动；选中后拖角缩放（默认等比，按住 Shift 临时切换）。\n"
            "3. 对象 → 添加文字标签：手动加 a/b/c 等编号，双击可多行编辑。\n"
            "4. 用对齐/分布工具和智能吸附把子图排整齐。\n"
            "5. 文件 → 导出：PDF 保留矢量；PNG/TIFF 可选最高 1200 DPI。\n"
            "6. 保存为 .ffp 项目（自带所有素材，可随时再编辑）。")

    def show_about(self):
        from . import __version__
        QtWidgets.QMessageBox.about(
            self, "关于 FigForge",
            f"<b>{constants.APP_TITLE}</b> v{__version__}<br><br>"
            "面向学术论文的轻量图排版工具。<br>"
            "矢量子图导出 PDF 仍为矢量，位图按原始分辨率嵌入。<br>"
            "基于 PySide6 + PyMuPDF + Pillow。")

    # ------------------------------------------------------------------ close
    def closeEvent(self, event):
        if self._confirm_discard():
            try:
                self.undo_stack.cleanChanged.disconnect()
            except (RuntimeError, TypeError):
                pass
            project.cleanup_tempdir(self._tempdir)
            event.accept()
        else:
            event.ignore()
