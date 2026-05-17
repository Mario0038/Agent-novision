#!/usr/bin/env python3
"""Refine knowledge-base metadata with topic taxonomy tags.

This updates:
- knowledge_base/index/source_metadata.jsonl
- knowledge_base/index/docs_manifest.json
- knowledge_base/index/chunks.jsonl
- knowledge_base/index/topic_summary.json

It does not re-extract documents and does not call any API.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.kb_taxonomy import classify_text, infer_knowledge_layer, is_public_product_related

INDEX = ROOT / "knowledge_base" / "index"
SOURCE_METADATA = INDEX / "source_metadata.jsonl"
DOCS_MANIFEST = INDEX / "docs_manifest.json"
CHUNKS = INDEX / "chunks.jsonl"
TOPIC_SUMMARY = INDEX / "topic_summary.json"


def load_jsonl(path: Path) -> list[dict]:
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


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def refine_record(record: dict, preview_text: str = "") -> dict:
    source = record.get("source_file", "")
    archive = record.get("original_archive", "")
    file_name = record.get("file_name", "")
    file_type = record.get("file_type", "")
    topic = classify_text(f"{file_name} {preview_text}", source, archive)
    out = dict(record)
    out.update(topic)
    out["knowledge_layer"] = infer_knowledge_layer(source, file_type)
    out["is_public_product_data"] = is_public_product_related(source, archive)
    if out["is_public_product_data"] and out.get("safety_class") != "restricted_reference":
        out["safety_class"] = "restricted_reference"
        blocked = set(out.get("not_applicable_task", []))
        blocked.update({
            "detailed_weapon_design",
            "manufacturing",
            "internal_layout_reconstruction",
            "weapon_effectiveness_optimization",
        })
        out["not_applicable_task"] = sorted(blocked)
    return out


def main() -> None:
    source_rows = [refine_record(r) for r in load_jsonl(SOURCE_METADATA)]
    source_map = {r.get("source_file", ""): r for r in source_rows}
    if source_rows:
        write_jsonl(SOURCE_METADATA, source_rows)

    manifest = json.loads(DOCS_MANIFEST.read_text(encoding="utf-8"))
    docs = manifest.get("docs", [])
    refined_docs: list[dict] = []
    for doc in docs:
        src = doc.get("source_file", "")
        base = source_map.get(src, doc)
        refined = refine_record({**doc, **{k: v for k, v in base.items() if k not in {"char_count", "processed_file"}}})
        doc.update({
            "topic_primary": refined["topic_primary"],
            "topic_label": refined["topic_label"],
            "topic_tags": refined["topic_tags"],
            "topic_scores": refined["topic_scores"],
            "knowledge_layer": refined["knowledge_layer"],
            "is_public_product_data": refined["is_public_product_data"],
            "source_reliability": refined.get("source_reliability", doc.get("source_reliability", "unreviewed")),
            "safety_class": refined.get("safety_class", doc.get("safety_class", "general_reference")),
            "applicable_task": refined.get("applicable_task", doc.get("applicable_task", [])),
            "not_applicable_task": refined.get("not_applicable_task", doc.get("not_applicable_task", [])),
        })
        refined_docs.append(doc)
    manifest["docs"] = refined_docs
    DOCS_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    doc_map = {d.get("doc_id", ""): d for d in refined_docs}
    chunks = load_jsonl(CHUNKS)
    refined_chunks: list[dict] = []
    for chunk in chunks:
        doc = doc_map.get(chunk.get("doc_id", ""), {})
        for key in (
            "topic_primary", "topic_label", "topic_tags", "topic_scores",
            "knowledge_layer", "is_public_product_data", "source_reliability",
            "safety_class", "applicable_task", "not_applicable_task",
        ):
            if key in doc:
                chunk[key] = doc[key]
        refined_chunks.append(chunk)
    write_jsonl(CHUNKS, refined_chunks)

    topic_counts = Counter(d.get("topic_primary", "unknown") for d in refined_docs)
    safety_counts = Counter(d.get("safety_class", "unknown") for d in refined_docs)
    layer_counts = Counter(d.get("knowledge_layer", "unknown") for d in refined_docs)
    by_topic_type = defaultdict(Counter)
    for d in refined_docs:
        by_topic_type[d.get("topic_primary", "unknown")][d.get("file_type", "unknown")] += 1

    summary = {
        "total_docs": len(refined_docs),
        "total_chunks": len(refined_chunks),
        "topic_counts": dict(topic_counts),
        "safety_counts": dict(safety_counts),
        "knowledge_layer_counts": dict(layer_counts),
        "topic_file_type_counts": {k: dict(v) for k, v in by_topic_type.items()},
    }
    TOPIC_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Metadata refined.")
    print(f"Documents: {len(refined_docs)}")
    print(f"Chunks: {len(refined_chunks)}")
    print("Topics:", dict(topic_counts))
    print(f"Summary: {TOPIC_SUMMARY}")


if __name__ == "__main__":
    main()
