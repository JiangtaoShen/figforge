# FigForge · 论文图排版

<img src="figforge/resources/icon.png" width="96" align="right" alt="FigForge icon">

[English](README.md) | **简体中文**

[![CI](https://github.com/JiangtaoShen/figforge/actions/workflows/ci.yml/badge.svg)](https://github.com/JiangtaoShen/figforge/actions/workflows/ci.yml)

**[⬇ Windows 版下载（v0.2.0）](https://github.com/JiangtaoShen/figforge/releases/latest)** —— 解压后双击 `FigForge.exe`，无需安装 Python。

一个面向学术论文的**轻量图排版工具**（专业平面设计软件的精简版），用于把多张子图拼成
Nature 风格的多面板大图、手动标注编号（a / b / c…），并导出**印刷级 PDF（矢量保真）**
与**高分辨率 PNG / TIFF**。

矢量子图（PDF / SVG / EPS）排版后导出 PDF **仍然是矢量**（无限分辨率）；位图子图按**原始
分辨率**嵌入；文字标签导出为**真正的 PDF 矢量文字**。PDF 与 PNG 同源生成，所见即所得。

## 运行

Windows：

```bat
py -m pip install -r requirements.txt
py run.py
```

macOS / Linux：

```bash
python3 -m pip install -r requirements.txt
python3 run.py
```

依赖：Python 3.10+（PySide6、PyMuPDF、Pillow、fontTools）。字体在 **Windows / macOS / Linux**
上均从系统字体目录解析；导出 PDF 嵌入**子集化**后的字体（只含用到的字形），含中文的文件也很小。
（导入 EPS/PS 需另装 Ghostscript：Windows 为 `gswin64c`，其他平台为 `gs`。）

## 主要功能

- **清爽现代界面**：基于 Fusion 的浅色主题（柔和中性色、圆角输入框与面板、蓝色强调色），
  在 Windows / macOS / Linux 上外观一致。
- **画布**：A4 / Letter，纵向 / 横向。
- **导入子图**：PNG、JPG、TIFF、BMP、GIF、WebP（位图）；PDF、SVG、EPS、PS（矢量）。
  多页 PDF 可选择页码。**可直接把文件从资源管理器拖入窗口**，落点即光标处。
- **排版**：拖动移动、拖角缩放（默认等比，按住 Shift 临时切换）；旋转（拖转角手柄，
  Shift 按 15° 步进，吸附 0/90/180/270，或输入精确角度）；裁剪（可视化框选，含三分线）；
  属性面板输入精确毫米数值；智能参考线吸附 + **Visio 式动态网格**（放大自动细分，
  1-2-5 mm 序列，网格吸附跟随当前步长）；对齐 / 等距分布；层叠顺序；
  复制 / 粘贴（Ctrl+C / Ctrl+V）、**按住 Ctrl 拖动即复制一份**、复制副本（Ctrl+D）。
  方向键移动选中对象（**Ctrl+方向键**微调）。
- **网格排版**：多选子图后「对象 → **网格排版**」（Ctrl+G）——行数 / 列数 / 毫米间距一次设好，
  可选把所有面板统一成同一尺寸，一步排成整齐网格。
- **尺寸绑定**：按住 Ctrl 选中多张图片，**右键 → 绑定尺寸**——之后调整其中任意一张，
  所有已绑定图片始终保持完全一样大。
- **锁定**：排好的对象可锁定（Ctrl+L）防止误拖动；图层面板中显示 🔒；
  「全部解锁」（Ctrl+Shift+L）一键释放。
- **编号 / 文字**：手动添加文字标签，常见字体含中文（Arial、Times New Roman、Calibri、
  微软雅黑、宋体…）、字号、加粗 / 斜体、颜色、对齐；**双击直接在画布上编辑**（原位显示光标，
  不再弹窗；按 Esc 或点击别处结束）。**中文会在导出时自动使用中文字体**。
  **不自动编号，完全由你掌控。**
- **标注**：**文本框**（可自动换行的文字框，支持**矩形 / 圆角矩形**——选中后拖动框上的菱形手柄
  即可直接调整圆角大小；**文字到边框的上下左右边距可分别设置**（毫米）；可选边框 / 背景填充，
  **背景透明度可调**，可旋转）与
  **线条 / 箭头**（实线或虚线，末端或两端箭头）。线条端点会**自动黏附到文本框 / 对象的节点**并保持连接——
  移动文本框时，连着的一端跟随、另一端不动；均以矢量导出。
  文本框与线条不参与网格吸附，标注可自由摆放。
- **导出**：
  - **PDF** —— 矢量保真，印刷首选。
  - **PNG** —— 150 / 300 / 600 / 1200 DPI，可选透明背景。
  - **TIFF** —— 高 DPI，LZW 压缩。
  - **裁剪至内容区域** —— 可选按内容包围盒 + 自定留白裁剪导出，去掉页面四周大白边，
    投稿尺寸即成品尺寸。
- **项目文件 `.ffp`** —— ZIP 打包，自带全部素材，换电脑 / 移动原图也能再编辑。
- **多语言**：英文与简体中文，可在「语言」菜单切换（记住选择；全新安装默认英文）。
- **自动保存与崩溃恢复**：未保存的工作每 2 分钟自动快照；程序或电脑意外挂掉后，
  下次启动会提示恢复。内部错误会写入日志并立即抢救快照，不再丢排版。
- 完整撤销 / 重做。

## 快捷键

| 操作 | 键 |
|---|---|
| 导入图片 | Ctrl+I |
| 添加文字标签 | T |
| 保存 / 另存为 | Ctrl+S / Ctrl+Shift+S |
| 撤销 / 重做 | Ctrl+Z / Ctrl+Y |
| 复制 / 剪切 / 粘贴 | Ctrl+C / Ctrl+X / Ctrl+V |
| 复制副本 / 删除 / 全选 | Ctrl+D / Del / Ctrl+A |
| 移动 / 微调 | 方向键 / Ctrl+方向键 |
| 裁剪选中图片 | C |
| 网格排版 | Ctrl+G |
| 锁定 / 全部解锁 | Ctrl+L / Ctrl+Shift+L |
| 取消选择 | Esc |
| 适应页面 / 放大 / 缩小 | Ctrl+0 / Ctrl++ / Ctrl+- |
| 缩放（Ctrl+滚轮）、平移（空格拖动 或 中键拖动） | |

## 打包成独立程序（可选）

务必用**干净的虚拟环境**打包，只带上 FigForge 需要的库（否则 PyInstaller 会把全局
Python 里无关的大库一起打进去）：

```bat
py -m venv C:\ffb
C:\ffb\Scripts\python -m pip install -r requirements.txt pyinstaller
C:\ffb\Scripts\python -m PyInstaller --noconfirm --windowed ^
    --icon figforge/resources/icon.ico --add-data "figforge/resources;figforge/resources" ^
    --exclude-module tkinter --name FigForge run.py
```

生成的程序在 `dist\FigForge\` 下（约 250 MB），双击 `FigForge.exe` 即可运行。移动到别的电脑时，
请把**整个 `FigForge` 文件夹**一起复制（`_internal` 文件夹是运行库）。在 macOS / Linux 上用
`python3` 执行同样的命令，即可得到对应平台的原生程序。

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
