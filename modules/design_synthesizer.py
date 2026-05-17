#!/usr/bin/env python3
"""
设计参数综合模块
=================
根据用户需求、知识库检索结果和规则提取参数，调用 DeepSeek
生成结构化设计参数建议，并标记每个参数的来源。

来源标记:
  - user_specified:    用户明确给出
  - inferred_from_docs: 根据知识库 + DeepSeek 推断
  - default_value:      系统默认值
  - missing:            仍缺失
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent

# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def synthesize_design_params(
    user_input: str,
    planner_result: dict,
    knowledge_chunks: list[dict] | None = None,
    dry_run: bool = False,
) -> dict:
    """综合设计参数：规则提取 + 知识库 + DeepSeek 补全。

    Args:
        user_input: 用户原始自然语言输入
        planner_result: task_planner.plan_task() 的输出
        knowledge_chunks: doc_search 检索结果（可选）
        dry_run: True=不调用 DeepSeek, 仅用规则参数 + 默认值

    Returns:
        {
            "geometry": {
                "span_mm": {"value": 1200.0, "source": "user_specified", "confidence": "high"},
                ...
            },
            "material": {...},
            "fea": {...},
            "build_mode": "simple_trapezoid",
            "requires_confirmation": ["span_mm (推断)", ...],
        }
    """
    # ── 1. 从 planner 提取已有参数 ──
    base_geo = _merge_geo_params(planner_result)
    base_mat = _merge_material_params(planner_result)
    base_fea = _merge_fea_params(planner_result)
    part_type = planner_result.get("part_type", "unknown")

    # ── 2. 构建知识上下文 ──
    doc_context = _build_doc_context(knowledge_chunks)

    # ── 3. DeepSeek 补全（或 dry_run 回退规则）──
    if dry_run:
        suggestion = _rule_based_fallback(user_input, base_geo, base_mat, base_fea)
    else:
        suggestion = _call_deepseek_synthesize(user_input, base_geo, base_mat,
                                                base_fea, doc_context)

    # ── 4. 合并结果 ──
    merged_geo = _merge_with_source(base_geo, suggestion.get("geometry", {}), "geometry")
    merged_mat = _merge_with_source(base_mat, suggestion.get("material", {}), "material")
    merged_fea = _merge_with_source(base_fea, suggestion.get("fea", {}), "fea")

    # ── 5. 标记需要确认的参数 ──
    requires_confirmation = _find_params_needing_confirmation(
        merged_geo, merged_mat, merged_fea)

    build_mode = suggestion.get("build_mode") or planner_result.get("intent", {}).get(
        "analysis_types", [None])[0] or "simple_trapezoid"

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "build_mode": build_mode if build_mode in ("simple_trapezoid", "loft_airfoil")
                      else "simple_trapezoid",
        "part_type": part_type,
        "geometry": merged_geo,
        "material": merged_mat,
        "fea": merged_fea,
        "requires_confirmation": requires_confirmation,
        "dry_run": dry_run,
    }


# ═══════════════════════════════════════════════════════════
# 参数提取辅助
# ═══════════════════════════════════════════════════════════

def _merge_geo_params(planner: dict) -> dict:
    """从 planner 提取用户明确给出的几何参数。"""
    raw = planner.get("geometry", {})
    out = {}
    keys = [
        "span_mm", "root_chord_mm", "tip_chord_mm",
        "thickness_mm", "sweep_deg", "dihedral_deg",
        "length_mm", "width_mm", "height_mm", "diameter_mm",
        "outer_diameter_mm", "inner_diameter_mm", "hole_diameter_mm",
        "bolt_hole_diameter_mm", "bolt_circle_diameter_mm", "bolt_count",
    ]
    for key in keys:
        val = raw.get(key)
        if val is not None:
            out[key] = val
    return out


def _merge_material_params(planner: dict) -> dict:
    mat = planner.get("material")
    if mat:
        return {"material_name": mat.get("name", "Aluminum 6061-T6")}
    return {}


def _merge_fea_params(planner: dict) -> dict:
    loads = planner.get("loads", [])
    bcs = planner.get("boundary_conditions", [])
    fea_cfg = planner.get("fea_config", {})
    intent = planner.get("intent", {})

    out = {}
    atypes = intent.get("analysis_types", [])
    out["analysis_type"] = atypes[0] if atypes else None
    out["fixed_region"] = bcs[0].get("region") if bcs else "root"
    if loads:
        ld = loads[0]
        out["load_region"] = ld.get("region", "tip")
        out["force_N"] = ld.get("value")
        out["force_direction"] = ld.get("direction", "Z")
    mesh = fea_cfg.get("mesh", {})
    out["mesh_size_mm"] = mesh.get("element_size_mm", 5.0)
    out["result_items"] = fea_cfg.get("result_items", [])
    return out


def _build_doc_context(chunks: list[dict] | None) -> str:
    if not chunks:
        return ""
    parts = []
    for i, c in enumerate(chunks[:5], 1):
        fname = c.get("file_name", "?")
        text = c.get("text", "")[:400]
        parts.append(f"[{i}] {fname}\n{text}")
    return "\n\n---\n\n".join(parts)


# ═══════════════════════════════════════════════════════════
# DeepSeek 调用
# ═══════════════════════════════════════════════════════════

_SYNTHESIZE_SYSTEM_PROMPT = """你是飞行器总体设计专家。请根据用户需求、知识库文献和已有参数，补全设计参数。

## 输出要求

请输出严格 JSON（不要加 markdown 代码块标记），格式如下：

{
  "geometry": {
    "span_mm": {"value": 1200.0, "source": "user_specified", "confidence": "high", "reason": "从输入提取"},
    "root_chord_mm": {"value": 220.0, "source": "user_specified", "confidence": "high"},
    "tip_chord_mm": {"value": 130.0, "source": "inferred_from_docs", "confidence": "medium", "reason": "根梢比0.6来自典型低速机翼"},
    "thickness_mm": {"value": 20.0, "source": "user_specified", "confidence": "high"},
    "sweep_deg": {"value": 0.0, "source": "default_value", "confidence": "high", "reason": "低速机翼通常无后掠"},
    "dihedral_deg": {"value": 0.0, "source": "default_value", "confidence": "medium"}
  },
  "material": {
    "material_name": {"value": "Aluminum 6061-T6", "source": "user_specified", "confidence": "high"},
    "elastic_modulus": {"value": 68900.0, "source": "default_value", "confidence": "medium", "reason": "6061-T6 弹性模量约68.9 GPa"}
  },
  "fea": {
    "analysis_type": {"value": "static_structural", "source": "user_specified", "confidence": "high"},
    "fixed_region": {"value": "root", "source": "user_specified", "confidence": "high"},
    "load_region": {"value": "tip", "source": "user_specified", "confidence": "high"},
    "force_N": {"value": 300.0, "source": "user_specified", "confidence": "high"},
    "force_direction": {"value": "+Z", "source": "user_specified", "confidence": "high"},
    "mesh_size_mm": {"value": 5.0, "source": "default_value", "confidence": "medium"},
    "result_items": {"value": ["total_deformation", "equivalent_stress"], "source": "inferred_from_docs", "confidence": "medium"}
  },
  "build_mode": "simple_trapezoid",
  "design_rationale": "根据用户需求的低速无人机机翼..."
}

## source 说明

- user_specified: 用户输入中明确给出，不要修改
- inferred_from_docs: 根据知识库文献推断，需要用户确认
- default_value: 工程经验默认值，需要用户确认
- missing: 无法推断，必须用户提供

## 材料参考值

- Aluminum 6061-T6: elastic_modulus=68900 MPa, poisson_ratio=0.33, density=2700 kg/m³, yield_strength=276 MPa
- Aluminum 7075-T6: elastic_modulus=71700 MPa, poisson_ratio=0.33, density=2810 kg/m³, yield_strength=503 MPa
- Structural Steel: elastic_modulus=200000 MPa, poisson_ratio=0.30, density=7850 kg/m³, yield_strength=250 MPa
- Titanium Ti-6Al-4V: elastic_modulus=113800 MPa, poisson_ratio=0.34, density=4430 kg/m³, yield_strength=880 MPa

## 重要规则

1. 用户明确给出的值不要修改，source 必须标记为 user_specified
2. 缺失参数可根据知识库和工程经验推断，source 标记为 inferred_from_docs 或 default_value
3. confidence 取值 high/medium/low
4. 每个参数必须包含 value, source, confidence
5. 可为推断参数增加 reason 字段说明依据"""


def _call_deepseek_synthesize(user_input: str, geo: dict, mat: dict,
                               fea: dict, doc_context: str) -> dict:
    """调用 DeepSeek 生成设计参数建议。"""
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(ROOT / ".env")
    api_key = os.getenv("DEEPSEEK_API_KEY")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

    if not api_key:
        return _rule_based_fallback(user_input, geo, mat, fea)

    user_prompt = f"""## 用户输入
{user_input}

## 当前规则提取的参数
geometry: {json.dumps(geo, ensure_ascii=False)}
material: {json.dumps(mat, ensure_ascii=False)}
fea:      {json.dumps(fea, ensure_ascii=False)}

## 知识库相关文献
{doc_context if doc_context else "(无相关文献)"}

请根据以上信息补全设计参数（JSON格式）。"""

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model, temperature=0.2,
            messages=[
                {"role": "system", "content": _SYNTHESIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = resp.choices[0].message.content
        return _parse_deepseek_json(content)
    except Exception as e:
        print(f"  [设计综合] DeepSeek 调用失败: {e}, 回退规则推断")
        return _rule_based_fallback(user_input, geo, mat, fea)


def _parse_deepseek_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*\n?", "", cleaned)
        cleaned = re.sub(r"\n```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


def _rule_based_fallback(user_input: str, geo: dict, mat: dict, fea: dict) -> dict:
    """规则回退：当 DeepSeek 不可用时使用。"""
    suggestion: dict = {"geometry": {}, "material": {}, "fea": {}, "build_mode": "simple_trapezoid"}

    # Geometry defaults
    geo_defaults = {
        "span_mm": 1200, "root_chord_mm": 220, "tip_chord_mm": 132,
        "thickness_mm": 20, "sweep_deg": 0, "dihedral_deg": 0,
    }
    for key, default in geo_defaults.items():
        if key not in geo:
            suggestion["geometry"][key] = {
                "value": default, "source": "default_value", "confidence": "medium"}

    # Material defaults
    mat_name = mat.get("material_name", "Aluminum 6061-T6")
    mat_defaults = {
        "material_name": ("Aluminum 6061-T6", {"E": 68900, "nu": 0.33, "rho": 2700, "yield": 276}),
        "Aluminum 7075-T6": ({"E": 71700, "nu": 0.33, "rho": 2810, "yield": 503}),
        "Structural Steel": ({"E": 200000, "nu": 0.30, "rho": 7850, "yield": 250}),
    }
    props = {"E": 68900, "nu": 0.33, "rho": 2700, "yield": 276}
    for name, p in mat_defaults.items():
        if name.lower() in mat_name.lower():
            props = p if isinstance(p, dict) else p[1]
            break
    if "material_name" not in mat:
        suggestion["material"]["material_name"] = {
            "value": mat_name, "source": "default_value", "confidence": "medium"}
    for pk, pkey in [("elastic_modulus", "E"), ("poisson_ratio", "nu"),
                      ("density", "rho"), ("yield_strength", "yield")]:
        if pk not in mat:
            suggestion["material"][pk] = {
                "value": props[pkey], "source": "default_value", "confidence": "medium"}

    # FEA defaults
    fea_defaults = {
        "analysis_type": "static_structural", "fixed_region": "root",
        "load_region": "tip", "mesh_size_mm": 5.0,
    }
    for key, default in fea_defaults.items():
        if key not in fea:
            suggestion["fea"][key] = {
                "value": default, "source": "default_value", "confidence": "medium"}

    if "result_items" not in fea:
        suggestion["fea"]["result_items"] = {
            "value": ["total_deformation", "equivalent_stress"],
            "source": "default_value", "confidence": "medium"}

    return suggestion


# ═══════════════════════════════════════════════════════════
# 合并 + 来源标记
# ═══════════════════════════════════════════════════════════

def _merge_with_source(base: dict, suggested: dict, category: str) -> dict:
    """合并规则参数和 DeepSeek 建议。"""
    result = {}
    all_keys = set(base.keys()) | set(suggested.keys())
    for key in all_keys:
        sug = suggested.get(key, {})
        base_val = base.get(key)
        if isinstance(sug, dict) and "value" in sug:
            # DeepSeek 已结构化
            if base_val is not None and sug.get("source") == "user_specified":
                result[key] = sug
            elif base_val is not None:
                result[key] = {"value": base_val, "source": "user_specified",
                               "confidence": "high"}
            else:
                result[key] = sug
        elif base_val is not None:
            result[key] = {"value": base_val, "source": "user_specified",
                           "confidence": "high"}
        elif isinstance(sug, dict) and "value" in sug:
            result[key] = sug
        else:
            val = sug.get("value") if isinstance(sug, dict) else sug
            result[key] = {"value": val, "source": "missing", "confidence": "low"}

    return result


def _find_params_needing_confirmation(geo: dict, mat: dict, fea: dict) -> list[str]:
    """找出需要用户确认的参数（推断值或默认值）。"""
    items: list[str] = []
    check_list = [
        ("几何", geo, ["span_mm", "root_chord_mm", "tip_chord_mm", "thickness_mm"]),
        ("材料", mat, ["material_name"]),
        ("FEA", fea, ["force_N", "analysis_type"]),
    ]
    for label, category, keys in check_list:
        for key in keys:
            p = category.get(key, {})
            if isinstance(p, dict) and p.get("source") in (
                    "inferred_from_docs", "default_value"):
                items.append(f"{label}.{key} ({p.get('value')})")
    return items


# ═══════════════════════════════════════════════════════════
# 格式化
# ═══════════════════════════════════════════════════════════

SIMPLE_PARAMS = ["span_mm", "root_chord_mm", "tip_chord_mm", "thickness_mm",
                 "sweep_deg", "dihedral_deg", "build_mode"]


def format_synthesis_result(synth: dict) -> str:
    lines: list[str] = []
    lines.append("## 设计参数综合结果")
    lines.append("")

    # 几何
    geo = synth.get("geometry", {})
    if geo:
        lines.append("### 几何参数")
        for key in SIMPLE_PARAMS:
            entry = geo.get(key)
            if isinstance(entry, dict):
                v, s, c = entry.get("value"), entry.get("source"), entry.get("confidence")
                r = entry.get("reason", "")
                tag = _source_tag(s, c)
                lines.append(f"  {key}: {v}  {tag}")
                if r:
                    lines.append(f"         {r}")
        lines.append("")

    # 材料
    mat = synth.get("material", {})
    if mat:
        lines.append("### 材料参数")
        for key, entry in mat.items():
            if isinstance(entry, dict):
                v, s, c = entry.get("value"), entry.get("source"), entry.get("confidence")
                lines.append(f"  {key}: {v}  {_source_tag(s, c)}")
        lines.append("")

    # FEA
    fea = synth.get("fea", {})
    if fea:
        lines.append("### FEA 参数")
        for key, entry in fea.items():
            if isinstance(entry, dict):
                v, s, c = entry.get("value"), entry.get("source"), entry.get("confidence")
                lines.append(f"  {key}: {v}  {_source_tag(s, c)}")
        lines.append("")

    # 确认清单
    confirm = synth.get("requires_confirmation", [])
    if confirm:
        lines.append("### 需要确认的参数")
        for item in confirm:
            lines.append(f"  ⚠️ {item}")
        lines.append("")
        lines.append("  以下参数将用于建模/仿真，请确认是否执行。")

    lines.append("")
    lines.append(f"  part_type: {synth.get('part_type', 'unknown')}")
    lines.append(f"  build_mode: {synth.get('build_mode', '?')}")
    lines.append(f"  dry_run: {synth.get('dry_run', False)}")

    return "\n".join(lines)


def _source_tag(source: str, confidence: str) -> str:
    icons = {"user_specified": "✓", "inferred_from_docs": "📖",
             "default_value": "⚙️", "missing": "❌"}
    conf_map = {"high": "", "medium": " (需确认)", "low": " (不可靠)"}
    icon = icons.get(source, "?")
    conf = conf_map.get(confidence, "")
    return f"[{icon} {source}{conf}]"


# ═══════════════════════════════════════════════════════════
# 安全过滤（复用 agent_router 逻辑）
# ═══════════════════════════════════════════════════════════

_BLOCKED_KW = [
    "战斗部", "毁伤", "杀伤", "爆破", "穿甲", "破甲",
    "制导打击", "精确打击", "发射部署", "阵地部署", "发射阵地",
    "突防", "反导", "武器化", "武器效能", "引战配合", "引信",
]


def is_safe_for_synthesis(user_input: str) -> bool:
    for kw in _BLOCKED_KW:
        if kw in user_input:
            return False
    return True


if __name__ == "__main__":
    import sys
    from modules.task_planner import plan_task
    test = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "设计翼展1200mm的铝合金机翼，根部固定，翼尖加载300N，做静力分析"
    )
    plan = plan_task(test)
    result = synthesize_design_params(test, plan, dry_run=True)
    print(format_synthesis_result(result))
