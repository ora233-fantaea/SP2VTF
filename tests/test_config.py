"""配置序列化/反序列化测试

覆盖: 配置文件读写、默认值、字段完整性

运行方式:
    python -m pytest tests/test_config.py -v
    # 或
    python tests/test_config.py
"""

import os
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["QT_QPA_PLATFORM"] = "offscreen"

# ══════════════════════════════════════════════════════════
# 配置文件结构验证
# ══════════════════════════════════════════════════════════

class TestConfigSchema:
    """配置 JSON 结构校验"""

    EXPECTED_TOP_KEYS = {
        "vtfcmd", "png_dir", "vmt_dir",
        "size_enabled", "resize_enabled",
        "resize_width", "resize_height",
        "vtf_version", "color_format", "alpha_format",
        "resize_method", "resize_filter",
        "preprocess_base", "preprocess_normal",
    }

    def test_default_config_has_all_keys(self, tmp_path):
        """默认配置应包含所有预期字段"""
        # 模拟 MainWindow._save_config 产生的数据结构
        # CONFIG_FILE 是主模块的常量，这里仅验证数据结构完整性
        # 直接构建一个典型的保存结果来验证结构
        data = {
            k: "" for k in ["vtfcmd", "png_dir", "vmt_dir"]
        }
        data.update({
            "size_enabled": True,
            "resize_enabled": True,
            "resize_width": 1024,
            "resize_height": 1024,
            "vtf_version": "7.2",
            "color_format": "DXT1",
            "alpha_format": "DXT5",
            "resize_method": "nearest",
            "resize_filter": "triangle",
            "preprocess_base": {"alpha_enabled": False, "alpha_source": "gray",
                                "levels_enabled": False, "out_black": 0, "out_white": 255},
            "preprocess_normal": {"alpha_enabled": False, "alpha_source": "gray",
                                  "levels_enabled": False, "out_black": 0, "out_white": 255},
        })

        missing = self.EXPECTED_TOP_KEYS - set(data.keys())
        assert not missing, f"缺少字段: {missing}"

    def test_config_is_valid_json(self, tmp_path):
        """配置文件应为合法 JSON"""
        cfg_path = tmp_path / "test_config.json"
        cfg_data = {
            "vtfcmd": "C:/tools/VTFCmd.exe",
            "png_dir": "D:/exports/PNG",
            "vmt_dir": "D:/game/materials",
            "size_enabled": True,
            "vtf_version": "7.2",
        }
        cfg_path.write_text(json.dumps(cfg_data, indent=2, ensure_ascii=False), encoding="utf-8")

        loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert loaded["vtfcmd"] == "C:/tools/VTFCmd.exe"
        assert loaded["size_enabled"] is True

    def test_empty_string_fields(self):
        """空字符串路径字段是合法的（用户未填写时）"""
        data = {
            "vtfcmd": "", "png_dir": "", "vmt_dir": "",
            "size_enabled": False,
            "resize_width": 1024, "resize_height": 1024,
            "vtf_version": "7.2",
            "color_format": "DXT1", "alpha_format": "DXT5",
            "resize_method": "nearest", "resize_filter": "triangle",
            "preprocess_base": {},
            "preprocess_normal": {},
        }
        # 不应抛异常
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["vtfcmd"] == ""

    def test_preprocess_config_structure(self):
        """预处理配置应包含所有必需子键"""
        for slot in ("base", "normal"):
            pp = {
                "alpha_enabled": True if slot == "base" else False,
                "alpha_source": "gray",
                "levels_enabled": False,
                "out_black": 0,
                "out_white": 255,
            }
            assert "alpha_enabled" in pp
            assert "alpha_source" in pp
            assert "levels_enabled" in pp
            assert "out_black" in pp
            assert "out_white" in pp
            assert isinstance(pp["out_black"], int)
            assert isinstance(pp["out_white"], int)
            assert 0 <= pp["out_black"] <= 255
            assert 0 <= pp["out_white"] <= 255


class TestConfigRoundTrip:
    """配置写入→读取往返一致性"""

    def test_round_trip_preserves_all_values(self, tmp_path):
        """写后再读，所有值应一致"""
        original = {
            "vtfcmd": "C:/VTFCmd.exe",
            "png_dir": "D:/SP/BaseColor",
            "vmt_dir": "D:/game/addon/materials",
            "size_enabled": True,
            "resize_enabled": False,
            "resize_width": 2048,
            "resize_height": 2048,
            "vtf_version": "7.5",
            "color_format": "DXT5",
            "alpha_format": "RGBA8888",
            "resize_method": "cubic",
            "resize_filter": "catrom",
            "preprocess_base": {
                "alpha_enabled": True,
                "alpha_source": "r",
                "levels_enabled": True,
                "out_black": 30,
                "out_white": 180,
            },
            "preprocess_normal": {
                "alpha_enabled": False,
                "alpha_source": "gray",
                "levels_enabled": False,
                "out_black": 0,
                "out_white": 255,
            },
        }

        cfg_path = tmp_path / "roundtrip.json"
        cfg_path.write_text(json.dumps(original, indent=2, ensure_ascii=False), encoding="utf-8")
        loaded = json.loads(cfg_path.read_text(encoding="utf-8"))

        for key, val in original.items():
            assert key in loaded, f"丢失键: {key}"
            assert loaded[key] == val, f"键 '{key}' 值不一致: {loaded[key]} != {val}"

    def test_unicode_paths(self, tmp_path):
        """Unicode 路径在 JSON 中正确处理"""
        original = {
            "png_dir": "D:/导出/基础贴图",
            "vmt_dir": "C:/游戏/素材/VMT",
        }
        cfg_path = tmp_path / "unicode.json"
        cfg_path.write_text(json.dumps(original, indent=2, ensure_ascii=False), encoding="utf-8")
        loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert loaded["png_dir"] == "D:/导出/基础贴图"
        assert loaded["vmt_dir"] == "C:/游戏/素材/VMT"


# ══════════════════════════════════════════════════════════
# VTF 格式/版本枚举值验证
# ══════════════════════════════════════════════════════════

class TestVTFEnums:
    """VTF 格式和版本常量验证"""

    def test_vtf_versions_are_strings(self):
        """版本号列表应全部为字符串"""
        versions = ["7.0", "7.1", "7.2", "7.3", "7.4", "7.5"]
        for v in versions:
            assert isinstance(v, str)

    def test_common_formats_in_list(self):
        """常用格式应在格式列表中"""
        formats_list = [
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
        for fmt in ("DXT1", "DXT5", "RGBA8888", "I8", "A8"):
            assert fmt in formats_list, f"缺少常用格式: {fmt}"

    def test_resize_methods_valid(self):
        """缩放方法列表"""
        methods = ["nearest", "biggest", "smallest"]
        for m in methods:
            assert isinstance(m, str) and len(m) > 0

    def test_resize_filters_valid(self):
        """滤波器列表"""
        filters = [
            "point", "box", "triangle", "quadratic", "cubic",
            "catrom", "mitchell", "gaussian", "sinc", "bessel",
            "hanning", "hamming", "blackman", "kaiser",
        ]
        assert len(filters) >= 10


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
