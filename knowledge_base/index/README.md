# index

本目录存放知识库索引和 metadata，是 `/searchdocs`、`/askdocs` 和自然语言 RAG 的主要数据源。

## 主要文件

| 文件 | 作用 |
| --- | --- |
| `archive_manifest.json` | 外部压缩包整理清单，记录压缩包来源、提取数量和处理方式。 |
| `source_metadata.jsonl` | 原始来源级 metadata，每行一个来源文件，包含主题、安全标签和来源信息。 |
| `docs_manifest.json` | 已入库文档清单，记录文档来源、类型、处理路径、主题和安全标签。 |
| `chunks.jsonl` | 检索切块索引，每行一个 JSON 对象，包含文本片段和 metadata。 |
| `topic_summary.json` | 主题分布、安全标签、知识层级等统计信息，供 `/kbtopics` 查看。 |

## 生成顺序

```bash
python scripts/organize_source_archives.py --archive-mode hardlink
python scripts/ingest_documents.py
python scripts/refine_kb_metadata.py
```

## 检索入口

```bash
python scripts/search_docs.py "复合材料 铺层"
```

Agent 内：

```text
/searchdocs 复合材料 铺层
/askdocs 复合材料铺层设计有哪些基础概念？
/kbtopics
```

## 维护规则

- 不建议手动编辑索引文件，除非调试检索系统。
- 不要把 API Key、密码或 token 写入索引。
- 如果重新整理资料或重新入库，建议随后运行 `scripts/refine_kb_metadata.py`。
- 受限来源的 `safety_class` 和 `not_applicable_task` 不应随意移除。
