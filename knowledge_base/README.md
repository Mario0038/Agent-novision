# knowledge_base

本目录是项目知识库根目录，包含长期记忆、人工整理知识、原始资料、提取文本和检索索引。

## 子目录

| 目录 | 作用 |
| --- | --- |
| `memory/` | 长期记忆、候选记忆、用户偏好和会话摘要。 |
| `domain_docs/` | 人工整理的 Markdown 知识资料、流程、模板和术语表。 |
| `raw_docs/` | 原始文献和整理后的外部资料，包括 PDF、DOCX、TXT/MD、压缩包、图片和表格。 |
| `processed_docs/` | 从原始文献抽取或规范化得到的 Markdown 文本。 |
| `index/` | 文档清单、切块索引、来源 metadata、主题统计。 |

## 当前知识库状态

当前索引已经完成主题 metadata 细化，主题包括：

- 结构动力学、振动与冲击
- 有限元与仿真
- 复材、材料与制造
- 热结构与热防护
- 可靠性、质量与问题归零
- 系统工程与技术管理
- 公开产品资料
- 飞行器/薄壁结构
- 通用工程资料

核心统计文件：

```text
index/topic_summary.json
```

当前主索引文件：

```text
index/docs_manifest.json
index/chunks.jsonl
index/source_metadata.jsonl
index/archive_manifest.json
```

## 维护流程

整理外部压缩包资料：

```bash
python scripts/organize_source_archives.py --archive-mode hardlink
```

重新抽取文本并构建索引：

```bash
python scripts/ingest_documents.py
```

重新细化主题 metadata：

```bash
python scripts/refine_kb_metadata.py
```

本地检索：

```bash
python scripts/search_docs.py "关键词"
```

## 维护规则

- 不要把原始文献放入 `memory/`。
- 不要把长期记忆写入 `domain_docs/`。
- 不要手动编辑 `index/chunks.jsonl`，除非调试检索系统。
- 不要在任何知识库文件中写入 API Key、密码或 token。
- `restricted_reference` 资料只用于公开资料检索、高层解释和证据追溯，不得用于具体结构设计、制造、效能优化或部署。
