#!/usr/bin/env python3
"""
FEA 任务包生成测试
===================
验证 fea_adapter_ansys 能否从 cad_fea_wing_static.json 生成完整任务包。

不调用 ANSYS，不调用 SolidWorks。
"""

import json
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.fea_adapter_ansys import generate_ansys_task_package

CONFIG_PATH = ROOT / "examples" / "cad_fea_wing_static.json"
OUT_DIR = ROOT / "generated_analysis" / "ansys" / "wing_static_test"

# 使用已有的 STEP 文件（如果不存在则用占位）
STEP_CANDIDATES = [
    ROOT / "generated_models" / "solidworks" / "wing" / "step" / "test_wing_pipeline.STEP",
    ROOT / "generated_models" / "solidworks" / "wing" / "step" / "test_wing_loft.STEP",
]


def run_test() -> int:
    print("=" * 55)
    print("  FEA 任务包生成测试")
    print("=" * 55)

    # ── Step 1: 读取配置 ──
    print(f"\n[1/5] 读取配置: {CONFIG_PATH.name}")
    if not CONFIG_PATH.exists():
        print(f"  ❌ 配置文件不存在: {CONFIG_PATH}")
        return 1
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    fea_cfg = config.get("fea", config)
    print(f"  ✅ 配置读取成功")
    print(f"     analysis_type: {fea_cfg.get('analysis_type', '?')}")
    print(f"     material:      {fea_cfg.get('material', '?')}")
    loads = fea_cfg.get("loads", [])
    bcs = fea_cfg.get("boundary_conditions", [])
    print(f"     loads:         {len(loads)} 项")
    print(f"     constraints:   {len(bcs)} 项")

    # ── Step 2: 选择 STEP ──
    print(f"\n[2/5] 选择 STEP 文件...")
    step_path = None
    for cand in STEP_CANDIDATES:
        if cand.exists():
            step_path = str(cand)
            print(f"  ✅ 使用: {cand.name} ({cand.stat().st_size / 1024:.1f} KB)")
            break
    if step_path is None:
        step_path = str(STEP_CANDIDATES[0])
        print(f"  ⚠️ STEP 文件未找到，将生成占位说明")

    # ── Step 3: 生成任务包 ──
    print(f"\n[3/5] 生成 ANSYS 任务包...")
    if OUT_DIR.exists():
        import shutil
        shutil.rmtree(OUT_DIR)

    result = generate_ansys_task_package(step_path, fea_cfg, str(OUT_DIR))
    print(f"  ✅ 状态: {result['status']}")

    # ── Step 4: 验证文件 ──
    print(f"\n[4/5] 验证输出文件...")
    checks = []

    # 目录检查
    for sub in ["input", "scripts", "results", "figures"]:
        d = OUT_DIR / sub
        ok = d.is_dir()
        checks.append((f"目录 {sub}/", ok))
        print(f"  {'✅' if ok else '❌'} 目录: {d.relative_to(ROOT)}")

    # 文件检查
    file_checks = [
        ("input/geometry.step", OUT_DIR / "input" / "geometry.step"),
        ("input/ansys_static_task.json", OUT_DIR / "input" / "ansys_static_task.json"),
        ("scripts/run_static_mechanical.py", OUT_DIR / "scripts" / "run_static_mechanical.py"),
        ("report.md", OUT_DIR / "report.md"),
    ]
    for label, path in file_checks:
        ok = path.exists() and path.stat().st_size > 0
        checks.append((label, ok))
        size = path.stat().st_size if path.exists() else 0
        print(f"  {'✅' if ok else '❌'} {label} ({size} B)")

    # JSON 字段完整性
    json_path = OUT_DIR / "input" / "ansys_static_task.json"
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        required_fields = [
            "task_id", "generated_at", "solver", "analysis_type",
            "material", "mesh", "boundary_conditions", "loads",
            "result_items", "expected_outputs",
        ]
        json_ok = True
        for field in required_fields:
            has = field in data
            if not has:
                print(f"  ❌ JSON 缺失字段: {field}")
                json_ok = False
        if json_ok:
            print(f"  ✅ ansys_static_task.json 字段完整 ({len(required_fields)} 个必需字段)")
        checks.append(("JSON 字段完整", json_ok))

    # report.md 内容
    report_path = OUT_DIR / "report.md"
    if report_path.exists():
        content = report_path.read_text(encoding="utf-8")
        has_key_sections = all(
            kw in content for kw in ["任务概述", "几何文件", "材料", "边界条件", "载荷", "下一步"]
        )
        checks.append(("report.md 内容完整", has_key_sections))
        print(f"  {'✅' if has_key_sections else '❌'} report.md 包含所有关键章节")

    # 脚本模板内容
    script_path = OUT_DIR / "scripts" / "run_static_mechanical.py"
    if script_path.exists():
        content = script_path.read_text(encoding="utf-8")
        has_steps = all(
            kw in content for kw in ["导入", "Static Structural", "材料", "网格", "固定", "载荷", "求解", "后处理"]
        )
        checks.append(("脚本模板步骤完整", has_steps))
        print(f"  {'✅' if has_steps else '❌'} run_static_mechanical.py 包含 8 个求解步骤")
        # 确认是模板（不包含真实 ANSYS 调用）
        has_todo = "TODO" in content
        print(f"  {'✅' if has_todo else '⚠️'} 脚本为模板（含 TODO 标记）")

    # ── Step 5: 判定 ──
    print(f"\n[5/5] 测试判定...")
    all_ok = all(ok for _, ok in checks)
    print(f"  {'─' * 45}")

    if all_ok:
        print(f"  🏆 结果: PASS")
        print(f"  说明: ANSYS 任务包生成成功，所有文件通过验证。")
        print(f"  输出目录: {OUT_DIR}")
        print(f"  {'─' * 45}")

        # 显示目录树
        print(f"\n  目录结构:")
        for p in sorted(OUT_DIR.rglob("*")):
            if p.is_file():
                rel = p.relative_to(OUT_DIR)
                size = p.stat().st_size
                print(f"    {rel} ({size} B)")

        return 0
    else:
        failed = [label for (label, ok) in checks if not ok]
        print(f"  ❌ 结果: FAIL")
        print(f"  失败项: {', '.join(failed)}")
        print(f"  {'─' * 45}")
        return 1


if __name__ == "__main__":
    sys.exit(run_test())
