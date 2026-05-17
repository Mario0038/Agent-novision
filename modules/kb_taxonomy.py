#!/usr/bin/env python3
"""Knowledge-base topic taxonomy and metadata classifier."""

from __future__ import annotations

from pathlib import Path


TOPIC_RULES: dict[str, dict] = {
    "structural_dynamics": {
        "label": "结构动力学",
        "keywords": [
            "结构动力学", "振动", "模态", "固有频率", "振型", "冲击", "响应谱",
            "随机振动", "颤振", "flutter", "aeroelastic", "气动弹性", "阵风",
            "dynamic", "vibration", "modal", "frequency", "mode", "shock",
        ],
    },
    "finite_element_simulation": {
        "label": "有限元与仿真",
        "keywords": [
            "有限元", "仿真", "网格", "单元", "节点", "静力", "应力", "应变",
            "位移", "屈曲", "接触", "收敛", "可信度", "验证", "确认", "V&V",
            "FEA", "FEM", "CAE", "ANSYS", "Nastran", "Abaqus", "Workbench",
            "mesh", "element", "simulation", "verification", "validation",
        ],
    },
    "composites_materials": {
        "label": "复材、材料与制造",
        "keywords": [
            "复合材料", "复材", "层合板", "铺层", "纤维", "树脂", "碳纤维",
            "玻璃纤维", "蜂窝", "夹层", "制造工艺", "成型", "固化", "材料",
            "composite", "laminate", "ply", "prepreg", "carbon fiber", "material",
        ],
    },
    "thermal_structures": {
        "label": "热结构与热防护",
        "keywords": [
            "热结构", "热防护", "热-力", "热力耦合", "热应力", "温度场",
            "传热", "烧蚀", "隔热", "thermal", "heat transfer", "thermo",
            "temperature", "TPS",
        ],
    },
    "reliability_quality": {
        "label": "可靠性、质量与问题归零",
        "keywords": [
            "可靠性", "质量", "问题归零", "故障", "失效", "寿命", "疲劳",
            "断裂", "损伤容限", "裂纹", "试验验证", "鉴定", "环境适应性",
            "reliability", "quality", "failure", "fatigue", "fracture", "damage tolerance",
        ],
    },
    "systems_engineering": {
        "label": "系统工程与技术管理",
        "keywords": [
            "系统工程", "需求", "指标分解", "技术管理", "流程", "评审", "风险",
            "构型管理", "项目管理", "权衡", "trade", "requirement", "systems engineering",
            "management", "workflow",
        ],
    },
    "public_product_data": {
        "label": "公开产品资料",
        "keywords": [
            "公开信息", "检索报告", "产品", "型号", "参数", "外形", "三视图",
            "部位安排", "舱段", "导弹", "火箭", "制导", "Javelin", "Spike",
            "product", "datasheet", "public", "missile", "rocket",
        ],
    },
    "aerospace_structures": {
        "label": "飞行器结构与薄壁结构",
        "keywords": [
            "飞行器结构", "薄壁结构", "机翼", "翼梁", "翼肋", "蒙皮", "壁板",
            "加筋", "梁", "板壳", "aircraft structure", "wing", "skin", "spar", "rib",
        ],
    },
}


def classify_text(text: str, source_file: str = "", archive: str = "") -> dict:
    haystack = f"{text} {source_file} {archive}".lower()
    scores: dict[str, int] = {}
    matched: dict[str, list[str]] = {}
    for topic, rule in TOPIC_RULES.items():
        hits = []
        for kw in rule["keywords"]:
            if kw.lower() in haystack:
                hits.append(kw)
        if hits:
            scores[topic] = len(hits)
            matched[topic] = hits[:8]

    if not scores:
        primary = "general_engineering"
        tags = ["general_engineering"]
    else:
        primary = max(scores, key=scores.get)
        tags = [topic for topic, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]

    return {
        "topic_primary": primary,
        "topic_label": TOPIC_RULES.get(primary, {}).get("label", "通用工程资料"),
        "topic_tags": tags,
        "topic_scores": scores,
        "topic_matched_terms": matched,
    }


def infer_knowledge_layer(source_file: str, file_type: str) -> str:
    path = source_file.lower()
    suffix = f".{file_type.lower().lstrip('.')}"
    if "/archives/" in path or suffix == ".zip":
        return "raw_archive"
    if "/spreadsheets/" in path or suffix in {".xlsx", ".xls", ".csv"}:
        return "structured_table"
    if "/images/" in path or suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}:
        return "image_evidence"
    if "/domain_docs/" in path:
        return "curated_domain_note"
    if suffix in {".pdf", ".docx", ".txt", ".md"}:
        return "processed_text_source"
    return "raw_evidence"


def is_public_product_related(source_file: str, archive: str = "") -> bool:
    text = f"{source_file} {archive}"
    result = classify_text(text, source_file, archive)
    return result["topic_primary"] == "public_product_data" or "public_product_data" in result["topic_tags"]


def source_package_name(path: str) -> str:
    parts = Path(path.replace("\\", "/")).parts
    try:
        idx = parts.index("raw_docs")
        if len(parts) > idx + 2:
            return parts[idx + 2]
    except ValueError:
        pass
    return ""
