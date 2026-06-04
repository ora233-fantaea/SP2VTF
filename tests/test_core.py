"""核心工具函数单元测试

覆盖: VMT 解析、PNG/TGA 尺寸读取、图片尺寸路由、灰度转换

运行方式:
    cd 项目根目录
    python -m pytest tests/test_core.py -v
    # 或
    python tests/test_core.py
"""

import os
import sys
import struct
import tempfile
from pathlib import Path

# 确保项目根目录在 sys.path 中，以便导入主模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── 在导入前设置环境变量防止 Qt 初始化 ──────────────
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

# ── 动态导入主模块（文件名含点号，无法直接 import） ─────
import importlib.util as _iu  # noqa: E402
_sp = _iu.spec_from_file_location("sp_core_mod", str(PROJECT_ROOT / "sp_to_vtf_v1.0.4.py"))
_sp_mod = _iu.module_from_spec(_sp)
_sp_mod.__name__ = "sp_core_mod"
if "sp_core_mod" not in sys.modules:
    sys.modules["sp_core_mod"] = _sp_mod
    _sp.loader.exec_module(_sp_mod)

# 从动态加载的模块中提取纯函数
parse_vmt = _sp_mod.parse_vmt
png_size = _sp_mod.png_size
tga_size = _sp_mod.tga_size
image_size = _sp_mod.image_size
_make_gray_gamma = _sp_mod._make_gray_gamma


# ══════════════════════════════════════════════════════════
# 测试辅助：创建临时图片/二进制文件
# ══════════════════════════════════════════════════════════

def _make_png(width=64, height=64, color=(128, 64, 200), tmpdir=None):
    """创建一个指定尺寸的临时 PNG 文件。"""
    img = Image.new("RGB", (width, height), color)
    path = Path(tmpdir or tempfile.mkdtemp()) / "test.png"
    img.save(path)
    return path


def _make_tga(width=32, height=32, tmpdir=None):
    """创建一个最小有效 TGA 文件（未压缩 RGB）。"""
    path = Path(tmpdir or tempfile.mkdtemp()) / "test.tga"
    with open(path, "wb") as f:
        # TGA header (18 bytes)
        f.write(b"\x00")          # ID length
        f.write(b"\x00")          # Color map type = none
        f.write(b"\x02")          # Image type = uncompressed true-color
        f.write(b"\x00\x00")      # Color map spec (5 bytes)
        f.write(b"\x00\x00")
        f.write(b"\x00")
        # X/Y origin (4 bytes)
        f.write(struct.pack("<HH", 0, 0))
        # Width/Height (4 bytes)
        f.write(struct.pack("<HH", width, height))
        f.write(b"\x18")           # Pixel depth = 24bit
        f.write(b"\x20")           # Descriptor: top-left origin
        # Pixel data (RGB)
        pixel_data = bytes([color % 256 for color in range(3)] * (width * height))
        f.write(pixel_data)
    return path


def _write_text_file(path, content):
    """写入文本文件。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ══════════════════════════════════════════════════════════
# VMT 解析测试
# ══════════════════════════════════════════════════════════

class TestParseVMT:
    """parse_vmt() 函数测试"""

    def test_basic_kv(self, tmp_path):
        """基础键值对提取"""
        _write_text_file(tmp_path / "test.vmt", '''
"VertexlitGeneric"
{
    "$basetexture" "models/weapons/v_rif/AK47_Base_Color"
    "$bumpmap" "models/weapons/vrif/AK47_Normal_OpenGL"
}
''')
        result = parse_vmt(tmp_path / "test.vmt")
        assert "$basetexture" in result
        assert "$bumpmap" in result
        assert result["$basetexture"] == "models/weapons/v_rif/AK47_Base_Color"
        assert result["$bumpmap"] == "models/weapons/vrif/AK47_Normal_OpenGL"

    def test_backslash_normalized_to_forward_slash(self, tmp_path):
        """反斜杠路径应规范化为正斜杠"""
        _write_text_file(tmp_path / "slash.vmt", '''
"VertexlitGeneric"
{
    "$basetexture" "models\\test\\texture"
}
''')
        result = parse_vmt(tmp_path / "slash.vmt")
        assert result["$basetexture"] == "models/test/texture"

    def test_comments_stripped(self, tmp_path):
        """行内 // 注释不应影响解析"""
        _write_text_file(tmp_path / "comment.vmt", '''
"VertexlitGeneric"
{
    "$basetexture" "models/abc"  // 这是注释
    "$bumpmap"   "models/normal" // 另一个注释
}
''')
        result = parse_vmt(tmp_path / "comment.vmt")
        assert result["$basetexture"] == "models/abc"
        assert result["$bumpmap"] == "models/normal"

    def test_duplicate_key_first_wins(self, tmp_path):
        """重复的键只保留第一个值"""
        _write_text_file(tmp_path / "dup.vmt", '''
"VertexlitGeneric"
{
    "$basetexture" "first_value"
    "$basetexture" "second_value"
}
''')
        result = parse_vmt(tmp_path / "dup.vmt")
        assert result["$basetexture"] == "first_value"

    def test_keys_lowercased(self, tmp_path):
        """键统一转小写"""
        _write_text_file(tmp_path / "case.vmt", '''
"VertexlitGeneric"
{
    "$BaseTexture" "models/tex"
    "$BumpMap" "models/nrm"
}
''')
        result = parse_vmt(tmp_path / "case.vmt")
        assert "$basetexture" in result
        assert "$bumpmap" in result

    def test_empty_vmt_returns_empty_dict(self, tmp_path):
        """空 VMT 返回空字典"""
        _write_text_file(tmp_path / "empty.vmt", '"VertexlitGeneric"\n{\n}\n')
        result = parse_vmt(tmp_path / "empty.vmt")
        assert result == {}

    def test_phongexponenttexture_parsed(self, tmp_path):
        """$phongexponenttexture 参数正确解析"""
        _write_text_file(tmp_path / "phong.vmt", '''
"VertexlitGeneric"
{
    "$basetexture" "models/base"
    "$phongexponenttexture" "models/exp"
}
''')
        result = parse_vmt(tmp_path / "phong.vmt")
        assert result.get("$phongexponenttexture") == "models/exp"


# ══════════════════════════════════════════════════════════
# PNG/TGA 尺寸读取测试
# ══════════════════════════════════════════════════════════

class TestPNGSize:
    """png_size() 函数测试"""

    def test_valid_png(self):
        """有效 PNG 应返回正确的宽高"""
        for w, h in [(256, 256), (512, 1024), (128, 64), (2048, 2048)]:
            p = _make_png(w, h)
            try:
                assert png_size(p) == (w, h)
            finally:
                p.unlink()
                p.parent.rmdir()

    def test_non_png_returns_none(self):
        """非 PNG 文件返回 None"""
        p = Path(tempfile.mkdtemp()) / "not_a.png"
        p.write_bytes(b"this is not a PNG at all!!")
        try:
            assert png_size(p) is None
        finally:
            p.unlink()
            p.parent.rmdir()

    def test_empty_file_returns_none(self):
        """空文件返回 None"""
        p = Path(tempfile.mkdtemp()) / "empty.png"
        p.write_bytes(b"")
        try:
            assert png_size(p) is None
        finally:
            p.unlink()
            p.parent.rmdir()

    def test_truncated_png_header(self):
        """截断的 PNG 头部返回 None"""
        p = Path(tempfile.mkdtemp()) / "trunc.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n")  # 只有签名没有 IHDR
        try:
            assert png_size(p) is None
        finally:
            p.unlink()
            p.parent.rmdir()


class TestTGASize:
    """tga_size() 函数测试"""

    def test_valid_tga(self):
        """有效 TGA 应返回正确宽高"""
        for w, h in [(256, 256), (64, 128), (1024, 512)]:
            p = _make_tga(w, h)
            try:
                assert tga_size(p) == (w, h)
            finally:
                p.unlink()
                p.parent.rmdir()

    def test_zero_dimension_returns_none(self):
        """宽高为 0 时返回 None"""
        p = Path(tempfile.mkdtemp()) / "zero.tga"
        with open(p, "wb") as f:
            f.write(b"\x00\x00\x02" + b"\x00" * 9 + struct.pack("<HH", 0, 0) + b"\x18\x20")
        try:
            assert tga_size(p) is None
        finally:
            p.unlink()
            p.parent.rmdir()

    def test_overflow_dimension_returns_none(self):
        """超出范围的维度返回 None"""
        p = Path(tempfile.mkdtemp()) / "overflow.tga"
        with open(p, "wb") as f:
            f.write(b"\x00\x00\x02" + b"\x00" * 9 + struct.pack("<HH", 65535, 65535) + b"\x18\x20")
        try:
            assert tga_size(p) is None
        finally:
            p.unlink()
            p.parent.rmdir()

    def test_truncated_header(self):
        """截断的 TGA 头返回 None"""
        p = Path(tempfile.mkdtemp()) / "short.tga"
        p.write_bytes(b"\x00" * 10)  # 不够 18 字节
        try:
            assert tga_size(p) is None
        finally:
            p.unlink()
            p.parent.rmdir()


class TestImageSize:
    """image_size() 路由函数测试"""

    def test_routes_to_png(self):
        """.png 后缀走 png_size 分支"""
        p = _make_png(320, 240)
        try:
            assert image_size(p) == (320, 240)
        finally:
            p.unlink()
            p.parent.rmdir()

    def test_routes_to_tga(self):
        """.tga 后缀走 tga_size 分支"""
        p = _make_tga(100, 200)
        try:
            assert image_size(p) == (100, 200)
        finally:
            p.unlink()
            p.parent.rmdir()

    def test_unknown_extension_returns_none(self):
        """未知后缀返回 None"""
        p = Path(tempfile.mkdtemp()) / "data.xyz"
        p.write_bytes(b"dummy data")
        try:
            assert image_size(p) is None
        finally:
            p.unlink()
            p.parent.rmdir()

    def test_case_insensitive_suffix(self):
        """后缀匹配不区分大小写"""
        p = _make_png(160, 120)
        # 重命名为大写后缀
        p_upper = p.with_suffix(".PNG")
        p.rename(p_upper)
        try:
            assert image_size(p_upper) == (160, 120)
        finally:
            p_upper.unlink()
            p_upper.parent.rmdir()


# ══════════════════════════════════════════════════════════
# 灰度转换测试 (sRGB → Gamma 2.2 灰度)
# ══════════════════════════════════════════════════════════

class TestMakeGrayGamma:
    """_make_gray_gamma() Gamma 灰度转换测试"""

    def test_pure_white_input(self):
        """纯白输入 → 输出全白 (255)"""
        white_img = Image.new("RGB", (10, 10), (255, 255, 255))
        gray = _make_gray_gamma(white_img)
        arr = np.array(gray)
        assert arr.shape == (10, 10)
        assert np.all(arr == 255), "纯白色应映射为灰度 255"

    def test_pure_black_input(self):
        """纯黑输入 → 输出全黑 (0)"""
        black_img = Image.new("RGB", (10, 10), (0, 0, 0))
        gray = _make_gray_gamma(black_img)
        arr = np.array(gray)
        assert np.all(arr == 0), "纯黑色应映射为灰度 0"

    def test_output_is_grayscale_mode(self):
        """输出应为 L 模式 (单通道)"""
        img = Image.new("RGB", (8, 8), (128, 128, 128))
        gray = _make_gray_gamma(img)
        assert gray.mode == "L", f"期望模式 'L'，实际 '{gray.mode}'"

    def test_luminance_weights(self):
        """BT.709 权重: 绿色通道贡献最大"""
        # R=255 G=0 B=0 -> 较暗
        red_img = Image.new("RGB", (4, 4), (255, 0, 0))
        gray_red = np.array(_make_gray_gamma(red_img))[0, 0]

        # R=0 G=255 B=0 -> 最亮
        green_img = Image.new("RGB", (4, 4), (0, 255, 0))
        gray_green = np.array(_make_gray_gamma(green_img))[0, 0]

        # R=0 G=0 B=255 -> 最暗
        blue_img = Image.new("RGB", (4, 4), (0, 0, 255))
        gray_blue = np.array(_make_gray_gamma(blue_img))[0, 0]

        assert gray_green > gray_red, "绿色亮度权重大于红色"
        assert gray_red > gray_blue, "红色亮度权重大于蓝色"

    def test_preserves_dimensions(self):
        """输出与输入尺寸一致"""
        for w, h in [(16, 16), (256, 128), (512, 512)]:
            img = Image.new("RGB", (w, h), (100, 150, 200))
            gray = _make_gray_gamma(img)
            assert gray.size == (w, h), f"尺寸不一致: {gray.size} != ({w}, {h})"

    def test_non_uniform_image(self):
        """非均匀颜色图像正常处理"""
        arr = np.zeros((20, 20, 3), dtype=np.uint8)
        arr[:10, :, 0] = 200   # 左半边偏红
        arr[10:, :, 1] = 200   # 右半边偏绿
        img = Image.fromarray(arr, mode="RGB")
        gray = _make_gray_gamma(img)
        gray_arr = np.array(gray)
        # 左半和右半应有明显差异
        left_mean = gray_arr[:10].mean()
        right_mean = gray_arr[10:].mean()
        assert abs(left_mean - right_mean) > 10, "左右两半灰度值差异不够"


# ══════════════════════════════════════════════════════════
# 入口（允许直接运行）
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import unittest

    # 加载当前模块的所有 TestCase
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 汇总输出
    print(f"\n{'='*60}")
    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped) if hasattr(result, "skipped") else 0
    passed = total - failures - errors - skipped
    print(f"结果: {passed}/{total} 通过 | {failures} 失败 | {errors} 错误 | {skipped} 跳过")

    sys.exit(0 if (failures == 0 and errors == 0) else 1)
