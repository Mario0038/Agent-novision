#!/usr/bin/env python3
"""Organize external ZIP source packages into the project knowledge base.

The script keeps the original ZIP packages as evidence files under
knowledge_base/raw_docs/archives/ and extracts agent-readable source files into:

- raw_docs/pdf/
- raw_docs/word/
- raw_docs/text/
- raw_docs/spreadsheets/
- raw_docs/images/
- raw_docs/other/

It also writes:
- knowledge_base/index/archive_manifest.json
- knowledge_base/index/source_metadata.jsonl

No API is called. ZIP contents are validated against path traversal, and only
selected file types are extracted for indexing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "knowledge_base"
RAW = KB / "raw_docs"
INDEX = KB / "index"

ARCHIVES = RAW / "archives"
PDF_DIR = RAW / "pdf"
WORD_DIR = RAW / "word"
TEXT_DIR = RAW / "text"
SPREADSHEET_DIR = RAW / "spreadsheets"
IMAGE_DIR = RAW / "images"
OTHER_DIR = RAW / "other"

TEXT_TYPES = {".txt", ".md"}
WORD_TYPES = {".docx"}
PDF_TYPES = {".pdf"}
SPREADSHEET_TYPES = {".xlsx", ".xls", ".csv"}
IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
NESTED_ARCHIVE_TYPES = {".zip"}

MAX_NESTED_DEPTH = 2
MAX_SINGLE_FILE_MB = 800


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def default_source_dir() -> Path:
    parent = ROOT.parent
    for child in parent.iterdir():
        if child.is_dir() and child.name == "\u8d44\u6599":
            return child
    return parent / "\u8d44\u6599"


def ensure_dirs() -> None:
    for d in (ARCHIVES, PDF_DIR, WORD_DIR, TEXT_DIR, SPREADSHEET_DIR, IMAGE_DIR, OTHER_DIR, INDEX):
        d.mkdir(parents=True, exist_ok=True)


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")


def safe_name(name: str, fallback: str = "file") -> str:
    keep = []
    for ch in name:
        if ch.isalnum() or ch in "._-（）()[]【】":
            keep.append(ch)
        elif "\u4e00" <= ch <= "\u9fff":
            keep.append(ch)
        else:
            keep.append("_")
    cleaned = "".join(keep).strip("._ ")
    return cleaned or fallback


def digest_text(text: str, size: int = 10) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()[:size]


def classify_source(archive_name: str, entry_name: str) -> dict:
    text = f"{archive_name} {entry_name}".lower()
    sensitive_terms = ["导弹", "火箭", "战斗部", "制导", "发射", "部位安排", "成品结构模型"]
    if any(term.lower() in text for term in sensitive_terms):
        return {
            "source_reliability": "unreviewed_public_source",
            "safety_class": "restricted_reference",
            "applicable_task": ["catalog", "search", "high_level_reference", "evidence_trace"],
            "not_applicable_task": [
                "detailed_weapon_design",
                "manufacturing",
                "internal_layout_reconstruction",
                "weapon_effectiveness_optimization",
                "deployment_or_launch_system_design",
            ],
        }
    return {
        "source_reliability": "unreviewed_public_source",
        "safety_class": "engineering_reference",
        "applicable_task": ["catalog", "search", "high_level_reference", "evidence_trace"],
        "not_applicable_task": ["unverified_design_authority"],
    }


def target_dir_for_suffix(suffix: str) -> Path | None:
    suffix = suffix.lower()
    if suffix in PDF_TYPES:
        return PDF_DIR
    if suffix in WORD_TYPES:
        return WORD_DIR
    if suffix in TEXT_TYPES:
        return TEXT_DIR
    if suffix in SPREADSHEET_TYPES:
        return SPREADSHEET_DIR
    if suffix in IMAGE_TYPES:
        return IMAGE_DIR
    return None


def link_or_copy_archive(src: Path, mode: str) -> Path:
    target = ARCHIVES / src.name
    if target.exists() and target.stat().st_size == src.stat().st_size:
        return target
    if target.exists():
        target = ARCHIVES / f"{src.stem}_{digest_text(str(src))}{src.suffix}"
    if mode == "none":
        return src
    if mode == "hardlink":
        try:
            os.link(src, target)
            return target
        except OSError:
            pass
    shutil.copy2(src, target)
    return target


def is_safe_zip_member(name: str) -> bool:
    normalized = name.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        return False
    if ":" in Path(normalized).parts[0]:
        return False
    return True


def unique_target(base_dir: Path, archive_name: str, entry_name: str, file_size: int) -> Path:
    entry_path = Path(entry_name.replace("\\", "/"))
    suffix = entry_path.suffix
    stem = safe_name(entry_path.stem, "source")
    archive_stem = safe_name(Path(archive_name).stem, "archive")
    h = digest_text(f"{archive_name}|{entry_name}|{file_size}", 12)
    return base_dir / archive_stem / f"{stem}_{h}{suffix}"


def write_bytes_if_needed(target: Path, data: bytes) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size == len(data):
        return False
    target.write_bytes(data)
    return True


def extract_from_zip_bytes(
    zip_bytes: bytes,
    archive_label: str,
    source_archive: str,
    depth: int,
    records: list[dict],
    archive_stats: dict,
) -> None:
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            archive_stats["entries"] += 1
            entry_name = info.filename
            suffix = Path(entry_name).suffix.lower()
            if not is_safe_zip_member(entry_name):
                archive_stats["skipped_unsafe"] += 1
                continue
            if info.file_size > MAX_SINGLE_FILE_MB * 1024 * 1024:
                archive_stats["skipped_large"] += 1
                continue

            if suffix in NESTED_ARCHIVE_TYPES and depth < MAX_NESTED_DEPTH:
                archive_stats["nested_archives"] += 1
                try:
                    nested = zf.read(info)
                    nested_label = f"{archive_label}::{entry_name}"
                    extract_from_zip_bytes(nested, nested_label, source_archive, depth + 1, records, archive_stats)
                except Exception as exc:
                    archive_stats["errors"].append({"entry": entry_name, "error": str(exc)})
                continue

            out_dir = target_dir_for_suffix(suffix)
            if out_dir is None:
                archive_stats["skipped_unsupported"] += 1
                continue

            try:
                data = zf.read(info)
            except Exception as exc:
                archive_stats["errors"].append({"entry": entry_name, "error": str(exc)})
                continue

            target = unique_target(out_dir, archive_label, entry_name, info.file_size)
            created = write_bytes_if_needed(target, data)
            meta = classify_source(source_archive, entry_name)
            record = {
                "source_file": rel(target),
                "original_archive": source_archive,
                "archive_entry": entry_name,
                "archive_label": archive_label,
                "file_name": target.name,
                "file_type": suffix.lstrip("."),
                "file_size": info.file_size,
                "extracted_at": ts(),
                "created_or_updated": created,
                **meta,
            }
            records.append(record)
            archive_stats["extracted"] += 1


def organize(source_dir: Path, archive_mode: str = "hardlink") -> dict:
    ensure_dirs()
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    archives = sorted(source_dir.glob("*.zip"), key=lambda p: p.name)
    source_records: list[dict] = []
    archive_records: list[dict] = []

    for archive in archives:
        print(f"[archive] {archive.name}")
        archived_path = link_or_copy_archive(archive, archive_mode)
        stats = {
            "archive_name": archive.name,
            "external_source": str(archive),
            "stored_archive": str(archived_path),
            "stored_archive_rel": rel(archived_path) if archived_path.is_relative_to(ROOT) else str(archived_path),
            "zip_size": archive.stat().st_size,
            "entries": 0,
            "extracted": 0,
            "nested_archives": 0,
            "skipped_unsupported": 0,
            "skipped_unsafe": 0,
            "skipped_large": 0,
            "errors": [],
        }
        try:
            data = archive.read_bytes()
            extract_from_zip_bytes(data, archive.name, archive.name, 0, source_records, stats)
        except Exception as exc:
            stats["errors"].append({"archive": archive.name, "error": str(exc)})
        archive_records.append(stats)
        print(f"          extracted={stats['extracted']} skipped={stats['skipped_unsupported']} nested={stats['nested_archives']}")

    manifest = {
        "generated_at": ts(),
        "source_dir": str(source_dir),
        "archive_mode": archive_mode,
        "total_archives": len(archive_records),
        "total_extracted_files": len(source_records),
        "archives": archive_records,
    }
    (INDEX / "archive_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (INDEX / "source_metadata.jsonl").open("w", encoding="utf-8") as f:
        for record in source_records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Organize external ZIP packages into knowledge_base/raw_docs.")
    parser.add_argument("--source", type=Path, default=default_source_dir(), help="Directory containing ZIP packages.")
    parser.add_argument(
        "--archive-mode",
        choices=["hardlink", "copy", "none"],
        default="hardlink",
        help="How to store original ZIP evidence packages in raw_docs/archives.",
    )
    args = parser.parse_args()
    manifest = organize(args.source, args.archive_mode)
    print("\nDone")
    print(f"Archives: {manifest['total_archives']}")
    print(f"Extracted files: {manifest['total_extracted_files']}")
    print(f"Manifest: {INDEX / 'archive_manifest.json'}")
    print(f"Metadata: {INDEX / 'source_metadata.jsonl'}")


if __name__ == "__main__":
    main()
