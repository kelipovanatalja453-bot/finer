# Canonical Asset V1 契约报告

> 生成日期: 2026-05-09
> 状态: SourceType 漂移已修复

## 1. 概述

本报告审计 `contract.py`（后端 Pydantic）与 `contracts.ts`（前端 TypeScript）之间的契约一致性，并记录 AssetFile 完整字段定义、存储路径规范和已知漂移修复。

---

## 2. AssetFile 完整字段定义

| 字段 | Pydantic 类型 | TypeScript 类型 | 别名 (alias) | 必填 | 默认值 |
|------|--------------|----------------|-------------|------|--------|
| id | str | string | id | 是 | - |
| name | str | string | name | 是 | - |
| size | str | string | size | 是 | - |
| date | str | string | date | 是 | - |
| type | str | string | type | 是 | - |
| status | str | string | status | 是 | - |
| workflow_stage | WorkflowStage | WorkflowStage | workflowStage | 是 | - |
| stage_badge | str | string | stageBadge | 是 | - |
| creator_name | str | string | creatorName | 是 | - |
| source_platform | str | string | sourcePlatform | 是 | - |
| content_type | str | string | contentType | 是 | - |
| content_id | str | string | contentId | 是 | - |
| source_path | Optional[str] | string? | sourcePath | 否 | None |
| manifest_path | Optional[str] | string? | manifestPath | 否 | None |
| evidence_path | Optional[str] | string? | evidencePath | 否 | None |
| candidate_event_path | Optional[str] | string? | candidateEventPath | 否 | None |
| approved_event_path | Optional[str] | string? | approvedEventPath | 否 | None |
| summary | str | string | summary | 是 | - |
| tags | List[str] | string[] | tags | 是 | - |
| review_payload | Optional[ReviewPayload] | ReviewPayload? | reviewPayload | 否 | None |
| source_type | SourceType | SourceType | sourceType | 否 | "unknown" |
| source_group_id | Optional[str] | string? | sourceGroupId | 否 | None |
| source_group_name | Optional[str] | string? | sourceGroupName | 否 | None |
| file_timestamp | Optional[str] | string? | fileTimestamp | 否 | None |
| file_type | Optional[str] | string? | fileType | 否 | None |
| source_name | Optional[str] | string? | sourceName | 否 | None |
| semantic_title | Optional[str] | string? | semanticTitle | 否 | None |

所有字段通过 `ConfigDict(populate_by_name=True)` 支持 snake_case 和 camelCase 双向映射。

---

## 3. 枚举类型前后端对比

### 3.1 WorkflowStage

| 值 | 后端 (contract.py) | 前端 (contracts.ts) | 状态 |
|----|-------------------|--------------------|----|
| intake | OK | OK | 一致 |
| enrichment | OK | OK | 一致 |
| library | OK | OK | 一致 |
| parsing | OK | OK | 一致 |
| extraction | OK | OK | 一致 |
| review | OK | OK | 一致 |
| backtest | OK | OK | 一致 |

### 3.2 SourceType

| 值 | 后端 (contract.py) | 前端 (contracts.ts) | 状态 |
|----|-------------------|--------------------|----|
| feishu | OK | OK | 一致 |
| notebooklm | OK | OK | 一致 |
| local | OK | OK | 一致 |
| wechat | OK (已修复) | OK | 一致 |
| bilibili | OK (已修复) | OK | 一致 |
| unknown | OK | OK | 一致 |

**修复记录**: 后端 `contract.py` 原先只有 `["feishu", "notebooklm", "local", "unknown"]`，缺少 `wechat` 和 `bilibili`。已在 2026-05-09 补齐。

### 3.3 ReviewDirection

| 值 | 后端 | 前端 | 状态 |
|----|------|------|------|
| bullish | OK | OK | 一致 |
| bearish | OK | OK | 一致 |
| neutral | OK | OK | 一致 |
| watchlist | OK | OK | 一致 |
| risk_warning | OK | OK | 一致 |

### 3.4 ReviewActionStatus

| 值 | 后端 | 前端 | 状态 |
|----|------|------|------|
| draft | OK | OK | 一致 |
| active | OK | OK | 一致 |
| watch | OK | OK | 一致 |

---

## 4. 辅助类型对比

### 4.1 ReviewPayload / ReviewActionPayload

后端 `ReviewPayload` 和 `ReviewActionPayload` 通过 Pydantic `Field(alias=...)` 映射到前端 camelCase 命名。所有字段完全一致。

### 4.2 前端独有类型

以下类型仅存在于 `contracts.ts`，后端无对应 Pydantic 模型（由前端独立使用）：

- `KOL`, `KOLTimelineEvent` — KOL 评分系统
- `BacktestTask` — 回测任务
- `SourceGroup` — 来源分组（`"feishu" | "notebooklm" | "wechat" | "bilibili"`，与 SourceType 对齐）
- `DataLineage`, `VersionInfo`, `PipelineRunInfo` — 数据血缘
- `PolicyMappingResult`, `PolicyMappedIntent` 等 — F4 Policy 类型
- `TradeActionTrace`, `CanonicalTraceStatus` — F5 上游追踪
- `WeChatLoginSession`, `WeChatAccount`, `WeChatArticle` 等 — 微信集成类型

---

## 5. 存储路径使用清单

### 5.1 F-stage Canonical 目录

| 路径 | 用途 | 使用模块 | 状态 |
|------|------|---------|------|
| `data/F0_intake/` | F0 接入层写入 | `ingestion/`, `wechat.py` | canonical |
| `data/F1_standardized/` | F1 标准化输出 | `parsing/` | canonical |
| `data/F1_gold_sets/` | F1 标注数据 | 测试/标注 | canonical |
| `data/F1_validation_runs/` | F1 验证运行 | 验证工具 | canonical |

### 5.2 Legacy L-tier 目录（仍被 asset_builder 使用）

| 路径 | 用途 | 使用模块 | 状态 |
|------|------|---------|------|
| `data/L0_ingest/` | 旧 F0 接入 | `asset_builder.py` (raw_paths) | legacy，与 F0_intake 并存 |
| `data/L1_enrichment/` | 旧 F2 富化 | `files.py`, `asset_builder.py` | legacy |
| `data/L1_inbox/` | 旧收件箱 | 存在但未被代码引用 | legacy |
| `data/L2_standardized/` | 旧标准化 | 存在但未被代码引用 | legacy |
| `data/L3_aligned/` | 旧对齐层 | `asset_builder.py` (evidence/candidate/approved paths) | legacy |
| `data/L4_parsed/` | 旧解析层 | `asset_builder.py` (candidate_paths) | legacy |
| `data/L5_candidate/` | 旧候选事件 | 存在但未被代码引用 | legacy |
| `data/L6_annotated/` | 旧标注层 | `asset_builder.py` (approved_paths) | legacy |
| `data/L7_model_results/` | 旧模型结果 | 存在但未被代码引用 | legacy |
| `data/L8_metrics/` | 旧指标 | `asset_builder.py` (backtest_paths) | legacy |

### 5.3 通用目录

| 路径 | 用途 | 使用模块 | 状态 |
|------|------|---------|------|
| `data/raw/` | 原始文件，按 creator 组织 | `asset_builder.py`, `paths.py` | canonical |
| `data/raw/_inbox/unclassified/` | 上传文件暂存 | `files.py` (upload) | canonical |
| `data/raw/wechat/` | 微信文章 | `wechat.py` | canonical |
| `data/raw/bilibili/video\|audio\|subtitle/` | B站资源 | `bilibili.py`, `paths.py` | canonical |
| `data/processed/manifests/` | ContentManifest | `files_utils.py` | canonical |
| `data/processed/documents/` | 文档证据 | `asset_builder.py` | canonical |
| `data/processed/transcripts/` | 转录文本 | `asset_builder.py` | canonical |
| `data/processed/candidate_events/` | 候选事件 | `asset_builder.py` | canonical |
| `data/processed/review_store/` | 审核存储 | `asset_builder.py` | canonical |
| `data/processed/approved_events/` | 已批准事件 | `asset_builder.py` | canonical |
| `data/backtests/` | 回测结果 | `asset_builder.py` | canonical |
| `data/cache/` | 应用缓存 | 多模块 | canonical |
| `data/feishu_sync_pool/` | 飞书同步池 | `files_utils.py` (source detection) | canonical |
| `data/nlm_sync_pool/` | NLM 同步池 | `files_utils.py` (source detection) | canonical |
| `data/inbox/` | 飞书下载暂存 | `paths.py` | canonical |
| `data/rlhf/` | RLHF 反馈 | `api/routes/rlhf.py` | canonical |

### 5.4 路径混用风险

`asset_builder.py` 同时扫描 legacy L-tier 和 canonical 目录，用于向后兼容：
- evidence_paths: `processed/documents`, `processed/transcripts`, `L3_aligned/documents`, `L3_aligned/transcripts`, `L3_aligned/blocks_md`
- candidate_paths: `processed/review_store`, `processed/candidate_events`, `L4_parsed/candidate_events`, `L3_aligned/candidate_events`
- approved_paths: `processed/approved_events`, `L3_aligned/approved_events`, `L6_annotated`

这种双轨扫描是 intentional backward compat，但增加了文件重复匹配风险（同一 content_id 可能在 canonical 和 legacy 目录中各有一份）。

---

## 6. source_type 赋值逻辑审计

`files_utils.py:extract_source_info()` 中的 source_type 赋值链：

1. manifest 中有 `feishu_chat_id` 或 `source_platform == "feishu"` -> `"feishu"`
2. manifest 中有 `nlm_notebook_id` 或 `source_platform == "notebooklm"` -> `"notebooklm"`
3. source_path 包含 `feishu_sync_pool` -> `"feishu"`
4. source_path 包含 `nlm_sync_pool` -> `"notebooklm"`
5. `source_platform == "wechat"` -> `"wechat"`
6. `source_platform == "bilibili"` -> `"bilibili"`
7. 其他情况 -> `"local"`

**已实现**: `extract_source_info()` 支持 `source_platform == "wechat"` -> `"wechat"` 和 `source_platform == "bilibili"` -> `"bilibili"` 分支（`files_utils.py:503-509`）。

---

## 7. _build_source_summary 漂移修复

`files_utils.py:_build_source_summary()` 中的 `source_counts` 字典原先硬编码为 `{"feishu": 0, "notebooklm": 0, "local": 0, "unknown": 0}`，不包含 `wechat` 和 `bilibili`。

已修复为 `{"feishu": 0, "notebooklm": 0, "local": 0, "wechat": 0, "bilibili": 0, "unknown": 0}`。

---

## 8. 已知漂移及修复状态

| 漂移项 | 位置 | 修复状态 |
|--------|------|---------|
| SourceType 缺少 wechat, bilibili | `contract.py:8` | 已修复 |
| source_counts 缺少 wechat, bilibili | `files_utils.py:544` | 已修复 |
| extract_source_info 不产出 wechat/bilibili | `files_utils.py:503-509` | 已修复 |
| L-tier 目录仍被 asset_builder 扫描 | `asset_builder.py:247-274` | Intentional backward compat |

---

## 9. 验证结果

```
pytest tests/test_schemas.py -v
60 passed, 6 warnings in 0.19s

npx tsc --noEmit contracts.ts
(无输出，编译通过)
```
