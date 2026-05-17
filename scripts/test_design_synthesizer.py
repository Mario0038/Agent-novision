#!/usr/bin/env python3
"""
设计参数综合模块测试
=====================
验证 synthesize_design_params() 在 dry_run 模式下的参数补全和来源标记。

不调用 DeepSeek API。
"""

import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.task_planner import plan_task
from modules.design_synthesizer import (
    synthesize_design_params, format_synthesis_result, is_safe_for_synthesis,
)

TEST_SCENARIOS = [
    # (label, user_input, checks)
    (
        "全参数-不应乱改",
        "翼展1200mm、根弦220mm、尖弦130mm、厚度20mm的机翼，6061铝合金",
        {"span_mm": 1200.0, "root_chord_mm": 220.0, "tip_chord_mm": 130.0,
         "thickness_mm": 20.0, "material_name": "Aluminum 6061-T6"},
    ),
    (
        "缺厚度-给出建议",
        "翼展1200mm、根弦220mm的铝合金机翼，做静力分析",
        {"span_mm": 1200.0, "root_chord_mm": 220.0},
    ),
    (
        "缺材料-给出建议",
        "翼展1200mm、根弦220mm、厚度20mm的机翼，根部固定，做静力分析",
        {"span_mm": 1200.0, "root_chord_mm": 220.0, "thickness_mm": 20.0},
    ),
    (
        "静力分析-FEA参数",
        "翼展1200mm的铝合金机翼，根部固定，翼尖加载300N，做静力分析",
        {"analysis_type": ("static_structural", None), "fixed_region": "root",
         "load_region": "tip", "force_N": 300.0},
    ),
    (
        "高风险-应拒绝",
        "设计战斗部结构并做毁伤分析",
        {"blocked": True},
    ),
]

PASS = 0
FAIL = 0

for label, user_input, checks in TEST_SCENARIOS:
    print(f"{'─'*55}")
    print(f"  测试: {label}")
    print(f"  输入: {user_input[:70]}")

    all_ok = True

    if checks.get("blocked"):
        ok = not is_safe_for_synthesis(user_input)
        print(f"    {'✅' if ok else '❌'} is_safe_for_synthesis: {not ok} (预期: False)")
        if ok:
            PASS += 1
        else:
            FAIL += 1
        continue

    plan = plan_task(user_input)
    result = synthesize_design_params(user_input, plan, dry_run=True)

    # Check geometry params
    geo = result.get("geometry", {})
    for key, expected_val in checks.items():
        if key in ("blocked",):
            continue
        entry = geo.get(key) or result.get("material", {}).get(key) or result.get("fea", {}).get(key)

        if isinstance(expected_val, tuple):
            expected_val, _ = expected_val

        if isinstance(entry, dict):
            actual_val = entry.get("value")
            source = entry.get("source", "?")
            if actual_val == expected_val:
                print(f"    ✅ {key}: {actual_val} (source={source})")
            else:
                print(f"    ❌ {key}: {actual_val} != {expected_val} (source={source})")
                all_ok = False
        elif key in ("analysis_type", "fixed_region", "load_region", "force_N"):
            # Check in fea
            fea = result.get("fea", {})
            fe = fea.get(key, {})
            actual_val = fe.get("value") if isinstance(fe, dict) else fe
            if isinstance(expected_val, tuple):
                expected_val, _ = expected_val
            if actual_val == expected_val:
                print(f"    ✅ fea.{key}: {actual_val}")
            else:
                print(f"    ❌ fea.{key}: {actual_val} != {expected_val}")
                all_ok = False

    # Check sources exist
    if geo:
        sources = set()
        for k, v in geo.items():
            if isinstance(v, dict):
                sources.add(v.get("source", "?"))
        print(f"    geometry sources: {sources}")

    # Check material filled
    mat = result.get("material", {})
    if mat:
        print(f"    material keys: {list(mat.keys())}")

    fea = result.get("fea", {})
    if fea:
        print(f"    fea keys: {list(fea.keys())}")

    requires = result.get("requires_confirmation", [])
    if requires:
        print(f"    requires_confirmation: {len(requires)} 项")

    if all_ok:
        print(f"  🏆 {label}: PASS")
        PASS += 1
    else:
        print(f"  ❌ {label}: FAIL")
        FAIL += 1

# Quick format test
print()
print("─" * 55)
print("  格式化输出示例")
print("─" * 55)
plan = plan_task("翼展1200mm的铝合金机翼，根部固定，翼尖加载300N，做静力分析")
result = synthesize_design_params(
    "翼展1200mm的铝合金机翼，根部固定，翼尖加载300N，做静力分析",
    plan, dry_run=True,
)
print(format_synthesis_result(result)[:1200])

print()
print("=" * 55)
print(f"  测试结果: {PASS} PASS / {FAIL} FAIL / {PASS+FAIL} TOTAL")
print("=" * 55)

if FAIL > 0:
    sys.exit(1)
sys.exit(0)
