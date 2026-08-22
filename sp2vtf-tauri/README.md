# SP2VTF 贴图转换工具

将 Substance Painter 导出的 PNG/TGA 贴图转换为 VTF 格式，并自动替换 L4D2 materials 目录下对应 VMT 所指定路径的贴图文件。

技术栈：Tauri 2 + Vue 3 + Vuetify 4 + PyO3（内嵌 Python 3.10 + Pillow + NumPy）。

## 分发产物

打包在 `src-tauri/target/release/bundle/` 下，共两种形式：

| 形式 | 路径 | 说明 |
|---|---|---|
| 安装程序 (NSIS) | `bundle/nsis/SP2VTF_<版本>_x64-setup.exe` | 需安装，写入 Program Files，带开始菜单/卸载项 |
| 绿色免安装 | `bundle/portable/SP2VTF_<版本>_x64-portable.zip` | 解压即用，双击 `sp2vtf-tauri.exe` 即运行，无需安装 |

> 注意：tauri 官方 bundle targets 不支持 `zip`，便携包是从 release 产物（exe + 依赖 DLL + `resources/python-embed`）手动压缩生成，需在解压后保持 `resources/python-embed` 相对 exe 的同级结构。

## 运行依赖（重要）

- **用户无需预装 Python。** 程序内嵌了 Python 3.10 + Pillow + NumPy（位于 `resources/python-embed`），所有功能（含预处理）均依赖它。
- 启动时 `python_bridge.rs` 会调用 `init_python()`，自动把内嵌的 `site-packages` 加入 `sys.path` 并加载 numpy/PIL——**预处理那套通道分离 / 灰度 / Alpha / 色阶处理都靠它**。若 `resources/python-embed` 缺失，程序会启动失败并提示「未找到 python-embed 目录」。
- VTFCmd.exe 需用户在界面中自行选择（不随程序分发）。

### 保险起见：用户自行安装 Python 有用吗？

**没有用，不建议作为常规运行前提。** 程序运行用的始终是它内嵌的 Python（`resources/python-embed`），不会去读用户系统里装的 Python 或不走 pip 安装的包。因此：

- ✅ 真正保险的是**确保 `resources/python-embed` 完整、随 exe 同级分发**（安装包 / 便携 zip 已包含）。
- ❌ 不要写「请先安装 Python 3.10 并 pip install numpy pillow」——用户装了程序也不会用，纯属误导。

**如果程序启动报「未找到 python-embed 目录」或预处理报错**，应按排障步骤处理：确认 exe 和 `resources/python-embed` 在同一级目录、`python310._pth` 存在、内嵌 `site-packages` 里有 `numpy` / `PIL`。需要定位问题时可安装一个独立的 Python 3.10 + `pip install numpy pillow` 仅供**对照调试**，但不要指望成品程序直接调用它。

## 打包方法

构建前设置环境变量（PyO3 交叉链接用）：

```powershell
$env:PYO3_PYTHON = "C:\Users\1\AppData\Local\Programs\Python\Python310\python.exe"
npm run tauri -- build
```

- 安装程序：`src-tauri/target/release/bundle/nsis/`（tauri 自动生成）
- 便携包：在 `src-tauri/target/release/bundle/portable/` 手动打包，取自 `target/release/` 下的 `sp2vtf-tauri.exe` + `python3.dll` + `python310.dll` + `vcruntime140.dll` + `vcruntime140_1.dll` + `resources/` 目录。

## 开发

```powershell
npm install
$env:PYO3_PYTHON = "C:\Users\1\AppData\Local\Programs\Python\Python310\python.exe"
npm run tauri dev
```

## 文件名规则

SP 导出文件名格式：`{VMT文件名}_{贴图类型}.png`，例如 VMT 文件 `reciever_mk17_fn_scar_h_std_LOD0f.vmt` 对应：

- `reciever_mk17_fn_scar_h_std_LOD0f_Base_Color.png`
- `reciever_mk17_fn_scar_h_std_LOD0f_Normal_OpenGL.png`

| SP 导出文件后缀 | VMT 参数 |
|---|---|
| `_Base_Color` | `$basetexture` |
| `_Normal_OpenGL` | `$bumpmap` |
| `_Roughness` | `$phongexponenttexture` |
| `_Metallic` | `$envmapmask` |

## 发布工作流

- 推送 `v*` 标签触发 GitHub Actions 自动构建 NSIS 安装器 + 便携 zip，并上传到对应 GitHub Release。
- 示例：`git tag v1.0.8 && git push origin v1.0.8`

## 常见警告（不影响产物）

- Vue/Vuetify CSS 打包时有 `@layer` 语法警告与 chunk >500KB 提示，均为 Vite 层面提示，不影响使用。
- `src-tauri/src/lib.rs` 存在 `use std::path::PathBuf;` 未使用警告，可删。
