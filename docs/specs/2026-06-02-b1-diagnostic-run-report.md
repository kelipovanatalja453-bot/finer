# B1 诊断跑报告 — 2026-06-02

## 概述

对 `data/packs/cat_lord/cat_lord_raw_20260531T142911Z/` 下 2 条 raw 执行 F1→quality_gate→F3→F4→F5 诊断跑。3/12 因 feishu_chat_standardizer 无法解析 raw 格式而止于 F3（无 intent）；4/26 通过 manual_text 适配器完成全链路（9 intents → 9 TradeActions）。发现 2 个阻断性 bug 和多项 F2 自生证据缺口。

---

## AS-B0: KOL ID 核查

**结论：`cat_lord` 与 `kol_cat_lord_fire` 是同一 KOL（猫大人FIRE）。**

| 来源 | ID | 位置 |
|------|-----|------|
| Pack manifest | `cat_lord` | `data/packs/cat_lord/…/manifest.json → kol_id` |
| Pipeline 产物 | `kol_cat_lord_fire` | `data/review/kol_cat_lord_fire/F4_policy/*.json → kol_id` |
| Pipeline 产物 | `kol_cat_lord_fire` | `data/review/kol_cat_lord_fire/F8_backtest/trades.json → kol_id` |
| API 路由注释 | `kol_cat_lord_fire` | `src/finer/api/routes/kol.py:395` |

**存在 ID 不一致**：pack 用短 ID `cat_lord`，pipeline 历史产物用 `kol_cat_lord_fire`。本次诊断在 trace 中记录映射 `{"pack": "cat_lord", "pipeline": "kol_cat_lord_fire"}`，不做全局改名。

---

## AS-B1: 诊断跑结果

### 条目 1: `cat_lord_strategy_2026_03_12` — NO_INTENTS

**实际函数链**：

```
1. symlink .raw → .md（StandardizationRouter 按后缀路由）
2. StandardizationRouter.route(ContentRecord, md_path) → adapter=feishu_chat
3. FeishuChatMarkdownStandardizer.standardize() → 1 block: system_event "[Standardization fallback: no_parseable_messages]"
4. evaluate_quality_card(envelope.quality_card) → status=review, score=0.48
5. LLMIntentExtractor.extract() → 0 intents（LLM 正确识别 fallback 文本无投资内容）
```

**失败原因**：Raw 文件格式不符合 feishu_chat_standardizer 期望。

| 期望格式 | 实际格式 |
|----------|----------|
| `### [2026-03-12 14:34:00] ou_xxx (text)` | `## 理想汽车分析` + `猫大人FIRE 2026年3月12日 20:46` |

feishu_chat adapter 的 `_HEADER_RE` 正则无法匹配实际 header，导致整个文档变成一个 fallback system_event block，丢失全部投资策略内容（理想汽车、宝丰能源、CSIQ、腾讯音乐 4 个分析段）。

**source_type 路由**：ContentRecord 使用 `source_type="chat_transcript"` 以触发 feishu_chat 路由。实际 raw 内容虽声称来自"飞书文档会话记录"，但并非标准飞书导出格式。若改用 `source_type="manual_upload"` 则路由到 manual_text adapter，可能产出更好结果。

### 条目 2: `cat_lord_image_strategy_2026_04_26` — GOLDEN_PATH_OK

**实际函数链**：

```
1. symlink .raw → .md
2. StandardizationRouter.route() → adapter=manual_text
3. ManualTextStandardizer.standardize() → 47 blocks
4. evaluate_quality_card(envelope.quality_card) → status=review, score=0.41
5. LLMIntentExtractor.extract() → 9 intents（含 evidence_spans）
   LLM provider: MiMo v2.5 via token-plan-cn.xiaomimimo.com
6. PolicyMapper.map_batch() → 9 mapped
7. CanonicalActionBuilder.build() + build_execution_timing() → 9 TradeActions
```

**F3 Intent 提取结果**：

| # | target_name | target_symbol | direction | conviction | actionability | keyword spans | block fallback spans |
|---|-------------|---------------|-----------|------------|---------------|--------------|---------------------|
| 1 | 储能 | ENERGY_STORAGE | bullish | 0.7 | opinion | 0 | 39 |
| 2 | 绿电 | GREEN_POWER | bullish | 0.7 | opinion | 1 | 0 |
| 3 | 600989 | 600989.SH | neutral | 0.5 | watch | 0 | 39 |
| 4 | 600989 | 600989.SH | neutral | 0.5 | watch | 0 | 39 |
| 5 | 理想汽车 | LI | bearish | 0.6 | opinion | 1 | 0 |
| 6 | 宝丰能源 | 600989 | neutral | 0.6 | watch | 1 | 0 |
| 7 | 阿特斯太阳能 | CSIQ | bullish | 0.8 | watch | 0 | 39 |
| 8 | 腾讯音乐 | TME | bullish | 0.6 | opinion | 1 | 0 |
| 9 | 600989 | 600989.SH | neutral | 0.5 | review_required | 1 | 0 |

**问题**：
- 600989 出现 3 个重复 intent（#3, #4, #9），加上 #6 宝丰能源（同一股票），共 4 个指向同一标的
- 宝丰能源 symbol 应为 `600989.SH` 但 #6 只标了 `600989`（不一致）
- 储能/阿特斯太阳能的 evidence_text 未命中任何 block 精确文本，退化为 39 个 block-level 全量 fallback span

---

## AS-B2a: Evidence Span ↔ 原文对齐验证

选取 3 个 keyword span 验证 char 偏移对齐：

### 验证 1: 绿电 intent

```
span char[31:52] in block "看好方向：\n- 储能：受益于算电协同需求，长期确定性增强\n- 绿电：成本优势明显，出口token逻辑清晰"
提取: "绿电：成本优势明显，出口token逻辑清晰"
原文 raw offset 686: "...储能：受益于算电协同需求，长期确定性增强\n- [绿电：成本优势明显，出口token逻辑清晰]..."
✅ 对齐正确
```

### 验证 2: 理想汽车 (LI) intent

```
span char[3:22] in block "结论：短期看空，等待新款车市场认可后再评估。"
提取: "短期看空，等待新款车市场认可后再评估。"
原文 raw offset 936: "...结论：[短期看空，等待新款车市场认可后再评估。]..."
✅ 对齐正确
```

### 验证 3: 腾讯音乐 (TME) intent

```
span char[0:16] in block "底部价值支撑，修复空间约20%。"
提取: "底部价值支撑，修复空间约20%。"
原文 raw offset 1222: "[底部价值支撑，修复空间约20%。]"
✅ 对齐正确
```

**结论**：keyword 类型 span 的 char 偏移（block 内偏移）对齐正确。block_level fallback span 始终是 `char[0:全文长度]`，无精确定位价值。

---

## AS-B2b: F2 自生证据缺口报告

### 1. Evidence Span 统计

| 类型 | 数量 | 占比 | 说明 |
|------|------|------|------|
| intent_keyword | 5 | 3.1% | LLM evidence_text 在 block 中精确匹配 |
| block_level | 156 | 96.9% | 退化：整块文本作为 evidence（char_start=0） |
| **总计** | **161** | | |

5 个 intent 有精确 keyword span（绿电、LI、宝丰能源、TME、600989#9），4 个 intent 退化为 39 个 block-level span（储能、600989#3、600989#4、CSIQ）。block-level span 无定位价值，等同于"整篇文档都是证据"。

**根因**：LLM 输出的 `evidence_text` 字段需精确匹配 block 内文本（`block.text.find(evidence_text)`）。LLM 的 evidence 表述与实际 block 文本不一致时，fallback 到 block-level。

### 2. Temporal Anchor 统计

| 字段 | 状态 | 说明 |
|------|------|------|
| `temporal_anchor_ids` | **全部为空** | 9 个 intent 无一有 temporal anchor |
| `envelope.temporal_anchors` | **空列表** | F2 锚定未运行 |

**原因**：本次跑跳过了 F2（设计如此——只跑 F1→quality_gate→F3→F4→F5）。temporal_anchors 需要 F2 enrichment 阶段填充。

### 3. 四时钟字段状态（4/26 "时间未知" 传播分析）

Raw 声明 `published_at: unknown`。tracking_builder 的处理：

| 字段 | 值 | 来源 | 问题 |
|------|-----|------|------|
| `intent_published_at` | `2026-06-02T12:21:38+08:00` | timing_builder 用 now() 估算 | **错误**：内容实际发布于 2026-04-26，但 raw 声明 unknown，timing_builder 无法获取真实时间 |
| `intent_effective_at` | `None` | 未设置 | 空字段，需要 F2 temporal anchor 填充 |
| `action_decision_at` | `2026-06-02T12:21:38` | timing_builder 用 now() | 实际含义是"pipeline 运行时间"，非 KOL 决策时间 |
| `action_executable_at` | `2026-06-02T12:26:38` | intent_published_at + 5min | **推断**：固定偏移 5 分钟，非真实可执行时间 |

**时区混用**：CN 市场标的（储能、600989、宝丰能源）使用 `+08:00`，US 市场标的（LI、CSIQ、TME）使用 `-04:00`（ET）。时区区分正确，但时间值本身是估算值。

**4/26 "时间未知" 结论**：`published_at: unknown` 被 timing_builder 默默替换为 `now()`（诊断运行时间 2026-06-02），一路传到 `action_executable_at = now() + 5min`。没有任何字段保留"时间未知"这一事实——所有四个时钟都被填了推断日期，且推断日期错误（应为 ~2026-04-26，实际为 2026-06-02）。

### 4. Quality Gate 状态

| 条目 | status | score | 拒绝原因 |
|------|--------|-------|----------|
| 3/12 | review | 0.48 | entity_resolution=0, temporal_resolution=0 |
| 4/26 | review | 0.41 | financial_relevance=0.49 < 0.6, entity_resolution=0, temporal_resolution=0 |

两条都是 `review`（非 reject），所以 quality gate 未阻止 F3。但 score 偏低是因为 F2 未运行导致 entity/temporal 得分为 0。

**quality gate bug**：`evaluate_envelope_quality()` 调用 `evaluate_quality_card(block.quality_card)` 时传入 `BlockQuality` 对象，但 `evaluate_quality_card()` 期望 `QualityCard`（需要 `overall_score` 属性）。本次诊断用 envelope 级 QualityCard 绕过。`golden_path.py:72` 调用此函数会直接崩溃。

### 5. 其他发现的阻断性 Bug

| Bug | 位置 | 影响 |
|-----|------|------|
| `LLMClient` 缺少 `model` property | `src/finer/llm/client.py` — 存储为 `self._model` 但 `router.py:112` 访问 `client.model` | F3 intent extraction 崩溃（`AttributeError: 'LLMClient' object has no attribute 'model'`） |
| `evaluate_envelope_quality` BlockQuality/QualityCard 类型不匹配 | `src/finer/services/quality_gate.py:330` | `golden_path.py:72` 的质量门控崩溃 |

两个 bug 均需修复才能让 `run_golden_path()` 正常运行。本次诊断通过 monkey-patch 和直接调用 F3→F4→F5 绕过。

### 6. Reject 清单

| 条目 | 被 reject/无产出 | 原因 |
|------|-----------------|------|
| 3/12 | NO_INTENTS | feishu_chat adapter 无法解析 raw 格式 → 产出 1 个 fallback block → LLM 正确返回 0 intents |
| 4/26 | 未被 reject | 全链路完成（9 intents → 9 TradeActions） |

---

## 诊断产物位置

```
data/b1_diagnostic_traces/
├── all_traces.json                              # 两条汇总
├── cat_lord_strategy_2026_03_12_trace.json       # 3/12 完整 trace
├── cat_lord_image_strategy_2026_04_26_trace.json # 4/26 完整 trace
└── cat_lord_image_strategy_2026_04_26/
    ├── F3_intents/      # 9 个 intent JSON
    ├── F4_policy_mapped/ # 9 个 policy mapping JSON
    └── F5_executed/      # 9 个 TradeAction JSON
```

诊断脚本：`scripts/b1_diagnostic_run.py`

---

## 验证命令

```bash
# 查看 trace
cat data/b1_diagnostic_traces/cat_lord_strategy_2026_03_12_trace.json | python -m json.tool | head -50
cat data/b1_diagnostic_traces/cat_lord_image_strategy_2026_04_26_trace.json | python -m json.tool | head -100

# 查看 F5 TradeAction（4/26）
ls data/b1_diagnostic_traces/cat_lord_image_strategy_2026_04_26/F5_executed/
```
