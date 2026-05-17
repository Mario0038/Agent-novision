# raw archives

本目录存放外部原始压缩包的副本或硬链接。

生成方式：

```bash
python scripts/organize_source_archives.py --archive-mode hardlink
```

维护规则：

- 压缩包用于来源追溯，不直接参与文本检索。
- 不要手动解压到项目根目录。
- 不要修改原始压缩包内容。
- 若重新整理，应同步更新 `knowledge_base/index/archive_manifest.json` 和 `source_metadata.jsonl`。
