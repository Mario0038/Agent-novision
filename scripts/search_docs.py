#!/usr/bin/env python3
"""Command-line keyword search for the local knowledge base.

Usage:
    python scripts/search_docs.py "机翼 升阻比 翼型"
    python scripts/search_docs.py "结构动力学 振动" --debug
"""

import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.doc_search import format_results, search


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('用法: python scripts/search_docs.py "关键词" [--debug]')
        print('示例: python scripts/search_docs.py "气动布局 升阻比"')
        print('      python scripts/search_docs.py "结构动力学 振动" --debug')
        sys.exit(0)

    args = sys.argv[1:]
    debug = False
    if "--debug" in args:
        debug = True
        args.remove("--debug")

    query = " ".join(args)
    results = search(query, top_k=5, debug=debug)
    print(format_results(results, query))
