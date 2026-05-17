#!/usr/bin/env python
"""
独立识图命令行入口 — 调用千问 VL 模型分析图片。

用法:
    python scripts/vision_image.py --image <图片路径> [--prompt <自定义提示词>]
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.vision_client import analyze_image


def main():
    parser = argparse.ArgumentParser(
        description="千问视觉模型识图工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  python scripts/vision_image.py --image examples/vision_test/test.png\n"
               '  python scripts/vision_image.py --image photo.jpg --prompt "请分析这张图片"',
    )
    parser.add_argument(
        "--image", required=True,
        help="图片文件路径 (支持 png, jpg, jpeg, webp)",
    )
    parser.add_argument(
        "--prompt", default=None,
        help="自定义识图提示词 (可选)",
    )
    args = parser.parse_args()

    result = analyze_image(image_path=args.image, prompt=args.prompt)
    print(result)

    if result.startswith("错误:"):
        sys.exit(1)


if __name__ == "__main__":
    main()
