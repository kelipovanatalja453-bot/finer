# Finer OS — V0/V0.5/V1 Schema 契约验收报告

> 生成时间: 2026-04-28 | 验收状态: **PARTIAL**

---

## 1. 总览

| 维度 | 结果 |
|------|------|
| 验收状态 | **PARTIAL** |
| 核心测试 | 115/115 通过 |
| Fixture 契约测试 | 27/27 通过 |
| V0 流程验证 | ✓ 加载 + 往返 + 引用一致性 |
| V1 流程验证 | ✓ 加载 + 往返 + 引用一致性 |
| V0-V1 跨层一致性 | ✓ envelope_id / block_ids / evidence_span_ids |
| 图片策略 fixture | **未完成** — 当前 fixture 为飞书文档会话记录，非图片 OCR fixture |
| 真实 V0→V1 生成链路 | **未验证** — golden case 为人工构造，非自动生成 |
| 进入 V2 Policy Mapping | **否** — 需先完成真实生成链路验证 |

---

## 2. Agent 执行记录

### 2.1 Agent A — 修正执行报告验收口径

| 项目 | 详情 |
|------|------|
| 状态 | ✓ 完成 |
| 操作 | 将执行报告从 PASS → PARTIAL，记录阻塞问题 |
| 引用 | `docs/multi-agent-execution-report.md` |

### 2.2 Agent B — 补齐 schema_version 字段

| 项目 | 详情 |
|------|------|
| 状态 | ✓ 完成 |
| 操作 | 为 4 个 schema 模型添加 `schema_version` 字段 |

**变更清单**：

| Schema 模型 | 文件路径 | schema_version 默认值 |
|-------------|---------|---------------------|
| `QualityCard` | `src/finer/schemas/quality.py` | `"v0.5"` |
| `TemporalAnchor` | `src/finer/schemas/temporal.py` | `"v0.5"` |
| `EvidenceSpan` | `src/finer/schemas/evidence.py` | `"v0.5"` |
| `EntityAnchor` | `src/finer/schemas/entity_anchor.py` | `"v0.5"` |

字段定义格式统一为：

```python
schema_version: str = Field(
    default="v0.5",
    description="Schema version for backward compatibility"
)
```

### 2.3 Agent C — 创建猫大人真实 fixture

| 项目 | 详情 |
|------|------|
| 状态 | ✓ 完成（经修复） |
| 操作 | 从飞书文档提取猫大人FIRE投资策略，创建 Markdown + V0 + V1 fixture |
| 说明 | 当前 fixture 是 **source_type=chat** 的飞书文档会话记录，不是图片策略 OCR fixture |

**Fixture 文件清单**：

| 文件 | 路径 | 行数 | 说明 |
|------|------|------|------|
| Markdown 原文 | `tests/fixtures/kol/cat_lord_strategy_2026_03_12.md` | 66 | 猫大人FIRE 5 段投资分析 |
| V0 golden case | `tests/fixtures/kol/cat_lord_strategy_2026_03_12.expected_v0.json` | 514 | ContentEnvelope (8 blocks) |
| V1 golden case | `tests/fixtures/kol/cat_lord_strategy_2026_03_12.expected_v1.json` | 219 | NormalizedInvestmentIntent (6 intents) |

**修复记录**（Agent C 初始创建后发现的 4 个问题）：

| # | 问题 | 修复 | 引用位置 |
|---|------|------|---------|
| 1 | JSON 中未转义的双引号 `"东数西算"` | → `\"东数西算\"` | V0 JSON line 202 |
| 2 | `resolution_strategy` 无效值 `fiscal_quarter_inference` | → `fiscal_period` | V0 JSON temporal_anchors[1] |
| 3 | `resolution_strategy` 无效值 `explicit_date_range` | → `explicit_date` | V0 JSON temporal_anchors[2] |
| 4 | `entity_anchors` 字段名与 schema 不匹配 | `entity_name` → `raw_text`/`resolved_name`；`entity_symbol` → `resolved_symbol`；`mentioned_in_blocks` → `metadata.mentioned_in_blocks` | V0 JSON entity_anchors 全部 |
| 5 | Block order 从 1-8 而非 0-7 | → 0-7 | V0 JSON blocks 全部 |

### 2.4 Agent D — 加强图片策略 block 合约

| 项目 | 详情 |
|------|------|
| 状态 | ✓ 完成 |
| 操作 | 在 BLOCK_TYPE_LITERAL 和 content_standardizer 中增加 placeholder block 类型 |

**变更清单**：

| 变更 | 文件路径 | 详情 |
|------|---------|------|
| 新增 block 类型 | `src/finer/schemas/content_envelope.py:34-48` | `table_region`, `chart_region`, `ocr_unreadable` |
| Placeholder 检测 | `src/finer/parsing/content_standardizer.py:64-69` | 4 种 placeholder pattern（中/英文） |
| Quality card 默认值 | `src/finer/parsing/content_standardizer.py:153-169` | 每种 placeholder 类型的差异化评分 |

新增的 `BLOCK_TYPE_LITERAL` 完整成员：

```
paragraph, heading, table, chart, image_region,
chat_message, transcript_segment, list, unknown,
table_region, chart_region, ocr_unreadable
```

Placeholder 检测模式：

| 类型 | 英文标记 | 中文标记 |
|------|---------|---------|
| `table_region` | `[TABLE_REGION]` | `[表格区域]` |
| `chart_region` | `[CHART_REGION]` | `[图表区域]` |
| `image_region` | `[IMAGE_REGION]` | `[图片区域]` |
| `ocr_unreadable` | `[OCR_UNREADABLE]` | `[无法识别]` |

### 2.5 Agent E — 验证 V0 流程

| 项目 | 详情 |
|------|------|
| 状态 | ✓ 完成 |
| 操作 | fixture → ContentEnvelope.from_dict() 加载验证 |

**验证结果**：

| 检查项 | 结果 |
|--------|------|
| ContentEnvelope 加载 | ✓ |
| envelope_id = `cat_lord_2026_03_12_feishu_doc` | ✓ |
| schema_version = `v0.1` | ✓（需修正为 v0.5） |
| source_type = `chat` | ✓ |
| creator_name = `猫大人FIRE` | ✓ |
| published_at 解析 | ✓ `2026-03-12 15:36:00+08:00` |
| Blocks 数量 = 8 | ✓ |
| Block types = {heading, list, paragraph} | ✓ |
| Block order 0-7 | ✓ |
| Quality card overall_score = 0.85 | ✓ |
| Quality card gate_status = `pass` | ✓ |
| Evidence spans 总数 = 12 | ✓ |
| Evidence span block_id 引用全部有效 | ✓ |
| Temporal anchors 数量 = 3 | ✓ |
| Entity anchors 数量 = 6 | ✓ |
| 序列化/反序列化往返 | ✓ |

### 2.6 Agent F — 验证 V1 流程

| 项目 | 详情 |
|------|------|
| 状态 | ✓ 完成 |
| 操作 | fixture → NormalizedInvestmentIntent.model_validate() 加载验证 |

**验证结果**：

| 检查项 | 结果 |
|--------|------|
| 6 个 intents 加载 | ✓ |
| direction 值范围 {bullish, bearish} | ✓ |
| actionability 值范围 {opinion, watch, explicit_action} | ✓ |
| conviction 范围 0.0-1.0 | ✓ |
| confidence 范围 0.0-1.0 | ✓ |
| evidence_span_ids 全部存在于 V0 | ✓ |
| 序列化/反序列化往返 | ✓ |

**Intent 详情**：

| intent_id | target_type | target_name | direction | actionability | conviction | confidence |
|-----------|-------------|-------------|-----------|---------------|------------|------------|
| intent_001 | stock | 理想汽车 | bearish | opinion | 0.75 | 0.85 |
| intent_002 | stock | 宝丰能源 | bullish | watch | 0.70 | 0.82 |
| intent_003 | sector | 绿电 | bullish | opinion | 0.65 | 0.78 |
| intent_004 | stock | 阿特斯太阳能 | bullish | explicit_action | 0.80 | 0.88 |
| intent_005 | stock | 腾讯音乐 | bullish | watch | 0.65 | 0.75 |
| intent_006 | sector | 储能 | bullish | opinion | 0.65 | 0.78 |

覆盖标的: LI, 600989, CSIQ, TME（4 个个股） + 绿电、储能（2 个板块）

### 2.7 Agent G — 只读验收

| 项目 | 详情 |
|------|------|
| 状态 | ✓ 完成 |
| 操作 | 运行全部 fixture 契约测试，汇总 PASS/PARTIAL/FAIL |
| 结果 | **PASS** — 27/27 通过 |

---

## 3. V0 ContentEnvelope 数据结构

### 3.1 Envelope 元数据

```
envelope_id:    cat_lord_2026_03_12_feishu_doc
schema_version: v0.1（需修正为 v0.5）
source_type:    chat
source_title:   猫大人投资策略分析 — 2026年3月12日
creator_id:     cat_lord_fire
creator_name:   猫大人FIRE
published_at:   2026-03-12T15:36:00+08:00
```

### 3.2 Blocks 结构

| order | block_id | block_type | 内容摘要 | evidence_spans |
|-------|----------|------------|---------|---------------|
| 0 | block_01 | heading | 理想汽车分析 | 0 |
| 1 | block_02 | paragraph | 年报很惨…四季报… | 0 |
| 2 | block_03 | list | 4 条分析要点 | 2 (ev_001, ev_002) |
| 3 | block_04 | heading | 宝丰能源分析 | 0 |
| 4 | block_05 | paragraph | 目标价 27.5-27.8 元 | 3 (ev_003-005) |
| 5 | block_06 | paragraph | 算电协同/绿电逻辑 | 2 (ev_006, ev_007) |
| 6 | block_07 | paragraph | CSIQ 储能订单 | 3 (ev_008-010) |
| 7 | block_08 | paragraph | 腾讯音乐修复空间 | 2 (ev_011, ev_012) |

### 3.3 Temporal Anchors

| anchor_id | anchor_type | raw_text | resolved_time | resolution_strategy |
|-----------|-------------|----------|---------------|---------------------|
| ta_001 | published_at | 2026年3月12日 | 2026-03-12T00:00:00+08:00 | explicit_date |
| ta_002 | mentioned_at | Q4 | 2025-10-01T00:00:00+08:00 | fiscal_period |
| ta_003 | mentioned_at | 2026年1-2月 | 2026-01-01T00:00:00+08:00 | explicit_date |

### 3.4 Entity Anchors

| anchor_id | entity_type | raw_text | resolved_symbol | market | confidence |
|-----------|-------------|----------|----------------|--------|------------|
| ea_001 | stock | 理想汽车 | LI | US | 0.95 |
| ea_002 | stock | 宝丰能源 | 600989 | A | 0.95 |
| ea_003 | stock | 阿特斯太阳能 | CSIQ | US | 0.92 |
| ea_004 | stock | 腾讯音乐 | TME | US | 0.90 |
| ea_005 | sector | 绿电 | null | null | 0.88 |
| ea_006 | sector | 储能 | null | null | 0.90 |

---

## 4. V0-V1 跨层一致性

| 检查项 | 结果 |
|--------|------|
| V1 所有 envelope_id 与 V0 一致 | ✓ `cat_lord_2026_03_12_feishu_doc` |
| V1 所有 block_ids 在 V0 中存在 | ✓ |
| V1 所有 evidence_span_ids 在 V0 中存在 | ✓ |

---

## 5. 测试执行汇总

### 5.1 Fixture 契约测试（27 项）

| 测试类 | 测试数 | 结果 |
|--------|--------|------|
| TestCatLordMarkdownFixture | 4 | ✓ 全通过 |
| TestCatLordV0Fixture | 9 | ✓ 全通过 |
| TestCatLordV1Fixture | 11 | ✓ 全通过 |
| TestV0V1Consistency | 3 | ✓ 全通过 |

### 5.2 核心模块测试（115 项）

| 测试文件 | 测试数 | 结果 |
|----------|--------|------|
| test_cat_lord_fixture_contract.py | 27 | ✓ |
| test_content_standardizer.py | 49 | ✓ |
| test_schemas.py | 39 | ✓ |

### 5.3 全项目测试（566 项）

| 结果 | 数量 | 说明 |
|------|------|------|
| PASSED | 545 | 正常通过 |
| SKIPPED | 21 | async 测试因 pytest 配置问题被跳过，需修复 |
| FAILED | 0 | 无失败 |

---

## 6. 变更文件索引

| 文件 | 变更类型 | Agent |
|------|---------|-------|
| `src/finer/schemas/quality.py` | 新增 schema_version 字段 | B |
| `src/finer/schemas/temporal.py` | 新增 schema_version 字段 | B |
| `src/finer/schemas/evidence.py` | 新增 schema_version 字段 | B |
| `src/finer/schemas/entity_anchor.py` | 新增 schema_version 字段 | B |
| `src/finer/schemas/content_envelope.py` | 新增 3 种 placeholder block 类型 | D |
| `src/finer/parsing/content_standardizer.py` | 新增 placeholder 检测 + quality card | D |
| `tests/fixtures/kol/cat_lord_strategy_2026_03_12.md` | 新建 Markdown fixture | C |
| `tests/fixtures/kol/cat_lord_strategy_2026_03_12.expected_v0.json` | 新建 V0 golden case | C |
| `tests/fixtures/kol/cat_lord_strategy_2026_03_12.expected_v1.json` | 新建 V1 golden case | C |
| `tests/test_cat_lord_fixture_contract.py` | 新建契约测试 | C |
| `docs/multi-agent-execution-report.md` | 修正验收口径 | A |
| `docs/fixture-validation-report.json` | 新建验收报告 | G |

---

## 7. 遗留事项

| # | 事项 | 优先级 | 说明 |
|---|------|--------|------|
| 1 | V0 fixture schema_version 为 `v0.1` | P1 | 应与 schema 定义一致改为 `v0.5`，需本轮修复 |
| 2 | V1 fixture schema_version 为 `v1.0` | P2 | NormalizedInvestmentIntent 模型默认为 `"1.0"`，一致 |
| 3 | async 测试 21 项被跳过 | P1 | 需修复 pytest 配置，让 async 测试正常运行 |
| 4 | 图片策略 OCR fixture 未创建 | P1 | 当前 fixture 为飞书文档会话记录，需创建图片策略 fixture |
| 5 | 真实 V0→V1 生成链路未验证 | P1 | golden case 为人工构造，需验证 content_standardizer + intent_extractor 能自动生成 |

---

## 8. 当前阶段判定

| 检查项 | 状态 |
|--------|------|
| V0/V1 schema contract | **PASS** |
| 飞书文档/chat fixture 验证 | **PASS** |
| 图片策略 fixture 验证 | **PARTIAL** — 未创建 |
| 真实 V0 processor → V1 extractor pipeline | **PARTIAL** — 未验证 |
| 进入 V2 Policy Mapping | **否** — 需先完成上述 PARTIAL 项 |