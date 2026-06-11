# F0 Adapter 进展审阅报告

> 日期：2026-05-31  
> 审阅范围：F0 Intake 合约、Project Memory / Import Console 查询层、本地上传、飞书、NotebookLM、微信公众号、微信视频号、B 站 / BBDown 相关 adapter 与测试。  
> 审阅方式：只读代码扫描 + targeted regression tests。未修改 adapter 代码、配置、数据、schema 或 CI。

## 结论

当前 F0 adapter 不是一个统一完成态，而是三类状态并存：

1. **微信视频号链路最接近 canonical F0**：已做到 raw profile/video、`ContentRecord`、receipt、idempotent import、route error mapping 和测试闭环。
2. **微信公众号和 B 站已有可用链路，但仍是 beta/legacy 混合态**：能产出 `ContentRecord` 或 manifest，但 receipt、raw artifact 语义、Project Memory 增量更新和 F0-only 边界还不完整。
3. **飞书、本地上传、NotebookLM 仍未达到 A2/A0 约定的完整 F0 adapter 标准**：飞书旧 orchestrator 会做视觉描述、摘要、NLM 同步；本地上传只落 raw 文件；NotebookLM intake 使用 `nlm_source` manifest，未产出 canonical `ContentRecord`。

架构主风险不是测试红，而是 **F0 边界和持久化契约不统一**：有的渠道写 `ContentRecord` JSON，有的只写 `ContentManifest` 到 `data/processed/manifests/`，有的只有 raw 文件；只有微信视频号写入独立 import receipt。后续若直接接 F1 / Import Console，会出现查询、去重、回溯和失败恢复口径不一致。

## 审阅基准

F0 权威边界来自：

- `AGENTS.md`：F0 核心 schema 是 `ContentRecord`，`ingestion/` 是 F0 owning area。
- `docs/specs/f-stage-contracts.md`：F0 只做多源接入和原始归档，不做 OCR/ASR/文本解析/LLM/质量判断。
- `docs/specs/2026-05-parallel-agent-execution.md`：F0 输出仅限 `ContentRecord`、raw archive、import receipt/run status、F0 local project memory index；渠道 adapter 不能调用 F1-F8 逻辑。
- `docs/agent-prompts/2026-05-a2-f0-wechat-bilibili.md`：WeChat/Bilibili A2 的验收目标是 raw artifact + valid `ContentRecord` + dedupe/source metadata + Line F error details + no F1-F8 invocation。

## 总览矩阵

| 模块 / 渠道 | 当前成熟度 | 已完成 | 主要缺口 | 审阅判断 |
|---|---:|---|---|---|
| F0-Core `ContentRecord` | beta | Pydantic schema、manifest mirror、schema/route tests | source taxonomy 不覆盖微信视频号；`collected_at` 仍用 naive `datetime.utcnow` | 可作为共享基线，但需要一次小型 contract 收口 |
| F0 Project Memory / Index | beta | index schema contract、health/records/import-runs/rebuild API、catalog-first files query | adapter 导入后未统一更新 index；存在 schema contract 与实际 Project Memory `asset_index` 的双口径 | 查询层可用，写入链路未统一 |
| Local upload | alpha | 文件上传到 `data/raw/_inbox/unclassified`，返回 F0 badge，files API 支持 catalog-first | 不创建 `ContentRecord` / manifest / receipt / dedupe；只清内存 cache | 只能算 raw inbox，不是完整 F0 adapter |
| Feishu | beta/legacy | lark-cli polling、附件下载、聊天 transcript、manifest、receipt 通知、source routes | 不产出 `ContentRecord` JSON；会做 Vision / Summary / NLM；dedupe 缺失；route 仍有 `HTTPException` | 可用但混入 F1/LLM 行为，需要拆边界 |
| NotebookLM intake | placeholder/alpha | 可通过 CLI 拉 source content 到 pool，并写 manifest | `source_type="nlm_source"` 不在 `ContentRecord` literal；没有 `nlm_note` `ContentRecord`；缺 tests；更多是 Feishu 的外部同步工具 | 尚不是 canonical F0 adapter |
| WeChat official account | beta | exporter client、artifact store、incremental sync、`ContentRecord` builder、route/tests | 只保存 markdown，HTML 为空；无 receipt JSON；未写 Project Memory；部分 legacy adapter 与新 exporter 并存 | 可接 F1，但要补 raw/receipt/index |
| WeChat Channels | beta+ | profile/video raw、`ContentRecord`、receipt、idempotency、route、error mapping、tests | `source_type="unclassified"` + metadata workaround；hardcoded vendored binary；依赖目录有许可/安全风险 | 当前最规范的 F0 adapter |
| Bilibili classic adapter | alpha/beta | video info、audio download、Paraformer transcript、`/sync` 写 `ContentRecord` 和 manifest、tests | ASR/transcribe 在 F0；sync 依赖先有 transcript；无 receipt；raw video/audio/subtitle 没形成统一 artifact set | 结果可用但 F0 边界不合格 |
| Bilibili BBDown adapter | alpha | BBDown CLI info/audio/subtitle、subtitle 优先、tests | convenience function 显式 import F1 parsing ASR；无 `ContentRecord`/route/F0_intake 写入 | 下载工具层，不是完整 adapter |

## 关键发现

### P1 - Bilibili 和 Feishu 仍在 F0 内执行 F1/LLM 类职责

`docs/specs/f-stage-contracts.md` 明确 F0 不做 OCR/ASR/文本解析和 LLM 调用。当前：

- `src/finer/ingestion/bilibili_adapter.py` 把 Paraformer ASR 放在 F0 ingestion adapter 内，`BilibiliAdapter.transcribe()` 会下载音频并调用 transcriber。
- `src/finer/api/routes/bilibili.py` 将 `/api/bilibili/transcribe/{bvid}` 标为 F0 route，并执行转录。
- `src/finer/ingestion/bbdown_client.py` 的 `transcribe_bilibili_video()` 从 `finer.parsing.mimo_asr_client` import F1 parsing ASR。
- `src/finer/ingestion/orchestrator.py` 在 Feishu sync 中创建 `VisionDescriptor`、调用 `describe_image()`，并初始化 `SummaryGenerator` 生成摘要。

这不是当前测试能发现的问题，因为 tests 主要验证 route/schema 不报错。架构上应把这些能力拆成：F0 只下载 raw video/audio/subtitle/image/chat raw；F1/F1.5 之后再转录、OCR、摘要或标准化。

### P1 - F0 持久化形态不统一，导致后续 Import Console / F1 routing 难以稳定消费

现状存在三套落盘口径：

- 微信视频号：`data/raw/wechat/channels/...` + `data/F0_intake/wechat/channels/.../{content_id}.json` + `.receipt.json`。
- 微信公众号 / B 站：部分写 `data/F0_intake/.../{content_id}.json`，同时或另外写 `ContentManifest` 到 `data/processed/manifests/`。
- 飞书 / NotebookLM / 本地上传：主要是 raw 文件、pool 文件或 `ContentManifest`，没有统一 `ContentRecord` JSON 和 receipt。

`ContentManifest` 现在是 `ContentRecord` 的 dataclass mirror，但写入位置仍是 `data/processed/manifests/`。如果 F0 的真实输出是 `ContentRecord + raw archive + receipt`，则所有 adapter 应收敛到同一落点：`data/raw/{channel}/...`、`data/F0_intake/{channel}/.../{content_id}.json`、`{content_id}.receipt.json`，再异步/增量更新 Project Memory。

### P1 - `scripts/wx_channels_download/` 依赖仍是发布风险

`docs/specs/2026-05-wx-channels-dependency-policy.md` 已记录该目录包含 Commons Clause + MIT、GPLv3 fork、MITM root CA、RSA private key 等高风险点，并建议 External Install。当前代码仍在：

- `WeChatChannelsDownloadClient` 默认依赖 `scripts/wx_channels_download/wx_video_download`。
- `/api/wechat/channels/import` route 也硬编码同一路径。

该目录当前是 untracked，且删除目录属于用户红线，不能自动处理。下一步应该在用户确认后走 External Install：配置/PATH 查找 binary，保留清晰安装说明，避免把 vendored code 或 binary 带进发布物。

### P2 - Local upload 只完成 raw inbox，没有完成 `ContentRecord`

`POST /api/files` 只把上传文件写到 `data/raw/_inbox/unclassified`，返回 `stageBadge="F0"`，未创建 `ContentRecord`、dedupe fingerprint、external/source metadata、receipt，也不会更新 F0 index。

这意味着本地上传目前只能作为“临时 raw dropbox”，不能作为完整 canonical F0 importer。若用户上传本地研报、截图或手工文本，F1 很难可靠回溯到标准 `source_record_id`。

### P2 - NotebookLM intake 使用的 `source_type` 与 schema 不一致

`src/finer/api/routes/integrations.py` 的 `/nlm/fetch` 创建 `ContentManifest(source_type="nlm_source")`，而 `ContentRecord.source_type` literal 中对应的是 `nlm_note`。这会导致 NLM source 不能无损升级成 `ContentRecord`，也不能通过当前 `tests/test_f0_contract.py` 的 literal 约束。

NotebookLM 现有模块 `src/finer/ingestion/nlm_sync.py` 实际更像“把 Feishu/raw 文件上传到 NotebookLM”的外部同步工具，不是 NotebookLM 作为来源的 F0 intake adapter。

### P2 - Official WeChat article raw artifact 仍不够“原始”

微信公众号链路有 `WeChatArtifactStore` 和 `build_content_record()`，但 route 当前调用 exporter 只拿 markdown，并以 `html=b""` 保存。`ContentRecord.raw_path` 指向 markdown。作为 F0 最小链路可以接受，但如果严格按“原始证据优先”，应补保存 exporter 原始响应、HTML 或可复现的 export receipt。

### P2 - Import receipt 只有微信视频号做到结构化落盘

`src/finer/ingestion/receipt.py` 是飞书群消息通知，不是通用 F0 import receipt。当前只有微信视频号有 `{content_id}.receipt.json`，包含 stage、source_channel、source_kind、status、dedupe、raw hashes。

其它渠道至少应补一个统一 receipt builder，避免每个 adapter 自己返回不同状态结构。

### P3 - 时间字段仍有 timezone consistency 问题

测试通过，但回归输出中有 `datetime.utcnow()` deprecation warnings。`ContentRecord.collected_at` 默认仍是 naive UTC。F0 是审计链起点，时间字段最好统一 timezone-aware UTC，尤其是跨平台来源发布时间、采集时间和 import run 时间。

## 分模块进展

### 1. F0-Core

已完成：

- `src/finer/schemas/content.py` 定义 canonical `ContentRecord`，包含 identity、source classification、creator、timestamps、raw path、file type、metadata、source url、external source id、dedupe fingerprint。
- `src/finer/manifests.py` 提供 `ContentManifest.from_record()` 和 legacy key 兼容。
- `tests/test_f0_contract.py` 覆盖 required fields、source/file type literal、serialization、manifest conversion 和 `/api/files` 基础 F0 response。

缺口：

- `wechat_channels_video` 未进入 `source_type` literal，只能用 `unclassified + metadata.source_kind`。
- `ContentManifest` 仍写 `data/processed/manifests/`，容易和 F0 output location 混淆。
- timezone-aware UTC 尚未统一。

建议：

1. 先做小型 A0 contract patch：新增 `wechat_channels_video` 或明确所有 video source 用 `unclassified + source_kind` 的长期规则。
2. 定义统一 `F0ImportReceipt` dataclass / pydantic model。
3. 明确 `ContentRecord` JSON 的 canonical 落点，manifest 只作兼容投影。

### 2. F0 Project Memory / Import Console 查询层

已完成：

- `src/finer/schemas/f0_index.py` 有 index schema/query/health contract。
- `src/finer/api/routes/f0_index.py` 提供 `/api/f0-index/records`、`/import-runs`、`/health`、`/rebuild`。
- `src/finer/api/routes/files.py` 支持 catalog-first query，Project Memory 不可用时 fallback 到 filesystem scan。
- `tests/test_f0_project_memory.py` 与 `tests/test_files_api_catalog.py` 覆盖 health、records、import runs 和 catalog fallback。

缺口：

- 各 channel adapter 完成 import 后未统一写入 Project Memory / `asset_index`。
- `/api/f0-index/records` 直接查 `asset_index WHERE stage='F0'`，而 `F0IndexSchema` 定义的是 `content_records/import_runs/index_metadata`，两者还没完全收敛。
- `files_utils.collect_files_from_directories()` fallback 仍会 `os.walk`，只是降级路径，不是启动默认路径。

建议：

1. 保持 SQLite schema 变更红线：新增/迁移表前单独确认。
2. 先定义 adapter import 后的 index update interface，不急着改 DB schema。
3. Import Console 默认只读 health/index；full scan 必须显式 rebuild 或后台任务。

### 3. Local upload

已完成：

- `POST /api/files` 可上传文件到 `data/raw/_inbox/unclassified`。
- 返回 `contract="canonical_asset_v1"`、`workflow="intake"`、`stageBadge="F0"`。
- `tests/test_f0_contract.py` 覆盖上传 response 中的 F0 字段。

缺口：

- 没有 `ContentRecord`。
- 没有 receipt。
- 没有 dedupe。
- 没有 `data/F0_intake/local/...`。
- 没有 Project Memory 增量更新。

建议：

把本地上传拆成两步：

1. `upload`：只收 raw file 到 staging inbox。
2. `register/import`：生成 `ContentRecord`、receipt、dedupe，并更新 F0 index。

### 4. Feishu

已完成：

- `FeishuPoller` 能用 lark-cli 拉消息、分页、下载附件、维护 `SyncState`。
- `sync_chat()` 会生成聊天 transcript，并通过 `ContentManifest` 记录 chat transcript 和附件 raw path。
- `ReceiptSender` 能发送飞书同步结果通知。
- `/api/integrations/feishu/fetch` 能把消息和附件拉到 sync pool。

缺口：

- 主链路创建的是 `ContentManifest`，不是 `ContentRecord` JSON。
- `dedupe_fingerprint=None`、`external_source_id=None` 的情况较多，回溯粒度不够。
- `sync_chat()` 中混入 Vision / Summary / NLM sync，违反 F0-only。
- `src/finer/api/routes/sources.py` 仍用 `HTTPException`，不是统一 FinerError envelope。
- 缺少 Feishu F0 adapter 专属 tests；现有覆盖更多在 F1 standardizer / files catalog。

建议：

1. 把 `sync_chat()` 拆成 F0-only `feishu_import_chat_window()`，只输出 raw transcript/attachments + `ContentRecord` + receipt。
2. Vision、summary、NLM sync 移到后续 stage 或 background integration，不在 F0 import path 内执行。
3. 为 Feishu 加 `tests/test_feishu_f0_contract.py`：raw archive、ContentRecord、receipt、dedupe、error envelope、no F1/F8 imports。

### 5. NotebookLM

已完成：

- `NLMSync` 可把本地文件上传到 NotebookLM。
- `/api/integrations/nlm/fetch` 可调用 `nlm source list/content` 拉取 notebook source，写入 `data/nlm_sync_pool` 并创建 manifest。

缺口：

- 这不是独立 canonical F0 adapter；更多是 Feishu workflow 的外部同步和一个 pool import。
- `/nlm/fetch` 使用 `source_type="nlm_source"`，与 `ContentRecord` literal `nlm_note` 不一致。
- 没有 `ContentRecord`、receipt、dedupe。
- 缺少 NotebookLM F0 tests。

建议：

1. 明确 NotebookLM source 的 canonical source_type：推荐 `nlm_note`。
2. 增加 `NotebookLMF0Importer`，统一输出 `data/raw/notebooklm/{notebook_id}/...` 和 `data/F0_intake/notebooklm/{notebook_id}/...`。
3. 保留 `NLMSync` 作为“向 NotebookLM 上传”的工具，不和 “NotebookLM 作为 F0 来源”混名。

### 6. WeChat official account

已完成：

- `WeChatExporterClient` 封装 exporter service，支持 login/session、account search、article list/export。
- `WeChatArtifactStore` 写 `data/raw/wechat/{account_id}/{article_id}.md`、sidecar 和 incremental sync state。
- `build_content_record()` 生成稳定 `content_id`、`source_type="wechat_article"`、source url、external source id、dedupe、raw hashes。
- `/api/wechat/sync/{account_id}` 能保存 raw markdown 和 `data/F0_intake/wechat/{account_id}/{content_id}.json`。
- `tests/test_wechat_artifact_store.py`、`tests/test_wechat_content_record.py`、`tests/test_wechat_api_routes.py`、`tests/test_wechat_f0_contract.py` 覆盖较完整。

缺口：

- article route 没有写 import receipt JSON。
- `html=b""`，raw HTML 不可用；F0 raw evidence 目前主要是 exporter markdown。
- 未更新 Project Memory index/import_runs。
- 老 `WeChatAdapter` 和新 exporter flow 并存，维护边界略复杂。

建议：

1. 补 official account receipt，沿用 WeChat Channels receipt 字段。
2. 保存 exporter raw response 或 HTML 快照；如果只能拿 markdown，receipt 中明确 `raw_artifact_kind=exporter_markdown`。
3. 将老 `WeChatAdapter` 标注 legacy，后续 route 优先走 exporter-backed F0 path。

### 7. WeChat Channels

已完成：

- `WeChatChannelsDownloadClient` 读取 downloader service profile JSON，可选调用 CLI 下载视频。
- `WeChatChannelsF0Importer` 写 raw profile/video、`ContentRecord`、receipt，并支持 idempotent import。
- `ContentRecord` 保留 creator、published_at、source_url、external_source_id、dedupe、raw sha256、media metadata。
- `/api/wechat/channels/import` 有 F0-only route 和 `F0_IN_001/F0_EXT_001/F0_EXT_002/F0_IO_001/F0_TMO_001/F0_INT_001` 映射。
- `tests/test_wechat_channels_f0.py` 覆盖 artifact write、idempotency、route success 和 input error。

缺口：

- `source_type="unclassified"` 是 contract workaround。
- downloader binary 路径硬编码到 `scripts/wx_channels_download/wx_video_download`。
- `scripts/wx_channels_download/` vendored 依赖存在许可、安全、发布风险；当前仍是 untracked。
- 未写 Project Memory index/import_runs。

建议：

1. 先处理 dependency policy：改为 external binary config/PATH 查找。
2. 再决定是否新增 `wechat_channels_video` source_type literal。
3. 把 receipt builder 泛化为通用 F0 receipt helper。

### 8. Bilibili classic adapter

已完成：

- `BilibiliClient` 支持 BV parse、video info、audio url/download。
- `BilibiliAdapter` 支持 audio download、Paraformer transcription、transcript/metadata 保存。
- `/api/bilibili/sync/{bvid}` 可从已有 transcript 生成 `ContentRecord`，写 `data/F0_intake/bilibili/{uploader_id}/{content_id}.json`，并通过 `ContentManifest.from_record()` 写兼容 manifest。
- `tests/test_bilibili.py` 和 `tests/test_bilibili_f0_contract.py` 覆盖 metadata、response naming、search stub、error envelope basics。

缺口：

- F0 adapter 内部直接转录，属于 ASR/F1 职责。
- `/sync` 依赖先跑 `/transcribe`，所以 F0 output 实际是 transcript，不是 raw video/audio/subtitle artifact set。
- 没有 receipt JSON。
- 没有 artifact hash、raw audio/video/subtitle path、import run 状态。
- `search_videos()` 仍是 stub。

建议：

1. 将 Bilibili F0 拆为 `download_raw_artifacts()`：video metadata、audio/video/subtitle raw 文件、source JSON。
2. `transcribe` 改为 F1/F1-adjacent processing endpoint，不作为 F0 acceptance 条件。
3. `/sync` 改名或重写为 `/import`，直接从 raw artifact set 生成 `ContentRecord` + receipt。

### 9. Bilibili BBDown adapter

已完成：

- `BBDownAdapter` 能从 CLI 输出解析视频信息、下载 audio、下载/解析 CC subtitle。
- subtitle 优先于 ASR 的行为有测试覆盖。
- `tests/test_bbdown_cli_adapter.py` 已通过。

缺口：

- 它没有写 `ContentRecord`、`data/F0_intake` 或 receipt。
- convenience function `transcribe_bilibili_video()` 从 `finer.parsing.mimo_asr_client` import ASR，显式跨入 F1 parsing。
- 没有 route 接到 canonical F0 import。

建议：

保留 BBDown 作为 Bilibili raw artifact acquisition backend，但不要让它直接承担 F0 adapter 完整职责。真正的 Bilibili F0 adapter 应在 route/service 层把 BBDown 输出包装成 `ContentRecord + receipt + index update`。

## 测试与扫描结果

已运行：

```bash
pytest tests/test_f0_contract.py tests/test_f0_project_memory.py tests/test_files_api_catalog.py tests/test_wechat_artifact_store.py tests/test_wechat_content_record.py tests/test_wechat_api_routes.py tests/test_wechat_f0_contract.py tests/test_wechat_channels_f0.py tests/test_bilibili.py tests/test_bilibili_f0_contract.py -q
```

结果：

```text
126 passed, 32 warnings in 2.75s
```

已运行：

```bash
pytest tests/test_bbdown_cli_adapter.py -q
```

结果：

```text
15 passed, 6 warnings in 0.36s
```

边界扫描：

```bash
rg -n "from finer\.(parsing|enrichment|extraction|policy|backtest)|import finer\.(parsing|enrichment|extraction|policy|backtest)|TradeAction|Backtest|ContentEnvelope|TopicBlock|EvidenceSpan|NormalizedInvestmentIntent|PolicyMappingResult" \
  src/finer/api/routes/wechat.py \
  src/finer/ingestion/wechat_adapter.py \
  src/finer/ingestion/wechat_exporter_client.py \
  src/finer/api/routes/bilibili.py \
  src/finer/ingestion/bilibili_adapter.py \
  src/finer/ingestion/bbdown_client.py \
  src/finer/ingestion/feishu_poller.py \
  src/finer/ingestion/orchestrator.py \
  src/finer/api/routes/integrations.py \
  src/finer/api/routes/files.py \
  src/finer/ingestion/nlm_sync.py
```

结果：

```text
src/finer/ingestion/bbdown_client.py:846:    from finer.parsing.mimo_asr_client import MiMoASRClient
```

语义边界扫描还发现 Bilibili ASR、Feishu vision/summary 虽未显式 import F1-F8 business modules，但实际职责已经越过 F0。

## 建议收口顺序

1. **先做 F0 receipt + ContentRecord 落点统一**  
   目标：所有 adapter 至少产出 `data/F0_intake/{channel}/.../{content_id}.json` 和 `{content_id}.receipt.json`。

2. **处理微信视频号 external dependency**  
   目标：移除硬编码 vendored binary；改为 config/PATH 查找。删除 vendored 目录需要用户单独确认。

3. **拆 Bilibili / Feishu 的 F1/LLM 行为**  
   目标：F0 只拿 raw artifact；ASR/OCR/summary 转到 F1 或 background processing。

4. **补 Local upload / NotebookLM 的真正 importer**  
   目标：本地文件和 NotebookLM note 都能生成 `ContentRecord`、receipt、dedupe。

5. **最后接 Project Memory 增量更新**  
   目标：adapter import 成功后写入 index/import_runs；Import Console 不再依赖 fallback scan。

## 建议下一批任务卡

### A0-small: F0 receipt and source taxonomy

- Owner：F0-Core
- 改动范围：`schemas/content.py`、新增 `ingestion/f0_receipt.py` 或等价 helper、F0 tests
- 产出：统一 receipt model；明确 `wechat_channels_video` 处理策略
- 验收：所有现有 F0 tests 通过，微信视频号不再需要散落的私有 receipt builder

### A2-local-nlm: Local upload and NotebookLM canonical import

- Owner：F0-Channel
- 改动范围：`api/routes/files.py`、`ingestion/nlm_sync.py` 或新增 `notebooklm_adapter.py`、tests
- 产出：local / NotebookLM `ContentRecord + receipt + dedupe`
- 验收：上传和 NLM fetch 均有 `data/F0_intake/...` 记录

### A2-bilibili-boundary: Bilibili raw acquisition split

- Owner：F0-Channel Bilibili
- 改动范围：`bilibili_adapter.py`、`bbdown_client.py`、`api/routes/bilibili.py`、tests
- 产出：raw video/audio/subtitle artifact set + `ContentRecord + receipt`
- 禁止：在 F0 route 内调用 ASR/transcribe

### A2-feishu-boundary: Feishu F0-only importer

- Owner：F0-Channel Feishu
- 改动范围：`feishu_poller.py`、`orchestrator.py` 或新增 `feishu_adapter.py`、route tests
- 产出：chat transcript/attachments raw archive + `ContentRecord + receipt`
- 禁止：Vision、Summary、NLM sync 在 F0 import path 内执行

## 附：当前工作区注意事项

审阅时 `git status --short` 显示当前仓库已有多处非本报告引起的修改和 untracked 文件，包括 `CLAUDE.md`、F3/F5/pipeline 相关文件、若干 tests、`docs/research/`、`docs/specs/2026-05-wx-channels-dependency-policy.md`、`scripts/wx_channels_download/` 等。本报告只新增本文件，不回退、不清理、不移动现有文件。
