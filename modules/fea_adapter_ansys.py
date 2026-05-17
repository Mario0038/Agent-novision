#!/usr/bin/env python3
"""
ANSYS Mechanical 静力分析适配器（第一版）
=========================================
当前仅生成标准化 FEA 任务包（目录、JSON、报告、求解脚本模板），
不实际启动 ANSYS 或调用 PyMAPDL。

后续版本将对接 PyMAPDL / ANSYS Mechanical APDL 进行真实求解。
"""

import json
import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_ROOT = ROOT / "generated_analysis"


def generate_ansys_task_package(
    step_path: str,
    fea_config: dict,
    output_dir: str | None = None,
) -> dict:
    """生成标准化 ANSYS 静力分析任务包。

    Args:
        step_path: SolidWorks 导出的 STEP 文件路径
        fea_config: FEA 配置 dict，至少包含:
            analysis_type, material, loads, boundary_conditions,
            mesh, result_items
        output_dir: 输出根目录（默认 generated_analysis/ansys/wing_static/）

    Returns:
        {"status": "generated", "files": [...], "output_dir": str}
    """
    if output_dir is None:
        output_dir = str(ANALYSIS_ROOT / "ansys" / "wing_static")

    out = Path(output_dir)
    dirs = {
        "root": out,
        "input": out / "input",
        "scripts": out / "scripts",
        "results": out / "results",
        "figures": out / "figures",
    }

    # ── 1. 创建目录 ──
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    # ── 2. 复制 STEP 到 input/ ──
    src_step = Path(step_path)
    dst_step = dirs["input"] / "geometry.step"
    if src_step.exists():
        shutil.copy2(src_step, dst_step)
    else:
        # STEP 不存在时仍创建占位说明
        dst_step.write_text(
            f"# STEP 文件未找到: {step_path}\n"
            f"# 请先运行 SolidWorks 机翼建模生成 STEP。\n",
            encoding="utf-8",
        )

    # ── 3. 写入任务 JSON ──
    task_json_path = dirs["input"] / "ansys_static_task.json"
    task_data = _build_task_json(str(dst_step), fea_config)
    task_json_path.write_text(
        json.dumps(task_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ── 4. 写入报告 ──
    report_path = out / "report.md"
    report_path.write_text(_build_report(task_data, dst_step), encoding="utf-8")

    # ── 5. 写入求解脚本模板 ──
    script_path = dirs["scripts"] / "run_static_mechanical.py"
    script_path.write_text(_build_template_script(task_data), encoding="utf-8")

    files_created = [
        str(task_json_path.relative_to(ROOT)),
        str(report_path.relative_to(ROOT)),
        str(script_path.relative_to(ROOT)),
        str(dst_step.relative_to(ROOT)),
    ]

    print(f"  ANSYS 任务包已生成: {out}")
    print(f"    输入: {task_json_path.name}, {dst_step.name}")
    print(f"    脚本: {script_path.name}")
    print(f"    报告: {report_path.name}")

    return {
        "status": "generated",
        "output_dir": str(out),
        "files": files_created,
    }


def _build_task_json(step_path: str, fea_config: dict) -> dict:
    return {
        "task_id": datetime.now().strftime("ANSYS-%Y%m%d-%H%M%S"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "solver": "ansys_mechanical",
        "solver_status": "planned",
        "geometry_step_path": step_path,
        "analysis_type": fea_config.get("analysis_type", "static_structural"),
        "material": fea_config.get("material", "Aluminum 6061-T6"),
        "mesh": fea_config.get("mesh", {
            "element_size_mm": 5.0,
            "element_type": "tet10",
        }),
        "boundary_conditions": fea_config.get("boundary_conditions", [
            {"type": "fixed_support", "region": "root"},
        ]),
        "loads": fea_config.get("loads", [
            {"type": "force", "value_N": 300, "direction": "+Z", "region": "tip"},
        ]),
        "result_items": fea_config.get("result_items", [
            "total_deformation",
            "equivalent_stress",
            "equivalent_strain",
        ]),
        "expected_outputs": {
            "total_deformation_mm": "<待求解>",
            "equivalent_stress_mpa": "<待求解>",
            "equivalent_strain": "<待求解>",
        },
    }


def _build_report(task_data: dict, step_path: Path) -> str:
    bc_list = task_data.get("boundary_conditions", [])
    load_list = task_data.get("loads", [])
    mesh = task_data.get("mesh", {})

    lines = [
        f"# ANSYS 静力分析任务报告",
        f"",
        f"## 任务概述",
        f"",
        f"- **任务 ID:** {task_data.get('task_id', '?')}",
        f"- **生成时间:** {task_data.get('generated_at', '?')}",
        f"- **求解器:** {task_data.get('solver', 'ansys_mechanical')}",
        f"- **分析类型:** {task_data.get('analysis_type', 'static_structural')}",
        f"- **当前状态:** ANSYS 任务包已生成，尚未求解",
        f"",
        f"## 几何文件",
        f"",
        f"- **路径:** {step_path}",
        f"- **格式:** STEP AP203/AP214",
        f"",
        f"## 材料",
        f"",
        f"- {task_data.get('material', '未指定')}",
        f"",
        f"## 网格",
        f"",
        f"- **单元尺寸:** {mesh.get('element_size_mm', 5)} mm",
        f"- **单元类型:** {mesh.get('element_type', 'tet10')}",
        f"",
        f"## 边界条件",
        f"",
    ]
    for bc in bc_list:
        lines.append(f"- **{bc.get('type', '?')}:** @ {bc.get('region', '?')}")
    lines.append("")

    lines.append("## 载荷")
    lines.append("")
    for ld in load_list:
        lines.append(f"- **{ld.get('type', '?')}:** {ld.get('value_N', '?')} N "
                     f"方向 {ld.get('direction', '?')} @ {ld.get('region', '?')}")
    lines.append("")

    lines.append("## 预期输出")
    lines.append("")
    for item in task_data.get("result_items", []):
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## 下一步")
    lines.append("")
    lines.append("1. 确认 STEP 几何文件已生成且有效")
    lines.append("2. 运行 `scripts/run_static_mechanical.py`（需 PyMAPDL 环境）")
    lines.append("3. 或在 ANSYS Workbench 中手动导入 `input/ansys_static_task.json`")
    lines.append("4. 求解后在 `results/` 查看结果文件")
    lines.append("5. 后处理图片输出到 `figures/`")
    lines.append("")

    return "\n".join(lines)


def _build_template_script(task_data: dict) -> str:
    """生成 ANSYS Mechanical 求解脚本模板。"""

    mat = task_data.get("material", "Aluminum 6061-T6")
    mesh = task_data.get("mesh", {})
    bc_list = task_data.get("boundary_conditions", [])
    load_list = task_data.get("loads", [])
    result_items = task_data.get("result_items", [])

    # 将载荷和约束转为 JSON 字符串嵌入脚本
    bc_json = json.dumps(bc_list, ensure_ascii=False, indent=8)
    load_json = json.dumps(load_list, ensure_ascii=False, indent=8)
    result_json = json.dumps(result_items, ensure_ascii=False)

    return f'''#!/usr/bin/env python3
"""
ANSYS Mechanical 静力分析求解脚本（模板）
=========================================
依赖: PyMAPDL (pip install ansys-mapdl-core)

运行方式:
    python scripts/run_static_mechanical.py

当前状态: 脚本模板，尚未连接真实 ANSYS 求解器。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

# ═══════════════════════════════════════════════════════════
# 任务配置（由 fea_adapter_ansys 自动生成）
# ═══════════════════════════════════════════════════════════

STEP_PATH = Path(r"input/geometry.step")
MATERIAL = "{mat}"
MESH_SIZE_MM = {mesh.get('element_size_mm', 5.0)}
ELEMENT_TYPE = "{mesh.get('element_type', 'tet10')}"

BOUNDARY_CONDITIONS = {bc_json}

LOADS = {load_json}

RESULT_ITEMS = {result_json}


# ═══════════════════════════════════════════════════════════
# 求解步骤（待 PyMAPDL 环境就绪后启用）
# ═══════════════════════════════════════════════════════════

def run_static_structural():
    """静力分析求解流程。"""

    print("=" * 55)
    print("  ANSYS Mechanical — 静力分析")
    print("=" * 55)

    # Step 1: 导入几何
    print("\\n[1/8] 导入 STEP 几何...")
    print(f"  文件: {{STEP_PATH}}")
    # TODO: mapdl.input(STEP_PATH) 或 mapdl.igesin(STEP_PATH)
    # 需要先将 STEP 转为 IGES 或使用 SpaceClaim 导入

    # Step 2: 创建 Static Structural 分析
    print("\\n[2/8] 创建 Static Structural 分析...")
    # TODO:
    #   mapdl.prep7()
    #   mapdl.antype("STATIC")

    # Step 3: 设置材料属性
    print(f"\\n[3/8] 设置材料: {{MATERIAL}}...")
    # TODO:
    #   mapdl.mp("EX", 1, 68900)    # Young's Modulus (MPa)
    #   mapdl.mp("PRXY", 1, 0.33)   # Poisson's Ratio
    #   mapdl.mp("DENS", 1, 2.7e-9) # Density (ton/mm³)

    # Step 4: 网格划分
    print(f"\\n[4/8] 网格划分 ({{ELEMENT_TYPE}}, {{MESH_SIZE_MM}} mm)...")
    # TODO:
    #   mapdl.et(1, "SOLID187")     # 10-node tetrahedral
    #   mapdl.esize(MESH_SIZE_MM)
    #   mapdl.vmesh("ALL")

    # Step 5: 施加边界条件
    print("\\n[5/8] 施加边界条件...")
    for bc in BOUNDARY_CONDITIONS:
        region = bc.get("region", "?")
        bctype = bc.get("type", "?")
        print(f"  {{bctype}} @ {{region}}")
    # TODO:
    #   mapdl.nsel("S", "LOC", "X", 0)  # 选根部节点
    #   mapdl.d("ALL", "ALL")            # 固定所有自由度

    # Step 6: 施加载荷
    print("\\n[6/8] 施加载荷...")
    for ld in LOADS:
        val = ld.get("value_N", 0)
        direction = ld.get("direction", "Z")
        region = ld.get("region", "?")
        print(f"  force {{val}}N {{direction}} @ {{region}}")
    # TODO:
    #   mapdl.nsel("S", "LOC", "X", span)  # 选尖部节点
    #   mapdl.f("ALL", "FZ", val)            # 施力

    # Step 7: 求解
    print("\\n[7/8] 求解...")
    # TODO:
    #   mapdl.allsel()
    #   mapdl.solve()

    # Step 8: 后处理 & 导出结果
    print("\\n[8/8] 后处理...")
    for item in RESULT_ITEMS:
        print(f"  导出: {{item}}")
    # TODO:
    #   mapdl.post1()
    #   mapdl.set(1, 1)
    #   mapdl.plnsol("U", "SUM")     # Total Deformation
    #   mapdl.plnsol("S", "EQV")     # Equivalent Stress

    print("\\n  ✅ 求解完成（模板 — 待 PyMAPDL 环境就绪后实际执行）")


if __name__ == "__main__":
    print("⚠️  此脚本为生成模板，尚未连接 ANSYS 求解器。")
    print("   待 pip install ansys-mapdl-core 后移除此提示并启用求解代码。")
    print()
    run_static_structural()
'''


# ═══════════════════════════════════════════════════════════
# Dry-run 执行器
# ═══════════════════════════════════════════════════════════

def execute_static_analysis(task_package_dir: str, dry_run: bool = True) -> dict:
    """对指定任务包执行静力分析（dry_run=True 仅生成执行计划）。

    Args:
        task_package_dir: 任务包根目录（含 input/ansys_static_task.json）
        dry_run: True=仅生成执行计划, False=实际求解（未实现）

    Returns:
        {"status": "planned"|"ready"|"blocked", "execution_plan": dict, ...}
    """
    pkg = Path(task_package_dir)
    task_json_path = pkg / "input" / "ansys_static_task.json"
    step_path = pkg / "input" / "geometry.step"
    report_path = pkg / "report.md"

    result = {
        "status": "pending",
        "execution_plan_path": str(pkg / "results" / "execution_plan.json"),
    }

    # ── 1. 读取任务定义 ──
    if not task_json_path.exists():
        return {"status": "blocked", "error": f"任务 JSON 不存在: {task_json_path}"}

    task = json.loads(task_json_path.read_text(encoding="utf-8"))

    # ── 2. 读取 ANSYS 配置 ──
    ansys_cfg = {}
    ansys_cfg_path = ROOT / "config" / "ansys_config.json"
    if ansys_cfg_path.exists():
        ansys_cfg = json.loads(ansys_cfg_path.read_text(encoding="utf-8"))

    # ── 3. 验证清单 ──
    checks: list[dict] = []
    issues: list[str] = []
    warnings: list[str] = []

    # 几何
    step_ok = step_path.exists() and step_path.stat().st_size > 500
    checks.append({"item": "geometry_step", "status": "ok" if step_ok else "fail",
                   "detail": str(step_path)})
    if not step_ok:
        issues.append("STEP 几何文件不存在或无效")

    # 材料
    mat = task.get("material", "")
    mat_ok = bool(mat and mat != "未指定")
    checks.append({"item": "material", "status": "ok" if mat_ok else "fail",
                   "detail": mat or "未指定"})
    if not mat_ok:
        issues.append("材料未指定")

    # 边界条件
    bcs = task.get("boundary_conditions", [])
    bcs_ok = len(bcs) > 0
    checks.append({"item": "boundary_conditions", "status": "ok" if bcs_ok else "fail",
                   "detail": f"{len(bcs)} 项"})
    if not bcs_ok:
        issues.append("边界条件缺失")

    # 载荷
    loads = task.get("loads", [])
    loads_ok = len(loads) > 0
    checks.append({"item": "loads", "status": "ok" if loads_ok else "fail",
                   "detail": f"{len(loads)} 项"})
    if not loads_ok:
        issues.append("载荷缺失")

    # ANSYS 求解器
    preferred = ansys_cfg.get("preferred_backend", "none")
    mapdl_ok = bool(ansys_cfg.get("mapdl_path"))
    wb_ok = bool(ansys_cfg.get("workbench_path"))
    pyansys_ok = bool(ansys_cfg.get("pyansys_available"))

    if preferred == "pymapdl" and pyansys_ok:
        solver_status = "ok"
        solver_detail = "PyMAPDL"
    elif preferred in ("workbench", "pymapdl") and mapdl_ok:
        solver_status = "ok"
        solver_detail = f"MAPDL @ {ansys_cfg.get('mapdl_path')}"
    elif wb_ok:
        solver_status = "ok"
        solver_detail = f"Workbench @ {ansys_cfg.get('workbench_path')}"
    else:
        solver_status = "fail"
        solver_detail = "无可用求解器"
        issues.append("无可用 ANSYS 求解器")

    checks.append({"item": "ansys_solver", "status": solver_status, "detail": solver_detail})

    # ── 4. 确定后端 ──
    if pyansys_ok:
        selected_backend = "pymapdl"
    elif mapdl_ok:
        selected_backend = "workbench"
    elif wb_ok:
        selected_backend = "workbench"
    else:
        selected_backend = "none"

    # ── 5. 执行步骤 ──
    planned_steps = [
        {"step": 1, "action": "导入 STEP 几何", "tool": selected_backend, "status": "pending"},
        {"step": 2, "action": "设置材料属性", "detail": mat, "status": "pending"},
        {"step": 3, "action": "网格划分", "detail": f"{task.get('mesh', {}).get('element_size_mm', 5)} mm tet10", "status": "pending"},
        {"step": 4, "action": "施加边界条件", "detail": str(bcs), "status": "pending"},
        {"step": 5, "action": "施加载荷", "detail": str(loads), "status": "pending"},
        {"step": 6, "action": "求解", "status": "pending"},
        {"step": 7, "action": "后处理导出结果", "detail": str(task.get("result_items", [])), "status": "pending"},
    ]

    # ── 6. 构建执行计划 ──
    all_checks_ok = all(c["status"] == "ok" for c in checks)
    plan = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "task_package_dir": str(pkg),
        "geometry_step_path": str(step_path),
        "selected_backend": selected_backend,
        "ansys_version": ansys_cfg.get("selected_version"),
        "workbench_path": ansys_cfg.get("workbench_path"),
        "mechanical_path": ansys_cfg.get("mechanical_path"),
        "mapdl_path": ansys_cfg.get("mapdl_path"),
        "material": mat,
        "mesh": task.get("mesh", {}),
        "boundary_conditions": bcs,
        "loads": loads,
        "expected_outputs": task.get("result_items", []),
        "checks": checks,
        "planned_steps": planned_steps,
        "ready_to_execute": all_checks_ok and not dry_run,
        "dry_run": dry_run,
        "blocking_issues": issues,
        "warnings": warnings + ansys_cfg.get("warnings", []),
    }

    # ── 7. 写入执行计划 ──
    results_dir = pkg / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    plan_path = results_dir / "execution_plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── 8. 更新 report.md ──
    if report_path.exists():
        _append_execution_to_report(report_path, plan)

    print(f"  执行计划已生成: {plan_path}")
    print(f"  后端: {selected_backend}")
    print(f"  就绪状态: {'✅ 可执行' if all_checks_ok else '❌ 存在阻塞问题'}")
    if issues:
        for iss in issues:
            print(f"    - {iss}")

    result["status"] = "ready" if all_checks_ok else "blocked"
    result["ready_to_execute"] = all_checks_ok and not dry_run
    result["blocking_issues"] = issues
    result["selected_backend"] = selected_backend

    return result


def _append_execution_to_report(report_path: Path, plan: dict):
    """在 report.md 末尾追加执行计划章节。"""
    existed = report_path.read_text(encoding="utf-8")
    # 如果已有执行计划章节则跳过
    if "## ANSYS 求解执行计划" in existed:
        return

    checks = plan.get("checks", [])
    issues = plan.get("blocking_issues", [])

    lines = [
        "",
        "## ANSYS 求解执行计划",
        "",
        f"- **生成时间:** {plan.get('generated_at', '?')}",
        f"- **模式:** {'Dry-run（仅生成计划）' if plan.get('dry_run') else '真实求解'}",
        f"- **选定后端:** {plan.get('selected_backend', 'none')}",
        f"- **ANSYS 版本:** {plan.get('ansys_version') or '未检测'}",
        f"- **MAPDL 路径:** {plan.get('mapdl_path') or '未检测'}",
        f"- **Workbench 路径:** {plan.get('workbench_path') or '未检测'}",
        "",
        "### 条件检查",
        "",
    ]
    for c in checks:
        icon = "✅" if c["status"] == "ok" else "❌"
        lines.append(f"- {icon} **{c['item']}**: {c.get('detail', '')}")

    lines.append("")
    lines.append("### 阻塞问题" if issues else "### 阻塞问题（无）")
    lines.append("")
    if issues:
        for iss in issues:
            lines.append(f"- ❌ {iss}")
    else:
        lines.append("- ✅ 无阻塞问题")

    lines.append("")
    lines.append("### 求解步骤")
    lines.append("")
    for s in plan.get("planned_steps", []):
        lines.append(f"{s['step']}. {s['action']} — {s.get('detail', '')}")

    ready = plan.get("ready_to_execute", False)
    lines.append("")
    lines.append(f"### 状态: {'✅ 就绪' if not issues else '❌ 阻塞'} | "
                 f"{'dry-run' if plan.get('dry_run') else 'ready to execute'}")
    lines.append("")
    if plan.get("dry_run"):
        lines.append("当前为 dry-run 模式，已生成执行计划但未启动求解。")
        lines.append("待条件就绪后，调用 `execute_static_analysis(dry_run=False)` 执行真实求解。")

    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    import sys
    # 从命令行参数或默认配置生成任务包
    config_path = sys.argv[1] if len(sys.argv) > 1 else None

    if config_path:
        config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        fea_config = config.get("fea", config)
        step = config.get("step_path", "")
    else:
        fea_config = {
            "analysis_type": "static_structural",
            "material": "Aluminum 6061-T6",
            "mesh": {"element_size_mm": 5.0, "element_type": "tet10"},
            "boundary_conditions": [{"type": "fixed_support", "region": "root"}],
            "loads": [{"type": "force", "value_N": 300, "direction": "+Z", "region": "tip"}],
            "result_items": ["total_deformation", "equivalent_stress"],
        }
        step = str(ROOT / "generated_models" / "solidworks" / "wing" / "step"
                   / "test_wing_pipeline.STEP")

    result = generate_ansys_task_package(step, fea_config)
    print(f"\n生成文件: {len(result['files'])} 个")
    for f in result['files']:
        print(f"  {f}")
