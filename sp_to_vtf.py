"""SP 贴图转 VTF 工具 — 单文件 tkinter GUI."""

import json
import re
import shutil
import struct
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, font as tkfont, scrolledtext, ttk

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "config.json"

SUFFIX_TO_PARAM = {
    "_Base_Color": "$basetexture",
    "_Normal_OpenGL": "$bumpmap",
}


def parse_vmt(path: Path) -> dict:
    """Return {param_lowercase: relative_texture_path} parsed from a VMT file."""
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    text = re.sub(r"//[^\n]*", "", text)
    result = {}
    for m in re.finditer(r'"?(\$[A-Za-z_]\w*)"?\s+"([^"]+)"', text):
        result[m.group(1).lower()] = m.group(2).strip().replace("\\", "/")
    for m in re.finditer(r'"?(\$[A-Za-z_]\w*)"?[ \t]+([A-Za-z0-9_./\\\-]+)', text):
        key = m.group(1).lower()
        if key not in result:
            result[key] = m.group(2).strip().replace("\\", "/")
    return result


def png_size(path: Path):
    """Read PNG width/height from IHDR chunk. Returns (w, h) or None."""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
        if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        w, h = struct.unpack(">II", head[16:24])
        return (w, h)
    except OSError:
        return None


class App:
    FIELDS = [
        ("VTFCmd.exe 路径", "vtfcmd", "file"),
        ("SP PNG 文件夹", "png_dir", "dir"),
        ("VMT 文件夹", "vmt_dir", "dir"),
        ("L4D2 materials 根目录", "materials_dir", "dir"),
    ]
    CHECK_ON = "☑"
    CHECK_OFF = "☐"
    CHECK_NA = "—"
    SLOT_TO_COL = {"base": "base", "normal": "normal"}
    VTF_VERSIONS = ["7.0", "7.1", "7.2", "7.3", "7.4", "7.5"]
    VTF_FORMATS = [
        "RGBA8888", "ABGR8888", "RGB888", "BGR888", "RGB565",
        "I8", "IA88", "A8",
        "RGB888_BLUESCREEN", "BGR888_BLUESCREEN",
        "ARGB8888", "BGRA8888",
        "DXT1", "DXT3", "DXT5",
        "BGRX8888", "BGR565", "BGRX5551", "BGRA4444",
        "DXT1_ONEBITALPHA", "BGRA5551",
        "UV88", "UVWQ8888",
        "RGBA16161616F", "RGBA16161616", "UVLX8888",
    ]
    RESIZE_METHODS = ["nearest", "biggest", "smallest"]
    RESIZE_FILTERS = [
        "point", "box", "triangle", "quadratic", "cubic", "catrom", "mitchell",
        "gaussian", "sinc", "bessel", "hanning", "hamming", "blackman", "kaiser",
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("SP 贴图转 VTF 工具")
        root.geometry("1060x800")
        root.minsize(900, 640)

        self.vars = {key: tk.StringVar() for _, key, _ in self.FIELDS}
        self.size_enabled = tk.BooleanVar(value=True)
        self.resize_enabled = tk.BooleanVar(value=True)
        self.resize_width = tk.IntVar(value=1024)
        self.resize_height = tk.IntVar(value=1024)
        self.vtf_version = tk.StringVar(value="7.2")
        self.color_format = tk.StringVar(value="DXT1")
        self.alpha_format = tk.StringVar(value="DXT5")
        self.resize_method = tk.StringVar(value="nearest")
        self.resize_filter = tk.StringVar(value="triangle")
        self.items = {}
        self.load_config()
        self.build_ui()

    def build_ui(self):
        ui_family = "Microsoft YaHei UI"
        for fname in ("TkDefaultFont", "TkTextFont", "TkMenuFont",
                      "TkHeadingFont", "TkTooltipFont", "TkIconFont"):
            try:
                tkfont.nametofont(fname).configure(family=ui_family)
            except tk.TclError:
                pass

        style = ttk.Style()
        for theme in ("vista", "winnative", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        style.configure("Accent.TButton", font=(ui_family, 10, "bold"))
        style.configure("Section.TLabelframe", padding=10)
        style.configure("Section.TLabelframe.Label", font=(ui_family, 10, "bold"),
                        foreground="#1f2937")
        style.configure("Hint.TLabel", foreground="#6b7280")
        style.configure("Status.TLabel", foreground="#6b7280")
        style.configure("Treeview", rowheight=26, font=(ui_family, 9))
        style.configure("Treeview.Heading", font=(ui_family, 9, "bold"))

        root_frm = ttk.Frame(self.root, padding=12)
        root_frm.pack(fill="both", expand=True)
        root_frm.columnconfigure(0, weight=1)

        paths = ttk.LabelFrame(root_frm, text=" 路径配置 ", style="Section.TLabelframe")
        paths.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        paths.columnconfigure(1, weight=1)
        for i, (label, key, kind) in enumerate(self.FIELDS):
            ttk.Label(paths, text=label, width=22).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Entry(paths, textvariable=self.vars[key]).grid(row=i, column=1, sticky="ew", padx=6, pady=3)
            ttk.Button(paths, text="浏览…", width=9,
                       command=lambda k=key, t=kind: self.browse(k, t)
                       ).grid(row=i, column=2, pady=3)

        vtf_box = ttk.LabelFrame(root_frm, text=" VTF 输出参数 ", style="Section.TLabelframe")
        vtf_box.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(vtf_box, text="版本").pack(side="left")
        ttk.Combobox(vtf_box, textvariable=self.vtf_version, values=self.VTF_VERSIONS,
                     width=6, state="readonly").pack(side="left", padx=(6, 20))
        ttk.Label(vtf_box, text="Color 格式").pack(side="left")
        ttk.Combobox(vtf_box, textvariable=self.color_format, values=self.VTF_FORMATS,
                     width=18, state="readonly").pack(side="left", padx=(6, 4))
        ttk.Label(vtf_box, text="basetexture", style="Hint.TLabel").pack(side="left", padx=(0, 20))
        ttk.Label(vtf_box, text="Alpha 格式").pack(side="left")
        ttk.Combobox(vtf_box, textvariable=self.alpha_format, values=self.VTF_FORMATS,
                     width=18, state="readonly").pack(side="left", padx=(6, 4))
        ttk.Label(vtf_box, text="bumpmap", style="Hint.TLabel").pack(side="left")

        resize_box = ttk.LabelFrame(root_frm, text=" 缩放设置 ", style="Section.TLabelframe")
        resize_box.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        row_a = ttk.Frame(resize_box)
        row_a.pack(fill="x", pady=(0, 6))
        ttk.Checkbutton(row_a, text="分辨率", variable=self.size_enabled,
                        command=self._update_size_state).pack(side="left", padx=(0, 10))
        lbl_w = ttk.Label(row_a, text="宽"); lbl_w.pack(side="left")
        sp_w = ttk.Spinbox(row_a, from_=128, to=4096, increment=128, width=7, textvariable=self.resize_width)
        sp_w.pack(side="left", padx=(4, 10))
        lbl_h = ttk.Label(row_a, text="高"); lbl_h.pack(side="left")
        sp_h = ttk.Spinbox(row_a, from_=128, to=4096, increment=128, width=7, textvariable=self.resize_height)
        sp_h.pack(side="left", padx=(4, 10))
        btn_apply = ttk.Button(row_a, text="应用默认到全部", command=self.apply_default_resize)
        btn_apply.pack(side="left", padx=(0, 16))
        ttk.Label(row_a, text="范围 128~4096,双击列表分辨率单元格可单独修改",
                  style="Hint.TLabel").pack(side="left")

        row_b = ttk.Frame(resize_box)
        row_b.pack(fill="x")
        ttk.Checkbutton(row_b, text="Resize", variable=self.resize_enabled,
                        command=self._update_resize_state).pack(side="left", padx=(0, 10))
        lbl_m = ttk.Label(row_b, text="Method"); lbl_m.pack(side="left")
        cb_m = ttk.Combobox(row_b, textvariable=self.resize_method, values=self.RESIZE_METHODS,
                            width=10, state="readonly")
        cb_m.pack(side="left", padx=(4, 16))
        lbl_f = ttk.Label(row_b, text="Filter"); lbl_f.pack(side="left")
        cb_f = ttk.Combobox(row_b, textvariable=self.resize_filter, values=self.RESIZE_FILTERS,
                            width=10, state="readonly")
        cb_f.pack(side="left", padx=(4, 0))

        self._size_children = [lbl_w, sp_w, lbl_h, sp_h, btn_apply]
        self._resize_children = [lbl_m, cb_m, lbl_f, cb_f]

        btns = ttk.Frame(root_frm)
        btns.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        ttk.Button(btns, text="载入 VMT", command=self.load_vmts).pack(side="left", padx=(0, 4))
        self.run_btn = ttk.Button(btns, text="开始转换", command=self.start_convert,
                                  style="Accent.TButton")
        self.run_btn.pack(side="left", padx=(0, 10))
        ttk.Separator(btns, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(btns, text="全选 base", command=lambda: self.select_all("base", True)).pack(side="left", padx=2)
        ttk.Button(btns, text="全不选 base", command=lambda: self.select_all("base", False)).pack(side="left", padx=2)
        ttk.Button(btns, text="全选 bump", command=lambda: self.select_all("normal", True)).pack(side="left", padx=2)
        ttk.Button(btns, text="全不选 bump", command=lambda: self.select_all("normal", False)).pack(side="left", padx=2)
        ttk.Separator(btns, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(btns, text="保存配置", command=lambda: (self.save_config(), self.log("配置已保存"))).pack(side="left", padx=2)
        ttk.Button(btns, text="清空日志", command=self.clear_log).pack(side="left", padx=2)

        paned = ttk.PanedWindow(root_frm, orient="vertical")
        paned.grid(row=4, column=0, sticky="nsew", pady=(4, 0))
        root_frm.rowconfigure(4, weight=1)

        tree_box = ttk.LabelFrame(paned, text=" VMT 列表 ", style="Section.TLabelframe")
        self.tree = ttk.Treeview(
            tree_box,
            columns=("base", "base_info", "normal", "normal_info"),
            show="tree headings",
            height=12,
        )
        self.tree.heading("#0", text="VMT 文件")
        self.tree.heading("base", text="basetexture")
        self.tree.heading("base_info", text="Base_Color  源 → 目标")
        self.tree.heading("normal", text="bumpmap")
        self.tree.heading("normal_info", text="Normal  源 → 目标")
        self.tree.column("#0", width=260, anchor="w")
        self.tree.column("base", width=100, anchor="center")
        self.tree.column("base_info", width=220, anchor="center")
        self.tree.column("normal", width=100, anchor="center")
        self.tree.column("normal_info", width=220, anchor="center")
        self.tree.tag_configure("odd", background="#f5f7fa")
        self.tree.tag_configure("even", background="#ffffff")
        vsb = ttk.Scrollbar(tree_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self.on_tree_click)
        self.tree.bind("<Double-Button-1>", self.on_tree_dblclick)
        paned.add(tree_box, weight=2)

        log_box = ttk.LabelFrame(paned, text=" 运行日志 ", style="Section.TLabelframe")
        self.log_widget = scrolledtext.ScrolledText(log_box, wrap="word", height=10,
                                                    font=("Consolas", 9),
                                                    relief="flat", borderwidth=0,
                                                    background="#fafbfc")
        self.log_widget.pack(fill="both", expand=True)
        self.log_widget.tag_configure("ts", foreground="#9ca3af")
        self.log_widget.tag_configure("error", foreground="#b00020", font=("Consolas", 9, "bold"))
        self.log_widget.tag_configure("warn", foreground="#b45309")
        self.log_widget.tag_configure("ok", foreground="#15803d")
        self.log_widget.tag_configure("info", foreground="#1d4ed8")
        self.log_widget.tag_configure("head", font=("Consolas", 9, "bold"), foreground="#111827")
        self.log_widget.configure(state="disabled", cursor="arrow")
        paned.add(log_box, weight=1)

        status_sep = ttk.Separator(root_frm, orient="horizontal")
        status_sep.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        status_frm = ttk.Frame(root_frm)
        status_frm.grid(row=6, column=0, sticky="ew", pady=(4, 0))
        self.status_var = tk.StringVar(value="就绪 — 填好路径后点击「载入 VMT」")
        ttk.Label(status_frm, textvariable=self.status_var, style="Status.TLabel").pack(side="left")

        self._update_size_state()
        self._update_resize_state()

    def _apply_enabled(self, children, on):
        flag = "!disabled" if on else "disabled"
        for w in children:
            try:
                w.state([flag])
            except tk.TclError:
                pass

    def _update_size_state(self):
        self._apply_enabled(getattr(self, "_size_children", ()), bool(self.size_enabled.get()))

    def _update_resize_state(self):
        self._apply_enabled(getattr(self, "_resize_children", ()), bool(self.resize_enabled.get()))

    def browse(self, key, kind):
        if kind == "file":
            path = filedialog.askopenfilename(filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")])
        else:
            path = filedialog.askdirectory()
        if path:
            self.vars[key].set(path)

    def clear_log(self):
        self.log_widget.configure(state="normal")
        self.log_widget.delete("1.0", "end")
        self.log_widget.configure(state="disabled")

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        tag = ()
        if any(k in msg for k in ("[错误]", "[异常]", "[失败]")):
            tag = ("error",)
        elif "[警告]" in msg:
            tag = ("warn",)
        elif "[成功]" in msg or msg.startswith("====") or msg.startswith("==== 完成"):
            tag = ("ok",)
        elif "[提示]" in msg:
            tag = ("info",)
        elif msg.startswith("===") or msg.startswith("开始转换") or msg.startswith("VTF 参数"):
            tag = ("head",)
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", f"[{ts}] ", ("ts",))
        self.log_widget.insert("end", msg + "\n", tag)
        self.log_widget.configure(state="disabled")
        self.log_widget.see("end")
        self.log_widget.update_idletasks()

    def load_config(self):
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            for k, v in self.vars.items():
                if isinstance(data.get(k), str):
                    v.set(data[k])
            if isinstance(data.get("resize_enabled"), bool):
                self.resize_enabled.set(data["resize_enabled"])
            if isinstance(data.get("size_enabled"), bool):
                self.size_enabled.set(data["size_enabled"])
            elif isinstance(data.get("resize_enabled"), bool):
                self.size_enabled.set(data["resize_enabled"])
            for key, var in (("resize_width", self.resize_width), ("resize_height", self.resize_height)):
                val = data.get(key)
                if isinstance(val, int) and 128 <= val <= 4096:
                    var.set(val)
            for key, var, allowed in (
                ("vtf_version", self.vtf_version, self.VTF_VERSIONS),
                ("color_format", self.color_format, self.VTF_FORMATS),
                ("alpha_format", self.alpha_format, self.VTF_FORMATS),
                ("resize_method", self.resize_method, self.RESIZE_METHODS),
                ("resize_filter", self.resize_filter, self.RESIZE_FILTERS),
            ):
                val = data.get(key)
                if isinstance(val, str):
                    if val in allowed:
                        var.set(val)
                    elif val.lower() in allowed:
                        var.set(val.lower())
        except (OSError, json.JSONDecodeError):
            pass

    def save_config(self):
        data = {k: v.get() for k, v in self.vars.items()}
        data["size_enabled"] = bool(self.size_enabled.get())
        data["resize_enabled"] = bool(self.resize_enabled.get())
        try:
            data["resize_width"] = int(self.resize_width.get())
            data["resize_height"] = int(self.resize_height.get())
        except (tk.TclError, ValueError):
            pass
        data["vtf_version"] = self.vtf_version.get()
        data["color_format"] = self.color_format.get()
        data["alpha_format"] = self.alpha_format.get()
        data["resize_method"] = self.resize_method.get()
        data["resize_filter"] = self.resize_filter.get()
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def load_vmts(self):
        vmt_dir = Path(self.vars["vmt_dir"].get().strip())
        png_dir = Path(self.vars["png_dir"].get().strip())
        if not vmt_dir.is_dir():
            self.log(f"[错误] VMT 目录不存在: {vmt_dir}")
            return
        if not png_dir.is_dir():
            self.log(f"[警告] PNG 目录不存在: {png_dir}")

        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.items.clear()

        vmts = sorted(vmt_dir.glob("*.vmt"))
        if not vmts:
            self.log("[错误] VMT 目录下没有 .vmt 文件")
            return

        default_w, default_h = self._safe_default_size()

        for idx, vmt in enumerate(vmts):
            try:
                params = parse_vmt(vmt)
            except Exception as e:
                self.log(f"[错误] 解析 {vmt.name} 失败: {e}")
                continue

            slots = {}
            for suffix, param in SUFFIX_TO_PARAM.items():
                slot = "base" if param == "$basetexture" else "normal"
                rel = params.get(param.lower())
                png = png_dir / f"{vmt.stem}{suffix}.png"
                exists = png.is_file()
                size = png_size(png) if exists else None
                enabled = bool(rel) and exists
                if size:
                    tw = max(128, min(4096, size[0]))
                    th = max(128, min(4096, size[1]))
                else:
                    tw, th = default_w, default_h
                slots[slot] = {
                    "enabled": enabled,
                    "checked": enabled,
                    "png": png,
                    "rel": rel,
                    "param": param,
                    "size": size,
                    "target_w": tw,
                    "target_h": th,
                }

            row_tag = "odd" if idx % 2 else "even"
            iid = self.tree.insert("", "end", text=vmt.name, values=(
                self._mark(slots["base"]),
                self._size_info(slots["base"]),
                self._mark(slots["normal"]),
                self._size_info(slots["normal"]),
            ), tags=(row_tag,))
            self.items[iid] = {"vmt": vmt, "params": params, **slots}

        total = len(self.items)
        base_ok = sum(1 for it in self.items.values() if it["base"]["enabled"])
        normal_ok = sum(1 for it in self.items.values() if it["normal"]["enabled"])
        self.log(f"已载入 {total} 个 VMT（可替换 basetexture: {base_ok}，bumpmap: {normal_ok}）")
        self.status_var.set(f"已载入 {total} 个 VMT · basetexture {base_ok} · bumpmap {normal_ok}")

    def _mark(self, slot):
        if not slot["enabled"]:
            return self.CHECK_NA
        return self.CHECK_ON if slot["checked"] else self.CHECK_OFF

    def _size_info(self, slot):
        if not slot["enabled"]:
            if not slot["rel"]:
                return "VMT 未定义"
            return "缺少 PNG"
        src = f"{slot['size'][0]}x{slot['size'][1]}" if slot["size"] else "?"
        tgt = f"{slot['target_w']}x{slot['target_h']}"
        return f"{src} → {tgt}"

    def _safe_default_size(self):
        try:
            w = int(self.resize_width.get())
            h = int(self.resize_height.get())
        except (tk.TclError, ValueError):
            return 1024, 1024
        w = max(128, min(4096, w))
        h = max(128, min(4096, h))
        return w, h

    def apply_default_resize(self):
        if not self.items:
            self.log("[提示] 请先载入 VMT")
            return
        w, h = self._safe_default_size()
        count = 0
        for iid, item in self.items.items():
            for slot in ("base", "normal"):
                s = item[slot]
                if s["enabled"]:
                    s["target_w"] = w
                    s["target_h"] = h
                    self.tree.set(iid, f"{slot}_info", self._size_info(s))
                    count += 1
        self.log(f"已将目标分辨率 {w}x{h} 应用到 {count} 项")

    def on_tree_dblclick(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        iid = self.tree.identify_row(event.y)
        if not iid or iid not in self.items:
            return
        slot = {"#2": "base", "#4": "normal"}.get(col)
        if slot:
            self.edit_target(iid, slot)

    def edit_target(self, iid, slot):
        item = self.items[iid]
        s = item[slot]
        if not s["enabled"]:
            return

        popup = tk.Toplevel(self.root)
        popup.title("设置目标分辨率")
        popup.transient(self.root)
        popup.resizable(False, False)
        popup.grab_set()

        body = ttk.Frame(popup, padding=14)
        body.pack(fill="both", expand=True)

        slot_name = "basetexture" if slot == "base" else "bumpmap"
        src_txt = f"{s['size'][0]}x{s['size'][1]}" if s["size"] else "未知"
        ttk.Label(body, text=item["vmt"].name, font=("Microsoft YaHei UI", 10, "bold"),
                  foreground="#111827").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(body, text=f"{slot_name}  ·  源分辨率 {src_txt}",
                  style="Hint.TLabel").grid(row=1, column=0, columnspan=2, pady=(0, 10), sticky="w")

        w_var = tk.IntVar(value=s["target_w"])
        h_var = tk.IntVar(value=s["target_h"])
        ttk.Label(body, text="宽").grid(row=2, column=0, padx=(0, 6), pady=4, sticky="e")
        ttk.Spinbox(body, from_=128, to=4096, increment=128, width=10, textvariable=w_var).grid(row=2, column=1, pady=4, sticky="w")
        ttk.Label(body, text="高").grid(row=3, column=0, padx=(0, 6), pady=4, sticky="e")
        ttk.Spinbox(body, from_=128, to=4096, increment=128, width=10, textvariable=h_var).grid(row=3, column=1, pady=4, sticky="w")
        ttk.Label(body, text="范围 128 ~ 4096", style="Hint.TLabel").grid(row=4, column=0, columnspan=2, pady=(4, 0))

        msg_var = tk.StringVar()
        ttk.Label(body, textvariable=msg_var, foreground="#b00020").grid(row=5, column=0, columnspan=2, pady=(4, 0))

        def ok():
            try:
                w = int(w_var.get())
                h = int(h_var.get())
            except (tk.TclError, ValueError):
                msg_var.set("请输入整数")
                return
            if not (128 <= w <= 4096 and 128 <= h <= 4096):
                msg_var.set("必须在 128 ~ 4096 之间")
                return
            s["target_w"] = w
            s["target_h"] = h
            self.tree.set(iid, f"{slot}_info", self._size_info(s))
            popup.destroy()

        bf = ttk.Frame(body)
        bf.grid(row=6, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(bf, text="确定", command=ok, style="Accent.TButton").pack(side="left", padx=6)
        ttk.Button(bf, text="取消", command=popup.destroy).pack(side="left", padx=6)

        popup.update_idletasks()
        w = popup.winfo_reqwidth()
        h = popup.winfo_reqheight()
        x = (popup.winfo_screenwidth() - w) // 2
        y = (popup.winfo_screenheight() - h) // 2
        popup.geometry(f"{w}x{h}+{x}+{y}")

    def on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        iid = self.tree.identify_row(event.y)
        if not iid or iid not in self.items:
            return
        slot = {"#1": "base", "#3": "normal"}.get(col)
        if not slot:
            return
        item = self.items[iid]
        if not item[slot]["enabled"]:
            return
        item[slot]["checked"] = not item[slot]["checked"]
        self.tree.set(iid, slot, self._mark(item[slot]))

    def select_all(self, slot, checked):
        for iid, item in self.items.items():
            if item[slot]["enabled"]:
                item[slot]["checked"] = checked
                self.tree.set(iid, slot, self._mark(item[slot]))

    def start_convert(self):
        self.save_config()
        if not self.items:
            self.log("[错误] 请先点击 载入 VMT")
            return
        self.run_btn.state(["disabled"])
        self.status_var.set("转换中…")
        threading.Thread(target=self._convert_safe, daemon=True).start()

    def _convert_safe(self):
        try:
            self.convert()
        except Exception as e:
            self.log(f"[异常] {e}")
            self.status_var.set("转换异常中断")
        finally:
            self.run_btn.state(["!disabled"])

    def convert(self):
        vtfcmd = Path(self.vars["vtfcmd"].get().strip())
        materials_dir = Path(self.vars["materials_dir"].get().strip())
        if not vtfcmd.is_file():
            self.log(f"[错误] VTFCmd.exe 不存在: {vtfcmd}")
            return
        if not materials_dir.is_dir():
            self.log(f"[错误] materials 目录不存在: {materials_dir}")
            return

        size_on = bool(self.size_enabled.get())
        resize_on = bool(self.resize_enabled.get())
        if size_on:
            for item in self.items.values():
                for slot in ("base", "normal"):
                    s = item[slot]
                    if s["enabled"] and s["checked"]:
                        if not (128 <= s["target_w"] <= 4096 and 128 <= s["target_h"] <= 4096):
                            self.log(f"[错误] {item['vmt'].name} {s['param']} 目标分辨率 {s['target_w']}x{s['target_h']} 越界（128~4096）")
                            return
            self.log("分辨率: 启用（每项使用自身目标分辨率）")
        else:
            self.log("分辨率: 关闭（保持 PNG 原始尺寸）")

        queue = []
        for item in self.items.values():
            for slot in ("base", "normal"):
                s = item[slot]
                if s["enabled"] and s["checked"]:
                    queue.append((item["vmt"], s))
        if not queue:
            self.log("[错误] 没有勾选任何要替换的项")
            return

        version = self.vtf_version.get().strip() or "7.2"
        color_fmt = self.color_format.get().strip() or "DXT1"
        alpha_fmt = self.alpha_format.get().strip() or "DXT5"
        r_method = self.resize_method.get().strip().lower() or "nearest"
        r_filter = self.resize_filter.get().strip().lower() or "triangle"
        self.log(f"VTF 参数: 版本={version}, Color={color_fmt} (basetexture), Alpha={alpha_fmt} (bumpmap)")
        if resize_on:
            self.log(f"Resize: method={r_method}, filter={r_filter}")
        else:
            self.log("Resize: 关闭（不附加 -rmethod/-rfilter）")

        self.log(f"开始转换，共 {len(queue)} 项")
        success = fail = 0
        last_vmt = None
        for vmt, s in queue:
            if vmt != last_vmt:
                self.log(f"=== {vmt.name} ===")
                last_vmt = vmt
            param = s["param"]
            fmt = color_fmt if param == "$basetexture" else alpha_fmt
            png = s["png"]
            size = s["size"] or png_size(png)
            src_str = f"{size[0]}x{size[1]}" if size else "未知"
            resize_flags = []
            if size_on:
                tgt_str = f"{s['target_w']}x{s['target_h']}"
                resize_flags += [
                    "-resize",
                    "-rwidth", str(s["target_w"]),
                    "-rheight", str(s["target_h"]),
                ]
            else:
                tgt_str = src_str
            if resize_on:
                if "-resize" not in resize_flags:
                    resize_flags.append("-resize")
                resize_flags += ["-rmethod", r_method, "-rfilter", r_filter]
            self.log(f"  {param}: {png.name} [{src_str} → {tgt_str}] -> {fmt}")

            target = materials_dir / (s["rel"] + ".vtf")
            target.parent.mkdir(parents=True, exist_ok=True)

            generated = png.with_suffix(".vtf")
            if generated.exists():
                try:
                    generated.unlink()
                except OSError:
                    pass

            cmd = [str(vtfcmd), "-file", str(png), "-output", str(png.parent),
                   "-version", version, "-format", fmt] + resize_flags
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            except (OSError, subprocess.TimeoutExpired) as e:
                self.log(f"    [失败] 调用 VTFCmd 出错: {e}")
                fail += 1
                continue

            if proc.returncode != 0 or not generated.exists():
                self.log(f"    [失败] VTFCmd 返回 {proc.returncode}")
                if proc.stderr.strip():
                    self.log(f"    stderr: {proc.stderr.strip()}")
                fail += 1
                continue

            try:
                if target.exists():
                    target.unlink()
                shutil.move(str(generated), str(target))
            except OSError as e:
                self.log(f"    [失败] 移动 VTF 失败: {e}")
                fail += 1
                continue

            self.log(f"    [成功] -> {target}")
            success += 1

        self.log(f"==== 完成：成功 {success}，失败 {fail} ====")
        self.status_var.set(f"转换完成 · 成功 {success} · 失败 {fail}")


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
