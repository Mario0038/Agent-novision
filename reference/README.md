# reference

本目录存放外部项目或实现思路的参考资料。

## 当前主要内容

| 目录 | 作用 |
| --- | --- |
| `qwen_vision_demo/` | Qwen 视觉接入参考 JS 文件。 |

## 维护规则

- 参考代码不作为 Python 主程序的运行依赖。
- 不要把参考 JS 直接混入 `domain_agent.py`。
- 不要在参考资料中写入真实 API Key。
- 如需借鉴外部实现，应在 Python 模块中重新实现，并保持接口清晰。
