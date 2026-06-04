"""文件对比引擎单元测试

覆盖: 文件收集、逐字节对比、VMT 引用解析、分组逻辑

运行方式:
    python -m pytest tests/test_compare.py -v
    # 或
    python tests/test_compare.py
"""

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["QT_QPA_PLATFORM"] = "offscreen"

# ── 动态导入主模块 ──────────────────────────────────────
import importlib.util as _iu  # noqa: E402
_cmp_spec = _iu.spec_from_file_location("sp_compare_mod", str(PROJECT_ROOT / "sp_to_vtf_v1.0.4.py"))
_cmp_mod = _iu.module_from_spec(_cmp_spec)
if "sp_compare_mod" not in sys.modules:
    sys.modules["sp_compare_mod"] = _cmp_mod
    _cmp_spec.loader.exec_module(_cmp_mod)

parse_vmt = _cmp_mod.parse_vmt


# ══════════════════════════════════════════════════════════
# 测试辅助：创建临时文件结构
# ══════════════════════════════════════════════════════════

def _create_file_tree(root: Path, files: dict[str, bytes]):
    """在 root 下创建文件树。files: {相对路径: 内容}"""
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)


def _make_vmt_content(basetexture=None, bumpmap=None, phongexp=None):
    """生成一个 VMT 文件内容字符串。"""
    lines = ['"VertexlitGeneric", "{']
    if basetexture:
        lines.append(f'    "$basetexture" "{basetexture}"')
    if bumpmap:
        lines.append(f'    "$bumpmap" "{bumpmap}"')
    if phongexp:
        lines.append(f'    "$phongexponenttexture" "{phongexp}"')
    lines.append("}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
# VMT 解析（对比工具专用）
# ══════════════════════════════════════════════════════════

# parse_vmt 已通过动态导入在文件顶部加载


class TestCompareParseVMT:
    """对比场景下的 VMT 解析"""

    def test_parse_bumpmap_only(self, tmp_path):
        """只含 bumpmap 的 VMT"""
        vmt_path = tmp_path / "mat.vmt"
        vmt_path.write_text(_make_vmt_content(bumpmap="models/mat_n"))
        result = parse_vmt(vmt_path)
        assert result.get("$bumpmap") == "models/mat_n"
        assert "$basetexture" not in result  # 未定义的键不应出现

    def test_parse_all_texture_params(self, tmp_path):
        """三个纹理参数都有的 VMT"""
        vmt_path = tmp_path / "full.vmt"
        vmt_path.write_text(_make_vmt_content(
            basetexture="models/base",
            bumpmap="models/norm",
            phongexp="models/exp"
        ))
        result = parse_vmt(vmt_path)
        assert len(result) == 3


class TestFileComparisonLogic:
    """文件对比核心逻辑（模拟 CompareDialog._compare_work）"""

    @staticmethod
    def _collect_files(root):
        """与 CompareDialog._collect_files 相同的逻辑"""
        files = {}
        for f in root.rglob("*"):
            if f.is_file():
                files[str(f.relative_to(root)).replace("\\", "/")] = f
        return files

    @staticmethod
    def _files_equal(a: Path, b: Path) -> bool:
        """与 CompareDialog._files_equal 相同的逻辑"""
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

    def test_identical_directories(self, tmp_path):
        """完全相同的目录 → 所有文件标记为未变化"""
        orig_dir = tmp_path / "orig"
        targ_dir = tmp_path / "targ"
        content = b"hello world" * 100

        _create_file_tree(orig_dir, {
            "a.txt": content,
            "sub/b.txt": content * 2,
            "sub/deep/c.dat": b"\x00" * 500,
        })
        # target 完全复制
        import shutil
        shutil.copytree(orig_dir, targ_dir, dirs_exist_ok=True)

        orig_files = self._collect_files(orig_dir)
        targ_files = self._collect_files(targ_dir)

        all_names = sorted(set(orig_files) | set(targ_files))
        for name in all_names:
            o = orig_files.get(name)
            t = targ_files.get(name)
            if o and t:
                assert o.stat().st_size == t.stat().st_size
                assert self._files_equal(o, t)

    def test_different_content(self, tmp_path):
        """内容不同的同名文件应被检测为变动"""
        orig_dir = tmp_path / "orig"
        targ_dir = tmp_path / "targ"

        (orig_dir).mkdir(parents=True)
        (targ_dir).mkdir(parents=True)

        (orig_dir / "data.bin").write_bytes(b"version_1_data_here")
        (targ_dir / "data.bin").write_bytes(b"version_2_data_modified")

        assert not self._files_equal(orig_dir / "data.bin", targ_dir / "data.bin")

    def test_only_in_target(self, tmp_path):
        """仅 Target 中有、Original 没有的文件"""
        orig_dir = tmp_path / "orig"
        targ_dir = tmp_path / "targ"
        orig_dir.mkdir()
        targ_dir.mkdir()

        (orig_dir / "old.txt").write_bytes(b"original only")
        (targ_dir / "new_file.txt").write_bytes(b"target only")

        orig_set = set(self._collect_files(orig_dir))
        targ_set = set(self._collect_files(targ_dir))
        only_target = targ_set - orig_set
        assert "new_file.txt" in only_target
        only_orig = orig_set - targ_set
        assert "old.txt" in only_orig

    def test_empty_directory(self, tmp_path):
        """空目录不崩溃"""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        files = self._collect_files(empty_dir)
        assert files == {}

    def test_large_file_comparison(self, tmp_path):
        """大文件（>64KB）分块对比正确性"""
        orig_dir = tmp_path / "orig_big"
        targ_dir = tmp_path / "targ_big"
        orig_dir.mkdir()
        targ_dir.mkdir()

        # 生成 ~200KB 的数据
        data_a = bytes(i % 256 for i in range(200_000))
        data_b = bytearray(data_a)
        data_b[100_000] ^= 0xFF  # 翻转一个字节

        (orig_dir / "big.bin").write_bytes(data_a)
        (targ_dir / "big.bin").write_bytes(bytes(data_b))

        assert not self._files_equal(orig_dir / "big.bin", targ_dir / "big.bin")

        # 但相同的大文件应该返回 True
        (targ_dir / "same_big.bin").write_bytes(data_a)
        assert self._files_equal(orig_dir / "big.bin", targ_dir / "same_big.bin")


class TestVMTReferenceResolution:
    """VMT 引用→VTF 文件解析度测试"""

    def test_resolve_basetexture_to_vtf(self, tmp_path):
        """$basetexture 值 + .vtf 后缀 应能定位到实际文件"""
        materials = tmp_path / "materials"
        (materials / "models").mkdir(parents=True)
        vtf_path = materials / "models" / "base.vtf"
        vtf_path.write_bytes(b"dummy vtf data")
        vmt_path = materials / "test.vmt"
        vmt_path.write_text(_make_vmt_content(basetexture="models/base"))

        params = parse_vmt(vmt_path)
        base_rel = params.get("$basetexture", "")
        expected_vtf = (materials / f"{base_rel}.vtf")
        assert expected_vtf.is_file(), \
            f"$basetexture '{base_rel}' 应能解析到 {expected_vtf}"

    def test_resolve_bumpmap_to_vtf(self, tmp_path):
        """$bumpmap 值 + .vtf 后缀 定位"""
        materials = tmp_path / "materials"
        (materials / "normals").mkdir(parents=True)
        vtf_path = materials / "normals" / "n_map.vtf"
        vtf_path.write_bytes(b"vtf normal")
        vmt_path = materials / "weapon.vmt"
        vmt_path.write_text(_make_vmt_content(bumpmap="normals/n_map"))

        params = parse_vmt(vmt_path)
        bump_rel = params.get("$bumpmap", "")
        expected_vtf = materials / f"{bump_rel}.vtf"
        assert expected_vtf.is_file()

    def test_missing_vtf_reference(self, tmp_path):
        """引用了不存在的 VTF 文件"""
        materials = tmp_path / "materials"
        materials.mkdir()
        vmt_path = materials / "ghost.vmt"
        vmt_path.write_text(_make_vmt_content(basetexture="nonexistent/texture"))

        params = parse_vmt(vmt_path)
        base_rel = params.get("$basetexture", "")
        expected_vtf = materials / f"{base_rel}.vtf"
        assert not expected_vtf.exists(), "不存在的 VTF 应返回不存在"


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
