"""
SP2VTF VPK 工具 — 完整管线 CLI 测试

测试步骤:
  1. 复制 VPK 到无中文路径
  2. 拆解 VPK → temp_d/e/n/vmts
  3. 法线 VTF → PNG
  4. 模拟回装（SP PNG → VTF → 材料重写 → 封包）
"""

import json, os, re, shutil, struct, subprocess, sys, traceback
from datetime import datetime
from pathlib import Path

PY = r"C:\Users\CardinalChitanda\anaconda3\envs\left4dead2\python.exe"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
    sys.stdout.flush()

# ============================================================
# VPK v1 解析器 (嵌入式)
# ============================================================

class VPKFile:
    def __init__(self, path: Path):
        self.path = path
        self.data = open(path, "rb").read()
        sig, ver, ts = struct.unpack_from("<III", self.data, 0)
        if sig != 0x55AA1234:
            raise ValueError(f"无效 VPK (sig=0x{sig:08X})")
        self.tree_size = ts
        self.entries = {}
        self._parse_tree()

    def _parse_tree(self):
        pos, end = 12, 12 + self.tree_size
        total_preload = 0
        while pos < end:
            ext = self._rs(self.data, pos); pos += len(ext) + 1
            if not ext: break
            while pos < end:
                dirn = self._rs(self.data, pos); pos += len(dirn) + 1
                if not dirn: break
                while pos < end:
                    fn = self._rs(self.data, pos); pos += len(fn) + 1
                    if not fn: break
                    crc, pre, ar, off, sz = struct.unpack_from("<IHHII", self.data, pos)
                    pos += 18  # 16 bytes struct + 2 bytes 0xFFFF terminator
                    total_preload += pre
                    dirn_clean = dirn.strip()
                    full = f"{dirn_clean}/{fn}.{ext}" if dirn_clean else f"{fn}.{ext}"
                    self.entries[full] = {"length": sz, "offset": off, "preload": pre, "archive": ar}
        self.file_data_start = 12 + self.tree_size + total_preload

    @staticmethod
    def _rs(d, p):
        e = p
        while d[e:e+1] != b"\x00": e += 1
        return d[p:e].decode("ascii", errors="replace")

    def extract(self, path: str, dest: Path):
        e = self.entries.get(path)
        if not e: raise KeyError(path)
        off = self.file_data_start + e["offset"]
        chunk = self.data[off:off + e["length"]]
        d = dest / path; d.parent.mkdir(parents=True, exist_ok=True); d.write_bytes(chunk)
        return d

    def list_vmts(self):
        return sorted(p for p in self.entries if p.endswith(".vmt") and p.startswith("materials/"))


# ============================================================
# VMT 工具
# ============================================================

VMT_PARAM_RE = re.compile(r'"?(\$[A-Za-z_]\w*)"?\s+(?:"([^"]+)"|([A-Za-z0-9_./\\\-]+))')

def parse_vmt(path: Path) -> dict:
    text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8", errors="ignore"))
    r = {}
    for m in VMT_PARAM_RE.finditer(text):
        k = m.group(1).lower()
        if k not in r: r[k] = (m.group(2) or m.group(3)).strip().replace("\\", "/")
    return r

def build_vmt(params: dict) -> str:
    lines = ['"VertexlitGeneric"', "{"] + [f'\t"{k}" "{v}"' for k, v in params.items()] + ["}"]
    return "\n".join(lines)


# ============================================================
# VTFCmd 工具
# ============================================================

def vtf_to_png(vtf: Path, cmd: Path, out: Path):
    td = out / "tga_tmp"; td.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(cmd), "-file", str(vtf), "-output", str(td),
                        "-format", "RGBA8888", "-silent"], capture_output=True, timeout=120)
    from PIL import Image
    tgas = list(td.glob(f"{vtf.stem}*.tga"))
    if not tgas: return None
    png = out / f"{vtf.stem}.png"
    Image.open(tgas[0]).convert("RGB").save(png)
    shutil.rmtree(td, ignore_errors=True)
    return png

def png_to_vtf(png: Path, cmd: Path, fmt="DXT5", ver="7.2"):
    r = subprocess.run([str(cmd), "-file", str(png), "-output", str(png.parent),
                        "-version", ver, "-format", fmt, "-silent"],
                       capture_output=True, timeout=300)
    vtf = png.with_suffix(".vtf")
    return vtf if vtf.exists() else None


# ============================================================
# 步骤 1: 准备环境
# ============================================================

log("=" * 60)
log("SP2VTF VPK 管线完整测试")
log("=" * 60)

BASE = Path(r"C:\sp2vtf_test")
if BASE.exists(): shutil.rmtree(BASE)
BASE.mkdir(parents=True)

# 路径
VPK_SRC = Path(r"C:\sp2vtf_test_src\garand.vpk")
VPK_CP = BASE / "garand.vpk"
VTFCMD = Path(r"E:\vtfcmd\VTFCmd.exe")
VPK_EXE = Path(r"D:\Steam\steamapps\common\Left 4 Dead 2\bin\vpk.exe")

# 验证
assert VPK_SRC.is_file(), f"VPK 不存在: {VPK_SRC}"
assert VTFCMD.is_file(), f"VTFCmd 不存在: {VTFCMD}"
assert VPK_EXE.is_file(), f"vpk.exe 不存在: {VPK_EXE}"

# 复制 VPK
shutil.copy2(VPK_SRC, VPK_CP)
log(f"[OK] VPK 已复制: {VPK_CP} ({VPK_CP.stat().st_size} bytes)")

# ============================================================
# 步骤 2: 拆解 VPK
# ============================================================
log("\n--- 步骤 2: 拆解 VPK ---")

vpk = VPKFile(VPK_CP)
log(f"[OK] VPK 解析成功: {len(vpk.entries)} 个文件, tree_size={vpk.tree_size}")

palette = {k: BASE / k for k in ("temp_d", "temp_e", "temp_n", "temp_n_png", "temp_vmts")}
for p in palette.values(): p.mkdir(exist_ok=True)

# 提取 VMT
vmts = vpk.list_vmts()
log(f"[OK] VMT 数量: {len(vmts)}")

vmt_map = {}
for vmt_path in vmts:
    dest = vpk.extract(vmt_path, palette["temp_vmts"])
    pure = palette["temp_vmts"] / Path(vmt_path).name
    if dest != pure: shutil.copy2(dest, pure)
    params = parse_vmt(pure)
    vn = Path(vmt_path).stem
    debug_text = pure.read_text(encoding="utf-8", errors="replace")[:300]
    log(f"  [DEBUG] {pure.name}: first 300 chars -> {repr(debug_text)}")
    log(f"  [DEBUG] parsed params: {params}")
    vmt_map[vn] = {
        "$basetexture": params.get("$basetexture", ""),
        "$bumpmap": params.get("$bumpmap", ""),
        "$phongexponenttexture": params.get("$phongexponenttexture", ""),
    }
    log(f"  VMT: {Path(vmt_path).name} -> $basetexture={vmt_map[vn]['$basetexture']}")

# 提取纹理
mat_files = [p for p in vpk.entries if p.startswith("materials/") and not p.endswith(".vmt")]
classified = {k: 0 for k in ("d", "e", "n")}
unmatched = []

for mat_path in mat_files:
    e = vpk.entries.get(mat_path)
    if not e or e["length"] == 0: continue
    stem = Path(mat_path).stem.lower()
    matched = False
    for vn, info in vmt_map.items():
        base_s = Path(info["$basetexture"]).stem.lower() if info["$basetexture"] else ""
        bump_s = Path(info["$bumpmap"]).stem.lower() if info["$bumpmap"] else ""
        exp_s = Path(info["$phongexponenttexture"]).stem.lower() if info["$phongexponenttexture"] else ""
        if stem == base_s and base_s:
            dest = vpk.extract(mat_path, palette["temp_d"])
            new = palette["temp_d"] / f"{vn}_d.vtf"
            if dest != new: shutil.copy2(dest, new)
            classified["d"] += 1; matched = True; break
        elif stem == bump_s and bump_s:
            dest = vpk.extract(mat_path, palette["temp_n"])
            new = palette["temp_n"] / f"{vn}_n.vtf"
            if dest != new: shutil.copy2(dest, new)
            classified["n"] += 1; matched = True; break
        elif stem == exp_s and exp_s:
            dest = vpk.extract(mat_path, palette["temp_e"])
            new = palette["temp_e"] / f"{vn}_e.vtf"
            if dest != new: shutil.copy2(dest, new)
            classified["e"] += 1; matched = True; break
    if not matched:
        unmatched.append(mat_path)

log(f"[OK] 分类完成: D={classified['d']}  E={classified['e']}  N={classified['n']}")
if unmatched:
    log(f"[?] 未分类: {len(unmatched)} 个 [{', '.join(Path(p).name for p in unmatched[:5])}]")

# 保存映射表
mapping = palette["temp_vmts"].parent / "mapping.json"
Path(mapping).write_text(json.dumps(vmt_map, indent=2, ensure_ascii=False), encoding="utf-8")
log(f"[OK] 映射表已保存: {mapping}")

# 验证: 列出 temp_d 文件
d_files = sorted(palette["temp_d"].iterdir())
log(f"  temp_d: {len(d_files)} 个 VTF")
for f in d_files: log(f"    {f.name}")

n_files = sorted(palette["temp_n"].iterdir())
log(f"  temp_n: {len(n_files)} 个 VTF")
for f in n_files: log(f"    {f.name}")

# ============================================================
# 步骤 3: 法线 VTF → PNG
# ============================================================
log("\n--- 步骤 3: 法线 VTF → PNG ---")

vtfs_n = list(palette["temp_n"].glob("*.vtf"))
log(f"  待转换: {len(vtfs_n)} 个")

for vtf in vtfs_n:
    png = vtf_to_png(vtf, VTFCMD, palette["temp_n_png"])
    if png:
        log(f"  [OK] {vtf.name} -> {png.name} ({png.stat().st_size} bytes)")
    else:
        log(f"  [FAIL] {vtf.name} 转换失败")

# ============================================================
# 步骤 4: 模拟回装
# ============================================================
log("\n--- 步骤 4: 模拟回装 ---")

# 4a. 用拆出来的 D 贴图模拟 SP 导出 (Base_Color.png)
mock_sp = BASE / "mock_sp"
mock_sp.mkdir()
mock_sp_n = BASE / "mock_sp_n"
mock_sp_n.mkdir()

for vn, info in vmt_map.items():
    # D: 模拟 Base_Color (从 temp_d 的 VTF 转为 PNG)
    d_vtf = palette["temp_d"] / f"{vn}_d.vtf"
    if d_vtf.exists():
        # 先转成 PNG (作为 SP 导出模拟)
        png = vtf_to_png(d_vtf, VTFCMD, mock_sp)
        if png:
            # 重命名为 SP 导出格式
            sp_name = mock_sp / f"{vn}_Base_Color.png"
            shutil.move(str(png), str(sp_name))
            log(f"  [D mock] {vn}_Base_Color.png 已准备")

    # N: 模拟法线
    n_png = palette["temp_n_png"] / f"{vn}_n.png"
    if n_png.exists():
        sp_name = mock_sp_n / f"{vn}_Normal_OpenGL.png"
        shutil.copy2(n_png, sp_name)
        log(f"  [N mock] {vn}_Normal_OpenGL.png 已准备")

# 统计模拟文件
d_mocks = list(mock_sp.glob("*_Base_Color.png"))
n_mocks = list(mock_sp_n.glob("*_Normal_OpenGL.png"))
log(f"[OK] 模拟 SP 输出: D={len(d_mocks)} 个, N={len(n_mocks)} 个")

# 4b. 用 VTFCmd 把模拟 PNG 转回 VTF
log("\n--- 步骤 4b: PNG -> VTF ---")
rebuild_mat = BASE / "rebuild" / "materials"
rebuild_mat.mkdir(parents=True)

converted_d = 0
for mock_png in d_mocks:
    vn = mock_png.name.replace("_Base_Color.png", "")
    info = vmt_map.get(vn)
    if not info: continue
    rel = info["$basetexture"].replace("\\", "/")
    target = rebuild_mat / f"{rel}.vtf"
    target.parent.mkdir(parents=True, exist_ok=True)

    result = png_to_vtf(mock_png, VTFCMD, "DXT1", "7.2")
    if result and result.exists():
        shutil.copy2(result, target)
        if result.parent != mock_png.parent: result.unlink(missing_ok=True)
        converted_d += 1

log(f"[OK] D 贴图转换: {converted_d}/{len(d_mocks)}")

converted_n = 0
for mock_png in n_mocks:
    vn = mock_png.name.replace("_Normal_OpenGL.png", "")
    info = vmt_map.get(vn)
    if not info: continue
    rel = info["$bumpmap"].replace("\\", "/")
    target = rebuild_mat / f"{rel}.vtf"
    target.parent.mkdir(parents=True, exist_ok=True)

    result = png_to_vtf(mock_png, VTFCMD, "DXT5", "7.2")
    if result and result.exists():
        shutil.copy2(result, target)
        if result.parent != mock_png.parent: result.unlink(missing_ok=True)
        converted_n += 1

log(f"[OK] N 贴图转换: {converted_n}/{len(n_mocks)}")

# 4c. 复用原 E 贴图
for vn, info in vmt_map.items():
    e_src = palette["temp_e"] / f"{vn}_e.vtf"
    if e_src.exists():
        rel = info["$phongexponenttexture"].replace("\\", "/")
        target = rebuild_mat / f"{rel}.vtf"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(e_src, target)
log(f"[OK] E 贴图复用完成")

# 4d. 写新 VMT
for vn, info in vmt_map.items():
    params = {
        "$basetexture": info["$basetexture"],
        "$bumpmap": info["$bumpmap"],
        "$phongexponenttexture": info["$phongexponenttexture"],
    }
    # 继承原 VMT 其他参数
    orig_vmt = palette["temp_vmts"] / f"{vn}.vmt"
    if orig_vmt.exists():
        orig = parse_vmt(orig_vmt)
        for k, v in orig.items():
            if k not in params: params[k] = v
    vmt_text = build_vmt(params)

    vmt_rel = info["$basetexture"].replace("\\", "/")
    vmt_dir = Path(vmt_rel).parent
    out_dir = rebuild_mat / vmt_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{vn}.vmt").write_text(vmt_text, encoding="utf-8")

log(f"[OK] VMT 写入完成: {len(vmt_map)} 个")

rebuild_vtfs = list(rebuild_mat.rglob("*.vtf"))
rebuild_vmts = list(rebuild_mat.rglob("*.vmt"))
log(f"[OK] rebuild/materials 内容: VTF={len(rebuild_vtfs)}  VMT={len(rebuild_vmts)}")

# ============================================================
# 步骤 5: vpk.exe 封包
# ============================================================
log("\n--- 步骤 5: vpk.exe 封包 ---")

# 提取原包 models + sound
for entry_path in vpk.entries:
    if not entry_path.startswith("materials/"):
        vpk.extract(entry_path, BASE / "rebuild")

# addoninfo.txt
addon = BASE / "rebuild" / "addoninfo.txt"
if not addon.exists():
    addon.write_text('"garand_mod"', encoding="utf-8")

log("  执行: vpk.exe rebuild")
result = subprocess.run(
    [str(VPK_EXE), str(BASE / "rebuild")],
    capture_output=True, text=True, timeout=120,
)
log(f"  stdout: {result.stdout.strip()}")
if result.stderr:
    stderr_clean = "\n".join(l for l in result.stderr.split("\n")
                             if "CDynamicFunction" not in l and "Loading library" not in l
                             and "Closing library" not in l)
    if stderr_clean.strip(): log(f"  stderr: {stderr_clean.strip()}")

expected = BASE / "rebuild.vpk"
output_vpk = BASE / "output.vpk"
if expected.exists():
    shutil.move(str(expected), str(output_vpk))
    log(f"[成功] VPK 已生成: {output_vpk} ({output_vpk.stat().st_size} bytes)")

    # 验证: 列出新 VPK
    result2 = subprocess.run([str(VPK_EXE), "L", str(output_vpk)],
                              capture_output=True, text=True, timeout=30)
    lines = [l for l in result2.stdout.split("\n") if l.strip()
             and "CDynamicFunction" not in l and not l.startswith(" ")]
    log(f"[OK] 新 VPK 包含 {len(lines)} 个文件:")
    for l in lines[:5]: log(f"  {l.strip()}")
    if len(lines) > 5: log(f"  ... 共 {len(lines)} 行")
else:
    log(f"[错误] 封包失败, 检查 {BASE / 'rebuild'}")
    log(f"  rebuild 内容: {list((BASE / 'rebuild').iterdir())}")

# ============================================================
# 结果
# ============================================================
log("\n" + "=" * 60)
log("测试完成")
log(f"工作目录: {BASE}")
log(f"  temp_d:     {len(d_files)} 个 VTF (BaseColor)")
log(f"  temp_e:     {len(list(palette['temp_e'].iterdir()))} 个 VTF (PhongExponent)")
log(f"  temp_n:     {len(n_files)} 个 VTF (Normal)")
log(f"  temp_n_png: {len(list(palette['temp_n_png'].glob('*.png')))} 个 PNG (法线)")
log(f"  temp_vmts:  {len(list(palette['temp_vmts'].glob('*.vmt')))} 个 VMT")
log(f"  最终 VPK:   {'✓' if output_vpk.exists() else '✗'} {output_vpk}")
log("=" * 60)
