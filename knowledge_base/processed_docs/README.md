# processed_docs

本目录存放从 `raw_docs/` 中 PDF、DOCX、TXT、Markdown 提取或规范化得到的 Markdown 文本。

## 子目录

| 目录 | 作用 |
| --- | --- |
| `pdf/` | 从 PDF 提取的 Markdown。 |
| `word/` | 从 DOCX 提取的 Markdown。 |
| `text/` | 从 TXT/MD 规范化得到的 Markdown。 |

## 生成方式

```bash
python scripts/ingest_documents.py
```

入库后建议运行：

```bash
python scripts/refine_kb_metadata.py
```

## 维护规则

- 这些文件通常由入库脚本自动生成。
- 一般不手动编辑，必要时可人工修正提取错误。
- 检索系统读取 `index/chunks.jsonl`，而不是直接遍历本目录。
- 如果手动修正文档内容，需要重新运行入库或 metadata 细化流程。
