#!/usr/bin/env python
"""
视觉模块环境检查 — 检查配置和依赖是否就绪，不实际调用 API。
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def check():
    all_ok = True

    # 1. 检查 .env
    env_path = ROOT / ".env"
    if env_path.exists():
        print("[OK] .env 文件存在")
    else:
        print("[FAIL] .env 文件不存在")
        all_ok = False

    # 2. 检查 VISION_API_KEY (不打印值)
    key = os.getenv("VISION_API_KEY", "")
    if key:
        masked = key[:4] + "****" + key[-4:] if len(key) > 8 else "***"
        print(f"[OK] VISION_API_KEY 已配置: {masked}")
    else:
        print("[FAIL] VISION_API_KEY 未配置，请在 .env 中设置")
        all_ok = False

    # 3. 检查 VISION_BASE_URL
    expected_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    actual_url = os.getenv("VISION_BASE_URL", "")
    if not actual_url:
        print(f"[WARN] VISION_BASE_URL 未配置，将使用默认值: {expected_url}")
    elif actual_url == expected_url:
        print(f"[OK] VISION_BASE_URL 正确: {actual_url}")
    else:
        print(f"[WARN] VISION_BASE_URL 与预期不同")
        print(f"       当前值: {actual_url}")
        print(f"       预期值: {expected_url}")

    # 4. 检查 VISION_MODEL
    expected_model = "qwen3.5-omni-plus"
    actual_model = os.getenv("VISION_MODEL", "")
    if not actual_model:
        print(f"[WARN] VISION_MODEL 未配置，将使用默认值: {expected_model}")
    elif actual_model == expected_model:
        print(f"[OK] VISION_MODEL 正确: {actual_model}")
    else:
        print(f"[WARN] VISION_MODEL 与预期不同")
        print(f"       当前值: {actual_model}")
        print(f"       预期值: {expected_model}")

    # 5. 检查 vision_client 导入
    try:
        from modules import vision_client  # noqa: F401
        print("[OK] vision_client 模块可导入")
    except ImportError as e:
        print(f"[FAIL] vision_client 模块导入失败: {e}")
        all_ok = False

    # 6. 检查 Pillow
    try:
        from PIL import Image  # noqa: F401
        print("[OK] Pillow 已安装")
    except ImportError:
        print("[FAIL] Pillow 未安装，请运行: pip install Pillow")
        all_ok = False

    # 7. 检查 openai
    try:
        import openai  # noqa: F401
        print("[OK] openai 已安装")
    except ImportError:
        print("[FAIL] openai 未安装，请运行: pip install openai")
        all_ok = False

    print()
    if all_ok:
        print("环境检查全部通过。")
    else:
        print("存在未通过的检查项，请修复后再试。")
        sys.exit(1)


if __name__ == "__main__":
    check()
