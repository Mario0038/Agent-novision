#!/usr/bin/env python3
"""
SolidWorks COM 控制器
=====================
提供 SolidWorks 连接管理、基础信息查询和通用机械零件建模。
"""

import sys
import time
from pathlib import Path
from typing import Optional

import pythoncom
import win32com.client

# SolidWorks 文档类型常量
swDocPART = 1
swDocASSEMBLY = 2
swDocDRAWING = 3


def get_solidworks_app(visible: bool = True, force_new: bool = False):
    """连接正在运行的 SolidWorks，或启动新实例。

    Args:
        visible: 是否将 SolidWorks 窗口设为可见。
        force_new: True 时跳过连接已有实例，直接启动新实例。

    Returns:
        swApp: SolidWorks COM Application 对象，失败时返回 None。
    """
    pythoncom.CoInitialize()

    sw_app = None

    try:
        if force_new:
            sw_app = win32com.client.Dispatch("SldWorks.Application")
        else:
            try:
                sw_app = win32com.client.GetActiveObject("SldWorks.Application")
            except Exception:
                sw_app = win32com.client.Dispatch("SldWorks.Application")
    except Exception as e:
        print(f"[错误] 无法获取 SolidWorks Application 对象: {e}", file=sys.stderr)
        print("  请确认 SolidWorks 已安装且 COM 注册完整。", file=sys.stderr)
        pythoncom.CoUninitialize()
        return None

    try:
        if visible:
            sw_app.Visible = True
    except Exception:
        pass

    return sw_app


def get_solidworks_version(sw_app) -> Optional[str]:
    """从已连接的 SolidWorks 实例读取版本号。

    Returns:
        版本字符串，如 "31.0.0"；失败返回 None。
    """
    if sw_app is None:
        return None
    try:
        return sw_app.RevisionNumber()
    except Exception:
        pass
    try:
        return str(sw_app.Version)
    except Exception:
        return None


def print_solidworks_info():
    """连接 SolidWorks 并打印连接状态和版本信息。"""
    print("=" * 50)
    print("  SolidWorks COM 连接测试")
    print("=" * 50)

    print("\n正在连接 SolidWorks ...")
    sw_app = get_solidworks_app(visible=True)

    if sw_app is None:
        print("\n[失败] 无法连接到 SolidWorks。")
        print("  可能的原因：")
        print("    1. 此机器未安装 SolidWorks")
        print("    2. SolidWorks COM 注册不完整")
        print("    3. 权限不足")
        return

    print("\n[OK] SolidWorks Application 对象获取成功。")

    version = get_solidworks_version(sw_app)
    if version:
        print(f"      版本号: {version}")
    else:
        print("      版本号: 无法读取（可能为较旧版本或 API 兼容性问题）")

    try:
        doc_count = sw_app.GetDocumentCount()
        print(f"      当前活动文档数: {doc_count}")
    except Exception:
        pass

    print("\n[OK] SolidWorks 连接成功。")
    print("=" * 50)


# ──────────────────────────────────────────────────────────
# 通用机械零件建模
# ──────────────────────────────────────────────────────────

def _get_part_template_path(sw_app) -> str:
    """获取 SolidWorks 默认零件模板路径。"""
    try:
        path = sw_app.GetDocumentTemplate(swDocPART)
        if path and Path(path).exists():
            return path
    except Exception:
        pass
    # 回退：尝试常见路径（含中文 GB 模板）
    candidates = [
        "C:\\ProgramData\\SOLIDWORKS\\SOLIDWORKS 2024\\templates\\gb_part.prtdot",
        "C:\\ProgramData\\SOLIDWORKS\\SOLIDWORKS 2024\\templates\\Part.prtdot",
        "C:\\ProgramData\\SolidWorks\\SOLIDWORKS 2024\\templates\\Part.prtdot",
        "C:\\ProgramData\\SOLIDWORKS\\SOLIDWORKS 2023\\templates\\gb_part.prtdot",
        "C:\\ProgramData\\SOLIDWORKS\\SOLIDWORKS 2022\\templates\\gb_part.prtdot",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    raise FileNotFoundError(
        "无法定位 SolidWorks 零件模板。请手动指定模板路径。\n"
        "常见路径: C:\\ProgramData\\SolidWorks\\SOLIDWORKS 20XX\\templates\\Part.prtdot"
    )


def _select_by_id2(part, name: str, sel_type: str, x: float, y: float, z: float,
                   append: bool = False) -> bool:
    """封装 SelectByID2，使用 VARIANT 兼容 SolidWorks 中文版。"""
    try:
        ok = part.Extension.SelectByID2(
            name, sel_type, x, y, z, append,
            win32com.client.VARIANT(pythoncom.VT_I4, 0),       # Mark
            win32com.client.VARIANT(pythoncom.VT_DISPATCH, None),  # Callout
            win32com.client.VARIANT(pythoncom.VT_I4, 0),       # SelectOption
        )
        return bool(ok)
    except Exception:
        return False


def create_plate_with_center_hole(
    length_mm: float = 100.0,
    width_mm: float = 50.0,
    thickness_mm: float = 5.0,
    hole_diameter_mm: float = 10.0,
    output_dir: str = "generated_models",
):
    """通过 SolidWorks COM API 创建带中心通孔的矩形板。

    建模步骤：
      1. 在前视基准面绘制中心定位的矩形草图
      2. 拉伸实体
      3. 在板顶面绘制中心圆草图
      4. 拉伸切除生成通孔
      5. 保存 SLDPRT 和 STEP 文件

    Args:
        length_mm: 板长度 (X 方向, mm)
        width_mm: 板宽度 (Y 方向, mm)
        thickness_mm: 板厚度 (Z 方向, mm)
        hole_diameter_mm: 中心孔直径 (mm)
        output_dir: 输出目录路径

    Returns:
        dict: {"sldprt": Path, "step": Path} 或 None（失败时）
    """
    # SolidWorks API 草图坐标使用米
    L = length_mm / 1000.0
    W = width_mm / 1000.0
    T = thickness_mm / 1000.0
    D = hole_diameter_mm / 1000.0

    out_dir = Path(output_dir)
    parts_dir = out_dir / "solidworks" / "parts"
    step_dir = out_dir / "solidworks" / "step"
    logs_dir = out_dir / "logs"
    for d in [parts_dir, step_dir, logs_dir]:
        d.mkdir(parents=True, exist_ok=True)
    sldprt_path = parts_dir / "test_plate.SLDPRT"
    step_path = step_dir / "test_plate.STEP"

    sw_app = None
    part = None

    try:
        # ── 1. 连接 SolidWorks ─────────────────────────
        sw_app = get_solidworks_app(visible=True)
        if sw_app is None:
            print("[失败] 无法连接到 SolidWorks")
            return None

        # ── 2. 新建零件 ─────────────────────────────────
        template = _get_part_template_path(sw_app)
        print(f"  使用模板: {template}")
        part = sw_app.NewDocument(template, 0, 0, 0)
        time.sleep(0.5)

        # ── 3. 选择基准面并插入草图 ────────────────────
        # 尝试中文名和英文名的前视基准面
        selected = _select_by_id2(part, "前视基准面", "PLANE", 0, 0, 0)
        if not selected:
            selected = _select_by_id2(part, "Front Plane", "PLANE", 0, 0, 0)
        if not selected:
            selected = _select_by_id2(part, "上视基准面", "PLANE", 0, 0, 0)
        if not selected:
            selected = _select_by_id2(part, "Top Plane", "PLANE", 0, 0, 0)
        if not selected:
            print("[错误] 无法选择任何基准面")
            return None

        part.SketchManager.InsertSketch(True)

        # ── 4. 绘制矩形和中心圆（同一草图，圆自动成为孔）──
        sketch_mgr = part.SketchManager
        sketch_mgr.CreateCornerRectangle(-L / 2, -W / 2, 0, L / 2, W / 2, 0)
        sketch_mgr.CreateCircleByRadius(0, 0, 0, D / 2)
        part.ClearSelection2(True)
        part.SketchManager.InsertSketch(True)

        # ── 5. 一次拉伸生成带孔实体 ──────────────────────
        feature_mgr = part.FeatureManager
        feature_mgr.FeatureExtrusion2(
            True, False, False, 0, 0, T, 0.01,
            False, False, False, False, 0, 0.01,
            False, False, False, False,
            True, True, True, 0, 0, False,
        )
        part.ClearSelection2(True)

        # ── 6. 保存文件 ───────────────────────────────

        # ── 8. 保存 SLDPRT ──────────────────────────────
        # ── 8. 保存 SLDPRT ──────────────────────────────
        long_ret = part.SaveAs3(str(sldprt_path), 0, 0)
        print(f"  SLDPRT 已保存: {sldprt_path}")

        # ── 9. 导出 STEP ────────────────────────────────
        try:
            long_ret2 = part.SaveAs3(str(step_path), 0, 0)
            print(f"  STEP 已导出: {step_path}")
        except Exception as e_step:
            print(f"  [警告] STEP 导出失败: {e_step}")

        print(f"\n[OK] 建模完成。")
        print(f"  尺寸: {length_mm}x{width_mm}x{thickness_mm} mm")
        print(f"  中心孔: D{hole_diameter_mm} mm")

        return {"sldprt": sldprt_path, "step": step_path}

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
    print_solidworks_info()
