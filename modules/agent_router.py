#!/usr/bin/env python3
"""Route user input to the Agent capability channel.

Routes:
- chat: normal conversation
- rag: knowledge-base retrieval
- cad: safe CAD/design helper flow
- cad_fea: safe CAD + FEA helper flow
- need_more_info: likely executable but missing core parameters
- blocked: safety boundary
"""

from __future__ import annotations

import re


BLOCKED_TERMS = [
    "战斗部", "毁伤", "杀伤", "爆破", "穿甲", "破甲", "引战配合", "引信",
    "发射装置", "发射机构", "发射阵地", "实战部署", "阵地部署",
    "突防", "规避拦截", "诱饵弹", "作战效能", "武器效能",
    "制导算法", "末端制导", "目标锁定", "打击精度提升",
    "推进剂配方", "发动机结构", "喷管设计", "装药",
    "核弹头", "化学弹头", "生物武器",
]

DETAIL_WEAPON_PATTERNS = [
    r"(导弹|火箭弹|制导火箭).*(详细|具体|制造|加工|装配|尺寸|参数|仿真流程|优化)",
    r"(还原|反推).*(内部结构|舱段尺寸|制导部件|发动机)",
    r"(设计|创建|建模).*(导弹|火箭弹|战斗部|发射机构|发动机)",
]

CAD_TERMS = [
    "建模", "SolidWorks", "solidworks", "CAD", "cad", "生成模型", "创建模型",
    "三维模型", "STEP", "SLDPRT", "机翼", "翼型", "翼展", "根弦", "尖弦",
    "矩形板", "平板", "带孔板", "圆柱", "支架", "法兰", "壳体", "盒体",
]

FEA_TERMS = [
    "有限元", "FEA", "fea", "ANSYS", "ansys", "应力", "应变", "变形",
    "位移", "模态", "固有频率", "振型", "静力", "热分析", "热应力",
    "载荷", "约束", "网格", "仿真",
]

RAG_TERMS = [
    "知识库", "文献", "资料", "依据", "参考", "论文", "教材", "书中",
    "检索", "解释", "说明", "对比", "比较", "分类", "流程", "方法",
    "原理", "公式", "结构动力学", "复合材料", "薄壁结构", "疲劳",
    "断裂", "损伤容限", "热结构", "可靠性", "系统工程",
]

CHAT_TERMS = ["你好", "谢谢", "再见", "你是谁", "你能做什么", "hello", "hi", "thanks"]


def _contains_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def _is_blocked(text: str) -> bool:
    return _contains_any(text, BLOCKED_TERMS) or _matches_any(text, DETAIL_WEAPON_PATTERNS)


def route_user_input(user_input: str) -> dict:
    text = user_input.strip()

    if _is_blocked(text):
        return {
            "route": "blocked",
            "reason": (
                "请求涉及敏感武器结构、实现、部署或效能提升边界。"
                "可以改为高层、非操作性的公开资料整理、术语解释或通用工程方法讨论。"
            ),
            "planner_result": None,
            "missing_params": [],
            "requires_confirmation": False,
        }

    if len(text) <= 30 and _contains_any(text, CHAT_TERMS):
        return {
            "route": "chat",
            "reason": "普通对话。",
            "planner_result": None,
            "missing_params": [],
            "requires_confirmation": False,
        }

    has_cad = _contains_any(text, CAD_TERMS)
    has_fea = _contains_any(text, FEA_TERMS)
    if has_cad or has_fea:
        plan = None
        missing: list[str] = []
        try:
            from modules.task_planner import plan_task
            plan = plan_task(text)
            missing = list(plan.get("missing_params", []) or [])
        except Exception:
            plan = None

        if has_cad and "机翼" in text and not any(k in text for k in ("翼展", "span", "长度", "尺寸")):
            missing.append("CAD.span_mm")

        if missing and has_cad:
            return {
                "route": "need_more_info",
                "reason": "识别为工程建模/分析任务，但缺少必要几何或载荷参数。",
                "planner_result": plan,
                "missing_params": sorted(set(missing)),
                "requires_confirmation": True,
            }

        return {
            "route": "cad_fea" if has_cad and has_fea else ("cad" if has_cad else "rag"),
            "reason": "识别为安全工程工具任务。",
            "planner_result": plan,
            "missing_params": missing,
            "requires_confirmation": True,
        }

    if _contains_any(text, RAG_TERMS) or len(text) > 40:
        return {
            "route": "rag",
            "reason": "识别为知识库/资料检索类问题。",
            "planner_result": None,
            "missing_params": [],
            "requires_confirmation": False,
        }

    return {
        "route": "chat",
        "reason": "默认普通对话。",
        "planner_result": None,
        "missing_params": [],
        "requires_confirmation": False,
    }


if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) or "根据知识库说明结构动力学"
    print(route_user_input(query))
