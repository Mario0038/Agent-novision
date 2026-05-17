#!/usr/bin/env python3
"""
文献入库脚本 — 调用 modules/doc_ingest.py 完成文献扫描、Markdown 转换和索引生成。

运行方式：
    python scripts/ingest_documents.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.doc_ingest import ingest_all

if __name__ == "__main__":
    ingest_all()
