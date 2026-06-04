"""VMT 重写引擎单元测试

覆盖: VMT 解析/构建、预设驱动重写、参数匹配规则、映射表

运行方式:
    python -m pytest tests/test_vmt_rewrite.py -v
    # 或
    python tests/test_vmt_rewrite.py
"""

import os
import sys
import json
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["QT_QPA_PLATFORM"] = "offscreen"

# ── 动态导入 VPK 工具模块 ──────────────────────────────
import importlib.util as _iu  # noqa: E402
_vpk_spec = _iu.spec_from_file_location("vpk_tool", str(PROJECT_ROOT / "sp2vtf_vpk_tool.py"))
_vpk_mod = _iu.module_from_spec(_vpk_spec)
if "vpk_tool" not in sys.modules:
    sys.modules["vpk_tool"] = _vpk_mod
    _vpk_spec.loader.exec_module(_vpk_mod)

# 从 VPK 工具模块中提取纯函数（不触发 tkinter GUI）
vpk_parse_vmt = _vpk_mod.parse_vmt
build_vmt = _vpk_mod.build_vmt
rewrite_vmt_params = _vpk_mod.rewrite_vmt_params
build_vmt_from_preset = _vpk_mod.build_vmt_from_preset
load_vmt_preset = _vpk_mod.load_vmt_preset
VmtMapping = _vpk_mod.VmtMapping


def _write_vmt(path: Path, content: str):
    """写入一个 VMT 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ══════════════════════════════════════════════════════════
# VMT 解析与构建
# ══════════════════════════════════════════════════════════

class TestVPKParseVMT:
    """VPK 工具的 parse_vmt 函数"""

    def test_basic_params(self, tmp_path):
        """基础参数提取"""
        _write_vmt(tmp_path / "test.vmt", '''
"VertexlitGeneric"
{
    "$basetexture" "models/test/base"
    "$bumpmap" "models/test/normal"
}
''')
        result = vpk_parse_vmt(tmp_path / "test.vmt")
        assert result["$basetexture"] == "models/test/base"
        assert result["$bumpmap"] == "models/test/normal"

    def test_normalizes_backslash(self, tmp_path):
        """反斜杠转正斜杠"""
        _write_vmt(tmp_path / "bs.vmt", '"VertexlitGeneric"\n{\n"$basetexture" "a\\b\\c"\n}\n')
        result = vpk_parse_vmt(tmp_path / "bs.vmt")
        assert result["$basetexture"] == "a/b/c"


class TestBuildVMT:
    """build_vmt() 构建函数测试"""

    def test_minimal_vmt(self):
        """最小 VMT 生成"""
        params = {"$basetexture": "models/tex"}
        vmt_str = build_vmt(params)
        assert '"VertexlitGeneric"' in vmt_str
        assert '$basetexture' in vmt_str or '"$basetexture"' in vmt_str

    def test_with_comments(self):
        """带注释的 VMT"""
        params = {"$basetexture": "tex"}
        vmt_str = build_vmt(params, comments="auto-generated")
        assert "auto-generated" in vmt_str


class TestRewriteVMTParams:
    """rewrite_vmt_params() 预设驱动重写测试"""

    def test_keep_original_basetexture(self):
        """无新 base stem 时保留原 $basetexture"""
        orig = {"$basetexture": "models/original/base"}
        preset = {"texture_rules": {"$bumpmap": "old"}, "params": {}}
        result = rewrite_vmt_params(orig, preset, "material_name")
        assert result["$basetexture"] == "models/original/base"

    def test_new_basetexture_from_sp(self):
        """有 SP 新 base stem 时更新 $basetexture"""
        orig = {"$basetexture": "models/old/base"}
        preset = {"texture_rules": {}, "params": {}}
        result = rewrite_vmt_params(orig, preset, "mat1", new_base_stem="mat1_Base_Color")
        assert "mat1_Base_Color" in result["$basetexture"]

    def test_bumpmap_rule_old(self):
        """bumpmap=old 时保留原值"""
        orig = {"$bumpmap": "models/old/norm"}
        preset = {"texture_rules": {"$bumpmap": "old"}, "params": {}}
        result = rewrite_vmt_params(orig, preset, "mat1")
        assert result["$bumpmap"] == "models/old/norm"

    def test_bumpmap_rule_new(self):
        """bumpmap=new 时使用新命名规则"""
        orig = {"$bumpmap": "models/old/norm"}
        preset = {"texture_rules": {"$bumpmap": "new"}, "params": {}}
        result = rewrite_vmt_params(orig, preset, "mat1")
        assert result["$bumpmap"].endswith("mat1_n")

    def test_phongexponent_rule_new(self):
        """phongexponent=new 时使用新命名"""
        orig = {"$phongexponenttexture": "old/exp"}
        preset = {"texture_rules": {"$phongexponenttexture": "new"}, "params": {}}
        result = rewrite_vmt_params(orig, preset, "mat2")
        assert result["$phongexponenttexture"].endswith("mat2_e")

    def test_custom_params_from_preset(self):
        """预设中的自定义参数被写入"""
        orig = {"$basetexture": "base"}
        preset = {
            "texture_rules": {},
            "params": {
                "$model": "1",
                "$halflambert": "1",
                "$envmap": "env_cubemap",
            },
        }
        result = rewrite_vmt_params(orig, preset, "test_mat")
        assert result.get("$model") == "1"
        assert result.get("$halflambert") == "1"
        assert result.get("$envmap") == "env_cubemap"

    def test_placeholder_substitution(self):
        """占位符替换: {vmt_name} {dir}"""
        orig = {"$basetexture": "models/weapons/v_rif/AK47"}
        preset = {
            "texture_rules": {},
            "params": {
                "$detail": "{dir}/{vmt_name}_detail",
                "$selfillummask": "{orig_base}_mask",
            },
        }
        result = rewrite_vmt_params(orig, preset, "AK47")
        dir_part = "models/weapons/v_rif"
        assert f"{dir_part}/AK47_detail" in result["$detail"].replace("\\", "/")
        assert "AK47_mask" in result["$selfillummask"]

    def test_bumpmap_not_overridden_by_params(self):
        """$bumpmap 由 texture_rules 控制，不被 params 覆盖"""
        orig = {"$bumpmap": "original_n"}
        preset = {
            "texture_rules": {"$bumpmap": "old"},
            "params": {"$bumpmap": "should_be_ignored"},
        }
        result = rewrite_vmt_params(orig, preset, "mat")
        assert result["$bumpmap"] == "original_n", \
            "$bumpmap 不应被 params 中的同名键覆盖"


# ══════════════════════════════════════════════════════════
# VmtMapping 映射表
# ══════════════════════════════════════════════════════════

class TestVmtMapping:
    """VmtMapping 序列化测试"""

    def test_save_and_load(self, tmp_path):
        """保存后加载应保持一致"""
        map_file = tmp_path / "mapping.json"
        data = {
            "AK47": {"$basetexture": "base", "$bumpmap": "norm", "$phongexponenttexture": "exp"},
            "M4A1": {"$basetexture": "m4_base", "$bumpmap": "m4_norm"},
        }
        vm = VmtMapping(data)
        vm.save(map_file)
        loaded = VmtMapping.load(map_file)
        assert dict(loaded._map) == data

    def test_empty_mapping(self, tmp_path):
        """空映射表的保存和加载"""
        map_file = tmp_path / "empty.json"
        vm = VmtMapping()
        vm.save(map_file)
        loaded = VmtMapping.load(map_file)
        assert len(loaded) == 0

    def test_get_method(self):
        """get 方法查找"""
        vm = VmtMapping({"a": {"k": "v"}})
        assert vm.get("a") == {"k": "v"}
        assert vm.get("nonexistent") is None

    def test_bool_conversion(self):
        """bool() 转换"""
        assert bool(VmtMapping({"x": {}})) is True
        assert bool(VmtMapping()) is False

    def test_items_iteration(self):
        """items() 迭代"""
        data = {"a": 1, "b": 2}
        vm = VmtMapping(data)
        items = dict(vm.items())
        assert items == data


# ══════════════════════════════════════════════════════════
# 预设 JSON 加载
# ══════════════════════════════════════════════════════════

class TestLoadPreset:
    """load_vmt_preset() 测试"""

    def test_load_existing_preset(self, tmp_path, monkeypatch):
        """加载存在的预设文件"""
        preset_dir = tmp_path / "presets"
        preset_dir.mkdir()
        (preset_dir / "sfm2sfm.json").write_text(json.dumps({
            "name": "SFM to SFM",
            "texture_rules": {"$bumpmap": "new", "$phongexponenttexture": "new"},
            "params": {"$model": "1"},
        }, ensure_ascii=False), encoding="utf-8")

        import sp2vtf_vpk_tool
        original_presets_dir = sp2vtf_vpk_tool.PRESETS_DIR
        sp2vtf_vpk_tool.PRESETS_DIR = preset_dir
        try:
            preset = load_vmt_preset("sfm2sfm")
            # 预设文件包含 texture_rules 和 params
            assert "texture_rules" in preset
            assert "params" in preset
            assert preset["texture_rules"]["$bumpmap"] in ("old", "new")  # 验证字段存在，值由预设定义
        finally:
            sp2vtf_vpk_tool.PRESETS_DIR = original_presets_dir

    def test_missing_preset_raises(self, monkeypatch):
        """缺少的预设抛出 FileNotFoundError"""
        import sp2vtf_vpk_tool
        original_presets_dir = sp2vtf_vpk_tool.PRESETS_DIR
        sp2vtf_vpk_tool.PRESETS_DIR = Path(tempfile.mkdtemp())
        try:
            try:
                load_vmt_preset("nonexistent_preset")
                assert False, "应抛出 FileNotFoundError"
            except FileNotFoundError:
                pass
        finally:
            sp2vtf_vpk_tool.PRESETS_DIR = original_presets_dir


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
