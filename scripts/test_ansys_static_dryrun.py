#!/usr/bin/env python3
"""
ANSYS 静力分析 Dry-run 测试
=============================
验证 execute_static_analysis(dry_run=True) 能否正确生成执行计划，
检查所有前置条件但不启动 ANSYS。

运行方式:
    python scripts/test_ansys_static_dryrun.py
"""

import json
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.fea_adapter_ansys import generate_ansys_task_package, execute_static_analysis

# 找一个已有的任务包目录（按修改时间取最新）
ANALYSIS_ROOT = ROOT / "generated_analysis" / "ansys"


def find_latest_pkg() -> Path | None:
    if not ANALYSIS_ROOT.exists():
        return None
    dirs = sorted(
        [d for d in ANALYSIS_ROOT.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime, reverse=True,
    )
    return dirs[0] if dirs else None


def run_test() -> int:
    print("=" * 55)
    print("  ANSYS 静力分析 Dry-run 测试")
    print("=" * 55)

    checks = []

    # ── Step 1: 确保有任务包 ──
    print("\n[1/5] 准备任务包...")
    pkg_dir = find_latest_pkg()

    if pkg_dir is None:
        print("  未找到已有任务包，创建测试任务包...")
        step_path = ROOT / "generated_models" / "solidworks" / "wing" / "step" / "test_wing_pipeline.STEP"
        fea_cfg = {
            "analysis_type": "static_structural",
            "material": "Aluminum 6061-T6",
            "mesh": {"element_size_mm": 5.0, "element_type": "tet10"},
            "boundary_conditions": [{"type": "fixed_support", "region": "root"}],
            "loads": [{"type": "force", "value_N": 300, "direction": "+Z", "region": "tip"}],
            "result_items": ["total_deformation", "equivalent_stress"],
        }
        out_dir = str(ANALYSIS_ROOT / "wing_static_dryrun_test")
        result = generate_ansys_task_package(str(step_path), fea_cfg, out_dir)
        pkg_dir = Path(result["output_dir"])
        print(f"  任务包: {pkg_dir}")
    else:
        print(f"  使用已有任务包: {pkg_dir}")

    checks.append(("任务包就绪", True))

    # ── Step 2: Dry-run ──
    print("\n[2/5] execute_static_analysis(dry_run=True)...")
    result = execute_static_analysis(str(pkg_dir), dry_run=True)
    status = result.get("status", "?")
    print(f"  状态: {status}")
    checks.append(("Dry-run 完成", status in ("ready", "blocked")))

    # ── Step 3: 检查执行计划 JSON ──
    print("\n[3/5] 验证 execution_plan.json...")
    plan_path = pkg_dir / "results" / "execution_plan.json"
    if plan_path.exists():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        print(f"  ✅ execution_plan.json ({plan_path.stat().st_size} B)")

        # 关键字段
        key_fields = [
            "task_package_dir", "selected_backend", "material",
            "boundary_conditions", "loads", "ready_to_execute",
            "dry_run", "blocking_issues", "planned_steps", "checks",
        ]
        missing = [f for f in key_fields if f not in plan]
        if missing:
            print(f"  ❌ 缺失字段: {missing}")
            checks.append(("执行计划字段完整", False))
        else:
            print(f"  ✅ 所有关键字段存在 ({len(key_fields)} 个)")
            checks.append(("执行计划字段完整", True))

        print(f"\n  计划摘要:")
        print(f"    selected_backend:   {plan.get('selected_backend')}")
        print(f"    material:           {plan.get('material')}")
        print(f"    ready_to_execute:   {plan.get('ready_to_execute')}")
        print(f"    dry_run:            {plan.get('dry_run')}")
        print(f"    blocking_issues:    {plan.get('blocking_issues')}")
        print(f"    planned_steps:      {len(plan.get('planned_steps', []))} 步")
        checks.append(("ready_to_execute 已设置", isinstance(plan.get("ready_to_execute"), bool)))
    else:
        print(f"  ❌ execution_plan.json 未生成")
        checks.append(("执行计划字段完整", False))

    # ── Step 4: 检查 report.md 更新 ──
    print("\n[4/5] 验证 report.md...")
    report_path = pkg_dir / "report.md"
    if report_path.exists():
        content = report_path.read_text(encoding="utf-8")
        has_plan = "## ANSYS 求解执行计划" in content
        has_checks = "### 条件检查" in content
        has_steps = "### 求解步骤" in content
        print(f"  {'✅' if has_plan else '❌'} 执行计划章节")
        print(f"  {'✅' if has_checks else '❌'} 条件检查")
        print(f"  {'✅' if has_steps else '❌'} 求解步骤")
        checks.append(("report.md 已更新", has_plan and has_checks))
    else:
        print(f"  ❌ report.md 不存在")
        checks.append(("report.md 已更新", False))

    # ── Step 5: 判定 ──
    print(f"\n[5/5] 测试判定...")
    all_ok = all(ok for _, ok in checks)
    print(f"  {'─' * 45}")

    if all_ok:
        print(f"  🏆 结果: PASS")
        print(f"  execution_plan:  {plan_path}")
        print(f"  selected_backend: {plan.get('selected_backend')}")
        print(f"  ready_to_execute: {plan.get('ready_to_execute')}")
        if plan.get("blocking_issues"):
            print(f"  blocking_issues:  {plan['blocking_issues']}")
        print(f"  {'─' * 45}")
        print()
        print(f"  ⚠️ Dry-run 模式：执行计划已生成，但未实际启动 ANSYS 求解。")
        if not plan.get("blocking_issues"):
            print(f"  下一步: 调用 execute_static_analysis(dry_run=False) 可进入真实求解。")
        else:
            print(f"  下一步: 先解决阻塞问题，再进入真实求解。")
        return 0
    else:
        failed = [label for label, ok in checks if not ok]
        print(f"  ❌ 结果: FAIL ({', '.join(failed)})")
        print(f"  {'─' * 45}")
        return 1


if __name__ == "__main__":
    sys.exit(run_test())
