"""Minimal in-app internationalization.

English is the base language (the source strings are the keys); Simplified
Chinese is provided as a translation.  The chosen language persists via
QSettings; the default (e.g. a fresh GitHub download) is English.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings

_LANG = "en"

_ZH = {
    # app / window
    "FigForge — Academic Figure Layout": "FigForge · 论文图排版",
    "Untitled": "未命名",
    # menus
    "File": "文件", "Edit": "编辑", "Object": "对象", "View": "视图",
    "Help": "帮助", "Language": "语言",
    "Align": "对齐", "Order": "层叠顺序", "Rotate": "旋转",
    # file
    "New": "新建", "Open…": "打开…", "Save": "保存", "Save As…": "另存为…",
    "Open Recent": "最近打开", "Clear Menu": "清空列表", "(empty)": "（空）",
    "File not found: {0}": "文件不存在：{0}",
    "Import Images…": "导入图片…",
    "Export PDF (vector)…": "导出 PDF（矢量）…",
    "Export PNG (high-res)…": "导出 PNG（高分辨率）…",
    "Export TIFF…": "导出 TIFF…", "Quit": "退出",
    # edit
    "Undo": "撤销", "Redo": "重做", "Delete": "删除", "Select All": "全选",
    "Duplicate": "复制副本", "Copy": "复制", "Cut": "剪切", "Paste": "粘贴",
    # object
    "Add Text Label": "添加文字标签", "Add Text Box": "添加文本框",
    "Add Line": "添加线条", "Crop Image…": "裁剪图片…",
    "Arrange in Grid…": "网格排版…", "Arrange in Grid": "网格排版",
    "Select at least two images to arrange.": "请至少选中两张图片再进行网格排版。",
    "Rows": "行数", "Columns": "列数",
    "Horizontal gap": "水平间距", "Vertical gap": "垂直间距",
    "Make all panels the same size as the first panel": "所有面板统一为第一个面板的尺寸",
    "Panels are placed row by row in their current order (top-left first).":
        "按当前位置从左上角开始，逐行排入网格。",
    "Lock": "锁定", "Unlock All": "全部解锁",
    "Rotate Left 90°": "向左旋转 90°", "Rotate Right 90°": "向右旋转 90°",
    "Reset Rotation": "重置旋转",
    "Align Left": "左对齐", "Align Center": "水平居中", "Align Right": "右对齐",
    "Align Top": "顶对齐", "Align Middle": "垂直居中", "Align Bottom": "底对齐",
    "Distribute Horizontally": "水平等距分布", "Distribute Vertically": "垂直等距分布",
    "Bring to Front": "置于顶层", "Bring Forward": "上移一层",
    "Send Backward": "下移一层", "Send to Back": "置于底层",
    # view
    "Zoom In": "放大", "Zoom Out": "缩小", "Fit Page": "适应页面",
    "Actual Size 100%": "实际大小 100%",
    # help
    "User Guide": "使用说明", "About": "关于",
    # toolbars / page bar
    "Main Toolbar": "主工具栏", "Page": "页面", " Paper ": " 纸张 ",
    "Portrait": "纵向", "Landscape": "横向", "Grid": "网格", "Smart Snap": "智能吸附",
    # docks
    "Properties": "属性", "Layers": "图层",
    # layers buttons
    "Bring to front": "置于顶层", "Bring forward": "上移一层",
    "Send backward": "下移一层", "Send to back": "置于底层",
    # status
    "Zoom {0}%": "缩放 {0}%",
    # properties groups
    "Position & Size": "位置与大小", "Image": "图片选项", "Text": "文字",
    "Text Box Border / Fill": "文本框边框 / 填充", "Line": "线条",
    "W": "宽", "H": "高", "Rotation": "旋转", "Lock aspect ratio": "锁定宽高比",
    "Crop…": "裁剪…", "Font": "字体", "Size": "字号", "Style": "样式",
    "Color": "颜色", "Show border": "显示边框", "Width": "线宽",
    "Border color": "边框颜色", "Fill background": "填充背景",
    "Fill color": "填充颜色", "Background transparency": "背景透明度",
    "Line style": "线型", "Arrow": "箭头",
    "Left": "左对齐", "Center": "居中", "Right": "右对齐",
    "Solid": "实线", "Dashed": "虚线",
    "None": "无箭头", "End": "末端箭头", "Both": "两端箭头",
    "Label": "标签", "Text Box": "文本框",
    "(no selection)": "（未选择对象）",
    "Multiple selected (use align tools)": "多选对象（用对齐工具）",
    "{0}: {1}": "{0}：{1}",
    "Drag to move; drag a corner to resize, the top dot to rotate.":
        "拖动移动；选中后拖角缩放，拖顶部圆点旋转。",
    "Source: {0}": "来源：{0}", "vector": "矢量", "raster": "位图",
    "Drag the end dots to adjust the line.": "选中后拖两端圆点可调整线条。",
    "Double-click the object to edit text.": "双击对象可多行编辑文字。",
    # crop dialog
    "Crop Image": "裁剪图片",
    "Drag the box to choose the area to keep:": "拖动方框选择保留区域：",
    "Reset": "重置",
    # export dialog
    "Export Settings": "导出设置", "Resolution": "分辨率",
    "Transparent background": "透明背景",
    "Crop to content": "裁剪至内容区域", "Content margin": "内容外留白",
    # dialogs / messages
    "Choose Page": "选择页面",
    "{0} has {1} pages. Which page to import?": "{0} 有 {1} 页，导入第几页？",
    "Import Failed": "导入失败",
    "Crop": "裁剪", "Please select a single image to crop.": "请选择单个图片进行裁剪。",
    "Info": "提示", "The page is empty — import an image first.": "页面是空的，先导入图片吧。",
    "Export PDF": "导出 PDF", "Export PNG": "导出 PNG", "Export TIFF": "导出 TIFF",
    "Exported vector PDF: {0}": "已导出矢量 PDF：{0}",
    "Exported {0} DPI PNG: {1}": "已导出 {0} DPI PNG：{1}",
    "Exported {0} DPI TIFF: {1}": "已导出 {0} DPI TIFF：{1}",
    "Export Failed": "导出失败",
    "Unsaved": "未保存",
    "The project has unsaved changes. Save them?": "当前项目有未保存的更改，是否保存？",
    "Open Project": "打开项目", "FigForge Project (*.ffp)": "FigForge 项目 (*.ffp)",
    "Open Failed": "打开失败", "Save As": "另存为", "Save Failed": "保存失败",
    "PDF (*.pdf)": "PDF (*.pdf)", "PNG (*.png)": "PNG (*.png)",
    "TIFF (*.tiff *.tif)": "TIFF (*.tiff *.tif)",
    # undo command names (shown after "Undo"/"Redo")
    "Move / Resize / Rotate": "移动 / 缩放 / 旋转",
    "Reorder": "调整层叠", "Distribute": "分布", "Modify geometry": "修改几何",
    "Edit text": "编辑文字", "Modify text style": "修改文字样式",
    "Modify text box": "修改文本框", "Modify line": "修改线条",
    "Drag-duplicate": "拖动复制", "Modify rotation": "旋转", "Move": "移动",
    "Bind Size (same size)": "绑定尺寸（大小一致）", "Unbind Size": "解除尺寸绑定",
    "Bind Size": "绑定尺寸",
    "Add object": "添加对象", "Delete objects": "删除对象",
    "Move / Resize": "移动 / 缩放",
    # import errors
    "Importing EPS/PS requires Ghostscript (gswin64c). Install "
    "Ghostscript, or convert the file to PDF/SVG first.":
        "导入 EPS/PS 需要安装 Ghostscript（命令 gswin64c）。"
        "请安装 Ghostscript，或先把文件转换为 PDF/SVG 后再导入。",
    "Unsupported file type: {0}": "不支持的文件类型：{0}",
    "Language changed": "语言已切换",
    "The language will switch after restarting. Restart now?":
        "语言将在重启后生效。现在重启吗？",
    "Import images": "导入图片",
    "All supported (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.gif *.webp "
    "*.pdf *.svg *.eps *.ps);;Raster (*.png *.jpg *.jpeg *.tif *.tiff *.bmp "
    "*.gif *.webp);;Vector (*.pdf *.svg *.eps *.ps);;All files (*.*)":
        "所有支持的图片 (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.gif *.webp "
        "*.pdf *.svg *.eps *.ps);;位图 (*.png *.jpg *.jpeg *.tif *.tiff *.bmp "
        "*.gif *.webp);;矢量 (*.pdf *.svg *.eps *.ps);;所有文件 (*.*)",
    "USER_GUIDE":
        "1. File → Import Images: PNG / JPG / TIFF / PDF / SVG / EPS, etc.\n"
        "2. Drag to move; drag a corner to resize (keeps aspect, hold Shift to toggle);\n"
        "   drag the top dot to rotate.\n"
        "3. Object → Add Text Label / Text Box / Line for annotations; double-click to edit.\n"
        "4. Line endpoints snap to text-box / object nodes and stay connected.\n"
        "5. Select several panels → Object → Arrange in Grid lays them out in one step;\n"
        "   align / distribute / smart snapping fine-tune; lock finished items.\n"
        "6. File → Export: PDF keeps vectors; PNG / TIFF up to 1200 DPI;\n"
        "   tick \"Crop to content\" to trim the white page margins.\n"
        "7. Save as a .ffp project (bundles all assets; re-editable any time).",
    "ABOUT_BODY":
        "A lightweight figure-layout tool for academic papers.<br>"
        "Vector sub-figures stay vector in the exported PDF; rasters embed at "
        "full resolution.<br>Built with PySide6 + PyMuPDF + Pillow.",
}

_USER_GUIDE_ZH = (
    "1. 文件 → 导入图片：支持 PNG/JPG/TIFF/PDF/SVG/EPS 等。\n"
    "2. 拖动移动；选中后拖角缩放（默认等比，按住 Shift 临时切换）；拖顶部圆点旋转。\n"
    "3. 对象 → 添加文字标签 / 文本框 / 线条 做标注；双击可编辑。\n"
    "4. 线条端点会自动黏附到文本框/对象的节点并保持连接。\n"
    "5. 多选子图后用「对象 → 网格排版」一步排成网格；再用对齐/分布与智能吸附微调；\n"
    "   排好的对象可锁定防止误动。\n"
    "6. 文件 → 导出：PDF 保留矢量；PNG/TIFF 最高 1200 DPI；勾选「裁剪至内容区域」\n"
    "   可去掉页面白边。\n"
    "7. 保存为 .ffp 项目（自带所有素材，可随时再编辑）。"
)
_ABOUT_ZH = (
    "面向学术论文的轻量图排版工具。<br>"
    "矢量子图导出 PDF 仍为矢量，位图按原始分辨率嵌入。<br>"
    "基于 PySide6 + PyMuPDF + Pillow。"
)
_ZH["USER_GUIDE"] = _USER_GUIDE_ZH
_ZH["ABOUT_BODY"] = _ABOUT_ZH


def set_language(lang: str) -> None:
    global _LANG
    _LANG = "zh" if str(lang).lower().startswith("zh") else "en"


def language() -> str:
    return _LANG


def tr(s: str) -> str:
    if _LANG == "zh":
        return _ZH.get(s, s)
    return s


def available():
    return [("en", "English"), ("zh", "简体中文")]


def _settings() -> QSettings:
    return QSettings("FigForge", "FigForge")


def load_saved() -> str:
    return "zh" if str(_settings().value("language", "en")).startswith("zh") else "en"


def save_language(lang: str) -> None:
    _settings().setValue("language", "zh" if str(lang).startswith("zh") else "en")
