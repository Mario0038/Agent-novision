#!/usr/bin/env python3
"""
工程设计任务解析模块 — 从自然语言中提取设计对象、目标、约束、工况等结构化信息，
检索知识库，生成结构化设计需求 JSON 和中文方案建议。

当设计参数完整且用户明确要求建模时，可自动调用 SolidWorks 生成机翼实体。
"""

import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
WING_PARAMS_PATH = ROOT / "examples" / "wing_params.json"

# ═══════════════════════════════════════════════════════════
# 设计对象关键词
# ═══════════════════════════════════════════════════════════

DESIGN_OBJECTS = [
    "机翼", "弹翼", "尾翼", "翼面", "舵面",
    "机身", "弹身", "舱段", "整流罩",
    "进气道", "喷管", "尾喷管",
    "起落架", "挂架", "发射架",
    "无人机", "导弹", "飞行器",
    "旋翼", "螺旋桨", "推进器",
    "翼型", "翼剖面",
    "控制面", "操纵面",
    "结构件", "框架", "隔框", "翼肋", "翼梁",
    "整流", "天线罩", "雷达罩",
]

DESIGN_GOALS = [
    "升阻比", "升力系数", "阻力系数", "气动效率",
    "重量", "质量", "减重", "轻量化",
    "强度", "刚度", "模态", "频率",
    "隐身", "RCS", "雷达截面",
    "航程", "射程", "续航", "飞行时间",
    "速度", "机动", "过载",
    "稳定性", "操纵性", "配平",
    "成本", "工艺", "制造",
    "噪声", "振动",
]

# ═══════════════════════════════════════════════════════════
# 参数提取
# ═══════════════════════════════════════════════════════════

def _extract_number_with_unit(text: str, patterns: list[str]) -> list[dict]:
    """提取带单位的数值。"""
    results: list[dict] = []
    for pat in patterns:
        for m in re.finditer(pat, text):
            val = m.group(1)
            unit = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
            results.append({
                "value": val,
                "unit": unit,
                "matched": m.group(0),
                "span": m.span(),
            })
    return results


def extract_design_params(user_input: str) -> dict:
    """从用户输入中提取结构化设计参数。

    Returns:
        {
            design_object: str | None,
            design_goals: [str],
            performance_targets: [dict],
            geometry_constraints: [dict],
            flight_conditions: dict,
            tool_requirements: [str],
            other_requirements: [str],
            unknowns: [str],
            raw_input: str,
        }
    """
    text = user_input

    # ── 设计对象 ──
    design_object = None
    for obj in DESIGN_OBJECTS:
        if obj in text:
            design_object = obj
            break

    # ── 设计目标 ──
    design_goals: list[str] = []
    for goal in DESIGN_GOALS:
        if goal in text:
            design_goals.append(goal)

    # ── 性能指标（速度、升阻比等）──
    performance_targets: list[dict] = []

    # 速度
    speed_patterns = [
        r"(\d+\.?\d*)\s*(?:m/s|米/秒|m·s)",
        r"(\d+\.?\d*)\s*(?:km/h|公里/小时)",
        r"[Mm]a\s*(\d+\.?\d*)",
        r"马赫\s*(\d+\.?\d*)",
        r"巡航速度\s*(\d+\.?\d*)",
        r"最大速度\s*(\d+\.?\d*)",
        r"飞行速度\s*(\d+\.?\d*)",
    ]
    for m in re.finditer("|".join(f"({p})" for p in speed_patterns), text):
        # 简化：找到数值即可
        pass
    # 用更简单的方式
    for pat, label in [
        (r"(\d+\.?\d*)\s*m/s", "speed_m_s"),
        (r"(\d+\.?\d*)\s*km/h", "speed_kmh"),
        (r"[Mm]a\s*(\d+\.?\d*)", "mach"),
        (r"马赫\s*(\d+\.?\d*)", "mach"),
    ]:
        m = re.search(pat, text)
        if m:
            performance_targets.append({
                "parameter": label,
                "value": float(m.group(1)),
                "source": m.group(0),
            })

    # 升阻比
    ld = re.search(r"升阻比[^\d]*(\d+\.?\d*)", text)
    if ld:
        performance_targets.append({
            "parameter": "L/D",
            "value": float(ld.group(1)),
            "source": ld.group(0),
        })
    elif "升阻比" in text:
        performance_targets.append({
            "parameter": "L/D",
            "value": None,
            "goal": "较高",
            "source": "升阻比",
        })

    # 升力系数
    cl = re.search(r"[CcLl][\s_]*(\d+\.?\d*)", text)
    if cl:
        performance_targets.append({
            "parameter": "CL",
            "value": float(cl.group(1)),
            "source": cl.group(0),
        })

    # ── 几何约束 ──
    geometry_constraints: list[dict] = []

    geo_patterns = [
        (r"翼展[^\d]*(\d+\.?\d*)\s*(?:mm|毫米|cm|厘米|米|m)?", "翼展"),
        (r"展长[^\d]*(\d+\.?\d*)\s*(?:mm|毫米|cm|厘米|米|m)?", "展长"),
        (r"根弦[^\d]*(\d+\.?\d*)\s*(?:mm|毫米|cm|厘米|米|m)?", "根弦"),
        (r"尖弦[^\d]*(\d+\.?\d*)\s*(?:mm|毫米|cm|厘米|米|m)?", "尖弦"),
        (r"弦长[^\d]*(\d+\.?\d*)\s*(?:mm|毫米|cm|厘米|米|m)?", "弦长"),
        (r"厚度[^\d]*(\d+\.?\d*)\s*(?:mm|毫米|cm|厘米|米|m)?", "厚度"),
        (r"直径[^\d]*(\d+\.?\d*)\s*(?:mm|毫米|cm|厘米|米|m)?", "直径"),
        (r"长度[^\d]*(\d+\.?\d*)\s*(?:mm|毫米|cm|厘米|米|m)?", "长度"),
        (r"宽度[^\d]*(\d+\.?\d*)\s*(?:mm|毫米|cm|厘米|米|m)?", "宽度"),
        (r"面积[^\d]*(\d+\.?\d*)\s*(?:m²|平米|平方米)?", "面积"),
        (r"展弦比[^\d]*(\d+\.?\d*)", "展弦比"),
        (r"根梢比[^\d]*(\d+\.?\d*)", "根梢比"),
        (r"后掠角[^\d]*(\d+\.?\d*)", "后掠角"),
        (r"不超过\s*(\d+\.?\d*)\s*(?:mm|毫米|cm|厘米|米|m)", "max_dimension"),
        (r"不大于\s*(\d+\.?\d*)\s*(?:mm|毫米|cm|厘米|米|m)", "max_dimension"),
    ]
    for pat, label in geo_patterns:
        m = re.search(pat, text)
        if m:
            geometry_constraints.append({
                "parameter": label,
                "value": float(m.group(1)) if re.match(r"[\d.]+", m.group(1)) else m.group(1),
                "source": m.group(0),
            })

    # ── 工况条件 ──
    flight_conditions: dict = {}

    alt = re.search(r"(?:高度|海拔)[^\d]*(\d+\.?\d*)\s*(?:m|米|km|公里)?", text)
    if alt:
        flight_conditions["altitude"] = {"value": float(alt.group(1)), "source": alt.group(0)}

    reynolds = re.search(r"[Rr]e(?:\s*=\s*|\s+)(\d+\.?\d*[eE]?\d*)", text)
    if reynolds:
        flight_conditions["reynolds"] = {"value": reynolds.group(1), "source": reynolds.group(0)}

    if "海平面" in text:
        flight_conditions["altitude"] = flight_conditions.get("altitude", {"value": 0, "source": "海平面"})
    if "低空" in text:
        flight_conditions.setdefault("altitude", {"value": "< 1000m", "source": "低空"})

    # ── 工具需求 ──
    tool_requirements: list[str] = []
    tool_kw = {
        "SolidWorks": "SolidWorks",
        "solidworks": "SolidWorks",
        "CATIA": "CATIA",
        "Fluent": "Fluent",
        "fluent": "Fluent",
        "ANSYS": "ANSYS",
        "Ansys": "ANSYS",
        "CFD": "CFD",
        "XFOIL": "XFOIL",
        "Xflr5": "Xflr5",
        "AVL": "AVL",
        "OpenVSP": "OpenVSP",
        "MATLAB": "MATLAB",
        "Python": "Python",
    }
    for kw, tool in tool_kw.items():
        if kw in text and tool not in tool_requirements:
            tool_requirements.append(tool)

    # ── 其他约束 ──
    other_requirements: list[str] = []
    if "第一版" in text or "初始" in text or "初步":
        other_requirements.append("初始设计阶段，允许简化假设")
    if "气动" in text and "结构" not in text:
        other_requirements.append("当前阶段仅考虑气动性能")
    if "低速" in text:
        other_requirements.append("低速飞行条件（不可压缩流动假设可能适用）")
    if re.search(r"3[Dd]打印|增材|3D打印", text):
        other_requirements.append("考虑增材制造/3D打印工艺约束")

    # ── 待确认 → 参数 → ──
    unknowns: list[str] = []
    if "翼型" not in text:
        unknowns.append("翼型选择尚未指定")
    if "展弦比" not in text:
        unknowns.append("展弦比尚未指定")
    if "材料" not in text:
        unknowns.append("材料尚未指定")
    if "攻角" not in text and "迎角" not in text:
        unknowns.append("设计工况攻角/迎角尚未指定")
    if "雷诺数" not in text and "Re" not in text:
        unknowns.append("雷诺数条件未明确指定")
    if "结构" not in text and "强度" not in text and "刚度" not in text:
        unknowns.append("结构强度/刚度要求尚未提出")

    return {
        "design_object": design_object,
        "design_goals": design_goals,
        "performance_targets": performance_targets,
        "geometry_constraints": geometry_constraints,
        "flight_conditions": flight_conditions,
        "tool_requirements": tool_requirements,
        "other_requirements": other_requirements,
        "unknowns": unknowns,
        "raw_input": user_input,
    }


# ═══════════════════════════════════════════════════════════
# 知识检索集成
# ═══════════════════════════════════════════════════════════

def search_knowledge(params: dict, top_k: int = 6) -> list[dict]:
    """基于提取的设计参数检索知识库。"""
    # 构建搜索 query
    query_parts: list[str] = []

    obj = params.get("design_object")
    if obj:
        query_parts.append(obj)

    goals = params.get("design_goals", [])
    if goals:
        query_parts.extend(goals[:3])

    # 加入几何约束关键词
    geo = params.get("geometry_constraints", [])
    for g in geo[:3]:
        query_parts.append(g.get("parameter", ""))

    query = " ".join(q for q in query_parts if q)

    if not query:
        return []

    try:
        from modules.doc_search import search as doc_search
        return doc_search(query, top_k=top_k)
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════
# 结构化输出
# ═══════════════════════════════════════════════════════════

def build_design_task(params: dict, knowledge_chunks: list[dict]) -> dict:
    """构建完整的设计任务 JSON。"""
    # 知识来源摘要
    knowledge_sources: list[dict] = []
    for c in knowledge_chunks[:6]:
        knowledge_sources.append({
            "file_name": c.get("file_name", ""),
            "file_type": c.get("file_type", ""),
            "chunk_id": c.get("chunk_id", ""),
            "score": c.get("score", 0),
            "preview": c.get("text", "")[:150],
        })

    # 下一步建议
    next_steps: list[str] = [
        "确认上述未知参数",
        "基于确认后的参数进行初步气动估算（升力线理论/涡格法/XFOIL）",
    ]
    tools = params.get("tool_requirements", [])
    if "SolidWorks" in tools:
        next_steps.append("确认后可进入 SolidWorks 参数化建模")
    if "Fluent" in tools or "CFD" in tools:
        next_steps.append("确认后可进入 CFD 网格生成与求解")
    next_steps.append("根据计算结果迭代优化设计参数")

    task = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "design_object": params.get("design_object", "未明确指定"),
        "mission": params.get("raw_input", ""),
        "performance_targets": params.get("performance_targets", []),
        "geometry_constraints": params.get("geometry_constraints", []),
        "flight_conditions": params.get("flight_conditions", {}),
        "assumptions": params.get("other_requirements", []),
        "unknowns_to_confirm": params.get("unknowns", []),
        "knowledge_sources": knowledge_sources,
        "next_steps": next_steps,
    }

    return task


# ═══════════════════════════════════════════════════════════
# 格式化输出
# ═══════════════════════════════════════════════════════════

def format_design_task(task: dict, params: dict, modeling_result: dict | None = None) -> str:
    """将设计任务格式化为可读的中文输出。"""
    lines: list[str] = []

    lines.append("╔" + "═" * 50 + "╗")
    lines.append("║" + "  工程设计任务解析".center(48) + "║")
    lines.append("╚" + "═" * 50 + "╝")
    lines.append("")

    # ── 1. 设计对象 ──
    lines.append("## 1. 设计对象")
    lines.append(f"   {task.get('design_object', '未指定')}")
    lines.append("")

    # ── 2. 设计目标 ──
    goals = params.get("design_goals", [])
    if goals:
        lines.append("## 2. 设计目标")
        for g in goals:
            lines.append(f"   - {g}")
        lines.append("")

    # ── 3. 性能指标 ──
    perf = task.get("performance_targets", [])
    if perf:
        lines.append("## 3. 性能指标")
        for p in perf:
            val = p.get("value")
            goal = p.get("goal")
            if val is not None:
                lines.append(f"   - {p['parameter']}: {val}  ({p.get('source', '')})")
            elif goal:
                lines.append(f"   - {p['parameter']}: 目标为「{goal}」")
            else:
                lines.append(f"   - {p['parameter']}: 待定量化")
        lines.append("")

    # ── 4. 几何约束 ──
    geo = task.get("geometry_constraints", [])
    if geo:
        lines.append("## 4. 几何约束")
        for g in geo:
            lines.append(f"   - {g['parameter']}: {g['value']}  ({g.get('source', '')})")
        lines.append("")

    # ── 5. 工况条件 ──
    fc = task.get("flight_conditions", {})
    if fc:
        lines.append("## 5. 工况条件")
        for k, v in fc.items():
            if isinstance(v, dict):
                lines.append(f"   - {k}: {v.get('value', '?')}  ({v.get('source', '')})")
            else:
                lines.append(f"   - {k}: {v}")
        lines.append("")

    # ── 6. 假设与前提 ──
    assumptions = task.get("assumptions", [])
    if assumptions:
        lines.append("## 6. 假设与前提")
        for a in assumptions:
            lines.append(f"   - {a}")
        lines.append("")

    # ── 7. 知识库依据 ──
    sources = task.get("knowledge_sources", [])
    lines.append(f"## 7. 知识库依据（共检索到 {len(sources)} 条相关片段）")
    if sources:
        for i, s in enumerate(sources[:6], 1):
            lines.append(f"   [{i}] {s['file_name']}  (相关度: {s['score']:.1f})")
            lines.append(f"       {s['preview'][:120]}…")
        lines.append("")
    else:
        lines.append("   （当前知识库中未找到直接相关的文献片段）")
        lines.append("")

    # ── 8. 需要确认的问题 ──
    unknowns = task.get("unknowns_to_confirm", [])
    if unknowns:
        lines.append("## 8. 需要用户确认的问题")
        for i, u in enumerate(unknowns, 1):
            lines.append(f"   {i}. {u}")
        lines.append("")

    # ── 9. 初始设计思路 ──
    lines.append("## 9. 初始设计思路")
    obj = task.get("design_object", "")
    lines.append(f"   根据设计任务和知识库文献，提出以下初始思路：")
    lines.append("")

    if "机翼" in obj or "翼" in obj:
        lines.append("   a) 翼型初选：")
        lines.append("      根据设计工况（低速/高速/跨声速）从 NACA 系列或")
        lines.append("      专用翼型库中初选 2~3 个候选翼型。")
        lines.append("   b) 平面形状确定：")
        lines.append("      根据展弦比、根梢比、后掠角等参数确定机翼平面形状。")
        lines.append("      低速机翼通常取展弦比 6~12，根梢比 0.4~0.6。")
        lines.append("   c) 气动特性估算：")
        lines.append("      使用升力线理论或涡格法（VLM）初步计算升力系数、")
        lines.append("      诱导阻力、升阻比等关键参数。")
        lines.append("   d) 迭代优化：")
        lines.append("      调整翼型弯度、厚度、扭转角等参数，优化升阻比。")

    elif "机身" in obj or "弹身" in obj:
        lines.append("   a) 外形确定：根据任务需求确定截面形状和纵向轮廓。")
        lines.append("   b) 阻力估算：估算摩擦阻力和压差阻力。")
        lines.append("   c) 容积校核：检查是否能容纳所需设备和载荷。")

    elif "进气道" in obj:
        lines.append("   a) 捕获面积确定：根据发动机流量需求计算。")
        lines.append("   b) 外形设计：选择皮托管式/斜板式/内压式等构型。")
        lines.append("   c) 总压恢复估算：初步估算总压恢复系数。")

    else:
        lines.append("   a) 明确设计需求和约束条件；")
        lines.append("   b) 参考知识库文献中的设计方法和经验公式；")
        lines.append("   c) 进行初步的参数计算和方案对比；")
        lines.append("   d) 确认是否进入 SolidWorks/Fluent 等工具建模。")

    lines.append("")

    # ── 10. 后续步骤 ──
    steps = task.get("next_steps", [])
    if steps:
        lines.append("## 10. 后续步骤")
        for i, s in enumerate(steps, 1):
            lines.append(f"   {i}. {s}")
        lines.append("")

    # ── 11. SolidWorks 建模结果（如有）──
    if modeling_result is not None:
        lines.append(_format_modeling_result(modeling_result))

    # ── JSON 摘要 ──
    lines.append("─" * 52)
    lines.append("## 结构化任务 JSON（摘要）")
    json_str = json.dumps(task, ensure_ascii=False, indent=2)
    # 截取前 2000 字符
    if len(json_str) > 2000:
        json_str = json_str[:2000] + "\n… (JSON 已截断，完整数据可通过 /design_task 内部获取)"
    lines.append(json_str)
    lines.append("─" * 52)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# 机翼参数映射与 SolidWorks 执行
# ═══════════════════════════════════════════════════════════

# 识别为 SolidWorks 建模任务的关键词
_MODELING_INTENT_KW = [
    "导出STEP", "导出 STP", "导出step", "生成STEP",
    "SolidWorks", "solidworks", "建模", "创建…模型", "生成模型",
    "生成 SLDPRT", "创建实体", "自动建模", "参数化建模",
    "CAD 模型", "CAD模型", "三维模型", "3D 模型", "3D模型",
    "画出", "画一个", "帮我建", "建一个",
]

# 将几何约束参数映射到 wing_params.json 字段
_GEO_TO_WING_KEY = {
    "翼展": "span_mm",
    "展长": "span_mm",
    "弦长": "root_chord_mm",
    "根弦": "root_chord_mm",
    "尖弦": "tip_chord_mm",
    "厚度": "thickness_mm",
    "后掠角": "sweep_deg",
    "上反角": "dihedral_deg",
    "展弦比": "aspect_ratio",
    "根梢比": "taper_ratio",
}

# 中文 → 安全英文文件名片段映射
_CN_TO_EN_FILE = {
    "机翼": "wing",
    "尾翼": "tail",
    "机身": "fuselage",
    "弹身": "body",
    "弹翼": "fin",
    "进气道": "inlet",
    "喷管": "nozzle",
    "旋翼": "rotor",
    "螺旋桨": "propeller",
    "起落架": "landing_gear",
    "翼型": "airfoil",
    "舵面": "control_surface",
    "整流罩": "fairing",
    "无人机": "uav",
    "导弹": "missile",
    "飞行器": "vehicle",
}


def sanitize_output_name(raw: str) -> str:
    """清理文件名，只保留 A-Z a-z 0-9 _ -

    规则：
    1. 中文关键词映射为英文片段（如 机翼→wing）
    2. 保留英文字母、数字、下划线、短横线
    3. 去除空格、中文、特殊符号
    4. 多个连续下划线/短横线合并为一个
    5. 去除首尾下划线和短横线
    6. 结果为空则返回 wing_design

    Args:
        raw: 原始输出名（可能含中文）

    Returns:
        安全文件名，如 design_task_wing
    """
    # Step 1: 中文关键词映射
    result = raw
    for cn, en in _CN_TO_EN_FILE.items():
        result = result.replace(cn, en)

    # Step 2: 只保留安全字符，其余替换为下划线
    safe_chars: list[str] = []
    for ch in result:
        if ch.isascii() and (ch.isalnum() or ch in "_-"):
            safe_chars.append(ch)
        else:
            safe_chars.append("_")

    result = "".join(safe_chars)

    # Step 3: 合并连续下划线和短横线
    result = re.sub(r"_{2,}", "_", result)
    result = re.sub(r"-{2,}", "-", result)
    result = re.sub(r"_-_", "_", result)
    result = re.sub(r"_-", "_", result)
    result = re.sub(r"-_", "_", result)

    # Step 4: 去除首尾特殊字符
    result = result.strip("_-")

    # Step 5: 不以数字开头
    if result and result[0].isdigit():
        result = "wing_" + result

    # Step 6: 兜底
    if not result:
        result = "wing_design"

    return result


def _detect_airfoil_code(text: str, position: str = "root") -> str | None:
    """从用户输入中检测 NACA 翼型代码。"""
    # 匹配 NACA 后跟 4 位数字
    matches = re.findall(r"NACA\s*(\d{4})", text, re.IGNORECASE)
    if not matches:
        matches = re.findall(r"(?<!\d)(\d{4})(?:\s*翼型)?", text)
        # 过滤非翼型数字
        matches = [m for m in matches if 0 < int(m[:2]) <= 99 and 0 < int(m[2:]) <= 50]

    if not matches:
        return None
    if position == "tip" and len(matches) >= 2:
        return f"NACA{matches[1]}"
    return f"NACA{matches[0]}"


def _detect_modeling_intent(text: str) -> bool:
    """检测用户是否明确要求 SolidWorks 建模/导出。"""
    for kw in _MODELING_INTENT_KW:
        if kw.lower() in text.lower():
            return True
    return False


def _map_geo_to_wing_params(params: dict) -> dict | None:
    """从 geometry_constraints 提取 wing_params.json 所需字段。

    仅当 span + root_chord + thickness 都存在时才返回有效 dict。
    弦长单位统一为 mm（如果用户用了 m 或 cm 则转换）。
    """
    geo_list = params.get("geometry_constraints", [])
    if not geo_list:
        return None

    wing: dict = {}
    for g in geo_list:
        key = _GEO_TO_WING_KEY.get(g.get("parameter", ""))
        if key and g.get("value") is not None:
            try:
                val = float(g["value"])
            except (ValueError, TypeError):
                continue
            # 单位检测：如果源文本中包含 "m" 但不是 "mm"，可能是米
            src = g.get("source", "")
            if "mm" in src or "毫米" in src:
                pass  # 已是 mm
            elif "cm" in src or "厘米" in src:
                val *= 10
            elif re.search(r"(?<!\d)m[\s,，。、；:]", src) or src.endswith("m"):
                # 单独的 m（非 mm 的一部分）
                if "mm" not in src:
                    val *= 1000
            wing[key] = val

    # 检查必需参数
    if "span_mm" not in wing or "root_chord_mm" not in wing or "thickness_mm" not in wing:
        return None

    # 填充默认值
    wing.setdefault("tip_chord_mm", wing.get("root_chord_mm", 200) * 0.6)
    wing.setdefault("sweep_deg", 0.0)
    wing.setdefault("dihedral_deg", 0.0)
    wing.setdefault("twist_root_deg", 0.0)
    wing.setdefault("twist_tip_deg", 0.0)
    wing.setdefault("airfoil_name", "simple_trapezoid")

    # 检测 build_mode：如果提到 NACA 或翼型放样，使用 loft_airfoil
    raw_input = params.get("raw_input", "")
    if re.search(r"NACA|翼型放样|loft|放样|真实翼型", raw_input, re.IGNORECASE):
        wing.setdefault("build_mode", "loft_airfoil")
        wing.setdefault("root_airfoil", _detect_airfoil_code(raw_input, "root") or "NACA2412")
        wing.setdefault("tip_airfoil", _detect_airfoil_code(raw_input, "tip") or "NACA0012")
    else:
        wing.setdefault("build_mode", "simple_trapezoid")

    # 生成输出名（始终使用安全文件名）
    raw_obj = params.get("design_object") or "wing"
    raw_name = f"design_task_{raw_obj}"
    wing["output_name"] = sanitize_output_name(raw_name)

    return wing


def _write_wing_params(wing: dict) -> Path:
    """将机翼参数写入 examples/wing_params.json。"""
    WING_PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WING_PARAMS_PATH.write_text(
        json.dumps(wing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return WING_PARAMS_PATH


def _verify_output_files(wing_params: dict) -> dict:
    """检查 SLDPRT 和 STEP 文件是否存在且大小 > 0。

    Returns:
        {"sldprt": {"path": str, "exists": bool, "size_kb": float},
         "step":  {"path": str, "exists": bool, "size_kb": float}}
    """
    output_name = wing_params.get("output_name", "design_task_wing")
    parts_dir = ROOT / "generated_models" / "solidworks" / "wing" / "parts"
    step_dir = ROOT / "generated_models" / "solidworks" / "wing" / "step"

    sldprt_path = parts_dir / f"{output_name}.SLDPRT"
    step_path = step_dir / f"{output_name}.STEP"

    def _check(p: Path) -> dict:
        if p.exists():
            size = p.stat().st_size
            return {"path": str(p), "exists": True, "size_kb": round(size / 1024, 1)}
        return {"path": str(p), "exists": False, "size_kb": 0.0}

    return {"sldprt": _check(sldprt_path), "step": _check(step_path)}


def _try_execute_wing_model(wing_params: dict) -> dict:
    """尝试调用 SolidWorks 生成机翼模型。

    即使建模调用超时或异常，也会检查输出文件是否已生成。

    Returns:
        status 取值:
          - "success"    : 建模正常完成，文件已验证
          - "partial"    : 建模过程报错/超时/返回 None，但文件已生成
          - "failed"     : 建模失败，文件未生成
    """
    process_error: str | None = None
    result = None

    # Step 1: 尝试导入
    try:
        from modules.solidworks_wing_builder import build_trapezoidal_wing
    except ImportError as e:
        return {
            "status": "failed",
            "error": f"无法导入建模模块: {e}",
            "hint": "请确认 modules/solidworks_wing_builder.py 存在且 pywin32 已安装。",
            "files": _verify_output_files(wing_params),
        }

    # Step 2: 调用建模（无内置超时，依赖 SolidWorks 自身响应）
    try:
        result = build_trapezoidal_wing(
            span_mm=wing_params.get("span_mm", 1200),
            root_chord_mm=wing_params.get("root_chord_mm", 220),
            tip_chord_mm=wing_params.get("tip_chord_mm", 130),
            thickness_mm=wing_params.get("thickness_mm", 20),
            sweep_deg=wing_params.get("sweep_deg", 0),
            dihedral_deg=wing_params.get("dihedral_deg", 0),
            twist_root_deg=wing_params.get("twist_root_deg", 0),
            twist_tip_deg=wing_params.get("twist_tip_deg", 0),
            airfoil_name=wing_params.get("airfoil_name", "simple_trapezoid"),
            output_name=wing_params.get("output_name", "design_task_wing"),
            build_mode=wing_params.get("build_mode", "simple_trapezoid"),
            root_airfoil=wing_params.get("root_airfoil", "NACA2412"),
            tip_airfoil=wing_params.get("tip_airfoil", "NACA0012"),
        )
    except Exception as e:
        process_error = str(e)

    # Step 3: 验证输出文件
    files = _verify_output_files(wing_params)
    sldprt_ok = files["sldprt"]["exists"] and files["sldprt"]["size_kb"] > 0
    step_ok = files["step"]["exists"] and files["step"]["size_kb"] > 0
    files_exist = sldprt_ok and step_ok

    sldprt_path = files["sldprt"]["path"]
    step_path = files["step"]["path"]

    # Step 4: 判定最终状态
    if result is not None and not process_error:
        # 正常返回
        if files_exist:
            return {
                "status": "success",
                "sldprt": sldprt_path,
                "step": step_path,
                "params": wing_params,
                "files": files,
                "build_actual_mode": result.get("build_actual_mode", result.get("build_mode", "?")),
            }
        else:
            return {
                "status": "partial",
                "sldprt": sldprt_path,
                "step": step_path,
                "params": wing_params,
                "files": files,
                "error": "建模函数返回成功但输出文件未生成或为空",
                "hint": "请检查 SolidWorks 写入权限和磁盘空间。",
            }

    # 建模异常或返回 None
    if files_exist:
        reason = process_error or "建模函数返回 None（可能超时）"
        return {
            "status": "partial",
            "sldprt": sldprt_path,
            "step": step_path,
            "params": wing_params,
            "files": files,
            "error": f"{reason}，但输出文件已成功生成",
            "hint": "文件已可用，可在 SolidWorks 中打开验证完整性。",
        }

    # 完全失败
    hint = "请确认 SolidWorks 已打开。若未安装，跳过此步骤，手动在 CAD 中建模。"
    if process_error:
        hint = f"异常: {process_error[:120]}。{hint}"
    return {
        "status": "failed",
        "error": process_error or "建模函数返回 None（连接 SolidWorks 失败或建模中断）。",
        "hint": hint,
        "files": files,
    }


def _format_modeling_result(model_result: dict) -> str:
    """格式化建模执行结果（三种状态）。"""
    lines: list[str] = []
    lines.append("## 11. SolidWorks 建模执行结果")
    lines.append("")

    status = model_result.get("status", "failed")
    files = model_result.get("files", {})

    # ── 文件验证信息 ──
    def _file_line(label: str, info: dict):
        if info.get("exists"):
            return f"  {label}: {info['path']}  ({info['size_kb']} KB)  ✅"
        return f"  {label}: {info['path']}  ❌ 未生成"

    if status == "success":
        actual_mode = model_result.get("build_actual_mode", "?")
        if actual_mode == "fallback_extrude":
            lines.append("  ⚠️ Loft 放样未成功，已回退为 NACA 等弦长拉伸实体。")
            lines.append("")
            lines.append("  当前模型为有效 STEP 几何，但未包含根梢翼型变化、")
            lines.append("  后掠、上反和扭转的真实放样效果。")
        else:
            lines.append("  ✅ 建模成功，文件已验证。")
        lines.append("")
        lines.append(_file_line("SLDPRT", files.get("sldprt", {})))
        lines.append(_file_line("STEP", files.get("step", {})))
        lines.append("")
        lines.append("  可在 SolidWorks 中打开 SLDPRT 查看/编辑模型。")

    elif status == "partial":
        lines.append("  ⚠️ 文件已生成但进程超时/异常。")
        lines.append(f"  原因: {model_result.get('error', '未知')}")
        lines.append("")
        lines.append(_file_line("SLDPRT", files.get("sldprt", {})))
        lines.append(_file_line("STEP", files.get("step", {})))
        lines.append("")
        lines.append(f"  💡 {model_result.get('hint', '请在 SolidWorks 中验证模型完整性。')}")

    else:  # failed
        lines.append(f"  ❌ 建模失败: {model_result.get('error', '未知错误')}")
        lines.append("")
        # 仍然显示文件状态
        if files:
            lines.append(_file_line("SLDPRT", files.get("sldprt", {})))
            lines.append(_file_line("STEP", files.get("step", {})))
        lines.append("")
        lines.append(f"  💡 {model_result.get('hint', '请检查 SolidWorks 连接。')}")
        lines.append("")
        lines.append("  你可以：")
        lines.append("  1. 手动打开 SolidWorks 后重试 /design_task")
        lines.append("  2. 手动运行 python scripts/create_wing_model.py")
        lines.append("  3. 使用其他 CAD 软件根据上述参数手动建模")

    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def run_design_task(user_input: str) -> str:
    """完整的设计任务解析流程，返回格式化文本。

    当用户明确要求 SolidWorks 建模且参数完整时，自动执行建模。
    """
    # 1. 提取参数
    params = extract_design_params(user_input)

    # 2. 检索知识库
    knowledge = search_knowledge(params)

    # 3. 构建结构化任务
    task = build_design_task(params, knowledge)

    # 4. 检测是否需要并能够执行 SolidWorks 建模
    modeling_result = None
    if _detect_modeling_intent(user_input):
        wing = _map_geo_to_wing_params(params)
        if wing is not None:
            _write_wing_params(wing)
            modeling_result = _try_execute_wing_model(wing)
            if modeling_result:
                status = modeling_result.get("status", "failed")
                if status in ("success", "partial"):
                    task["next_steps"].append(
                        f"SolidWorks 模型已生成: {modeling_result.get('step', '')}"
                    )
                task["modeling_result"] = status

    # 5. 格式化输出
    return format_design_task(task, params, modeling_result)


if __name__ == "__main__":
    import sys
    test_input = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "请基于知识库资料，设计一个低速无人机机翼，翼展不超过1.2m，"
        "巡航速度20m/s，目标是升阻比较高，第一版只考虑气动性能。"
    )
    print(run_design_task(test_input))
