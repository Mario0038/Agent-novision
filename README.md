# 基于 DeepSeek V4 Pro 的命令行交互式专业分析与写作助手

> Original creator: Mario <ma15890397381@gmail.com>  
> Copyright (c) 2026 Mario. All rights reserved.  
> See `AUTHORS.md`, `NOTICE`, and `LICENSE` for author attribution and copyright terms.

这是一个基于 **Python + DeepSeek V4 Pro + 本地知识库 + 工程工具接口** 的命令行交互式专业分析与写作助手。正式入口是：

```bash
python domain_agent.py
```

它不是网页端 GPT，也不是 GPT Builder 项目，而是在本地电脑上运行的专用 Agent。当前版本重点面向专业问答、文献检索、写作辅助、长期记忆、公开资料追溯、通用机械结构教学验证和工程流程辅助。

详细操作说明和使用原则见：

```text
docs/operation_guide.md
```

## 当前能力

1. 本地多轮对话 Agent。
2. 长期记忆与候选记忆系统。
3. PDF、DOCX、TXT、Markdown 文献入库与本地检索。
4. 知识库主题 metadata 分类与安全标签。
5. 自然语言自动判断是否需要检索知识库，并结合 DeepSeek 回答。
6. `/searchdocs` 本地检索和 `/askdocs` 强制知识库问答。
7. `/kbtopics` 查看知识库主题分布和安全标签统计。
8. 千问/Qwen 视觉模型识图入口。
9. SolidWorks 通用机械零件建模测试脚本。
10. ANSYS/FEA 任务包与环境检查脚本。

本项目不用于具体武器实现、敏感结构设计、战斗部、制导部件、发动机结构、发射机构或实战部署相关内容。遇到敏感请求时，Agent 应转为高层次、非操作性的系统工程或方法论说明。

## 快速开始

在项目根目录运行：

```bash
pip install -r requirements.txt
copy .env.example .env
python scripts/check_environment.py
python scripts/check_deepseek.py
python domain_agent.py
```

首次运行前，请在本地 `.env` 中填写自己的 API Key。`.env` 包含敏感信息，不应提交到 GitHub。

常用检查命令：

```bash
python scripts/check_vision.py
python scripts/test_solidworks_connection.py
python scripts/search_docs.py "结构动力学 模态"
```

退出 Agent：

```text
exit
quit
退出
```

退出时会保存会话记录、会话摘要，并提取候选长期记忆。

## Agent 内常用命令

### 文献与知识库

```text
/docs
/kbtopics
/searchdocs 关键词
/askdocs 问题
```

说明：

- `/docs`：列出已入库文献。
- `/kbtopics`：查看主题分类、安全标签、知识层级统计。
- `/searchdocs`：只做本地关键词与主题增强检索，不调用 API。
- `/askdocs`：先检索知识库，再调用 DeepSeek 综合回答，会消耗 API 额度。
- 直接输入自然语言问题时，Agent 会自动判断是否需要检索知识库；不一定必须使用 `/askdocs`。

示例：

```text
结构动力学中模态分析有什么作用？
有限元仿真可信度如何评估？
复合材料铺层设计需要注意哪些概念？
/searchdocs 热结构 热防护 热力耦合
/askdocs 系统工程中需求分解和指标分解的关系是什么？
```

### 记忆

```text
/remember 内容
/style 内容
/workflow 内容
/correction 内容
/focus 内容
/memory
/reload
```

### 候选记忆

```text
/candidates
/acceptmem
/rejectmem
/forget keyword
```

### 自动学习

```text
/autolearn status
/autolearn on
/autolearn off
```

### 识图

```text
/vision image=examples/vision_test/test3.jpg prompt=请分析这张图片
/vision examples/vision_test/test3.jpg 请分析这张图片
```

也支持自然语言图片路径识别：

```text
请分析 examples/vision_test/test3.jpg 这张图片
```

识图会调用千问/Qwen 视觉 API。`scripts/check_vision.py` 只检查配置是否存在，不实际调用 API。图片 base64 不会写入 `sessions/`。

## 知识库状态

当前知识库已经完成原始压缩包整理、文本抽取、索引构建和主题 metadata 细化。

当前统计：

| 项目 | 数量 |
| --- | ---: |
| 文档 | 8284 |
| 文本切块 | 238123 |
| 工程参考资料 | 6643 |
| 受限参考资料 | 1625 |
| 通用参考资料 | 16 |

主题分类：

| 主题 | 数量 |
| --- | ---: |
| 复材、材料与制造 | 5172 |
| 通用工程资料 | 1249 |
| 有限元与仿真 | 991 |
| 结构动力学、振动与冲击 | 586 |
| 飞行器/薄壁结构 | 240 |
| 公开产品资料 | 16 |
| 系统工程与技术管理 | 13 |
| 可靠性、质量与问题归零 | 13 |
| 热结构与热防护 | 4 |

主题统计文件：

```text
knowledge_base/index/topic_summary.json
```

核心索引文件：

```text
knowledge_base/index/docs_manifest.json
knowledge_base/index/chunks.jsonl
knowledge_base/index/source_metadata.jsonl
knowledge_base/index/archive_manifest.json
```

## 文献管理流程

原始文献目录：

```text
knowledge_base/raw_docs/pdf/
knowledge_base/raw_docs/word/
knowledge_base/raw_docs/text/
knowledge_base/raw_docs/archives/
knowledge_base/raw_docs/spreadsheets/
knowledge_base/raw_docs/images/
knowledge_base/raw_docs/other/
```

人工整理资料目录：

```text
knowledge_base/domain_docs/
```

自动提取文本目录：

```text
knowledge_base/processed_docs/
```

重新整理外部压缩包：

```bash
python scripts/organize_source_archives.py --archive-mode hardlink
```

重新入库：

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

支持格式：

| 格式 | 状态 |
| --- | --- |
| `.pdf` | 支持文字型 PDF |
| `.docx` | 支持 |
| `.txt` | 支持 |
| `.md` | 支持 |
| `.doc` | 暂不支持，建议转为 `.docx` |
| 扫描版 PDF | 暂不支持 OCR |
| `.pptx` / `.xlsx` | 暂不进入文本问答索引 |

## 知识库 metadata

当前 metadata 包含：

- `topic_primary`：主主题。
- `topic_label`：中文主题标签。
- `topic_tags`：相关主题标签。
- `topic_scores`：主题匹配得分。
- `knowledge_layer`：知识层级，例如 `processed_text_source`、`curated_domain_note`。
- `source_reliability`：来源可靠性标记。
- `safety_class`：安全分类，例如 `engineering_reference`、`restricted_reference`。
- `applicable_task`：适用任务范围。
- `not_applicable_task`：不适用任务范围。

`restricted_reference` 资料只用于公开资料检索、高层概念解释和证据追溯，不能作为具体结构设计、制造、仿真优化或部署依据。

## 目录结构

```text
.
├── AGENTS.md                    # Codex 项目维护规则
├── CLAUDE.md                    # Claude Code 项目规则
├── README.md                    # 项目总览
├── domain_agent.py              # 正式 Agent 入口
├── requirements.txt             # Python 依赖
├── output/
│   └── best_prompt.md           # Agent 核心 system prompt
├── modules/                     # 核心 Python 模块
├── scripts/                     # 检查脚本、入库脚本和命令行工具
├── examples/                    # 参数示例和测试图片
├── knowledge_base/              # 长期记忆、领域资料、索引
├── generated_models/            # SolidWorks 生成模型
├── generated_analysis/          # ANSYS/FEA 任务包和分析输出
├── sessions/                    # Agent 会话记录
├── reference/                   # 外部参考实现
└── _archive/                    # 历史归档内容
```

更详细的目录说明见：

- `modules/README.md`
- `scripts/README.md`
- `knowledge_base/README.md`
- `examples/README.md`
- `generated_models/README.md`
- `generated_analysis/README.md`

## 核心文件

| 文件/目录 | 作用 |
| --- | --- |
| `domain_agent.py` | 正式 Agent 主程序，负责对话、记忆、命令、路由、文献、视觉和工作流入口。 |
| `output/best_prompt.md` | Agent 核心 system prompt，不要删除、清空或随意覆盖。 |
| `.env` | 本地 API 配置文件，包含敏感 Key，不要上传、打印或写入代码。 |
| `modules/agent_router.py` | 自然语言路由，判断普通对话、RAG、CAD/FEA 或安全阻断。 |
| `modules/doc_ingest.py` | 文献抽取、切块、索引构建。 |
| `modules/doc_search.py` | 本地关键词与主题增强检索。 |
| `modules/kb_taxonomy.py` | 知识库主题分类规则。 |
| `scripts/refine_kb_metadata.py` | 细化 docs、chunks、source metadata 的主题与安全标签。 |
| `scripts/organize_source_archives.py` | 整理外部压缩包资料到知识库结构。 |
| `knowledge_base/memory/` | 长期记忆、写作偏好、候选记忆和会话摘要。 |
| `knowledge_base/index/` | 文献索引和主题 metadata。 |

## SolidWorks 建模

检查连接：

```bash
python scripts/test_solidworks_connection.py
```

运行通用板件示例：

```bash
python scripts/run_create_plate.py
```

运行教学机翼示例：

```bash
python scripts/create_wing_model.py
```

说明：

- `solidworks_controller.py` 是 SolidWorks COM 底层控制模块。
- `solidworks_generic_builder.py` 是通用零件模板模块。
- `solidworks_wing_builder.py` 是可选教学机翼模板模块。
- 所有生成模型应保存到 `generated_models/` 下，不要保存到项目根目录。

## ANSYS / FEA

相关模块：

```text
modules/ansys_environment.py
modules/fea_adapter_ansys.py
```

相关测试：

```bash
python scripts/test_ansys_environment.py
python scripts/test_ansys_static_dryrun.py
python scripts/test_fea_task_package.py
```

说明：

- 当前主要用于环境检测和静力分析任务包生成。
- dry-run 测试不应直接执行真实仿真。
- 真实复杂仿真需要用户明确确认。

## 视觉模块

配置检查：

```bash
python scripts/check_vision.py
```

独立识图：

```bash
python scripts/vision_image.py --image examples/vision_test/test3.jpg --prompt "请分析这张图片"
```

Agent 内识图：

```text
/vision image=examples/vision_test/test3.jpg prompt=请分析这张图片
```

支持图片格式：

```text
.png
.jpg
.jpeg
.webp
```

## 安全与维护规则

1. 不要读取、打印或提交 `.env` 中的真实 Key。
2. 不要把 API Key 写死到 Python、Markdown 或日志中。
3. 不要删除 `domain_agent.py`、`output/best_prompt.md`、`knowledge_base/memory/`。
4. 不要自动运行真实 DeepSeek 长对话、真实视觉 API、复杂建模或真实仿真。
5. 不要运行 `_archive/training/training_orchestrator.py`。
6. 不要把 `sessions/`、`generated_models/`、`generated_analysis/` 上传到 Git。
7. 修改 Python 文件后至少运行 `python -m py_compile <文件>`。
8. SolidWorks 和 ANSYS 输出统一放入 `generated_models/` 或 `generated_analysis/`。
9. 不要执行或输出可直接用于武器实现、优化或部署的结构设计、参数或仿真流程。

## 推荐使用顺序

第一次使用：

```bash
pip install -r requirements.txt
python scripts/check_environment.py
python scripts/check_deepseek.py
python domain_agent.py
```

添加资料后：

```bash
python scripts/organize_source_archives.py --archive-mode hardlink
python scripts/ingest_documents.py
python scripts/refine_kb_metadata.py
python scripts/search_docs.py "关键词"
```

需要识图时：

```bash
python scripts/check_vision.py
python domain_agent.py
```

需要建模前：

```bash
python scripts/test_solidworks_connection.py
```

开发验证：

```bash
python -m py_compile domain_agent.py
python -m py_compile modules/doc_ingest.py
python -m py_compile modules/doc_search.py
python -m py_compile modules/kb_taxonomy.py
python -m py_compile modules/agent_router.py
python -m py_compile scripts/refine_kb_metadata.py
```
