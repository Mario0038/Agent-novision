# Codex 项目规则

本文件是给 Codex 使用的项目维护规则。  
它不是给用户看的 README，也不是 `domain_agent.py` 的 system prompt。

本项目是一个基于 **DeepSeek API + Python + Codex** 的本地专业 Agent 项目，目前包含五部分能力：

1. 本地专业 Agent 对话系统；
2. 长期记忆与候选记忆系统；
3. 知识库文献管理系统（支持 PDF/Word/Markdown 入库与检索）；
4. SolidWorks 自动化连接与基础建模测试脚本；
5. 千问/Qwen 视觉模型识图模块。

---

## 1. 项目定位

本项目的正式 Agent 入口是：

```bash
python domain_agent.py
```

该 Agent 的核心 system prompt 来自：

```text
output/best_prompt.md
```

DeepSeek API 配置来自：

```text
.env
```

长期记忆文件位于：

```text
knowledge_base/memory/
```

SolidWorks 自动化脚本包括：

```text
modules/solidworks_controller.py
modules/solidworks_wing_builder.py
scripts/test_solidworks_connection.py
scripts/run_create_plate.py
scripts/create_wing_model.py
examples/plate_params.json
examples/wing_params.json
generated_models/
```

识图模块脚本包括：

```text
modules/vision_client.py
scripts/vision_image.py
scripts/check_vision.py
examples/vision_test/
reference/qwen_vision_demo/vision.js
```

识图模块已经接入 `domain_agent.py`，当前支持：

```text
/vision image=<path> prompt=<text>
/vision <图片路径> <提示词>
自然语言图片路径识别，例如：请分析 examples/vision_test/test3.jpg 这张图片
```

---

## 2. 绝对禁止操作

除非用户明确要求，否则不要执行以下操作：

- 不要读取、打印或修改 `.env`
- 不要泄露 API Key、token、密码等敏感内容
- 不要把 `DEEPSEEK_API_KEY` 或 `VISION_API_KEY` 写死到代码中
- 不要删除或清空 `output/best_prompt.md`
- 不要删除 `domain_agent.py`
- 不要删除 `knowledge_base/memory/`
- 不要删除 `sessions/`
- 不要删除 `generated_models/`
- 不要运行 `_archive/training/training_orchestrator.py`
- 不要自动发起 DeepSeek 长对话测试
- 不要自动调用千问/Qwen 真实识图 API，除非用户明确要求测试
- 不要把图片 base64 写入 `sessions/`
- 不要在日志或终端中打印 `VISION_API_KEY`
- 不要把 SolidWorks 生成文件保存到项目根目录
- 不要让 Python 主程序依赖 `reference/qwen_vision_demo/vision.js`
- 不要把 JS 代码直接混入 Python 主程序
- 不要删除 `/vision` 命令
- 不要破坏自然语言图片路径自动识别功能
- 不要把识图请求错误地送入普通 DeepSeek 对话分支
- 不要创建具体武器模型、战斗部、制导部件、发动机结构、发射机构或实战部署相关结构
- 不要输出可直接用于武器实现的结构、参数或仿真流程
- 不要进行敏感武器结构、战斗部、制导部件、发动机结构或实战部署图像分析

---

## 3. 允许操作

在用户要求下，可以执行以下操作：

- 修改普通 Python 工具脚本
- 创建环境检查脚本
- 运行 `python -m py_compile 文件名.py`
- 运行 `python scripts/check_environment.py`
- 运行 `python scripts/check_deepseek.py`
- 运行 `python scripts/check_vision.py`
- 运行 `python scripts/test_solidworks_connection.py`
- 运行 `python scripts/run_create_plate.py`
- 创建或修改 `generated_models/` 下的输出目录
- 创建通用机械零件测试模型
- 修改 README.md 或 AGENTS.md
- 为 `domain_agent.py` 增加安全、明确、可控的命令功能
- 创建或维护识图模块脚本
- 创建或维护文献入库与检索脚本（modules/doc_ingest.py、modules/doc_search.py 等）
- 整理 knowledge_base/ 目录结构
- 运行 `python scripts/ingest_documents.py`（需用户明确确认）
- 运行 `python scripts/search_docs.py 关键词`
- 在 Agent 内使用 `/docs`、`/searchdocs`（不调用 API）
- 在 Agent 内使用 `/askdocs`（需用户明确确认，会调用 DeepSeek API）
- 在用户明确确认后运行真实识图测试命令

在用户明确要求下，可以执行以下识图相关检查：

```bash
python scripts/check_vision.py
python -m py_compile modules/vision_client.py
python -m py_compile scripts/vision_image.py
python -m py_compile scripts/check_vision.py
python -m py_compile domain_agent.py
```

在用户明确确认真实测试时，可以执行：

```bash
python scripts/vision_image.py --image examples/vision_test/test3.jpg --prompt "请分析这张图片"
```

---

## 4. 关键文件说明

### `.env`

保存 DeepSeek API Key、千问视觉 API Key 和模型配置。

可能包含：

```env
DEEPSEEK_API_KEY=用户手动填写
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro

VISION_API_KEY=用户手动填写
VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VISION_MODEL=qwen3.5-omni-plus
```

规则：

- 不要读取
- 不要打印
- 不要修改
- 不要提交到 Git
- 不要在终端输出真实 Key
- 不要在代码、README、AGENTS.md 或日志中暴露真实 Key
- 可以检查变量是否存在，但不能输出变量值

---

### `domain_agent.py`

正式 Agent 主程序。

作用：

- 启动本地 Agent
- 读取 `.env`
- 读取 `output/best_prompt.md`
- 读取长期记忆
- 支持多轮对话
- 支持手动记忆和候选记忆管理
- 支持 `/vision` 显式识图命令
- 支持自然语言图片路径自动识别
- 保存会话记录

修改规则：

- 修改前要明确目的
- 不要破坏已有命令
- 不要删除长期记忆功能
- 不要删除候选记忆功能
- 不要删除安全边界
- 不要破坏 SolidWorks 自动化相关扩展接口
- 不要破坏 `/vision` 显式识图命令
- 不要破坏自然语言图片路径自动识别功能
- 不要让识图请求错误进入普通 DeepSeek 对话分支
- 修改后运行：

```bash
python -m py_compile domain_agent.py
```

---

### `output/best_prompt.md`

Agent 的核心 system prompt。

规则：

- 不要随意修改
- 不要清空
- 不要删除
- 只有用户明确要求优化 Agent 核心行为时，才可以修改

---

### `knowledge_base/`

项目知识库根目录，包含长期记忆和领域文献资料。

目录结构：

```text
knowledge_base/
├── memory/                          # 长期记忆（用户偏好、候选记忆、会话摘要）
├── domain_docs/                     # 人工整理的 Markdown 知识资料
│   ├── 00_core_subjects/            #   核心领域知识文件（00-09）
│   ├── 01_literature_notes/         #   文献摘要卡片
│   ├── 02_textbook_notes/           #   教材笔记
│   ├── 03_writing_templates/        #   写作模板
│   ├── 04_engineering_workflows/    #   工程流程说明
│   └── 05_glossary/                 #   术语表
├── raw_docs/                        # 原始文献（PDF/Word/TXT/MD）
│   ├── pdf/
│   ├── word/
│   ├── text/
│   └── other/
├── processed_docs/                  # 从原始文献提取的 Markdown 文本
│   ├── pdf/
│   ├── word/
│   └── text/
└── index/                           # 知识库索引
    ├── docs_manifest.json           #   文档清单
    └── chunks.jsonl                 #   切块文本
```

#### knowledge_base/memory/ — 长期记忆

包含：

```text
user_profile.md
writing_preferences.md
workflow_preferences.md
correction_patterns.md
domain_focus.md
candidate_memories.md
auto_memory_settings.md
session_summaries/
```

规则：

- 不要删除
- 不要乱清空
- 写入记忆时要避免敏感信息
- 候选记忆应先进入 `candidate_memories.md`
- 不要把一次性任务误写入长期记忆
- 不要把 API Key、账号、密码、token 写入长期记忆

#### knowledge_base/domain_docs/ — 领域知识资料

这里存放人工整理的 Markdown 知识资料。

适合放：
- 核心领域知识文件（00_core_subjects/）
- 文献摘要卡片（01_literature_notes/）
- 教材笔记（02_textbook_notes/）
- 写作模板（03_writing_templates/）
- 工程流程说明（04_engineering_workflows/）
- 术语表（05_glossary/）

规则：
- 不建议直接放原始 PDF/Word（请放入 raw_docs/）
- 不放自动生成的提取文本（请放入 processed_docs/）
- 不放长期记忆或用户偏好（请放入 memory/）

#### knowledge_base/raw_docs/ — 原始文献

这里存放原始 PDF、Word、TXT、MD 文件。

规则：
- pdf/ 放 PDF 文件
- word/ 放 DOCX 文件
- text/ 放 TXT 或 MD 文件
- other/ 放暂未支持的文件格式
- 不要把原始文献放入 memory/
- 不要把原始文献放入 domain_docs/

#### knowledge_base/processed_docs/ — 提取后的文本

这里存放从 PDF/Word/TXT/MD 提取后的 Markdown 文本。

规则：
- 这些文件由入库脚本（modules/doc_ingest.py）自动生成
- 一般不手动编辑
- 必要时可人工修正提取错误
- 文献检索会读取此目录和 domain_docs/

#### knowledge_base/index/ — 知识库索引

这里存放知识库索引文件。

规则：
- docs_manifest.json 记录文档清单（标题、来源、路径、入库时间等）
- chunks.jsonl 记录切块文本（每行一个 JSON 对象）
- /searchdocs 和 /askdocs 命令使用这里的索引
- 索引由入库脚本自动生成或更新
- 不要手动编辑索引文件（除非调试）

#### knowledge_base/ 总体规则

1. knowledge_base/memory/ 只放用户长期记忆、偏好、候选记忆和会话摘要
2. knowledge_base/domain_docs/ 放人工整理的 Markdown 知识资料
3. knowledge_base/raw_docs/ 放原始 PDF、Word、TXT、MD 文件
4. knowledge_base/processed_docs/ 放从原始文献中提取出的 Markdown 文本
5. knowledge_base/index/ 放 docs_manifest.json 和 chunks.jsonl
6. 不要把 PDF/Word 原文放入 memory/
7. 不要把整篇文献全文塞入 output/best_prompt.md
8. 后续文献检索应读取 processed_docs/ 和 domain_docs/，并生成 index/chunks.jsonl

---

### `sessions/`

完整会话记录目录。

规则：

- 不要上传
- 不要随意删除
- 可用于复盘和记忆总结
- 不要把图片 base64 写入 sessions
- 如果接入识图功能，只保存识图结果文本，不保存图片 base64

---

## 5. SolidWorks 自动化规则

SolidWorks 自动化脚本包括：

```text
modules/solidworks_controller.py
modules/solidworks_wing_builder.py
scripts/test_solidworks_connection.py
scripts/run_create_plate.py
scripts/create_wing_model.py
examples/plate_params.json
examples/wing_params.json
generated_models/
```

---

### `modules/solidworks_controller.py`

SolidWorks COM 控制器模块。

作用：

- 连接 SolidWorks
- 新建零件
- 创建草图
- 拉伸实体
- 保存 SLDPRT
- 导出 STEP

修改后运行：

```bash
python -m py_compile modules/solidworks_controller.py
```

---

### `scripts/test_solidworks_connection.py`

SolidWorks 连接测试脚本。

运行方式：

```bash
python scripts/test_solidworks_connection.py
```

作用：

- 测试 Python 是否能通过 COM 连接 SolidWorks
- 不创建模型
- 不保存文件
- 不运行仿真

---

### `scripts/run_create_plate.py`

带孔矩形板建模测试入口。

运行方式：

```bash
python scripts/run_create_plate.py
```

作用：

- 读取 `examples/plate_params.json`
- 调用 `modules/solidworks_controller.py`
- 创建通用带孔矩形板
- 保存 SLDPRT
- 导出 STEP

---

### `examples/plate_params.json`

带孔矩形板参数文件。

示例：

```json
{
  "length_mm": 100,
  "width_mm": 50,
  "thickness_mm": 5,
  "hole_diameter_mm": 10
}
```

---

## 6. SolidWorks 输出目录规则

所有 SolidWorks 自动生成文件必须放在：

```text
generated_models/
```

推荐结构：

```text
generated_models/
└── solidworks/
    ├── parts/
    ├── step/
    ├── drawings/
    └── simulations/
```

具体规则：

- `.SLDPRT` 保存到 `generated_models/solidworks/parts/`
- `.STEP` 或 `.STP` 保存到 `generated_models/solidworks/step/`
- 工程图保存到 `generated_models/solidworks/drawings/`
- 仿真相关文件保存到 `generated_models/solidworks/simulations/`
- 日志文件保存到 `generated_models/logs/`

禁止将 SolidWorks 生成文件保存到项目根目录。

---

## 7. SolidWorks 安全边界

允许创建：

- 通用矩形板
- 通用圆柱
- 通用支架
- 通用壳体示意件
- 通用低速无人机梯形机翼教学/验证模型
- 非武器化教学零件
- 通用机械结构验证模型

禁止创建：

- 具体导弹外形
- 具体导弹弹翼、尾翼、舵面
- 战斗部结构
- 制导部件
- 发动机结构
- 发射机构
- 实战部署相关模型
- 可直接用于武器实现的结构模型
- 可直接用于武器效能提升的仿真流程

如果用户提出敏感建模请求，应转为高层次、非操作性的系统工程或方法论说明。

### 7.1 机翼建模规则

梯形机翼模型属于通用低速无人机教学/验证模型。

相关文件：

```text
modules/solidworks_wing_builder.py
scripts/create_wing_model.py
examples/wing_params.json
```

规则：
- 机翼模型输出到 `generated_models/solidworks/wing/parts/` 和 `generated_models/solidworks/wing/step/`
- 第一版使用简单梯形实体，不使用真实 NACA 翼型放样
- 不创建具体导弹弹翼、尾翼、舵面或制导相关翼面
- 不要自动运行 Fluent
- 不要自动运行 SolidWorks 建模
- 只有用户明确确认后才运行 `python scripts/create_wing_model.py`

---

## 8. 识图模块维护规则

当前项目已经新增千问/Qwen 识图模块。  
该模块参考了 GitHub 项目 `asuojun/Codex-vision-skill` 中 `vision.js` 的实现思路，但当前项目主体是 Python，因此不直接运行 `vision.js`，而是使用 Python 版识图模块。

当前千问/Qwen 识图模块已经接入 `domain_agent.py`。

相关文件：

```text
modules/vision_client.py
scripts/vision_image.py
scripts/check_vision.py
examples/vision_test/
reference/qwen_vision_demo/vision.js
domain_agent.py
```

当前支持三种方式：

```text
/vision image=examples/vision_test/test3.jpg prompt=请分析这张图片
/vision examples/vision_test/test3.jpg 请分析这张图片
请分析 examples/vision_test/test3.jpg 这张图片
```

维护原则：

1. 保留 `/vision` 显式命令；
2. 保留自然语言图片路径自动识别；
3. 只有同时检测到图片路径和分析意图时，才自动调用视觉 API；
4. 如果只检测到图片路径但没有分析意图，不调用 API，只提示用户；
5. 识图结果可以保存到会话记录；
6. 图片 base64 不得保存到会话记录；
7. 不要将识图请求继续送入普通 DeepSeek 对话分支；
8. 不要自动运行真实识图测试。

---

### 8.1 识图模块文件

识图模块相关文件包括：

```text
modules/vision_client.py
scripts/vision_image.py
scripts/check_vision.py
examples/vision_test/
reference/qwen_vision_demo/vision.js
```

文件作用：

```text
modules/vision_client.py
    Python 版识图核心模块，负责图片读取、格式检查、base64 data URL 转换和视觉模型调用。

scripts/vision_image.py
    独立命令行识图测试入口。

scripts/check_vision.py
    视觉 API 配置检查脚本，不实际调用 API。

examples/vision_test/
    用户手动放置测试图片的目录。

reference/qwen_vision_demo/vision.js
    GitHub 原项目中的参考文件，不作为当前 Python 项目的运行入口。
```

---

### 8.2 视觉模型配置

视觉模型配置位于 `.env`，变量名如下：

```env
VISION_API_KEY=用户手动填写
VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VISION_MODEL=qwen3.5-omni-plus
```

维护规则：

- 不要读取、打印或修改 `.env` 中的真实 API Key；
- 不要把 `VISION_API_KEY` 写死进任何代码；
- 不要在日志、终端输出、README 或注释中暴露真实 API Key；
- 可以检查变量是否存在，但不能输出变量值；
- 不要删除原有 DeepSeek 配置。

---

### 8.3 图片路径解析规则

`domain_agent.py` 中的图片路径应统一按项目根目录解析。

要求：

- 相对路径以项目根目录 `ROOT` 为基准；
- 不要依赖 `Path.cwd()`；
- 支持路径示例：

```text
examples/vision_test/test3.jpg
`examples/vision_test/test3.jpg`
"examples/vision_test/test3.jpg"
E:\BIT\Agent-MVP\Codex\examples\vision_test\test3.jpg
```

- 识别路径时应去除首尾引号、反引号和中文标点；
- 文件不存在时应提示原始路径和解析后路径；
- 文件后缀必须与真实文件一致，例如 `.jpg` 不要写成 `.png`。

---

### 8.4 允许操作

在用户明确要求下，可以执行：

```bash
python -m py_compile modules/vision_client.py
python -m py_compile scripts/vision_image.py
python -m py_compile scripts/check_vision.py
python scripts/check_vision.py
python -m py_compile domain_agent.py
```

说明：

- `py_compile` 只做语法检查；
- `check_vision.py` 只检查配置是否存在，不实际调用 API；
- 这些操作不会调用 DeepSeek API；
- 这些操作不会调用千问视觉 API。

---

### 8.5 真实识图测试

真实识图测试命令：

```bash
python scripts/vision_image.py --image examples/vision_test/test3.jpg --prompt "请分析这张图片"
```

Agent 内真实识图测试：

```text
请分析 examples/vision_test/test3.jpg 这张图片
```

注意：

- 该命令会调用千问视觉 API；
- 会消耗 API 额度；
- 只有用户明确确认后才运行；
- 不要自动运行真实识图测试。

---

### 8.6 禁止操作

除非用户明确要求，否则不要执行以下操作：

- 不要修改 `.env`；
- 不要读取或打印 `VISION_API_KEY`；
- 不要把 API Key 写入代码；
- 不要修改 `output/best_prompt.md`；
- 不要破坏 `domain_agent.py` 现有功能；
- 不要删除长期记忆系统；
- 不要删除 SolidWorks 自动化脚本；
- 不要运行 `_archive/training/training_orchestrator.py`；
- 不要自动调用 DeepSeek API；
- 不要自动调用千问视觉 API；
- 不要让 Python 主程序依赖 `reference/qwen_vision_demo/vision.js`；
- 不要把 JS 代码混入 Python 主程序；
- 不要破坏 `/vision` 命令；
- 不要破坏自然语言识图逻辑。

---

### 8.7 识图功能适用范围

允许用于：

```text
普通图片分析
工程图分析
仿真图分析
软件界面截图分析
图表分析
论文或报告图片解释
实验结果截图分析
```

禁止用于：

```text
具体武器结构识别
战斗部结构分析
制导部件识别
发动机结构分析
发射机构分析
实战部署图像分析
可直接用于武器实现、攻击、优化或部署的图像分析
```

如遇敏感图像请求，应转为高层次、非操作性的系统工程或方法论说明。

---

### 8.8 识图模块当前运行方式

配置检查：

```bash
python scripts/check_vision.py
```

独立识图测试：

```bash
python scripts/vision_image.py --image examples/vision_test/test3.jpg --prompt "请分析这张图片"
```

Agent 内显式识图：

```text
/vision image=examples/vision_test/test3.jpg prompt=请分析这张图片
```

Agent 内自然语言识图：

```text
请分析 examples/vision_test/test3.jpg 这张图片
```

测试图片目录：

```text
examples/vision_test/
```

视觉模型：

```text
qwen3.5-omni-plus
```

视觉接口：

```text
https://dashscope.aliyuncs.com/compatible-mode/v1
```

---

### 8.9 识图模块维护原则

Codex 在维护识图模块时应遵守：

1. 先检查，再修改；
2. 不碰 `.env` 中的真实 Key；
3. 不自动运行真实 API 调用；
4. 不让 JS 参考文件影响 Python 主程序；
5. 保留 `/vision` 显式命令；
6. 保留自然语言图片路径自动识别；
7. 只有同时检测到图片路径和分析意图时才调用视觉 API；
8. 如果只检测到图片路径但无分析意图，不调用 API；
9. 不把图片 base64 写入会话记录；
10. 不破坏现有 Agent、记忆系统和 SolidWorks 自动化功能。

---

### 8.10 文献入库与检索模块

文献管理脚本（已实现）：

```text
modules/doc_ingest.py
modules/doc_search.py
scripts/ingest_documents.py
scripts/search_docs.py
```

这些脚本遵守 knowledge_base 目录结构：

1. 原始文献读取目录：`knowledge_base/raw_docs/`
2. 人工整理资料读取目录：`knowledge_base/domain_docs/`
3. 自动转换结果输出目录：`knowledge_base/processed_docs/`
4. 索引输出目录：`knowledge_base/index/`
5. 不要扫描 `knowledge_base/memory/`

入库脚本职责：
- 读取 raw_docs/ 中的 PDF/Word/TXT/MD
- 提取文本并转换为 Markdown
- 输出到 processed_docs/ 对应子目录
- 按 800-1200 字符切块（120 字符重叠）
- 更新 index/docs_manifest.json 和 index/chunks.jsonl

检索脚本职责：
- 读取 index/chunks.jsonl 进行关键词检索（不调用 API）
- 同时支持检索 processed_docs/ 和 domain_docs/（均通过索引）
- 不读取 raw_docs/ 中的原始文件（应检索已处理文本）

支持的格式：
- ✅ .pdf（PyMuPDF 提取）
- ✅ .docx（python-docx 提取）
- ✅ .txt / .md（规范化处理）

暂不支持的格式：
- ❌ .doc（建议用户手动转为 .docx）
- ❌ 扫描版 PDF（暂不进行 OCR）
- ❌ .pptx / .xlsx

Agent 内命令：

| 命令 | 作用 | 调用 API |
|------|------|---------|
| `/docs` | 列出已入库文献清单 | 否 |
| `/searchdocs 关键词` | 关键词检索相关片段 | 否 |
| `/askdocs 问题` | 检索后由 DeepSeek 综合回答 | 是 |

规则：
- `/searchdocs` 不调用 API，仅关键词匹配
- `/askdocs` 会调用 DeepSeek API，只有用户主动输入时才调用
- 不要自动运行入库脚本
- 不要自动运行 `/askdocs`
- 不要自动调用任何 API 做 embedding
- 不要把原始 PDF/Word 放入 memory/
- 不要把整篇文献全文塞入 output/best_prompt.md
- 暂不处理扫描版 PDF OCR
- .doc 文件建议用户先手动转为 .docx

语法检查：

```bash
python -m py_compile modules/doc_ingest.py
python -m py_compile modules/doc_search.py
python -m py_compile scripts/ingest_documents.py
python -m py_compile scripts/search_docs.py
```

---

## 9. 推荐运行命令

### 启动专业 Agent

```bash
python domain_agent.py
```

### 检查项目环境

```bash
python scripts/check_environment.py
```

### 检查 DeepSeek API

```bash
python scripts/check_deepseek.py
```

### 检查视觉 API 配置

```bash
python scripts/check_vision.py
```

### 测试 SolidWorks 连接

```bash
python scripts/test_solidworks_connection.py
```

### 运行 SolidWorks 建模测试

```bash
python scripts/run_create_plate.py
```

### 独立识图测试

```bash
python scripts/vision_image.py --image examples/vision_test/test3.jpg --prompt "请分析这张图片"
```

### Agent 内识图测试

```text
请分析 examples/vision_test/test3.jpg 这张图片
```

### 文献入库

```bash
python scripts/ingest_documents.py
```

### 文献检索

```bash
python scripts/search_docs.py "关键词"
```

### Agent 内文献管理

```text
/docs                     （列出已入库文献）
/searchdocs 关键词         （检索相关片段，不调用 API）
/askdocs 问题              （检索 + DeepSeek 回答，调用 API）
```
```

### Python 语法检查

```bash
python -m py_compile domain_agent.py
python -m py_compile modules/solidworks_controller.py
python -m py_compile scripts/run_create_plate.py
python -m py_compile modules/vision_client.py
python -m py_compile scripts/vision_image.py
python -m py_compile scripts/check_vision.py
```

---

## 10. 修改代码后的验证规则

修改 Python 文件后，必须至少运行：

```bash
python -m py_compile 修改的文件.py
```

如果修改了 SolidWorks 自动化脚本，可以运行：

```bash
python scripts/test_solidworks_connection.py
```

如果用户明确确认要测试建模，可以运行：

```bash
python scripts/run_create_plate.py
```

如果修改了识图模块或 `domain_agent.py` 的识图逻辑，至少运行：

```bash
python -m py_compile domain_agent.py
python -m py_compile modules/vision_client.py
python -m py_compile scripts/vision_image.py
python -m py_compile scripts/check_vision.py
python scripts/check_vision.py
```

如果修改了文献入库或检索模块，运行：

```bash
python -m py_compile modules/doc_ingest.py
python -m py_compile modules/doc_search.py
python -m py_compile scripts/ingest_documents.py
python -m py_compile scripts/search_docs.py
```

不要自动运行真实识图 API。

只有用户明确确认后，才可以运行：

```bash
python scripts/vision_image.py --image examples/vision_test/test3.jpg --prompt "请分析这张图片"
```

不要在未确认的情况下自动运行复杂建模、仿真或真实 API 调用。

---

## 11. Git 忽略建议

`.gitignore` 应包含：

```gitignore
.env
__pycache__/
.pytest_cache/
*.pyc
*.log
.idea/
.venv/
sessions/
generated_models/
.DS_Store
```

重点：

- `.env` 不能上传；
- `sessions/` 不建议上传；
- `generated_models/` 不建议上传；
- `.idea/` 通常不上传；
- 测试图片如包含隐私或敏感信息，也不建议上传。

---

## 12. 当前开发阶段

当前阶段：

```text
本地 Agent 已可运行
长期记忆系统已建立
知识库目录结构已整理
文献入库与检索系统已建立（支持 PDF/DOCX/TXT/MD）
SolidWorks COM 连接已通过
基础带孔矩形板建模已跑通
梯形机翼参数化建模模板已创建（待运行）
千问/Qwen 识图独立模块已跑通
/vision 命令已接入 domain_agent.py
自然语言图片路径自动识别已接入 domain_agent.py
SolidWorks 尚未完全接入 domain_agent.py
文献入库与检索脚本待开发
```

当前推荐保持三条主线：

### 专业 Agent 主线

```bash
python domain_agent.py
```

用于专业问答、写作、记忆管理、Agent 内识图。

### SolidWorks 自动化主线

```bash
python scripts/test_solidworks_connection.py
python scripts/run_create_plate.py
```

用于连接测试和基础建模测试。

### 识图模块主线

```bash
python scripts/check_vision.py
python scripts/vision_image.py --image examples/vision_test/test3.jpg --prompt "请分析这张图片"
```

用于检查视觉配置和独立图片识别。

后续如果用户明确要求，再将以下命令接入或完善到 `domain_agent.py`：

```text
/sw_create_plate length=... width=... thickness=... hole=...
```

---

## 13. 给 Codex 的总体原则

在本项目中，Codex 应遵守：

1. 先检查，再修改；
2. 小步修改，不一次性大改；
3. 不碰 `.env`；
4. 不乱改 `output/best_prompt.md`；
5. 不破坏 `domain_agent.py` 现有功能；
6. 不破坏长期记忆和候选记忆系统；
7. 不破坏 `/vision` 和自然语言识图功能；
8. 不破坏知识库目录结构；
9. SolidWorks 文件统一放入 `generated_models/`；
10. 识图参考 JS 文件只保存在 `reference/qwen_vision_demo/`；
11. 原始文献只放入 `knowledge_base/raw_docs/`，不放 memory/ 或 domain_docs/；
12. 修改代码后做语法检查；
13. 不运行训练脚本；
14. 不自动调用真实 API；
15. 不执行敏感武器设计；
16. 不进行敏感武器图像分析；
17. 对不确定的操作先说明，再等待用户确认。