# raw text

本目录存放原始 TXT、Markdown 和从压缩包中提取的文本类资料。

说明：

- 这里可能包含外部开源项目或资料包自带的 README、代码说明和配置文本。
- 入库脚本会读取支持的 `.txt` 和 `.md` 文件。
- 不要手动改写外部资料自带文本，避免污染来源。

新增或整理资料后运行：

```bash
python scripts/ingest_documents.py
python scripts/refine_kb_metadata.py
```
