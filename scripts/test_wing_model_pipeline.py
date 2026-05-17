#!/usr/bin/env python3
"""
固定回归测试 — 机翼参数化建模全流程验证。

支持双模式测试：
  - simple_trapezoid: 梯形实体
  - loft_airfoil:     NACA 翼型放样

运行方式：
    python scripts/test_wing_model_pipeline.py
"""

import json
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WING_PARAMS_PATH = ROOT / "examples" / "wing_params.json"

SIMPLE_TRAPEZOID_PARAMS = {
    "build_mode": "simple_trapezoid",
    "span_mm": 1200,
    "root_chord_mm": 220,
    "tip_chord_mm": 130,
    "thickness_mm": 20,
    "sweep_deg": 0,
    "dihedral_deg": 0,
    "twist_root_deg": 0,
    "twist_tip_deg": 0,
    "airfoil_name": "simple_trapezoid",
    "output_name": "test_wing_pipeline",
}

LOFT_AIRFOIL_PARAMS = {
    "build_mode": "loft_airfoil",
    "span_mm": 1200,
    "root_chord_mm": 220,
    "tip_chord_mm": 130,
    "thickness_mm": 20,
    "sweep_deg": 0,
    "dihedral_deg": 0,
    "twist_root_deg": 0,
    "twist_tip_deg": 0,
    "airfoil_name": "NACA2412/NACA0012",
    "root_airfoil": "NACA2412",
    "tip_airfoil": "NACA0012",
    "output_name": "test_wing_loft",
}

WING_DIR = ROOT / "generated_models" / "solidworks" / "wing"


def write_params(params: dict) -> Path:
    WING_PARAMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    WING_PARAMS_PATH.write_text(
        json.dumps(params, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return WING_PARAMS_PATH


# STEP 文件必须包含的几何实体关键词（至少一个）
_STEP_GEOMETRY_KW = [
    "MANIFOLD_SOLID_BREP",
    "ADVANCED_FACE",
    "FACE_SURFACE",
    "CLOSED_SHELL",
    "B_SPLINE_CURVE_WITH_KNOTS",
    "EDGE_CURVE",
    "CARTESIAN_POINT",
    "DIRECTION",
    "VECTOR",
    "LINE",
    "CIRCLE",
    "SURFACE_OF_LINEAR_EXTRUSION",
    "PLANE",
]


def _check_step_geometry(step_path: Path) -> dict:
    """检查 STEP 文件是否包含几何实体（非空壳文件）。"""
    if not step_path.exists():
        return {"has_geometry": False, "keywords_found": [], "size_kb": 0.0}

    size_kb = step_path.stat().st_size / 1024
    try:
        content = step_path.read_text(encoding="utf-8", errors="replace")[:50000]
    except Exception:
        content = ""

    keywords_found = [kw for kw in _STEP_GEOMETRY_KW if kw in content]

    # 如果文件很小 (< 500 bytes) 且无几何关键词 → 空壳
    has_geometry = len(keywords_found) >= 2 and size_kb > 1.0

    return {
        "has_geometry": has_geometry,
        "keywords_found": keywords_found,
        "size_kb": round(size_kb, 1),
    }


def verify_files(output_name: str) -> dict:
    sldprt_path = WING_DIR / "parts" / f"{output_name}.SLDPRT"
    step_path = WING_DIR / "step" / f"{output_name}.STEP"
    results = {}
    for label, path in [("sldprt", sldprt_path), ("step", step_path)]:
        if path.exists():
            size_kb = path.stat().st_size / 1024
            results[label] = {
                "path": str(path), "exists": True,
                "size_kb": round(size_kb, 1), "valid": size_kb > 0,
            }
        else:
            results[label] = {
                "path": str(path), "exists": False,
                "size_kb": 0.0, "valid": False,
            }

    # STEP 几何内容检查
    step_geo = _check_step_geometry(step_path)
    results["step_geo"] = step_geo

    return results


def run_one_test(label: str, params: dict, strict_loft: bool = False) -> tuple[int, dict]:
    """执行单模式测试。返回 (exit_code, files_dict)。

    exit_code for loft_airfoil:
      default: 0 if geometry valid (even fallback), 1 if failed
      strict:  0 if true_loft, 2 if fallback, 1 if failed
    """
    print()
    print("─" * 58)
    print(f"  [{label}] build_mode={params['build_mode']}")
    print("─" * 58)

    output_name = params["output_name"]
    build_mode = params.get("build_mode", "simple_trapezoid")
    write_params(params)

    print(f"  输出名: {output_name}")
    process_error = None
    build_result = None

    try:
        from modules.solidworks_wing_builder import build_trapezoidal_wing
    except ImportError as e:
        print(f"  ❌ 无法导入: {e}")
        return 1, verify_files(output_name)

    try:
        build_result = build_trapezoidal_wing(**params)
    except Exception as e:
        process_error = str(e)
        print(f"  ⚠️ 异常: {e}")

    actual_mode = "?"
    if build_result is not None:
        actual_mode = build_result.get("build_actual_mode", build_result.get("build_mode", "?"))
        print(f"  ✅ 函数正常返回 (mode={build_result.get('build_mode','?')}, actual={actual_mode})")
    else:
        print(f"  ⚠️ 函数返回 None")

    files = verify_files(output_name)
    sldprt_ok = files["sldprt"]["valid"]
    step_ok = files["step"]["valid"]

    # 显示文件状态
    for lbl, key in [("SLDPRT", "sldprt"), ("STEP", "step")]:
        info = files[key]
        mark = "✅" if info["valid"] else "❌"
        if info["exists"]:
            print(f"  {mark} {lbl}: {Path(info['path']).name} ({info['size_kb']} KB)")
        else:
            print(f"  {mark} {lbl}: 未生成")

    # 判定（loft_airfoil 需要额外检查 STEP 几何内容）
    step_geo = files.get("step_geo", {})
    step_has_geo = step_geo.get("has_geometry", False)
    step_keywords = step_geo.get("keywords_found", [])

    if build_mode == "loft_airfoil":
        print(f"  STEP 几何关键词: {step_keywords}")
        print(f"  STEP 含几何实体: {step_has_geo}")

    if build_mode == "loft_airfoil" and not step_has_geo:
        files["_actual_mode"] = "failed"
        print(f"  ❌ {label}: FAIL (STEP 文件存在但无几何实体 — 空壳文件)")
        if step_keywords:
            print(f"     仅找到: {step_keywords}")
        return 1, files

    if sldprt_ok and step_ok:
        if build_result is not None and not process_error:
            # 区分 true_loft 和 fallback
            if build_mode == "loft_airfoil" and actual_mode == "fallback_extrude":
                files["_actual_mode"] = "fallback_extrude"
                if strict_loft:
                    print(f"  ❌ {label}: GEOMETRY_PASS_WITH_FALLBACK (strict)")
                    print(f"      说明: Loft 未成功，已回退为 NACA 等弦长拉伸。")
                    print(f"      严格模式下此结果视为未通过。")
                    return 2, files
                else:
                    print(f"  ⚠️  {label}: GEOMETRY_PASS_WITH_FALLBACK")
                    print(f"      说明: Loft 未成功，已回退为 NACA 等弦长拉伸。")
                    print(f"      模型包含有效 STEP 几何，但无双截面放样效果。")
                    return 0, files  # default: geometry OK → not an error
            elif build_mode == "loft_airfoil" and actual_mode == "true_loft":
                files["_actual_mode"] = "true_loft"
                print(f"  🏆 {label}: TRUE_LOFT_PASS")
                print(f"      说明: 真实双截面 Loft 放样成功。")
                return 0, files
            else:
                files["_actual_mode"] = actual_mode
                print(f"  🏆 {label}: PASS")
                return 0, files
        else:
            files["_actual_mode"] = "partial"
            print(f"  ⚠️ {label}: PARTIAL (文件已生成但函数异常)")
            return 2, files
    else:
        files["_actual_mode"] = "failed"
        missing = []
        if not sldprt_ok:
            missing.append("SLDPRT")
        if not step_ok:
            missing.append("STEP")
        print(f"  ❌ {label}: FAIL ({', '.join(missing)} 缺失)")
        return 1, files


def main(strict_loft: bool = False) -> int:
    print("=" * 58)
    print("  机翼建模管道 — 双模式回归测试")
    if strict_loft:
        print("  [严格模式] loft_airfoil 必须 TRUE_LOFT_PASS")
    print("=" * 58)

    # ── 先测试 NACA 生成器（纯数学，不调 SolidWorks）──
    print("\n  [0] NACA 翼型生成器自检")
    try:
        from modules.solidworks_wing_builder import generate_naca_4digit
        for code in ["0012", "2412", "4415"]:
            pts = generate_naca_4digit(code, 40)
            print(f"      NACA{code}: {len(pts)} points, "
                  f"x=[{min(p[0] for p in pts):.3f}, {max(p[0] for p in pts):.3f}], "
                  f"y=[{min(p[1] for p in pts):.3f}, {max(p[1] for p in pts):.3f}]")
        print("  ✅ NACA 生成器正常")
    except Exception as e:
        print(f"  ❌ NACA 生成器异常: {e}")
        return 1

    # ── 双模式测试 ──
    results = {}

    for label, params in [
        ("SIMPLE_TRAPEZOID", SIMPLE_TRAPEZOID_PARAMS),
        ("LOFT_AIRFOIL",     LOFT_AIRFOIL_PARAMS),
    ]:
        code, files = run_one_test(label, params, strict_loft=strict_loft)
        # Determine actual_mode from the build result (passed via files for now)
        actual = files.get("_actual_mode", "?")
        results[label] = {"code": code, "files": files, "actual_mode": actual}

    # ── 汇总 ──
    print()
    print("=" * 58)
    print("  测试汇总")
    print("=" * 58)
    fallback_detected = False
    for label, info in results.items():
        code = info["code"]
        files = info["files"]
        actual = info.get("actual_mode", "?")
        if code == 0:
            if label == "LOFT_AIRFOIL" and actual == "fallback_extrude":
                status = "GEOMETRY_PASS_WITH_FALLBACK"
                fallback_detected = True
            elif label == "LOFT_AIRFOIL" and actual == "true_loft":
                status = "TRUE_LOFT_PASS"
            else:
                status = "PASS"
        elif code == 2:
            if label == "LOFT_AIRFOIL" and actual == "fallback_extrude":
                status = "GEOMETRY_PASS_WITH_FALLBACK"
                fallback_detected = True
            else:
                status = "PARTIAL"
        else:
            status = "FAIL"
        print(f"  {status}")
        for key in ("sldprt", "step"):
            f = files[key]
            if f["valid"]:
                print(f"           {Path(f['path']).name} ({f['size_kb']} KB)")
            else:
                print(f"           {Path(f['path']).name} — 未生成")

    # ── 退出码 ──
    codes = [info["code"] for info in results.values()]

    # FAIL (code 1) always takes priority
    if 1 in codes:
        return 1

    # In strict mode: code 2 = fallback treated as error
    if strict_loft and 2 in codes:
        return 2

    # In default mode with fallback: print warning, exit 0
    if fallback_detected and not strict_loft:
        print()
        print("  WARNING: loft_airfoil used fallback_extrude, true Loft is not achieved.")
        print("  如需严格要求真实 Loft，请使用 --strict-loft 参数。")

    # Default mode: fallback → exit 0 (not an error)
    return 0


if __name__ == "__main__":
    strict = "--strict-loft" in sys.argv
    sys.exit(main(strict_loft=strict))
