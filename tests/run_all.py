"""SP2VTF 测试套件 — 全量运行入口

用法:
    python tests/run_all.py          # 运行全部测试
    python tests/run_all.py --verbose # 详细输出
    python tests/run_all.py core      # 只运行核心测试
"""

import sys
import os
import unittest
from pathlib import Path

# ── 项目根目录加入路径 ────────────────────────────────
TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 防止 Qt GUI 初始化
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ══════════════════════════════════════════════════════
# 模块发现与加载
# ══════════════════════════════════════════════════════

def discover_tests(pattern="test_*.py"):
    """自动发现并加载 tests/ 下所有测试模块。"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for test_file in sorted(TESTS_DIR.glob(pattern)):
        if test_file.name == __name__ or test_file.suffix != ".py":
            continue
        module_name = test_file.stem
        try:
            # 动态导入测试模块（文件名含下划线，可正常导入）
            import importlib.util
            spec = importlib.util.spec_from_file_location(module_name, str(test_file))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            sub_suite = loader.loadTestsFromModule(mod)
            suite.addTest(sub_suite)
            print(f"  [加载] {test_file.name}")
        except Exception as e:
            print(f"  [跳过] {test_file.name}: {e}")
    return suite


# ══════════════════════════════════════════════════════
# 主函数
# ══════════════════════════════════════════════════════

def main():
    args = set(sys.argv[1:])
    verbose = "--verbose" in args or "-v" in args

    # 确定运行范围
    target_modules = [a for a in args if a.startswith("test_")]
    if target_modules:
        pattern = f"({'|'.join(target_modules)}).py"
    else:
        pattern = "test_*.py"

    print(f"\n{'='*60}")
    print("  SP2VTF 测试套件")
    print(f"{'='*60}")
    print(f"  模式: {'详细' if verbose else '标准'}")
    print(f"  范围: {pattern or '全部'}")
    print(f"{'='*60}\n")

    suite = discover_tests(pattern)

    if suite.countTestCases() == 0:
        print("未找到任何测试用例！")
        return 1

    verbosity = 2 if verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    # ═══ 汇总报告 ═══
    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = getattr(result, "skipped", [])
    skip_count = len(skipped) if skipped else 0
    passed = total - failures - errors - skip_count

    rate = (passed / total * 100) if total > 0 else 0

    print(f"\n{'='*60}")
    print(f"  总计: {total} | 通过: {passed} | 失败: {failures}")
    print(f"  错误: {errors} | 跳过: {skip_count}")
    print(f"  通过率: {rate:.1f}%")
    print(f"{'='*60}\n")

    if failures:
        print("  失败详情:")
        for test, traceback in result.failures:
            print(f"    ✗ {test}")
            if verbose:
                for line in traceback.split("\n")[:5]:
                    print(f"      {line}")

    if errors:
        print("  错误详情:")
        for test, traceback in result.errors:
            print(f"    ✗ {test}")
            if verbose:
                for line in traceback.split("\n")[:5]:
                    print(f"      {line}")

    return 0 if (failures == 0 and errors == 0) else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
