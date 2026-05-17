# raw pdf

本目录存放原始 PDF 文献。

维护规则：

- 适合放文字型 PDF。
- 扫描版 PDF 当前不做 OCR，入库后可能无法提取正文。
- 不要把 PDF 放入 `memory/` 或 `domain_docs/`。
- 新增 PDF 后运行 `scripts/ingest_documents.py` 和 `scripts/refine_kb_metadata.py`。
