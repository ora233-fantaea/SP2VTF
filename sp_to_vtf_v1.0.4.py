"""SP 贴图转 VTF 工具 made by 一个橘色的橙子 — 单文件 PySide6 GUI."""

# ── 标准库 ─────────────────────────────────────────────────────────
import json
import math
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from PIL import Image

# ── PySide6 ────────────────────────────────────────────────────────
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QPoint, QRectF
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor, QPainter, QPen, QPainterPath, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QTextEdit,
    QProgressBar,
    QSplitter,
    QFileDialog,
    QDialog,
    QFrame,
    QStatusBar,
    QSizePolicy,
    QDialogButtonBox,
    QProxyStyle,
    QStyle,
)

# ── 运行时路径（兼容打包为 exe 后定位自身目录） ─────────────────
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "config.json"

# ── SP 贴图后缀 → VMT 参数 偏好匹配（按顺序优先） ─────────────
_PARAM_PREFERRED = [
    ("base", "$basetexture", ("_Base_Color", "_2D_View", "_Color", "_rgb")),
    ("normal", "$bumpmap", ("_Normal_OpenGL", "_Normal_DirectX", "_Normal")),
]

# ── Tooltip 帮助文本（仅用于文档说明） ───────────────────────────
VTF_FORMAT_HELP = {
    "DXT1": "有损压缩 · 无 Alpha · 文件最小",
    "DXT3": "有损压缩 · 锐利 Alpha",
    "DXT5": "有损压缩 · 平滑 Alpha · 法线贴图推荐",
    "RGBA8888": "无损 · 32 位 RGBA · 文件较大",
    "RGB888": "无损 · 24 位 RGB · 无 Alpha",
    "I8": "8 位灰度",
    "A8": "8 位 Alpha 通道",
}
RESIZE_METHOD_HELP = {
    "nearest": "最近邻采样 · 速度最快 · 像素风格",
    "biggest": "等比缩放到可容纳的最大尺寸",
    "smallest": "等比缩放到可容纳的最小尺寸",
}
RESIZE_FILTER_HELP = {
    "point": "点采样",
    "box": "方框滤波",
    "triangle": "三角滤波 · 线性插值",
    "cubic": "三次滤波",
    "catrom": "Catmull-Rom 滤波",
    "mitchell": "Mitchell-Netravali 滤波",
    "gaussian": "高斯滤波",
    "sinc": "Sinc 滤波",
    "bessel": "Bessel 滤波",
    "hanning": "Hanning 滤波",
    "hamming": "Hamming 滤波",
    "blackman": "Blackman 滤波",
    "kaiser": "Kaiser 滤波",
}

# ── 全局 QSS 样式表（Material Design 3 风格） ────────────────────
APP_STYLESHEET = """
/* ── 全局 ───────────────────────────────── */
QMainWindow, QDialog { background: #F5F5F5; }
QWidget { font-family: "Microsoft YaHei UI", "Roboto", "Segoe UI", sans-serif; color: #212121; font-size: 9pt; }
/* ── QGroupBox (Material Card) ──────────── */
QGroupBox {
    background: #FFFFFF; border: none; border-radius: 12px;
    margin-top: 18px; padding: 18px 12px 10px 12px; font-size: 9.5pt;
}
QGroupBox::title {
    subcontrol-origin: margin; subcontrol-position: top left; left: 16px;
    padding: 0 10px; color: #1976D2; font-weight: 500; background: #FFFFFF; border-radius: 4px;
}
/* ── QLabel ─────────────────────────────── */
QLabel#groupLabel { color: #9E9E9E; font-size: 8pt; font-weight: 600; text-transform: uppercase; }
QLabel#hintLabel { color: #9E9E9E; font-size: 8.5pt; }
QLabel#errorLabel { color: #D32F2F; font-size: 8.5pt; }
/* ── QLineEdit ──────────────────────────── */
QLineEdit { border: 1px solid #BDBDBD; border-radius: 8px; padding: 7px 10px; background: #FAFAFA; }
QLineEdit:focus { border: 2px solid #1976D2; padding: 6px 9px; background: #FFFFFF; }
QLineEdit:hover:!focus { border-color: #757575; background: #FFFFFF; }
QLineEdit:disabled { background: #F0F0F0; color: #BDBDBD; }
/* ── QPushButton ────────────────────────── */
QPushButton { border: none; border-radius: 8px; padding: 6px 16px; background: transparent; color: #1976D2; font-weight: 500; }
QPushButton:hover { background: rgba(25,118,210,0.08); }
QPushButton:pressed { background: rgba(25,118,210,0.14); }
QPushButton:disabled { color: #BDBDBD; background: transparent; }
QPushButton#accentButton { background: #1976D2; color: #FFFFFF; border-radius: 20px; padding: 7px 24px; font-weight: 600; font-size: 9.5pt; }
QPushButton#accentButton:hover { background: #1565C0; }
QPushButton#accentButton:pressed { background: #0D47A1; }
QPushButton#accentButton:disabled { background: #E0E0E0; color: #9E9E9E; }
QPushButton#dangerButton { color: #D32F2F; border: 1px solid #EF9A9A; border-radius: 8px; padding: 5px 16px; }
QPushButton#dangerButton:hover { background: rgba(211,47,47,0.06); }
QPushButton#dangerButton:disabled { color: #BDBDBD; border-color: #E0E0E0; background: transparent; }
/* ── QComboBox ──────────────────────────── */
QComboBox { border: 1px solid #BDBDBD; border-radius: 8px; padding: 5px 8px; background: #FAFAFA; min-width: 60px; }
QComboBox:focus { border: 2px solid #1976D2; padding: 4px 7px; background: #FFFFFF; }
QComboBox:hover:!focus { border-color: #757575; background: #FFFFFF; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { border: 1px solid #E0E0E0; border-radius: 8px; background: #FFFFFF; selection-background-color: #E3F2FD; selection-color: #212121; outline: none; padding: 6px 2px; }
/* ── QSpinBox ───────────────────────────── */
QSpinBox { border: 1px solid #BDBDBD; border-radius: 8px; padding: 5px 8px; background: #FAFAFA; }
QSpinBox:focus { border: 2px solid #1976D2; padding: 4px 7px; background: #FFFFFF; }
QSpinBox:hover:!focus { border-color: #757575; background: #FFFFFF; }
QSpinBox:disabled { background: #F0F0F0; color: #BDBDBD; }
QSpinBox::up-button { border: none; border-radius: 0 6px 0 0; width: 20px; background: #F5F5F5; }
QSpinBox::down-button { border: none; border-radius: 0 0 6px 0; width: 20px; background: #F5F5F5; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #E3F2FD; }
/* ── QCheckBox ──────────────────────────── */
QCheckBox { spacing: 8px; color: #212121; padding: 2px 0; }
QCheckBox::indicator { width: 18px; height: 18px; border: 2px solid #757575; border-radius: 2px; background: transparent; }
QCheckBox::indicator:checked { background: #1976D2; border-color: #1976D2; }
QCheckBox::indicator:hover { border-color: #1976D2; }
QCheckBox:disabled { color: #BDBDBD; }
QCheckBox:disabled::indicator { border-color: #E0E0E0; background: #F5F5F5; }
/* ── QTreeWidget ────────────────────────── */
QTreeWidget { border: 1px solid #E0E0E0; border-radius: 10px; background: #FFFFFF; alternate-background-color: #F8F8F8; outline: none; padding: 4px; }
QTreeWidget::item { padding: 5px 6px; min-height: 24px; }
QTreeWidget::item:hover { background: #E3F2FD; }
QTreeWidget::item:selected { background: #BBDEFB; color: #212121; }
QHeaderView::section { background: #FAFAFA; color: #616161; font-weight: 600; border: none; border-bottom: 2px solid #1976D2; padding: 8px 10px; font-size: 8.5pt; }
QTreeWidget::branch { background: transparent; }
/* ── QTextEdit#logEdit ──────────────────── */
QTextEdit#logEdit { border: 1px solid #E0E0E0; border-radius: 10px; background: #FAFAFA; padding: 8px 10px; font-family: "Cascadia Code","Consolas","SF Mono",monospace; font-size: 9pt; color: #37474F; }
/* ── QProgressBar ───────────────────────── */
QProgressBar { border: none; border-radius: 4px; background: #E7E0EC; height: 4px; min-height: 4px; text-align: center; font-size: 7pt; color: transparent; }
QProgressBar::chunk { background: #1976D2; border-radius: 4px; }
/* ── QStatusBar ─────────────────────────── */
QStatusBar { background: #FFFFFF; border-top: 1px solid #E0E0E0; padding: 4px 10px; font-size: 8.5pt; }
QStatusBar QLabel { color: #757575; }
/* ── QSplitter ──────────────────────────── */
QSplitter::handle { background: #E0E0E0; height: 1px; }
QSplitter::handle:hover { background: #1976D2; height: 2px; }
/* ── QScrollBar ─────────────────────────── */
QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: rgba(0,0,0,0.18); border-radius: 4px; min-height: 32px; }
QScrollBar::handle:vertical:hover { background: rgba(0,0,0,0.32); }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 2px; }
QScrollBar::handle:horizontal { background: rgba(0,0,0,0.18); border-radius: 4px; min-width: 32px; }
QScrollBar::handle:horizontal:hover { background: rgba(0,0,0,0.32); }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
/* ── QFrame / QDialogButtonBox ──────────── */
QFrame[frameShape="4"], QFrame[frameShape="5"] { color: #E0E0E0; }
QDialogButtonBox QPushButton { min-width: 76px; }
"""


def parse_vmt(path: Path) -> dict:
    """解析 VMT 文件，提取键值对（键统一小写，值用正斜杠路径）。"""
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    text = re.sub(r"//[^\n]*", "", text)
    result = {}
    for m in re.finditer(
        r'"?(\$[A-Za-z_]\w*)"?\s+(?:"([^"]+)"|([A-Za-z0-9_./\\\-]+))', text
    ):
        key = m.group(1).lower()
        if key not in result:
            val = m.group(2) if m.group(2) is not None else m.group(3)
            result[key] = val.strip().replace("\\", "/")
    return result


def png_size(path: Path):
    """读取 PNG 前 24 字节获取宽高，不是有效 PNG 返回 None。"""
    try:
        with open(path, "rb") as f:
            head = f.read(24)
        if len(head) < 24 or head[:8] != b"\x89PNG\r\n\x1a\n":
            return None
        w, h = struct.unpack(">II", head[16:24])
        return (w, h)
    except OSError:
        return None


def tga_size(path: Path):
    """读取 TGA 头获取宽高，不是有效 TGA 返回 None。"""
    try:
        with open(path, "rb") as f:
            head = f.read(18)
        if len(head) < 18:
            return None
        w = struct.unpack_from("<H", head, 12)[0]
        h = struct.unpack_from("<H", head, 14)[0]
        if not (1 <= w <= 32767 and 1 <= h <= 32767):
            return None
        return (w, h)
    except OSError:
        return None


def image_size(path: Path):
    """根据文件后缀选择对应的尺寸读取函数。"""
    sfx = path.suffix.lower()
    if sfx == ".png":
        return png_size(path)
    if sfx == ".tga":
        return tga_size(path)
    return None


# ── Gamma 2.2 灰度转换 ─────────────────────────────────────────
def _srgb_to_linear(c: float) -> float:
    if c <= 0.04045:
        return c / 12.92
    return math.pow((c + 0.055) / 1.055, 2.4)


def _linear_to_srgb(c: float) -> float:
    if c <= 0.0031308:
        return c * 12.92
    return 1.055 * math.pow(c, 1.0 / 2.4) - 0.055


def _make_gray_gamma(rgb_image: Image.Image) -> Image.Image:
    """sRGB → 线性 → BT.709 亮度 → sRGB，返回灰度通道。"""
    r, g, b = rgb_image.split()

    def _to_linear(channel):
        return channel.point(lambda v: int(_srgb_to_linear(v / 255.0) * 65535))

    def _bt709_to_gray(r_lin, g_lin, b_lin):
        result = Image.new("L", rgb_image.size)
        rp = r_lin.load()
        gp = g_lin.load()
        bp = b_lin.load()
        rp_out = result.load()
        for y in range(result.height):
            for x in range(result.width):
                y_lin = 0.2126 * rp[x, y] + 0.7152 * gp[x, y] + 0.0722 * bp[x, y]
                y_lin /= 65535.0
                rp_out[x, y] = int(max(0, min(255, round(_linear_to_srgb(y_lin) * 255))))
        return result

    r_lin = _to_linear(r)
    g_lin = _to_linear(g)
    b_lin = _to_linear(b)
    return _bt709_to_gray(r_lin, g_lin, b_lin)


# ── 预处理：PNG → TGA（Alpha 通道生成 + 色阶） ─────────────────
def apply_preprocess(png_path: Path, config: dict, temp_dir: Path) -> Path:
    img = Image.open(png_path).convert("RGBA")
    rgb = img.convert("RGB")

    alpha_source = config.get("alpha_source", "gray")
    if alpha_source == "r":
        gray = img.getchannel("R")
    elif alpha_source == "g":
        gray = img.getchannel("G")
    elif alpha_source == "b":
        gray = img.getchannel("B")
    else:  # gray
        gray = _make_gray_gamma(rgb)

    if config.get("levels_enabled"):
        ob = int(config.get("out_black", 0))
        ow = int(config.get("out_white", 255))
        if ob != ow:
            gray = gray.point(lambda v: 0 if v < ob else (255 if v > ow else int((v - ob) / (ow - ob) * 255)))

    result = Image.merge("RGBA", (*rgb.split(), gray))
    tga_path = temp_dir / f"{png_path.stem}.tga"
    result.save(tga_path, format="TGA")
    return tga_path


class _Signals(QObject):
    """跨线程信号桥：工作线程通过 emit 安全推送到 GUI 线程。"""
    finished = Signal()
    progress = Signal(int, int, str)
    log_msg = Signal(str)


class EditTargetDialog(QDialog):
    """双击树项弹出的目标分辨率编辑对话框。"""
    def __init__(self, parent, vmt_name, slot_name, src_size, target_w, target_h):
        super().__init__(parent)
        self.setWindowTitle("设置目标分辨率")
        self.setModal(True)
        self.resize(320, 280)
        self.setMinimumSize(0, 0)
        self._result_w = target_w
        self._result_h = target_h

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)

        title_lbl = QLabel(vmt_name)
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title_lbl.setFont(title_font)
        layout.addWidget(title_lbl)

        src_str = f"{src_size[0]}x{src_size[1]}" if src_size else "未知"
        hint_lbl = QLabel(f"{slot_name}  ·  源分辨率 {src_str}")
        hint_lbl.setObjectName("hintLabel")
        layout.addWidget(hint_lbl)
        layout.addSpacing(8)

        form = QGridLayout()
        w_spin = QSpinBox()
        w_spin.setRange(128, 4096)
        w_spin.setSingleStep(128)
        w_spin.setValue(target_w)
        w_spin.setMinimumWidth(100)
        h_spin = QSpinBox()
        h_spin.setRange(128, 4096)
        h_spin.setSingleStep(128)
        h_spin.setValue(target_h)
        h_spin.setMinimumWidth(100)
        form.addWidget(QLabel("宽"), 0, 0)
        form.addWidget(w_spin, 0, 1)
        form.addWidget(QLabel("高"), 1, 0)
        form.addWidget(h_spin, 1, 1)
        layout.addLayout(form)

        range_hint = QLabel("范围 128 ~ 4096")
        range_hint.setObjectName("hintLabel")
        layout.addWidget(range_hint)

        self._msg = QLabel()
        self._msg.setObjectName("errorLabel")
        layout.addWidget(self._msg)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._w_spin = w_spin
        self._h_spin = h_spin

    def _on_ok(self):
        w = self._w_spin.value()
        h = self._h_spin.value()
        self._result_w = w
        self._result_h = h
        self.accept()

    @property
    def result_size(self):
        return self._result_w, self._result_h





class PreprocessDialog(QDialog):
    """预处理设置弹窗：Alpha 通道生成 + 色阶（Gamma 2.2 灰度）。"""
    ALPHA_SOURCES = [("R 通道", "r"), ("G 通道", "g"), ("B 通道", "b"), ("灰度", "gray")]

    def __init__(self, parent, config_base, config_normal):
        super().__init__(parent)
        self.setWindowTitle("预处理设置 — [base]")
        self.setModal(True)
        self.resize(380, 400)
        self.setMinimumSize(0, 0)

        self._config = {"base": dict(config_base), "normal": dict(config_normal)}
        self._current_slot = "base"
        self._widgets: dict[str, dict] = {}
        self._slot_containers: dict[str, QWidget] = {}
        self._show_initialized = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        # 槽位切换
        slot_row = QHBoxLayout()
        slot_row.setSpacing(4)
        slot_row.addWidget(QLabel("槽位"))
        self._btn_base = QPushButton("[base]")
        self._btn_normal = QPushButton("[normal]")
        self._btn_base.clicked.connect(lambda: self._switch_slot("base"))
        self._btn_normal.clicked.connect(lambda: self._switch_slot("normal"))
        slot_row.addWidget(self._btn_base)
        slot_row.addWidget(self._btn_normal)
        slot_row.addStretch()
        layout.addLayout(slot_row)

        # 每个槽位创建独立容器（parent=self），控件归属容器，避免产生无 parent 的顶层窗口
        for slot in ("base", "normal"):
            container = QWidget(self)
            cl = QVBoxLayout(container)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(6)

            alpha_cb  = QCheckBox("生成 Alpha 通道", container)
            alpha_cb.toggled.connect(lambda c, s=slot: self._on_alpha_toggled(s))
            src_label = QLabel("来源", container)
            src_combo = QComboBox(container)
            for label, val in self.ALPHA_SOURCES:
                src_combo.addItem(label, val)
            levels_cb = QCheckBox("Alpha 色阶", container)
            levels_cb.toggled.connect(lambda c, s=slot: self._on_levels_toggled(s))
            ob_label  = QLabel("输出黑点", container)
            ob_spin   = QSpinBox(container)
            ob_spin.setRange(0, 255)
            ow_label  = QLabel("输出白点", container)
            ow_spin   = QSpinBox(container)
            ow_spin.setRange(0, 255)

            self._widgets[slot] = {
                "alpha_cb": alpha_cb, "src_combo": src_combo, "src_label": src_label,
                "levels_cb": levels_cb, "ob_spin": ob_spin, "ob_label": ob_label,
                "ow_spin": ow_spin, "ow_label": ow_label,
            }

            cl.addWidget(alpha_cb)
            src_sub = QHBoxLayout()
            src_sub.addWidget(src_label)
            src_sub.addWidget(src_combo, 1)
            cl.addLayout(src_sub)
            cl.addWidget(levels_cb)
            levels_grid = QGridLayout()
            levels_grid.addWidget(ob_label, 0, 0)
            levels_grid.addWidget(ob_spin,  0, 1)
            levels_grid.addWidget(ow_label, 1, 0)
            levels_grid.addWidget(ow_spin,  1, 1)
            cl.addLayout(levels_grid)

            if slot == "base":
                hint2 = QLabel("当前默认输出格式为 DXT1 时 Alpha 通道将被丢弃", container)
                hint2.setObjectName("hintLabel")
                cl.addWidget(hint2)

            self._slot_containers[slot] = container
            layout.addWidget(container)
            container.setVisible(slot == "base")  # normal 容器整体隐藏

        hint1 = QLabel("仅作用于 Alpha（灰度 · Gamma 2.2）通道")
        hint1.setObjectName("hintLabel")
        layout.addWidget(hint1)

        hint3 = QLabel("做夜光选择\u201C灰度\u201D，调整夜光强度仅需要调整\u201C输出白点\u201D，建议值：45\u201375")
        hint3.setObjectName("hintLabel")
        layout.addWidget(hint3)

        layout.addStretch()
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._show_initialized:
            self._show_initialized = True
            self._apply_config_values()
            self._sync_slot_ui()

    def _apply_config_values(self):
        for slot in ("base", "normal"):
            cfg = self._config[slot]
            w = self._widgets[slot]
            w["alpha_cb"].blockSignals(True)
            w["alpha_cb"].setChecked(cfg.get("alpha_enabled", False))
            w["alpha_cb"].blockSignals(False)
            src = cfg.get("alpha_source", "gray")
            idx = w["src_combo"].findData(src)
            if idx >= 0:
                w["src_combo"].setCurrentIndex(idx)
            w["levels_cb"].blockSignals(True)
            w["levels_cb"].setChecked(cfg.get("levels_enabled", False))
            w["levels_cb"].blockSignals(False)
            w["ob_spin"].setValue(cfg.get("out_black", 0))
            w["ow_spin"].setValue(cfg.get("out_white", 255))

    def _switch_slot(self, slot):
        self._flush_config(self._current_slot)
        self._current_slot = slot
        for s, c in self._slot_containers.items():
            c.setVisible(s == slot)
        self.setWindowTitle(f"预处理设置 — [{slot}]")
        self._highlight_slot_button()
        self._sync_slot_ui()

    def _highlight_slot_button(self):
        for s, btn in (("base", self._btn_base), ("normal", self._btn_normal)):
            btn.setStyleSheet(
                "QPushButton { background: #1976D2; color: #FFFFFF; border-radius: 6px; padding: 3px 12px; }"
                if s == self._current_slot else
                "QPushButton { background: transparent; color: #757575; border: 1px solid #BDBDBD; border-radius: 6px; padding: 3px 12px; }"
            )

    def _sync_slot_ui(self):
        w = self._widgets[self._current_slot]
        sl = self._current_slot
        w["alpha_cb"].blockSignals(True)
        w["alpha_cb"].setChecked(self._config[sl].get("alpha_enabled", False))
        w["alpha_cb"].blockSignals(False)
        src = self._config[sl].get("alpha_source", "gray")
        idx = w["src_combo"].findData(src)
        if idx >= 0:
            w["src_combo"].setCurrentIndex(idx)
        w["levels_cb"].blockSignals(True)
        w["levels_cb"].setChecked(self._config[sl].get("levels_enabled", False))
        w["levels_cb"].blockSignals(False)
        w["ob_spin"].setValue(self._config[sl].get("out_black", 0))
        w["ow_spin"].setValue(self._config[sl].get("out_white", 255))
        self._on_alpha_toggled(sl)
        self._on_levels_toggled(sl)

    def _flush_config(self, slot):
        w = self._widgets[slot]
        self._config[slot]["alpha_enabled"] = w["alpha_cb"].isChecked()
        self._config[slot]["alpha_source"] = w["src_combo"].currentData()
        self._config[slot]["levels_enabled"] = w["levels_cb"].isChecked()
        self._config[slot]["out_black"] = w["ob_spin"].value()
        self._config[slot]["out_white"] = w["ow_spin"].value()

    def _on_alpha_toggled(self, slot):
        on = self._widgets[slot]["alpha_cb"].isChecked()
        self._widgets[slot]["src_combo"].setEnabled(on)
        self._widgets[slot]["src_label"].setEnabled(on)
        self._widgets[slot]["levels_cb"].setEnabled(on)
        if not on:
            cb = self._widgets[slot]["levels_cb"]
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
        self._on_levels_toggled(slot)

    def _on_levels_toggled(self, slot):
        on = self._widgets[slot]["levels_cb"].isChecked() and self._widgets[slot]["alpha_cb"].isChecked()
        for k in ("ob_spin", "ob_label", "ow_spin", "ow_label"):
            self._widgets[slot][k].setEnabled(on)

    def _on_ok(self):
        self._flush_config(self._current_slot)
        self.accept()

    @property
    def config_base(self):
        return dict(self._config["base"])

    @property
    def config_normal(self):
        return dict(self._config["normal"])


class CompareDialog(QDialog):
    """双目录贴图对比弹窗：解析 VMT 引用关系，按组展示文件变动。"""
    COL_FILE, COL_STATUS, COL_ORIG_SIZE, COL_TARG_SIZE = range(4)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("文件对比 — Original vs Target")
        self.resize(800, 560)
        self.setMinimumSize(600, 400)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        layout.addLayout(self._build_orig_row())
        layout.addLayout(self._build_target_row())

        btn_row = QHBoxLayout()
        self._btn_compare = QPushButton("开始对比")
        self._btn_compare.setFixedWidth(105)
        self._btn_compare.setObjectName("accentButton")
        self._btn_compare.clicked.connect(self._run_compare)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_compare)
        layout.addLayout(btn_row)

        self._status_label = QLabel("")
        self._status_label.setObjectName("hintLabel")
        layout.addWidget(self._status_label)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["文件名", "状态", "Original 大小", "Target 大小"])
        self._tree.setColumnWidth(0, 300)
        self._tree.setColumnWidth(1, 100)
        self._tree.setColumnWidth(2, 120)
        self._tree.setColumnWidth(3, 120)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(False)
        layout.addWidget(self._tree, 1)

    def _build_orig_row(self):
        lay = QHBoxLayout()
        lay.setSpacing(6)
        lay.addWidget(QLabel("Original 目录"))
        self._orig_entry = QLineEdit()
        self._orig_entry.setPlaceholderText("参考贴图目录（基准）")
        lay.addWidget(self._orig_entry, 1)
        btn = QPushButton("浏览…")
        btn.setFixedWidth(60)
        btn.clicked.connect(self._browse_orig)
        lay.addWidget(btn)
        return lay

    def _build_target_row(self):
        lay = QHBoxLayout()
        lay.setSpacing(6)
        lay.addWidget(QLabel("Target   目录"))
        self._target_entry = QLineEdit()
        self._target_entry.setPlaceholderText("待检测贴图目录")
        lay.addWidget(self._target_entry, 1)
        btn = QPushButton("浏览…")
        btn.setFixedWidth(60)
        btn.clicked.connect(self._browse_target)
        lay.addWidget(btn)
        return lay

    def _browse_orig(self):
        path = QFileDialog.getExistingDirectory(self, "选择 Original 目录")
        if path:
            self._orig_entry.setText(path)

    def _browse_target(self):
        path = QFileDialog.getExistingDirectory(self, "选择 Target 目录")
        if path:
            self._target_entry.setText(path)

    def _run_compare(self):
        orig_dir = Path(self._orig_entry.text().strip())
        target_dir = Path(self._target_entry.text().strip())
        if not orig_dir.is_dir():
            self._status_label.setText("Original 目录不存在")
            return
        if not target_dir.is_dir():
            self._status_label.setText("Target 目录不存在")
            return
        if orig_dir.resolve() == target_dir.resolve():
            self._status_label.setText("两个目录相同，无法对比")
            return

        self._tree.clear()
        self._btn_compare.setEnabled(False)
        self._status_label.setText("对比中…")
        QTimer.singleShot(50, lambda: self._compare_work(orig_dir, target_dir))

    _TEXTURE_PARAMS = ["$basetexture", "$bumpmap", "$phongexponenttexture", "$envmapmask"]
    _PARAM_SHORT = {
        "$basetexture": "basetexture",
        "$bumpmap": "bumpmap",
        "$phongexponenttexture": "phong",
        "$envmapmask": "envmask",
    }

    def _collect_files(self, root: Path) -> dict[str, Path]:
        """递归收集目录下所有文件，返回 {相对路径: 绝对路径}。"""
        files = {}
        for f in root.rglob("*"):
            if f.is_file():
                files[str(f.relative_to(root)).replace("\\", "/")] = f
        return files

    def _compare_work(self, orig_dir: Path, target_dir: Path):
        """核心对比逻辑：收集文件 → 逐字节对比 → 解析 VMT 引用 → 分组展示。"""
        orig_files = self._collect_files(orig_dir)
        target_files = self._collect_files(target_dir)

        all_names = sorted(set(orig_files) | set(target_files))
        status_map: dict[str, tuple[str, int | None, int | None]] = {}
        for name in all_names:
            o = orig_files.get(name)
            t = target_files.get(name)
            if o and t:
                o_size = o.stat().st_size
                t_size = t.stat().st_size
                if o_size == t_size and self._files_equal(o, t):
                    status_map[name] = ("未变化", o_size, t_size)
                else:
                    status_map[name] = ("有变动", o_size, t_size)
            elif t:
                status_map[name] = ("仅Target有", None, t.stat().st_size)
            else:
                status_map[name] = ("仅Original有", o.stat().st_size, None)

        # 构建文件名 → 全路径 索引（VMT 引用无法精确匹配时按文件名回退）
        fname_index: dict[str, list[str]] = {}
        for name in all_names:
            stem = Path(name).name.lower()
            if stem not in fname_index:
                fname_index[stem] = []
            fname_index[stem].append(name)

        def resolve_vtf(rel: str) -> str | None:
            vtf_rel = rel + ".vtf"
            if vtf_rel in status_map:
                return vtf_rel
            fname = Path(vtf_rel).name.lower()
            candidates = fname_index.get(fname, [])
            if len(candidates) == 1:
                return candidates[0]
            if len(candidates) > 1:
                suffix = vtf_rel.lower()
                for c in candidates:
                    if c.lower().endswith(suffix):
                        return c
                for c in candidates:
                    if c.lower().endswith(fname):
                        return c
            return None

        all_files = {**orig_files, **target_files}
        vmt_to_vtfs: dict[str, list[tuple[str, str]]] = {}
        vtf_to_vmts: dict[str, list[str]] = {}

        for name in sorted(all_files):
            if not name.lower().endswith(".vmt"):
                continue
            fpath = all_files[name]
            try:
                params = parse_vmt(fpath)
            except Exception:
                continue
            refs: list[tuple[str, str]] = []
            for param_key in self._TEXTURE_PARAMS:
                rel = params.get(param_key)
                if not rel:
                    continue
                target_path = resolve_vtf(rel)
                label = self._PARAM_SHORT.get(param_key, param_key)
                refs.append((label, rel, target_path))
                if target_path:
                    if target_path not in vtf_to_vmts:
                        vtf_to_vmts[target_path] = []
                    vtf_to_vmts[target_path].append(name)
            vmt_to_vtfs[name] = refs

        groups: list[tuple[str, list[tuple[str, str, tuple]]]] = []
        placed: set[str] = set()

        for vmt_name in sorted(vmt_to_vtfs):
            items: list[tuple[str, str, tuple]] = []
            if vmt_name in status_map:
                items.append((vmt_name, "", status_map[vmt_name]))
            placed.add(vmt_name)
            for param_label, vmt_rel, resolved_path in vmt_to_vtfs[vmt_name]:
                if resolved_path is None:
                    items.append((vmt_rel + ".vtf", param_label, ("(未找到)", None, None)))
                    continue
                if resolved_path in placed:
                    continue
                shared_count = len(vtf_to_vmts.get(resolved_path, []))
                if shared_count >= 2:
                    continue
                if resolved_path in status_map:
                    items.append((resolved_path, param_label, status_map[resolved_path]))
                else:
                    items.append((resolved_path, param_label, ("(未找到)", None, None)))
                placed.add(resolved_path)
            if items:
                groups.append((f"VMT: {vmt_name}", items))

        shared_set = {k for k, v in vtf_to_vmts.items() if len(v) >= 2}
        if shared_set:
            shared_items: list[tuple[str, str, tuple]] = []
            for vtf_rel in sorted(shared_set):
                ref_list = ", ".join(vtf_to_vmts[vtf_rel])
                if vtf_rel in status_map:
                    shared_items.append((vtf_rel, f"← {ref_list}", status_map[vtf_rel]))
                else:
                    shared_items.append((vtf_rel, f"← {ref_list}", ("(未找到)", None, None)))
                placed.add(vtf_rel)
            groups.append(("[共用的贴图]", shared_items))

        unplaced = [n for n in all_names if n not in placed]
        if unplaced:
            other_items: list[tuple[str, str, tuple]] = []
            for name in unplaced:
                if name in status_map:
                    other_items.append((name, "", status_map[name]))
            groups.append(("[其他文件]", other_items))

        self._populate_tree(groups)

        same = sum(1 for s in status_map.values() if s[0] == "未变化")
        changed = sum(1 for s in status_map.values() if s[0] == "有变动")
        only_t = sum(1 for s in status_map.values() if s[0] == "仅Target有")
        only_o = sum(1 for s in status_map.values() if s[0] == "仅Original有")
        self._status_label.setText(
            f"总 {len(all_names)} · 未变化 {same} · 有变动 {changed} · "
            f"仅Target {only_t} · 仅Original {only_o}"
        )
        self._btn_compare.setEnabled(True)

    @staticmethod
    def _files_equal(a: Path, b: Path) -> bool:
        """64KB 分块逐字节对比两个文件是否内容一致。"""
        size_a = a.stat().st_size
        size_b = b.stat().st_size
        if size_a != size_b:
            return False
        buf_size = 1 << 16
        with open(a, "rb") as fa, open(b, "rb") as fb:
            while True:
                ba = fa.read(buf_size)
                bb = fb.read(buf_size)
                if ba != bb:
                    return False
                if not ba:
                    return True

    def _populate_tree(self, groups):
        """将分组后的对比结果渲染到树控件。"""
        self._tree.setUpdatesEnabled(False)
        self._tree.setRootIsDecorated(True)
        status_colors = {
            "未变化": QColor("#22c55e"),
            "有变动": QColor("#ef4444"),
            "仅Target有": QColor("#f59e0b"),
            "仅Original有": QColor("#6366f1"),
            "(未找到)": QColor("#9E9E9E"),
        }

        for group_name, items in groups:
            parent = QTreeWidgetItem()
            parent.setText(self.COL_FILE, group_name)
            parent_font = parent.font(0)
            parent_font.setBold(True)
            parent.setFont(0, parent_font)
            self._tree.addTopLevelItem(parent)

            for file_name, param_label, (status, orig_size, targ_size) in items:
                child = QTreeWidgetItem(parent)
                display = f"[{param_label}] {file_name}" if param_label else file_name
                child.setText(self.COL_FILE, display)
                child.setText(self.COL_STATUS, status)
                color = status_colors.get(status, QColor("#212121"))
                child.setForeground(self.COL_STATUS, color)
                child.setText(self.COL_ORIG_SIZE, self._format_size(orig_size))
                child.setText(self.COL_TARG_SIZE, self._format_size(targ_size))
            parent.setExpanded(True)

        self._tree.setUpdatesEnabled(True)

    @staticmethod
    def _format_size(size_bytes):
        if size_bytes is None:
            return "—"
        if size_bytes < 1024:
            return f"{size_bytes} B"
        return f"{size_bytes / 1024:.1f} KiB"


class MainWindow(QMainWindow):
    """主窗口：路径配置 + VMT 列表 + 输出设置 + 转换执行。"""
    FIELDS = [
        ("VTFCmd.exe 路径", "vtfcmd", "file"),
        ("SP PNG 文件夹", "png_dir", "dir"),
        ("VMT 文件夹", "vmt_dir", "dir"),
        ("L4D2 materials 根目录", "materials_dir", "dir"),
    ]
    CHECK_ON = "\u2611"
    CHECK_OFF = "\u2610"
    CHECK_NA = "\u2014"
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

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SP 贴图转 VTF 工具 - made by 一个橘色的橙子")
        self.setFixedSize(1304, 852)

        self.setWindowIcon(QIcon(str(Path(__file__).parent / "tape-x64.png")))

        self._signals = _Signals()
        self._signals.finished.connect(self._on_convert_finished)
        self._signals.progress.connect(self._on_progress)
        self._signals.log_msg.connect(self._log_insert_safe)

        self._entries = {key: QLineEdit() for _, key, _ in self.FIELDS}
        self._indicators: dict[str, QLabel] = {}
        self._items: dict[QTreeWidgetItem, dict] = {}
        self._stop_requested = False
        self._log_entries: list[tuple[str, str, str]] = []
        self._log_filter_on = False
        self._enabled_sizes = True
        self._enabled_resize = True
        self._size_children: list[QWidget] = []
        self._resize_children: list[QWidget] = []
        self._preprocess_config = {
            "base": {"alpha_enabled": False, "alpha_source": "gray", "levels_enabled": False, "out_black": 0, "out_white": 255},
            "normal": {"alpha_enabled": False, "alpha_source": "gray", "levels_enabled": False, "out_black": 0, "out_white": 255},
        }
        self._temp_dir: Path | None = None

        self._build_ui()
        self._load_config()
        self._auto_detect_vtfcmd()
        self._validate_all_paths()

    def _build_ui(self):
        """组装主界面布局：路径组 → 设置组 → 按钮栏 → VMT 列表/日志分屏。"""
        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(12, 12, 12, 12)
        main_lay.setSpacing(8)

        main_lay.addWidget(self._build_paths_group())
        main_lay.addWidget(self._build_settings_group())
        main_lay.addLayout(self._build_button_bar())

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self._build_tree_group())
        splitter.addWidget(self._build_log_group())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        main_lay.addWidget(splitter, 1)

        self._status_label = QLabel("就绪 — 填好路径后点击「载入 VMT」")

        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(280)
        self._progress_bar.setVisible(False)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)

        sb = self.statusBar()
        sb.addWidget(self._status_label, 1)
        sb.addPermanentWidget(self._progress_bar)

        self._update_size_state()
        self._update_resize_state()

    def _build_paths_group(self):
        grp = QGroupBox("路径配置")
        grid = QGridLayout(grp)
        grid.setColumnStretch(1, 1)

        for i, (label, key, kind) in enumerate(self.FIELDS):
            lbl = QLabel(label)
            lbl.setFixedWidth(160)
            grid.addWidget(lbl, i, 0)

            entry = self._entries[key]
            grid.addWidget(entry, i, 1)

            btn = QPushButton("浏览…")
            btn.setFixedWidth(60)
            btn.clicked.connect(lambda checked, k=key, t=kind: self._browse(k, t))
            grid.addWidget(btn, i, 2)

            ind = QLabel("\u2014")
            ind.setFixedWidth(24)
            ind.setAlignment(Qt.AlignCenter)
            ind.setStyleSheet("color: #9E9E9E;")
            grid.addWidget(ind, i, 3)
            self._indicators[key] = ind

        return grp

    def _build_settings_group(self):
        grp = QGroupBox("输出设置")
        vlay = QVBoxLayout(grp)
        vlay.setSpacing(4)

        row_vtf = QHBoxLayout()
        row_vtf.setSpacing(4)
        row_vtf.addWidget(QLabel("VTFCmd"))
        row_vtf.addWidget(QLabel("版本"))
        self._combo_version = QComboBox()
        self._combo_version.addItems(self.VTF_VERSIONS)
        self._combo_version.setCurrentText("7.2")
        self._combo_version.setFixedWidth(70)
        self._combo_version.setToolTip("VTF 文件版本 · L4D2 推荐 7.2")
        row_vtf.addWidget(self._combo_version)

        row_vtf.addWidget(QLabel("Color"))
        self._combo_color = QComboBox()
        self._combo_color.addItems(self.VTF_FORMATS)
        self._combo_color.setCurrentText("DXT1")
        self._combo_color.setFixedWidth(130)
        self._combo_color.setToolTip("basetexture 贴图格式\n常用: DXT1 (无Alpha), DXT5 (有Alpha)")
        row_vtf.addWidget(self._combo_color)
        hint_base = QLabel("(basetexture)")
        hint_base.setObjectName("hintLabel")
        row_vtf.addWidget(hint_base)

        row_vtf.addWidget(QLabel("Alpha"))
        self._combo_alpha = QComboBox()
        self._combo_alpha.addItems(self.VTF_FORMATS)
        self._combo_alpha.setCurrentText("DXT5")
        self._combo_alpha.setFixedWidth(130)
        self._combo_alpha.setToolTip("bumpmap / 法线贴图格式\n常用: DXT5 (推荐), RGBA8888")
        row_vtf.addWidget(self._combo_alpha)
        hint_bump = QLabel("(bumpmap)")
        hint_bump.setObjectName("hintLabel")
        row_vtf.addWidget(hint_bump)

        row_vtf.addStretch()
        vlay.addLayout(row_vtf)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        vlay.addWidget(sep)

        row_resize = QHBoxLayout()
        row_resize.setSpacing(4)
        row_resize.addWidget(QLabel("缩放"))

        self._check_size = QCheckBox("分辨率")
        self._check_size.setChecked(True)
        self._check_size.toggled.connect(self._update_size_state)
        row_resize.addWidget(self._check_size)

        w_lbl = QLabel("宽")
        self._spin_w = QSpinBox()
        self._spin_w.setRange(128, 4096)
        self._spin_w.setSingleStep(128)
        self._spin_w.setValue(1024)
        self._spin_w.setFixedWidth(70)
        h_lbl = QLabel("高")
        self._spin_h = QSpinBox()
        self._spin_h.setRange(128, 4096)
        self._spin_h.setSingleStep(128)
        self._spin_h.setValue(1024)
        self._spin_h.setFixedWidth(70)

        self._size_children = [w_lbl, self._spin_w, h_lbl, self._spin_h]

        row_resize.addWidget(w_lbl)
        row_resize.addWidget(self._spin_w)
        row_resize.addWidget(h_lbl)
        row_resize.addWidget(self._spin_h)

        btn_apply = QPushButton("应用默认")
        btn_apply.setFixedWidth(95)
        btn_apply.clicked.connect(self._apply_default_resize)
        row_resize.addWidget(btn_apply)
        row_resize.addSpacing(8)

        self._check_resize = QCheckBox("Resize")
        self._check_resize.setChecked(True)
        self._check_resize.toggled.connect(self._update_resize_state)
        row_resize.addWidget(self._check_resize)

        m_lbl = QLabel("Method")
        self._combo_method = QComboBox()
        self._combo_method.addItems(self.RESIZE_METHODS)
        self._combo_method.setCurrentText("nearest")
        self._combo_method.setFixedWidth(80)
        self._combo_method.setToolTip("等比缩放方式\nnearest=最近邻 biggest/smallest=等比")

        f_lbl = QLabel("Filter")
        self._combo_filter = QComboBox()
        self._combo_filter.addItems(self.RESIZE_FILTERS)
        self._combo_filter.setCurrentText("triangle")
        self._combo_filter.setFixedWidth(90)
        self._combo_filter.setToolTip("图像滤波算法\ntriangle=线性 catrom/mitchell=高质量")

        self._resize_children = [m_lbl, self._combo_method, f_lbl, self._combo_filter]

        row_resize.addWidget(m_lbl)
        row_resize.addWidget(self._combo_method)
        row_resize.addWidget(f_lbl)
        row_resize.addWidget(self._combo_filter)
        row_resize.addStretch()

        vlay.addLayout(row_resize)
        return grp

    def _build_button_bar(self):
        lay = QHBoxLayout()
        lay.setSpacing(6)

        op_lbl = QLabel("操作")
        op_lbl.setObjectName("groupLabel")
        lay.addWidget(op_lbl)

        btn_load = QPushButton("载入 VMT")
        btn_load.setFixedWidth(100)
        btn_load.clicked.connect(self._load_vmts)
        lay.addWidget(btn_load)

        self._btn_run = QPushButton("开始转换")
        self._btn_run.setObjectName("accentButton")
        self._btn_run.setFixedWidth(105)
        self._btn_run.clicked.connect(self._start_convert)
        lay.addWidget(self._btn_run)

        self._btn_stop = QPushButton("\u25a0 停止")
        self._btn_stop.setObjectName("dangerButton")
        self._btn_stop.setFixedWidth(75)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)
        lay.addWidget(self._btn_stop)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setFrameShadow(QFrame.Sunken)
        lay.addWidget(sep1)

        sel_lbl = QLabel("选择")
        sel_lbl.setObjectName("groupLabel")
        lay.addWidget(sel_lbl)

        for label, slot, checked in [
            ("全选 base", "base", True),
            ("全不选 base", "base", False),
            ("全选 bump", "normal", True),
            ("全不选 bump", "normal", False),
        ]:
            btn = QPushButton(label)
            btn.setFixedWidth(105)
            btn.clicked.connect(lambda c, s=slot, ch=checked: self._select_all(s, ch))
            lay.addWidget(btn)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFrameShadow(QFrame.Sunken)
        lay.addWidget(sep2)

        tool_lbl = QLabel("工具")
        tool_lbl.setObjectName("groupLabel")
        lay.addWidget(tool_lbl)

        btn_save = QPushButton("保存配置")
        btn_save.setFixedWidth(95)
        btn_save.clicked.connect(self._on_save_config)
        lay.addWidget(btn_save)

        btn_clear = QPushButton("清空日志")
        btn_clear.setFixedWidth(95)
        btn_clear.clicked.connect(self._clear_log)
        lay.addWidget(btn_clear)

        btn_preprocess = QPushButton("预处理设置")
        btn_preprocess.setFixedWidth(105)
        btn_preprocess.clicked.connect(self._open_preprocess_dialog)
        lay.addWidget(btn_preprocess)

        btn_compare = QPushButton("对比文件")
        btn_compare.setFixedWidth(95)
        btn_compare.clicked.connect(self._open_compare_dialog)
        lay.addWidget(btn_compare)
        return lay

    def _build_tree_group(self):
        grp = QGroupBox("VMT 列表")
        vlay = QVBoxLayout(grp)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(5)
        self._tree.setHeaderLabels([
            "VMT 文件", "basetexture", "basetexture 源 → 目标", "bumpmap", "bumpmap 源 → 目标",
        ])
        self._tree.setColumnWidth(0, 260)
        self._tree.setColumnWidth(1, 90)
        self._tree.setColumnWidth(2, 230)
        self._tree.setColumnWidth(3, 90)
        self._tree.setColumnWidth(4, 230)
        self._tree.setAlternatingRowColors(True)
        self._tree.setRootIsDecorated(True)
        self._tree.itemClicked.connect(self._on_tree_clicked)
        self._tree.itemDoubleClicked.connect(self._on_tree_dblclick)

        self._col_slot = {
            1: ("base", False),
            2: ("base", True),
            3: ("normal", False),
            4: ("normal", True),
        }

        vlay.addWidget(self._tree)
        return grp

    def _build_log_group(self):
        grp = QGroupBox("运行日志")
        vlay = QVBoxLayout(grp)

        header = QHBoxLayout()
        header.addStretch()
        self._check_filter = QCheckBox("仅显示错误/警告")
        self._check_filter.toggled.connect(self._toggle_log_filter)
        header.addWidget(self._check_filter)
        vlay.addLayout(header)

        self._log_edit = QTextEdit()
        self._log_edit.setObjectName("logEdit")
        self._log_edit.setReadOnly(True)
        self._log_edit.setFont(QFont("Cascadia Code", 9))
        vlay.addWidget(self._log_edit)
        return grp

    # ── 路径验证 ─────────────────────────────────────────────────

    def _validate_all_paths(self):
        for _, key, kind in self.FIELDS:
            self._validate_path(key, kind)

    def _validate_path(self, key, kind):
        """校验单个路径是否存在，更新对应指示器（✓ / ✗ / —）。"""
        ind = self._indicators.get(key)
        if not ind:
            return
        raw = self._entries[key].text().strip()
        if not raw:
            ind.setText("\u2014")
            ind.setStyleSheet("color: #9E9E9E;")
            return
        try:
            valid = Path(raw).is_file() if kind == "file" else Path(raw).is_dir()
        except OSError:
            valid = False
        if valid:
            ind.setText("\u2713")
            ind.setStyleSheet("color: #22c55e;")
        else:
            ind.setText("\u2717")
            ind.setStyleSheet("color: #ef4444;")

    def _auto_detect_vtfcmd(self):
        current = self._entries["vtfcmd"].text().strip()
        if current and Path(current).is_file():
            return
        for candidate in (
            APP_DIR / "VTFCmd.exe",
            APP_DIR / "bin" / "VTFCmd.exe",
            APP_DIR / "tools" / "VTFCmd.exe",
            APP_DIR.parent / "VTFCmd.exe",
        ):
            try:
                if candidate.is_file():
                    self._entries["vtfcmd"].setText(str(candidate))
                    return
            except OSError:
                continue

    # ── 路径浏览 ─────────────────────────────────────────────────

    def _browse(self, key, kind):
        if kind == "file":
            path, _ = QFileDialog.getOpenFileName(self, "选择 VTFCmd.exe", "",
                                                   "可执行文件 (*.exe);;所有文件 (*.*)")
        else:
            path = QFileDialog.getExistingDirectory(self, "选择目录")
        if path:
            self._entries[key].setText(path)
            self._validate_path(key, kind)

    # ── 配置文件读写 ─────────────────────────────────────────────

    def _load_config(self):
        if not CONFIG_FILE.exists():
            return
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            for k, entry in self._entries.items():
                if isinstance(data.get(k), str):
                    entry.setText(data[k])
            if isinstance(data.get("resize_enabled"), bool):
                self._check_resize.setChecked(data["resize_enabled"])
            if isinstance(data.get("size_enabled"), bool):
                self._check_size.setChecked(data["size_enabled"])
            elif isinstance(data.get("resize_enabled"), bool):
                self._check_size.setChecked(data["resize_enabled"])
            for key, spin in (("resize_width", self._spin_w), ("resize_height", self._spin_h)):
                val = data.get(key)
                if isinstance(val, int) and 128 <= val <= 4096:
                    spin.setValue(val)
            for key, combo, allowed in (
                ("vtf_version", self._combo_version, self.VTF_VERSIONS),
                ("color_format", self._combo_color, self.VTF_FORMATS),
                ("alpha_format", self._combo_alpha, self.VTF_FORMATS),
                ("resize_method", self._combo_method, self.RESIZE_METHODS),
                ("resize_filter", self._combo_filter, self.RESIZE_FILTERS),
            ):
                val = data.get(key)
                if isinstance(val, str):
                    if val in allowed:
                        combo.setCurrentText(val)
                    elif val.lower() in allowed:
                        combo.setCurrentText(val.lower())
            for slot in ("base", "normal"):
                pp = data.get(f"preprocess_{slot}")
                if isinstance(pp, dict):
                    cfg = self._preprocess_config[slot]
                    if isinstance(pp.get("alpha_enabled"), bool):
                        cfg["alpha_enabled"] = pp["alpha_enabled"]
                    if isinstance(pp.get("alpha_source"), str):
                        cfg["alpha_source"] = pp["alpha_source"]
                    if isinstance(pp.get("levels_enabled"), bool):
                        cfg["levels_enabled"] = pp["levels_enabled"]
                    if isinstance(pp.get("out_black"), int):
                        cfg["out_black"] = pp["out_black"]
                    if isinstance(pp.get("out_white"), int):
                        cfg["out_white"] = pp["out_white"]
        except (OSError, json.JSONDecodeError):
            pass

    def _on_save_config(self):
        self._save_config()
        self._log("配置已保存")

    def _save_config(self):
        data = {k: entry.text() for k, entry in self._entries.items()}
        data["size_enabled"] = self._check_size.isChecked()
        data["resize_enabled"] = self._check_resize.isChecked()
        data["resize_width"] = self._spin_w.value()
        data["resize_height"] = self._spin_h.value()
        data["vtf_version"] = self._combo_version.currentText()
        data["color_format"] = self._combo_color.currentText()
        data["alpha_format"] = self._combo_alpha.currentText()
        data["resize_method"] = self._combo_method.currentText()
        data["resize_filter"] = self._combo_filter.currentText()
        data["preprocess_base"] = self._preprocess_config["base"]
        data["preprocess_normal"] = self._preprocess_config["normal"]
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _update_size_state(self):
        on = self._check_size.isChecked()
        self._enabled_sizes = on
        for w in self._size_children:
            w.setEnabled(on)

    def _update_resize_state(self):
        on = self._check_resize.isChecked()
        self._enabled_resize = on
        for w in self._resize_children:
            w.setEnabled(on)

    # ── VMT 加载与匹配 ───────────────────────────────────────────

    def _load_vmts(self):
        """扫描 VMT 目录，匹配 SP PNG/TGA，填充左侧树列表。"""
        vmt_dir = Path(self._entries["vmt_dir"].text().strip())
        png_dir = Path(self._entries["png_dir"].text().strip())
        if not vmt_dir.is_dir():
            self._log(f"[错误] VMT 目录不存在: {vmt_dir}")
            return
        png_dir_ok = png_dir.is_dir()
        if not png_dir_ok:
            self._log(f"[警告] PNG 目录不存在: {png_dir}")

        self._tree.clear()
        self._items.clear()

        vmts = sorted(vmt_dir.glob("*.vmt"))
        if not vmts:
            self._log("[错误] VMT 目录下没有 .vmt 文件")
            return

        default_w, default_h = self._safe_default_size()

        png_by_name: dict[str, Path] = {}
        if png_dir_ok:
            for f in png_dir.iterdir():
                sfx = f.suffix.lower()
                if sfx in (".png", ".tga"):
                    png_by_name[f.name.lower()] = f

        png_stems = [(name_l.rsplit(".", 1)[0].lower(), path) for name_l, path in png_by_name.items()]

        def fuzzy_match(vmt_path: str) -> Path | None:
            vmt_base = Path(vmt_path).stem.lower()
            for name_l, png_path in png_by_name.items():
                stem_l = name_l.rsplit(".", 1)[0]
                if stem_l == vmt_base:
                    return png_path
                if stem_l.startswith(vmt_base) or vmt_base.startswith(stem_l):
                    return png_path
            return None

        for idx, vmt in enumerate(vmts):
            try:
                params = parse_vmt(vmt)
            except Exception as e:
                self._log(f"[错误] 解析 {vmt.name} 失败: {e}")
                continue

            slots = {}
            sp_prefixes = self._sp_prefixes(vmt, params)

            candidates: dict[str, Path] = {}
            pfx_lower_set = {p.lower() for p in sp_prefixes}
            for stem_l, png_path in png_stems:
                for pfx in pfx_lower_set:
                    if stem_l.startswith(pfx + "_"):
                        suffix = stem_l[len(pfx):]
                        if suffix not in candidates:
                            candidates[suffix] = png_path

            assigned_suffixes: set[str] = set()

            for slot, param, preferred in _PARAM_PREFERRED:
                rel = params.get(param.lower())
                png = None
                matched_suffix = None

                for sfx in preferred:
                    key = sfx.lower()
                    if key in candidates and key not in assigned_suffixes:
                        png = candidates[key]
                        assigned_suffixes.add(key)
                        matched_suffix = sfx
                        break

                if png is None:
                    for suffix, png_path in candidates.items():
                        if suffix not in assigned_suffixes:
                            png = png_path
                            assigned_suffixes.add(suffix)
                            matched_suffix = suffix.lstrip("_")
                            break

                if png is None and rel:
                    png = fuzzy_match(rel)

                exists = png is not None and png.is_file()
                size = image_size(png) if exists else None
                enabled = bool(rel) and exists
                if size:
                    tw = max(128, min(4096, size[0]))
                    th = max(128, min(4096, size[1]))
                else:
                    tw, th = default_w, default_h
                slots[slot] = {
                    "enabled": enabled,
                    "checked": enabled,
                    "png": png if exists else png_dir / f"{vmt.stem}.png",
                    "rel": rel,
                    "param": param,
                    "size": size,
                    "target_w": tw,
                    "target_h": th,
                    "suffix": matched_suffix,
                }

            item = QTreeWidgetItem()
            item.setText(0, vmt.name)
            item.setText(1, self._mark(slots["base"]))
            item.setText(2, self._size_info(slots["base"]))
            item.setText(3, self._mark(slots["normal"]))
            item.setText(4, self._size_info(slots["normal"]))
            self._tree.addTopLevelItem(item)

            self._items[item] = {"vmt": vmt, "params": params, **slots}

            if png_by_name:
                matched_pngs = []
                pfx_lower = {p.lower() for p in sp_prefixes}
                for stem_l, png_path in png_stems:
                    for p in pfx_lower:
                        if stem_l.startswith(p + "_"):
                            matched_pngs.append(png_path)
                            break
                matched_pngs = sorted(set(matched_pngs), key=lambda p: p.name)
                for png in matched_pngs:
                    child = QTreeWidgetItem(item)
                    child.setText(0, f"  {png.name}")
                    for col in range(5):
                        child.setForeground(col, QColor("#9E9E9E"))
                if matched_pngs:
                    item.setExpanded(True)

        total = len(self._items)
        base_ok = sum(1 for it in self._items.values() if it["base"]["enabled"])
        normal_ok = sum(1 for it in self._items.values() if it["normal"]["enabled"])
        self._log(f"已载入 {total} 个 VMT（可替换 basetexture: {base_ok}，bumpmap: {normal_ok}）")
        self._status_label.setText(f"已载入 {total} 个 VMT · basetexture {base_ok} · bumpmap {normal_ok}")

    VMT_STRIP_SUFFIXES = ("_s", "_d", "_n", "_2D_View")

    def _sp_prefixes(self, vmt: Path, params: dict) -> set[str]:
        """从 VMT 文件名和参数值提取可能的前缀（用于匹配 SP PNG 命名变体）。"""
        prefixes = {vmt.stem}
        for param_key in ("$basetexture", "$bumpmap"):
            rel = params.get(param_key)
            if rel:
                name = Path(rel.replace("\\", "/")).stem
                prefixes.add(name)
                while True:
                    for sfx in self.VMT_STRIP_SUFFIXES:
                        if name.endswith(sfx):
                            name = name[:-len(sfx)]
                            prefixes.add(name)
                            break
                    else:
                        break
        return prefixes

    # ── 树列表交互 ───────────────────────────────────────────────

    def _mark(self, slot):
        if not slot["enabled"]:
            return self.CHECK_NA
        return self.CHECK_ON if slot["checked"] else self.CHECK_OFF

    def _size_info(self, slot):
        if not slot["enabled"]:
            if not slot["rel"]:
                return "VMT 未定义"
            return "缺少 PNG"
        sfx = (slot.get("suffix") or "").lstrip("_")
        src = f"{slot['size'][0]}x{slot['size'][1]}" if slot["size"] else "?"
        tgt = f"{slot['target_w']}x{slot['target_h']}"
        label = f"{sfx} " if sfx else ""
        return f"{label}{src} \u2192 {tgt}"

    def _safe_default_size(self):
        w = self._spin_w.value()
        h = self._spin_h.value()
        w = max(128, min(4096, w))
        h = max(128, min(4096, h))
        return w, h

    def _apply_default_resize(self):
        if not self._items:
            self._log("[提示] 请先载入 VMT")
            return
        w, h = self._safe_default_size()
        count = 0
        for item, data in self._items.items():
            for slot in ("base", "normal"):
                s = data[slot]
                if s["enabled"]:
                    s["target_w"] = w
                    s["target_h"] = h
                    col = 2 if slot == "base" else 4
                    item.setText(col, self._size_info(s))
                    count += 1
        self._log(f"已将目标分辨率 {w}x{h} 应用到 {count} 项")

    def _on_tree_clicked(self, item, column):
        if item not in self._items:
            return
        mapping = self._col_slot.get(column)
        if not mapping:
            return
        slot, is_info = mapping
        if is_info:
            return
        data = self._items[item]
        if not data[slot]["enabled"]:
            return
        data[slot]["checked"] = not data[slot]["checked"]
        item.setText(column, self._mark(data[slot]))

    def _on_tree_dblclick(self, item, column):
        if item not in self._items:
            return
        mapping = self._col_slot.get(column)
        if not mapping:
            return
        slot, is_info = mapping
        if not is_info:
            return
        data = self._items[item]
        s = data[slot]
        if not s["enabled"]:
            return

        slot_name = "basetexture" if slot == "base" else "bumpmap"
        dlg = EditTargetDialog(self, data["vmt"].name, slot_name, s["size"],
                               s["target_w"], s["target_h"])
        if dlg.exec() == QDialog.Accepted:
            w, h = dlg.result_size
            s["target_w"] = w
            s["target_h"] = h
            item.setText(column, self._size_info(s))

    def _select_all(self, slot, checked):
        for item, data in self._items.items():
            if data[slot]["enabled"]:
                data[slot]["checked"] = checked
                col = 1 if slot == "base" else 3
                item.setText(col, self._mark(data[slot]))

    # ── 转换流程（运行在工作线程） ───────────────────────────────

    def _on_convert_started(self):
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(True)
        self._status_label.setText("转换中…")

    def _on_convert_finished(self):
        self._progress_bar.setVisible(False)
        self._btn_run.setEnabled(True)
        self._btn_stop.setEnabled(False)

    def _on_progress(self, current, total, status_text):
        if self._progress_bar.maximum() != total:
            self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)
        if status_text:
            self._status_label.setText(status_text)

    def _start_convert(self):
        self._save_config()
        if not self._items:
            self._log("[错误] 请先点击 载入 VMT")
            return
        self._stop_requested = False
        self._btn_run.setEnabled(False)
        self._btn_stop.setEnabled(True)
        threading.Thread(target=self._convert_safe, daemon=True).start()

    def _on_stop(self):
        self._stop_requested = True

    def _convert_safe(self):
        """线程入口：捕获异常并通过信号通知主线程。"""
        QTimer.singleShot(0, self._on_convert_started)
        try:
            self._convert()
        except Exception as e:
            self._signals.log_msg.emit(f"[异常] {e}")
        finally:
            self._signals.finished.emit()

    def _convert(self):
        """核心转换：遍历队列 → VTFCmd 转换 → 复制到 materials 目标路径。"""
        vtfcmd = Path(self._entries["vtfcmd"].text().strip())
        materials_dir = Path(self._entries["materials_dir"].text().strip())
        if not vtfcmd.is_file():
            self._signals.log_msg.emit(f"[错误] VTFCmd.exe 不存在: {vtfcmd}")
            return
        if not materials_dir.is_dir():
            self._signals.log_msg.emit(f"[错误] materials 目录不存在: {materials_dir}")
            return

        # 创建预处理临时目录
        temp_dir = None
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="sp2vtf_"))
            self._temp_dir = temp_dir

            size_on = self._check_size.isChecked()
            resize_on = self._check_resize.isChecked()
            if size_on:
                for data in self._items.values():
                    for slot in ("base", "normal"):
                        s = data[slot]
                        if s["enabled"] and s["checked"]:
                            if not (128 <= s["target_w"] <= 4096 and 128 <= s["target_h"] <= 4096):
                                self._signals.log_msg.emit(
                                    f"[错误] {data['vmt'].name} {s['param']} "
                                    f"目标分辨率 {s['target_w']}x{s['target_h']} 越界（128~4096）")
                                return
                self._signals.log_msg.emit("分辨率: 启用（每项使用自身目标分辨率）")
            else:
                self._signals.log_msg.emit("分辨率: 关闭（保持原始尺寸）")

            queue = []
            for data in self._items.values():
                for slot in ("base", "normal"):
                    s = data[slot]
                    if s["enabled"] and s["checked"]:
                        queue.append((data["vmt"], s, slot))
            if not queue:
                self._signals.log_msg.emit("[错误] 没有勾选任何要替换的项")
                return

            version = self._combo_version.currentText().strip() or "7.2"
            color_fmt = self._combo_color.currentText().strip() or "DXT1"
            alpha_fmt = self._combo_alpha.currentText().strip() or "DXT5"
            r_method = self._combo_method.currentText().strip().lower() or "nearest"
            r_filter = self._combo_filter.currentText().strip().lower() or "triangle"
            self._signals.log_msg.emit(
                f"VTF 参数: 版本={version}, Color={color_fmt} (basetexture), Alpha={alpha_fmt} (bumpmap)")
            if resize_on:
                self._signals.log_msg.emit(f"Resize: method={r_method}, filter={r_filter}")
            else:
                self._signals.log_msg.emit("Resize: 关闭（不附加 -rmethod/-rfilter）")

            total = len(queue)
            self._signals.log_msg.emit(f"开始转换，共 {total} 项")
            success = fail = 0
            last_vmt = None
            for i, (vmt, s, slot_name) in enumerate(queue):
                if self._stop_requested:
                    self._signals.log_msg.emit("[提示] 用户中止转换")
                    break
                self._signals.progress.emit(i + 1, total, f"转换中… {i + 1}/{total}")
                if vmt != last_vmt:
                    self._signals.log_msg.emit(f"=== {vmt.name} ===")
                    last_vmt = vmt
                param = s["param"]
                fmt = color_fmt if param == "$basetexture" else alpha_fmt
                png = s["png"]
                size = s["size"] or image_size(png)
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

                # 预处理
                pp_config = self._preprocess_config[slot_name]
                source = png
                if pp_config.get("alpha_enabled"):
                    try:
                        source = apply_preprocess(png, pp_config, temp_dir)
                        self._signals.log_msg.emit(f"    预处理: Alpha ({pp_config['alpha_source']}) → {source.name}")
                    except Exception as e:
                        self._signals.log_msg.emit(f"    [失败] 预处理出错: {e}")
                        fail += 1
                        continue

                self._signals.log_msg.emit(
                    f"  {param}: {png.name} [{src_str} \u2192 {tgt_str}] -> {fmt}")

                target = materials_dir / (s["rel"] + ".vtf")
                target.parent.mkdir(parents=True, exist_ok=True)

                generated = source.with_suffix(".vtf")
                same_location = generated.resolve() == target.resolve()

                if generated.exists() and not same_location:
                    try:
                        generated.unlink()
                    except OSError:
                        pass

                cmd = [str(vtfcmd), "-file", str(source), "-output", str(source.parent),
                       "-version", version, "-format", fmt] + resize_flags
                try:
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                except (OSError, subprocess.TimeoutExpired) as e:
                    self._signals.log_msg.emit(f"    [失败] 调用 VTFCmd 出错: {e}")
                    self._cleanup_generated(generated)
                    fail += 1
                    continue

                if proc.returncode != 0 or not generated.exists():
                    self._signals.log_msg.emit(f"    [失败] VTFCmd 返回 {proc.returncode}")
                    if proc.stderr.strip():
                        self._signals.log_msg.emit(f"    stderr: {proc.stderr.strip()}")
                    self._cleanup_generated(generated)
                    fail += 1
                    continue

                if not same_location:
                    try:
                        # 先拷贝到目标目录（避免跨盘 move 失败导致旧文件已被删除）
                        tmp = target.with_suffix(target.suffix + ".tmp")
                        shutil.copy2(str(generated), str(tmp))
                        # 目标目录内的重命名是同盘的原子操作
                        tmp.replace(target)
                        self._cleanup_generated(generated)
                    except OSError as e:
                        self._signals.log_msg.emit(f"    [失败] 移动 VTF 失败: {e}")
                        self._cleanup_generated(generated)
                        self._cleanup_generated(tmp)
                        fail += 1
                        continue

                self._signals.log_msg.emit(f"    [成功] -> {target}")
                success += 1

            self._signals.log_msg.emit(f"==== 完成：成功 {success}，失败 {fail} ====")
            self._signals.progress.emit(success + fail, success + fail,
                                        f"转换完成 · 成功 {success} · 失败 {fail}")

        finally:
            if temp_dir is not None:
                try:
                    shutil.rmtree(temp_dir)
                except OSError:
                    pass
            self._temp_dir = None

    @staticmethod
    def _cleanup_generated(path: Path):
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass

    # ── 日志系统 ─────────────────────────────────────────────────

    def _log(self, msg: str):
        """通过信号安全地将日志推送到 GUI 线程。"""
        self._signals.log_msg.emit(msg)

    def _log_insert_safe(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        tag = "info"
        is_err = False
        if any(k in msg for k in ("[错误]", "[异常]", "[失败]")):
            tag = "error"
            is_err = True
        elif "[警告]" in msg:
            tag = "warn"
            is_err = True
        elif "[成功]" in msg or msg.startswith("====") or msg.startswith("==== 完成"):
            tag = "ok"
        elif "[提示]" in msg:
            tag = "info"
        elif msg.startswith("===") or msg.startswith("开始转换") or msg.startswith("VTF 参数"):
            tag = "head"

        self._log_entries.append((ts, msg, tag))
        if self._log_filter_on and not is_err:
            return
        self._log_append(ts, msg, tag)

    def _log_append(self, ts, msg, tag):
        cursor = self._log_edit.textCursor()
        cursor.movePosition(QTextCursor.End)

        ts_fmt = QTextCharFormat()
        ts_fmt.setForeground(QColor("#9E9E9E"))
        cursor.insertText(f"[{ts}] ", ts_fmt)

        msg_fmt = QTextCharFormat()
        if tag == "error":
            msg_fmt.setForeground(QColor("#ef4444"))
            msg_fmt.setFontWeight(QFont.Bold)
        elif tag == "warn":
            msg_fmt.setForeground(QColor("#f59e0b"))
        elif tag == "ok":
            msg_fmt.setForeground(QColor("#22c55e"))
        elif tag == "info":
            msg_fmt.setForeground(QColor("#5b6def"))
        elif tag == "head":
            msg_fmt.setForeground(QColor("#1e293b"))
            msg_fmt.setFontWeight(QFont.Bold)

        cursor.insertText(msg + "\n", msg_fmt)
        self._log_edit.setTextCursor(cursor)
        self._log_edit.ensureCursorVisible()

    def _toggle_log_filter(self):
        self._log_filter_on = self._check_filter.isChecked()
        self._log_edit.clear()
        for ts, msg, tag in self._log_entries:
            is_err = tag in ("error", "warn")
            if self._log_filter_on and not is_err:
                continue
            self._log_append(ts, msg, tag)

    def _open_preprocess_dialog(self):
        dlg = PreprocessDialog(self, self._preprocess_config["base"], self._preprocess_config["normal"])
        if dlg.exec() == QDialog.Accepted:
            self._preprocess_config["base"] = dlg.config_base
            self._preprocess_config["normal"] = dlg.config_normal
            self._log("预处理配置已更新")

    def _open_compare_dialog(self):
        dlg = CompareDialog(self)
        dlg.exec()

    def _clear_log(self):
        self._log_entries.clear()
        self._log_edit.clear()


class ArrowStyle(QProxyStyle):
    """自定义绘制 ComboBox 下箭头和 SpinBox 上下箭头（Fusion 样式下生效）。"""
    _COMBO_PATH = QPainterPath()
    _COMBO_PATH.moveTo(-4, -1.6)
    _COMBO_PATH.lineTo(0, 2.4)
    _COMBO_PATH.lineTo(4, -1.6)

    _SPIN_UP_PATH = QPainterPath()
    _SPIN_UP_PATH.moveTo(0, -2.1)
    _SPIN_UP_PATH.lineTo(-2.4, 1.5)
    _SPIN_UP_PATH.lineTo(2.4, 1.5)
    _SPIN_UP_PATH.closeSubpath()

    _SPIN_DOWN_PATH = QPainterPath()
    _SPIN_DOWN_PATH.moveTo(0, 2.1)
    _SPIN_DOWN_PATH.lineTo(-2.4, -1.5)
    _SPIN_DOWN_PATH.lineTo(2.4, -1.5)
    _SPIN_DOWN_PATH.closeSubpath()

    def drawComplexControl(self, control, option, painter, widget=None):
        super().drawComplexControl(control, option, painter, widget)
        if control == QStyle.CC_ComboBox:
            self._draw_combo_arrow(option, painter, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        if element in (QStyle.PE_IndicatorArrowUp, QStyle.PE_IndicatorArrowDown):
            self._draw_spin_arrow(element, option, painter, widget)
        else:
            super().drawPrimitive(element, option, painter, widget)

    def subControlRect(self, control, option, subControl, widget=None):
        rect = super().subControlRect(control, option, subControl, widget)
        if control == QStyle.CC_ComboBox and subControl == QStyle.SC_ComboBoxArrow:
            rect.adjust(-2, 0, 0, 0)
        return rect

    def _draw_combo_arrow(self, option, painter, widget):
        rect = self.subControlRect(QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxArrow, widget)
        if rect.isEmpty():
            return
        color = QColor("#9E9E9E") if option.state & QStyle.State_Enabled else QColor("#E0E0E0")
        painter.save()
        painter.translate(rect.center())
        painter.setPen(QPen(color, 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPath(self._COMBO_PATH)
        painter.restore()

    def _draw_spin_arrow(self, element, option, painter, widget):
        rect = option.rect
        if rect.isEmpty():
            return
        color = QColor("#9E9E9E") if option.state & QStyle.State_Enabled else QColor("#E0E0E0")
        path = self._SPIN_UP_PATH if element == QStyle.PE_IndicatorArrowUp else self._SPIN_DOWN_PATH
        painter.save()
        painter.translate(rect.center())
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawPath(path)
        painter.restore()


def main():
    """应用入口：设置主题 → 应用 QSS → 启动主窗口。"""
    app = QApplication(sys.argv)
    font = QFont("Microsoft YaHei UI", 9)
    app.setFont(font)
    app.setStyle(ArrowStyle("Fusion"))
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
