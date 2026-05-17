"""
识图核心模块 — 使用 OpenAI 兼容格式调用千问视觉模型。

参考: reference/qwen_vision_demo/vision.js
"""

import base64
import os
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from PIL import Image

load_dotenv()

VISION_API_KEY = os.getenv("VISION_API_KEY", "")
VISION_BASE_URL = os.getenv("VISION_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen3.5-omni-plus")

SUPPORTED_FORMATS = {"png", "jpg", "jpeg", "webp"}

DEFAULT_PROMPT = (
    "请用中文分析这张图片，说明图片中的主要内容、可能的问题、"
    "关键信息和需要注意的细节。"
)


def _image_to_data_url(image_path: str) -> str:
    """将本地图片转换为 base64 data URL。"""
    path = Path(image_path)
    ext = path.suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    if ext not in ("jpeg", "png", "webp"):
        raise ValueError(f"不支持的图片格式: .{ext}，支持: png, jpg, jpeg, webp")

    with open(path, "rb") as f:
        raw = f.read()

    return f"data:image/{ext};base64,{base64.b64encode(raw).decode('utf-8')}"


def analyze_image(image_path: str, prompt: str = None) -> str:
    """分析图片并返回文字描述。

    Args:
        image_path: 图片文件路径
        prompt: 自定义提示词，默认使用中文分析提示

    Returns:
        模型返回的识图结果文本，失败时返回错误信息
    """
    # 1. 检查 API Key
    if not VISION_API_KEY:
        return "错误: 未配置 VISION_API_KEY，请在 .env 中设置"

    # 2. 检查图片文件
    path = Path(image_path)
    if not path.exists():
        return f"错误: 图片文件不存在: {image_path}"

    ext = path.suffix.lower().lstrip(".")
    if ext == "jpg":
        ext = "jpeg"
    if ext not in SUPPORTED_FORMATS:
        return f"错误: 不支持的图片格式 .{ext}，支持: {', '.join(sorted(SUPPORTED_FORMATS))}"

    # 3. 用 Pillow 验证图片格式
    try:
        img = Image.open(image_path)
        img.verify()
    except Exception as e:
        return f"错误: 无法读取图片文件: {e}"

    # 4. 转换为 base64 data URL
    try:
        image_url = _image_to_data_url(image_path)
    except Exception as e:
        return f"错误: 图片编码失败: {e}"

    # 5. 调用视觉模型
    user_prompt = prompt or DEFAULT_PROMPT

    try:
        client = OpenAI(
            api_key=VISION_API_KEY,
            base_url=VISION_BASE_URL,
        )
        response = client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {"type": "text", "text": user_prompt},
                    ],
                }
            ],
            stream=False,
            max_tokens=1024,
        )
        content = response.choices[0].message.content
        return content if content else "警告: 模型返回了空内容"
    except Exception as e:
        return f"错误: API 调用失败: {e}"
