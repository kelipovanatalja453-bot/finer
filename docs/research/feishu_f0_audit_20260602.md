# 飞书 F0 模块只读体检报告

> 日期：2026-06-02  
> 范围：`src/finer/ingestion/feishu_poller.py`、Feishu 相关 F0 入口、F0 契约、card #3 stopgap 路径。  
> 执行方式：只读代码/文档/数据核验；未重导飞书，未跑 F0-F8，未冻 pack，未修改源码，未 `git add`。

## 结论

推荐 **(b) 旁边建一条最小干净路径：飞书导出文件/消息窗口 -> `ContentRecord` + 真实 `published_at`**。

现有 Feishu F0 不能直接作为本次重导入口：它的主链路写 `ContentManifest`，不写 canonical `ContentRecord`；`published_at` 没有可靠使用飞书 IM 逐条 `create_time`；并且 `sync_chat()` 把 Vision、Summary、NotebookLM 上传和可触发 LLM 的分类逻辑混在 F0 内。若直接修现有模块，必须先拆除这些历史职责，改动面会覆盖 poller、orchestrator、integration routes、classifier、receipt、tests 和落盘结构。对“重新导入前建立可信 F0 输入”这个目标，旁路更短、更可控。

审计裁决：**PAUSE 现有 Feishu F0 作为重导入口；CONTINUE 新建最小 F0-only 导出注册路径。**

## 审计基准

- 根规则要求 F0 的核心 schema 是 `ContentRecord`，`ingestion/` 是 F0 owning area：`AGENTS.md:27-35`, `AGENTS.md:58-78`。
- F0 权威契约要求输出 `ContentRecord + 原始文件归档到 data/F0_intake/ 和 data/raw/`：`docs/specs/f-stage-contracts.md:34-40`。
- F0 禁止 OCR/ASR/文本解析/LLM/质量判断/改写原始内容：`docs/specs/f-stage-contracts.md:71-78`。
- A2a Feishu channel 的目标输出是 raw archive、`ContentRecord`、import receipt、Line F error details：`docs/specs/2026-05-parallel-agent-execution.md:312-333`, `docs/specs/2026-05-parallel-agent-execution.md:343-357`。

## AS-6a：四点结论

### 1. 产物类型

结论：**现有 Feishu F0 主产物不是 canonical `ContentRecord`，而是 `ContentManifest`；`FeishuPoller` 本身只返回消息/下载对象。**

证据：

- `FeishuPoller` 定义 `FeishuMessage` 和 `DownloadedFile`，字段里有 `message_id`、`create_time`、`sent_at`，但没有 `ContentRecord`：`src/finer/ingestion/feishu_poller.py:24-48`。
- `poll_chat()` 从 lark-cli 结果解析 `create_time` 并返回 `FeishuMessage` 列表：`src/finer/ingestion/feishu_poller.py:121-200`。
- `download_attachment()` 只把附件保存到 inbox，并返回 `DownloadedFile(sent_at=message.create_time)`：`src/finer/ingestion/feishu_poller.py:202-256`。
- `orchestrator._create_manifest()` 构造 `ContentManifest`，再调用 `write_manifest()`：`src/finer/ingestion/orchestrator.py:60-115`。
- `orchestrator._create_chat_transcript_manifest()` 也构造 `ContentManifest`：`src/finer/ingestion/orchestrator.py:118-160`。
- `/api/integrations/import` 从 pool 导入时构造 `ContentManifest` 并 `write_manifest()`：`src/finer/api/routes/integrations.py:302-377`。
- 对 Feishu 相关入口做 symbol scan，只有 `ContentManifest/write_manifest`，没有 `ContentRecord` import、构造或 `data/F0_intake` 写入：`src/finer/ingestion/orchestrator.py:26,94,113,139,158`, `src/finer/api/routes/integrations.py:13,218,241,349,370`。

是否能转成 `ContentRecord`：**可以作为兼容输入转，但不能原样信任。**

原因：

- `ContentManifest` 是 `ContentRecord` 的 dataclass mirror，字段形状基本对应：`src/finer/manifests.py:15-42`；`ContentRecord.to_manifest()` / `ContentManifest.from_record()` 也说明两者可互转：`src/finer/schemas/content.py:73-95`, `src/finer/manifests.py:74-95`。
- 但现有 Feishu manifest 需要先修正/补齐：`published_at` 可能不是飞书真实时间；`published_at/collected_at` 是 ISO string，需要转 `datetime`；`source_type` 是 unconstrained string，而 `ContentRecord.source_type` 是 Literal：`src/finer/schemas/content.py:22-36`；`external_source_id` 和 `dedupe_fingerprint` 当前多为 `None`：`src/finer/ingestion/orchestrator.py:106-108`, `src/finer/api/routes/integrations.py:364-366`；`raw_path` 落在 manifest 目录索引体系，不是明确的 `data/F0_intake/feishu/.../{content_id}.json`。

最小转换要求：

1. 从飞书原始消息或导出 manifest 中取 `message_id/chat_id/create_time`，不要从现有 manifest 的 `published_at` 反推。
2. `published_at = message.create_time`，无法核验则 `None`，并在 `metadata.timestamp_source` 标注。
3. `external_source_id = message_id` 或 chat-window 稳定 ID。
4. `dedupe_fingerprint = sha256(platform + chat_id + message_id + raw_hash)` 或导出窗口 hash。
5. `source_type` 归一化到 `feishu_chat` / `chat_transcript` / `chat_export` 等 schema 允许值。
6. 写 `ContentRecord` JSON 到 `data/F0_intake/feishu/...`，manifest 只做兼容投影。

### 2. `published_at` 现状

结论：**F0 Feishu 当前没有把飞书 IM 自带的逐条真实时间戳可靠写进产物的 `published_at`。它只在 poller 阶段拿到了 `create_time`，后续落盘时被 filename/date inference、`datetime.now()` 或 `datetime.utcnow()` 替换/降级。**

证据：

- poller 确实解析飞书 `create_time`：`src/finer/ingestion/feishu_poller.py:71-89`, `src/finer/ingestion/feishu_poller.py:161-179`。
- 下载附件时 `DownloadedFile.sent_at` 等于 `message.create_time`：`src/finer/ingestion/feishu_poller.py:241-249`。
- 但附件 manifest 的 `published_at` 取自 `classification.published_at`，不是 `file.sent_at`：`src/finer/ingestion/orchestrator.py:94-105`。
- `classification.published_at` 由 `_infer_date(filename, sent_at)` 产生；如果 filename 里有 `YYYYMMDD`，会返回当天 09:00，而不是原始 HH:MM；否则才 fallback 到 `sent_at`：`src/finer/ingestion/classifier.py:95-112`, `src/finer/ingestion/classifier.py:220-229`。
- Feishu 下载文件名本身被 prefix 成 `YYYYMMDD_HHMM_...`，会命中 `_infer_date()` 的 `YYYYMMDD` 规则，从而把真实分钟级时间降级成 09:00：`src/finer/ingestion/feishu_poller.py:216-220`, `src/finer/ingestion/classifier.py:88-108`。
- 聊天 transcript manifest 的 `published_at` 直接用 `datetime.now().isoformat()`，不是窗口首条/末条消息时间：`src/finer/ingestion/orchestrator.py:139-146`。
- API pool import 的 `published_at` 直接用 `datetime.utcnow().isoformat()`，不是飞书消息时间：`src/finer/api/routes/integrations.py:323-356`。
- `/api/integrations/feishu/fetch` 创建 transcript 时保留了文本里的时间范围和逐条 header，但只写到 pool 文件，并没有写 `ContentRecord.published_at`：`src/finer/api/routes/integrations.py:105-127`。

card #3 那条 `published_at` 的来源确认：**不是 F0 Feishu 做的。**

- card #3 的 stopgap 脚本手工定义 `ITEMS[0].published_at = "2026-03-12T00:00:00+08:00"`：`scripts/b1_diagnostic_run.py:54-78`。
- 该值在 `build_content_record()` 里手工转成 `datetime` 后传给 `ContentRecord`：`scripts/b1_diagnostic_run.py:81-99`。
- raw pack manifest 也说明 3/12 的发布时间来自 fixture header，而不是 Feishu F0 导入：`data/packs/cat_lord/cat_lord_raw_20260531T142911Z/manifest.json:8-20`。

### 3. F0 边界越界点

结论：**现有 Feishu 主链路不是 F0-only；越界集中在 `orchestrator.py`、`classifier.py`、`vision_utils.py`、`summary_generator.py`、`nlm_sync.py` 和 Feishu source route。**

具体越界：

1. Vision/OCR 类处理混在 F0 sync：
   - `orchestrator.py` 导入 `VisionDescriptor/get_vision_transcript_path`：`src/finer/ingestion/orchestrator.py:23-27`。
   - `sync_chat()` 根据配置初始化 `VisionDescriptor`：`src/finer/ingestion/orchestrator.py:221-236`。
   - 对 image 调 `vision_desc.describe_image()` 并写 `Vision Analysis` transcript：`src/finer/ingestion/orchestrator.py:346-361`。
   - `VisionDescriptor.describe_image()` 实际会编码图片并调用 vision model：`src/finer/ingestion/vision_utils.py:122-155`, `src/finer/ingestion/vision_utils.py:166-220`。

2. Summary/时间抽取混在 F0 sync：
   - `orchestrator.py` 导入并初始化 `SummaryGenerator`：`src/finer/ingestion/orchestrator.py:27`, `src/finer/ingestion/orchestrator.py:238-246`。
   - `sync_chat()` 对归档文件调用 `summary_gen.generate_summary()`，写入 `summary` 和 `extracted_timestamp` metadata：`src/finer/ingestion/orchestrator.py:365-397`。
   - `SummaryGenerator.generate_summary()` 使用 LLM client 生成摘要，并用 `TimestampExtractor` 抽时间：`src/finer/services/summary_generator.py:473-560`。

3. NotebookLM 外部同步混在 F0 import：
   - `orchestrator.py` 初始化 `NLMSync`：`src/finer/ingestion/orchestrator.py:231`。
   - transcript 创建后可上传 NotebookLM：`src/finer/ingestion/orchestrator.py:270-279`。
   - attachment/vision transcript 归档后也可上传 NotebookLM：`src/finer/ingestion/orchestrator.py:399-409`。
   - `NLMSync.sync_file()` 直接执行 `nlm source add` 外部 CLI：`src/finer/ingestion/nlm_sync.py:57-93`。

4. AI 分类可触发 LLM/CLI：
   - `FileClassifier` 注释里的优先级包含 AI-assisted classification：`src/finer/ingestion/classifier.py:1-9`。
   - `_ai_classify()` 通过 Gemini CLI 做语义分类：`src/finer/ingestion/classifier.py:141-190`。
   - 当 `ai_enabled` 为真且前序规则没返回时会采用 AI 分类结果：`src/finer/ingestion/classifier.py:260-273`。
   - 当前 `configs/feishu.yaml` 打开了 `classification.ai_enabled: true`，并且开启了 vision：`configs/feishu.yaml:45-60`。

5. Feishu source route 直接调用 legacy `sync_chat()`：
   - `/api/sources/refresh` 对 Feishu 调用 `sync_chat(..., dry_run=False, auto_nlm=True)`：`src/finer/api/routes/sources.py:91-121`。
   - 因此从 UI/source refresh 触发时默认会进入上述 Vision/Summary/NLM 混合链路。

补充判断：`feishu_poller.py` 自身相对接近 F0 acquisition，但也不是完整 F0 adapter。它会解析 text/post 的 `content_text`、为附件关联邻近 text context：`src/finer/ingestion/feishu_poller.py:166-183`, `src/finer/ingestion/feishu_poller.py:269-292`。这些可作为 metadata 辅助，但不能替代 lossless raw message archive；真正 F0 应至少保存原始 lark-cli/API message JSON 或 NDJSON。

### 4. 与 card #3 路径的关系

结论：**card #3 与现有 Feishu F0 模块没有直接调用关系；它是 symlink + 手工 stopgap `ContentRecord` 的诊断路径。**

证据：

- `scripts/b1_diagnostic_run.py` 文件说明就是 stopgap：手工构造 2 条 cat_lord raw item 的 minimal `ContentRecord`，再跑 F1 及后续诊断：`scripts/b1_diagnostic_run.py:1-10`。
- `build_content_record()` 手工从 `ITEMS` 构造 `ContentRecord`，没有调用 `FeishuPoller`、`sync_chat()` 或 `/integrations/feishu`：`scripts/b1_diagnostic_run.py:81-99`。
- `create_md_symlink()` 把 `.raw` 临时转成 `.md` symlink：`scripts/b1_diagnostic_run.py:102-107`。
- `run_one()` 明确记录 symlink 是因为 router 需要 `.md` 后缀：`scripts/b1_diagnostic_run.py:121-130`。
- `StandardizationRouter` 对 `.raw`/`.md` 且 `source_type in {"feishu_chat","chat_transcript","chat_export"}` 才选择 `feishu_chat` adapter：`src/finer/parsing/standardization_router.py:42-47`, `src/finer/parsing/standardization_router.py:86-111`。
- B1 报告也显示 3/12 实际函数链是 symlink -> F1 router -> feishu_chat adapter，不是 F0 Feishu：`docs/specs/2026-06-02-b1-diagnostic-run-report.md:26-47`。

重导选择：

- **不应走 card #3 stopgap 路径重导。** 它会创建 symlink，并手工填 `published_at`，不是 F0。
- **不应直接走现有 `sync_chat()` 重导。** 它会混入 Vision/Summary/NLM，并且落盘是 manifest。
- **应新建最小干净 F0-only 路径。** 输入可以是飞书导出文件、lark-cli 导出的 raw messages JSON/NDJSON，或一段 chat window；输出只包括 raw archive、`ContentRecord`、可选 import receipt。

## AS-6b：推荐方案与改动范围

### 推荐：(b) 新建最小干净旁路

目标：**飞书导出文件/消息窗口 -> raw archive + validated `ContentRecord` + true `published_at`**。

建议形态：

1. 新增一个小的 Feishu F0-only builder/importer，例如 `src/finer/ingestion/feishu_content_record_builder.py` 或 `src/finer/ingestion/feishu_f0_importer.py`。
2. 输入只接受已导出的 Feishu raw messages / chat transcript / attachment metadata，不在该路径调用 lark-cli 重导、Vision、Summary、NLM、F1-F8。
3. 原始导出文件 byte-for-byte 归档到 `data/raw/feishu/{chat_id}/...`。
4. 每条消息或每个 chat window 生成一个 `ContentRecord`：
   - `source_platform="feishu"`
   - `source_type="feishu_chat"` 或 `chat_transcript/chat_export`
   - `published_at` 来自飞书 `create_time`；窗口级 transcript 使用首条消息时间或明确 `metadata.time_range`
   - `collected_at` 为导入登记时间
   - `raw_path` 指向 raw archive
   - `external_source_id` 为 `message_id` 或稳定 window id
   - `dedupe_fingerprint` 为 raw bytes + source id hash
   - `metadata` 保留 `chat_id`、`message_id(s)`、`sender_id(s)`、`timestamp_source="feishu_create_time"`、导出文件路径和 raw hash
5. 写入 `data/F0_intake/feishu/{chat_id}/{content_id}.json`。
6. 可选再写兼容 `ContentManifest.from_record(record)` 到 `data/processed/manifests/`，但 canonical source of truth 应是 `ContentRecord`。
7. 新增 focused tests：valid `ContentRecord`、真实 `published_at` 保留、invalid source_type 拒绝或归一化、no imports/calls to `VisionDescriptor`/`SummaryGenerator`/`NLMSync`/F1-F8。

大致改动范围：**小到中等**。

- 1 个 F0-only builder/importer 文件。
- 1 个 fixture 文件或小型 tests fixture。
- 1 个 `tests/test_feishu_f0_contract.py`。
- 如果需要 API route，优先新增 Feishu-specific route 或拆小 route；不要继续把逻辑塞进 `integrations.py`。
- 不需要改 schema，除非发现当前 `source_type` literal 无法覆盖目标导出类型。
- 不需要数据库 schema 迁移，不需要跑 pipeline。

### 为什么不优先修现有模块

修现有 Feishu F0 的最小合格范围并不小：

1. 把 `sync_chat()` 拆成 F0-only import 与后续 integration/background jobs。
2. 停止在 F0 内初始化/调用 `VisionDescriptor`、`SummaryGenerator`、`NLMSync`。
3. 禁止或隔离 AI classification，至少不能作为 F0 canonical path 的必要步骤。
4. 把 `ContentManifest` 落盘替换为 `ContentRecord` canonical 落盘。
5. 修 `published_at`，直接使用 `message.create_time`，避免 filename/date inference。
6. 补 `external_source_id`、`dedupe_fingerprint`、receipt、Line F error envelope。
7. 拆/收敛 `/api/sources/refresh` 与 `/api/integrations/*` 两条 Feishu 路径。
8. 补专属 Feishu F0 tests。

这条修复适合后续做 Feishu module cleanup，但不适合在“重新导入前先确保 raw truth 和真实发布时间”这一步承担主路径。

## 最终判断

- AS-6a：已覆盖。四点结论分别为：现有 Feishu 主产物是 `ContentManifest`/pool/raw，不是 `ContentRecord`；`published_at` 未可靠保留飞书逐条真实时间；F0 内存在 Vision/Summary/NLM/AI classification 越界；card #3 是独立 stopgap，与 Feishu F0 无直接调用关系。
- AS-6b：已覆盖。推荐新建最小干净旁路，原因是现有模块混入后续处理且修复范围大；旁路可在不重导、不跑 pipeline 的前提下为后续重导建立可信 F0 输入。

