# modules

本目录存放项目核心 Python 模块。`domain_agent.py` 会直接或间接调用这里的模块完成对话、路由、知识库检索、视觉识别、CAD/FEA 工作流和工程任务解析。

## 核心模块

| 文件 | 作用 |
| --- | --- |
| `agent_router.py` | 自然语言路由，判断普通对话、知识库 RAG、CAD/FEA、需要补充信息或安全阻断。 |
| `doc_ingest.py` | 文献入库，抽取 PDF/DOCX/TXT/MD 文本，生成 processed docs、manifest 和 chunks 索引。 |
| `doc_search.py` | 本地检索模块，读取 `knowledge_base/index/chunks.jsonl`，支持主题 metadata 加权检索。 |
| `kb_taxonomy.py` | 知识库主题分类规则，覆盖结构动力学、有限元、复材、热结构、可靠性、系统工程、公开产品资料等主题。 |
| `vision_client.py` | 千问/Qwen 视觉模型客户端，负责图片检查、base64 data URL 构造和视觉 API 调用。 |
| `design_parser.py` | 设计任务解析与 `/design_task` 兼容入口。 |
| `task_planner.py` | 将用户任务解析为结构化计划，提取零件类型、参数、材料和分析类型。 |
| `design_synthesizer.py` | 在参数不完整时综合默认参数，并生成需要用户确认的方案。 |
| `workflow_orchestrator.py` | 调度 CAD 建模、FEA 任务包生成等工程工作流。 |

## 工程工具模块

| 文件 | 作用 |
| --- | --- |
| `solidworks_controller.py` | SolidWorks COM 底层控制模块。 |
| `solidworks_generic_builder.py` | 通用机械零件建模模板，如板件、圆柱、法兰、支架、盒体/壳体。 |
| `solidworks_wing_builder.py` | 通用低速无人机/教学用途梯形机翼模板。 |
| `ansys_environment.py` | ANSYS 环境检测模块。 |
| `fea_adapter_ansys.py` | ANSYS 静力分析任务包、脚本和报告框架生成模块。 |

## 维护规则

- 修改 Python 文件后至少运行 `python -m py_compile <文件>`。
- 不要把 API Key、token 或密码写入任何模块。
- 不要让主程序依赖 `reference/` 中的示例 JS。
- 不要破坏 `/vision`、自然语言图片路径识别、知识库 RAG 和长期记忆逻辑。
- 敏感武器实现、详细结构设计、制造参数、效能优化或部署流程必须由路由和回答层阻断。
