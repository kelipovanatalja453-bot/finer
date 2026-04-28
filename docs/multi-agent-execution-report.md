# Finer 多 Agent 并行执行报告

> **执行时间**: 2026-04-27  
> **项目路径**: `/Users/zhouhongyuan/Desktop/finer`  
> **执行模式**: 三轮并行  
> **文档版本**: 1.0

---

## 目录

1. [执行结构概览](#一执行结构概览)
2. [Round 1: 合约并行](#二round-1-合约并行)
3. [Round 2: 样本和链路并行](#三round-2-样本和链路并行)
4. [Round 3: 独立验收](#四round-3-独立验收)
5. [验收结果汇总](#五验收结果汇总)
6. [问题清单](#六问题清单)
7. [新增文件统计](#七新增文件统计)
8. [下一步行动](#八下一步行动)

---

## 一、执行结构概览

```
Round 1: 合约并行
├── Agent 1: V0/V0.5 Schema Contracts
├── Agent 2: V1 Intent Contract
└── Agent 3: Quality Gate Contract

Round 2: 样本和链路并行
├── Agent 4: Cat Lord Fixture + Golden Cases
├── Agent 5: Minimal V0 Processor
└── Agent 6: Minimal Intent Extractor

Round 3: 独立验收
└── Agent 7: Verification Only
```

**执行依赖关系**:

```
Agent 1 (V0 Schema) ──┬──→ Agent 5 (V0 Processor)
                      │
                      └──→ Agent 6 (Intent Extractor)
                      
Agent 2 (V1 Intent) ─────→ Agent 6 (Intent Extractor)

Agent 3 (Quality Gate) ──→ Agent 5 (V0 Processor)

Agent 4 (Fixture) ────────→ Agent 6 (Intent Extractor) [验证用]

Agent 1 + 2 + 3 + 4 + 5 + 6 ──→ Agent 7 (Verification)
```

---

## 二、Round 1: 合约并行

### 2.1 Agent 1: V0/V0.5 Schema Contracts

**状态**: ✅ 完成

**任务目标**: 新增 V0 和 V0.5 的 Pydantic schema，建立统一内容标准化层

**修改文件清单**:

| 文件路径 | 操作 | 说明 |
|----------|------|------|
| `src/finer/schemas/quality.py` | 新增 | 六维质量卡 |
| `src/finer/schemas/temporal.py` | 新增 | 四类时间锚 |
| `src/finer/schemas/evidence.py` | 新增 | 证据跨度 |
| `src/finer/schemas/entity_anchor.py` | 新增 | 实体锚 |
| `src/finer/schemas/content_envelope.py` | 新增 | V0 内容容器 |
| `src/finer/schemas/__init__.py` | 修改 | 导出新 schema |
| `tests/test_content_envelope_schema.py` | 新增 | V0 测试 |
| `tests/test_quality_temporal_evidence_schema.py` | 新增 | V0.5 测试 |

**新增 Schema 清单**:

| Schema | 文件引用 | 核心字段 |
|--------|----------|----------|
| `QualityCard` | `src/finer/schemas/quality.py:72-112` | 六维评分 + `overall_score` + `gate_status` |
| `EvidenceSpan` | `src/finer/schemas/evidence.py:66-111` | `block_id`, `char_start`, `char_end`, `text`, `confidence` |
| `TemporalAnchor` | `src/finer/schemas/temporal.py:29-34, 66-120` | 四类时间类型 + `resolved_time` + `confidence` |
| `EntityAnchor` | `src/finer/schemas/entity_anchor.py:35-50, 75-130` | 14种实体类型 + `resolved_symbol` + `market` |
| `ContentBlock` | `src/finer/schemas/content_envelope.py:150-250` | 9种 block 类型 + `quality_card` + `evidence_spans` |
| `ContentEnvelope` | `src/finer/schemas/content_envelope.py:260-350` | 7种 source 类型 + `blocks` + `quality_card` |

#### QualityCard 六维主卡

**引用**: `src/finer/schemas/quality.py:72-112`

```
┌─────────────────────────────────────────────────────────────┐
│                    QualityCard 六维主卡                      │
├─────────────────────────────────────────────────────────────┤
│ readability_score           │ 可读性           │ [0.0, 1.0] │
│ semantic_completeness_score │ 语义完整性       │ [0.0, 1.0] │
│ financial_relevance_score   │ 金融相关性       │ [0.0, 1.0] │
│ entity_resolution_score     │ 实体解析度       │ [0.0, 1.0] │
│ temporal_resolution_score   │ 时间解析度       │ [0.0, 1.0] │
│ evidence_traceability_score │ 证据可追溯性     │ [0.0, 1.0] │
├─────────────────────────────────────────────────────────────┤
│ 派生字段:                                                    │
│   overall_score = mean(六维分数)                             │
│   gate_status = "pass" | "review" | "reject"                 │
│   gate_reasons = List[str]                                   │
└─────────────────────────────────────────────────────────────┘
```

#### TemporalAnchor 四类时间

**引用**: `src/finer/schemas/temporal.py:29-34`

```python
TemporalAnchorType = Literal[
    "published_at",      # 内容发布/采集时间
    "mentioned_at",      # 文本中显式或隐式提到的时间
    "resolved_at",       # 相对时间解析后的绝对时间
    "effective_trade_at" # 回测采用的交易生效时间
]
```

| 时间类型 | 示例 | 用途 |
|----------|------|------|
| `published_at` | 2026-04-12 20:00 | 内容发布/采集时间 |
| `mentioned_at` | "上周" | 文本中显式或隐式提到的时间 |
| `resolved_at` | 2026-04-05 至 2026-04-11 | 相对时间解析后的绝对范围 |
| `effective_trade_at` | 2026-04-06 开盘后 | 回测采用的交易生效时间 |

#### ContentBlock 九种类型

**引用**: `src/finer/schemas/content_envelope.py:35-45`

```python
BLOCK_TYPE_LITERAL = Literal[
    "paragraph",          # 段落
    "heading",            # 标题
    "table",              # 表格
    "chart",              # 图表
    "image_region",       # 图片区域
    "chat_message",       # 聊天消息
    "transcript_segment", # 转录片段
    "list",               # 列表
    "unknown",            # 未知
]
```

#### ContentEnvelope 七种来源

**引用**: `src/finer/schemas/content_envelope.py:25-33`

```python
SOURCE_TYPE_LITERAL = Literal[
    "image",            # 图片
    "chat",             # 聊天记录
    "feishu_doc",       # 飞书文档
    "pdf",              # PDF
    "audio_transcript", # 音频转录
    "video_transcript", # 视频转录
    "text",             # 纯文本
]
```

---

### 2.2 Agent 2: V1 Intent Contract

**状态**: ✅ 完成

**任务目标**: 新增 `NormalizedInvestmentIntent`，明确它是 TradeAction 前置层

**修改文件清单**:

| 文件路径 | 操作 | 说明 |
|----------|------|------|
| `src/finer/schemas/investment_intent.py` | 新增 | V1 投资意图模型 |
| `src/finer/schemas/__init__.py` | 修改 | 导出 Intent schema |
| `tests/test_investment_intent_schema.py` | 新增 | V1 测试 |

#### NormalizedInvestmentIntent 四个主轴

**引用**: `src/finer/schemas/investment_intent.py:173-186`

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    NormalizedInvestmentIntent 四主轴                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. direction (方向)                                                     │
│     ├── bullish    看多                                                  │
│     ├── bearish   看空                                                  │
│     ├── neutral   中性                                                  │
│     ├── mixed     混合                                                  │
│     └── unknown   未知                                                  │
│                                                                          │
│  2. actionability (可操作性)                                             │
│     ├── opinion          只是观点                                        │
│     ├── watch            观察/关注                                       │
│     ├── explicit_action  明确动作                                        │
│     └── review_required  需要复核                                        │
│                                                                          │
│  3. position_delta_hint (仓位变动暗示)                                   │
│     ├── open    开仓                                                     │
│     ├── add     加仓                                                     │
│     ├── reduce  减仓                                                     │
│     ├── hold    持有                                                     │
│     ├── exit    退出                                                     │
│     ├── none    无变动                                                   │
│     └── unknown 未知                                                    │
│                                                                          │
│  4. conviction (信念强度)                                                │
│     └── float ∈ [0.0, 1.0]                                               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 完整字段清单

**引用**: `src/finer/schemas/investment_intent.py:130-230`

```python
class NormalizedInvestmentIntent(BaseModel):
    # 标识
    intent_id: str
    schema_version: str = "1.0"
    
    # 来源关联
    envelope_id: str
    block_ids: List[str]
    creator_id: Optional[str]
    
    # 目标
    target_type: Literal["stock", "sector", "index", "macro", "commodity", "crypto", "unknown"]
    target_name: str
    target_symbol: Optional[str]
    market: Optional[str]
    
    # 四主轴
    direction: Literal["bullish", "bearish", "neutral", "mixed", "unknown"]
    actionability: Literal["opinion", "watch", "explicit_action", "review_required"]
    position_delta_hint: Literal["open", "add", "reduce", "hold", "exit", "none", "unknown"]
    conviction: float
    
    # 辅助字段
    sentiment_score: Optional[float]  # 情绪分数（辅助）
    risk_preference_hint: Literal["aggressive", "balanced", "conservative", "unknown"]
    time_horizon_hint: Literal["intraday", "short_term", "medium_term", "long_term", "unknown"]
    
    # 证据绑定
    temporal_anchor_ids: List[str]
    evidence_span_ids: List[str]  # ← 关键：证据绑定
    
    # 模糊处理
    ambiguity_flags: List[str]
    confidence: float
    
    # 元数据
    metadata: Dict[str, Any]
```

#### Opinion vs Action 区分规则

**引用**: `src/finer/schemas/investment_intent.py:250-280`

| 原文 | direction | actionability | position_delta_hint |
|------|-----------|---------------|---------------------|
| "我看好宁德时代" | bullish | opinion | none |
| "我加仓宁德时代" | bullish | explicit_action | add |
| "继续持有腾讯" | bullish/neutral | explicit_action | hold |

---

### 2.3 Agent 3: Quality Gate Contract

**状态**: ✅ 完成

**任务目标**: 建立任务导向的质量门控规则

**修改文件清单**:

| 文件路径 | 操作 | 说明 |
|----------|------|------|
| `src/finer/services/quality_gate.py` | 新增 | 质量门控服务 |
| `src/finer/services/__init__.py` | 修改 | 导出服务 |
| `tests/test_quality_gate.py` | 新增 | 门控测试 |
| `docs/specs/quality-gate.md` | 新增 | 规格文档 |

#### 默认门控规则

**引用**: `src/finer/services/quality_gate.py:8-10`

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Quality Gate 规则                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  PASS (通过)                                                             │
│  ├── 条件: overall >= 0.75                                               │
│  │        AND financial_relevance >= 0.6                                 │
│  │        AND evidence_traceability >= 0.6                               │
│  └── 下一步: extract_intent                                              │
│                                                                          │
│  REVIEW (复核)                                                           │
│  ├── 条件: overall >= 0.45                                               │
│  │        OR 关键维度低                                                  │
│  └── 下一步: manual_review / reprocess_source                            │
│                                                                          │
│  REJECT (拒绝)                                                           │
│  ├── 条件: overall < 0.45                                                │
│  │        AND financial_relevance < 0.3                                  │
│  └── 下一步: drop                                                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 新增函数清单

**引用**: `src/finer/services/quality_gate.py:165-273`

| 函数 | 说明 |
|------|------|
| `evaluate_quality_card(card, policy) -> QualityGateDecision` | 评估单个 QualityCard |
| `evaluate_envelope_quality(envelope, policy) -> QualityGateDecision` | 评估 ContentEnvelope（含 block 聚合） |
| `get_default_policy() -> QualityGatePolicy` | 获取默认策略 |
| `create_strict_policy() -> QualityGatePolicy` | 创建严格策略 |
| `create_lenient_policy() -> QualityGatePolicy` | 创建宽松策略 |

#### 猫大人图片策略

**引用**: `src/finer/services/quality_gate.py:12-18`

对于图片策略，不能因为 OCR 局部乱码直接 reject：

| Block 类型 | 条件 | 处理 |
|------------|------|------|
| 大段策略正文 | readable + 金融相关高 | PASS → V1 |
| 表格/图表 | OCR 低但位置清楚 | REVIEW |
| 社交媒体 UI 噪声 | 无法识别 | DROP 或低优先级 |

---

## 三、Round 2: 样本和链路并行

### 3.1 Agent 4: Cat Lord Fixture + Golden Cases

**状态**: ⚠️ 阻塞

**阻塞原因**: 缺少实际数据源

**任务要求**:
- OCR 文本必须来自用户提供样本或真实转写，不允许补写
- 需要"超长猫大人 KOL 内容"的图片或 OCR 数据

**预期文件** (未创建):

```
tests/fixtures/kol/
├── cat_lord_strategy_image_2026_04_26.md           # OCR 转写文本
├── cat_lord_strategy_image_2026_04_26.expected_v0.json  # V0 黄金期望
└── cat_lord_strategy_image_2026_04_26.expected_v1.json  # V1 黄金期望

tests/
└── test_cat_lord_fixture_contract.py               # Fixture 合约测试

docs/specs/
└── cat-lord-golden-case.md                         # 黄金样本文档
```

**Fixture 合约要求**:

| 文件 | 要求 |
|------|------|
| `*.md` | 至少包含真实 OCR 文本，无法识别处用 `[OCR_UNREADABLE]` |
| `expected_v0.json` | 至少 8 个 ContentBlock，覆盖 3 种类型 |
| `expected_v1.json` | 至少 5 条 intent，覆盖市场/板块/个股/风险/图表 |

**需要用户提供**:
1. 猫大人策略图片的 OCR 输出或人工转写文本
2. 或图片文件路径
3. 或明确说明是否需要创建占位 fixture 结构

---

### 3.2 Agent 5: Minimal V0 Processor

**状态**: ✅ 完成

**任务目标**: 实现最小 V0 标准化处理器

**修改文件清单**:

| 文件路径 | 操作 | 说明 |
|----------|------|------|
| `src/finer/parsing/content_standardizer.py` | 新增 | 核心标准化处理器 |
| `src/finer/parsing/__init__.py` | 新增 | 模块导出 |
| `tests/test_content_standardizer.py` | 新增 | 完整测试套件 |

#### 新增函数清单

**引用**: `src/finer/parsing/content_standardizer.py:253-331`

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    V0 Processor 函数清单                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  主函数:                                                                 │
│  ├── standardize_text_source(text, ...) -> ContentEnvelope              │
│  └── standardize_markdown_source(markdown, ...) -> ContentEnvelope      │
│                                                                          │
│  便捷函数:                                                               │
│  ├── standardize_chat_transcript(transcript, ...) -> ContentEnvelope    │
│  ├── standardize_audio_transcript(transcript, ...) -> ContentEnvelope   │
│  └── standardize_image_strategy(text_content, ...) -> ContentEnvelope   │
│                                                                          │
│  内部辅助:                                                               │
│  ├── _detect_block_type(text) -> BLOCK_TYPE_LITERAL                     │
│  ├── _create_default_quality_card(block_type) -> QualityCard            │
│  ├── _create_evidence_span(...) -> EvidenceSpan                         │
│  └── _split_into_blocks(text) -> List[str]                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Block 拆分规则

**引用**: `src/finer/parsing/content_standardizer.py:185-246`

```
输入文本
    │
    ▼
双换行分隔 → 段落边界
    │
    ▼
逐行处理:
├── 标题行 (H1-H6) → 独立 heading block
├── 列表项 (-, 1.) → 合并为 list block
├── 表格行 (|...|) → 识别为 table block
├── 图表占位符 ([图表]) → 识别为 chart block
└── 其他 → paragraph block
    │
    ▼
输出: List[ContentBlock]
```

#### 约束验证

| 约束 | 状态 | 说明 |
|------|------|------|
| 不调用 LLM | ✅ | 纯规则处理 |
| 不做复杂 NLP | ✅ | 仅做文本分割和类型检测 |
| 不映射 TradeAction | ✅ | 输出为 ContentEnvelope |
| 保留 creator_id | ✅ | 参数传递 |
| 保留 published_at | ✅ | 参数传递 |

---

### 3.3 Agent 6: Minimal Intent Extractor

**状态**: ✅ 完成

**任务目标**: 实现规则优先的最小 V1 intent extractor

**修改文件清单**:

| 文件路径 | 操作 | 说明 |
|----------|------|------|
| `src/finer/extraction/intent_extractor.py` | 新增 | 意图提取器 |
| `src/finer/extraction/__init__.py` | 新增 | 模块导出 |
| `tests/test_intent_extractor.py` | 新增 | 完整测试套件 |

#### 新增 Schema/函数清单

**引用**: `src/finer/extraction/intent_extractor.py:360-380`

| 名称 | 说明 |
|------|------|
| `IntentExtractionResult` | 意图提取结果容器 |
| `extract_intents_from_envelope(envelope) -> IntentExtractionResult` | 主提取函数 |

#### 规则映射表

**引用**: `src/finer/extraction/intent_extractor.py:100-112, 191-222`

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Intent 提取规则映射                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Direction 检测:                                                         │
│  ├── 看好/受益/机会/加仓/抄底/持有 → bullish                             │
│  └── 看空/减仓/退出/不及预期/风险/回避 → bearish                         │
│                                                                          │
│  Actionability 检测:                                                     │
│  ├── 加仓/抄底/买入/增持/建仓 → explicit_action, add                     │
│  ├── 卖出/减仓/清仓/退出/减持 → explicit_action, reduce                  │
│  ├── 持有/继续拿 → explicit_action, hold                                 │
│  ├── 看好 → opinion, none                                                │
│  └── 关注/观察/留意 → watch, none                                        │
│                                                                          │
│  实体提取:                                                               │
│  ├── 优先从 entity_anchors 获取                                          │
│  ├── 回退: 匹配 "XX板块" / "XX行业" / "XX股"                             │
│  └── 无匹配 → target_name="unknown" + ambiguity flag                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 强制约束

**引用**: `src/finer/extraction/intent_extractor.py:329`

```python
# 每个 intent 必须有至少一个 evidence span
if not block_evidence:
    continue  # 跳过无证据的 intent
```

| 约束 | 状态 | 说明 |
|------|------|------|
| 每个 intent 绑定 evidence span | ✅ | 强制检查，无证据则跳过 |
| sentiment_score 不覆盖 action | ✅ | sentiment_score 为 None |
| 不生成仓位比例 | ✅ | metadata 无 position_ratio |
| 不写入 TradeAction | ✅ | 返回 IntentExtractionResult |

---

## 四、Round 3: 独立验收

### 4.1 Agent 7: Verification Only

**状态**: ✅ 完成

**验收结论**: **PARTIAL**

**说明**: Agent 4 因缺少实际数据源被阻塞，无法完成猫大人 fixture 创建。该任务为独立任务，不影响已完成的 Schema/Processor/Extractor 功能，但需要用户补充数据后方可进入下一阶段。

**检查命令执行**:

```bash
# 1. Git 状态检查
git status --short
git diff --name-only

# 2. 目标测试
pytest tests/test_content_envelope_schema.py \
       tests/test_quality_temporal_evidence_schema.py \
       tests/test_investment_intent_schema.py \
       tests/test_quality_gate.py \
       tests/test_content_standardizer.py \
       tests/test_intent_extractor.py -q

# 3. 全量测试
pytest -q

# 4. 编译检查
python -m compileall src/finer
```

---

## 五、验收结果汇总

### 5.1 测试执行结果

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         测试执行结果                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Round 1 Targeted Tests:                                                 │
│  ├── test_content_envelope_schema.py     ✅                              │
│  ├── test_quality_temporal_evidence_schema.py  ✅                        │
│  ├── test_investment_intent_schema.py    ✅                              │
│  └── test_quality_gate.py                ✅                              │
│  结果: 111 passed                                                        │
│                                                                          │
│  Round 2 Targeted Tests:                                                 │
│  ├── test_content_standardizer.py        ✅                              │
│  └── test_intent_extractor.py            ✅                              │
│  结果: 54 passed                                                         │
│                                                                          │
│  全量测试: 508 passed, 21 skipped                                        │
│  编译检查: 成功，无错误                                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Schema 验收清单

| 检查项 | 状态 | 引用 |
|--------|------|------|
| QualityCard 六维主卡 | ✅ | `src/finer/schemas/quality.py:72-112` |
| TemporalAnchor 四类时间 | ✅ | `src/finer/schemas/temporal.py:29-34` |
| NormalizedInvestmentIntent 四主轴 | ✅ | `src/finer/schemas/investment_intent.py:173-186` |
| ContentEnvelope schema_version | ✅ | `src/finer/schemas/content_envelope.py:275` |
| NormalizedInvestmentIntent schema_version | ✅ | `src/finer/schemas/investment_intent.py:135` |

### 5.3 证据链验收

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           证据链结构                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  NormalizedInvestmentIntent                                              │
│  └── evidence_span_ids: List[str]                                        │
│          │                                                               │
│          ▼                                                               │
│      EvidenceSpan                                                        │
│      └── block_id: str                                                   │
│              │                                                           │
│              ▼                                                           │
│          ContentBlock                                                    │
│          └── 属于 ContentEnvelope.blocks                                 │
│                  │                                                       │
│                  ▼                                                       │
│              ContentEnvelope                                             │
│              └── source_type, source_uri, creator_id                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

| 检查项 | 状态 | 引用 |
|--------|------|------|
| Intent 绑定 evidence span | ✅ | `intent_extractor.py:329` 强制检查 |
| Evidence 指向 block | ✅ | `evidence.py:66-69` |
| Block 属于 envelope | ✅ | `content_envelope.py:302-305` |

### 5.4 文件边界验收

| 检查项 | 状态 | 说明 |
|--------|------|------|
| TradeAction 未修改 | ✅ | `src/finer/schemas/trade_action.py` 未触及 |
| 前端未修改 | ✅ | `src/finer_dashboard/` 未触及 |
| Pipeline 未修改 | ✅ | `src/finer/pipeline/` 未触及 |
| Backtest 未修改 | ✅ | `src/finer/backtest/` 未触及 |

---

## 六、问题清单

### 6.1 阻塞问题

| # | 问题 | 严重度 | 影响 | 解决方案 |
|---|------|--------|------|----------|
| B1 | Agent 4 缺少实际数据源 | 🔴 高 | 无法创建猫大人 fixture | 需用户提供图片/OCR 数据 |

### 6.2 非阻塞问题

| # | 问题 | 严重度 | 引用 | 说明 |
|---|------|--------|------|------|
| P1 | QualityCard 缺少 schema_version 字段 | 🟡 中 | `quality.py` | 文件头部注释有版本声明 v0.5 |
| P2 | TemporalAnchor 缺少 schema_version 字段 | 🟡 中 | `temporal.py` | - |
| P3 | EvidenceSpan 缺少 schema_version 字段 | 🟡 中 | `evidence.py` | - |
| P4 | EntityAnchor 缺少 schema_version 字段 | 🟡 中 | `entity_anchor.py` | - |

---

## 七、新增文件统计

### 7.1 按类型统计

| 类型 | 数量 | 文件列表 |
|------|------|----------|
| **Schema** | 6 | `quality.py`, `temporal.py`, `evidence.py`, `entity_anchor.py`, `content_envelope.py`, `investment_intent.py` |
| **Service** | 1 | `quality_gate.py` |
| **Processor** | 1 | `content_standardizer.py` |
| **Extractor** | 1 | `intent_extractor.py` |
| **Test** | 6 | `test_content_envelope_schema.py`, `test_quality_temporal_evidence_schema.py`, `test_investment_intent_schema.py`, `test_quality_gate.py`, `test_content_standardizer.py`, `test_intent_extractor.py` |
| **Doc** | 1 | `docs/specs/quality-gate.md` |

### 7.2 按层级统计

| 层级 | 新增文件 | 说明 |
|------|----------|------|
| **V0 (ContentEnvelope)** | 5 schema + 2 test | 内容标准化层 |
| **V0.5 (Quality/Temporal/Evidence)** | 包含在 V0 中 | 质量、时间、证据锚定 |
| **V1 (Intent)** | 1 schema + 1 test | 投资意图层 |
| **Quality Gate** | 1 service + 1 test + 1 doc | 质量门控 |
| **V0 Processor** | 1 module + 1 test | 标准化处理器 |
| **Intent Extractor** | 1 module + 1 test | 意图提取器 |

---

## 八、下一步行动

### 8.1 是否允许进入下一阶段

**结论**: ⚠️ **PARTIAL** — 需先解决 Agent 4 阻塞问题

**条件验证**:
- [x] 测试全部通过
- [x] 文件边界合规
- [x] 证据链完整
- [ ] **Agent 4 fixture 数据缺失** — 需用户提供猫大人策略图片/OCR 数据

**阻塞说明**:
- Agent 4 任务（猫大人 fixture + golden cases）因缺少实际数据源被阻塞
- 该 fixture 用于 V1 意图提取的黄金样本验证，是端到端测试的关键输入
- 其他 Agent 的 Schema/Processor/Extractor 实现已完成并通过测试
- 用户需补充数据后方可进入 Policy Mapping 阶段

### 8.2 待办事项

| 优先级 | 事项 | 说明 |
|--------|------|------|
| **P0** | 提供猫大人策略图片/OCR 数据 | 完成 Agent 4 fixture 创建 |
| **P1** | 补充 schema_version 字段 | 修复 P1-P4 非阻塞问题 |
| **P2** | 进入 Policy Mapping 阶段 | V2 层实现 |

### 8.3 版本规划对照

```
| v1.3 (当前) ─── 架构文档对齐 ✅
    │
    ▼
v1.4 (2周) ─── V0/V1 schema + 质量卡 + 时间锚 + 图片/聊天标准化 MVP
    │           ├── Round 1 完成 ✅
    │           ├── Round 2 部分完成 (Agent 4 阻塞 ⚠️)
    │           └── Round 3 验收通过 (结论: PARTIAL)
    ▼
v1.5 (4周) ─── Policy Mapping + KOL Persona Policy (需先完成 Agent 4)
    ▼
v1.6 (6周) ─── ViewpointState + 多 KOL 分歧图谱
    ▼
v2.0 (8+周) ─ SFT/DPO 训练
```

---

## 附录 A: 关键代码引用索引

| 模块 | 文件 | 关键行号 | 说明 |
|------|------|----------|------|
| QualityCard 六维 | `src/finer/schemas/quality.py` | 72-112 | 六维评分定义 |
| TemporalAnchor 四类 | `src/finer/schemas/temporal.py` | 29-34 | 时间类型 Literal |
| Intent 四主轴 | `src/finer/schemas/investment_intent.py` | 173-186 | direction/actionability/position_delta/conviction |
| Intent 证据绑定 | `src/finer/schemas/investment_intent.py` | 225-228 | evidence_span_ids 字段 |
| Quality Gate 规则 | `src/finer/services/quality_gate.py` | 8-10, 224-273 | 门控逻辑 |
| V0 Processor | `src/finer/parsing/content_standardizer.py` | 185-246, 253-331 | Block 拆分 + 标准化 |
| Intent Extractor | `src/finer/extraction/intent_extractor.py` | 100-112, 191-222, 329 | 规则映射 + 强制 evidence |

---

## 附录 B: Git 变更摘要

```bash
# 新增文件 (15 个)
src/finer/schemas/quality.py
src/finer/schemas/temporal.py
src/finer/schemas/evidence.py
src/finer/schemas/entity_anchor.py
src/finer/schemas/content_envelope.py
src/finer/schemas/investment_intent.py
src/finer/services/quality_gate.py
src/finer/parsing/content_standardizer.py
src/finer/parsing/__init__.py
src/finer/extraction/intent_extractor.py
src/finer/extraction/__init__.py
tests/test_content_envelope_schema.py
tests/test_quality_temporal_evidence_schema.py
tests/test_investment_intent_schema.py
tests/test_quality_gate.py
tests/test_content_standardizer.py
tests/test_intent_extractor.py
docs/specs/quality-gate.md

# 修改文件 (2 个)
src/finer/schemas/__init__.py
src/finer/services/__init__.py
```

---

*文档生成时间: 2026-04-27*  
*执行者: Claude Code Multi-Agent System*
