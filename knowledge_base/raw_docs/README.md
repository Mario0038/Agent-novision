# raw_docs

本目录存放原始资料和由压缩包整理得到的未加工文件。入库脚本会从这里读取支持的文档格式，并将提取结果输出到 `knowledge_base/processed_docs/`。

## 子目录

| 目录 | 作用 |
| --- | --- |
| `archives/` | 原始压缩包副本或硬链接。 |
| `pdf/` | PDF 文献。 |
| `word/` | DOCX 文档。 |
| `text/` | TXT、Markdown 和代码仓库中的说明文本。 |
| `spreadsheets/` | XLSX、CSV 等表格资料，当前不进入文本问答索引。 |
| `images/` | 图片资料，当前不进入文本问答索引。 |
| `other/` | 暂未支持或暂未分类的文件。 |

## 支持入库的格式

| 格式 | 状态 |
| --- | --- |
| `.pdf` | 支持文字型 PDF |
| `.docx` | 支持 |
| `.txt` | 支持 |
| `.md` | 支持 |
| `.doc` | 暂不支持，建议转为 `.docx` |
| 扫描版 PDF | 暂不支持 OCR |
| `.xlsx` / `.csv` | 已整理保存，但暂不进入文本问答索引 |

## 维护规则

- 不要把原始资料放入 `memory/` 或 `domain_docs/`。
- 不要手动修改外部项目自带的 README 或源码文件，避免污染来源资料。
- 新增压缩包后，优先使用 `scripts/organize_source_archives.py` 统一整理。
- 涉及公开产品资料或敏感领域的来源应保留 `restricted_reference` 等安全标签。
