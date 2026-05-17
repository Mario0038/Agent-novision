#!/usr/bin/env python3
"""
CAD + FEA 工作流集成测试
=========================
验证从自然语言输入到 ANSYS 任务包生成的全流程闭环。

不调用 ANSYS 求解器。
"""

import json
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.task_planner import plan_task
from modules.workflow_orchestrator import run_workflow

TEST_INPUT = (
    "创建一个翼展1200mm、根弦220mm、尖弦130mm、厚度20mm的低速无人机梯形机翼，"
    "材料为6061铝合金，根部固定，在翼尖施加300N向上力，"
    "进行静力结构分析，输出最大变形和最大等效应力。"
)


def run_test() -> int:
    print("=" * 60)
    print("  CAD + FEA 工作流集成测试")
    print("=" * 60)
    print(f"\n  输入: {TEST_INPUT[:80]}...")
    print()

    # ── Step 1: 任务规划 ──
    print("[1] task_planner.plan_task()")
    plan = plan_task(TEST_INPUT)
    intent = plan.get("intent", {})
    print(f"    cad_required: {intent.get('cad_required')}")
    print(f"    fea_required: {intent.get('fea_required')}")
    print(f"    analysis_types: {intent.get('analysis_types')}")
    print(f"    can_execute_cad: {plan.get('can_execute_cad')}")
    print(f"    material: {(plan.get('material') or {}).get('name', '未指定')}")
    loads = plan.get("loads", [])
    bcs = plan.get("boundary_conditions", [])
    print(f"    loads: {len(loads)} 项, bcs: {len(bcs)} 项")

    # ── Step 2: 工作流编排 ──
    print("\n[2] workflow_orchestrator.run_workflow()")
    text, report = run_workflow(TEST_INPUT)
    print(text)

    # ── Step 3: 验证报告字段 ──
    print("\n[3] 验证 workflow_report 字段...")
    checks = []
    fields = {
        "cad_required": True,
        "cad_step_path": lambda v: v and Path(v).exists(),
        "fea_required": True,
        "fea_status": "task_package_generated",
        "fea_solver": "ansys_mechanical",
        "analysis_type": "static_structural",
        "ansys_task_package_path": lambda v: v and Path(v).is_dir(),
        "ansys_task_json": lambda v: v and Path(v).exists(),
        "ansys_script_path": lambda v: v and Path(v).exists(),
        "report_path": lambda v: v and Path(v).exists(),
    }

    for key, expected in fields.items():
        actual = report.get(key)
        if callable(expected):
            ok = expected(actual)
        else:
            ok = actual == expected
        icon = "✅" if ok else "❌"
        print(f"    {icon} {key}: {repr(actual)[:100]}")
        checks.append(ok)

    # ── Step 4: 验证生成的文件 ──
    print("\n[4] 验证 FEA 任务包文件...")
    pkg = report.get("ansys_task_package_path")
    if pkg:
        expected_files = [
            "input/geometry.step",
            "input/ansys_static_task.json",
            "scripts/run_static_mechanical.py",
            "report.md",
        ]
        for fname in expected_files:
            fp = Path(pkg) / fname
            ok = fp.exists() and fp.stat().st_size > 0
            size = fp.stat().st_size if fp.exists() else 0
            icon = "✅" if ok else "❌"
            print(f"    {icon} {fname} ({size} B)")
            checks.append(ok)

        # 检查 JSON 内容
        json_path = Path(pkg) / "input" / "ansys_static_task.json"
        if json_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8"))
            for field in ["analysis_type", "material", "loads", "boundary_conditions"]:
                ok = field in data
                icon = "✅" if ok else "❌"
                print(f"    {icon} JSON.{field}: {'存在' if ok else '缺失'}")
                checks.append(ok)

    # ── Step 5: 判定 ──
    print("\n[5] 测试判定...")
    all_ok = all(checks)

    print(f"  {'─' * 50}")
    if all_ok:
        print(f"  🏆 结果: PASS")
        print(f"  CAD STEP:  {report.get('cad_step_path')}")
        print(f"  任务包路径: {report.get('ansys_task_package_path')}")
        print(f"  {'─' * 50}")
        print()
        print("  ⚠️ 当前仍未执行真实 ANSYS 求解。")
        print("     任务包已生成，待 PyMAPDL 适配器接入后可启动求解。")
        return 0
    else:
        failed_n = sum(1 for c in checks if not c)
        print(f"  ❌ 结果: FAIL ({failed_n} 项未通过)")
        print(f"  {'─' * 50}")
        return 1


if __name__ == "__main__":
    sys.exit(run_test())
