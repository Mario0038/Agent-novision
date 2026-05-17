# 操作说明和使用原则

项目名称：基于 DeepSeek V4 Pro 的命令行交互式专业分析与写作助手

原始创建者：Mario <ma15890397381@gmail.com>

## 1. 项目用途

本项目是一个在本地运行的命令行专业 Agent，面向专业分析、文献检索、写作辅助、长期记忆管理、工程流程辅助、通用机械结构教学验证和图片分析等场景。

正式入口：

```bash
python domain_agent.py
```

## 2. 环境准备

建议在项目根目录执行：

```bash
pip install -r requirements.txt
copy .env.example .env
python scripts/check_environment.py
```

然后在本地 `.env` 文件中填写自己的 API 配置。

注意：

- `.env` 保存真实 API Key，只能保留在本地。
- `.env` 已被 `.gitignore` 忽略，不应提交到 GitHub。
- `.env.example` 只保存占位符，用于说明需要哪些配置项。

## 3. 启动方式

检查 DeepSeek 配置：

```bash
python scripts/check_deepseek.py
```

启动 Agent：

```bash
python domain_agent.py
```

退出命令：

```text
exit
quit
退出
```

退出时会保存会话记录、会话摘要，并提取候选长期记忆。

## 4. 常用 Agent 命令

文献与知识库：

```text
/docs
/kbtopics
/searchdocs 关键词
/askdocs 问题
```

记忆管理：

```text
/remember 内容
/style 内容
/workflow 内容
/correction 内容
/focus 内容
/memory
/reload
```

候选记忆：

```text
/candidates
/acceptmem
/rejectmem
/forget keyword
```

识图：

```text
/vision image=examples/vision_test/test3.jpg prompt=请分析这张图片
/vision examples/vision_test/test3.jpg 请分析这张图片
```

## 5. 文献检索与入库

本地关键词检索不会调用 API：

```bash
python scripts/search_docs.py "关键词"
```

文献入库会读取 `knowledge_base/raw_docs/` 和 `knowledge_base/domain_docs/`，并更新索引：

```bash
python scripts/ingest_documents.py
```

原则：

- 原始 PDF、Word、TXT、Markdown 放入 `knowledge_base/raw_docs/`。
- 人工整理的 Markdown 知识资料放入 `knowledge_base/domain_docs/`。
- 自动提取文本放入 `knowledge_base/processed_docs/`。
- 索引文件放入 `knowledge_base/index/`。
- 不要把原始文献放入 `knowledge_base/memory/`。

## 6. 视觉模块

只检查视觉配置，不调用真实视觉 API：

```bash
python scripts/check_vision.py
```

独立识图测试会调用真实视觉 API：

```bash
python scripts/vision_image.py --image examples/vision_test/test3.jpg --prompt "请分析这张图片"
```

原则：

- 真实识图会消耗 API 额度，应由用户明确确认后执行。
- 不要把图片 base64 写入 `sessions/`。
- 不要把 `VISION_API_KEY` 写入代码、文档或日志。

## 7. SolidWorks 与工程脚本

检查 SolidWorks 连接：

```bash
python scripts/test_solidworks_connection.py
```

运行通用板件示例：

```bash
python scripts/run_create_plate.py
```

原则：

- 所有 SolidWorks 输出统一保存到 `generated_models/`。
- 不要把生成模型保存到项目根目录。
- 复杂建模和真实仿真应由用户明确确认后执行。

## 8. 安全与使用原则

1. 不读取、打印、提交 `.env` 中的真实 API Key。
2. 不把 API Key、token、密码写死到代码、README、日志或会话记录中。
3. 不自动运行真实 DeepSeek 长对话、真实视觉 API、复杂建模或真实仿真。
4. 不运行 `_archive/training/training_orchestrator.py`。
5. 不删除 `domain_agent.py`、`output/best_prompt.md`、`knowledge_base/memory/`。
6. 不破坏长期记忆、候选记忆、文献检索、识图命令和自然语言图片路径识别。
7. 不执行或输出可直接用于武器实现、优化、制造或部署的结构设计、参数或仿真流程。
8. 修改 Python 文件后至少运行 `python -m py_compile <文件>`。
9. GitHub 提交前检查 `.env`、`sessions/`、`generated_models/`、`generated_analysis/` 未被纳入提交。
10. 项目版权、作者署名和 NOTICE 文件应随项目一起保留。

## 9. 推荐验证命令

基础验证：

```bash
python scripts/check_environment.py
python scripts/check_deepseek.py
python -m py_compile domain_agent.py
```

文献模块验证：

```bash
python -m py_compile modules/doc_ingest.py
python -m py_compile modules/doc_search.py
python -m py_compile scripts/ingest_documents.py
python -m py_compile scripts/search_docs.py
```

视觉模块验证：

```bash
python -m py_compile modules/vision_client.py
python -m py_compile scripts/vision_image.py
python -m py_compile scripts/check_vision.py
python scripts/check_vision.py
```

以上视觉验证不应自动运行真实识图 API。

