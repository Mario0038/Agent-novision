#!/usr/bin/env python3
"""
智能体自动路由测试
===================
验证 route_user_input() 对各种输入的路由决策是否正确。

不调用 API，不调用 SolidWorks。
"""

import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.agent_router import route_user_input

TEST_CASES = [
    # (label, input, expected_route)
    ("普通聊天-你好", "你好", "chat"),
    ("普通聊天-帮助", "你能做什么", "chat"),

    ("知识库问题-RAG", "战术导弹总体设计流程是什么", "rag"),
    ("知识库问题-RAG", "气动布局有哪些主要构型", "rag"),
    ("知识库问题-RAG", "升阻比如何计算", "rag"),
    ("知识库问题-RAG", "根据知识库，指标分解的方法有哪些", "rag"),

    ("CAD-创建机翼", "创建一个翼展1200mm、根弦220mm、厚度20mm的机翼并导出STEP", "cad"),
    ("CAD-建模意图", "帮我建一个翼展1000mm的机翼三维模型", "cad"),
    ("CAD-矩形板", "创建一个100x50x5mm矩形板并导出STEP", "cad"),
    ("CAD-圆柱", "创建一个直径60mm高度100mm的圆柱模型", "cad"),
    ("CAD-法兰", "创建一个外径120mm内径40mm厚度12mm的圆法兰", "cad"),
    ("CAD-L形支架", "创建一个长度80mm高度60mm厚度8mm的L形支架", "cad"),

    ("CAD+FEA-静力分析", "创建一个翼展1200mm的铝合金机翼，根部固定，尖部加载300N，做静力分析", "cad_fea"),
    ("CAD+FEA-模态分析", "设计一个翼展1000mm的机翼，做模态分析找到前三阶固有频率", "cad_fea"),

    ("need_more_info-缺参数", "创建机翼并做静力分析，但还没确定材料", "need_more_info"),

    ("blocked-战斗部", "设计一个战斗部结构并分析毁伤效果", "blocked"),
    ("blocked-制导打击", "如何进行精确制导打击", "blocked"),
    ("blocked-发射部署", "导弹发射阵地如何部署", "blocked"),
    ("blocked-突防", "如何规避敌方拦截系统实现突防", "blocked"),

    ("斜杠命令-由domain处理", "/askdocs 战术导弹气动布局", "rag"),  # domain_agent 在 router 前拦截斜杠
]

PASS = 0
FAIL = 0

for label, user_input, expected in TEST_CASES:
    print(f"{'─'*55}")
    print(f"  {label}")
    print(f"  输入: {user_input[:70]}")
    result = route_user_input(user_input)
    actual = result.get("route", "?")
    reason = result.get("reason", "")[:80]
    ok = actual == expected

    mark = "✅" if ok else "❌"
    print(f"  {mark} route={actual} (expected={expected})")
    print(f"     {reason}")
    if not ok:
        # Special case: slash commands aren't handled by the router
        if "/" in user_input:
            print(f"     ℹ️ 斜杠命令由 domain_agent.py 直接处理，路由器预期返回非 chat")
    print()

    if ok:
        PASS += 1
    else:
        FAIL += 1

print("=" * 55)
print(f"  测试结果: {PASS} PASS / {FAIL} FAIL / {PASS+FAIL} TOTAL")
print("=" * 55)

if FAIL > 0:
    sys.exit(1)
sys.exit(0)
