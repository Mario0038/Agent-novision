# output

本目录存放 Agent 的核心输出和提示词文件。

## 关键文件

| 文件 | 作用 |
| --- | --- |
| `best_prompt.md` | `domain_agent.py` 启动时读取的核心 system prompt。 |

## 维护规则

- 不要删除或清空 `best_prompt.md`。
- 只有在明确优化 Agent 核心行为时才修改。
- 不要把文献全文塞进 prompt，文献应进入 `knowledge_base/` 并通过 RAG 检索。
- 不要在 prompt 或 README 中写入 API Key、密码或 token。
