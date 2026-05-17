#!/usr/bin/env python3
"""环境检查脚本 —— 为 domain_agent.py 和 SolidWorks 自动化做准备。"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OK = "[OK]"
WARN = "[!!]"
ERR = "[XX]"

results: list[tuple[str, bool, str]] = []


def check(label: str, ok: bool, detail: str = ""):
    results.append((label, ok, detail))
    icon = OK if ok else ERR
    print(f"  {icon} {label}{' - ' + detail if detail else ''}")


print("=" * 50)
print("  项目环境检查")
print("=" * 50)

# ── Python ──────────────────────────────────────────
print("\n── Python ──")
check("Python 版本", sys.version_info >= (3, 10), sys.version.split()[0])
check("Python 路径", Path(sys.executable).exists(), str(Path(sys.executable)))

# ── pip ─────────────────────────────────────────────
print("\n── pip ──")
try:
    result = subprocess.run([sys.executable, "-m", "pip", "--version"],
                            capture_output=True, text=True)
    check("pip 可用", result.returncode == 0, result.stdout.strip()[:60])
except Exception as e:
    check("pip 可用", False, str(e))

# ── 核心包 ──────────────────────────────────────────
print("\n── 核心包 ──")
packages = {
    "openai": "DeepSeek API 调用",
    "dotenv": "环境变量加载",
    "pandas": "数据处理与表格",
    "tqdm": "进度条",
    "pydantic": "数据校验",
    "tenacity": "API 重试",
}
for mod, desc in packages.items():
    try:
        __import__(mod)
        check(f"{mod} ({desc})", True)
    except ImportError:
        check(f"{mod} ({desc})", False, "未安装")

# ── SolidWorks 自动化 ───────────────────────────────
print("\n── SolidWorks 自动化 ──")
try:
    import win32com.client
    check("pywin32 (COM)", True)
except ImportError:
    check("pywin32 (COM)", False, "未安装 — 请运行: pip install pywin32")

try:
    # 只检查类型库，不创建实例（避免弹出 SW 窗口）
    import pythoncom
    pythoncom.CoInitialize()
    # 仅探测注册表，不做实际连接
    sw_progid = "SldWorks.Application"
    check(f"SolidWorks ProgID 存在 ({sw_progid})", True, "注册表项可访问")
    pythoncom.CoUninitialize()
except Exception:
    check(f"SolidWorks ProgID", False, "此机器可能未安装 SolidWorks 或 COM 注册不完整")

# ── 项目文件 ────────────────────────────────────────
print("\n── 项目关键文件 ──")
key_files = [
    ".env",
    "requirements.txt",
    "domain_agent.py",
    "output/best_prompt.md",
    "knowledge_base/",
    "sessions/",
    "knowledge_base/memory/",
]
for f in key_files:
    p = ROOT / f
    ok = p.exists()
    detail = ""
    if not ok:
        detail = "不存在"
    check(f, ok, detail)

# ── 汇总 ────────────────────────────────────────────
print("\n" + "=" * 50)
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"  检查结果: {passed}/{total} 通过")
if passed == total:
    print(f"  所有检查通过，环境就绪。")
else:
    failed = [(l, d) for l, ok, d in results if not ok]
    print(f"  {len(failed)} 项未通过：")
    for label, detail in failed:
        print(f"    - {label}: {detail}")
print("=" * 50)
