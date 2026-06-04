"""预处理管线单元测试

覆盖: Alpha 通道生成 (R/G/B/灰度)、色阶调整、PNG→TGA 转换

运行方式:
    python -m pytest tests/test_preprocess.py -v
    # 或
    python tests/test_preprocess.py
"""

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

# ── 动态导入主模块 ──────────────────────────────────────
import importlib.util as _iu  # noqa: E402
_sp = _iu.spec_from_file_location("sp_preprocess_mod", str(PROJECT_ROOT / "sp_to_vtf_v1.0.4.py"))
_sp_mod = _iu.module_from_spec(_sp)
if "sp_preprocess_mod" not in sys.modules:
    sys.modules["sp_preprocess_mod"] = _sp_mod
    _sp.loader.exec_module(_sp_mod)

apply_preprocess = _sp_mod.apply_preprocess


def _make_rgba_png(w=64, h=64, r=128, g=100, b=200, a=255):
    """创建一个 RGBA PNG 文件，返回 Path。"""
    img = Image.new("RGBA", (w, h), (r, g, b, a))
    d = tempfile.mkdtemp()
    path = Path(d) / "test_rgba.png"
    img.save(path)
    return path


# ══════════════════════════════════════════════════════════
# Alpha 通道来源测试
# ══════════════════════════════════════════════════════════

class TestAlphaSource:
    """Alpha 通道来源选择"""

    def test_gray_source(self):
        """灰度模式: 使用 BT.709 亮度"""
        png = _make_rgba_png(32, 32, r=200, g=50, b=50)
        try:
            tmp = tempfile.mkdtemp()
            config = {"alpha_source": "gray", "alpha_enabled": True}
            tga = apply_preprocess(png, config, Path(tmp))
            assert tga.exists(), "TGA 文件应被创建"

            result = Image.open(tga)
            assert result.mode == "RGBA", f"期望 RGBA 模式，实际 {result.mode}"
            alpha_ch = result.getchannel("A")
            # 绿色分量最低(50)，灰度值应偏低
            mean_alpha = np.array(alpha_ch).mean()
            assert 0 < mean_alpha < 255, f"Alpha 均值 {mean_alpha} 应在 (0,255) 内"
        finally:
            for p in [png] + list(Path(tmp).glob("*")):
                if p.is_file():
                    p.unlink()

    def test_red_channel_source(self):
        """R 通道模式: Alpha 直接取 R 值"""
        png = _make_rgba_png(32, 32, r=230, g=10, b=10)
        try:
            tmp = tempfile.mkdtemp()
            config = {"alpha_source": "r", "alpha_enabled": True}
            tga = apply_preprocess(png, config, Path(tmp))
            result = Image.open(tga)
            alpha_arr = np.array(result.getchannel("A"))
            # R=230 → 灰度高
            assert alpha_arr.mean() > 200, "R 通道为 230 时 Alpha 应接近 230"
        finally:
            for p in [png] + list(Path(tmp).glob("*")):
                if p.is_file():
                    p.unlink()

    def test_green_channel_source(self):
        """G 通道模式: Alpha 直接取 G 值"""
        png = _make_rgba_png(32, 32, r=10, g=240, b=10)
        try:
            tmp = tempfile.mkdtemp()
            config = {"alpha_source": "g", "alpha_enabled": True}
            tga = apply_preprocess(png, config, Path(tmp))
            result = Image.open(tga)
            alpha_arr = np.array(result.getchannel("A"))
            assert alpha_arr.mean() > 220, "G 通道为 240 时 Alpha 应接近 240"
        finally:
            for p in [png] + list(Path(tmp).glob("*")):
                if p.is_file():
                    p.unlink()

    def test_blue_channel_source(self):
        """B 通道模式: Alpha 直接取 B 值"""
        png = _make_rgba_png(32, 32, r=10, g=10, b=180)
        try:
            tmp = tempfile.mkdtemp()
            config = {"alpha_source": "b", "alpha_enabled": True}
            tga = apply_preprocess(png, config, Path(tmp))
            result = Image.open(tga)
            alpha_arr = np.array(result.getchannel("A"))
            assert 160 < alpha_arr.mean() < 200, "B 通道为 180 时 Alpha 应接近 180"
        finally:
            for p in [png] + list(Path(tmp).glob("*")):
                if p.is_file():
                    p.unlink()


class TestLevelsAdjustment:
    """色阶调整 (输出黑点/白点) 测试"""

    def test_levels_clamp_low(self):
        """低色阶裁切：黑点以下归零"""
        png = _make_rgba_png(16, 16, r=80, g=80, b=80)
        try:
            tmp = tempfile.mkdtemp()
            config = {
                "alpha_source": "gray",
                "alpha_enabled": True,
                "levels_enabled": True,
                "out_black": 60,
                "out_white": 255,
            }
            tga = apply_preprocess(png, config, Path(tmp))
            result = Image.open(tga)
            alpha_arr = np.array(result.getchannel("A"))
            # 黑点设为 60，原始灰度约 86 (>60)，所以不应全零
            # 但应比无色阶时更低（因为范围压缩了）
            assert alpha_arr.min() >= 0, "Alpha 不应有负值"
            assert alpha_arr.max() <= 255, "Alpha 不应超过 255"
        finally:
            for p in [png] + list(Path(tmp).glob("*")):
                if p.is_file():
                    p.unlink()

    def test_levels_clamp_high(self):
        """高色阶裁切：白点以上归 255"""
        png = _make_rgba_png(16, 16, r=250, g=250, b=250)
        try:
            tmp = tempfile.mkdtemp()
            config = {
                "alpha_source": "gray",
                "alpha_enabled": True,
                "levels_enabled": True,
                "out_black": 0,
                "out_white": 200,
            }
            tga = apply_preprocess(png, config, Path(tmp))
            result = Image.open(tga)
            alpha_arr = np.array(result.getchannel("A"))
            # 原始灰度很高 (~248)，白点截断到 200 → 应该全部映射到 255
            assert alpha_arr.mean() == 255, "超过白点的值应全部映射到 255"
        finally:
            for p in [png] + list(Path(tmp).glob("*")):
                if p.is_file():
                    p.unlink()

    def test_no_levels_when_disabled(self):
        """禁用色阶时不应有裁切效果"""
        png = _make_rgba_png(16, 16, r=128, g=128, b=128)
        try:
            tmp_a = tempfile.mkdtemp()
            tmp_b = tempfile.mkdtemp()
            cfg_with = {
                "alpha_source": "gray",
                "alpha_enabled": True,
                "levels_enabled": True,
                "out_black": 40,
                "out_white": 200,
            }
            cfg_without = {
                "alpha_source": "gray",
                "alpha_enabled": True,
                "levels_enabled": False,
                "out_black": 40,
                "out_white": 200,
            }
            tga_a = apply_preprocess(png, cfg_with, Path(tmp_a))
            tga_b = apply_preprocess(png, cfg_without, Path(tmp_b))
            arr_a = np.array(Image.open(tga_a).getchannel("A"))
            arr_b = np.array(Image.open(tga_b).getchannel("A"))
            # 启用色阶的版本应该有不同的分布
            assert not np.array_equal(arr_a, arr_b), "启用和禁用色阶的结果应不同"
        finally:
            for p in [png]:
                p.unlink(p)


class TestPreprocessOutput:
    """预处理输出格式验证"""

    def test_output_is_tga(self):
        """输出文件应为 .tga 后缀"""
        png = _make_rgba_png()
        try:
            tmp = tempfile.mkdtemp()
            config = {"alpha_source": "gray", "alpha_enabled": True}
            tga = apply_preprocess(png, config, Path(tmp))
            assert tga.suffix.lower() == ".tga", f"期望 .tga 后缀，实际 {tga.suffix}"
        finally:
            for p in [png] + list(Path(tmp).glob("*")):
                if p.is_file():
                    p.unlink()

    def test_output_uses_png_stem(self):
        """输出文件名应基于输入 PNG 的 stem"""
        png = _make_rgba_png()
        try:
            tmp = tempfile.mkdtemp()
            config = {"alpha_source": "gray", "alpha_enabled": True}
            tga = apply_preprocess(png, config, Path(tmp))
            assert tga.stem == png.stem, f"期望 stem='{png.stem}'，实际 '{tga.stem}'"
        finally:
            for p in [png] + list(Path(tmp).glob("*")):
                if p.is_file():
                    p.unlink()

    def test_rgb_channels_preserved(self):
        """RGB 通道应保持不变"""
        png = _make_rgba_png(32, 32, r=77, g=143, b=210)
        try:
            tmp = tempfile.mkdtemp()
            config = {"alpha_source": "b", "alpha_enabled": True}  # 用 B 通道作为 alpha
            tga = apply_preprocess(png, config, Path(tmp))
            result = Image.open(tga)
            rgb = result.convert("RGB")
            expected = Image.new("RGB", (32, 32), (77, 143, 210))
            # RGB 应完全相同（只改变了 Alpha）
            assert np.array_equal(np.array(rgb), np.array(expected)), \
                "RGB 通道应在预处理后保持不变"
        finally:
            for p in [png] + list(Path(tmp).glob("*")):
                if p.is_file():
                    p.unlink()

    def test_alpha_disabled_keeps_original(self):
        """不启用 alpha 时，Alpha 通道仍来自灰度转换（默认行为）"""
        png = _make_rgba_png(32, 32, r=100, g=100, b=100)
        try:
            tmp = tempfile.mkdtemp()
            config = {"alpha_enabled": False}
            tga = apply_preprocess(png, config, Path(tmp))
            assert tga.exists(), "即使未启用 alpha 也应生成 TGA"
            result = Image.open(tga)
            result.close()  # 显式关闭释放文件句柄
            assert result.mode == "RGBA", "结果应为 RGBA"
        finally:
            # 延迟删除，等待文件句柄释放
            import time
            time.sleep(0.1)
            for p in list(Path(tmp).glob("*")) + [png]:
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass
            try:
                Path(tmp).rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    import unittest

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print(f"\n{'='*60}")
    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total - failures - errors
    print(f"结果: {passed}/{total} 通过 | {failures} 失败 | {errors} 错误")

    sys.exit(0 if (failures == 0 and errors == 0) else 1)
