# scripts

本目录存放命令行入口、检查脚本、知识库维护脚本和开发测试脚本。大多数脚本不是启动 Agent 必需项，但用于维护、验证和扩展项目。

## 环境检查

| 文件 | 作用 | 是否调用外部 API |
| --- | --- | --- |
| `check_environment.py` | 检查 Python 版本、依赖包、关键目录和关键文件。 | 否 |
| `check_deepseek.py` | 检查 DeepSeek 配置是否存在；不得打印真实 Key。 | 否 |
| `check_vision.py` | 检查视觉模型配置和 `vision_client.py` 是否可导入。 | 否 |

## 知识库维护

| 文件 | 作用 |
| --- | --- |
| `organize_source_archives.py` | 将外部压缩包资料整理到 `knowledge_base/raw_docs/`，并生成 `archive_manifest.json` 与 `source_metadata.jsonl`。 |
| `ingest_documents.py` | 调用 `modules/doc_ingest.py`，抽取文本并生成 `docs_manifest.json` 与 `chunks.jsonl`。 |
| `refine_kb_metadata.py` | 细化 docs、chunks、source metadata 的主题、知识层级、可靠性和安全标签。 |
| `search_docs.py` | 命令行本地检索入口，不调用 API。 |

推荐维护顺序：

```bash
python scripts/organize_source_archives.py --archive-mode hardlink
python scripts/ingest_documents.py
python scripts/refine_kb_metadata.py
python scripts/search_docs.py "结构动力学 模态"
```

## 视觉与工程工具

| 文件 | 作用 | 注意 |
| --- | --- | --- |
| `vision_image.py` | 独立识图测试入口。 | 会调用视觉 API，需用户明确确认。 |
| `test_solidworks_connection.py` | 测试 SolidWorks COM 连接，不创建模型。 | 可用于环境排查。 |
| `run_create_plate.py` | 创建通用带孔矩形板示例。 | 会调用 SolidWorks。 |
| `create_wing_model.py` | 创建通用低速无人机/教学用途梯形机翼示例。 | 会调用 SolidWorks。 |

## 开发测试

| 文件 | 作用 |
| --- | --- |
| `test_agent_router.py` | 测试自然语言路由和安全阻断。 |
| `test_task_planner.py` | 测试任务规划和参数提取。 |
| `test_design_synthesizer.py` | 测试设计参数综合。 |
| `test_auto_design_confirmation.py` | 测试自动设计确认流程。 |
| `test_cad_fea_workflow.py` | 测试 CAD/FEA 工作流编排。 |
| `test_fea_task_package.py` | 测试 ANSYS 任务包生成。 |
| `test_ansys_environment.py` | 测试 ANSYS 环境检测。 |
| `test_ansys_static_dryrun.py` | dry-run 方式测试静力分析流程。 |
| `test_wing_model_pipeline.py` | 测试教学机翼建模流水线。 |

## 维护规则

- 不要自动运行真实 API、复杂建模或真实仿真，除非用户明确确认。
- 所有脚本都不应打印 `.env` 中的真实 Key。
- 修改脚本后运行对应的 `python -m py_compile scripts/<file>.py`。
- 知识库脚本不扫描 `knowledge_base/memory/`，避免把长期记忆混入文献索引。
