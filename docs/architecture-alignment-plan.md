# Finer 架构对齐规划

> 创建日期: 2026-04-27  
> 目标: 将当前 Finer 项目从“直接抽取 TradeAction 的原型系统”，对齐到“复杂 KOL 内容时间轴 -> 标准化内容块 -> 投资意图 -> 个性化 policy -> 交易执行 -> 回测评估”的可扩展架构。

---

## 1. 对齐原则

### 1.1 不把模型训练当作第一步

当前项目的核心瓶颈不是缺一个更强模型，而是中间语义层不清楚。如果直接训练模型，模型会学习到混乱的输入边界、时间错误、证据断裂和 KOL 风格混杂。

优先级应为:

1. 先统一原始内容标准化结构。
2. 再定义投资意图 schema。
3. 再定义 policy 和交易动作映射。
4. 最后才进入 SFT/DPO/LoRA 等训练。

### 1.2 区分三类完成度

后续文档和任务状态必须区分:

| 状态 | 含义 |
|---|---|
| Schema 完成 | 数据结构存在，字段可校验 |
| 逻辑完成 | 核心算法/规则/模型调用可运行 |
| 端到端完成 | 从输入、存储、API、前端、测试全链路打通 |

当前项目很多模块处在“Schema 完成”或“局部逻辑完成”，不能直接视作端到端完成。

### 1.3 保持文件系统为真相源，引入索引层

当前 JSON/Markdown 文件存储适合审计和版本追踪，应保留。但时间线、KOL 查询、跨文档关联、回测任务需要索引层。

推荐原则:

- 文件系统: authoritative source of truth。
- SQLite/DuckDB: 可重建查询索引。
- 不在第一阶段引入复杂数据库集群。

---

## 2. 当前架构与目标架构差异

### 2.1 当前架构实际状态

当前主链路大致为:

```text
L0 ingestion
  -> L1 enrichment
  -> L3 perception / OCR / ASR
  -> L4 aggregation summary
  -> L5 direct TradeAction extraction
  -> L6 review / RLHF
  -> L7 timeline by TradeAction
  -> L8 backtest
```

已具备的基础能力:

- 多源接入: 飞书、微信、B站、NotebookLM、手动上传。
- 多模态解析雏形: OCR、ASR、DocumentConverter、Qwen-VL。
- TradeAction schema 较完整。
- RLHF、DPO 导出、KOL scoring、backtest engine 均有初版实现。
- 前端已有工作台、观点时间线、KOL 页面、回测页面。

主要问题:

- V0 标准化内容层缺失。
- 直接从文本摘要抽取 TradeAction，证据链容易丢失。
- 投资意图和交易动作混在一起。
- 时间字段没有分层。
- KOL persona/policy 没有进入抽取和交易映射链路。
- 图片、表格、长聊天记录、音频转录稿没有统一 block schema。
- 跨文档观点串联缺失。
- L8 回测引擎存在，但 pipeline 集成仍不完整。

### 2.2 目标架构

目标链路应调整为:

```text
S0 Raw Source
  -> V0 Content Standardization
  -> V0.5 Quality + Temporal + Entity Anchoring
  -> V1 NormalizedInvestmentIntent
  -> V2 Policy Mapping
  -> V3 ExecutableTradeAction
  -> V4 Timeline + Viewpoint State
  -> V5 Backtest + KOL Evaluation
  -> V6 Training Data + Model Improvement
```

对应到现有 L0-L8:

| 新目标层 | 对应现有层 | 说明 |
|---|---|---|
| S0 Raw Source | L0 | 原始文件、飞书消息、图片、音频、PDF、链接文档 |
| V0 Content Standardization | L2/L3 前置 | 新增统一内容 envelope/block |
| V0.5 Quality/Time/Entity | L1/L3/L4 | 对现有 enrichment/perception 重新定位 |
| V1 Intent | L5 前置 | 新增投资意图层，不直接进入 TradeAction |
| V2 Policy Mapping | 新增 | 全局 policy + 风格 policy + 风险偏好 + KOL 个体修正 |
| V3 TradeAction | L5/L6 | 现有 TradeAction 作为执行层产物 |
| V4 Timeline State | L7 | 不只列动作，还维护观点状态演化 |
| V5 Backtest/Evaluation | L8 | 回测、归因、KOL 评分 |
| V6 Training Loop | ML/RLHF/DPO | 从标注和回测结果生产训练数据 |

---

## 3. 核心 Schema 对齐

### 3.1 V0: ContentEnvelope

用途: 把所有来源统一成一个可审计、可分块、可追踪的内容容器。

建议字段:

```python
class ContentEnvelope:
    envelope_id: str
    source_id: str
    source_type: Literal["feishu_chat", "feishu_doc", "image", "pdf", "audio_transcript", "video_transcript", "wechat_article", "manual"]
    kol_id: Optional[str]
    creator_name: Optional[str]
    published_at: Optional[datetime]
    collected_at: datetime
    source_uri: Optional[str]
    raw_path: Optional[str]
    blocks: list[ContentBlock]
    quality_card: QualityCard
    temporal_anchors: list[TemporalAnchor]
    lineage: DataLineage
    metadata: dict
```

### 3.2 V0: ContentBlock

用途: 把复杂材料拆成统一 block，后续抽取只面对 block，而不是直接面对任意文件。

建议字段:

```python
class ContentBlock:
    block_id: str
    envelope_id: str
    block_type: Literal[
        "chat_message",
        "paragraph",
        "image_text",
        "table",
        "chart",
        "audio_segment",
        "video_segment",
        "quote",
        "link_reference",
        "section_title"
    ]
    text: str
    order_index: int
    speaker: Optional[str]
    page_index: Optional[int]
    image_region: Optional[dict]
    start_time_sec: Optional[float]
    end_time_sec: Optional[float]
    parent_block_id: Optional[str]
    thread_id: Optional[str]
    evidence_span: Optional[EvidenceSpan]
    quality_card: QualityCard
    metadata: dict
```

### 3.3 V0.5: TemporalAnchor

用途: 解决“发布时间”和“文本指向时间”不一致的问题。

必须区分四类时间:

| 字段 | 示例 | 用途 |
|---|---|---|
| `published_at` | 2026-04-12 20:00 | 内容发布/采集时间 |
| `mentioned_time` | 上周 | 文本中显式或隐式提到的时间 |
| `resolved_time_range` | 2026-04-05 至 2026-04-11 | 相对时间解析后的绝对范围 |
| `effective_trade_time` | 2026-04-06 开盘后 | 回测采用的交易生效时间 |

建议字段:

```python
class TemporalAnchor:
    anchor_id: str
    text_span: str
    anchor_type: Literal["published", "mentioned", "resolved", "effective_trade"]
    resolved_start: Optional[datetime]
    resolved_end: Optional[datetime]
    confidence: float
    resolution_rule: Optional[str]
    needs_review: bool
```

### 3.4 V1: NormalizedInvestmentIntent

用途: 把 KOL 自然语言观点转成标准投资意图，但暂不直接生成交易。

V1 至少拆成四个主轴:

| 轴 | 含义 | 示例 |
|---|---|---|
| `direction` | 看多/看空/中性/风险提示 | “看好腾讯长期护城河” -> bullish |
| `actionability` | 只是观点，还是明确动作 | “看好”低于“加仓” |
| `position_delta_hint` | 仓位变化提示 | 开仓/加仓/减仓/持有/退出 |
| `conviction` | 信念强度 | “坚定抄底”高于“可以看看” |

建议扩展附加轴:

| 轴 | 是否进入 V1 | 说明 |
|---|---|---|
| `sentiment_features` | 是 | zhiziX/情绪强度作为附加维度，不替代 direction |
| `time_horizon` | 是 | 日内、短线、波段、中长期 |
| `risk_signal` | 是 | 是否包含止损、仓位、波动、政策风险 |
| `evidence_quality` | 是 | 抽取证据是否来自完整语境 |
| `ambiguity_type` | 是 | 保留模糊样本并标注原因 |

建议字段:

```python
class NormalizedInvestmentIntent:
    intent_id: str
    envelope_id: str
    block_ids: list[str]
    kol_id: Optional[str]
    target: TargetInfo
    direction: Literal["bullish", "bearish", "neutral", "watchlist", "risk_warning"]
    actionability: Literal["view_only", "implicit_action", "explicit_action"]
    position_delta_hint: Literal["open", "add", "reduce", "hold", "exit", "unknown"]
    conviction: float
    sentiment_features: dict
    time_horizon: Optional[str]
    temporal_anchor_id: Optional[str]
    rationale: str
    evidence_text: str
    ambiguity_notes: list[str]
    confidence: float
    policy_context: Optional[dict]
```

---

## 4. Policy 分层设计

### 4.1 为什么不能只用统一 policy

同一句“加仓”在不同 KOL 风格下含义不同:

- 短线割头皮: 加仓可能只代表日内资金试探。
- 板块景气流: 加仓可能代表对产业趋势确认。
- 价值投资流: 加仓可能代表估值进入安全边际。
- 烟蒂股策略: 加仓可能代表低估但不一定高确定性。

统一 policy 会导致:

- 仓位解释错误。
- 时间周期错误。
- 回测持仓期错误。
- 看多强度和交易动作强度混淆。

### 4.2 推荐 policy 层级

```text
Global Base Policy
  -> Style Archetype Policy
  -> Risk Preference Policy
  -> KOL Persona Policy
  -> Content-Specific Correction
```

| 层级 | 作用 | 生成方式 |
|---|---|---|
| Global Base Policy | 通用金融语言到意图的基准映射 | 人工规则 + 少量标注 |
| Style Archetype Policy | 短线、景气、价值、烟蒂等风格差异 | 聚类 + 人工命名 |
| Risk Preference Policy | 激进/均衡/保守，止损和仓位习惯 | 从历史内容统计 |
| KOL Persona Policy | 某个 KOL 的口头禅、动作含义、持仓习惯 | 200-1000 条内容总结 |
| Content-Specific Correction | 当前上下文对 policy 的临时修正 | V1 抽取时动态生成 |

### 4.3 200-1000 条内容是否足够生成 persona

结论: 足够生成“可用的 policy 草案”，但不足以完全自动化交易。

可生成:

- 常用表达映射。
- 常覆盖行业/标的。
- 时间周期偏好。
- 风险偏好。
- 是否经常复盘和承认错误。
- “看好”“买”“加仓”“配置”“观察”等词在该 KOL 语境下的强度分布。

不应直接生成:

- 精确仓位比例。
- 稳定收益承诺。
- 自动跟单策略。

---

## 5. 多源内容处理策略

### 5.1 来源差异

| 来源 | 难点 | V0 处理重点 |
|---|---|---|
| 图片策略 | OCR、版面、表格、图表、截图上下文 | 多模块拆分，保留 image region |
| 长聊天记录 | 多人混杂、回复关系、时间跨度长 | 按 KOL、话题、时间窗口重组 |
| 飞书链接文档 | 文档结构、嵌入图片、引用链接 | 拉取正文 + 子资源 + 引用关系 |
| PDF | 页眉页脚、表格、跨页结构 | 页块、表格块、标题层级 |
| 音频转录稿 | 口语、断句、ASR 错误、无段落 | 语义断句、时间戳、说话人 |
| 视频转录稿 | 音频和画面不同步 | 字幕/ASR + 画面关键帧 |

### 5.2 图片优先级调整

图片应在 V0 中提升为高优先级输入，因为大量 KOL 策略以截图或长图形式发布。

图片 V0 不应只输出 Markdown 文本，还应输出:

- block 类型: 标题、段落、表格、图表、清单、截图嵌套图。
- region 坐标。
- OCR 置信度。
- 表格结构。
- 图表解释。
- 与周边聊天消息的关系。

---

## 6. 质量卡与门控机制

### 6.1 质量卡六维主卡

每个 `ContentEnvelope` 和 `ContentBlock` 都应有质量卡。

| 维度 | 目标 | 判断方式 |
|---|---|---|
| completeness | 内容是否完整 | 是否缺页、缺图、截断、ASR 过短 |
| readability | 文本是否可读 | OCR/ASR 乱码率、断句质量 |
| structure | 结构是否恢复 | 标题、表格、段落、列表是否识别 |
| temporal_resolvability | 时间是否可解析 | 是否有发布/指称/生效时间 |
| entity_resolvability | 标的是否可链接 | 股票名、代码、板块能否标准化 |
| evidence_fidelity | 证据是否可追溯 | intent 是否能回到原 block/span/图片区域 |

### 6.2 门控等级

| 等级 | 条件 | 处理 |
|---|---|---|
| Pass | 关键字段完整，证据可追溯 | 自动进入 V1 |
| Soft Pass | 有小缺陷但不影响意图判断 | 进入 V1，标注 warning |
| Review | 时间/标的/动作存在歧义 | 进入人工复核队列 |
| Reject | 内容不可读或证据断裂 | 不进入 V1，仅存档 |

### 6.3 门控是否调用 API 模型

建议采用混合方式:

| 判断项 | 优先方式 |
|---|---|
| 文件是否缺失、长度、格式、OCR 字符数 | 规则 |
| 乱码率、重复率、ASR 断句 | 规则 + 本地模型 |
| 表格/版面是否恢复 | VLM/API 模型 |
| 时间指称解析 | 规则 + LLM |
| 标的实体链接 | 规则库 + 金融实体库 + LLM fallback |
| 证据是否支撑 intent | LLM judge + 人工抽样 |

---

## 7. 跨文档观点串联

### 7.1 什么时候执行

建议分两段执行:

1. V0 后执行轻量 linking: 同一 KOL、同一标的、相近时间、相似主题。
2. V1 后执行观点状态机: 基于 intent 维护观点变化、仓位变化、理由变化。

### 7.2 Viewpoint State

目标不是只列出一条条 TradeAction，而是维护“某 KOL 对某标的的观点状态”。

建议状态字段:

```python
class ViewpointState:
    kol_id: str
    target_id: str
    current_direction: str
    current_position_hint: str
    conviction: float
    active_thesis: list[str]
    risk_factors: list[str]
    last_updated_at: datetime
    supporting_intent_ids: list[str]
    contradiction_intent_ids: list[str]
```

可支持案例:

- 2025 年不看好 600 元腾讯，认为脱离内在价值。
- 2026 年 500 元附近逐渐加仓腾讯。
- 3 月看好福寿园现金模式。
- 4 月因财报不及预期减仓福寿园。

### 7.3 多 KOL 同标的分歧

在 V1 Intent 稳定后，建立 `TargetOpinionGraph`:

```text
target_id
  -> KOL A: bullish, high conviction, long-term
  -> KOL B: bearish, valuation risk
  -> KOL C: neutral, wait for earnings
```

用途:

- 展示同一标的的共识/分歧。
- 识别风格差异。
- 为回测提供组合策略: 跟随单 KOL、跟随共识、跟随反向信号。

---

## 8. 模型/API/训练分工

### 8.1 API 模型适合做什么

适合:

- 多模态标准化: 图片、PDF、复杂图表、飞书文档。
- 复杂时间指称解析。
- V1 初始 intent 抽取。
- 证据一致性 judge。
- KOL persona 初稿总结。

优点:

- 上手快。
- 多模态能力强。
- 对复杂文本鲁棒。

缺点:

- 成本高。
- 难以完全可控。
- 输出稳定性需要 schema 和评估兜底。

### 8.2 规则/本地模型适合做什么

适合:

- 文件完整性检测。
- 重复率、乱码率、长度、OCR 质量。
- 常见股票代码和公司名标准化。
- 常见时间表达解析。
- 基础情绪/强度特征。

优点:

- 快、便宜、可解释。
- 适合批量处理。

缺点:

- 复杂语义能力有限。
- 需要持续维护词表和规则。

### 8.3 开源基座微调适合做什么

适合放在后期:

- V1 intent 抽取。
- KOL 风格分类。
- actionability/conviction/position_delta_hint 分类。
- evidence -> intent 的结构化输出。

不建议第一阶段就做:

- 端到端从原始文件直接到 TradeAction。
- 直接学习仓位比例。
- 在没有高质量标签前做大规模 DPO。

### 8.4 推荐训练路线

```text
Phase 0: API + 规则跑通 V0/V1
Phase 1: 人工复核 300-500 个高质量 intent 样本
Phase 2: Few-shot prompt library
Phase 3: 导出 SFT 数据，微调小模型做 intent 分类/抽取
Phase 4: 用 RLHF 偏好数据做 DPO
Phase 5: 用回测结果做 policy 层评估，不直接当唯一训练标签
```

---

## 9. 分阶段任务拆分

### Phase A: 架构契约冻结

目标: 先定义新中间层，不大改现有业务逻辑。

任务:

1. 新增 `ContentEnvelope`, `ContentBlock`, `QualityCard`, `TemporalAnchor`, `EvidenceSpan` schema。
2. 新增 `NormalizedInvestmentIntent` schema。
3. 明确 `TradeAction` 是 V3 执行动作，不再承担全部语义。
4. 更新 docs/ARCHITECTURE.md，把 L0-L8 和 V0-V6 对齐。
5. 为每个 schema 写最小单测。

验收:

- schema 可序列化/反序列化。
- 可以用一条图片策略、一段聊天记录、一段音频转录构造样例。
- 文档不再把 schema 完成误写为端到端完成。

### Phase B: V0 标准化 MVP

目标: 把复杂文件统一清洗为 envelope/block。

任务:

1. 图片 OCR 输出从 Markdown 升级为 block list。
2. 飞书聊天记录按消息、说话人、时间拆 block。
3. 音频转录按语义段落和时间戳拆 block。
4. PDF/文档按标题、段落、表格拆 block。
5. 为每个 block 生成质量卡。
6. 建立 V0 存储目录和索引。

验收:

- 至少支持图片、聊天记录、飞书文档、音频转录四类输入。
- 每个 block 能追溯到原始文件或原始消息。
- 低质量 block 不直接进入 V1。

### Phase C: 时间与实体锚定

目标: 解决时间错配和标的错配。

任务:

1. 实现四类时间字段。
2. 相对时间解析加入 confidence。
3. 实体链接从“文本识别”升级为“公司/股票/板块标准化”。
4. 对无法解析的时间和实体进入 review 队列。

验收:

- “上周坚定抄底光模块，这周资金回归”能解析为相对时间范围。
- 同一内容中多个时间表达能分别落锚。
- 标的、板块、指数可区分。

### Phase D: V1 Intent 抽取

目标: 先抽投资意图，不急着执行交易。

任务:

1. 从 block/context 生成 `NormalizedInvestmentIntent`。
2. 输出 direction/actionability/position_delta_hint/conviction。
3. 接入 zhiziX/text_analysis 作为附加维度。
4. 保留 ambiguity_notes。
5. 建立 V1 人工复核面板字段。

验收:

- “我看好宁德时代”和“我加仓宁德时代”都看多，但 actionability 和 position_delta_hint 不同。
- “目前依然持有，稍微加仓一点”不会被错误映射为全仓买入。
- V1 输出能追溯到 V0 block/evidence。

### Phase E: Policy 与 TradeAction 映射

目标: 从 intent 进入可回测动作。

任务:

1. 实现 Global Base Policy。
2. 定义 Style Archetype Policy。
3. 定义 Risk Preference Policy。
4. 为 KOL 生成 Persona Policy 草案。
5. 将 intent 映射为 TradeAction。
6. 保留 policy_version 和 mapping_rationale。

验收:

- 同一句“加仓”在不同风格 KOL 下可得到不同持仓期/动作强度假设。
- V1 不放仓位，V2/V3 可按 policy 生成默认仓位假设。
- 所有 policy 映射可审计。

### Phase F: 跨文档时间线与观点状态机

目标: 从“动作列表”升级为“观点演化”。

任务:

1. 实现同一 KOL 同一标的 linking。
2. 维护 `ViewpointState`。
3. 支持观点反转、增强、减弱、暂停、退出。
4. 支持多 KOL 同标的分歧视图。

验收:

- 可展示腾讯从“不看好 600”到“500 附近逐渐加仓”的演化。
- 可展示福寿园从“现金模式看好”到“财报不及预期减仓”的演化。
- 可对同一标的聚合多个 KOL 的不同观点。

### Phase G: 回测闭环与评分

目标: 将 V3 TradeAction 真正接入 L8 回测和 KOL 评分。

任务:

1. pipeline L8 接入现有 BacktestEngine。
2. 明确 effective_trade_time 和交易价格选择规则。
3. 支持单 KOL、同标的多 KOL、共识策略回测。
4. KOL 评分从 mock/后验文件升级为真实 pipeline 输出。
5. 将回测结果回写 intent/action/profile。

验收:

- 指定 KOL + 时间范围可一键生成 timeline 和 backtest。
- 回测结果能回溯到 intent、block、原文证据。
- KOL 评分不是 mock 数据。

---

## 10. 近期优先级建议

### P0: 必须先做

1. V0/V1 schema 契约。
2. 图片/聊天/文档/音频的 V0 标准化 MVP。
3. 四类时间戳和质量卡。
4. Intent 层拆分。

### P1: 紧随其后

1. Policy 分层。
2. Persona 生成。
3. V1 -> TradeAction 映射。
4. 前端 review 面板支持 V0/V1 证据链。

### P2: 再做

1. 跨文档观点状态机。
2. 多 KOL 同标的分歧图谱。
3. 回测 pipeline 闭环。

### P3: 数据稳定后做

1. SFT/DPO 训练。
2. 本地模型替代部分 API 调用。
3. 自动 policy 优化。

---

## 11. 立即可执行的下一批任务

建议下一轮任务拆成 5 个 PR/任务包:

1. `schema-v0-content-envelope`
   - 新增 V0 schema 和样例。
   - 不改现有 pipeline。

2. `schema-v1-investment-intent`
   - 新增 intent schema。
   - 写腾讯/宁德时代/福寿园示例单测。

3. `v0-image-chat-normalizer`
   - 图片 OCR 和飞书聊天先进入 envelope/block。
   - 优先覆盖你当前实际数据。

4. `quality-temporal-anchors`
   - 质量卡和时间锚。
   - 先规则 + LLM fallback。

5. `intent-extraction-prototype`
   - 从 V0 block 生成 V1 intent。
   - 暂不训练，只用 API + schema validation + review。

---

## 12. 判断标准

如果一个改造不能回答下面任一问题，就不应优先做:

1. 这条交易动作来自哪段原始证据？
2. 这个时间是发布时间、提及时间，还是交易生效时间？
3. 这个 KOL 的“加仓”在他的个人语境中代表什么？
4. 这个 intent 是观点、隐式动作，还是明确动作？
5. 这个样本质量是否足够进入模型训练？
6. 这个回测结果能否回溯到原始 KOL 内容？

---

## 13. 总结

Finer 当前已经具备较多模块，但架构上缺少两个关键中间层:

1. V0: 复杂原始内容的标准化内容层。
2. V1: 自然语言投资观点的标准化意图层。

在这两层稳定前，不建议把重点放在大规模训练或自动交易 policy 优化上。正确顺序是先让数据可审计、可追溯、可复核，再让模型从高质量样本中学习。

