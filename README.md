这份原版的 `README.md` 已经写得非常详尽了，特别是“文件名约定”和“参数说明”部分非常清晰专业。

结合我们之前确定的 **GPLv3 协议**、**零第三方库依赖 (Zero-dependency)** 以及面向 GitHub 的排版规范，我为你重新梳理并优化了这份文档。

优化重点如下：

1.  **增加了徽章 (Badges)**：提升开源项目的专业感。
2.  **重构了文档结构**：将受众明确划分为“普通用户”和“开发者”，让想直接用的玩家和想看代码的程序员都能立刻找到对应部分。
3.  **补充了协议声明**：在文末加上了刚才确定的 GPLv3 声明。
4.  **视觉优化**：增加了适当的 Emoji 作为视觉锚点，提升阅读体验。

你可以直接复制以下完整内容，覆盖掉你本地的 `README.md` 文件：

-----

````markdown
# SP2VTF - 贴图转换工具

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![Zero Dependency](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](https://github.com/)

一个专为 Source 引擎（如《求生之路2》）模组开发者设计的图形化辅助工具。
本工具可将 Substance Painter (SP) 导出的 PNG 贴图批量转换为 VTF 格式，并根据 VMT 文件所指向的路径，自动覆盖至目标 `materials` 目录中。采用纯 Python 标准库结合 Tkinter 开发，**无需安装任何第三方 Python 依赖**。

## ✨ 核心特性

- **智能解析路径：** 自动解析 VMT 文件，根据 `$basetexture` / `$bumpmap` 寻找对应的 PNG 贴图并就地替换。
- **丰富的导出选项：** 可自定义 VTF 版本（7.0 ~ 7.5）及 Color / Alpha 通道格式（多达 26 种）。
- **灵活的尺寸控制：** 支持全局分辨率缩放（128 ~ 4096），也支持在列表中双击单独修改某张贴图的目标尺寸；提供 3 种 Resize Method 和 14 种 Filter 算法。
- **极简操作体验：** 全中文原生 GUI 界面，带状态栏与彩色实时日志；支持一键保存路径与参数配置到本地。

## 📸 界面预览

*(请在此处放置一张软件运行界面的截图，并将图片命名为 screenshot.png 放在项目根目录下)*
`![软件截图](screenshot.png)`

## 🏷️ 文件名约定

为了让工具能正确匹配，SP 导出的文件名必须严格遵循 `{VMT 文件名}_{贴图类型}.png` 的格式：

| SP 导出后缀 | VMT 参数映射 |
| :--- | :--- |
| `_Base_Color` | `$basetexture` |
| `_Normal_OpenGL` | `$bumpmap` |

> **📝 示例说明：**
> 假设你的 VMT 文件名为 `reciever_mk17_fn_scar_h_std_LOD0f.vmt`
> 那么对应的贴图应命名为：
> - `reciever_mk17_fn_scar_h_std_LOD0f_Base_Color.png`
> - `reciever_mk17_fn_scar_h_std_LOD0f_Normal_OpenGL.png`
> 
> *(注：当前版本默认处理上述两类贴图，如需增加其他映射，可在源码的 `SUFFIX_TO_PARAM` 字典中自行扩展)*

---

## 🚀 如何使用 (普通玩家/模组作者)

如果你只需要使用该工具进行转换，无需配置任何代码环境：

### 1. 准备工作
本工具底层依赖于 VTFLib 的核心组件，请务必先下载它：
- 下载并解压 [VTFCmd.exe](https://nemstools.github.io/pages/VTFLib-Download.html) 及其配套的 dll 文件。

### 2. 运行软件
1. 前往本仓库的 **Releases** 页面，下载最新版本的 `SP2VTF.exe`。
2. 双击运行即可。

### 3. 操作流程
1. 在主界面填好四个核心路径：**VTFCmd.exe 所在路径**、**SP 导出的 PNG 文件夹**、**VMT 文件夹**、**游戏 materials 根目录**。
2. 点击 **载入 VMT**，左下方列表将列出所有 `.vmt` 文件，并自动标记可用状态。
3. 勾选需要转换的贴图（双击“分辨率”单元格可单独调整指定贴图的大小）。
4. 在右侧配置好你需要的 **VTF 输出参数** 和 **缩放设置**。
5. 点击 **开始转换**，在日志区查看实时处理结果。

---

## 💻 本地开发与构建 (开发者)

本项目秉承 **零第三方依赖 (Zero-dependency)** 原则，克隆即跑。

### 环境准备
- Python 3.8 或更高版本。
- [VTFCmd.exe](https://nemstools.github.io/pages/VTFLib-Download.html)

### 运行源码
```bash
git clone [https://github.com/你的用户名/你的仓库名.git](https://github.com/你的用户名/你的仓库名.git)
cd 你的仓库名
python sp_to_vtf.py
````

### 打包发布

如果需要自行将其编译为独立的 `.exe` 可执行文件，请先安装 `pyinstaller`：

```bash
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "SP2VTF" sp_to_vtf.py
```

编译产物将生成在 `dist/` 目录下。

-----

## ⚙️ 进阶：配置文件与项目结构

首次运行并保存设置后，程序同级目录下会自动生成 `config.json` 文件（若使用打包好的 exe，则生成在 exe 同级目录）：

```json
{
  "vtfcmd": "C:/tools/VTFCmd.exe",
  "png_dir": "...",
  "vmt_dir": "...",
  "materials_dir": "...",
  "size_enabled": true,
  "resize_enabled": true,
  "resize_width": 1024,
  "resize_height": 1024,
  "vtf_version": "7.2",
  "color_format": "DXT1",
  "alpha_format": "DXT5",
  "resize_method": "nearest",
  "resize_filter": "triangle"
}
```

**项目结构概览：**

```text
.
├── sp_to_vtf.py     # 核心源码（单文件即可运行全部功能）
├── config.json      # 配置文件（程序运行时自动生成）
├── README.md        # 项目说明文档
└── CLAUDE.md        # AI 辅助开发上下文说明
```

## 📄 开源协议

本项目采用 [GPL-3.0 License](https://www.google.com/search?q=LICENSE) 协议开源。
允许任何个人或组织自由使用、修改和分发本项目的代码。如若衍生项目包含了本项目的代码，衍生项目同样必须以 GPLv3 协议开源。

```
```