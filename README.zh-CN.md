# FigForge · 论文图排版

<img src="figforge/resources/icon.png" width="96" align="right" alt="FigForge icon">

[English](README.md) | **简体中文**

一个面向学术论文的**轻量图排版工具**（专业平面设计软件的精简版），用于把多张子图拼成
Nature 风格的多面板大图、手动标注编号（a / b / c…），并导出**印刷级 PDF（矢量保真）**
与**高分辨率 PNG / TIFF**。

矢量子图（PDF / SVG / EPS）排版后导出 PDF **仍然是矢量**（无限分辨率）；位图子图按**原始
分辨率**嵌入；文字标签导出为**真正的 PDF 矢量文字**。PDF 与 PNG 同源生成，所见即所得。

## 运行

```bat
py -m pip install -r requirements.txt
py run.py
```

依赖：Python 3.10+、PySide6、PyMuPDF、Pillow。（导入 EPS/PS 需另装 Ghostscript。）

## 主要功能

- **画布**：A4 / Letter，纵向 / 横向。
- **导入子图**：PNG、JPG、TIFF、BMP、GIF、WebP（位图）；PDF、SVG、EPS、PS（矢量）。
  多页 PDF 可选择页码。**可直接把文件从资源管理器拖入窗口**，落点即光标处。
- **排版**：拖动移动、拖角缩放（默认等比，按住 Shift 临时切换）；旋转（拖转角手柄，
  Shift 按 15° 步进，吸附 0/90/180/270，或输入精确角度）；裁剪（可视化框选，含三分线）；
  属性面板输入精确毫米数值；智能参考线吸附 + 可选网格；对齐 / 等距分布；层叠顺序；复制副本。
- **编号 / 文字**：手动添加文字标签，常见字体（Arial、Times New Roman、Calibri…）、
  字号、加粗 / 斜体、颜色、对齐；双击多行编辑。**不自动编号，完全由你掌控。**
- **标注**：**文本框**（可自动换行的文字框，可选边框 / 背景填充，**背景透明度可调**，可旋转）与
  **线条 / 箭头**（实线或虚线，末端或两端箭头）。线条端点会**自动黏附到文本框 / 对象的节点**并保持连接——
  移动文本框时，连着的一端跟随、另一端不动；均以矢量导出。
- **导出**：
  - **PDF** —— 矢量保真，印刷首选。
  - **PNG** —— 150 / 300 / 600 / 1200 DPI，可选透明背景。
  - **TIFF** —— 高 DPI，LZW 压缩。
- **项目文件 `.ffp`** —— ZIP 打包，自带全部素材，换电脑 / 移动原图也能再编辑。
- 完整撤销 / 重做。

## 快捷键

| 操作 | 键 |
|---|---|
| 导入图片 | Ctrl+I |
| 添加文字标签 | T |
| 保存 / 另存为 | Ctrl+S / Ctrl+Shift+S |
| 撤销 / 重做 | Ctrl+Z / Ctrl+Y |
| 复制副本 / 删除 / 全选 | Ctrl+D / Del / Ctrl+A |
| 裁剪选中图片 | C |
| 适应页面 / 放大 / 缩小 | Ctrl+0 / Ctrl++ / Ctrl+- |
| 缩放（Ctrl+滚轮）、平移（空格拖动 或 中键拖动） | |

## 打包成 .exe（可选）

```bat
py -m pip install pyinstaller
py -m PyInstaller --noconfirm --windowed --name FigForge run.py
```

生成的程序在 `dist\FigForge\` 下，双击 `FigForge.exe` 即可运行。移动到别的电脑时，
请把**整个 `FigForge` 文件夹**一起复制（`_internal` 文件夹是运行库）。

## 代码结构

```
figforge/
  constants.py        单位 / 页面 / 默认值
  fonts.py            字体解析（导出时嵌入真实 TTF）
  qtutils.py          QImage 转换助手
  fileio/
    importers.py      导入各种格式 → 预览 + 矢量数据
    exporters.py      导出 PDF（矢量）/ PNG / TIFF（同源）
    project.py        .ffp 项目存取（ZIP 打包素材）
  canvas/
    items.py          图片 / 标签 / 文本框 / 线条项（移动、缩放、旋转、裁剪、导出）
    scene.py          页面、网格、智能吸附、参考线
    view.py           缩放 / 平移 / 拖拽导入
  ui/
    properties_panel.py   位置大小 + 标签样式 + 旋转 / 裁剪
    layers_panel.py       对象列表 + 层叠顺序
    crop_dialog.py        可视化裁剪对话框
  main_window.py      菜单 / 工具栏 / 文件与导出 / 对齐 / 撤销
  app.py              启动入口
run.py
```

## 矢量保真原理

编辑用 Qt 的 `QGraphicsScene`（1 场景单位 = 1 PDF 点）；导出走独立的 PyMuPDF 管线作为唯一
真源：矢量子图用 `show_pdf_page` 嵌入（保持矢量）、位图按原分辨率嵌入、文字写成 PDF 矢量
文字；旋转 / 裁剪经过一个中间页处理后同样保持矢量。PNG / TIFF 再由这份 PDF 高 DPI 栅格化得到，
因此各格式像素级一致。
