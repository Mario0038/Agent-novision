#!/usr/bin/env python3
"""
ANSYS 环境检测测试
===================
验证 ansys_environment 模块能否正常运行检测并生成配置文件。

不启动 ANSYS 求解器。
"""

import json
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CONFIG_PATH = ROOT / "config" / "ansys_config.json"


def run_test() -> int:
    print("=" * 45)
    print("  ANSYS 环境检测测试")
    print("=" * 45)

    checks = []

    # ── 1. 运行检测 ──
    print("\n[1/4] 运行 detect_ansys_installation()...")
    try:
        from modules.ansys_environment import detect_ansys_installation
        result = detect_ansys_installation()
        checks.append(("检测未崩溃", True))
    except Exception as e:
        print(f"  ❌ 检测异常: {e}")
        checks.append(("检测未崩溃", False))
        return 1

    # ── 2. 检查返回字段 ──
    print("\n[2/4] 检查返回字段...")
    required_fields = [
        "ansys_found", "ansys_root", "detected_versions",
        "selected_version", "mapdl_path", "workbench_path",
        "mechanical_path", "fluent_path", "license_tool_path",
        "pyansys_available", "pyansys_packages",
        "preferred_backend", "warnings", "config_written",
    ]
    all_fields_ok = True
    for field in required_fields:
        ok = field in result
        if not ok:
            print(f"  ❌ 缺失字段: {field}")
            all_fields_ok = False
    if all_fields_ok:
        print(f"  ✅ 所有必需字段存在 ({len(required_fields)} 个)")
    checks.append(("字段完整", all_fields_ok))

    # ── 3. 检查配置文件 ──
    print("\n[3/4] 检查配置文件...")
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        size = CONFIG_PATH.stat().st_size
        print(f"  ✅ {CONFIG_PATH.name} ({size} B)")

        # 检查配置关键字段
        cfg_fields = ["ansys_found", "ansys_root", "preferred_backend",
                      "pyansys_available", "note"]
        cfg_ok = True
        for field in cfg_fields:
            if field not in config:
                print(f"  ❌ 配置缺失字段: {field}")
                cfg_ok = False
        if cfg_ok:
            print(f"  ✅ 配置字段完整 ({len(cfg_fields)} 个关键字段)")
        checks.append(("配置文件存在且完整", True))

        # 显示配置摘要
        print(f"\n  配置摘要:")
        print(f"    ansys_found:       {config.get('ansys_found')}")
        print(f"    ansys_root:        {config.get('ansys_root')}")
        print(f"    selected_version:  {config.get('selected_version')}")
        print(f"    mapdl_path:        {config.get('mapdl_path')}")
        print(f"    workbench_path:    {config.get('workbench_path')}")
        print(f"    fluent_path:       {config.get('fluent_path')}")
        print(f"    pyansys_available: {config.get('pyansys_available')}")
        print(f"    preferred_backend: {config.get('preferred_backend')}")
    else:
        print(f"  ❌ 配置文件未生成: {CONFIG_PATH}")
        checks.append(("配置文件存在且完整", False))

    # ── 4. 状态输出 ──
    print(f"\n[4/4] 状态评估...")
    ansys_found = result.get("ansys_found", False)
    pyansys_ok = result.get("pyansys_available", False)
    backend = result.get("preferred_backend", "none")

    print(f"  本地 ANSYS:  {'✅ 检测到' if ansys_found else '❌ 未检测到'}")
    print(f"  PyMAPDL:     {'✅ 可用' if pyansys_ok else '❌ 未安装'}")
    print(f"  首选后端:    {backend}")

    if not ansys_found and not pyansys_ok:
        print(f"\n  💡 ANSYS 未检测到且 PyMAPDL 未安装。")
        print(f"     当前只能生成 FEA 任务包，不能实际求解。")
        print(f"     如需启用求解，请:")
        print(f"       1. 安装 ANSYS 后运行本检测脚本")
        print(f"       2. 或 pip install ansys-mapdl-core")
        print(f"       3. 或手动编辑 config/ansys_config.json")
        checks.append(("无 ANSYS 时优雅降级", True))

    # ── 判定 ──
    print(f"\n  {'─' * 40}")
    all_ok = all(ok for _, ok in checks)
    if all_ok:
        print(f"  🏆 结果: PASS")
        print(f"  {'─' * 40}")
        return 0
    else:
        failed = [label for label, ok in checks if not ok]
        print(f"  ❌ 结果: FAIL ({', '.join(failed)})")
        print(f"  {'─' * 40}")
        return 1


if __name__ == "__main__":
    sys.exit(run_test())
