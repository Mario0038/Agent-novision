#!/usr/bin/env python3
"""
SolidWorks 机翼参数化建模模块
===============================
支持两种建模模式：
  - simple_trapezoid: 梯形实体（已有稳定功能）
  - loft_airfoil:     NACA 翼型双截面放样（新增）

依赖: modules/solidworks_controller.py (连接与基础工具)
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


# ═══════════════════════════════════════════════════════════
# NACA 4 位数翼型生成器
# ═══════════════════════════════════════════════════════════

def generate_naca_4digit(code: str, n_points: int = 80) -> list[tuple[float, float]]:
    """生成 NACA 4 位数翼型的上下表面坐标点。

    公式来源: NACA 4-digit series (Jacobs et al., 1933)

    Args:
        code: 翼型代码，如 "0012", "2412", "4415"
        n_points: 半表面采样点数（总返回约 2*n_points 点）

    Returns:
        坐标点列表 [(x, y), ...]，从 TE 上表面 → LE → TE 下表面，
        x 范围 [0, 1]，y 为无量纲厚度坐标。
    """
    code = code.strip().upper().replace("NACA", "")
    if len(code) != 4:
        raise ValueError(f"NACA 代码必须为 4 位数字，收到: {code}")

    m = int(code[0]) / 100.0      # 最大弯度
    p = int(code[1]) / 10.0       # 最大弯度位置
    t = int(code[2:]) / 100.0     # 最大厚度

    # 余弦分布点（前缘密、后缘疏）
    betas = [0.5 * (1 - math.cos(math.pi * i / (n_points - 1)))
             for i in range(n_points)]
    xs = list(betas)  # 0 (LE) → 1 (TE)

    upper: list[tuple[float, float]] = []
    lower: list[tuple[float, float]] = []

    for x in xs:
        # 厚度分布 (关闭后缘: TE 处厚度为 0)
        yt = 5 * t * (
            0.2969 * math.sqrt(x)
            - 0.1260 * x
            - 0.3516 * x**2
            + 0.2843 * x**3
            - 0.1015 * x**4   # 原系数 0.1036 改 0.1015 使 TE 厚度近 0
        )

        # 弯度线
        if m == 0:
            yc, dyc_dx = 0.0, 0.0
        else:
            if x < p:
                yc = m / p**2 * (2 * p * x - x**2)
                dyc_dx = 2 * m / p**2 * (p - x)
            else:
                yc = m / (1 - p)**2 * ((1 - 2 * p) + 2 * p * x - x**2)
                dyc_dx = 2 * m / (1 - p)**2 * (p - x)

        theta = math.atan(dyc_dx)

        # 上表面
        xu = x - yt * math.sin(theta)
        yu = yc + yt * math.cos(theta)
        upper.append((xu, yu))

        # 下表面
        xl = x + yt * math.sin(theta)
        yl = yc - yt * math.cos(theta)
        lower.append((xl, yl))

    # 组装: TE 上表面 → LE → TE 下表面（SolidWorks 草图顺序）
    # upper 已是 TE→LE，lower 是 LE→TE
    points = list(upper) + list(reversed(lower))

    # 归一化: 确保 x 范围在 [0, 1]，关闭 TE
    return [(max(0.0, min(1.0, p[0])), p[1]) for p in points]


# ═══════════════════════════════════════════════════════════
# 建模块
# ═══════════════════════════════════════════════════════════

def _setup_output_dirs(output_name: str) -> tuple[Path, Path, Path, Path]:
    """创建输出目录并返回路径。"""
    out_root = ROOT / "generated_models" / "solidworks" / "wing"
    parts_dir = out_root / "parts"
    step_dir = out_root / "step"
    logs_dir = ROOT / "generated_models" / "logs"
    for d in [parts_dir, step_dir, logs_dir]:
        d.mkdir(parents=True, exist_ok=True)
    return parts_dir, step_dir, parts_dir / f"{output_name}.SLDPRT", step_dir / f"{output_name}.STEP"


def _create_sketch_spline(sketch_mgr, points_2d: list[tuple[float, float]]):
    """在活动草图中通过一组 2D 点创建闭合样条曲线。

    先创建样条，再用直线闭合 TE 间隙（如有）。
    """
    pts = [(p[0], p[1], 0.0) for p in points_2d]
    coords = [v for pt in pts for v in pt]
    try:
        sketch_mgr.CreateSpline(coords)
    except Exception:
        for i in range(len(pts) - 1):
            sketch_mgr.CreateLine(pts[i][0], pts[i][1], 0,
                                  pts[i + 1][0], pts[i + 1][1], 0)
    # 闭合 TE（如果首尾点不重合）
    dx = pts[0][0] - pts[-1][0]
    dy = pts[0][1] - pts[-1][1]
    if abs(dx) > 1e-9 or abs(dy) > 1e-9:
        sketch_mgr.CreateLine(pts[-1][0], pts[-1][1], 0,
                              pts[0][0], pts[0][1], 0)


def _build_simple_trapezoid(part, span: float, root_c: float, tip_c: float,
                            depth: float, sweep_offset: float) -> None:
    """simple_trapezoid 模式：Top Plane 梯形 → 拉伸实体。"""
    # 选择 Top Plane
    selected = _select_by_id2(part, "上视基准面", "PLANE", 0, 0, 0)
    if not selected:
        selected = _select_by_id2(part, "Top Plane", "PLANE", 0, 0, 0)
    if not selected:
        raise RuntimeError("无法选择 Top Plane / 上视基准面")

    part.SketchManager.InsertSketch(True)
    sm = part.SketchManager

    rle_x, rle_y = 0.0, 0.0
    rte_x, rte_y = 0.0, root_c
    tte_x, tte_y = span, sweep_offset + tip_c
    tle_x, tle_y = span, sweep_offset

    sm.CreateLine(rle_x, rle_y, 0, rte_x, rte_y, 0)
    sm.CreateLine(rte_x, rte_y, 0, tte_x, tte_y, 0)
    sm.CreateLine(tte_x, tte_y, 0, tle_x, tle_y, 0)
    sm.CreateLine(tle_x, tle_y, 0, rle_x, rle_y, 0)

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
    time.sleep(0.3)


def _fallback_extrude_airfoil(part, pts_raw, chord, span, airfoil_code):
    """回退方案：将 NACA 翼型沿展向拉伸，生成等弦长机翼实体。"""
    print(f"  使用回退方案: {airfoil_code} 等弦长拉伸")

    # 选择 Right Plane
    ok = _select_by_id2(part, "Right Plane", "PLANE", 0, 0, 0)
    if not ok:
        ok = _select_by_id2(part, "右视基准面", "PLANE", 0, 0, 0)
    if not ok:
        raise RuntimeError("回退方案: 无法选择 Right Plane")

    part.SketchManager.InsertSketch(True)
    sm = part.SketchManager

    # 在 Right Plane (YZ) 上创建 NACA 翼型闭合轮廓
    pts_2d = [(chord * p[0], chord * p[1]) for p in pts_raw]
    _create_sketch_spline(sm, pts_2d)
    part.ClearSelection2(True)
    part.SketchManager.InsertSketch(True)

    # 沿 X 方向拉伸 span
    fm = part.FeatureManager
    fm.FeatureExtrusion2(
        True, False, False, 0, 0, span, 0.0,
        False, False, False, False, 0, 0.001,
        False, False, False, False,
        True, True, True, 0, 0, False,
    )
    part.ClearSelection2(True)
    time.sleep(0.3)
    print(f"  回退拉伸完成: span={span*1000:.0f}mm chord={chord*1000:.0f}mm")


def _build_loft_airfoil(part, span: float, root_c: float, tip_c: float,
                        sweep_offset: float, dihedral_offset: float,
                        twist_rad: float,
                        root_airfoil: str, tip_airfoil: str,
                        n_pts: int = 80) -> None:
    """loft_airfoil 模式：NACA 翼型双截面放样。

    坐标系：Right Plane 为根截面 (X=0, Y=弦向, Z=厚度)
    梢截面在 X=span 偏移平面上，包含后掠/上反/扭转。
    """
    # ── 生成翼型点 (无量纲) ──
    root_pts_raw = generate_naca_4digit(root_airfoil, n_pts)
    tip_pts_raw = generate_naca_4digit(tip_airfoil, n_pts)

    # 缩放 + 定位
    # 根截面: (X=0, Y = chord * x_airfoil, Z = thickness * y_airfoil)
    def scale_and_position(pts, chord, span_pos, sweep_y, dihedral_z, twist):
        result = []
        cos_t = math.cos(twist)
        sin_t = math.sin(twist)
        for (xa, ya) in pts:
            # 翼型坐标: xa 沿弦向 [0→1], ya 为厚度方向
            y_base = chord * xa
            z_base = chord * ya
            # 扭转: 绕 X 轴旋转
            y_rot = y_base * cos_t - z_base * sin_t
            z_rot = y_base * sin_t + z_base * cos_t
            result.append((span_pos, sweep_y + y_rot, dihedral_z + z_rot))
        return result

    root_pts = scale_and_position(root_pts_raw, root_c, 0.0, 0.0, 0.0, 0.0)
    tip_pts = scale_and_position(tip_pts_raw, tip_c,
                                 span,                    # X = 展向
                                 sweep_offset,            # Y (弦向) = 后掠偏移
                                 dihedral_offset,         # Z (垂直) = 上反偏移
                                 twist_rad)               # 扭转

    # ── 创建根截面草图 (Right Plane) ──
    selected = _select_by_id2(part, "右视基准面", "PLANE", 0, 0, 0)
    if not selected:
        selected = _select_by_id2(part, "Right Plane", "PLANE", 0, 0, 0)
    if not selected:
        raise RuntimeError("无法选择 Right Plane / 右视基准面")

    part.SketchManager.InsertSketch(True)
    sm = part.SketchManager
    # 在 Right Plane (YZ) 上: Y = 弦向, Z = 厚度
    pts_2d_root = [(p[1], p[2]) for p in root_pts]
    _create_sketch_spline(sm, pts_2d_root)
    part.ClearSelection2(True)
    part.SketchManager.InsertSketch(True)
    time.sleep(0.2)
    root_sketch_name = _get_last_sketch_name(part)

    # ── 创建梢截面偏移平面 ──
    part.ClearSelection2(True)
    time.sleep(0.1)

    # 选择 Right Plane 作为参考
    sel_ok = _select_by_id2(part, "Right Plane", "PLANE", 0, 0, 0)
    if not sel_ok:
        sel_ok = _select_by_id2(part, "右视基准面", "PLANE", 0, 0, 0)
    if not sel_ok:
        raise RuntimeError("无法选择 Right Plane 用于创建偏移平面")

    # 创建偏移参考平面
    print(f"  正在创建偏移平面, distance={span:.3f}m...")
    try:
        part.FeatureManager.InsertRefPlane(2, span, 0, 0, 0, 0)
        time.sleep(0.4)
    except Exception as e1:
        try:
            part.FeatureManager.InsertRefPlane(8, span, 0, 0, 0, 0)
            time.sleep(0.4)
        except Exception as e2:
            raise RuntimeError(f"无法创建偏移参考平面: {e1} / {e2}")

    # ── 选中新平面并创建草图 ──
    # 新创建的参考平面会以 "Plane1" / "基准面1" 等名称出现在特征树中
    # 尝试直接 InsertSketch(True) — 新平面创建后应处于选中状态
    part.SketchManager.InsertSketch(True)
    sm2 = part.SketchManager
    pts_2d_tip = [(p[1], p[2]) for p in tip_pts]
    _create_sketch_spline(sm2, pts_2d_tip)
    part.ClearSelection2(True)
    part.SketchManager.InsertSketch(True)
    time.sleep(0.2)
    tip_sketch_name = _get_last_sketch_name(part, skip=root_sketch_name)

    # ── Loft ──
    print(f"  草图名: root={root_sketch_name}  tip={tip_sketch_name}")

    # 选第一个草图
    part.ClearSelection2(True)
    time.sleep(0.15)
    s1 = _select_sketch_by_name(part, root_sketch_name, append=False)
    if not s1:
        part.ClearSelection2(True)
        s1 = _select_by_id2(part, root_sketch_name, "SKETCH", 0, 0, 0, False)
    print(f"  选中 root: {s1}")

    # 选第二个草图 (append)
    s2 = _select_sketch_by_name(part, tip_sketch_name, append=True)
    if not s2:
        s2 = _select_by_id2(part, tip_sketch_name, "SKETCH", 0, 0, 0, True)
    print(f"  选中 tip:  {s2}")

    if not (s1 and s2):
        raise RuntimeError(
            f"无法选中 Loft 草图: root={root_sketch_name} tip={tip_sketch_name}"
        )

    # 直接调用 Loft（不查询 SelectionMgr 以免扰乱选择状态）
    feature = None
    try:
        feature = part.FeatureManager.InsertProtrusionBlend(
            False,  # Thin
            True,   # Solid
            False,  # Merge
            1,      # Direction
            0,      # TwistType
            0,      # TwistVal
            False,  # KeepTangency
            1,      # AdvancedSmoothing
            0,      # StartMatch
            True,   # StartConstraint (NormalToProfile)
            0.0,    # StartTanLen
            True,   # EndConstraint (NormalToProfile)
            0.0,    # EndTanLen
            False,  # UseStartCurv
            False,  # UseEndCurv
            False,  # MergeResult
            False,  # UseFeatScope
        )
    except Exception as e:
        raise RuntimeError(f"Loft API 调用失败: {e}")

    part.ClearSelection2(True)

    print(f"  Loft feature: {feature.Name if feature else 'None'}")

    # ── 强制重建 + 检查实体 ──
    try:
        part.ForceRebuild3(True)
    except Exception:
        pass
    time.sleep(0.5)

    # 检查 solid body 数量
    try:
        bodies = part.GetBodies2(0, False)  # 0=swSolidBody
    except Exception:
        # 尝试 swBodyType_e 的其他值
        try:
            bodies = part.GetBodies2(0, True)  # True=all bodies
        except Exception:
            bodies = None

    body_count = len(bodies) if bodies else 0
    print(f"  Loft 后 solid body 数量: {body_count}")

    if body_count == 0 and feature is not None:
        # feature 存在但无 body — 可能是曲面体
        try:
            surf_bodies = part.GetBodies2(1, False)  # 1=swSurfaceBody
            surf_count = len(surf_bodies) if surf_bodies else 0
            print(f"  surface body 数量: {surf_count}")
        except Exception:
            surf_count = 0
        if surf_count > 0:
            print("  [警告] Loft 生成了曲面体而非实体 — 请检查草图是否闭合")

    actual_mode = "true_loft"  # will be overridden if fallback used

    if body_count == 0:
        print("  [回退] Loft 未生成 solid body，切换为 NACA 翼型拉伸…")
        _fallback_extrude_airfoil(part, root_pts_raw, root_c, span, root_airfoil)
        actual_mode = "fallback_extrude"

    return actual_mode


def _get_last_sketch_name(part, skip: str = "") -> str:
    """获取最近创建的草图名称。"""
    try:
        # 从后往前遍历特征树，找最近的草图
        feat = part.FirstFeature()
        names: list[str] = []
        while feat is not None:
            ftype = feat.GetTypeName2()
            if ftype == "ProfileFeature":
                names.append(feat.Name)
            feat = feat.GetNextFeature()
        # 返回最后一个（最新）非 skip 的草图名
        for n in reversed(names):
            if n != skip:
                return n
    except Exception:
        pass
    return "Sketch2" if skip else "Sketch1"


def _cn_sketch_name(name: str) -> str:
    """英文草圖名 → 中文草圖名。"""
    if "Sketch" in name:
        return name.replace("Sketch", "草图")
    if "草图" in name:
        return name.replace("草图", "Sketch")
    return name


def _select_sketch_by_name(part, name: str, append: bool = False) -> bool:
    """尝试多种名称格式选择草图（兼容中英文 SolidWorks）。"""
    if _select_by_id2(part, name, "SKETCH", 0, 0, 0, append):
        return True
    alt = _cn_sketch_name(name)
    if alt != name and _select_by_id2(part, alt, "SKETCH", 0, 0, 0, append):
        return True
    return False


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def build_trapezoidal_wing(
    span_mm: float = 1200.0,
    root_chord_mm: float = 220.0,
    tip_chord_mm: float = 130.0,
    thickness_mm: float = 20.0,
    sweep_deg: float = 0.0,
    dihedral_deg: float = 0.0,
    twist_root_deg: float = 0.0,
    twist_tip_deg: float = 0.0,
    airfoil_name: str = "simple_trapezoid",
    output_name: str = "low_speed_uav_wing_demo",
    build_mode: str = "simple_trapezoid",
    root_airfoil: str = "NACA2412",
    tip_airfoil: str = "NACA0012",
) -> dict | None:
    """通过 SolidWorks COM API 创建参数化机翼实体。

    Args:
        span_mm: 翼展 (mm)
        root_chord_mm: 根弦长 (mm)
        tip_chord_mm: 尖弦长 (mm)
        thickness_mm: 最大厚度 (mm) — simple_trapezoid 模式使用
        sweep_deg: 后掠角 (deg)
        dihedral_deg: 上反角 (deg, simple_trapezoid 仅记录)
        twist_root_deg: 根部扭转角 (deg, simple_trapezoid 仅记录)
        twist_tip_deg: 梢部扭转角 (deg, simple_trapezoid 仅记录)
        airfoil_name: 翼型标识 (simple_trapezoid 模式显示)
        output_name: 输出文件名（不含扩展名）
        build_mode: "simple_trapezoid" | "loft_airfoil"
        root_airfoil: 根翼型代码 (loft_airfoil 模式, 如 "NACA2412")
        tip_airfoil: 尖翼型代码 (loft_airfoil 模式, 如 "NACA0012")

    Returns:
        dict: {"sldprt": Path, "step": Path, "build_mode": str} 或 None
    """
    # ── 单位转换 ──
    span = span_mm / 1000.0
    root_c = root_chord_mm / 1000.0
    tip_c = tip_chord_mm / 1000.0
    depth = thickness_mm / 1000.0
    sweep_rad = math.radians(sweep_deg)
    sweep_offset = span * math.tan(sweep_rad)
    dihedral_rad = math.radians(dihedral_deg)
    dihedral_offset = span * math.tan(dihedral_rad)
    twist_rad = math.radians(twist_tip_deg - twist_root_deg)

    mode = build_mode if build_mode in ("simple_trapezoid", "loft_airfoil") else "simple_trapezoid"

    # ── 输出目录 ──
    parts_dir, step_dir, sldprt_path, step_path = _setup_output_dirs(output_name)

    sw_app = None
    part = None

    try:
        # ── 1. 连接 SolidWorks ──
        sw_app = get_solidworks_app(visible=True)
        if sw_app is None:
            print("[失败] 无法连接到 SolidWorks")
            return None

        # ── 2. 新建零件 ──
        template = _get_part_template_path(sw_app)
        print(f"  使用模板: {template}")
        part = sw_app.NewDocument(template, 0, 0, 0)
        time.sleep(0.5)

        # ── 3. 按模式建模 ──
        build_actual_mode = mode  # simple_trapezoid → simple_trapezoid
        if mode == "simple_trapezoid":
            print(f"  建模模式: simple_trapezoid")
            _build_simple_trapezoid(part, span, root_c, tip_c, depth, sweep_offset)
        else:  # loft_airfoil
            print(f"  建模模式: loft_airfoil  (根 {root_airfoil} / 尖 {tip_airfoil})")
            print(f"  后掠: {sweep_deg}°  上反: {dihedral_deg}°  扭转: {twist_tip_deg - twist_root_deg}°")
            build_actual_mode = _build_loft_airfoil(part, span, root_c, tip_c,
                               sweep_offset, dihedral_offset, twist_rad,
                               root_airfoil, tip_airfoil)

        # ── 4. 保存 ──
        long_ret = part.SaveAs3(str(sldprt_path), 0, 0)
        print(f"  SLDPRT 已保存: {sldprt_path}")

        try:
            long_ret2 = part.SaveAs3(str(step_path), 0, 0)
            print(f"  STEP 已导出: {step_path}")
        except Exception as e_step:
            print(f"  [警告] STEP 导出失败: {e_step}")

        print()
        print(f"  [OK] 机翼建模完成。")
        print(f"  翼展: {span_mm} mm")
        print(f"  根弦: {root_chord_mm} mm  |  尖弦: {tip_chord_mm} mm")
        if mode == "loft_airfoil":
            print(f"  根翼型: {root_airfoil}  |  尖翼型: {tip_airfoil}")
            print(f"  后掠: {sweep_deg}°  上反: {dihedral_deg}°  扭转: {twist_tip_deg - twist_root_deg}°")
        else:
            print(f"  厚度: {thickness_mm} mm")
            print(f"  后掠: {sweep_deg} deg")
        print(f"  翼型: {airfoil_name if mode == 'simple_trapezoid' else root_airfoil + '/' + tip_airfoil}")

        return {"sldprt": sldprt_path, "step": step_path, "build_mode": mode,
                "build_actual_mode": build_actual_mode}

    except Exception as e:
        print(f"\n[错误] 建模过程中出现异常: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None

    finally:
        if part is not None:
            try:
                part = None
            except Exception:
                pass


if __name__ == "__main__":
    import json
    params_path = ROOT / "examples" / "wing_params.json"
    if params_path.exists():
        params = json.loads(params_path.read_text(encoding="utf-8"))
        mode = params.get("build_mode", "simple_trapezoid")
        print("=" * 55)
        print(f"  机翼参数化建模 ({mode})")
        print("=" * 55)
        result = build_trapezoidal_wing(**params)
        if result:
            print(f"\n  生成文件:")
            print(f"    SLDPRT: {result['sldprt']}")
            print(f"    STEP:   {result['step']}")
        else:
            print("\n  建模未成功完成。")
    else:
        print(f"[错误] 参数文件不存在: {params_path}")
