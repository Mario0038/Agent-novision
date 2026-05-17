#!/usr/bin/env python3
"""Offline search over knowledge_base/index/chunks.jsonl.

No API is called. The search combines keyword matching, small synonym expansion,
and topic metadata boosts produced by scripts/refine_kb_metadata.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = ROOT / "knowledge_base" / "index"

TOPIC_QUERY_TERMS: dict[str, list[str]] = {
    "structural_dynamics": ["结构动力学", "振动", "模态", "固有频率", "冲击", "颤振", "气动弹性", "flutter", "modal"],
    "finite_element_simulation": ["有限元", "仿真", "网格", "应力", "应变", "ansys", "nastran", "fea", "fem", "可信度"],
    "composites_materials": ["复合材料", "复材", "材料", "铺层", "层合板", "碳纤维", "制造工艺", "composite"],
    "thermal_structures": ["热结构", "热防护", "热力耦合", "热应力", "传热", "温度场", "thermal"],
    "reliability_quality": ["可靠性", "质量", "问题归零", "疲劳", "断裂", "损伤容限", "试验验证", "鉴定"],
    "systems_engineering": ["系统工程", "需求", "指标分解", "技术管理", "流程", "评审", "风险"],
    "public_product_data": ["公开产品", "公开资料", "产品资料", "型号", "外形", "部位安排", "舱段", "检索报告"],
    "aerospace_structures": ["飞行器结构", "薄壁结构", "机翼", "翼梁", "翼肋", "蒙皮", "壁板"],
}

SYNONYM_MAP: dict[str, list[str]] = {
    "结构动力学": ["振动", "模态", "固有频率", "振型", "冲击"],
    "有限元": ["FEA", "FEM", "CAE", "仿真", "网格", "单元"],
    "复合材料": ["复材", "层合板", "铺层", "碳纤维", "composite"],
    "热结构": ["热防护", "热力耦合", "热应力", "传热"],
    "可靠性": ["质量", "问题归零", "失效", "寿命", "试验验证"],
    "系统工程": ["需求", "指标分解", "技术管理", "流程", "风险"],
    "公开产品资料": ["公开资料", "产品资料", "检索报告", "外形", "舱段"],
    "薄壁结构": ["飞行器结构", "机翼", "翼梁", "翼肋", "蒙皮", "壁板"],
}

STOP_WORDS = {"请", "帮我", "分析", "说明", "一下", "基于", "根据", "知识库", "资料", "文献", "如何", "哪些", "什么"}
TOKEN_RE = re.compile(r"[A-Za-z0-9_+\-./]+|[\u4e00-\u9fff]+")


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def load_chunks() -> list[dict]:
    return _load_jsonl(INDEX_DIR / "chunks.jsonl")


def load_manifest() -> list[dict]:
    path = INDEX_DIR / "docs_manifest.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    return data.get("docs", []) or data.get("documents", [])


def detect_query_topics(query: str) -> list[str]:
    lower = query.lower()
    topics = []
    for topic, terms in TOPIC_QUERY_TERMS.items():
        if any(term.lower() in lower for term in terms):
            topics.append(topic)
    return topics


def _ngrams(text: str) -> list[str]:
    grams: list[str] = []
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        run = run[:80]
        for n in (2, 3, 4):
            for i in range(max(len(run) - n + 1, 0)):
                grams.append(run[i:i + n])
    return grams


def generate_keywords(query: str, debug: bool = False) -> list[tuple[str, float]]:
    seen: set[str] = set()
    keywords: list[tuple[str, float]] = []

    def add(term: str, weight: float) -> None:
        term = term.strip().lower()
        if len(term) < 2 or term in STOP_WORDS or term in seen:
            return
        seen.add(term)
        keywords.append((term, weight))

    for token in TOKEN_RE.findall(query):
        add(token, 3.0)
        for gram in _ngrams(token):
            add(gram, 0.7 if len(gram) == 2 else 1.0)

    for canonical, synonyms in SYNONYM_MAP.items():
        terms = [canonical] + synonyms
        if any(t.lower() in seen or t in query for t in terms):
            for term in terms:
                add(term, 2.0)

    if debug:
        print("[debug] keywords:", ", ".join(f"{k}:{w:.1f}" for k, w in keywords[:50]))
        print("[debug] topics:", ", ".join(detect_query_topics(query)) or "(none)")
    return keywords


def _score_text(text: str, file_name: str, keywords: list[tuple[str, float]]) -> float:
    lower_text = text.lower()
    lower_name = file_name.lower()
    score = 0.0
    for kw, weight in keywords:
        count = lower_text.count(kw)
        if count:
            score += weight * (1.0 + min(count, 10) * 0.2)
        if kw in lower_name:
            score += weight * 0.8
    return score


def _metadata_boost(chunk: dict, doc: dict, query_topics: list[str]) -> float:
    if not query_topics:
        return 0.0
    topic_primary = chunk.get("topic_primary") or doc.get("topic_primary")
    topic_tags = set(chunk.get("topic_tags") or doc.get("topic_tags") or [])
    boost = 0.0
    for topic in query_topics:
        if topic == topic_primary:
            boost += 8.0
        elif topic in topic_tags:
            boost += 4.0
    return boost


def search(query: str, top_k: int = 5, debug: bool = False) -> list[dict]:
    chunks = load_chunks()
    if not chunks:
        return []
    manifest = {d.get("doc_id", ""): d for d in load_manifest()}
    keywords = generate_keywords(query, debug=debug)
    query_topics = detect_query_topics(query)
    if not keywords and not query_topics:
        return []

    scored: list[tuple[float, dict]] = []
    for chunk in chunks:
        doc = manifest.get(chunk.get("doc_id", ""), {})
        score = _score_text(chunk.get("text", ""), doc.get("file_name", ""), keywords)
        score += _metadata_boost(chunk, doc, query_topics)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    results: list[dict] = []
    per_doc: dict[str, int] = {}
    seen: set[str] = set()

    for score, chunk in scored:
        chunk_id = chunk.get("chunk_id", "")
        doc_id = chunk.get("doc_id", "")
        if chunk_id in seen or per_doc.get(doc_id, 0) >= 3:
            continue
        doc = manifest.get(doc_id, {})
        result = {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "source_file": chunk.get("source_file", ""),
            "processed_file": chunk.get("processed_file", ""),
            "file_name": doc.get("file_name", chunk.get("source_file", "").split("/")[-1]),
            "file_type": doc.get("file_type", ""),
            "page": chunk.get("page", -1),
            "chunk_index": chunk.get("chunk_index", 0),
            "text": chunk.get("text", ""),
            "char_count": chunk.get("char_count", 0),
            "score": round(score, 2),
            "source_reliability": chunk.get("source_reliability", doc.get("source_reliability", "unreviewed")),
            "safety_class": chunk.get("safety_class", doc.get("safety_class", "general_reference")),
            "topic_primary": chunk.get("topic_primary", doc.get("topic_primary", "")),
            "topic_label": chunk.get("topic_label", doc.get("topic_label", "")),
            "topic_tags": chunk.get("topic_tags", doc.get("topic_tags", [])),
            "knowledge_layer": chunk.get("knowledge_layer", doc.get("knowledge_layer", "")),
            "not_applicable_task": chunk.get("not_applicable_task", doc.get("not_applicable_task", [])),
        }
        results.append(result)
        seen.add(chunk_id)
        per_doc[doc_id] = per_doc.get(doc_id, 0) + 1
        if len(results) >= top_k:
            break

    if debug:
        print(f"[debug] hits: {len(scored)}, returned: {len(results)}")
    return results


def format_results(results: list[dict], query: str = "") -> str:
    if not results:
        return (
            "[!] 当前知识库中没有找到相关内容。\n\n"
            "建议：\n"
            "1. 使用更短的关键词。\n"
            "2. 运行 python scripts/ingest_documents.py 更新索引。\n"
            "3. 使用 /docs 查看已入库文档。"
        )

    lines = [f"[search] {query}", f"共找到 {len(results)} 条相关片段。\n"]
    for i, r in enumerate(results, 1):
        preview = r.get("text", "")[:420]
        if len(r.get("text", "")) > 420:
            preview += "..."
        lines.append(f"--- [{i}] {r.get('file_name', '?')} ({r.get('file_type', '?').upper()}) score={r.get('score', 0):.1f}")
        lines.append(f"topic: {r.get('topic_label', '')} | layer: {r.get('knowledge_layer', '')}")
        lines.append(f"source: {r.get('source_file', '')}")
        lines.append(f"processed: {r.get('processed_file', '')}")
        lines.append(f"reliability: {r.get('source_reliability', 'unreviewed')} | safety: {r.get('safety_class', 'general_reference')}")
        lines.append(preview)
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    debug = False
    if "--debug" in args:
        debug = True
        args.remove("--debug")
    q = " ".join(args) if args else "结构设计"
    print(format_results(search(q, top_k=5, debug=debug), q))
