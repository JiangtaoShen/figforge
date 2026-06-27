"""Properties dock — precise geometry plus label styling for the selection."""
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from .. import constants, fonts
from ..canvas.items import FigureItem, LabelItem
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
        self.setWidgetResizable(True)
        self._build()
        self.set_selection([])

    # ---- ui --------------------------------------------------------------
    def _spin(self, mx=4000.0, dec=2, suffix=" mm"):
        s = QtWidgets.QDoubleSpinBox()
        s.setRange(-mx, mx)
        s.setDecimals(dec)
        s.setSuffix(suffix)
        s.setSingleStep(1.0)
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

        # geometry -------------------------------------------------------
        self.box_geom = QtWidgets.QGroupBox("位置与大小")
        g = QtWidgets.QFormLayout(self.box_geom)
        self.spin_x = self._spin()
        self.spin_y = self._spin()
        self.spin_w = self._spin()
        self.spin_h = self._spin()
        g.addRow("X", self.spin_x)
        g.addRow("Y", self.spin_y)
        g.addRow("宽", self.spin_w)
        g.addRow("高", self.spin_h)
        lay.addWidget(self.box_geom)
        for s in (self.spin_x, self.spin_y):
            s.editingFinished.connect(self._apply_geometry)
        self.spin_w.editingFinished.connect(lambda: self._wh_edited("w"))
        self.spin_h.editingFinished.connect(lambda: self._wh_edited("h"))

        # image-only options ---------------------------------------------
        self.box_image = QtWidgets.QGroupBox("图片选项")
        ig = QtWidgets.QFormLayout(self.box_image)
        self.chk_aspect = QtWidgets.QCheckBox("锁定宽高比")
        self.spin_rot = QtWidgets.QDoubleSpinBox()
        self.spin_rot.setRange(-360.0, 360.0)
        self.spin_rot.setDecimals(1)
        self.spin_rot.setSuffix(" °")
        self.spin_rot.setWrapping(True)
        self.spin_rot.setKeyboardTracking(False)
        self.btn_crop = QtWidgets.QPushButton("裁剪…")
        ig.addRow("", self.chk_aspect)
        ig.addRow("旋转", self.spin_rot)
        ig.addRow("裁剪", self.btn_crop)
        lay.addWidget(self.box_image)
        self.chk_aspect.toggled.connect(self._aspect_toggled)
        self.spin_rot.editingFinished.connect(self._apply_rotation)
        self.btn_crop.clicked.connect(self._open_crop)

        # label ----------------------------------------------------------
        self.box_label = QtWidgets.QGroupBox("文字标签")
        f = QtWidgets.QFormLayout(self.box_label)
        self.ed_text = QtWidgets.QLineEdit()
        self.cmb_font = QtWidgets.QComboBox()
        self.cmb_font.addItems(fonts.available_families())
        self.spin_size = QtWidgets.QDoubleSpinBox()
        self.spin_size.setRange(1.0, 400.0)
        self.spin_size.setDecimals(1)
        self.spin_size.setSuffix(" pt")
        self.spin_size.setKeyboardTracking(False)
        self.btn_bold = QtWidgets.QToolButton()
        self.btn_bold.setText("B")
        self.btn_bold.setCheckable(True)
        self.btn_bold.setStyleSheet("font-weight:bold;")
        self.btn_italic = QtWidgets.QToolButton()
        self.btn_italic.setText("I")
        self.btn_italic.setCheckable(True)
        self.btn_italic.setStyleSheet("font-style:italic;")
        style_row = QtWidgets.QHBoxLayout()
        style_row.addWidget(self.btn_bold)
        style_row.addWidget(self.btn_italic)
        style_row.addStretch(1)
        style_w = QtWidgets.QWidget()
        style_w.setLayout(style_row)
        self.btn_color = QtWidgets.QPushButton("颜色")
        self.cmb_align = QtWidgets.QComboBox()
        self.cmb_align.addItems(["左对齐", "居中"])
        f.addRow("文字", self.ed_text)
        f.addRow("字体", self.cmb_font)
        f.addRow("字号", self.spin_size)
        f.addRow("样式", style_w)
        f.addRow("颜色", self.btn_color)
        f.addRow("对齐", self.cmb_align)
        lay.addWidget(self.box_label)
        self.ed_text.editingFinished.connect(self._apply_label)
        self.cmb_font.currentIndexChanged.connect(self._apply_label)
        self.spin_size.editingFinished.connect(self._apply_label)
        self.btn_bold.toggled.connect(self._apply_label)
        self.btn_italic.toggled.connect(self._apply_label)
        self.cmb_align.currentIndexChanged.connect(self._apply_label)
        self.btn_color.clicked.connect(self._pick_color)

        self.info = QtWidgets.QLabel("")
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color:#666; font-size:11px;")
        lay.addWidget(self.info)
        lay.addStretch(1)
        self._color = QtGui.QColor("black")

    # ---- selection -------------------------------------------------------
    def set_selection(self, items):
        if self._geom_conn is not None:
            try:
                self._geom_conn.geometryChanged.disconnect(self._load_geometry)
            except (RuntimeError, TypeError):
                pass
            self._geom_conn = None

        if len(items) != 1:
            self._item = None
            self.box_geom.setEnabled(False)
            self.box_image.setVisible(False)
            self.box_label.setVisible(False)
            self.lbl_kind.setText("多选对象（用对齐工具）" if items else "（未选择对象）")
            self.info.setText("提示：拖动移动，选中后拖角缩放（按住 Shift 临时切换等比）。")
            return

        it = items[0]
        self._item = it
        self.box_geom.setEnabled(True)
        is_fig = isinstance(it, FigureItem)
        self.spin_w.setEnabled(is_fig)
        self.spin_h.setEnabled(is_fig)
        self.box_image.setVisible(is_fig)
        self.box_label.setVisible(isinstance(it, LabelItem))
        self.lbl_kind.setText(("图片：" if is_fig else "标签：") + it.name())
        self._load_geometry()
        if isinstance(it, LabelItem):
            self._load_label()
        if is_fig:
            self.info.setText(
                f"来源：{'矢量' if it._source_kind == 'vector' else '位图'}　"
                f"原始尺寸 {it._src_w * _MM:.1f}×{it._src_h * _MM:.1f} mm")
        else:
            self.info.setText("双击画布上的标签可多行编辑。")
        self._geom_conn = it
        it.geometryChanged.connect(self._load_geometry)

    def _load_geometry(self):
        it = self._item
        if it is None:
            return
        self._loading = True
        x, y, w, h = it.get_geometry()
        self.spin_x.setValue(x * _MM)
        self.spin_y.setValue(y * _MM)
        self.spin_w.setValue(w * _MM)
        self.spin_h.setValue(h * _MM)
        if isinstance(it, FigureItem):
            self.chk_aspect.setChecked(it.aspect_locked)
            self.spin_rot.setValue(it.rotation())
        self._loading = False

    def _load_label(self):
        it = self._item
        self._loading = True
        self.ed_text.setText(it.text)
        i = self.cmb_font.findText(it.family)
        if i >= 0:
            self.cmb_font.setCurrentIndex(i)
        self.spin_size.setValue(it.size_pt)
        self.btn_bold.setChecked(it.bold)
        self.btn_italic.setChecked(it.italic)
        self.cmb_align.setCurrentIndex(0 if it.align == "left" else 1)
        self._color = QtGui.QColor(it.color)
        self._update_color_btn()
        self._loading = False

    # ---- apply -----------------------------------------------------------
    def _push(self, cmd):
        if self.main.undo_stack is not None:
            self.main.undo_stack.push(cmd)

    def _apply_geometry(self):
        it = self._item
        if self._loading or it is None:
            return
        old = it.get_geometry()
        x = self.spin_x.value() * _PT
        y = self.spin_y.value() * _PT
        w = self.spin_w.value() * _PT if isinstance(it, FigureItem) else old[2]
        h = self.spin_h.value() * _PT if isinstance(it, FigureItem) else old[3]
        new = (x, y, w, h)
        if new == old:
            return
        self._push(FuncCommand("修改几何",
                               lambda: it.set_geometry(*new),
                               lambda: it.set_geometry(*old)))

    def _wh_edited(self, which):
        it = self._item
        if self._loading or not isinstance(it, FigureItem):
            return
        if it.aspect_locked:
            asp = it.source_aspect()
            self._loading = True
            if which == "w":
                self.spin_h.setValue(self.spin_w.value() / asp)
            else:
                self.spin_w.setValue(self.spin_h.value() * asp)
            self._loading = False
        self._apply_geometry()

    def _aspect_toggled(self, on):
        if self._loading or not isinstance(self._item, FigureItem):
            return
        self._item.aspect_locked = on

    def _apply_rotation(self):
        it = self._item
        if self._loading or not isinstance(it, FigureItem):
            return
        old = it.get_state()
        new = (old[0], old[1], old[2], old[3], self.spin_rot.value())
        if new == old:
            return
        self._push(FuncCommand("旋转",
                               lambda: it.set_state(new),
                               lambda: it.set_state(old)))

    def _open_crop(self):
        it = self._item
        if not isinstance(it, FigureItem):
            return
        from .crop_dialog import CropDialog
        dlg = CropDialog(self, it._pixmap, it.crop)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        old, new = it.crop, dlg.get_crop()
        if new == old:
            return
        self._push(FuncCommand("裁剪",
                               lambda: it.set_crop(new),
                               lambda: it.set_crop(old)))

    def _apply_label(self):
        it = self._item
        if self._loading or not isinstance(it, LabelItem):
            return
        before = it.to_dict()
        new = dict(text=self.ed_text.text(),
                   family=self.cmb_font.currentText(),
                   size_pt=self.spin_size.value(),
                   bold=self.btn_bold.isChecked(),
                   italic=self.btn_italic.isChecked(),
                   color=QtGui.QColor(self._color),
                   align="left" if self.cmb_align.currentIndex() == 0 else "center")

        def do():
            it.set_text(new["text"])
            it.apply_style(family=new["family"], size_pt=new["size_pt"],
                           bold=new["bold"], italic=new["italic"],
                           color=new["color"], align=new["align"])

        def undo():
            it.set_text(before["text"])
            it.apply_style(family=before["family"], size_pt=before["size_pt"],
                           bold=before["bold"], italic=before["italic"],
                           color=QtGui.QColor(before["color"]), align=before["align"])

        self._push(FuncCommand("修改标签", do, undo))

    def _pick_color(self):
        c = QtWidgets.QColorDialog.getColor(self._color, self, "选择文字颜色")
        if c.isValid():
            self._color = c
            self._update_color_btn()
            self._apply_label()

    def _update_color_btn(self):
        self.btn_color.setStyleSheet(
            f"background:{self._color.name()}; color:"
            f"{'#000' if self._color.lightness() > 128 else '#fff'};")
        self.btn_color.setText(self._color.name())
