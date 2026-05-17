#!/usr/bin/env python3
"""
任务规划器测试 — 验证各种自然语言输入的意图识别和参数提取。

运行方式:
    python scripts/test_task_planner.py
"""

import json
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.task_planner import plan_task, format_task_plan

TEST_CASES = [
    # (label, user_input, expected_intents)
    (
        "纯设计分析",
        "请分析战术导弹总体设计中气动布局和控制系统之间的关系",
        {"design_analysis": True, "cad_required": False, "fea_required": False},
    ),
    (
        "创建机翼并导出STEP",
        "创建一个翼展1200mm、根弦220mm、尖弦130mm、厚度20mm的低速无人机梯形机翼，并导出STEP",
        {"design_analysis": True, "cad_required": True, "fea_required": False},
    ),
    (
        "创建机翼并做静力分析",
        "创建一个翼展1200mm的铝合金机翼，根弦220mm，厚度20mm，根部固定，尖部加载300N，做静力分析",
        {"design_analysis": True, "cad_required": True, "fea_required": True},
    ),
    (
        "创建机翼并做模态分析",
        "设计一个翼展1000mm的铝合金机翼，做模态分析，找到前三阶固有频率",
        {"design_analysis": True, "cad_required": True, "fea_required": True},
    ),
    (
        "缺少材料信息",
        "创建机翼并做静力分析，翼展1200mm，根弦220mm，厚度20mm，根部固定，尖部加载300N",
        {"design_analysis": True, "cad_required": True, "fea_required": True},
    ),
    (
        "缺少载荷信息",
        "创建铝合金机翼并做静力分析，翼展1200mm，根部固定",
        {"design_analysis": True, "cad_required": True, "fea_required": True},
    ),
    (
        "CFD 流场分析",
        "对翼展1200mm的机翼进行CFD气动分析，来流速度20m/s",
        {"design_analysis": True, "cad_required": False, "fea_required": True},
    ),
]

# 额外专项测试：边界条件 + 载荷区域解析
BC_LOAD_TESTS = [
    (
        "根部固定 + 翼尖载荷",
        "创建一个翼展1200mm的铝合金机翼，根部固定，在翼尖施加300N向上力，做静力分析",
        {"fix_region": "root", "load_type": "force", "load_region": "tip", "load_val": 300.0},
    ),
    (
        "翼根固定 + 尖部压力",
        "翼根固定，在尖部施加2MPa压力，分析结构变形",
        {"fix_region": "root", "load_type": "pressure", "load_region": "tip", "load_val": 2.0},
    ),
    (
        "只说固定根部",
        "机翼在根部固定，进行静力分析",
        {"fix_region": "root", "load_count": 0},
    ),
    (
        "只说翼尖施加载荷",
        "在翼尖施加500N力，分析机翼应力",
        {"fix_region": "root", "load_type": "force", "load_region": "tip", "load_val": 500.0},
    ),
]

PASS = 0
FAIL = 0

for label, user_input, expected in TEST_CASES:
    print("─" * 60)
    print(f"  测试: {label}")
    print("─" * 60)
    print(f"  输入: {user_input[:80]}...")
    print()

    plan = plan_task(user_input)
    intent = plan.get("intent", {})

    # 检查核心意图
    checks = []
    for key in expected:
        actual = intent.get(key, False)
        exp = expected[key]
        ok = actual == exp
        checks.append((key, actual, exp, ok))

    # 显示检测结果
    print("  意图检测:")
    all_ok = True
    for key, actual, exp, ok in checks:
        mark = "✅" if ok else "❌"
        print(f"    {mark} {key}: {actual} (期望: {exp})")
        if not ok:
            all_ok = False

    # 显示几何
    geo = plan.get("geometry", {})
    if geo:
        print(f"  几何: {json.dumps(geo, ensure_ascii=False)}")

    # 显示材料
    mat = plan.get("material")
    if mat:
        print(f"  材料: {mat.get('name')}")

    # 显示载荷
    loads = plan.get("loads", [])
    for ld in loads:
        print(f"  载荷: {ld['type']} {ld['value']}{ld['unit']} dir={ld.get('direction','?')}")

    # 显示边界条件
    bcs = plan.get("boundary_conditions", [])
    for bc in bcs:
        print(f"  约束: {bc['type']} @ {bc['region']}")

    # 显示分析类型
    atypes = intent.get("analysis_types", [])
    if atypes:
        print(f"  分析类型: {atypes}")

    # 显示缺失参数
    missing = plan.get("missing_params", [])
    if missing:
        print(f"  缺失参数: {missing}")

    # 检查特定预期
    if "缺少材料信息" in label:
        if "FEA.material" in missing:
            print(f"  ✅ 正确标记缺失材料")
        else:
            print(f"  ❌ 未标记缺失材料 (missing={missing})")
            all_ok = False

    if "缺少载荷信息" in label:
        if "FEA.loads" in missing:
            print(f"  ✅ 正确标记缺失载荷")
        else:
            print(f"  ❌ 未标记缺失载荷 (missing={missing})")
            all_ok = False

    if "模态分析" in label:
        if "modal" in atypes:
            print(f"  ✅ 正确识别模态分析")
        else:
            print(f"  ❌ 未识别模态分析 (atypes={atypes})")
            all_ok = False

    if "CFD" in label:
        if "cfd" in atypes:
            print(f"  ✅ 正确识别 CFD 分析")
        else:
            print(f"  ❌ 未识别 CFD (atypes={atypes})")
            all_ok = False

    if all_ok:
        print(f"\n  🏆 {label}: PASS")
        PASS += 1
    else:
        print(f"\n  ❌ {label}: FAIL")
        FAIL += 1

    print()


# ── 汇总 ──
print("=" * 60)
print(f"  测试结果: {PASS} PASS / {FAIL} FAIL / {PASS + FAIL} TOTAL")
print("=" * 60)

# ── BC/Load 专项测试 ──
BC_PASS = 0
BC_FAIL = 0
print()
print("=" * 60)
print("  边界条件 / 载荷 区域解析专项测试")
print("=" * 60)

for label, user_input, expected in BC_LOAD_TESTS:
    print()
    print(f"  {label}")
    plan = plan_task(user_input)
    bcs = plan.get("boundary_conditions", [])
    loads = plan.get("loads", [])

    bc_ok = True
    if "fix_region" in expected:
        actual_region = bcs[0]["region"] if bcs else "?"
        ok = actual_region == expected["fix_region"]
        bc_ok = bc_ok and ok
        print(f"    {'✅' if ok else '❌'} fixed_support @ {actual_region} (预期: {expected['fix_region']})")

    if "load_region" in expected:
        actual_region = loads[0]["region"] if loads else "?"
        ok = actual_region == expected["load_region"]
        bc_ok = bc_ok and ok
        print(f"    {'✅' if ok else '❌'} load_region={actual_region} (预期: {expected['load_region']})")

    if "load_type" in expected:
        actual_type = loads[0]["type"] if loads else "?"
        ok = actual_type == expected["load_type"]
        bc_ok = bc_ok and ok
        print(f"    {'✅' if ok else '❌'} load_type={actual_type} (预期: {expected['load_type']})")

    if "load_val" in expected:
        actual_val = loads[0]["value"] if loads else 0
        ok = abs(actual_val - expected["load_val"]) < 0.01
        bc_ok = bc_ok and ok
        print(f"    {'✅' if ok else '❌'} load_val={actual_val} (预期: {expected['load_val']})")

    if "load_count" in expected:
        ok = len(loads) == expected["load_count"]
        bc_ok = bc_ok and ok
        print(f"    {'✅' if ok else '❌'} load_count={len(loads)} (预期: {expected['load_count']})")

    if bc_ok:
        BC_PASS += 1
    else:
        BC_FAIL += 1
    print(f"  {'🏆' if bc_ok else '❌'} {label}: {'PASS' if bc_ok else 'FAIL'}")

PASS += BC_PASS
FAIL += BC_FAIL

# 功能清单
print()
print("当前可执行功能:")
print("  ✅ 纯设计分析（不建模）")
print("  ✅ 设计分析 + CAD 建模（simple_trapezoid, 稳定）")
print("  ✅ 设计分析 + CAD 建模（loft_airfoil, fallback 回退）")
print("  ⏳ 设计分析 + CAD 建模 + FEA 静力分析（ANSYS 适配器待实现）")
print("  ⏳ 设计分析 + CAD 建模 + FEA 模态分析（ANSYS 适配器待实现）")
print("  ⏳ 设计分析 + CFD 气动分析（ANSYS Fluent 适配器待实现）")
print()

if FAIL > 0:
    sys.exit(1)
sys.exit(0)
