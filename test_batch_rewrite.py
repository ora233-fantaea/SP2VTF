"""
批量 VPK 测试 + VMT 复写 (sfm2sfm / sf2ems)

流程:
  1. 复制 VPK 到无中文路径
  2. 拆解 → 分类 temp_d/e/n/vmts
  3. 按预设 (sfm2sfm / sf2ems) 重写 VMT
  4. vpk.exe 封包
  5. 验证输出
"""

import json, os, re, shutil, struct, subprocess, sys, time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sp2vtf_vpk_tool import VPKFile, parse_vmt, build_vmt
from sp2vtf_vpk_tool import load_vmt_preset, rewrite_vmt_params

PY = r"C:\Users\CardinalChitanda\anaconda3\envs\left4dead2\python.exe"
VTFCMD = Path(r"E:\vtfcmd\VTFCmd.exe")
VPK_EXE = Path(r"D:\Steam\steamapps\common\Left 4 Dead 2\bin\vpk.exe")

assert VTFCMD.is_file(), f"VTFCmd 不存在: {VTFCMD}"
assert VPK_EXE.is_file(), f"vpk.exe 不存在: {VPK_EXE}"

BASE_TEST = Path(r"C:\sp2vtf_batch_test")

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")
    sys.stdout.flush()

def ensure_dir(d):
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_one_vpk(src_vpk: Path, preset_name: str) -> bool:
    """跑单个 VPK + 单个预设的全流程。返回 True=成功。"""
    stem = src_vpk.stem.replace(" ", "_").replace("{", "").replace("}", "")
    short = stem[:30]

    work = BASE_TEST / f"{stem}_{preset_name}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    copy_vpk = work / "input.vpk"
    palette = {
        "d": ensure_dir(work / "temp_d"),
        "e": ensure_dir(work / "temp_e"),
        "n": ensure_dir(work / "temp_n"),
        "n_png": ensure_dir(work / "temp_n_png"),
        "vmts": ensure_dir(work / "temp_vmts"),
    }

    try:
        # ── 1. 复制 VPK ──
        shutil.copy2(src_vpk, copy_vpk)
        log(f"[{short}] VPK 已复制 ({src_vpk.stat().st_size} bytes)")

        # ── 2. 拆解 ──
        vpk = VPKFile(copy_vpk)
        vmts = vpk.list_vmts()
        log(f"[{short}] VPK 解析: {len(vpk.entries)} 个文件, {len(vmts)} 个 VMT")

        if not vmts:
            log(f"[{short}] 跳过: 无 VMT 文件")
            return False

        # 读取 VMT
        vmt_map = {}
        for vmt_path in vmts:
            dest = vpk.extract(vmt_path, palette["vmts"])
            pure = palette["vmts"] / Path(vmt_path).name
            if dest != pure:
                shutil.copy2(dest, pure)
            params = parse_vmt(pure)
            vn = Path(vmt_path).stem
            vmt_map[vn] = {
                "$basetexture": params.get("$basetexture", ""),
                "$bumpmap": params.get("$bumpmap", ""),
                "$phongexponenttexture": params.get("$phongexponenttexture", ""),
            }

        # 提取纹理并分类
        mat_files = [p for p in vpk.entries
                      if p.startswith("materials/") and not p.endswith(".vmt")]
        classified = {"d": 0, "e": 0, "n": 0}
        for mat_path in mat_files:
            e = vpk.entries.get(mat_path)
            if not e or e["length"] == 0:
                continue
            stem_lower = Path(mat_path).stem.lower()
            for vn, info in vmt_map.items():
                base_s = Path(info["$basetexture"]).stem.lower() if info["$basetexture"] else ""
                bump_s = Path(info["$bumpmap"]).stem.lower() if info["$bumpmap"] else ""
                exp_s = Path(info["$phongexponenttexture"]).stem.lower() if info["$phongexponenttexture"] else ""
                if stem_lower == base_s and base_s:
                    dest = vpk.extract(mat_path, palette["d"])
                    new = palette["d"] / f"{vn}_d.vtf"
                    if dest != new: shutil.copy2(dest, new)
                    classified["d"] += 1; break
                elif stem_lower == bump_s and bump_s:
                    dest = vpk.extract(mat_path, palette["n"])
                    new = palette["n"] / f"{vn}_n.vtf"
                    if dest != new: shutil.copy2(dest, new)
                    classified["n"] += 1; break
                elif stem_lower == exp_s and exp_s:
                    dest = vpk.extract(mat_path, palette["e"])
                    new = palette["e"] / f"{vn}_e.vtf"
                    if dest != new: shutil.copy2(dest, new)
                    classified["e"] += 1; break

        log(f"[{short}] 分类: D={classified['d']} E={classified['e']} N={classified['n']}")

        # 记录未分类的材料文件，稍后原样复制
        classified_set = set()
        for mat_path in mat_files:
            e = vpk.entries.get(mat_path)
            if not e or e["length"] == 0:
                continue
            stem_lower = Path(mat_path).stem.lower()
            for vn, info in vmt_map.items():
                base_s = Path(info["$basetexture"]).stem.lower() if info["$basetexture"] else ""
                bump_s = Path(info["$bumpmap"]).stem.lower() if info["$bumpmap"] else ""
                exp_s = Path(info["$phongexponenttexture"]).stem.lower() if info["$phongexponenttexture"] else ""
                if stem_lower == base_s or stem_lower == bump_s or stem_lower == exp_s:
                    if base_s or bump_s or exp_s:
                        classified_set.add(mat_path)
                        break
        unmatched_mats = [p for p in mat_files if p not in classified_set]
        if unmatched_mats:
            log(f"[{short}] 未分类材料: {len(unmatched_mats)} 个")

        # ── 3. 重写 VMT ──
        preset = load_vmt_preset(preset_name)
        log(f"[{short}] 应用预设: {preset_name}")

        # 生成新 VMT，同时计算新贴图路径映射
        vmt_rewrite_map = {}  # vn -> new_params dict
        rebuilt_vmts = ensure_dir(work / "rebuild_vmts")
        for vn, info in vmt_map.items():
            # 无 SP 导出时 new_base_stem=None，$basetexture 保留原值
            new_params = rewrite_vmt_params(info, preset, vn)
            # 继承原 VMT 预设未覆盖的参数
            orig_vmt_path = palette["vmts"] / f"{vn}.vmt"
            if orig_vmt_path.exists():
                orig = parse_vmt(orig_vmt_path)
                for k, v in orig.items():
                    if k not in new_params:
                        new_params[k] = v
            vmt_text = build_vmt(new_params)
            (rebuilt_vmts / f"{vn}.vmt").write_text(vmt_text, encoding="utf-8")
            vmt_rewrite_map[vn] = new_params

        log(f"[{short}] VMT 复写完成: {len(vmt_map)} 个")

        # ── 4. 封包 ──
        rebuild = work / "rebuild"
        materials = rebuild / "materials"
        for vn, new_params in vmt_rewrite_map.items():
            # 使用重写后的路径（VMT 与 VTF 路径一致）
            new_base = new_params.get("$basetexture", "").replace("\\", "/")
            new_bump = new_params.get("$bumpmap", "").replace("\\", "/")
            new_exp = new_params.get("$phongexponenttexture", "").replace("\\", "/")

            # VMT 写入到新 basetexture 目录
            vmt_dir_part = Path(new_base).parent if new_base else ""
            out_dir = materials / vmt_dir_part
            out_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(rebuilt_vmts / f"{vn}.vmt", out_dir / f"{vn}.vmt")

            # D 贴图 → 新 basetexture 路径
            d_vtf = palette["d"] / f"{vn}_d.vtf"
            if d_vtf.exists() and new_base:
                target = materials / f"{new_base}.vtf"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(d_vtf, target)

            # N 贴图 → 新 bumpmap 路径
            n_vtf = palette["n"] / f"{vn}_n.vtf"
            if n_vtf.exists() and new_bump:
                target = materials / f"{new_bump}.vtf"
                if not target.exists():  # 可能多个 VMT 共享同一个 N
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(n_vtf, target)

            # E 贴图 → 新 exponent 路径
            e_vtf = palette["e"] / f"{vn}_e.vtf"
            if e_vtf.exists() and new_exp:
                target = materials / f"{new_exp}.vtf"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(e_vtf, target)

        # 未分类的材料文件原样复制
        for mat_path in unmatched_mats:
            vpk.extract(mat_path, materials)

        # 非 materials 文件（模型/音效）
        for entry_path in vpk.entries:
            if not entry_path.startswith("materials/"):
                vpk.extract(entry_path, rebuild)

        # addoninfo
        addon = rebuild / "addoninfo.txt"
        if not addon.exists():
            addon.write_text(f'"{stem}"', encoding="utf-8")

        log(f"[{short}] 执行 vpk.exe 封包...")
        result = subprocess.run(
            [str(VPK_EXE), str(rebuild)],
            capture_output=True, text=True, timeout=120,
        )

        expected = rebuild.parent / f"{rebuild.name}.vpk"
        output_vpk = work / "output.vpk"
        if expected.exists():
            shutil.move(str(expected), str(output_vpk))
            sz = output_vpk.stat().st_size
            ok = src_vpk.stat().st_size * 0.3 < sz < src_vpk.stat().st_size * 2.0
            log(f"[{'成功' if ok else '?'}] VPK 生成: {output_vpk} ({sz} bytes, 原={src_vpk.stat().st_size})")
            return ok
        else:
            log(f"[错误] 封包失败, 检查 {rebuild}")
            return False

    except Exception as e:
        log(f"[异常] {short}: {e}")
        import traceback
        for line in traceback.format_exc().split("\n")[-5:]:
            log(f"  {line}")
        return False
    finally:
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)


def main():
    log("=" * 60)
    log("批量 VPK 测试 — VMT 复写验证")
    log("=" * 60)

    vpks = [
        Path(r"D:\Steam\steamapps\common\Left 4 Dead 2\left4dead2\addons\【碧蓝档案】泳装日奈victus xmr (awp).vpk"),
        Path(r"D:\Steam\steamapps\common\Left 4 Dead 2\left4dead2\addons\爱丽丝沙鹰.vpk"),
        Path(r"D:\Steam\steamapps\common\Left 4 Dead 2\left4dead2\addons\{定制}孤独摇滚4渐变spas12v1.2.vpk"),
        Path(r"D:\Steam\steamapps\common\Left 4 Dead 2\left4dead2\addons\爱丽丝scar.vpk"),
    ]
    presets = ["sfm2sfm", "sf2ems"]
    results = {}

    for vpk in vpks:
        if not vpk.is_file():
            log(f"[跳过] 文件不存在: {vpk}")
            continue
        results[vpk.name] = {}
        for preset in presets:
            log(f"\n── {vpk.name} | 预设: {preset} ──")
            ok = test_one_vpk(vpk, preset)
            results[vpk.name][preset] = "✓" if ok else "✗"
            time.sleep(1)  # 避免 vpk.exe 争用

    log("\n" + "=" * 60)
    log("结果汇总")
    log("=" * 60)
    for vpk_name, preset_results in results.items():
        short = vpk_name[:40]
        res = " | ".join(f"{k}={v}" for k, v in preset_results.items())
        log(f"  {short}: {res}")
    log("=" * 60)


if __name__ == "__main__":
    main()
