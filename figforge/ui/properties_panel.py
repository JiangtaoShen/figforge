"""Properties dock — geometry + per-type styling for the current selection."""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from .. import constants, fonts
from ..canvas.items import FigureItem, LabelItem, LineItem, TextBoxItem
from ..commands import FuncCommand

_MM = constants.MM_PER_PT
_PT = constants.PT_PER_MM


class PropertiesPanel(QtWidgets.QScrollArea):
    def __init__(self, main):
        super().__init__()
        self.main = main
        self._item = None
        self._loading = False
        self._geom_conn = None
        self._color = QtGui.QColor("black")
        self._border_color = QtGui.QColor(70, 70, 70)
        self._fill_color = QtGui.QColor("white")
        self._line_color = QtGui.QColor(40, 40, 40)
        self.setWidgetResizable(True)
        self._build()
        self.set_selection([])

    # ------------------------------------------------------------- builders
    def _spin(self, lo=-4000.0, hi=4000.0, dec=2, suffix=" mm", step=1.0):
        s = QtWidgets.QDoubleSpinBox()
        s.setRange(lo, hi)
        s.setDecimals(dec)
        s.setSuffix(suffix)
        s.setSingleStep(step)
        s.setKeyboardTracking(False)
        return s

    def _build(self):
        root = QtWidgets.QWidget()
        self.setWidget(root)
        lay = QtWidgets.QVBoxLayout(root)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(10)

        self.lbl_kind = QtWidgets.QLabel("（未选择对象）")
        self.lbl_kind.setStyleSheet("font-weight:600;")
        lay.addWidget(self.lbl_kind)

        # --- geometry ---------------------------------------------------
        self.box_geom = QtWidgets.QGroupBox("位置与大小")
        g = QtWidgets.QFormLayout(self.box_geom)
        self.spin_x = self._spin()
        self.spin_y = self._spin()
        self.spin_w = self._spin()
        self.spin_h = self._spin()
        self.spin_rot = self._spin(-360, 360, 1, " °")
        self.spin_rot.setWrapping(True)
        g.addRow("X", self.spin_x)
        g.addRow("Y", self.spin_y)
        g.addRow("宽", self.spin_w)
        g.addRow("高", self.spin_h)
        g.addRow("旋转", self.spin_rot)
        lay.addWidget(self.box_geom)
        self.spin_x.editingFinished.connect(self._apply_geometry)
        self.spin_y.editingFinished.connect(self._apply_geometry)
        self.spin_w.editingFinished.connect(lambda: self._wh_edited("w"))
        self.spin_h.editingFinished.connect(lambda: self._wh_edited("h"))
        self.spin_rot.editingFinished.connect(self._apply_rotation)

        # --- image options ----------------------------------------------
        self.box_image = QtWidgets.QGroupBox("图片选项")
        ig = QtWidgets.QFormLayout(self.box_image)
        self.chk_aspect = QtWidgets.QCheckBox("锁定宽高比")
        self.btn_crop = QtWidgets.QPushButton("裁剪…")
        ig.addRow("", self.chk_aspect)
        ig.addRow("裁剪", self.btn_crop)
        lay.addWidget(self.box_image)
        self.chk_aspect.toggled.connect(self._aspect_toggled)
        self.btn_crop.clicked.connect(self._open_crop)

        # --- text style (label + text box) ------------------------------
        self.box_text = QtWidgets.QGroupBox("文字")
        f = QtWidgets.QFormLayout(self.box_text)
        self.ed_text = QtWidgets.QLineEdit()
        self.cmb_font = QtWidgets.QComboBox()
        self.cmb_font.addItems(fonts.available_families())
        self.spin_size = self._spin(1, 400, 1, " pt")
        self.btn_bold = QtWidgets.QToolButton()
        self.btn_bold.setText("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setStyleSheet("font-weight:bold;")
        self.btn_italic = QtWidgets.QToolButton()
        self.btn_italic.setText("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setStyleSheet("font-style:italic;")
        srow = QtWidgets.QHBoxLayout()
        srow.addWidget(self.btn_bold)
        srow.addWidget(self.btn_italic)
        srow.addStretch(1)
        sw = QtWidgets.QWidget()
        sw.setLayout(srow)
        self.btn_color = QtWidgets.QPushButton("颜色")
        self.cmb_align = QtWidgets.QComboBox()
        self.cmb_align.addItems(["左对齐", "居中", "右对齐"])
        f.addRow("文字", self.ed_text)
        f.addRow("字体", self.cmb_font)
        f.addRow("字号", self.spin_size)
        f.addRow("样式", sw)
        f.addRow("颜色", self.btn_color)
        f.addRow("对齐", self.cmb_align)
        lay.addWidget(self.box_text)
        self.ed_text.editingFinished.connect(self._apply_text)
        self.cmb_font.currentIndexChanged.connect(self._apply_text)
        self.spin_size.editingFinished.connect(self._apply_text)
        self.btn_bold.toggled.connect(self._apply_text)
        self.btn_italic.toggled.connect(self._apply_text)
        self.cmb_align.currentIndexChanged.connect(self._apply_text)
        self.btn_color.clicked.connect(self._pick_text_color)

        # --- text-box frame (border / fill) -----------------------------
        self.box_frame = QtWidgets.QGroupBox("文本框边框 / 填充")
        bf = QtWidgets.QFormLayout(self.box_frame)
        self.chk_border = QtWidgets.QCheckBox("显示边框")
        self.spin_bw = self._spin(0, 20, 1, " pt", 0.5)
        self.btn_border_color = QtWidgets.QPushButton("边框颜色")
        self.chk_fill = QtWidgets.QCheckBox("填充背景")
        self.btn_fill_color = QtWidgets.QPushButton("填充颜色")
        bf.addRow("", self.chk_border)
        bf.addRow("线宽", self.spin_bw)
        bf.addRow("", self.btn_border_color)
        bf.addRow("", self.chk_fill)
        bf.addRow("", self.btn_fill_color)
        lay.addWidget(self.box_frame)
        self.chk_border.toggled.connect(self._apply_frame)
        self.spin_bw.editingFinished.connect(self._apply_frame)
        self.btn_border_color.clicked.connect(lambda: self._pick_frame_color("border"))
        self.chk_fill.toggled.connect(self._apply_frame)
        self.btn_fill_color.clicked.connect(lambda: self._pick_frame_color("fill"))

        # --- line -------------------------------------------------------
        self.box_line = QtWidgets.QGroupBox("线条")
        lf = QtWidgets.QFormLayout(self.box_line)
        self.btn_line_color = QtWidgets.QPushButton("颜色")
        self.spin_lw = self._spin(0.1, 50, 1, " pt", 0.5)
        self.cmb_style = QtWidgets.QComboBox()
        self.cmb_style.addItems(["实线", "虚线"])
        self.cmb_arrow = QtWidgets.QComboBox()
        self.cmb_arrow.addItems(["无箭头", "末端箭头", "两端箭头"])
        lf.addRow("颜色", self.btn_line_color)
        lf.addRow("线宽", self.spin_lw)
        lf.addRow("线型", self.cmb_style)
        lf.addRow("箭头", self.cmb_arrow)
        lay.addWidget(self.box_line)
        self.btn_line_color.clicked.connect(self._pick_line_color)
        self.spin_lw.editingFinished.connect(self._apply_line)
        self.cmb_style.currentIndexChanged.connect(self._apply_line)
        self.cmb_arrow.currentIndexChanged.connect(self._apply_line)

        self.info = QtWidgets.QLabel("")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color:#666; font-size:11px;")
        lay.addWidget(self.info)
        lay.addStretch(1)

    # ------------------------------------------------------------ selection
    def set_selection(self, items):
        if self._geom_conn is not None:
            try:
                self._geom_conn.geometryChanged.disconnect(self._on_item_geom)
            except (RuntimeError, TypeError):
                pass
            self._geom_conn = None

        single = items[0] if len(items) == 1 else None
        self._item = single
        is_fig = isinstance(single, FigureItem)
        is_label = isinstance(single, LabelItem)
        is_tb = isinstance(single, TextBoxItem)
        is_line = isinstance(single, LineItem)

        self.box_geom.setVisible(single is not None and not is_line)
        self.box_image.setVisible(is_fig)
        self.box_text.setVisible(is_label or is_tb)
        self.box_frame.setVisible(is_tb)
        self.box_line.setVisible(is_line)

        if single is None:
            self.lbl_kind.setText("多选对象（用对齐工具）" if items else "（未选择对象）")
            self.info.setText("提示：拖动移动；选中后拖角缩放，拖顶部圆点旋转。")
            return

        self.spin_w.setEnabled(is_fig or is_tb)
        self.spin_h.setEnabled(is_fig or is_tb)
        self.spin_rot.setEnabled(is_fig or is_tb)

        kind = {"FigureItem": "图片", "LabelItem": "标签",
                "TextBoxItem": "文本框", "LineItem": "线条"}.get(
                    type(single).__name__, "对象")
        self.lbl_kind.setText(f"{kind}：{single.name()}")

        if not is_line:
            self._load_geometry()
        if is_label or is_tb:
            self._load_text()
        if is_tb:
            self._load_frame()
        if is_line:
            self._load_line()

        if is_fig:
            self.info.setText("来源：" + ("矢量" if single._source_kind == "vector" else "位图"))
        elif is_line:
            self.info.setText("选中后拖两端圆点可调整线条。")
        else:
            self.info.setText("双击对象可多行编辑文字。")

        self._geom_conn = single
        single.geometryChanged.connect(self._on_item_geom)

    def _on_item_geom(self):
        if self._item is not None and not isinstance(self._item, LineItem):
            self._load_geometry()

    # ------------------------------------------------------------- loaders
    def _load_geometry(self):
        it = self._item
        if it is None or isinstance(it, LineItem):
            return
        self._loading = True
        x, y, w, h = it.get_geometry()
        self.spin_x.setValue(x * _MM)
        self.spin_y.setValue(y * _MM)
        self.spin_w.setValue(w * _MM)
        self.spin_h.setValue(h * _MM)
        self.spin_rot.setValue(it.rotation())
        if isinstance(it, FigureItem):
            self.chk_aspect.setChecked(it.aspect_locked)
        self._loading = False

    def _load_text(self):
        it = self._item
        self._loading = True
        self.ed_text.setText(it.text)
        i = self.cmb_font.findText(it.family)
        if i >= 0:
            self.cmb_font.setCurrentIndex(i)
        self.spin_size.setValue(it.size_pt)
        self.btn_bold.setChecked(it.bold)
        self.btn_italic.setChecked(it.italic)
        self.cmb_align.setCurrentIndex({"left": 0, "center": 1, "right": 2}.get(it.align, 0))
        self._color = QtGui.QColor(it.color)
        self._tint(self.btn_color, self._color)
        self._loading = False

    def _load_frame(self):
        it = self._item
        self._loading = True
        self.chk_border.setChecked(it.border)
        self.spin_bw.setValue(it.border_width)
        self._border_color = QtGui.QColor(it.border_color)
        self._tint(self.btn_border_color, self._border_color)
        self.chk_fill.setChecked(it.fill)
        self._fill_color = QtGui.QColor(it.fill_color)
        self._tint(self.btn_fill_color, self._fill_color)
        self._loading = False

    def _load_line(self):
        it = self._item
        self._loading = True
        self._line_color = QtGui.QColor(it.color)
        self._tint(self.btn_line_color, self._line_color)
        self.spin_lw.setValue(it.width_pt)
        self.cmb_style.setCurrentIndex(1 if it.dashed else 0)
        self.cmb_arrow.setCurrentIndex({"none": 0, "end": 1, "both": 2}.get(it.arrow, 0))
        self._loading = False

    # --------------------------------------------------------------- apply
    def _push(self, cmd):
        if self.main.undo_stack is not None:
            self.main.undo_stack.push(cmd)

    def _apply_geometry(self):
        it = self._item
        if self._loading or it is None or isinstance(it, LineItem):
            return
        old = it.get_state()
        w = self.spin_w.value() * _PT if self.spin_w.isEnabled() else old[2]
        h = self.spin_h.value() * _PT if self.spin_h.isEnabled() else old[3]
        new = (self.spin_x.value() * _PT, self.spin_y.value() * _PT, w, h, old[4])
        if new == old:
            return
        self._push(FuncCommand("修改几何",
                               lambda: it.set_state(new),
                               lambda: it.set_state(old)))

    def _wh_edited(self, which):
        it = self._item
        if self._loading or it is None:
            return
        if isinstance(it, FigureItem) and it.aspect_locked:
            asp = it.source_aspect()
            self._loading = True
            if which == "w":
                self.spin_h.setValue(self.spin_w.value() / asp)
            else:
                self.spin_w.setValue(self.spin_h.value() * asp)
            self._loading = False
        self._apply_geometry()

    def _apply_rotation(self):
        it = self._item
        if self._loading or it is None or not self.spin_rot.isEnabled():
            return
        old = it.get_state()
        new = (old[0], old[1], old[2], old[3], self.spin_rot.value())
        if new == old:
            return
        self._push(FuncCommand("旋转",
                               lambda: it.set_state(new),
                               lambda: it.set_state(old)))

    def _aspect_toggled(self, on):
        if not self._loading and isinstance(self._item, FigureItem):
            self._item.aspect_locked = on

    def _open_crop(self):
        it = self._item
        if not isinstance(it, FigureItem):
            return
        from .crop_dialog import CropDialog
        dlg = CropDialog(self, it._pixmap, it.crop)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        old, new = it.crop, dlg.get_crop()
        if new != old:
            self._push(FuncCommand("裁剪",
                                   lambda: it.set_crop(new),
                                   lambda: it.set_crop(old)))

    def _apply_text(self):
        it = self._item
        if self._loading or not isinstance(it, (LabelItem, TextBoxItem)):
            return
        before = it.to_dict()
        align = {0: "left", 1: "center", 2: "right"}[self.cmb_align.currentIndex()]
        nt = self.ed_text.text()
        new = dict(family=self.cmb_font.currentText(), size_pt=self.spin_size.value(),
                   bold=self.btn_bold.isChecked(), italic=self.btn_italic.isChecked(),
                   color=QtGui.QColor(self._color), align=align)

        def do():
            it.set_text(nt)
            it.apply_style(**new)

        def undo():
            it.set_text(before["text"])
            it.apply_style(family=before["family"], size_pt=before["size_pt"],
                           bold=before["bold"], italic=before["italic"],
                           color=QtGui.QColor(before["color"]), align=before["align"])

        self._push(FuncCommand("修改文字", do, undo))

    def _pick_text_color(self):
        c = QtWidgets.QColorDialog.getColor(self._color, self, "文字颜色")
        if c.isValid():
            self._color = c
            self._tint(self.btn_color, c)
            self._apply_text()

    def _apply_frame(self):
        it = self._item
        if self._loading or not isinstance(it, TextBoxItem):
            return
        before = it.to_dict()
        new = dict(border=self.chk_border.isChecked(), border_width=self.spin_bw.value(),
                   border_color=QtGui.QColor(self._border_color),
                   fill=self.chk_fill.isChecked(),
                   fill_color=QtGui.QColor(self._fill_color))

        def do():
            it.apply_style(**new)

        def undo():
            it.apply_style(border=before["border"], border_width=before["border_width"],
                           border_color=QtGui.QColor(before["border_color"]),
                           fill=before["fill"], fill_color=QtGui.QColor(before["fill_color"]))

        self._push(FuncCommand("修改文本框", do, undo))

    def _pick_frame_color(self, which):
        cur = self._border_color if which == "border" else self._fill_color
        c = QtWidgets.QColorDialog.getColor(cur, self, "选择颜色")
        if not c.isValid():
            return
        if which == "border":
            self._border_color = c
            self._tint(self.btn_border_color, c)
        else:
            self._fill_color = c
            self._tint(self.btn_fill_color, c)
        self._apply_frame()

    def _apply_line(self):
        it = self._item
        if self._loading or not isinstance(it, LineItem):
            return
        before = dict(color=QtGui.QColor(it.color), width_pt=it.width_pt,
                      dashed=it.dashed, arrow=it.arrow)
        new = dict(color=QtGui.QColor(self._line_color), width_pt=self.spin_lw.value(),
                   dashed=self.cmb_style.currentIndex() == 1,
                   arrow={0: "none", 1: "end", 2: "both"}[self.cmb_arrow.currentIndex()])

        self._push(FuncCommand("修改线条",
                               lambda: it.apply_style(**new),
                               lambda: it.apply_style(**before)))

    def _pick_line_color(self):
        c = QtWidgets.QColorDialog.getColor(self._line_color, self, "线条颜色")
        if c.isValid():
            self._line_color = c
            self._tint(self.btn_line_color, c)
            self._apply_line()

    def _tint(self, btn, c):
        btn.setStyleSheet(
            f"background:{c.name()}; color:{'#000' if c.lightness() > 128 else '#fff'};")
