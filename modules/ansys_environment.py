#!/usr/bin/env python3
"""
ANSYS 环境检测与配置模块
=========================
自动检测 D:/ANSYS, E:/ANSYS 等常见安装路径中的可执行程序，
过滤 licensing 辅助工具，识别真实 MAPDL/Workbench/Mechanical/Fluent。

生成标准化配置文件 config/ansys_config.json。
不启动 ANSYS 求解器。
"""

import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
CONFIG_PATH = CONFIG_DIR / "ansys_config.json"

# ═══════════════════════════════════════════════════════════
# 搜索配置
# ═══════════════════════════════════════════════════════════

# 高优先级搜索根目录
_SEARCH_ROOTS = [
    "D:/ANSYS",
    "E:/ANSYS",
    "D:/ANSYS Inc",
    "E:/ANSYS Inc",
    "C:/Program Files/ANSYS Inc",
    "C:/Program Files/ANSYS",
    "E:/BIT/Ansys",
]

# 版本子目录正则
_VERSION_RE = re.compile(r"^v\d{2,3}$", re.IGNORECASE)

# 精确可执行文件名（不含扩展名）
_EXE_TARGETS = {
    "mapdl": ["ansys241.exe", "ansys242.exe", "ansys251.exe", "ansys252.exe",
              "ansys.exe", "ANSYS241.exe", "ANSYS242.exe"],
    "workbench": ["RunWB2.exe", "runwb2.exe", "ansyswbu.exe"],
    "mechanical": ["AnsysWBU.exe", "Mechanical.exe"],
    "fluent": ["fluent.exe", "Fluent.exe"],
}

# 必须排除的路径关键词（不是求解器）
_LICENSE_KW = ["licensing", "license", "licclient", "Shared Files",
               "Licensing", "License", "LicClient"]


def _is_license_tool(path_str: str) -> bool:
    return any(kw.lower() in path_str.lower() for kw in _LICENSE_KW)


def _extract_version(path_str: str) -> str | None:
    """从路径中提取版本号，如 v241, v242, v251。"""
    m = re.search(r"(v\d{3})", path_str, re.IGNORECASE)
    return m.group(1).lower() if m else None


# ═══════════════════════════════════════════════════════════
# 主检测函数
# ═══════════════════════════════════════════════════════════

def detect_ansys_installation() -> dict:
    """检测本机 ANSYS 安装。

    Returns:
        dict with keys: ansys_found, ansys_root, detected_versions,
        selected_version, mapdl_path, workbench_path, mechanical_path,
        fluent_path, license_tool_path, pyansys_available, preferred_backend, ...
    """
    result: dict = {
        "detected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ansys_found": False,
        "ansys_root": None,
        "detected_versions": [],
        "selected_version": None,
        "mapdl_path": None,
        "workbench_path": None,
        "mechanical_path": None,
        "fluent_path": None,
        "license_tool_path": None,
        "pyansys_available": False,
        "pyansys_packages": [],
        "preferred_backend": "none",
        "warnings": [],
        "config_written": False,
    }

    print("检测 ANSYS 安装...")

    # ── 1. 收集所有候选根目录 ──
    candidates: list[Path] = []
    for root_str in _SEARCH_ROOTS:
        p = Path(root_str)
        if p.exists():
            candidates.append(p)

    # 同时搜索版本子目录
    all_scan_roots: list[Path] = []
    for c in candidates:
        all_scan_roots.append(c)
        for sub in sorted(c.iterdir()) if c.is_dir() else []:
            if sub.is_dir() and _VERSION_RE.match(sub.name):
                all_scan_roots.append(sub)

    if not all_scan_roots:
        result["warnings"].append("未找到任何 ANSYS 相关目录")
        _check_pyansys(result)
        _write_config(result)
        _print_status(result)
        return result

    # ── 2. 搜索可执行文件 ──
    found: dict[str, list[tuple[str, str, str]]] = {
        "mapdl": [], "workbench": [], "mechanical": [], "fluent": [],
    }
    license_hits: list[str] = []

    for scan_root in all_scan_roots:
        if not scan_root.is_dir():
            continue
        for root, dirs, files in _walk(scan_root, depth=6):
            for fname in files:
                for category, targets in _EXE_TARGETS.items():
                    if fname in targets or fname.lower() in [t.lower() for t in targets]:
                        full = str(Path(root) / fname)
                        ver = _extract_version(full) or _extract_version(str(scan_root))
                        if _is_license_tool(full):
                            if full not in license_hits:
                                license_hits.append(full)
                        else:
                            found[category].append((full, ver or "?"))

    # 去重
    for cat in found:
        seen = set()
        unique = []
        for path, ver in found[cat]:
            if path not in seen:
                seen.add(path)
                unique.append((path, ver))
        found[cat] = unique

    # ── 3. 填充结果 ──
    # 按版本排序，优先选最新的
    all_versions: list[str] = []
    for cat_entries in found.values():
        for _, ver in cat_entries:
            if ver not in all_versions and ver != "?":
                all_versions.append(ver)

    all_versions.sort(reverse=True)
    result["detected_versions"] = all_versions

    if any(found[cat] for cat in found):
        result["ansys_found"] = True
        result["selected_version"] = all_versions[0] if all_versions else None

        # 选最佳 MAPDL（优先匹配版本号、优先高版本）
        if found["mapdl"]:
            # 按版本排序选第一个
            found["mapdl"].sort(key=lambda x: x[1], reverse=True)
            result["mapdl_path"] = found["mapdl"][0][0]
            if found["mapdl"][0][1] != "?":
                result["selected_version"] = found["mapdl"][0][1]

        if found["workbench"]:
            found["workbench"].sort(key=lambda x: x[1], reverse=True)
            result["workbench_path"] = found["workbench"][0][0]

        if found["mechanical"]:
            found["mechanical"].sort(key=lambda x: x[1], reverse=True)
            result["mechanical_path"] = found["mechanical"][0][0]

        if found["fluent"]:
            found["fluent"].sort(key=lambda x: x[1], reverse=True)
            result["fluent_path"] = found["fluent"][0][0]

        if license_hits:
            result["license_tool_path"] = license_hits[0]

        # 推断 ansys_root
        if result["mapdl_path"]:
            p = Path(result["mapdl_path"])
            # 往上找到 v* 目录
            for parent in p.parents:
                if _VERSION_RE.match(parent.name):
                    result["ansys_root"] = str(parent.parent)
                    if not result["selected_version"]:
                        result["selected_version"] = parent.name.lower()
                    break
            if not result["ansys_root"]:
                result["ansys_root"] = str(p.parents[2]) if len(p.parents) > 2 else str(p.parent)
        elif result["workbench_path"]:
            p = Path(result["workbench_path"])
            for parent in p.parents:
                if _VERSION_RE.match(parent.name):
                    result["ansys_root"] = str(parent.parent)
                    break
    else:
        result["ansys_found"] = False
        if license_hits:
            result["license_tool_path"] = license_hits[0]
            result["warnings"].append(
                f"仅找到 licensing 工具，非求解器 ({len(license_hits)} 个)"
            )
        else:
            result["warnings"].append(
                f"扫描了 {len(all_scan_roots)} 个目录，未找到 ANSYS 可执行程序"
            )

    # ── 4. PyMAPDL ──
    _check_pyansys(result)

    # ── 5. 首选后端 ──
    if result["pyansys_available"]:
        result["preferred_backend"] = "pymapdl"
    elif result["mapdl_path"]:
        result["preferred_backend"] = "workbench"
    elif result["workbench_path"]:
        result["preferred_backend"] = "workbench"
    else:
        result["preferred_backend"] = "none"

    # ── 6. 写配置 & 输出 ──
    _write_config(result)
    _print_status(result)

    return result


def _walk(path: Path, depth: int):
    """受控递归遍历，限制深度避免搜索过深。"""
    if depth <= 0:
        return
    try:
        entries = list(path.iterdir())
    except (PermissionError, OSError):
        return
    dirs = [e for e in entries if e.is_dir() and not e.name.startswith(".")]
    files = [e.name for e in entries if e.is_file()]
    yield str(path), [d.name for d in dirs], files
    for d in dirs[:20]:  # 每层最多搜索 20 个子目录
        yield from _walk(d, depth - 1)


def _check_pyansys(result: dict):
    packages = {
        "ansys.mapdl.core": "ansys-mapdl-core",
        "ansys.mapdl.reader": "ansys-mapdl-reader",
        "ansys.mechanical.core": "ansys-mechanical-core",
        "ansys.fluent.core": "ansys-fluent-core",
        "pyansys": "pyansys",
    }
    found: list[str] = []
    for mod, pkg in packages.items():
        try:
            __import__(mod)
            found.append(pkg)
            print(f"  Python 包: {pkg} ✅")
        except ImportError:
            pass
    result["pyansys_packages"] = found
    result["pyansys_available"] = len(found) > 0


def _write_config(result: dict):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config = {
        "generated_at": result["detected_at"],
        "ansys_found": result["ansys_found"],
        "ansys_root": result["ansys_root"],
        "detected_versions": result["detected_versions"],
        "selected_version": result["selected_version"],
        "mapdl_path": result["mapdl_path"],
        "workbench_path": result["workbench_path"],
        "mechanical_path": result["mechanical_path"],
        "fluent_path": result["fluent_path"],
        "license_tool_path": result["license_tool_path"],
        "pyansys_available": result["pyansys_available"],
        "pyansys_packages": result["pyansys_packages"],
        "preferred_backend": result["preferred_backend"],
        "warnings": result["warnings"],
        "note": (
            "此文件由 modules/ansys_environment.py 自动生成。"
            "如 ANSYS 未检测到或路径有误，请手动编辑。"
        ),
        "backend_usage": {
            "pymapdl": "静力结构分析 / 模态分析（Python API, PyMAPDL）",
            "workbench": "Workbench Mechanical（GUI 或批处理）",
            "fluent": "暂不启用，待 CFD 流程就绪后扩展",
        },
    }

    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result["config_written"] = True
    print(f"\n  配置已写入: {CONFIG_PATH}")


def _print_status(result: dict):
    print()
    print("─" * 50)
    print("  ANSYS 环境检测结果")
    print("─" * 50)

    if result["ansys_found"]:
        print(f"  ANSYS:         ✅ 已检测到")
        print(f"  根目录:        {result['ansys_root']}")
        print(f"  检测到版本:    {result['detected_versions']}")
        print(f"  选定版本:      {result['selected_version']}")
    else:
        print(f"  ANSYS:         ❌ 未检测到")
        print(f"  请手动编辑:    {CONFIG_PATH}")

    print()
    print("  可执行程序:")
    for key, label in [("mapdl", "MAPDL 求解器"), ("workbench", "Workbench"),
                       ("mechanical", "Mechanical"), ("fluent", "Fluent")]:
        path = result.get(f"{key}_path")
        icon = "✅" if path else "❌"
        print(f"    {icon} {label}: {path or '未找到'}")

    lic = result.get("license_tool_path")
    if lic:
        print(f"    ℹ️  许可证工具: {lic}")

    print()
    print("  Python 接口:")
    if result["pyansys_available"]:
        print(f"    ✅ PyMAPDL 可用 ({', '.join(result['pyansys_packages'])})")
    else:
        print(f"    ❌ PyMAPDL 未安装")

    print(f"\n  首选后端: {result['preferred_backend']}")

    # 求解条件判断
    can_solve = bool(
        result["pyansys_available"] or result["mapdl_path"]
    )
    print(f"\n  自动静力求解条件: {'✅ 具备' if can_solve else '❌ 不具备'}")
    if not can_solve:
        print(f"     - PyMAPDL: {'已安装' if result['pyansys_available'] else '未安装'}")
        print(f"     - MAPDL:   {'已检测到' if result['mapdl_path'] else '未检测到'}")

    if result["warnings"]:
        print(f"\n  ⚠️ 警告:")
        for w in result["warnings"]:
            print(f"    - {w}")

    if not result["ansys_found"] and not result["pyansys_available"]:
        print(f"\n  💡 当前只能生成 FEA 任务包，不能实际求解。")
        print(f"     安装 ANSYS 或 pip install ansys-mapdl-core 后可启用求解。")

    print("─" * 50)


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


if __name__ == "__main__":
    detect_ansys_installation()
