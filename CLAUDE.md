# SP贴图转VTF工具

## 功能
将 Substance Painter 导出的 PNG 贴图转换为 VTF 格式，
并自动替换 L4D2 materials 目录下对应 VMT 所指定路径的贴图文件。

## 文件名规则
SP 导出的文件名格式为：`{VMT文件名}_{贴图类型}.png`
例如 VMT 文件名为 `reciever_mk17_fn_scar_h_std_LOD0f.vmt`，
则对应的 SP 导出文件为：
- `reciever_mk17_fn_scar_h_std_LOD0f_Base_Color.png`
- `reciever_mk17_fn_scar_h_std_LOD0f_Normal_OpenGL.png`

## SP贴图类型与VMT参数映射关系
| SP导出文件后缀 | VMT参数 |
|---|---|
| _Base_Color | $basetexture |
| _Normal_OpenGL | $bumpmap |
| _Roughness | $phongexponenttexture |
| _Metallic | $envmapmask |

## 工具要求
- 语言：Python，单文件
- 界面：tkinter GUI
- 用户可自定义以下路径（界面里有输入框+浏览按钮）：
  - VTFCmd.exe 路径
  - SP 导出 PNG 所在文件夹
  - VMT 文件夹
  - L4D2 materials 根目录
- 工具读取 VMT 文件内容，解析各参数的贴图路径
- 根据映射关系找到对应 PNG，调用 VTFCmd.exe 转换成 VTF
- 转换完成后将 VTF 复制到 VMT 中指定的路径（相对于 materials 根目录）
- 所有路径配置保存到 config.json，下次启动自动读取
- 处理完成后在界面显示成功/失败日志

## 注意
- VMT 文件里的路径是相对于 materials 目录的，例如
  `$basetexture "escape/from/Tarkov/mk17/reciever_d"`
  对应实际路径为 `{materials根目录}/escape/from/Tarkov/mk17/reciever_d.vtf`
- Normal 贴图转 VTF 时 VTFCmd 参数需要加 `-format DXT5`
- 其他贴图用 `-format DXT1`