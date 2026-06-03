"""
SP2VTF VPK 拆装器 — 完整管线工具 (tkinter 版)

工作流:
  拆包: VPK → 解析树 → 提取 VMT → 分类 temp_d/temp_e/temp_n/temp_vmts
           → VTF → PNG (法线解压)
  回装: SP PNG → 匹配 VMT → VTFCmd 转 VTF → 写新 VMT → vpk.exe 封包

依赖: Python 3.10+, numpy, Pillow, VTFCmd.exe, vpk.exe
"""

import json
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image


# ── 运行时路径 ────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "config_vpk.json"


# ═══════════════════════════════════════════════════════════════
# VPK v1 解析器
# ═══════════════════════════════════════════════════════════════

class VPKFile:
    """解析并提取 VPK v1 文件。"""

    def __init__(self, path: Path):
        self.path = path
        self.data = open(path, "rb").read()
        self._parse_header()
        self._parse_tree()

    def _parse_header(self):
        sig, ver, ts = struct.unpack_from("<III", self.data, 0)
        if sig != 0x55AA1234:
            raise ValueError(f"不是有效的 VPK 文件 (sig=0x{sig:08X})")
        if ver != 1:
            raise ValueError(f"不支持的 VPK 版本: {ver}")
        self.tree_size = ts

    def _parse_tree(self):
        self.entries: dict[str, dict] = {}
        pos = 12
        end = pos + self.tree_size
        total_preload = 0

        while pos < end:
            ext = self._read_str(self.data, pos)
            pos += len(ext) + 1
            if not ext:
                break

            while pos < end:
                dirname = self._read_str(self.data, pos)
                pos += len(dirname) + 1
                if not dirname:
                    break

                while pos < end:
                    fname = self._read_str(self.data, pos)
                    pos += len(fname) + 1
                    if not fname:
                        break

                    crc, preload, archive, offset, length = struct.unpack_from(
                        "<IHHII", self.data, pos
                    )
                    pos += 18  # 16 bytes struct + 2 bytes 0xFFFF terminator
                    total_preload += preload

                    dirn_clean = dirname.strip()
                    full = f"{dirn_clean}/{fname}.{ext}" if dirn_clean else f"{fname}.{ext}"
                    self.entries[full] = {
                        "crc": crc, "preload": preload,
                        "archive": archive, "offset": offset, "length": length,
                    }

        self.file_data_start = 12 + self.tree_size + total_preload

    @staticmethod
    def _read_str(data: bytes, pos: int) -> str:
        end = pos
        while data[end:end+1] != b"\x00":
            end += 1
        return data[pos:end].decode("ascii", errors="replace")

    def extract(self, path: str, dest_dir: Path):
        entry = self.entries.get(path)
        if not entry:
            raise KeyError(f"文件不在 VPK 中: {path}")
        abs_off = self.file_data_start + entry["offset"]
        chunk = self.data[abs_off:abs_off + entry["length"]]
        dest = dest_dir / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(chunk)
        return dest

    def list_files(self, prefix: str = "") -> list[str]:
        if prefix:
            return sorted(p for p in self.entries if p.startswith(prefix))
        return sorted(self.entries.keys())

    def list_materials(self) -> list[str]:
        return self.list_files("materials/")

    def list_vmts(self) -> list[str]:
        return [p for p in self.entries if p.endswith(".vmt") and p.startswith("materials/")]


# ═══════════════════════════════════════════════════════════════
# VMT 解析/写入
# ═══════════════════════════════════════════════════════════════

VMT_PARAM_RE = re.compile(r'"?(\$[A-Za-z_]\w*)"?\s+(?:"([^"]+)"|([A-Za-z0-9_./\\\-]+))')


def parse_vmt(path: Path) -> dict:
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    text = re.sub(r"//[^\n]*", "", text)
    result = {}
    for m in VMT_PARAM_RE.finditer(text):
        key = m.group(1).lower()
        if key not in result:
            val = m.group(2) if m.group(2) is not None else m.group(3)
            result[key] = val.strip().replace("\\", "/")
    return result


def build_vmt(params: dict, comments: str = "") -> str:
    lines = ['"VertexlitGeneric"', "{"]
    if comments:
        lines.append(f"\t// {comments}")
    for key, val in params.items():
        lines.append(f'\t"{key}" "{val}"')
    lines.append("}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# VTF 转换 (VTFCmd)
# ═══════════════════════════════════════════════════════════════

def vtf_to_png(vtf_path: Path, vtfcmd: Path, output_dir: Path) -> Path | None:
    try:
        tga_dir = output_dir / "tga_temp"
        tga_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [str(vtfcmd), "-file", str(vtf_path), "-output", str(tga_dir),
             "-format", "RGBA8888", "-silent"],
            capture_output=True, text=True, timeout=120,
        )
        tgas = list(tga_dir.glob(f"{vtf_path.stem}*.tga"))
        if not tgas:
            return None
        img = Image.open(tgas[0]).convert("RGB")
        png_path = output_dir / f"{vtf_path.stem}.png"
        img.save(png_path)
        shutil.rmtree(tga_dir, ignore_errors=True)
        return png_path
    except Exception:
        return None


def convert_sp_png_to_vtf(png_path: Path, vtfcmd: Path, fmt: str = "DXT5",
                          version: str = "7.2") -> Path | None:
    cmd = [str(vtfcmd), "-file", str(png_path), "-output", str(png_path.parent),
           "-version", version, "-format", fmt, "-silent"]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        vtf = png_path.with_suffix(".vtf")
        return vtf if vtf.exists() else None
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════
# VMT 重写器 (JSON 驱动)
# ═══════════════════════════════════════════════════════════════

PRESETS_DIR = APP_DIR / "presets"


def load_vmt_preset(preset_name: str) -> dict:
    """载入预设 JSON，内置 sfm2sfm / sf2ems。"""
    path = PRESETS_DIR / f"{preset_name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"预设不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def rewrite_vmt_params(orig_params: dict, preset: dict, vmt_name: str,
                       new_base_stem: str | None = None) -> dict:
    """
    根据预设 JSON 重写 VMT 参数。

    - $basetexture: 自动匹配 SP 导出 (new_base_stem) 或保留原值
    - $bumpmap / $phongexponenttexture: 按 texture_rules 的 old/new 开关
    - 其余参数从 preset.params 写入（支持 {dir} {vmt_name} 占位符）
    """
    orig_base = orig_params.get("$basetexture", "")
    base_dir = str(Path(orig_base).parent) if orig_base else ""

    new_params = {}

    # 1. $basetexture — 有 SP 就自动匹配，否则保留原值
    if new_base_stem:
        new_params["$basetexture"] = f"{base_dir}/{new_base_stem}"
    elif orig_base:
        new_params["$basetexture"] = orig_base

    # 2. texture_rules — old/new 开关
    tex_rules = preset.get("texture_rules", {})

    bump_rule = tex_rules.get("$bumpmap", "old")
    if bump_rule == "new":
        new_params["$bumpmap"] = f"{base_dir}/{vmt_name}_n"
    else:
        orig_val = orig_params.get("$bumpmap", "")
        if orig_val:
            new_params["$bumpmap"] = orig_val

    exp_rule = tex_rules.get("$phongexponenttexture", "old")
    if exp_rule == "new":
        new_params["$phongexponenttexture"] = f"{base_dir}/{vmt_name}_e"
    else:
        orig_val = orig_params.get("$phongexponenttexture", "")
        if orig_val:
            new_params["$phongexponenttexture"] = orig_val

    # 3. 预设参数（不含 $basetexture / $bumpmap / $phongexponenttexture，
    #    这些由上面逻辑处理）
    for key, raw_val in preset.get("params", {}).items():
        if not key.startswith("$"):
            continue
        if key in ("$bumpmap", "$phongexponenttexture"):
            continue  # 这些由 texture_rules 控制
        val = str(raw_val)
        val = val.replace("{vmt_name}", vmt_name)
        val = val.replace("{dir}", base_dir)
        val = val.replace("{orig_base}", orig_base)
        new_params[key] = val

    return new_params


def build_vmt_from_preset(vmt_name: str, orig_params: dict,
                          preset: dict, extra_params: dict | None = None) -> str:
    """用预设重写 VMT，可选附加额外参数。"""
    params = rewrite_vmt_params(orig_params, preset, vmt_name)
    if extra_params:
        params.update(extra_params)
    return build_vmt(params)


# ═══════════════════════════════════════════════════════════════
# VMT 映射表
# ═══════════════════════════════════════════════════════════════

class VmtMapping:
    def __init__(self, data: dict | None = None):
        self._map: dict[str, dict] = data or {}

    def save(self, path: Path):
        path.write_text(json.dumps(self._map, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path):
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def items(self):
        return self._map.items()

    def get(self, vmt_name: str) -> dict | None:
        return self._map.get(vmt_name)

    def __len__(self):
        return len(self._map)

    def __bool__(self):
        return bool(self._map)


# ═══════════════════════════════════════════════════════════════
# 主应用 (tkinter)
# ═══════════════════════════════════════════════════════════════

class VPKToolApp:
    """VPK 拆装器主应用。"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SP2VTF VPK 工具 — 拆装器 + VMT 引擎")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)

        # 状态
        self._temp_root: Path | None = None
        self._palette: dict[str, Path] = {}
        self._vpk_file: VPKFile | None = None
        self._mapping: VmtMapping | None = None
        self._stop_requested = False

        # 路径
        self.vpk_exe = tk.StringVar()
        self.vpk_path = tk.StringVar()
        self.vtfcmd_path = tk.StringVar()
        self.workdir = tk.StringVar()
        self.sp_png = tk.StringVar()
        self.sp_png_n = tk.StringVar()
        self.vpk_out = tk.StringVar()
        self.vtf_version = tk.StringVar(value="7.2")
        self.vtf_color = tk.StringVar(value="DXT1")
        self.vtf_normal = tk.StringVar(value="DXT5")

        # 复选框
        self.reuse_e = tk.BooleanVar(value=True)
        self.reuse_n = tk.BooleanVar(value=False)

        self._build_ui()
        self._load_config()
        self._log("[信息] 就绪")

    # ── UI 构建 ──────────────────────────────────────────────

    def _build_ui(self):
        # 笔记本
        self._notebook = ttk.Notebook(self.root)
        self._notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # 三个标签页
        self._build_extract_tab()
        self._build_repack_tab()
        self._build_vmt_tab()

        # 日志
        log_frame = ttk.LabelFrame(self.root, text="运行日志")
        log_frame.pack(fill="both", expand=False, padx=5, pady=(0, 5))

        self._log_text = tk.Text(log_frame, height=10, font=("Consolas", 9),
                                 bg="#fafafa", fg="#333", wrap="word")
        self._log_text.pack(fill="both", expand=True, padx=3, pady=3)

        # 滚动条
        scroll = ttk.Scrollbar(self._log_text)
        scroll.pack(side="right", fill="y")
        self._log_text.config(yscrollcommand=scroll.set)
        scroll.config(command=self._log_text.yview)

        # 状态栏
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", padx=5, pady=(0, 3))
        self._status_var = tk.StringVar(value="就绪")
        self._progress_var = tk.DoubleVar(value=0)

        ttk.Label(status_frame, textvariable=self._status_var).pack(side="left")
        self._progress_bar = ttk.Progressbar(status_frame, variable=self._progress_var,
                                              mode="determinate", length=200)
        self._progress_bar.pack(side="right", padx=5)
        self._progress_bar.pack_forget()  # 初始隐藏

    # ── Tab 1: 拆包 ──────────────────────────────────────────

    def _build_extract_tab(self):
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text="① 拆解 VPK")

        # 路径
        path_frame = ttk.LabelFrame(frame, text="路径配置")
        path_frame.pack(fill="x", padx=5, pady=5)

        fields = [
            ("vpk.exe 路径", self.vpk_exe, self._browse_vpk_exe),
            ("VPK 文件", self.vpk_path, self._browse_vpk),
            ("VTFCmd.exe", self.vtfcmd_path, self._browse_vtfcmd),
            ("工作目录", self.workdir, self._browse_workdir),
        ]
        for i, (label, var, cmd) in enumerate(fields):
            ttk.Label(path_frame, text=label).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            ttk.Entry(path_frame, textvariable=var).grid(row=i, column=1, sticky="ew", padx=5, pady=2)
            ttk.Button(path_frame, text="浏览", command=cmd).grid(row=i, column=2, padx=5)
        path_frame.columnconfigure(1, weight=1)

        # 按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", padx=5, pady=5)

        self._btn_extract = ttk.Button(btn_frame, text="🔧 拆解 VPK", command=self._start_extract)
        self._btn_extract.pack(side="left", padx=2)
        ttk.Button(btn_frame, text="📷 法线解 PNG", command=self._start_normal_export).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="📋 查看映射表", command=self._show_mapping).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="保存配置", command=self._save_config).pack(side="right", padx=2)

        # 拆解预览
        tree_frame = ttk.LabelFrame(frame, text="拆解预览")
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        columns = ("VMT", "BaseTexture", "BumpMap", "PhongExp", "状态")
        self._extract_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                           height=12)
        for col in columns:
            self._extract_tree.heading(col, text=col)
            self._extract_tree.column(col, width=140 if col != "VMT" else 200)
        self._extract_tree.pack(fill="both", expand=True, side="left")

        scroll = ttk.Scrollbar(tree_frame, command=self._extract_tree.yview)
        scroll.pack(side="right", fill="y")
        self._extract_tree.config(yscrollcommand=scroll.set)

    # ── Tab 2: 回装 ──────────────────────────────────────────

    def _build_repack_tab(self):
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text="② 回装 VPK")

        # SP 路径
        sp_frame = ttk.LabelFrame(frame, text="SP 导出路径")
        sp_frame.pack(fill="x", padx=5, pady=5)

        fields = [
            ("BaseColor 目录", self.sp_png, self._browse_sp_png),
            ("法线目录", self.sp_png_n, self._browse_sp_png_n),
            ("VPK 输出路径", self.vpk_out, self._browse_vpk_out),
        ]
        for i, (label, var, cmd) in enumerate(fields):
            ttk.Label(sp_frame, text=label).grid(row=i, column=0, sticky="w", padx=5, pady=2)
            ttk.Entry(sp_frame, textvariable=var).grid(row=i, column=1, sticky="ew", padx=5, pady=2)
            ttk.Button(sp_frame, text="浏览", command=cmd).grid(row=i, column=2, padx=5)
        sp_frame.columnconfigure(1, weight=1)

        ttk.Checkbutton(sp_frame, text="复用原 E 贴图 (phongexponenttexture)",
                         variable=self.reuse_e).grid(row=3, column=1, sticky="w", padx=5)
        ttk.Checkbutton(sp_frame, text="复用原 N 贴图 (bumpmap)",
                         variable=self.reuse_n).grid(row=4, column=1, sticky="w", padx=5)

        # VTF 设置
        vtf_frame = ttk.LabelFrame(frame, text="VTF 输出设置")
        vtf_frame.pack(fill="x", padx=5, pady=5)

        ttk.Label(vtf_frame, text="Color 格式:").grid(row=0, column=0, padx=5, pady=2)
        ttk.Combobox(vtf_frame, textvariable=self.vtf_color,
                      values=["DXT1", "DXT5", "RGBA8888", "RGB888"],
                      width=12, state="readonly").grid(row=0, column=1, padx=5)
        ttk.Label(vtf_frame, text="法线格式:").grid(row=0, column=2, padx=5)
        ttk.Combobox(vtf_frame, textvariable=self.vtf_normal,
                      values=["DXT5", "RGBA8888", "DXT1"],
                      width=12, state="readonly").grid(row=0, column=3, padx=5)
        ttk.Label(vtf_frame, text="VTF 版本:").grid(row=0, column=4, padx=5)
        ttk.Combobox(vtf_frame, textvariable=self.vtf_version,
                      values=["7.0", "7.1", "7.2", "7.3", "7.4", "7.5"],
                      width=6, state="readonly").grid(row=0, column=5, padx=5)

        # 按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", padx=5, pady=5)
        self._btn_repack = ttk.Button(btn_frame, text="📦 回装 VPK", command=self._start_repack)
        self._btn_repack.pack(side="left", padx=2)
        ttk.Button(btn_frame, text="刷新预览", command=self._refresh_repack_tree).pack(side="left", padx=2)

        # 回装预览
        tree_frame = ttk.LabelFrame(frame, text="回装预览")
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        columns = ("VMT", "BaseTexture 回写", "BumpMap 回写", "状态")
        self._repack_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                          height=12)
        for col in columns:
            self._repack_tree.heading(col, text=col)
            self._repack_tree.column(col, width=160 if col != "VMT" else 200)
        self._repack_tree.pack(fill="both", expand=True, side="left")

        scroll = ttk.Scrollbar(tree_frame, command=self._repack_tree.yview)
        scroll.pack(side="right", fill="y")
        self._repack_tree.config(yscrollcommand=scroll.set)

    # ── Tab 3: VMT 引擎 ──────────────────────────────────────

    def _build_vmt_tab(self):
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text="③ VMT 规则引擎")

        text = tk.Text(frame, font=("Microsoft YaHei UI", 10), wrap="word",
                        bg="#fafafa", fg="#444", padx=10, pady=10)
        text.insert("1.0", """VMT 规则集引擎将在后续版本实现。

当前版本提供自动/手动两种模式:
  自动: VPK 拆解后，保留原 VMT 参数不变
  手动: 在 temp_vmts 中直接编辑 VMT 文件

后续计划:
  - 支持 JSON/YAML 规则集预设
  - 根据金属度/粗糙度/曝光推算 VMT 参数
  - 社区规则集分享 (类似印花集、赛车烤漆等)
  - 本标签页将作为规则集管理界面
""")
        text.config(state="disabled")
        text.pack(fill="both", expand=True, padx=5, pady=5)

    # ── 浏览 ─────────────────────────────────────────────────

    def _browse_vpk_exe(self):
        p = filedialog.askopenfilename(title="选择 vpk.exe", filetypes=[("vpk.exe", "vpk.exe")])
        if p: self.vpk_exe.set(p)

    def _browse_vpk(self):
        p = filedialog.askopenfilename(title="选择 VPK", filetypes=[("VPK", "*.vpk")])
        if p: self.vpk_path.set(p)

    def _browse_vtfcmd(self):
        p = filedialog.askopenfilename(title="选择 VTFCmd.exe", filetypes=[("VTFCmd.exe", "VTFCmd.exe")])
        if p: self.vtfcmd_path.set(p)

    def _browse_workdir(self):
        p = filedialog.askdirectory(title="选择工作目录")
        if p: self.workdir.set(p)

    def _browse_sp_png(self):
        p = filedialog.askdirectory(title="SP BaseColor 目录")
        if p: self.sp_png.set(p)

    def _browse_sp_png_n(self):
        p = filedialog.askdirectory(title="SP 法线目录")
        if p: self.sp_png_n.set(p)

    def _browse_vpk_out(self):
        p = filedialog.asksaveasfilename(title="VPK 输出", defaultextension=".vpk",
                                          filetypes=[("VPK", "*.vpk")])
        if p: self.vpk_out.set(p)

    # ── 拆包 ─────────────────────────────────────────────────

    def _start_extract(self):
        vpk_exe = Path(self.vpk_exe.get().strip())
        vpk_path = Path(self.vpk_path.get().strip())
        vtfcmd = Path(self.vtfcmd_path.get().strip())
        workdir = Path(self.workdir.get().strip())

        if not vpk_exe.is_file():
            messagebox.showerror("错误", "vpk.exe 不存在"); return
        if not vpk_path.is_file():
            messagebox.showerror("错误", "VPK 文件不存在"); return
        if not vtfcmd.is_file():
            messagebox.showerror("错误", "VTFCmd.exe 不存在"); return

        self._temp_root = workdir
        self._palette = {
            "d": self._ensure(workdir / "temp_d"),
            "e": self._ensure(workdir / "temp_e"),
            "n": self._ensure(workdir / "temp_n"),
            "n_png": self._ensure(workdir / "temp_n_png"),
            "vmts": self._ensure(workdir / "temp_vmts"),
        }

        self._stop_requested = False
        self._btn_extract.config(state="disabled")
        threading.Thread(target=self._extract_worker,
                         args=(vpk_exe, vpk_path, vtfcmd), daemon=True).start()

    def _extract_worker(self, vpk_exe, vpk_path, vtfcmd):
        try:
            self._log("[信息] 开始拆解 VPK...")
            self._show_progress(0, 100, "解析 VPK 结构...")

            vpk = VPKFile(vpk_path)
            self._vpk_file = vpk
            vmts = vpk.list_vmts()
            self._log(f"[信息] VPK 包含 {len(vmts)} 个 VMT 文件")

            # 提取 VMT
            self._log("[信息] 提取 VMT...")
            vmt_map = {}
            for vmt_path in vmts:
                if self._stop_requested:
                    break
                dest = vpk.extract(vmt_path, self._palette["vmts"])
                pure_name = Path(vmt_path).name
                if dest.name != pure_name:
                    shutil.copy2(dest, self._palette["vmts"] / pure_name)
                params = parse_vmt(dest)
                vmt_name = Path(vmt_path).stem
                vmt_map[vmt_name] = {
                    "$basetexture": params.get("$basetexture", ""),
                    "$bumpmap": params.get("$bumpmap", ""),
                    "$phongexponenttexture": params.get("$phongexponenttexture", ""),
                }
            self._log(f"[信息] 已提取 {len(vmt_map)} 个 VMT")

            # 提取纹理
            self._log("[信息] 提取纹理文件...")
            all_mat = vpk.list_materials()
            for mat_path in all_mat:
                if self._stop_requested:
                    break
                if mat_path.endswith(".vmt"):
                    continue

                entry = vpk.entries.get(mat_path)
                if not entry or entry["length"] == 0:
                    continue

                fname = Path(mat_path).name.lower()
                vtf_stem = Path(mat_path).stem.lower()
                matched = False

                for vmt_name, info in vmt_map.items():
                    base_stem = Path(info.get("$basetexture", "")).stem.lower()
                    bump_stem = Path(info.get("$bumpmap", "")).stem.lower()
                    exp_stem = Path(info.get("$phongexponenttexture", "")).stem.lower()

                    if vtf_stem == base_stem and base_stem:
                        dest = vpk.extract(mat_path, self._palette["d"])
                        new = self._palette["d"] / f"{vmt_name}_d.vtf"
                        if dest.name != new.name:
                            shutil.copy2(dest, new)
                        matched = True
                        break
                    elif vtf_stem == bump_stem and bump_stem:
                        dest = vpk.extract(mat_path, self._palette["n"])
                        new = self._palette["n"] / f"{vmt_name}_n.vtf"
                        if dest.name != new.name:
                            shutil.copy2(dest, new)
                        matched = True
                        break
                    elif vtf_stem == exp_stem and exp_stem:
                        dest = vpk.extract(mat_path, self._palette["e"])
                        new = self._palette["e"] / f"{vmt_name}_e.vtf"
                        if dest.name != new.name:
                            shutil.copy2(dest, new)
                        matched = True
                        break

                if not matched:
                    self._log(f"  [?] 未分类: {fname}")

            # 映射表
            self._mapping = VmtMapping(vmt_map)
            map_path = workdir / "mapping.json"
            self._mapping.save(map_path)
            self._log(f"[成功] 映射表: {map_path}")

            # 刷新树
            self._after_safe(lambda: self._fill_extract_tree(vmt_map))
            self._log(f"[成功] 拆解完成，共 {len(vmt_map)} 组")
            self._show_progress(100, 100, "完成")

        except Exception as e:
            self._log(f"[异常] 拆解失败: {e}")
            import traceback
            for line in traceback.format_exc().split("\n"):
                self._log(f"  {line}")
        finally:
            self._after_safe(lambda: self._btn_extract.config(state="normal"))

    def _fill_extract_tree(self, vmt_map):
        for item in self._extract_tree.get_children():
            self._extract_tree.delete(item)
        for vmt_name, info in sorted(vmt_map.items()):
            d_ok = (self._palette.get("d", Path()) / f"{vmt_name}_d.vtf").exists()
            e_ok = (self._palette.get("e", Path()) / f"{vmt_name}_e.vtf").exists()
            n_ok = (self._palette.get("n", Path()) / f"{vmt_name}_n.vtf").exists()
            status = f"D={'✓' if d_ok else '✗'} E={'✓' if e_ok else '✗'} N={'✓' if n_ok else '✗'}"
            self._extract_tree.insert("", "end", values=(
                f"{vmt_name}.vmt",
                info.get("$basetexture", ""),
                info.get("$bumpmap", ""),
                info.get("$phongexponenttexture", ""),
                status,
            ))

    # ── 法线导出 ─────────────────────────────────────────────

    def _start_normal_export(self):
        if not self._palette or not self._palette.get("n"):
            messagebox.showerror("错误", "请先拆解 VPK"); return
        vtfcmd = Path(self.vtfcmd_path.get().strip())
        if not vtfcmd.is_file():
            messagebox.showerror("错误", "VTFCmd.exe 不存在"); return

        threading.Thread(target=self._normal_export_worker, args=(vtfcmd,), daemon=True).start()

    def _normal_export_worker(self, vtfcmd):
        try:
            n_dir = self._palette["n"]
            png_dir = self._palette["n_png"]
            vtfs = list(n_dir.glob("*.vtf"))
            self._log(f"[信息] 法线 VTF → PNG: {len(vtfs)} 个")

            for i, vtf in enumerate(vtfs):
                if self._stop_requested:
                    break
                self._show_progress(i + 1, len(vtfs), f"转换 {i+1}/{len(vtfs)}")
                png = vtf_to_png(vtf, vtfcmd, png_dir)
                self._log(f"  {'[OK]' if png else '[失败]'} {vtf.name}")

            self._log("[成功] 法线转换完成")
            self._show_progress(len(vtfs), len(vtfs), "完成")
        except Exception as e:
            self._log(f"[异常] {e}")

    def _show_mapping(self):
        if not self._mapping:
            self._log("[信息] 请先拆解 VPK"); return
        self._log("==== 映射表 ====")
        for vmt_name, info in self._mapping.items():
            self._log(f"  {vmt_name}.vmt:")
            for k, v in info.items():
                self._log(f"    {k}: {v}")

    # ── 回装 ─────────────────────────────────────────────────

    def _refresh_repack_tree(self):
        for item in self._repack_tree.get_children():
            self._repack_tree.delete(item)
        if not self._mapping:
            return

        sp_dir = Path(self.sp_png.get().strip())
        sp_dir_n = Path(self.sp_png_n.get().strip())

        for vmt_name, info in self._mapping.items():
            d_src = sp_dir / f"{vmt_name}_Base_Color.png"
            if not d_src.exists():
                d_src = sp_dir / f"{vmt_name}_base_color.png"
            n_src = sp_dir_n / f"{vmt_name}_Normal_OpenGL.png"
            if not n_src.exists():
                n_src = sp_dir_n / f"{vmt_name}_normal_opengl.png"

            d_target = info.get("$basetexture", "?")
            n_status = "复用" if self.reuse_n.get() else (n_src.name if n_src.exists() else "未找到")
            status = "可回装" if d_src.exists() or self.reuse_n.get() else "缺文件"

            self._repack_tree.insert("", "end", values=(
                f"{vmt_name}.vmt",
                f"{d_target} ← {d_src.name if d_src.exists() else '?'}",
                f"{info.get('$bumpmap', '?')} ← {n_status}",
                status,
            ))

    def _start_repack(self):
        vpk_exe = Path(self.vpk_exe.get().strip())
        vtfcmd = Path(self.vtfcmd_path.get().strip())
        sp_dir = Path(self.sp_png.get().strip())
        sp_dir_n = Path(self.sp_png_n.get().strip())
        vpk_out = Path(self.vpk_out.get().strip())

        if not vpk_exe.is_file():
            messagebox.showerror("错误", "vpk.exe 不存在"); return
        if not vtfcmd.is_file():
            messagebox.showerror("错误", "VTFCmd.exe 不存在"); return
        if not self._mapping or not self._temp_root:
            messagebox.showerror("错误", "请先拆解 VPK"); return
        if not sp_dir.is_dir():
            messagebox.showerror("错误", "SP PNG 目录不存在"); return
        if not vpk_out.parent.exists():
            messagebox.showerror("错误", "输出目录不存在"); return

        self._stop_requested = False
        self._btn_repack.config(state="disabled")
        threading.Thread(target=self._repack_worker,
                         args=(vpk_exe, vtfcmd, sp_dir, sp_dir_n, vpk_out),
                         daemon=True).start()

    def _repack_worker(self, vpk_exe, vtfcmd, sp_dir, sp_dir_n, vpk_out):
        rebuild_dir = self._temp_root / "rebuild"
        materials_dir = rebuild_dir / "materials"
        try:
            self._log("[信息] 开始回装...")
            color_fmt = self.vtf_color.get()
            normal_fmt = self.vtf_normal.get()
            version = self.vtf_version.get()
            reuse_e = self.reuse_e.get()
            reuse_n = self.reuse_n.get()

            items = list(self._mapping.items())
            total = len(items)

            for i, (vmt_name, info) in enumerate(items):
                if self._stop_requested:
                    self._log("[提示] 用户中止"); break

                self._show_progress(i + 1, total, f"处理 {vmt_name}...")

                # BaseColor
                d_png = sp_dir / f"{vmt_name}_Base_Color.png"
                if not d_png.exists():
                    d_png = sp_dir / f"{vmt_name}_base_color.png"
                if d_png.exists():
                    base_rel = info.get("$basetexture", f"{vmt_name}_Base_Color").replace("\\", "/")
                    vtf_path = materials_dir / f"{base_rel}.vtf"
                    vtf_path.parent.mkdir(parents=True, exist_ok=True)

                    result = convert_sp_png_to_vtf(d_png, vtfcmd, color_fmt, version)
                    if result and result.exists():
                        shutil.copy2(result, vtf_path)
                        if result.parent != d_png.parent:
                            result.unlink(missing_ok=True)
                        self._log(f"  [D] {vmt_name}: {base_rel}.vtf")

                # BumpMap
                if not reuse_n:
                    n_png = sp_dir_n / f"{vmt_name}_Normal_OpenGL.png"
                    if not n_png.exists():
                        n_png = sp_dir_n / f"{vmt_name}_normal_opengl.png"
                    if n_png.exists():
                        bump_rel = info.get("$bumpmap", f"{vmt_name}_n").replace("\\", "/")
                        vtf_path = materials_dir / f"{bump_rel}.vtf"
                        vtf_path.parent.mkdir(parents=True, exist_ok=True)

                        result = convert_sp_png_to_vtf(n_png, vtfcmd, normal_fmt, version)
                        if result and result.exists():
                            shutil.copy2(result, vtf_path)
                            if result.parent != n_png.parent:
                                result.unlink(missing_ok=True)
                            self._log(f"  [N] {vmt_name}: {bump_rel}.vtf")

                # PhongExponent (复用原文件)
                if reuse_e:
                    e_src = self._palette.get("e", Path()) / f"{vmt_name}_e.vtf"
                    if e_src.exists():
                        exp_rel = info.get("$phongexponenttexture", f"{vmt_name}_e").replace("\\", "/")
                        vtf_path = materials_dir / f"{exp_rel}.vtf"
                        vtf_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(e_src, vtf_path)

                # VMT
                vmt_params = {
                    "$basetexture": info.get("$basetexture", f"{vmt_name}_Base_Color"),
                    "$bumpmap": info.get("$bumpmap", f"{vmt_name}_n"),
                    "$phongexponenttexture": info.get("$phongexponenttexture", f"{vmt_name}_e"),
                }
                orig_vmt_path = self._palette.get("vmts", Path()) / f"{vmt_name}.vmt"
                if orig_vmt_path.exists():
                    orig_params = parse_vmt(orig_vmt_path)
                    for k, v in orig_params.items():
                        if k.startswith("$") and k not in vmt_params:
                            vmt_params[k] = v
                vmt_text = build_vmt(vmt_params)

                vmt_rel = info.get("$basetexture", f"{vmt_name}_Base_Color").replace("\\", "/")
                vmt_dir_part = Path(vmt_rel).parent
                vmt_out_dir = materials_dir / vmt_dir_part
                vmt_out_dir.mkdir(parents=True, exist_ok=True)
                (vmt_out_dir / f"{vmt_name}.vmt").write_text(vmt_text, encoding="utf-8")
                self._log(f"  [VMT] {vmt_name}: 已写入")

            if not self._stop_requested:
                # 模型+音效
                self._log("[信息] 提取原包模型和音效...")
                if self._vpk_file:
                    for entry_path in self._vpk_file.entries:
                        if not entry_path.startswith("materials/"):
                            self._vpk_file.extract(entry_path, rebuild_dir)

                # 封包
                self._log("[信息] 正在封包 VPK...")
                self._show_progress(total, total, "封包中...")

                # addoninfo.txt
                addon = rebuild_dir / "addoninfo.txt"
                if not addon.exists():
                    addon.write_text('"addon"', encoding="utf-8")

                result = subprocess.run(
                    [str(vpk_exe), str(rebuild_dir)],
                    capture_output=True, text=True, timeout=120,
                )
                expected = rebuild_dir.parent / f"{rebuild_dir.name}.vpk"
                if expected.exists():
                    shutil.move(str(expected), str(vpk_out))
                    self._log(f"[成功] VPK 生成: {vpk_out}")
                else:
                    self._log("[错误] 封包失败，检查临时目录")

        except Exception as e:
            self._log(f"[异常] 回装失败: {e}")
            import traceback
            for line in traceback.format_exc().split("\n"):
                self._log(f"  {line}")
        finally:
            if rebuild_dir.exists():
                shutil.rmtree(rebuild_dir, ignore_errors=True)
            self._after_safe(lambda: self._btn_repack.config(state="normal"))

    # ── 工具 ─────────────────────────────────────────────────

    @staticmethod
    def _ensure(d: Path) -> Path:
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._after_safe(lambda: self._log_text.insert("end", f"[{ts}] {msg}\n"))

    def _show_progress(self, current, total, text):
        if total:
            val = current / total * 100
            self._after_safe(lambda: self._progress_bar.pack(side="right", padx=5))
            self._after_safe(lambda: self._progress_bar.config(value=val))
        self._after_safe(lambda: self._status_var.set(text or ""))

    def _after_safe(self, func):
        """线程安全地调度 UI 更新。"""
        if threading.current_thread() is threading.main_thread():
            func()
        else:
            self.root.after(0, func)

    # ── 配置 ─────────────────────────────────────────────────

    def _load_config(self):
        if not CONFIG_FILE.exists():
            return
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        for key, var in [
            ("vpk_exe", self.vpk_exe), ("vpk_path", self.vpk_path),
            ("vtfcmd", self.vtfcmd_path), ("workdir", self.workdir),
            ("sp_png", self.sp_png), ("sp_png_n", self.sp_png_n),
            ("vpk_out", self.vpk_out), ("vtf_version", self.vtf_version),
            ("color_format", self.vtf_color), ("normal_format", self.vtf_normal),
        ]:
            if key in cfg:
                var.set(cfg[key])

    def _save_config(self):
        cfg = {
            "vpk_exe": self.vpk_exe.get(), "vpk_path": self.vpk_path.get(),
            "vtfcmd": self.vtfcmd_path.get(), "workdir": self.workdir.get(),
            "sp_png": self.sp_png.get(), "sp_png_n": self.sp_png_n.get(),
            "vpk_out": self.vpk_out.get(), "vtf_version": self.vtf_version.get(),
            "color_format": self.vtf_color.get(), "normal_format": self.vtf_normal.get(),
        }
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

    def run(self):
        self.root.mainloop()


# ═══════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = VPKToolApp()
    app.run()
