#!/usr/bin/env python3
"""
SolidWorks 通用零件模板建模模块。

当前支持的非武器化教学/验证零件：
- plate: 带可选中心孔的矩形板
- cylinder: 圆柱/套筒
- flange: 简化圆法兰
- bracket: L 形支架
- box: 简化开口盒/壳体

这些是参数化模板，不是任意自由造型 CAD 生成器。
"""

import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.solidworks_controller import (
    get_solidworks_app,
    _get_part_template_path,
    _select_by_id2,
)


def _mm(value, default):
    try:
        return float(value) / 1000.0
    except (TypeError, ValueError):
        return float(default) / 1000.0


def _setup_output_dirs(part_type: str, output_name: str) -> tuple[Path, Path]:
    out_root = ROOT / "generated_models" / "solidworks" / part_type
    parts_dir = out_root / "parts"
    step_dir = out_root / "step"
    logs_dir = ROOT / "generated_models" / "logs"
    for d in [parts_dir, step_dir, logs_dir]:
        d.mkdir(parents=True, exist_ok=True)
    return parts_dir / f"{output_name}.SLDPRT", step_dir / f"{output_name}.STEP"


def _select_plane(part, *names: str) -> None:
    for name in names:
        if _select_by_id2(part, name, "PLANE", 0, 0, 0):
            return
    raise RuntimeError(f"无法选择基准面: {', '.join(names)}")


def _extrude(part, depth: float) -> None:
    part.ClearSelection2(True)
    part.SketchManager.InsertSketch(True)
    fm = part.FeatureManager
    fm.FeatureExtrusion2(
        True, False, False, 0, 0, depth, 0.0,
        False, False, False, False, 0, 0.001,
        False, False, False, False,
        True, True, True, 0, 0, False,
    )
    part.ClearSelection2(True)
    time.sleep(0.2)


def _sketch_plate(part, geo: dict) -> None:
    length = _mm(geo.get("length_mm"), 100)
    width = _mm(geo.get("width_mm"), 60)
    hole_d = _mm(geo.get("hole_diameter_mm"), 0)
    _select_plane(part, "前视基准面", "Front Plane", "上视基准面", "Top Plane")
    part.SketchManager.InsertSketch(True)
    sm = part.SketchManager
    sm.CreateCornerRectangle(-length / 2, -width / 2, 0, length / 2, width / 2, 0)
    if hole_d > 0:
        sm.CreateCircleByRadius(0, 0, 0, hole_d / 2)


def _sketch_cylinder(part, geo: dict) -> None:
    outer_d = _mm(geo.get("outer_diameter_mm") or geo.get("diameter_mm"), 60)
    inner_d = _mm(geo.get("inner_diameter_mm"), 0)
    _select_plane(part, "前视基准面", "Front Plane", "上视基准面", "Top Plane")
    part.SketchManager.InsertSketch(True)
    sm = part.SketchManager
    sm.CreateCircleByRadius(0, 0, 0, outer_d / 2)
    if inner_d > 0 and inner_d < outer_d:
        sm.CreateCircleByRadius(0, 0, 0, inner_d / 2)


def _sketch_flange(part, geo: dict) -> None:
    outer_d = _mm(geo.get("outer_diameter_mm") or geo.get("diameter_mm"), 120)
    inner_d = _mm(geo.get("inner_diameter_mm") or geo.get("hole_diameter_mm"), 40)
    bolt_d = _mm(geo.get("bolt_hole_diameter_mm") or geo.get("hole_diameter_mm"), 10)
    bolt_circle_d = _mm(geo.get("bolt_circle_diameter_mm"), outer_d * 1000 * 0.72)
    bolt_count = int(geo.get("bolt_count", 4) or 4)
    _select_plane(part, "前视基准面", "Front Plane", "上视基准面", "Top Plane")
    part.SketchManager.InsertSketch(True)
    sm = part.SketchManager
    sm.CreateCircleByRadius(0, 0, 0, outer_d / 2)
    if inner_d > 0 and inner_d < outer_d:
        sm.CreateCircleByRadius(0, 0, 0, inner_d / 2)
    if bolt_d > 0:
        radius = bolt_circle_d / 2
        for i in range(max(1, bolt_count)):
            a = 2 * math.pi * i / bolt_count
            sm.CreateCircleByRadius(radius * math.cos(a), radius * math.sin(a), 0, bolt_d / 2)


def _sketch_bracket(part, geo: dict) -> None:
    height = _mm(geo.get("height_mm"), 80)
    length = _mm(geo.get("length_mm"), 80)
    thickness = _mm(geo.get("thickness_mm"), 8)
    _select_plane(part, "前视基准面", "Front Plane")
    part.SketchManager.InsertSketch(True)
    sm = part.SketchManager
    pts = [
        (0, 0), (length, 0), (length, thickness),
        (thickness, thickness), (thickness, height), (0, height), (0, 0),
    ]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        sm.CreateLine(x1, y1, 0, x2, y2, 0)


def _sketch_box(part, geo: dict) -> None:
    length = _mm(geo.get("length_mm"), 120)
    height = _mm(geo.get("height_mm"), 80)
    wall = _mm(geo.get("thickness_mm"), 5)
    _select_plane(part, "前视基准面", "Front Plane")
    part.SketchManager.InsertSketch(True)
    sm = part.SketchManager
    sm.CreateCornerRectangle(-length / 2, -height / 2, 0, length / 2, height / 2, 0)
    if wall * 2 < min(length, height):
        sm.CreateCornerRectangle(
            -length / 2 + wall, -height / 2 + wall, 0,
            length / 2 - wall, height / 2 - wall, 0,
        )


def build_generic_part(part_type: str, geometry: dict, output_name: str = "generic_part") -> dict | None:
    """按模板创建通用非武器化机械零件。"""
    part_type = (part_type or "unknown").lower()
    if part_type not in {"plate", "cylinder", "flange", "bracket", "box"}:
        raise ValueError(f"不支持的通用零件类型: {part_type}")

    depth_defaults = {
        "plate": geometry.get("thickness_mm", 6),
        "cylinder": geometry.get("height_mm") or geometry.get("length_mm", 80),
        "flange": geometry.get("thickness_mm", 12),
        "bracket": geometry.get("width_mm", 40),
        "box": geometry.get("width_mm", 60),
    }
    depth = _mm(depth_defaults[part_type], 20)

    sldprt_path, step_path = _setup_output_dirs(part_type, output_name)
    sw_app = None
    part = None

    try:
        sw_app = get_solidworks_app(visible=True)
        if sw_app is None:
            print("[失败] 无法连接到 SolidWorks")
            return None

        template = _get_part_template_path(sw_app)
        print(f"  使用模板: {template}")
        part = sw_app.NewDocument(template, 0, 0, 0)
        time.sleep(0.5)

        print(f"  建模模板: {part_type}")
        if part_type == "plate":
            _sketch_plate(part, geometry)
        elif part_type == "cylinder":
            _sketch_cylinder(part, geometry)
        elif part_type == "flange":
            _sketch_flange(part, geometry)
        elif part_type == "bracket":
            _sketch_bracket(part, geometry)
        elif part_type == "box":
            _sketch_box(part, geometry)

        _extrude(part, depth)

        part.SaveAs3(str(sldprt_path), 0, 0)
        print(f"  SLDPRT 已保存: {sldprt_path}")
        try:
            part.SaveAs3(str(step_path), 0, 0)
            print(f"  STEP 已导出: {step_path}")
        except Exception as e_step:
            print(f"  [警告] STEP 导出失败: {e_step}")

        return {"sldprt": sldprt_path, "step": step_path, "part_type": part_type}
    except Exception as e:
        print(f"\n[错误] 通用零件建模异常: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None
    finally:
        if part is not None:
            try:
                part = None
            except Exception:
                pass
