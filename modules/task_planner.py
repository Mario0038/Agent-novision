#!/usr/bin/env python3
"""
任务规划器 — 从自然语言输入中判断设计/建模/分析意图，
提取几何、材料、载荷、边界条件参数，输出结构化任务计划。

不调用任何 API 或外部求解器。
"""

import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent

# ═══════════════════════════════════════════════════════════
# 意图检测关键词
# ═══════════════════════════════════════════════════════════

_DESIGN_ONLY_KW = ["分析", "设计思路", "方案", "对比", "报告", "综述", "总结"]

_CAD_KW = [
    "建模", "SolidWorks", "solidworks", "CAD", "cad",
    "生成模型", "创建", "三维模型", "3D模型", "3D 模型",
    "导出STEP", "导出STP", "导出 SLDPRT", "SLDPRT",
    "参数化", "画一个", "建一个",
    "翼展", "根弦", "尖弦", "翼型", "机翼", "几何",
    "矩形板", "平板", "板件", "圆柱", "圆筒", "法兰", "支架", "L形", "L 型",
    "壳体", "盒体", "箱体", "轴套",
]

_FEA_KW = [
    "有限元", "FEA", "fea", "ANSYS", "ansys",
    "应力", "应变", "变形", "位移", "模态", "频率", "振型",
    "静力", "静力学", "结构分析", "强度分析", "刚度分析",
    "热分析", "热应力", "温度场", "热传导",
    "CFD", "cfd", "流场", "气动分析",
    "载荷", "加载", "受力", "固定", "约束",
]

_ANALYSIS_TYPE_MAP = {
    "静力": "static_structural", "静力学": "static_structural",
    "结构分析": "static_structural", "强度": "static_structural",
    "应力": "static_structural", "应变": "static_structural",
    "变形": "static_structural", "位移": "static_structural",
    "模态": "modal", "频率": "modal", "振型": "modal",
    "固有频率": "modal",
    "热": "thermal", "温度": "thermal", "热应力": "thermal_structural",
    "热传导": "thermal",
    "CFD": "cfd", "流场": "cfd", "气动": "cfd",
}

_MATERIAL_MAP = {
    "铝合金": "Aluminum 6061-T6",
    "铝": "Aluminum 6061-T6",
    "6061": "Aluminum 6061-T6",
    "7075": "Aluminum 7075-T6",
    "钢": "Structural Steel",
    "结构钢": "Structural Steel",
    "不锈钢": "Stainless Steel 304",
    "钛合金": "Titanium Ti-6Al-4V",
    "钛": "Titanium Ti-6Al-4V",
    "碳纤维": "Carbon Fiber UD Prepreg",
    "ABS": "ABS Plastic",
    "PLA": "PLA",
    "尼龙": "Nylon 6",
}


# ═══════════════════════════════════════════════════════════
# 主解析函数
# ═══════════════════════════════════════════════════════════

def plan_task(user_input: str) -> dict:
    """解析用户自然语言，输出结构化任务计划。

    Returns:
        {
            task_id: str,
            raw_input: str,
            intent: {
                design_analysis: bool,
                cad_required: bool,
                fea_required: bool,
                analysis_types: [str],
            },
            geometry: dict,
            material: dict | None,
            loads: [dict],
            boundary_conditions: [dict],
            fea_config: dict,
            missing_params: [str],
            can_execute_cad: bool,
            can_execute_fea: bool,
            recommend_commands: [str],
        }
    """
    text = user_input
    part_type = _detect_part_type(text)

    # ── 1. 意图检测 ──
    design_analysis = True  # always true as baseline
    cad_required = _detect_keywords(text, _CAD_KW)
    fea_required = _detect_keywords(text, _FEA_KW)

    # 补充: 有几何参数 + "设计一个/做一个/建一个" → 视为 CAD 意图
    if not cad_required:
        geo = _extract_geometry(text)
        if len(geo) >= 1 and re.search(r"设计一个|做一个|建一个", text):
            cad_required = True

    # 纯设计分析：无 CAD 无 FEA 关键词
    if not cad_required and not fea_required:
        for kw in _DESIGN_ONLY_KW:
            if kw in text:
                design_analysis = True
                break

    # ── 2. 分析类型 ──
    analysis_types = _detect_analysis_types(text)

    # ── 3. 几何参数 ──
    geometry = _extract_geometry(text)

    # ── 4. 材料 ──
    material = _extract_material(text)

    # ── 5. 载荷 ──
    loads = _extract_loads(text)

    # ── 6. 边界条件 ──
    bcs = _extract_boundary_conditions(text)

    # ── 7. FEA 配置 ──
    fea_config = _build_fea_config(analysis_types, material, loads, bcs)

    # ── 8. 缺失参数 ──
    missing = _check_missing(cad_required, fea_required, part_type, geometry, material,
                             loads, bcs, analysis_types)

    # ── 9. 可执行性 ──
    can_execute_cad = cad_required and _can_execute_cad(part_type, geometry)
    can_execute_fea = False  # FEA solver not yet integrated

    # ── 10. 建议命令 ──
    recommends: list[str] = []
    if can_execute_cad:
        recommends.append("/design_task " + user_input[:80])
    if fea_required:
        recommends.append("FEA 分析任务已生成计划，等待 ANSYS 适配器实现")
    if missing:
        recommends.append(f"请补充缺失参数: {', '.join(missing[:5])}")

    return {
        "task_id": datetime.now().strftime("TASK-%Y%m%d-%H%M%S"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw_input": user_input,
        "part_type": part_type,
        "intent": {
            "design_analysis": design_analysis,
            "cad_required": cad_required,
            "fea_required": fea_required,
            "analysis_types": analysis_types,
        },
        "geometry": geometry,
        "material": material,
        "loads": loads,
        "boundary_conditions": bcs,
        "fea_config": fea_config,
        "missing_params": missing,
        "can_execute_cad": can_execute_cad,
        "can_execute_fea": can_execute_fea,
        "recommend_commands": recommends,
    }


# ═══════════════════════════════════════════════════════════
# 子检测函数
# ═══════════════════════════════════════════════════════════

def _detect_keywords(text: str, keywords: list[str]) -> bool:
    for kw in keywords:
        if kw.lower() in text.lower():
            return True
    return False


def _detect_analysis_types(text: str) -> list[str]:
    types: list[str] = []
    for kw, atype in _ANALYSIS_TYPE_MAP.items():
        if kw in text and atype not in types:
            types.append(atype)
    if not types and _detect_keywords(text, _FEA_KW):
        types.append("static_structural")  # default
    return types


def _extract_geometry(text: str) -> dict:
    """提取结构化几何参数（mm 单位）。"""
    geo: dict = {}

    patterns = [
        (r"翼展\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "span_mm"),
        (r"展长\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "span_mm"),
        (r"根弦\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "root_chord_mm"),
        (r"尖弦\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "tip_chord_mm"),
        (r"弦长\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "root_chord_mm"),
        (r"厚度\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "thickness_mm"),
        (r"壁厚\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "thickness_mm"),
        (r"板厚\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "thickness_mm"),
        (r"(\d+\.?\d*)\s*(?:mm|毫米)?\s*(?:厚|厚度|壁厚|板厚)", "thickness_mm"),
        (r"后掠角?\s*(\d+\.?\d*)\s*(?:°|deg|度)?", "sweep_deg"),
        (r"上反角?\s*(\d+\.?\d*)\s*(?:°|deg|度)?", "dihedral_deg"),
        (r"长度\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "length_mm"),
        (r"长\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "length_mm"),
        (r"(\d+\.?\d*)\s*(?:mm|毫米)?\s*长", "length_mm"),
        (r"宽度\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "width_mm"),
        (r"宽\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "width_mm"),
        (r"(\d+\.?\d*)\s*(?:mm|毫米)?\s*宽", "width_mm"),
        (r"高度\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "height_mm"),
        (r"高\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "height_mm"),
        (r"(\d+\.?\d*)\s*(?:mm|毫米)?\s*高", "height_mm"),
        (r"直径\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "diameter_mm"),
        (r"(\d+\.?\d*)\s*(?:mm|毫米)?\s*直径", "diameter_mm"),
        (r"外径\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "outer_diameter_mm"),
        (r"(\d+\.?\d*)\s*(?:mm|毫米)?\s*外径", "outer_diameter_mm"),
        (r"内径\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "inner_diameter_mm"),
        (r"(\d+\.?\d*)\s*(?:mm|毫米)?\s*内径", "inner_diameter_mm"),
        (r"孔径\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "hole_diameter_mm"),
        (r"中心孔\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "hole_diameter_mm"),
        (r"安装孔\s*(\d+\.?\d*)\s*(?:mm|毫米)?", "hole_diameter_mm"),
        (r"(\d+\.?\d*)\s*(?:mm|毫米)?\s*(?:孔径|中心孔|安装孔)", "hole_diameter_mm"),
    ]
    for pat, key in patterns:
        m = re.search(pat, text)
        if m and key not in geo:
            geo[key] = float(m.group(1))

    dim3 = re.search(
        r"(\d+\.?\d*)\s*(?:x|X|×|\*)\s*(\d+\.?\d*)\s*(?:x|X|×|\*)\s*(\d+\.?\d*)\s*(?:mm|毫米)?",
        text,
    )
    if dim3:
        geo.setdefault("length_mm", float(dim3.group(1)))
        geo.setdefault("width_mm", float(dim3.group(2)))
        geo.setdefault("height_mm", float(dim3.group(3)))
        geo.setdefault("thickness_mm", float(dim3.group(3)))

    dim2 = re.search(
        r"(\d+\.?\d*)\s*(?:x|X|×|\*)\s*(\d+\.?\d*)\s*(?:mm|毫米)?",
        text,
    )
    if dim2:
        geo.setdefault("length_mm", float(dim2.group(1)))
        geo.setdefault("width_mm", float(dim2.group(2)))

    return geo


def _detect_part_type(text: str) -> str:
    """识别当前 CAD 请求的零件类型。"""
    if re.search(r"机翼|翼展|根弦|尖弦|翼型|梯形翼|无人机.*翼", text):
        return "wing"
    if re.search(r"法兰|flange", text, re.IGNORECASE):
        return "flange"
    if re.search(r"L\s*形|L\s*型|支架|bracket", text, re.IGNORECASE):
        return "bracket"
    if re.search(r"壳体|盒体|箱体|外壳|housing|box", text, re.IGNORECASE):
        return "box"
    if re.search(r"圆柱|圆筒|轴套|套筒|cylinder|tube|sleeve", text, re.IGNORECASE):
        return "cylinder"
    if re.search(r"矩形板|平板|板件|带孔板|plate", text, re.IGNORECASE):
        return "plate"
    return "unknown"


def _can_execute_cad(part_type: str, geo: dict) -> bool:
    if part_type == "wing":
        return len([k for k in ("span_mm", "root_chord_mm", "thickness_mm") if k in geo]) >= 1
    if part_type in {"plate", "cylinder", "flange", "bracket", "box"}:
        return True
    return False


def _extract_material(text: str) -> dict | None:
    for kw, mat in _MATERIAL_MAP.items():
        if kw in text:
            return {"name": mat, "source": kw}
    return None


def _extract_loads(text: str) -> list[dict]:
    loads: list[dict] = []

    # 力载荷
    force_pat = re.search(r"(\d+\.?\d*)\s*(?:N|牛|牛顿)(?:\s*[，,]\s*([\+\-]?[XYZz])[轴方向]?)?", text)
    if force_pat:
        val = float(force_pat.group(1))
        direction = force_pat.group(2) or "Z"
        loads.append({
            "type": "force",
            "value": val,
            "unit": "N",
            "direction": direction.upper(),
            "region": _extract_region(text, "load"),
        })

    # 压力载荷
    press_pat = re.search(r"(\d+\.?\d*)\s*(?:MPa|Mpa|mpa|兆帕)", text)
    if press_pat:
        loads.append({
            "type": "pressure",
            "value": float(press_pat.group(1)),
            "unit": "MPa",
            "region": _extract_region(text, "load"),
        })

    return loads


def _extract_region(text: str, role: str) -> str | None:
    """从文本中提取载荷/约束作用的区域。"""
    # 按角色区分搜索模式
    if role == "fix":
        # 固定区域: 搜索 "X固定" / "固定X" / "X约束" 句式
        for pat, region in [
            (r"(根部|翼根|根|固定端|root)\s*(?:固定|约束|固支|夹紧)", "root"),
            (r"(?:固定|约束|固支|夹紧)\s*(?:在|于)?\s*(根部|翼根|根|固定端)", "root"),
            (r"(?:根部|翼根)\s*$", "root"),
        ]:
            if re.search(pat, text):
                return region
        return "root"  # 默认根部

    if role == "load":
        # 载荷区域: 搜索 "X施加" / "施加X" / "X加载" / "X作用" 句式
        for pat, region in [
            (r"(?:在|于|对)?\s*(翼尖|尖部|梢部|尖梢|tip)\s*(?:施加|加载|作用|受力|施力)", "tip"),
            (r"(?:施加|加载|作用|施力)\s*(?:在|于)?\s*(翼尖|尖部|梢部|尖梢|自由端)", "tip"),
            (r"(?:在|于|对)?\s*(上表面|上面|顶部|upper)\s*(?:施加|加载|作用)", "upper_surface"),
            (r"(?:在|于|对)?\s*(下表面|下面|底部|lower)\s*(?:施加|加载|作用)", "lower_surface"),
            (r"(?:在|于|对)?\s*(前缘|LE)\s*(?:施加|加载|作用)", "leading_edge"),
            (r"(?:在|于|对)?\s*(后缘|TE)\s*(?:施加|加载|作用)", "trailing_edge"),
        ]:
            if re.search(pat, text):
                return region
        return "tip"  # 默认尖部

    return None


def _extract_boundary_conditions(text: str) -> list[dict]:
    bcs: list[dict] = []
    # 搜索固定+区域模式的句子上下文
    fix_region = _extract_region(text, "fix")
    fix_kw = ["固定", "固支", "约束", "夹紧", "锁住", "不可移动"]
    for kw in fix_kw:
        if kw in text:
            bcs.append({
                "type": "fixed_support",
                "region": fix_region,
                "source": kw,
            })
            break
    if not bcs and _detect_keywords(text, _FEA_KW):
        bcs.append({
            "type": "fixed_support",
            "region": "root",
            "source": "默认（根部固支）",
        })
    return bcs


def _build_fea_config(analysis_types: list[str], material: dict | None,
                      loads: list[dict], bcs: list[dict]) -> dict:
    return {
        "solver": "ansys_mechanical",
        "status": "planned",  # planned | executing | done
        "analysis_types": analysis_types,
        "material": material,
        "loads": loads,
        "boundary_conditions": bcs,
        "mesh": {"element_size_mm": 5.0, "element_type": "tet10"},
        "result_items": _default_result_items(analysis_types),
    }


def _default_result_items(analysis_types: list[str]) -> list[str]:
    items: list[str] = []
    for at in analysis_types:
        if at == "static_structural":
            items.extend(["total_deformation", "equivalent_stress", "equivalent_strain"])
        elif at == "modal":
            items.extend(["total_deformation_mode_1", "total_deformation_mode_2",
                          "total_deformation_mode_3"])
        elif at == "thermal":
            items.extend(["temperature", "total_heat_flux"])
        elif at == "thermal_structural":
            items.extend(["total_deformation", "equivalent_stress", "temperature"])
    return items


def _check_missing(cad: bool, fea: bool, part_type: str, geo: dict, mat: dict | None,
                   loads: list[dict], bcs: list[dict],
                   analysis_types: list[str]) -> list[str]:
    missing: list[str] = []

    if cad and part_type == "wing":
        for key in ["span_mm", "root_chord_mm", "thickness_mm"]:
            if key not in geo:
                missing.append(f"CAD.{key}")
        if "tip_chord_mm" not in geo:
            missing.append("CAD.tip_chord_mm (将按 root×0.6 估算)")
    elif cad and part_type == "unknown":
        missing.append("CAD.part_type")

    if fea:
        if mat is None:
            missing.append("FEA.material")
        if not loads:
            missing.append("FEA.loads")
        if not bcs:
            missing.append("FEA.boundary_conditions")
        if "cfd" in analysis_types:
            missing.append("FEA.cfd_mesh (CFD 网格生成尚未实现)")

    return missing


# ═══════════════════════════════════════════════════════════
# 格式化输出
# ═══════════════════════════════════════════════════════════

def format_task_plan(plan: dict) -> str:
    """将任务计划格式化为可读文本。"""
    lines: list[str] = []
    intent = plan.get("intent", {})

    lines.append(f"任务计划: {plan.get('task_id', '?')}")
    lines.append("─" * 50)

    # 意图
    lines.append(f"\n[意图]")
    lines.append(f"  设计分析: {'是' if intent.get('design_analysis') else '否'}")
    lines.append(f"  CAD 建模: {'是' if intent.get('cad_required') else '否'}")
    lines.append(f"  FEA 分析: {'是' if intent.get('fea_required') else '否'}")
    lines.append(f"  零件类型: {plan.get('part_type', 'unknown')}")
    atypes = intent.get("analysis_types", [])
    lines.append(f"  分析类型: {', '.join(atypes) if atypes else '(未指定)'}")

    # 几何
    geo = plan.get("geometry", {})
    if geo:
        lines.append(f"\n[几何参数]")
        for k, v in geo.items():
            lines.append(f"  {k}: {v}")

    # 材料
    mat = plan.get("material")
    if mat:
        lines.append(f"\n[材料]")
        lines.append(f"  {mat.get('name', '?')}  (来源: {mat.get('source', '?')})")
    elif intent.get("fea_required"):
        lines.append(f"\n[材料]  ⚠️ 未指定")

    # 载荷
    loads = plan.get("loads", [])
    if loads:
        lines.append(f"\n[载荷]")
        for ld in loads:
            lines.append(f"  {ld['type']}: {ld['value']} {ld['unit']} "
                         f"方向{ld.get('direction','?')} @ {ld.get('region','?')}")
    elif intent.get("fea_required"):
        lines.append(f"\n[载荷]  ⚠️ 未指定")

    # 边界条件
    bcs = plan.get("boundary_conditions", [])
    if bcs:
        lines.append(f"\n[边界条件]")
        for bc in bcs:
            lines.append(f"  {bc['type']} @ {bc['region']}  ({bc.get('source','')})")

    # FEA 配置
    fea = plan.get("fea_config", {})
    if intent.get("fea_required") and fea:
        lines.append(f"\n[FEA 配置]")
        lines.append(f"  求解器: {fea.get('solver', '?')}")
        lines.append(f"  状态: {fea.get('status', '?')}")
        lines.append(f"  网格: {fea.get('mesh', {}).get('element_size_mm', '?')} mm, "
                     f"{fea.get('mesh', {}).get('element_type', '?')}")
        items = fea.get("result_items", [])
        lines.append(f"  结果项: {', '.join(items) if items else '(默认)'}")

    # 缺失参数
    missing = plan.get("missing_params", [])
    if missing:
        lines.append(f"\n[缺失参数]")
        for m in missing:
            lines.append(f"  ⚠️ {m}")

    # 可执行性
    lines.append(f"\n[可执行性]")
    lines.append(f"  CAD 建模: {'✅ 可执行' if plan.get('can_execute_cad') else '❌ 参数不足'}")
    lines.append(f"  FEA 分析: {'✅ 可执行' if plan.get('can_execute_fea') else '⏳ 适配器待实现'}")

    # 建议
    recs = plan.get("recommend_commands", [])
    if recs:
        lines.append(f"\n[建议]")
        for r in recs:
            lines.append(f"  → {r}")

    lines.append("\n" + "─" * 50)
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    test = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "创建一个翼展1200mm的铝合金机翼，根弦220mm，厚度20mm，"
        "根部固定，尖部加载300N，做静力分析"
    )
    plan = plan_task(test)
    print(format_task_plan(plan))
    print()
    print(json.dumps(plan, ensure_ascii=False, indent=2))
