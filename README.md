# SP 贴图转 VTF 工具

把 Substance Painter 导出的 PNG 贴图批量转换为 VTF，并按 VMT 所指路径自动覆盖进 L4D2 的 `materials` 目录。单文件 Python + tkinter GUI，零安装依赖（无需其他运行库）。

## 功能特性

- 解析 VMT，自动根据 `$basetexture` / `$bumpmap` 找到对应 PNG 并就地替换
- 可自定义 VTF 版本（7.0 ~ 7.5）、Color / Alpha 格式（26 种）
- 可选分辨率缩放（128 ~ 4096，支持每张贴图单独设置）
- 可选 Resize 的 Method（3 种）和 Filter（14 种）
- VMT 列表里勾选要替换的项，双击可单独改目标分辨率
- 所有路径与参数持久化到 `config.json`
- 全中文界面，微软雅黑字体，带状态栏和彩色日志

## 文件名约定

SP 导出文件名必须是 `{VMT 文件名}_{贴图类型}.png`：

| SP 导出后缀        | VMT 参数               |
| ------------------ | ---------------------- |
| `_Base_Color`      | `$basetexture`         |
| `_Normal_OpenGL`   | `$bumpmap`             |

> 当前版本默认处理前两类（Base_Color、Normal_OpenGL），其它映射在 `SUFFIX_TO_PARAM` 中按需扩展即可。

示例：VMT 名为 `reciever_mk17_fn_scar_h_std_LOD0f.vmt`，则对应 PNG 为
`reciever_mk17_fn_scar_h_std_LOD0f_Base_Color.png`、
`reciever_mk17_fn_scar_h_std_LOD0f_Normal_OpenGL.png`。

## 依赖

- Python 3.8+（只用标准库：`tkinter`、`json`、`subprocess`、`pathlib` 等）
- [VTFCmd.exe](https://nemstools.github.io/pages/VTFLib-Download.html)（VTFLib 自带的命令行工具）

## 运行

```bash
py sp_to_vtf.py
```

或在 VS Code 里直接按 F5。

## 使用步骤

1. **填好四个路径**
   - VTFCmd.exe 路径
   - SP 导出 PNG 所在文件夹
   - VMT 文件夹
   - L4D2 materials 根目录
2. 点击 **载入 VMT** —— 左下列表会列出所有 `.vmt`，并标出 basetexture / bumpmap 两列的可用状态
3. 按需勾选要替换的贴图；双击分辨率单元格可单独调整目标尺寸
4. 配置 **VTF 输出参数** 和 **缩放设置**
5. 点击 **开始转换**，日志区实时输出结果

VMT 里的相对路径示例：`$basetexture "escape/from/Tarkov/mk17/reciever_d"`
实际写入位置：`{materials 根目录}/escape/from/Tarkov/mk17/reciever_d.vtf`

## 参数说明

| 参数            | 作用                                              |
| --------------- | ------------------------------------------------- |
| VTF 版本        | 默认 `7.2`，可选 7.0 ~ 7.5                        |
| Color 格式      | 用于 basetexture，默认 `DXT1`                     |
| Alpha 格式      | 用于 bumpmap，默认 `DXT5`                         |
| 分辨率          | 开启后强制缩放到指定宽高，关闭则保持 PNG 原尺寸   |
| Resize          | 开启后附加 `-rmethod` / `-rfilter` 给 VTFCmd      |

## 打包成 exe

```bash
pip install pyinstaller
pyinstaller --onefile --windowed sp_to_vtf.py
```

产物在 `dist/sp_to_vtf.exe`。`config.json` 会保存在 exe 同级目录（已做 `sys.frozen` 检测）。

## 配置文件

首次保存或点击 **保存配置** 后，在程序目录生成 `config.json`，结构大致如下：

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

## 项目结构

```
sp_to_vtf.py     # 全部代码（单文件）
config.json      # 首次运行后生成
README.md       # 本文件
CLAUDE.md       # 给 Claude Code 的项目说明
```
