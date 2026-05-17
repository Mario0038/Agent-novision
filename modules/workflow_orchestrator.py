#!/usr/bin/env python3
"""
工作流编排器 — 根据 task_planner 的输出执行 CAD 建模和 FEA 任务包生成。

当前状态:
  - CAD: 按零件类型调用 SolidWorks 模板建模 ✅
  - FEA: 调用 fea_adapter_ansys 生成 ANSYS 任务包 ✅（不实际求解）
"""

import json
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.task_planner import plan_task, format_task_plan


def run_workflow(user_input: str) -> tuple[str, dict]:
    """完整工作流：规划 → CAD 建模 → FEA 任务包生成。

    Returns:
        (formatted_text, workflow_report_dict)
    """
    report: dict = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "raw_input": user_input,
        "cad_required": False,
        "cad_status": "not_requested",
        "cad_step_path": None,
        "fea_required": False,
        "fea_status": "not_requested",
        "fea_solver": None,
        "analysis_type": None,
        "ansys_task_package_path": None,
        "ansys_task_json": None,
        "ansys_script_path": None,
        "report_path": None,
    }

    lines: list[str] = []
    lines.append("╔" + "═" * 55 + "╗")
    lines.append("║" + "  CAD + FEA 工作流编排".center(53) + "║")
    lines.append("╚" + "═" * 55 + "╝")
    lines.append("")

    # ── Step 1: 任务规划 ──
    lines.append("## Step 1: 任务解析")
    lines.append("")
    plan = plan_task(user_input)
    lines.append(format_task_plan(plan))
    lines.append("")

    intent = plan.get("intent", {})
    report["cad_required"] = intent.get("cad_required", False)
    report["fea_required"] = intent.get("fea_required", False)
    report["analysis_type"] = (intent.get("analysis_types") or [None])[0]

    # ── Step 2: CAD 建模 ──
    step_path = None

    if intent.get("cad_required"):
        geo = plan.get("geometry", {})
        has_span = "span_mm" in geo
        if has_span or plan.get("can_execute_cad"):
            # 有翼展或参数足够 → 尝试建模（缺失参数使用默认值）
            lines.append("## Step 2: CAD 建模")
            if not plan.get("can_execute_cad"):
                lines.append("  (部分参数使用默认值: chord=span/5.4, thickness=12%chord)")
            lines.append("")
            cad_text, cad_info = _execute_cad(plan)
            lines.append(cad_text)
            lines.append("")
            report["cad_status"] = cad_info.get("status", "unknown")
            step_path = cad_info.get("step_path")
            report["cad_step_path"] = step_path
        else:
            lines.append("## Step 2: CAD 建模 — ⏭️ 跳过（缺少翼展）")
            lines.append("")
            report["cad_status"] = "skipped_missing_span"

    # ── Step 3: FEA 任务包生成 ──
    if intent.get("fea_required"):
        lines.append("## Step 3: FEA 分析任务包生成")
        lines.append("")
        atypes = intent.get("analysis_types", [])
        if "static_structural" in atypes and step_path:
            fea_text, fea_info = _execute_fea_task_package(plan, step_path)
            lines.append(fea_text)
            lines.append("")
            report.update(fea_info)
        elif "static_structural" in atypes and not step_path:
            lines.append("  ❌ CAD 未生成 STEP 文件，无法创建 FEA 任务包。")
            lines.append("     请先确认 SolidWorks 建模成功后再重试。")
            lines.append("")
            report["fea_status"] = "error_no_step"
        else:
            # 非静力分析或 STEP 不存在 → 生成计划描述
            fea_text = _generate_fea_plan_text(plan)
            lines.append(fea_text)
            lines.append("")
            report["fea_status"] = "planned_only"
            report["fea_solver"] = "ansys_mechanical"

    # ── Step 4: 汇总 ──
    lines.append("## Step 4: 工作流汇总")
    lines.append("─" * 55)
    lines.append("")
    lines.append(_summary(report))
    lines.append("")
    lines.append("─" * 55)

    return "\n".join(lines), report


def _execute_cad(plan: dict) -> tuple[str, dict]:
    """执行 CAD 建模，返回 (text, info_dict)。"""
    lines: list[str] = []
    geo = plan.get("geometry", {})
    info: dict = {"status": "unknown", "step_path": None}

    part_type = plan.get("part_type", "unknown")

    try:
        lines.append(f"  零件类型: {part_type}")
        lines.append("  正在调用 SolidWorks...")

        if part_type == "wing":
            from modules.solidworks_wing_builder import build_trapezoidal_wing
            span = geo.get("span_mm", 1200)
            root_c = geo.get("root_chord_mm", 220)
            tip_c = geo.get("tip_chord_mm", root_c * 0.6)
            thick = geo.get("thickness_mm", 20)
            sweep = geo.get("sweep_deg", 0)
            lines.append(f"  建模参数: 翼展={span}mm 根弦={root_c}mm 尖弦={tip_c}mm 厚度={thick}mm")
            result = build_trapezoidal_wing(
                span_mm=span,
                root_chord_mm=root_c,
                tip_chord_mm=tip_c,
                thickness_mm=thick,
                sweep_deg=sweep,
                dihedral_deg=geo.get("dihedral_deg", 0),
                output_name=sanitize_output_name_for_workflow(plan),
                build_mode="loft_airfoil" if "NACA" in plan.get("raw_input", "").upper() else "simple_trapezoid",
            )
        elif part_type in {"plate", "cylinder", "flange", "bracket", "box"}:
            from modules.solidworks_generic_builder import build_generic_part
            lines.append(f"  通用模板参数: {geo}")
            result = build_generic_part(
                part_type=part_type,
                geometry=geo,
                output_name=sanitize_output_name_for_workflow(plan),
            )
        else:
            lines.append("  ❌ 当前无法识别零件类型，已取消自动建模。")
            lines.append("     支持: wing, plate, cylinder, flange, bracket, box")
            info["status"] = "unsupported_part_type"
            return "\n".join(lines), info

        if result:
            actual = result.get("build_actual_mode", result.get("part_type", "?"))
            step = result.get("step", "")
            lines.append(f"  ✅ CAD 建模完成 (actual_mode={actual})")
            lines.append(f"  SLDPRT: {result['sldprt']}")
            lines.append(f"  STEP:   {step}")
            info["status"] = "success"
            info["step_path"] = step
        else:
            lines.append("  ❌ CAD 建模失败（SolidWorks 连接异常）")
            info["status"] = "failed"
    except ImportError:
        lines.append("  ⚠️ SolidWorks 模块未就绪")
        info["status"] = "module_unavailable"
    except Exception as e:
        lines.append(f"  ❌ CAD 建模异常: {e}")
        info["status"] = "error"

    return "\n".join(lines), info


def sanitize_output_name_for_workflow(plan: dict) -> str:
    raw = plan.get("task_id", "workflow_wing").lower().replace(":", "-")
    safe = "".join(c if c.isalnum() or c in "_-" else "_" for c in raw)
    return safe.strip("_-") or "workflow_wing"


def _execute_fea_task_package(plan: dict, step_path: str) -> tuple[str, dict]:
    """调用 fea_adapter_ansys 生成 ANSYS 静力分析任务包。"""
    lines: list[str] = []
    info: dict = {}

    fea_config = plan.get("fea_config", {})
    material = (plan.get("material") or {}).get("name", "Aluminum 6061-T6")
    loads = plan.get("loads", [])
    bcs = plan.get("boundary_conditions", [])

    # 构建 fea_adapter 所需的配置
    fea_cfg = {
        "analysis_type": "static_structural",
        "material": material,
        "mesh": fea_config.get("mesh", {"element_size_mm": 5.0, "element_type": "tet10"}),
        "boundary_conditions": bcs,
        "loads": [
            {"type": ld.get("type", "force"),
             "value_N": ld.get("value", 0),
             "direction": ld.get("direction", "Z"),
             "region": ld.get("region", "tip")}
            for ld in loads
        ],
        "result_items": fea_config.get("result_items",
            ["total_deformation", "equivalent_stress", "equivalent_strain"]),
    }

    # 检查 STEP
    step = Path(step_path)
    if not step.exists():
        lines.append(f"  ❌ STEP 文件不存在: {step_path}")
        lines.append("     无法生成 FEA 任务包。请先运行 CAD 建模。")
        info["fea_status"] = "error_step_missing"
        return "\n".join(lines), info

    if step.stat().st_size < 500:
        lines.append(f"  ❌ STEP 文件无效（< 500 B）: {step_path}")
        info["fea_status"] = "error_step_invalid"
        return "\n".join(lines), info

    # 生成任务包
    output_name = f"wing_static_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    out_dir = ROOT / "generated_analysis" / "ansys" / output_name

    try:
        from modules.fea_adapter_ansys import generate_ansys_task_package
        result = generate_ansys_task_package(step_path, fea_cfg, str(out_dir))
        lines.append(f"  ✅ ANSYS 静力分析任务包已生成")
        lines.append(f"  输出目录: {out_dir}")
        for f in result.get("files", []):
            lines.append(f"    {f}")
        lines.append("")
        lines.append("  ⚠️ 当前已生成 ANSYS 静力分析任务包，尚未执行真实求解。")
        lines.append("     下一步请运行 dry-run 执行计划检查 Workbench / Mechanical / MAPDL 后端条件。")

        info["fea_status"] = "task_package_generated"
        info["fea_solver"] = "ansys_mechanical"
        info["ansys_task_package_path"] = str(out_dir)
        info["ansys_task_json"] = str(out_dir / "input" / "ansys_static_task.json")
        info["ansys_script_path"] = str(out_dir / "scripts" / "run_static_mechanical.py")
        info["report_path"] = str(out_dir / "report.md")
    except ImportError:
        lines.append("  ⚠️ fea_adapter_ansys 模块未就绪")
        info["fea_status"] = "module_unavailable"
    except Exception as e:
        lines.append(f"  ❌ FEA 任务包生成异常: {e}")
        info["fea_status"] = "error"

    return "\n".join(lines), info


def _generate_fea_plan_text(plan: dict) -> str:
    """为非静力分析类型生成描述性计划。"""
    lines: list[str] = []
    fea = plan.get("fea_config", {})
    atypes = fea.get("analysis_types", plan.get("intent", {}).get("analysis_types", []))

    lines.append(f"  ⏳ 分析类型 ({', '.join(atypes)}) 的任务包生成尚未实现。")
    lines.append("  当前仅支持 static_structural → ANSYS Mechanical 任务包。")
    lines.append("  以下类型待后续支持: modal, thermal, cfd")
    return "\n".join(lines)


def _summary(report: dict) -> str:
    lines: list[str] = []

    cad = report.get("cad_status", "?")
    fea = report.get("fea_status", "?")

    cad_icon = "✅" if cad == "success" else ("⚠️" if cad == "not_requested" else "❌")
    fea_icon = "✅" if fea == "task_package_generated" else ("⏳" if fea == "not_requested" else "❌")

    lines.append(f"  CAD 状态:    {cad_icon} {cad}")
    if report.get("cad_step_path"):
        lines.append(f"  CAD STEP:    {report['cad_step_path']}")

    lines.append(f"  FEA 需求:    {'是' if report.get('fea_required') else '否'}")
    lines.append(f"  FEA 状态:    {fea_icon} {fea}")
    if report.get("fea_required") and fea == "task_package_generated":
        lines.append(f"  FEA 任务包:   ✅ 可生成")
        lines.append(f"  真实求解:    ⏳ 尚未执行")
    lines.append(f"  分析类型:    {report.get('analysis_type') or '—'}")

    if report.get("ansys_task_package_path"):
        lines.append(f"  任务包路径:  {report['ansys_task_package_path']}")
    if report.get("ansys_task_json"):
        lines.append(f"  任务 JSON:   {report['ansys_task_json']}")
    if report.get("ansys_script_path"):
        lines.append(f"  求解脚本:    {report['ansys_script_path']}")
    if report.get("report_path"):
        lines.append(f"  报告:        {report['report_path']}")

    lines.append("")
    if not report.get("fea_required"):
        lines.append("  本次任务未请求有限元分析，未生成 FEA 任务包。")
    elif fea == "task_package_generated":
        lines.append("  ⚠️ FEA 任务包已生成但尚未实际求解。")
        lines.append("     请执行 dry-run 检查 Workbench / Mechanical / MAPDL 后端条件。")
    elif fea == "error_no_step":
        lines.append("  ❌ FEA 任务包生成失败：CAD 未生成 STEP 文件。")
    elif fea == "error_step_missing":
        lines.append("  ❌ FEA 任务包生成失败：STEP 文件不存在。")
    elif fea == "module_unavailable":
        lines.append("  ⚠️ FEA 适配器模块未就绪。")
    elif fea == "planned_only":
        lines.append("  ⏳ FEA 分析计划已生成，该分析类型的任务包尚未实现。")
    else:
        lines.append(f"  FEA 状态: {fea}")

    return "\n".join(lines)


if __name__ == "__main__":
    test = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "创建一个翼展1200mm的铝合金机翼，根弦220mm，厚度20mm，"
        "根部固定，尖部加载300N，做静力分析"
    )
    text, _ = run_workflow(test)
    print(text)
