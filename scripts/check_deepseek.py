import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
model = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

if not api_key:
    raise RuntimeError("没有读取到 DEEPSEEK_API_KEY，请检查 .env 文件")

client = OpenAI(
    api_key=api_key,
    base_url=base_url,
)

response = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": "你是一个严谨的中文写作助手。"},
        {"role": "user", "content": "请用一句话说明什么是写作 Agent。"},
    ],
)

print(response.choices[0].message.content)