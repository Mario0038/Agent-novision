# raw word

本目录存放原始 Word 文档。

支持格式：

- `.docx`

暂不支持：

- `.doc`，建议先手动转换为 `.docx`。

新增文档后运行：

```bash
python scripts/ingest_documents.py
python scripts/refine_kb_metadata.py
```
