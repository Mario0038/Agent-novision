#!/usr/bin/env python3
"""
战术导弹总体设计领域专业 Agent
================================
基于 DeepSeek V4 Pro 的命令行交互式专业分析与写作助手。
支持长期记忆、自动提取候选记忆、习惯学习功能。

运行方式：python domain_agent.py

命令速览：
  记忆写入  /remember  /style  /workflow  /correction  /focus
  自动学习  /autolearn on|off|status
  记忆管理  /candidates  /acceptmem  /rejectmem  /forget
  识图      /vision image=<path> prompt=<text>
  文献      /docs  /kbtopics  /searchdocs 关键词  /askdocs 问题
  设计      /design_task 设计需求
  系统      /memory  /reload  /help
  退出      exit / quit / 退出
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from modules.vision_client import analyze_image
from modules.doc_search import search as doc_search, format_results as format_doc_results
from modules.design_parser import run_design_task
from modules.agent_router import route_user_input
from modules.design_synthesizer import synthesize_design_params, format_synthesis_result, is_safe_for_synthesis
from modules.task_planner import plan_task

# ═══════════════════════════════════════════════════════════
# 路径与常量
# ═══════════════════════════════════════════════════════════
ROOT = Path(__file__).resolve().parent
SESSIONS_DIR = ROOT / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

BEST_PROMPT_PATH = ROOT / "output" / "best_prompt.md"
MEMORY_DIR = ROOT / "knowledge_base" / "memory"
SUMMARIES_DIR = MEMORY_DIR / "session_summaries"
CANDIDATE_FILE = MEMORY_DIR / "candidate_memories.md"
AUTO_SETTINGS_FILE = MEMORY_DIR / "auto_memory_settings.md"

for d in [SESSIONS_DIR, MEMORY_DIR, SUMMARIES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

MEMORY_FILES: dict[str, Path] = {
    "user_profile":          MEMORY_DIR / "user_profile.md",
    "writing_preferences":   MEMORY_DIR / "writing_preferences.md",
    "workflow_preferences":  MEMORY_DIR / "workflow_preferences.md",
    "correction_patterns":   MEMORY_DIR / "correction_patterns.md",
    "domain_focus":          MEMORY_DIR / "domain_focus.md",
}

MEMORY_LABELS: dict[str, str] = {
    "user_profile":          "用户背景与偏好",
    "writing_preferences":   "写作风格偏好",
    "workflow_preferences":  "工作流程偏好",
    "correction_patterns":   "纠错模式",
    "domain_focus":          "领域关注方向",
}

MANUAL_COMMANDS: dict[str, str] = {
    "/remember":   "user_profile",
    "/style":      "writing_preferences",
    "/workflow":   "workflow_preferences",
    "/correction": "correction_patterns",
    "/focus":      "domain_focus",
}

MAX_HISTORY = 10
MAX_MEMORY_CHARS = 5000

# ═══════════════════════════════════════════════════════════
# 环境变量
# ═══════════════════════════════════════════════════════════
load_dotenv(ROOT / ".env")
API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro")

if not API_KEY:
    print("❌ 未读取到 DEEPSEEK_API_KEY，请检查 .env 文件", file=sys.stderr)
    sys.exit(1)

# ═══════════════════════════════════════════════════════════
# System Prompt 构建
# ═══════════════════════════════════════════════════════════
SAFETY_APPENDIX = """

## 安全边界（必须严格遵守）

以下内容**绝对禁止**出现在任何回答中：
- 在役或在研具体导弹型号的完整总体参数、性能指标
- 可执行的制导律算法、引战配合优化公式、战斗部设计方法
- 实战部署方案、攻击策略、突防战术、杀伤概率推导
- 可直接用于武器实现的工程数据集

如果用户的请求涉及上述内容，你必须：
1. 明确告知用户该请求涉及安全边界
2. 将问题转换为**高层次的方法论讨论**或**系统工程概念分析**
3. 以教学性、综述性的方式回答，不提供可操作的具体方案"""


def load_base_prompt() -> str:
    if BEST_PROMPT_PATH.exists():
        content = BEST_PROMPT_PATH.read_text(encoding="utf-8").strip()
        if content:
            return content
    print("❌ 未找到 output/best_prompt.md", file=sys.stderr)
    sys.exit(1)


def load_memory_section() -> str:
    blocks: list[str] = []
    total = 0
    for key, path in MEMORY_FILES.items():
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        label = MEMORY_LABELS.get(key, key)
        if len(text) > 1500:
            text = "…(较早内容已省略)\n" + text[-1500:]
        blocks.append(f"### {label}\n{text}")
        total += len(text)
        if total > MAX_MEMORY_CHARS:
            blocks.append("…(记忆总量超限，后续记忆已省略)")
            break
    if not blocks:
        return ""
    return "\n\n## 长期记忆（用户偏好与习惯）\n\n" + "\n\n".join(blocks)


def build_system_prompt() -> str:
    return load_base_prompt() + SAFETY_APPENDIX + load_memory_section()


# ═══════════════════════════════════════════════════════════
# API Client
# ═══════════════════════════════════════════════════════════
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


def call_api(messages: list[dict], temperature: float = 0.7) -> str:
    try:
        resp = client.chat.completions.create(
            model=MODEL, temperature=temperature, messages=messages,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"[API 调用失败] {e}"


def trim_history(messages: list[dict]) -> list[dict]:
    system_msg = messages[0]
    history = messages[1:]
    return [system_msg] + history[-(2 * MAX_HISTORY):]


# ═══════════════════════════════════════════════════════════
# 自动学习设置
# ═══════════════════════════════════════════════════════════
def load_auto_settings() -> dict:
    if not AUTO_SETTINGS_FILE.exists():
        return {"auto_learn": "off", "auto_write_confidence": "high"}
    text = AUTO_SETTINGS_FILE.read_text(encoding="utf-8")
    settings: dict = {}
    for line in text.strip().split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            settings[k.strip()] = v.strip()
    return settings


def save_auto_settings(settings: dict):
    settings["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"{k}: {v}" for k, v in settings.items()]
    AUTO_SETTINGS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ═══════════════════════════════════════════════════════════
# 安全校验
# ═══════════════════════════════════════════════════════════
API_KEY_PATTERN = re.compile(r"sk-[a-zA-Z0-9_-]{20,}")
SENSITIVE_KW = ["api_key", "api key", "password", "密码", "密钥", "token",
                "手机号", "身份证", "账号"]


def memory_safe_check(content: str) -> bool:
    if API_KEY_PATTERN.search(content):
        return False
    low = content.lower()
    for kw in SENSITIVE_KW:
        if kw in low and len(content) < 200:
            return False
    return True


# ═══════════════════════════════════════════════════════════
# 手动记忆写入
# ═══════════════════════════════════════════════════════════
def append_to_memory(key: str, content: str) -> bool:
    path = MEMORY_FILES[key]
    path.parent.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    entry = f"- {date_str}：{content}\n"
    # 去重：检查是否已有高度相似的条目
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if content[:40] in existing:
        return False
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)
    return True


def show_memory_status():
    print("\n  📋 长期记忆状态")
    print(f"  {'─' * 38}")
    total = 0
    for key, path in MEMORY_FILES.items():
        label = MEMORY_LABELS.get(key, key)
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
            chars = len(text)
            lines = text.count("\n") + 1 if text else 0
            total += chars
            print(f"  {label:<14} {lines:>3} 行  {chars:>5} 字符")
        else:
            print(f"  {label:<14}  (空)")
    print(f"  {'─' * 38}")
    print(f"  记忆总量: {total} 字符  (注入上限: {MAX_MEMORY_CHARS} 字符)")


# ═══════════════════════════════════════════════════════════
# /docs — 列出已入库文献
# ═══════════════════════════════════════════════════════════
MANIFEST_PATH = ROOT / "knowledge_base" / "index" / "docs_manifest.json"
TOPIC_SUMMARY_PATH = ROOT / "knowledge_base" / "index" / "topic_summary.json"


def show_docs():
    """读取 docs_manifest.json 并格式化显示已入库文档清单。"""
    if not MANIFEST_PATH.exists():
        print("  📭 尚未找到文献索引。")
        print("     请先运行：python scripts/ingest_documents.py")
        return

    try:
        data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, Exception) as e:
        print(f"  ❌ 文献索引读取失败: {e}")
        return

    # 兼容两种结构：list 或 {docs: [...]} 或 {documents: [...]}
    if isinstance(data, list):
        docs = data
    elif isinstance(data, dict):
        docs = data.get("docs") or data.get("documents") or []
    else:
        print("  ❌ 文献索引格式异常")
        return

    if not docs:
        print("  📭 当前知识库没有已入库文档。")
        return

    total = len(docs)
    print(f"\n  📚 当前知识库文档：{total} 篇\n")

    max_show = 30
    for i, d in enumerate(docs[:max_show], 1):
        fname = d.get("file_name", "?")
        ftype = d.get("file_type", "?").upper()
        chars = d.get("char_count", 0)
        page = d.get("page_count", d.get("section_count", "-"))
        source = d.get("source_file", "")
        processed = d.get("processed_file", "")

        print(f"  [{i}] {fname}")
        print(f"      类型: {ftype}")
        print(f"      字符数: {chars:,}")
        print(f"      页数/章节: {page}")
        print(f"      原始路径: {source}")
        print(f"      处理后: {processed}")
        print()

    if total > max_show:
        print(f"  … 其余 {total - max_show} 篇文档已省略。")
        print()


def show_kb_topics():
    if not TOPIC_SUMMARY_PATH.exists():
        print("  📭 尚未生成主题统计。请先运行：python scripts/refine_kb_metadata.py")
        return

    try:
        data = json.loads(TOPIC_SUMMARY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  ❌ 读取主题统计失败：{exc}")
        return

    total_docs = int(data.get("total_docs", data.get("total_documents", 0)))
    topic_counts = data.get("topic_counts", {}) or {}
    safety_counts = data.get("safety_counts", {}) or {}
    layer_counts = data.get("knowledge_layer_counts", {}) or {}

    print(f"\n  🧭 知识库主题统计：{total_docs} 篇文档\n")

    if topic_counts:
        print("  主题分布:")
        for topic, count in sorted(topic_counts.items(), key=lambda item: item[1], reverse=True):
            print(f"    - {topic}: {count}")
        print()

    if safety_counts:
        print("  安全标签:")
        for label, count in sorted(safety_counts.items(), key=lambda item: item[1], reverse=True):
            print(f"    - {label}: {count}")
        print()

    if layer_counts:
        print("  知识层级:")
        for layer, count in sorted(layer_counts.items(), key=lambda item: item[1], reverse=True):
            print(f"    - {layer}: {count}")
        print()


# ═══════════════════════════════════════════════════════════
# 自动记忆提取（退出时调用）
# ═══════════════════════════════════════════════════════════
MEMORY_EXTRACTION_PROMPT = """你是一位用户偏好分析专家。你的任务是从一段对话历史中提取用户的**长期稳定偏好**。

## 提取类别

请从以下类别中识别值得记录的长期偏好：

1. **writing_preferences** — 写作风格偏好（格式、语气、结构、引用方式等）
2. **workflow_preferences** — 工作流程偏好（分析步骤、决策顺序、迭代方式等）
3. **correction_patterns** — 纠错模式（用户对你错误的纠正、术语修正、方法修正等）
4. **domain_focus** — 领域关注方向（用户长期关注的技术主题、研究方向等）
5. **user_profile** — 用户背景与长期偏好（身份、专业背景、长期目标等）

## 提取标准（严格）

- ✅ 只提取**长期稳定**的偏好，不提取一次性任务
- ✅ 只提取**用户明确表达或反复出现**的模式
- ❌ 不提取普通问答内容
- ❌ 不提取 API Key、密码、账号、手机号等敏感信息
- ❌ 不提取不确定或模型猜测的内容
- ❌ 不提取具体的武器设计参数、制导攻击细节

## 输出格式

请严格输出 JSON（不要包含 markdown 代码块标记）：

{
  "candidates": [
    {
      "category": "writing_preferences",
      "content": "用户偏好使用表格对比不同方案的优劣",
      "evidence": "用户在第3轮明确表示'用表格对比更直观'",
      "confidence": "high",
      "reason": "用户直接表达了偏好，属于长期稳定的格式偏好"
    }
  ]
}

confidence 取值：high（用户明确表达）、medium（用户反复出现但未明确声明）、low（可推断但不确定）

如果没有值得记录的长期偏好，返回：{"candidates": []}"""


def extract_candidate_memories(messages: list[dict]) -> list[dict]:
    """调用 DeepSeek 提取本轮会话中的长期偏好候选。"""
    dialogue_parts: list[str] = []
    for i, m in enumerate(messages):
        if m["role"] == "system":
            continue
        role = "用户" if m["role"] == "user" else "Agent"
        dialogue_parts.append(f"[{role}] {m['content']}")
    dialogue_text = "\n\n".join(dialogue_parts[-30:])  # 最多取最近 30 条

    resp = call_api(
        messages=[
            {"role": "system", "content": MEMORY_EXTRACTION_PROMPT},
            {"role": "user", "content": f"请从以下对话中提取长期偏好：\n\n{dialogue_text}"},
        ],
        temperature=0.2,
    )
    # 解析 JSON
    try:
        # 去除可能的 markdown 代码块标记
        cleaned = resp.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```\w*\n?", "", cleaned)
            cleaned = re.sub(r"\n```$", "", cleaned)
        data = json.loads(cleaned)
        return data.get("candidates", [])
    except json.JSONDecodeError:
        return []


def write_candidates_to_file(candidates: list[dict]):
    """将候选记忆写入 candidate_memories.md。"""
    if not candidates:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"\n## 候选记忆 - {timestamp}\n"]
    for c in candidates:
        lines.append(f"- category: {c.get('category', '')}")
        lines.append(f"- confidence: {c.get('confidence', 'low')}")
        lines.append(f"- content: {c.get('content', '')}")
        lines.append(f"- evidence: {c.get('evidence', '')}")
        lines.append(f"- reason: {c.get('reason', '')}")
        lines.append(f"- status: pending\n")
    with open(CANDIDATE_FILE, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))


def auto_write_high_confidence(candidates: list[dict]):
    """自动写入 high confidence 的候选到正式记忆文件。"""
    written = 0
    for c in candidates:
        if c.get("confidence") != "high":
            continue
        cat = c.get("category", "")
        content = c.get("content", "")
        if cat not in MEMORY_FILES:
            continue
        if not memory_safe_check(content):
            continue
        if append_to_memory(cat, content):
            written += 1
    if written:
        print(f"  📝 已自动写入 {written} 条 high-confidence 记忆")


# ═══════════════════════════════════════════════════════════
# /candidates /acceptmem /rejectmem /forget
# ═══════════════════════════════════════════════════════════
def show_candidates():
    if not CANDIDATE_FILE.exists():
        print("  📭 尚无候选记忆。")
        return
    text = CANDIDATE_FILE.read_text(encoding="utf-8").strip()
    if not text or text == "# 候选记忆":
        print("  📭 尚无候选记忆。")
        return
    # 显示最近 60 行
    lines = text.split("\n")
    recent = lines[-60:]
    print("\n  📋 候选记忆（最近部分）\n")
    for line in recent:
        print(f"  {line}")
    print()


def accept_candidates():
    """将 pending 候选（high/medium）写入正式记忆，标记为 accepted。"""
    if not CANDIDATE_FILE.exists():
        print("  📭 尚无候选记忆。")
        return
    text = CANDIDATE_FILE.read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=## 候选记忆)", text)
    accepted_count = 0
    new_blocks: list[str] = []
    for block in blocks:
        if "status: pending" not in block:
            new_blocks.append(block)
            continue
        # 提取 confidence
        conf_m = re.search(r"confidence:\s*(\w+)", block)
        conf = conf_m.group(1) if conf_m else "low"
        if conf not in ("high", "medium"):
            new_blocks.append(block)
            continue
        # 提取 category 和 content
        cat_m = re.search(r"category:\s*(\w+)", block)
        content_m = re.search(r"content:\s*(.+)", block)
        if not cat_m or not content_m:
            new_blocks.append(block)
            continue
        cat = cat_m.group(1)
        content = content_m.group(1).strip()
        if cat not in MEMORY_FILES:
            new_blocks.append(block)
            continue
        if not memory_safe_check(content):
            new_blocks.append(block.replace("status: pending", "status: rejected (safety)"))
            continue
        if append_to_memory(cat, content):
            block = block.replace("status: pending", "status: accepted")
            accepted_count += 1
        else:
            block = block.replace("status: pending", "status: rejected (duplicate)")
        new_blocks.append(block)
    CANDIDATE_FILE.write_text("".join(new_blocks), encoding="utf-8")
    print(f"  ✅ 已接受 {accepted_count} 条候选记忆，已写入正式记忆文件")


def reject_candidates():
    """将所有 pending 候选标记为 rejected。"""
    if not CANDIDATE_FILE.exists():
        print("  📭 尚无候选记忆。")
        return
    text = CANDIDATE_FILE.read_text(encoding="utf-8")
    text = text.replace("status: pending", "status: rejected")
    CANDIDATE_FILE.write_text(text, encoding="utf-8")
    print("  ✅ 所有 pending 候选已标记为 rejected")


def forget_keyword(keyword: str):
    """在所有正式记忆文件中搜索关键字并显示匹配条目。"""
    if not keyword:
        print("  ⚠️  请提供搜索关键字，例如：/forget 表格")
        return
    found = 0
    for key, path in MEMORY_FILES.items():
        if not path.exists():
            continue
        label = MEMORY_LABELS.get(key, key)
        lines = path.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines):
            if keyword.lower() in line.lower() and line.strip():
                print(f"  [{label}] L{i + 1}: {line.strip()}")
                found += 1
    if found == 0:
        print(f"  ℹ️  未找到包含「{keyword}」的记忆条目")
    else:
        print(f"\n  ℹ️  找到 {found} 条匹配。请手动编辑对应文件删除不需要的条目。")


# ═══════════════════════════════════════════════════════════
# 会话保存
# ═══════════════════════════════════════════════════════════
def save_session(messages: list[dict], session_file: Path):
    lines = [
        "# 战术导弹总体设计领域专业 Agent 会话记录\n",
        f"- **时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        f"- **模型**：{MODEL}\n",
        f"- **轮次**：{(len(messages) - 1) // 2} 轮\n",
        "\n---\n\n",
    ]
    for msg in messages:
        if msg["role"] == "system":
            continue
        role = "### 👤 用户\n" if msg["role"] == "user" else "### 🤖 Agent\n"
        lines.append(role)
        lines.append(msg["content"])
        lines.append("\n\n---\n\n")
    session_file.write_text("".join(lines), encoding="utf-8")


def save_session_summary(messages: list[dict]):
    user_msgs = [m["content"] for m in messages if m["role"] == "user"]
    topics = [m[:60] for m in user_msgs if not m.startswith("/")]
    if not topics:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    summary_file = SUMMARIES_DIR / f"summary_{timestamp}.md"
    lines = [
        f"# 会话摘要 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n",
        f"- 轮次：{(len(messages) - 1) // 2}\n",
        f"- 话题：\n",
    ]
    for t in topics[:15]:
        lines.append(f"  - {t}\n")
    summary_file.write_text("".join(lines), encoding="utf-8")


# ═══════════════════════════════════════════════════════════
# 主循环
# ═══════════════════════════════════════════════════════════
def print_banner():
    settings = load_auto_settings()
    auto_status = settings.get("auto_learn", "off")
    auto_conf = settings.get("auto_write_confidence", "high")
    print("=" * 55)
    print("  战术导弹总体设计领域专业 Agent")
    print(f"  模型: {MODEL}")
    print(f"  System Prompt: {BEST_PROMPT_PATH}")
    print(f"  长期记忆: {MEMORY_DIR}")
    print(f"  自动学习: {auto_status}  (仅写入 >= {auto_conf})")
    print(f"  上下文窗口: 最近 {MAX_HISTORY} 轮")
    print("=" * 55)
    print("  命令: /remember /style /workflow /correction /focus")
    print("        /autolearn on|off|status  /candidates")
    print("        /acceptmem  /rejectmem  /forget <kwd>")
    print("        /vision image=<path> prompt=<text>")
    print("        /docs  /kbtopics  /searchdocs <kwd>  /askdocs <question>")
    print("        /design_task <描述>")
    print("        /memory  /reload  /help  exit/quit/退出")
    print("=" * 55)
    print("  💡 也可以直接输入含图片路径的自然语言，例如：")
    print("     请分析 examples/vision_test/test.png 这张图片")
    print("=" * 55)


def print_help():
    print("""
  ┌──────────────────────────────────────────────────────────┐
  │  可用命令                                                 │
  ├──────────────────────────────────────────────────────────┤
  │  手动记忆写入                                             │
  │    /remember 内容      存入用户偏好记忆                    │
  │    /style 内容         存入写作风格记忆                    │
  │    /workflow 内容      存入工作流程记忆                    │
  │    /correction 内容    存入纠错模式记忆                    │
  │    /focus 内容         存入领域关注记忆                    │
  ├──────────────────────────────────────────────────────────┤
  │  自动学习管理                                             │
  │    /autolearn on       开启自动学习（退出时自动写入 high）  │
  │    /autolearn off      关闭自动学习（仅生成候选）           │
  │    /autolearn status   显示当前自动学习状态                │
  ├──────────────────────────────────────────────────────────┤
  │  候选记忆管理                                             │
  │    /candidates         查看最近候选记忆                    │
  │    /acceptmem          接受 pending 候选 → 写入正式记忆     │
  │    /rejectmem          拒绝所有 pending 候选               │
  │    /forget keyword     搜索正式记忆中包含关键字的条目        │
  ├──────────────────────────────────────────────────────────┤
  │  识图                                                     │
  │    /vision image=路径 prompt=提示词                         │
  │    /vision 图片路径 提示词                                  │
  │    自然语言（含图片路径+分析意图时自动触发）                  │
  │    例如：请分析 examples/vision_test/test.png 这张图片       │
  ├──────────────────────────────────────────────────────────┤
  │  文献检索                                                   │
  │    /docs                 列出已入库文献                      │
  │    /kbtopics             查看主题/安全标签统计                │
  │    /searchdocs 关键词     检索相关片段（不调用 API）           │
  │    /askdocs 问题          检索后由 DeepSeek 回答（调用 API）   │
  ├──────────────────────────────────────────────────────────┤
  │  工程设计任务解析                                            │
  │    /design_task 描述     解析设计需求，检索知识库，输出        │
  │                          结构化方案建议（不调用 SolidWorks）    │
  ├──────────────────────────────────────────────────────────┤
  │  系统                                                     │
  │    /memory             显示长期记忆摘要                    │
  │    /reload             重新加载 prompt 和记忆               │
  │    /help               显示本帮助                          │
  │    exit / quit / 退出   退出（自动提取候选记忆）            │
  └──────────────────────────────────────────────────────────┘
  默认：自动学习 = off，退出时生成候选但不自动写入正式记忆。
  只有 /acceptmem 或开启 /autolearn on 才会写入正式记忆。
""")


def is_slash_command(s: str) -> bool:
    return s.startswith("/")


def _parse_vision_args(arg: str):
    """解析 /vision 命令参数。

    支持格式:
        image=path/to/img.png prompt=请分析
        或位置参数: path/to/img.png 请分析这张图片

    Returns:
        (image_path: str | None, prompt: str | None)
    """
    image_path = None
    prompt = None

    # 尝试 key=value 格式
    img_match = re.search(r"image=(.+?)(?:\s+prompt=|\s*$)", arg)
    prompt_match = re.search(r"prompt=(.+)", arg)

    if img_match:
        image_path = img_match.group(1).strip()
        # 去除可能的引号
        image_path = image_path.strip("\"'")
    if prompt_match:
        prompt = prompt_match.group(1).strip()
        prompt = prompt.strip("\"'")

    # 如果 key=value 没匹配到 image，尝试位置参数
    if not image_path and arg:
        parts = arg.split(maxsplit=1)
        image_path = parts[0].strip()
        if len(parts) > 1:
            prompt = parts[1].strip() if not prompt else prompt

    return image_path, prompt


# ═══════════════════════════════════════════════════════════
# 自然语言图片路径自动识别
# ═══════════════════════════════════════════════════════════
_IMAGE_EXTS = r"\.(?:png|jpg|jpeg|webp)"

# 需要从识别出的路径首尾剥离的包装字符
_PATH_WRAPPERS = '`"\'""'' \t,，。、；;:：.!?*)]}）'

_INTENT_KW = re.compile(
    r"分析|识别|看看|帮我看看|帮我看|这张图|图片|截图|"
    r"云图|工程图|图中|什么问题|什么原因|描述|说明"
)


def detect_image_request(user_input: str):
    """从自然语言输入中检测图片分析请求。

    Returns:
        (image_path, prompt, auto_call)
        - auto_call=True:  检测到图片路径且有分析意图，应自动调用识图
        - auto_call=False: 检测到图片路径但无分析意图，仅提示
        - image_path 为 None: 未检测到图片路径
    """
    image_path = None
    raw_path = None

    # Step 1: 尝试匹配各类引号包裹的路径（可含空格）
    quote_pairs = [
        ('"', '"'), ("'", "'"), ("`", "`"),
        ("“", "”"),  # 中文双引号 " "
        ("‘", "’"),  # 中文单引号 ' '
    ]
    for left, right in quote_pairs:
        pat = re.escape(left) + r"(.+?" + _IMAGE_EXTS + r")" + re.escape(right)
        m = re.search(pat, user_input, re.IGNORECASE)
        if m:
            image_path = m.group(1)
            raw_path = left + m.group(1) + right  # 含引号的完整片段
            break

    # Step 2: 回退到无空格/无引号路径
    if not image_path:
        m = re.search(rf"(\S+{_IMAGE_EXTS})", user_input, re.IGNORECASE)
        if m:
            raw_path = m.group(1)
            image_path = raw_path

    if not image_path:
        return None, None, False

    # Step 3: 剥离首尾包装字符
    image_path = image_path.strip(_PATH_WRAPPERS)
    if not image_path:
        return None, None, False

    # Step 4: 检查分析意图
    has_intent = bool(_INTENT_KW.search(user_input))

    # Step 5: 从用户输入中移除路径片段，剩余作为 prompt
    escaped_raw = re.escape(raw_path)
    remaining = re.sub(rf"\s*{escaped_raw}\s*", " ", user_input, count=1).strip()

    if has_intent:
        prompt = remaining if remaining else None
        return image_path, prompt, True
    else:
        return image_path, None, False


# ═══════════════════════════════════════════════════════════
# 设计参数确认流程（CAD / CAD+FEA 路由使用）
# ═══════════════════════════════════════════════════════════

_pending_params: dict | None = None  # 待确认的设计参数（跨轮次保留）
_pending_route: str | None = None
_pending_request: str | None = None


def _run_design_confirmation_flow(user_input: str, route: str) -> str | None:
    """设计参数确认流程：synthesize → confirm → execute。

    Returns:
        格式化输出文本，或 None（取消/跳过）。
    """
    global _pending_params, _pending_route, _pending_request

    # 检查是否是对上一轮 pending 参数的修改
    if _pending_params and _is_param_modification(user_input):
        _apply_param_modification(user_input, _pending_params)
        print("  📝 参数已更新：")
        print(format_synthesis_result(_pending_params))
        print("  请确认以上参数后输入 y 执行，或继续修改。")
        return None

    # ── 1. 任务规划 ──
    print("  📋 解析设计需求...", end="", flush=True)
    plan = plan_task(user_input)
    print(f"\r{' ' * 20}\r", end="")

    # ── 2. 知识库检索 ──
    print("  📚 检索知识库...", end="", flush=True)
    knowledge = doc_search(user_input, top_k=5)
    print(f"\r{' ' * 20}\r", end="")

    # ── 3. 参数综合 ──
    print("  🔬 综合设计参数...", end="", flush=True)
    dry_run = os.getenv("DESIGN_SYNTH_DRY_RUN", "").lower() in ("1", "true", "yes", "on")
    _pending_params = synthesize_design_params(user_input, plan, knowledge, dry_run=dry_run)
    _pending_route = route
    _pending_request = user_input
    print(f"\r{' ' * 20}\r", end="")

    # ── 4. 输出确认表 ──
    print()
    print(format_synthesis_result(_pending_params))
    print()
    print(f"  路由: {route}  |  build_mode: {_pending_params.get('build_mode', '?')}")
    print("  以上参数将用于建模/仿真，请确认。")
    print("    y  = 确认执行")
    print("    n  = 取消")
    print("   修改 <参数> = <新值>  (例如: 修改 厚度为30mm)")
    return None


def _param_value(section: dict, key: str, default=None):
    entry = section.get(key, default)
    if isinstance(entry, dict):
        return entry.get("value", default)
    return entry


def _material_text(material_name: str | None) -> str:
    if not material_name:
        return "6061铝合金"
    low = material_name.lower()
    if "7075" in low:
        return "7075铝合金"
    if "6061" in low or "aluminum" in low:
        return "6061铝合金"
    if "steel" in low:
        return "结构钢"
    if "titanium" in low or "ti-" in low:
        return "钛合金"
    if "carbon" in low:
        return "碳纤维"
    return material_name


def _confirmed_params_to_workflow_input(pending: dict, route: str, original: str | None) -> str:
    """将确认后的结构化参数转换成 task_planner 可解析的自然语言任务。"""
    geo = pending.get("geometry", {})
    mat = pending.get("material", {})
    fea = pending.get("fea", {})
    part_type = pending.get("part_type", "unknown")

    thick = _param_value(geo, "thickness_mm", 8)
    material = _material_text(_param_value(mat, "material_name", "Aluminum 6061-T6"))

    if part_type == "wing":
        span = _param_value(geo, "span_mm", 1200)
        root = _param_value(geo, "root_chord_mm", 220)
        tip = _param_value(geo, "tip_chord_mm", float(root) * 0.6 if root else 132)
        sweep = _param_value(geo, "sweep_deg", 0)
        dihedral = _param_value(geo, "dihedral_deg", 0)
        parts = [
            f"创建一个翼展{span}mm、根弦{root}mm、尖弦{tip}mm、厚度{thick}mm的低速无人机梯形机翼",
            f"后掠角{sweep}度，上反角{dihedral}度",
            f"材料为{material}",
            "并导出STEP",
        ]
    elif part_type == "plate":
        length = _param_value(geo, "length_mm", 100)
        width = _param_value(geo, "width_mm", 60)
        hole = _param_value(geo, "hole_diameter_mm", None)
        hole_text = f"，中心孔{hole}mm" if hole else ""
        parts = [f"创建一个长度{length}mm、宽度{width}mm、厚度{thick}mm的矩形板{hole_text}，材料为{material}，并导出STEP"]
    elif part_type == "cylinder":
        diameter = _param_value(geo, "outer_diameter_mm", _param_value(geo, "diameter_mm", 60))
        inner = _param_value(geo, "inner_diameter_mm", None)
        height = _param_value(geo, "height_mm", _param_value(geo, "length_mm", 80))
        inner_text = f"，内径{inner}mm" if inner else ""
        parts = [f"创建一个直径{diameter}mm{inner_text}、高度{height}mm的圆柱，材料为{material}，并导出STEP"]
    elif part_type == "flange":
        outer = _param_value(geo, "outer_diameter_mm", _param_value(geo, "diameter_mm", 120))
        inner = _param_value(geo, "inner_diameter_mm", 40)
        hole = _param_value(geo, "hole_diameter_mm", 10)
        parts = [f"创建一个外径{outer}mm、内径{inner}mm、厚度{thick}mm、安装孔{hole}mm的圆法兰，材料为{material}，并导出STEP"]
    elif part_type == "bracket":
        length = _param_value(geo, "length_mm", 80)
        width = _param_value(geo, "width_mm", 40)
        height = _param_value(geo, "height_mm", 80)
        parts = [f"创建一个长度{length}mm、宽度{width}mm、高度{height}mm、厚度{thick}mm的L形支架，材料为{material}，并导出STEP"]
    elif part_type == "box":
        length = _param_value(geo, "length_mm", 120)
        width = _param_value(geo, "width_mm", 60)
        height = _param_value(geo, "height_mm", 80)
        parts = [f"创建一个长度{length}mm、宽度{width}mm、高度{height}mm、壁厚{thick}mm的开口盒体壳体，材料为{material}，并导出STEP"]
    else:
        parts = [original or "创建一个通用机械零件并导出STEP"]

    if route == "cad_fea" or _param_value(fea, "analysis_type"):
        fixed = _param_value(fea, "fixed_region", "root")
        load_region = _param_value(fea, "load_region", "tip")
        force = _param_value(fea, "force_N", None)
        direction = _param_value(fea, "force_direction", "Z")
        fixed_cn = "根部" if fixed == "root" else str(fixed)
        load_cn = "翼尖" if load_region == "tip" else str(load_region)
        parts.append(f"{fixed_cn}固定")
        if force is not None:
            parts.append(f"在{load_cn}施加{force}N {direction}轴方向力")
        parts.append("做静力分析，输出最大变形和最大等效应力")

    if original:
        parts.append(f"原始需求：{original}")
    return "，".join(parts)


def _is_param_modification(text: str) -> bool:
    return bool(re.search(r"修改|改成|改为|换成|变更为", text))


def _apply_param_modification(text: str, pending: dict):
    """将用户修改应用到 pending_params。"""
    # 厚度: 厚度30mm / 厚度为30mm / 改成厚度30
    m = re.search(r"(?:厚度|thickness)[^\d]*(\d+\.?\d*)", text)
    if m:
        pending.setdefault("geometry", {})["thickness_mm"] = {
            "value": float(m.group(1)), "source": "user_specified", "confidence": "high"}
        return

    # 材料: 材料改成7075 / 换成钛合金 / 改为ABS
    for kw, mat in [
        ("7075", "Aluminum 7075-T6"), ("钛合金", "Titanium Ti-6Al-4V"),
        ("钛", "Titanium Ti-6Al-4V"), ("不锈钢", "Stainless Steel 304"),
        ("钢", "Structural Steel"), ("ABS", "ABS Plastic"),
        ("碳纤维", "Carbon Fiber UD Prepreg"), ("6061", "Aluminum 6061-T6"),
        ("铝合金", "Aluminum 6061-T6"),
    ]:
        if kw in text:
            pending.setdefault("material", {})["material_name"] = {
                "value": mat, "source": "user_specified", "confidence": "high"}
            return

    # 翼展
    m = re.search(r"(?:翼展|span)[^\d]*(\d+\.?\d*)", text)
    if m:
        pending.setdefault("geometry", {})["span_mm"] = {
            "value": float(m.group(1)), "source": "user_specified", "confidence": "high"}
        return

    # 载荷
    m = re.search(r"(?:载荷|力|force)[^\d]*(\d+\.?\d*)\s*(?:N|牛)?", text)
    if m:
        pending.setdefault("fea", {})["force_N"] = {
            "value": float(m.group(1)), "source": "user_specified", "confidence": "high"}
        return

    print("  ⚠️ 未能识别的参数修改格式。支持: 厚度/材料/翼展/载荷。")


def main():
    global _pending_params, _pending_route, _pending_request

    print_banner()
    system_prompt = build_system_prompt()
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    round_count = 0

    while True:
        try:
            user_input = input(f"\n[{round_count + 1}] 👤 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n会话结束。")
            break

        if not user_input:
            continue

        # ── 退出 ──────────────────────────────────────
        if user_input.lower() in ("exit", "quit", "退出"):
            print("\n再见。")

            # 自动记忆提取
            if round_count > 0:
                print("  🧠 正在分析会话，提取长期偏好候选…")
                candidates = extract_candidate_memories(messages)
                if candidates:
                    write_candidates_to_file(candidates)
                    high_n = sum(1 for c in candidates if c.get("confidence") == "high")
                    med_n = sum(1 for c in candidates if c.get("confidence") == "medium")
                    low_n = sum(1 for c in candidates if c.get("confidence") == "low")
                    print(f"  📋 已提取 {len(candidates)} 条候选记忆 "
                          f"(high:{high_n} medium:{med_n} low:{low_n})")
                    print(f"  📁 候选记忆已保存至 {CANDIDATE_FILE}")

                    settings = load_auto_settings()
                    if settings.get("auto_learn") == "on":
                        auto_write_high_confidence(candidates)
                    else:
                        print("  💡 自动学习已关闭，输入 /acceptmem 确认写入")
                        print("     或输入 /autolearn on 开启自动学习")
                else:
                    print("  ℹ️  本轮未发现值得记录的长期偏好")
            break

        # ── 设计参数待确认：优先处理 y/n/修改，避免被普通聊天路由吞掉 ──
        if _pending_params and (
            user_input.lower() in ("y", "yes", "n", "no")
            or _is_param_modification(user_input)
        ):
            if _is_param_modification(user_input):
                _apply_param_modification(user_input, _pending_params)
                print("  📝 参数已更新：")
                print(format_synthesis_result(_pending_params))
                print("  请确认后输入 y 执行，或继续修改。")
                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "assistant", "content": "[设计参数已更新，等待用户确认执行]"})
                messages = trim_history(messages)
                round_count += 1
                continue

            confirm = user_input.lower()
            if confirm in ("n", "no"):
                print("  ⏭️ 已取消。")
                messages.append({"role": "user", "content": user_input})
                messages.append({"role": "assistant", "content": "[已取消设计建模/分析任务]"})
                _pending_params = None
                _pending_route = None
                _pending_request = None
                messages = trim_history(messages)
                round_count += 1
                continue

            workflow_route = _pending_route or "cad"
            workflow_input = _confirmed_params_to_workflow_input(
                _pending_params, workflow_route, _pending_request
            )
            print(f"\n  🔧 开始执行 {workflow_route} 工作流...")
            try:
                from modules.workflow_orchestrator import run_workflow
                text, _ = run_workflow(workflow_input)
                print(text)
                assistant_record = text
            except Exception as e:
                assistant_record = f"工作流执行失败: {e}"
                print(f"  ❌ {assistant_record}")

            print("-" * 45)
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": assistant_record})
            _pending_params = None
            _pending_route = None
            _pending_request = None
            messages = trim_history(messages)
            round_count += 1
            continue

        # ── 命令处理 ──────────────────────────────────
        if is_slash_command(user_input):
            parts = user_input.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            # /help
            if cmd == "/help":
                print_help()
                continue

            # /memory
            if cmd == "/memory":
                show_memory_status()
                continue

            # /reload
            if cmd == "/reload":
                system_prompt = build_system_prompt()
                messages[0] = {"role": "system", "content": system_prompt}
                print("  ✅ 已重新加载 system prompt 和长期记忆")
                continue

            # /autolearn on|off|status
            if cmd == "/autolearn":
                settings = load_auto_settings()
                if arg == "on":
                    settings["auto_learn"] = "on"
                    save_auto_settings(settings)
                    print("  ✅ 自动学习已开启。退出时 high-confidence 候选将自动写入正式记忆。")
                elif arg == "off":
                    settings["auto_learn"] = "off"
                    save_auto_settings(settings)
                    print("  ✅ 自动学习已关闭。退出时仅生成候选记忆，不自动写入。")
                elif arg == "status":
                    print(f"  自动学习: {settings.get('auto_learn', 'off')}")
                    print(f"  自动写入阈值: >= {settings.get('auto_write_confidence', 'high')}")
                else:
                    print("  ⚠️  用法：/autolearn on | /autolearn off | /autolearn status")
                continue

            # /candidates
            if cmd == "/candidates":
                show_candidates()
                continue

            # /acceptmem
            if cmd == "/acceptmem":
                accept_candidates()
                system_prompt = build_system_prompt()
                messages[0] = {"role": "system", "content": system_prompt}
                continue

            # /rejectmem
            if cmd == "/rejectmem":
                reject_candidates()
                continue

            # /forget
            if cmd == "/forget":
                forget_keyword(arg)
                continue

            # /docs — 列出已入库文档
            if cmd == "/docs":
                show_docs()
                continue

            # /kbtopics — 查看知识库主题和安全标签统计
            if cmd == "/kbtopics":
                show_kb_topics()
                continue

            # /searchdocs — 关键词检索（不调用 API）
            if cmd == "/searchdocs":
                if not arg:
                    print("  ⚠️  用法：/searchdocs 关键词")
                    print("       示例：/searchdocs 机翼 升阻比 翼型")
                    continue
                results = doc_search(arg, top_k=8)
                print(format_doc_results(results, arg))
                # 不调用 API，不记录到对话
                continue

            # /askdocs — 检索后由 DeepSeek 回答（调用 API）
            if cmd == "/askdocs":
                if not arg:
                    print("  ⚠️  用法：/askdocs 问题")
                    print("       示例：/askdocs 战术导弹气动布局有哪些主要构型")
                    continue

                askdocs_route = route_user_input(arg)
                if askdocs_route.get("route") == "blocked":
                    print(f"\n  ⛔ {askdocs_route.get('reason', '安全过滤已阻止此请求。')}")
                    print("     /askdocs 仅用于公开资料检索、高层解释和证据追溯，不能用于敏感武器实现、详细结构设计或效能优化。")
                    print("-" * 45)
                    continue

                # Step 1: 检索相关片段（取 Top 8，保证覆盖面）
                print("  📚 正在检索文献…", end="", flush=True)
                results = doc_search(arg, top_k=8)
                print(f"\r{' ' * 20}\r", end="")

                if not results:
                    print("  📭 当前知识库中未找到任何匹配片段。")
                    print("     请尝试：")
                    print("     1. 使用更简短的关键词")
                    print("     2. 运行 python scripts/ingest_documents.py 确认文献已入库")
                    print("     3. 输入 /docs 查看已入库文献")
                    continue

                # Step 2: 构建上下文
                context_parts: list[str] = []
                for i, r in enumerate(results, 1):
                    src = r.get("file_name", "?")
                    text = r.get("text", "")
                    topic = r.get("topic_label", "")
                    layer = r.get("knowledge_layer", "")
                    reliability = r.get("source_reliability", "unreviewed")
                    safety = r.get("safety_class", "general_reference")
                    source = r.get("source_file", "")
                    meta = f"topic={topic}; layer={layer}; reliability={reliability}; safety={safety}; source={source}"
                    context_parts.append(f"[文献{i}] {src}\n[metadata] {meta}\n{text}")

                context = "\n\n---\n\n".join(context_parts)

                askdocs_system = (
                    "你是战术导弹总体设计领域的专业分析助手。\n\n"
                    "以下是知识库中检索到的相关文献片段，请基于这些片段回答用户的问题。\n\n"
                    "## 回答要求\n\n"
                    "请将回答分为三个层次，并明确标注：\n\n"
                    "### 📖 文献依据\n"
                    "从文献片段中可直接找到的内容，引用时标注 [文献N]。\n\n"
                    "### 🔬 推理分析\n"
                    "基于文献依据，结合专业知识进行的逻辑推理和补充说明。\n\n"
                    "### 🛠️ 工程假设\n"
                    "文献片段未覆盖、但工程实践中通常需要考虑的方面（如有）。\n\n"
                    "注意：\n"
                    "1. 如果文献片段覆盖了问题的核心，文献依据应占主要篇幅；\n"
                    "2. 如果文献片段仅部分相关，请在推理分析中补充，并明确说明哪些是推理；\n"
                    "3. 如果文献片段与问题关联较弱，请在开头说明「当前知识库中关于此问题的文献依据有限」；\n"
                    "4. 不要编造文献中不存在的数据或结论；\n"
                    "5. 注意每条文献的 metadata：unreviewed 或 restricted_reference 只能作为公开资料线索和高层参考，不能当作制造级设计依据；\n"
                    "6. 保持专业、准确、工程化的表达风格。\n\n"
                    "## 文献片段\n\n"
                    f"{context}"
                )

                print(f"  📚 已检索到 {len(results)} 条相关文献片段，正在请 DeepSeek 回答…")

                # Step 3: 调用 DeepSeek
                askdocs_messages = [
                    {"role": "system", "content": askdocs_system},
                    {"role": "user", "content": arg},
                ]
                reply = call_api(askdocs_messages, temperature=0.3)

                print(f"\n  ── /askdocs 回答 ──\n")
                print(reply)
                print(f"\n  ── 依据来源 ──")
                for i, r in enumerate(results, 1):
                    fname = r.get("file_name", "?")
                    page = r.get("page", -1)
                    score = r.get("score", 0)
                    page_info = f"Page {page}" if page > 0 else f"Chunk #{r.get('chunk_index', '?')}"
                    print(f"  [文献{i}] {fname}  {page_info}  (相关度: {score:.1f})")
                print("-" * 45)

                # 保存到会话
                messages.append({"role": "user", "content": f"/askdocs {arg}"})
                messages.append({"role": "assistant", "content": reply})
                messages = trim_history(messages)
                round_count += 1
                continue

            # /design_task — 工程设计任务解析
            if cmd == "/design_task":
                if not arg:
                    print("  ⚠️  用法：/design_task 设计需求描述")
                    print("       示例：/design_task 设计一个低速无人机机翼，翼展不超过1.2m，")
                    print("              巡航速度20m/s，目标是升阻比较高")
                    continue

                print("  🔧 正在解析设计任务…")
                result = run_design_task(arg)
                print(result)
                messages.append({"role": "user", "content": f"/design_task {arg}"})
                messages.append({"role": "assistant", "content": result})
                messages = trim_history(messages)
                round_count += 1
                continue

            # /vision — 千问视觉模型识图
            if cmd == "/vision":
                image_path, prompt = _parse_vision_args(arg)
                if not image_path:
                    print("  ⚠️  用法：/vision image=<path> prompt=<text>")
                    print("         /vision <图片路径> <提示词>")
                    continue
                if not Path(image_path).exists():
                    print(f"  ❌ 图片文件不存在: {image_path}")
                    continue
                print("  🔍 正在分析图片...", end="", flush=True)
                vision_result = analyze_image(image_path, prompt)
                print(f"\r{' ' * 20}\r", end="")
                print(f"\n  📷 识图结果:\n")
                print(vision_result)
                print("-" * 45)
                # 将识图结果保存到会话（不保存 base64）
                session_user_msg = f"/vision image={image_path}"
                if prompt:
                    session_user_msg += f" prompt={prompt}"
                messages.append({"role": "user", "content": session_user_msg})
                messages.append({"role": "assistant", "content": vision_result})
                messages = trim_history(messages)
                round_count += 1
                continue

            # 手动记忆命令
            if cmd in MANUAL_COMMANDS:
                if not arg:
                    print(f"  ⚠️  请提供内容，例如：{cmd} 我喜欢用表格对比方案")
                    continue
                if not memory_safe_check(arg):
                    print("  ⛔ 疑似包含 API Key 或密码等敏感信息，拒绝写入")
                    continue
                key = MANUAL_COMMANDS[cmd]
                if append_to_memory(key, arg):
                    label = MEMORY_LABELS.get(key, key)
                    print(f"  ✅ 已存入「{label}」")
                    system_prompt = build_system_prompt()
                    messages[0] = {"role": "system", "content": system_prompt}
                else:
                    print(f"  ℹ️  内容与已有记忆高度相似，跳过写入")
                continue

            print(f"  ⚠️  未知命令：{cmd}（输入 /help 查看命令列表）")
            continue

        # ── 自然语言图片识别 ──────────────────────────
        img_path, img_prompt, auto_call = detect_image_request(user_input)

        if img_path and auto_call:
            # 解析绝对/相对路径
            img_full_path = Path(img_path)
            if not img_full_path.is_absolute():
                img_full_path = Path.cwd() / img_path
            if not img_full_path.exists():
                print(f"  ❌ 图片文件不存在: {img_path}")
                continue

            print("  🔍 正在分析图片...", end="", flush=True)
            vision_result = analyze_image(str(img_full_path), img_prompt)
            print(f"\r{' ' * 20}\r", end="")
            print(f"\n  📷 识图结果:\n")
            print(vision_result)
            print("-" * 45)
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": vision_result})
            messages = trim_history(messages)
            round_count += 1
            continue

        if img_path and not auto_call:
            print(f'  💡 检测到图片路径，如需分析图片，请输入「请分析 {img_path}」')
            continue

        # ── 自动路由 ──────────────────────────────────
        router = route_user_input(user_input)
        route = router.get("route", "chat")

        if route == "blocked":
            print(f"\n  ⛔ {router.get('reason', '安全过滤已阻止此请求。')}")
            print("-" * 45)
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant",
                             "content": f"[系统自动拦截] {router.get('reason', '')}"})
            messages = trim_history(messages)
            round_count += 1
            continue

        if route == "need_more_info":
            missing = router.get("missing_params", [])
            print(f"\n  💡 {router.get('reason', '参数不足，请补充。')}")
            if missing:
                print(f"     缺失: {', '.join(missing[:8])}")
            print("-" * 45)
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant",
                             "content": f"[参数不足] {router.get('reason', '')} 缺失: {missing}"})
            messages = trim_history(messages)
            round_count += 1
            continue

        if route == "cad" or route == "cad_fea":
            # ── 安全过滤 ──
            if not is_safe_for_synthesis(user_input):
                print(f"\n  ⛔ 请求涉及敏感内容，已阻止自动执行。")
                print("-" * 45)
                messages.append({"role": "user", "content": user_input})
                messages = trim_history(messages)
                round_count += 1
                continue

            _run_design_confirmation_flow(user_input, route)
            print("-" * 45)
            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": "[已生成设计参数确认表，等待用户确认执行]"})
            messages = trim_history(messages)
            round_count += 1
            continue

        if route == "rag":
            # 自动知识库检索 + DeepSeek
            results = doc_search(user_input, top_k=6)
            if results:
                context_parts = []
                for i, r in enumerate(results, 1):
                    src = r.get("file_name", "?")
                    text = r.get("text", "")
                    topic = r.get("topic_label", "")
                    layer = r.get("knowledge_layer", "")
                    reliability = r.get("source_reliability", "unreviewed")
                    safety = r.get("safety_class", "general_reference")
                    source = r.get("source_file", "")
                    meta = f"topic={topic}; layer={layer}; reliability={reliability}; safety={safety}; source={source}"
                    context_parts.append(f"[文献{i}] {src}\n[metadata] {meta}\n{text}")
                context = "\n\n---\n\n".join(context_parts)

                rag_system = (
                    "你是战术导弹总体设计领域的专业分析助手。\n\n"
                    "以下是知识库中检索到的相关文献片段。请基于片段回答用户问题，"
                    "标注文献来源 [文献N]。\n"
                    "如果知识库信息不足以完整回答，请说明并补充你的专业知识。\n"
                    "注意 metadata：unreviewed 或 restricted_reference 只能作为公开资料线索和高层参考，"
                    "不能当作制造级设计依据。\n\n"
                    f"## 文献片段\n\n{context}"
                )
                rag_messages = [
                    {"role": "system", "content": rag_system},
                    {"role": "user", "content": user_input},
                ]
                print("  📚 自动检索知识库...", end="", flush=True)
                reply = call_api(rag_messages, temperature=0.3)
                print(f"\r{' ' * 20}\r", end="")
            else:
                # 无知识库结果，回退普通聊天
                messages.append({"role": "user", "content": user_input})
                messages = trim_history(messages)
                print("  ⏳ 思考中...", end="", flush=True)
                reply = call_api(messages)
                print(f"\r{' ' * 20}\r", end="")

            messages.append({"role": "user", "content": user_input})
            messages.append({"role": "assistant", "content": reply})
            messages = trim_history(messages)
            round_count += 1
            print(f"[{round_count}] 🤖")
            print(reply)
            print("-" * 45)
            continue

        # ── 正常对话 ──────────────────────────────────
        messages.append({"role": "user", "content": user_input})
        messages = trim_history(messages)

        print("  ⏳ 思考中...", end="", flush=True)
        reply = call_api(messages)
        print(f"\r{' ' * 20}\r", end="")

        messages.append({"role": "assistant", "content": reply})
        round_count += 1
        print(f"[{round_count}] 🤖")
        print(reply)
        print("-" * 45)

    # ── 保存 ─────────────────────────────────────────
    if round_count > 0:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session_file = SESSIONS_DIR / f"chat_{timestamp}.md"
        save_session(messages, session_file)
        save_session_summary(messages)
        print(f"\n📝 会话已保存: {session_file}")
        print(f"   会话摘要: knowledge_base/memory/session_summaries/")
        print(f"   共 {round_count} 轮对话")
    else:
        print("\n(无对话内容，未保存会话)")


if __name__ == "__main__":
    main()
