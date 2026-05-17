# vision_test

本目录存放视觉识图模块的本地测试图片。

## 用途

- 供 `/vision` 命令手动测试使用。
- 供 `scripts/vision_image.py` 独立识图测试使用。
- 验证自然语言图片路径识别能力。

## 示例

```text
/vision image=examples/vision_test/test3.jpg prompt=请分析这张图片
请分析 examples/vision_test/test3.jpg 这张图片
```

## 维护规则

- 不要放隐私图片或敏感武器结构图片。
- 不要把图片 base64 写入会话、日志或 README。
- 真实识图会调用视觉 API，测试前需要用户明确确认。
