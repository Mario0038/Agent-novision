#!/usr/bin/env python3
"""
梯形机翼参数化建模入口
=======================
读取 examples/wing_params.json，调用 solidworks_wing_builder.py 创建机翼实体。

运行方式：
    python scripts/create_wing_model.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.solidworks_wing_builder import build_trapezoidal_wing

PARAMS_FILE = ROOT / "examples" / "wing_params.json"

if __name__ == "__main__":
    if not PARAMS_FILE.exists():
        print(f"[错误] 参数文件不存在: {PARAMS_FILE}")
        print(f"  请先创建 examples/wing_params.json")
        sys.exit(1)

    params = json.loads(PARAMS_FILE.read_text(encoding="utf-8"))

    print("=" * 55)
    print("  梯形机翼参数化建模")
    print("=" * 55)
    print(f"  参数文件: {PARAMS_FILE}")
    print(f"  参数内容:")
    for k, v in params.items():
        print(f"    {k}: {v}")
    print()

    result = build_trapezoidal_wing(**params)

    if result:
        print(f"\n生成文件:")
        print(f"  SLDPRT: {result['sldprt']}")
        print(f"  STEP:   {result['step']}")
    else:
        print("\n建模未成功完成。")
        sys.exit(1)
