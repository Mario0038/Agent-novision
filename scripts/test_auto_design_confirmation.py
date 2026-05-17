#!/usr/bin/env python3
"""
自动设计确认流程测试
=====================
验证 CAD/FEA 路由中 synthesize → confirm → execute 的完整流程。

不调用 SolidWorks。
"""

import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.task_planner import plan_task
from modules.agent_router import route_user_input
from modules.design_synthesizer import (
    synthesize_design_params, format_synthesis_result, is_safe_for_synthesis,
)
from modules.doc_search import search as doc_search

PASS = 0
FAIL = 0

# ── Test 1: CAD route → synthesize → check output ──
print("=" * 55)
print("  Test 1: CAD 路由 → 参数综合")
print("=" * 55)

user_input = "帮我建一个翼展1000mm的机翼三维模型"
route = route_user_input(user_input)
print(f"  route: {route['route']}")
print(f"  reason: {route['reason'][:60]}")

plan = plan_task(user_input)
knowledge = doc_search(user_input, top_k=5)
synth = synthesize_design_params(user_input, plan, knowledge, dry_run=True)

geo = synth.get("geometry", {})
span = geo.get("span_mm", {}).get("value")
source = geo.get("span_mm", {}).get("source")
ok = route["route"] == "cad" and span == 1000.0 and source == "user_specified"
print(f"  span_mm: {span} (source={source})")
print(f"  build_mode: {synth.get('build_mode')}")
print(f"  {'✅ PASS' if ok else '❌ FAIL'}")
PASS += 1 if ok else 0
FAIL += 0 if ok else 1

# ── Test 2: CAD+FEA route → FEA params present ──
print()
print("=" * 55)
print("  Test 2: CAD+FEA 路由 → FEA 参数综合")
print("=" * 55)

user_input2 = "翼展1200mm的铝合金机翼，根部固定，翼尖加载300N，做静力分析"
route2 = route_user_input(user_input2)
plan2 = plan_task(user_input2)
knowledge2 = doc_search(user_input2, top_k=5)
synth2 = synthesize_design_params(user_input2, plan2, knowledge2, dry_run=True)

fea = synth2.get("fea", {})
ok2 = (
    route2["route"] == "cad_fea"
    and fea.get("fixed_region", {}).get("value") == "root"
    and fea.get("load_region", {}).get("value") == "tip"
    and fea.get("force_N", {}).get("value") == 300.0
)
print(f"  route: {route2['route']}")
print(f"  fixed_region: {fea.get('fixed_region', {}).get('value')}")
print(f"  load_region: {fea.get('load_region', {}).get('value')}")
print(f"  force_N: {fea.get('force_N', {}).get('value')}")
print(f"  {'✅ PASS' if ok2 else '❌ FAIL'}")
PASS += 1 if ok2 else 0
FAIL += 0 if ok2 else 1

# ── Test 3: Parameter modification simulation ──
print()
print("=" * 55)
print("  Test 3: 参数修改（模拟）")
print("=" * 55)

# Simulate _apply_param_modification
pending = {
    "geometry": {"thickness_mm": {"value": 20.0, "source": "default_value", "confidence": "medium"}},
    "material": {"material_name": {"value": "Aluminum 6061-T6", "source": "default_value", "confidence": "medium"}},
    "fea": {},
}

# Simulate domain_agent._apply_param_modification
import re
def sim_modify(text, pend):
    m = re.search(r"(?:厚度|thickness)[^\d]*(\d+\.?\d*)", text)
    if m:
        pend.setdefault("geometry", {})["thickness_mm"] = {
            "value": float(m.group(1)), "source": "user_specified", "confidence": "high"}
        return True
    for kw, mat in [("7075", "Aluminum 7075-T6"), ("钛合金", "Titanium Ti-6Al-4V")]:
        if kw in text:
            pend.setdefault("material", {})["material_name"] = {
                "value": mat, "source": "user_specified", "confidence": "high"}
            return True
    return False

ok3a = sim_modify("修改厚度为30mm", pending)
val3a = pending["geometry"]["thickness_mm"]["value"]
print(f"  修改厚度为30mm → thickness={val3a}, source=user_specified: {ok3a and val3a==30.0}")

ok3b = sim_modify("材料改成7075铝合金", pending)
val3b = pending["material"]["material_name"]["value"]
print(f"  材料改成7075 → material={val3b}: {ok3b and '7075' in val3b}")

ok3 = ok3a and ok3b and val3a == 30.0 and "7075" in str(val3b)
print(f"  {'✅ PASS' if ok3 else '❌ FAIL'}")
PASS += 1 if ok3 else 0
FAIL += 0 if ok3 else 1

# ── Test 4: Safety filter ──
print()
print("=" * 55)
print("  Test 4: 安全过滤")
print("=" * 55)

blocked_input = "设计战斗部结构并做毁伤分析"
ok4 = not is_safe_for_synthesis(blocked_input)
print(f"  is_safe('{blocked_input}'): {not ok4} (预期: False)")
print(f"  {'✅ PASS' if ok4 else '❌ FAIL'}")
PASS += 1 if ok4 else 0
FAIL += 0 if ok4 else 1

# ── Test 5: /design_task still works ──
print()
print("=" * 55)
print("  Test 5: /design_task 不受影响")
print("=" * 55)

from modules.design_parser import run_design_task
try:
    result = run_design_task("翼展1000mm的无人机机翼")
    ok5 = "设计对象" in result
    print(f"  /design_task output contains '设计对象': {ok5}")
    print(f"  {'✅ PASS' if ok5 else '❌ FAIL'}")
    PASS += 1 if ok5 else 0
    FAIL += 0 if ok5 else 1
except Exception as e:
    print(f"  ❌ FAIL: {e}")
    FAIL += 1

# ── Summary ──
print()
print("=" * 55)
print(f"  测试结果: {PASS} PASS / {FAIL} FAIL / {PASS+FAIL} TOTAL")
print("=" * 55)

if FAIL > 0:
    sys.exit(1)
sys.exit(0)
