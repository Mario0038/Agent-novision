#!/usr/bin/env python3
"""运行带孔矩形板自动建模测试。"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.solidworks_controller import create_plate_with_center_hole
PARAMS_FILE = ROOT / "examples" / "plate_params.json"

# 读取参数
if not PARAMS_FILE.exists():
    print(f"[错误] 参数文件不存在: {PARAMS_FILE}")
    exit(1)

params = json.loads(PARAMS_FILE.read_text(encoding="utf-8"))

print("=" * 50)
print("  带孔矩形板自动建模")
print("=" * 50)
print(f"  参数: {json.dumps(params, indent=2, ensure_ascii=False)}")

result = create_plate_with_center_hole(
    length_mm=params["length_mm"],
    width_mm=params["width_mm"],
    thickness_mm=params["thickness_mm"],
    hole_diameter_mm=params["hole_diameter_mm"],
    output_dir=str(ROOT / "generated_models"),  # 子目录由 create_plate_with_center_hole 自动创建
)

if result:
    print(f"\n生成文件:")
    print(f"  SLDPRT: {result['sldprt']}")
    print(f"  STEP:   {result['step']}")
else:
    print("\n建模未成功完成。")
    exit(1)
