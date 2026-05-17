# memory

本目录存放长期记忆、候选记忆、用户偏好和会话摘要。它属于 Agent 的个性化记忆系统，不属于文献知识库。

## 主要文件

| 文件/目录 | 作用 |
| --- | --- |
| `user_profile.md` | 用户背景和长期偏好。 |
| `writing_preferences.md` | 写作风格偏好。 |
| `workflow_preferences.md` | 工作流程偏好。 |
| `correction_patterns.md` | 纠错模式。 |
| `domain_focus.md` | 长期关注方向。 |
| `candidate_memories.md` | 待确认候选记忆。 |
| `auto_memory_settings.md` | 自动学习设置。 |
| `session_summaries/` | 会话摘要。 |

## Agent 内命令

```text
/remember 内容
/style 内容
/workflow 内容
/correction 内容
/focus 内容
/memory
/candidates
/acceptmem
/rejectmem
/forget keyword
/autolearn status
```

## 维护规则

- 不要写入 API Key、账号、密码、token。
- 不要把一次性任务写成长期记忆。
- 不要把原始文献、PDF、Word 或全文资料放进这里。
- 候选记忆应先进入 `candidate_memories.md`，再由用户确认。
- 本目录不应被 `scripts/ingest_documents.py` 扫描入库。
