#!/usr/bin/env python3
"""SolidWorks 连接测试脚本。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.solidworks_controller import print_solidworks_info

if __name__ == "__main__":
    print_solidworks_info()
