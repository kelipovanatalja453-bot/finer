# Finer OS 项目全量架构审阅报告

> **状态：Superseded** — 本报告中的关键发现已被后续提交修复。F4 Policy 层已实现 (3b99e81)，TradeAction trace 字段已补全 (da540c8)，F4 spec-code 已对齐 (3b99e81)。**本文件仅作为历史记录保留。** 最新架构以 `docs/ARCHITECTURE.md` 和 `docs/specs/f-stage-contracts.md` 为准。

**日期**：2026-04-28  
**审阅范围**：全项目 130+ Python 文件、60+ TypeScript 文件、29 个测试文件、配置与文档

---

## 1. 项目总览

Finer OS 是一个 AI-native 投研自动化流水线，目标是将 KOL 社交媒体内容（飞书群聊、B站视频、微信公众号文章、NotebookLM 笔记）转化为结构化、可回测、可审计的投资事件。

**技术栈**：Python 3.11+ (FastAPI + Pydantic V2) | TypeScript (Next.js 16 + React 19 + TailwindCSS 4) | SQLite + 文件系统存储

**当前规模**：
- Python 源文件：~110 个（不计 `__pycache__`）
- TypeScript 源文件：~60 个
- API 端点：~90 个（22 个路由模块）
- 测试用例：619 passed / 21 skipped / 0 failed
- 代码行数：Python ~25,000+ 行，TypeScript ~8,000+ 行

---

## 2. 分层架构梳理

### 2.1 F-Stage 流水线全景

```
F0 Intake ──→ F1 Standardize ──→ F2 Anchor ──→ F5 Execute ──→ F6 Review ──→ F8 Backtest
 (ingestion)    (library)         (enrichment)   (extraction)    (review)       (backtest)
```

| Stage | 工作流名 | 数据目录 | 核心模块 | API 端点数量 |
|-------|---------|---------|---------|------------|
| F0 Intake | `intake` | `data/raw/`, `data/L0_ingest/` | `ingestion/orchestrator.py`, `feishu_poller.py`, `bilibili_adapter.py`, `wechat_adapter.py`, `classifier.py` | ~12 |
| F1 Standardize | `library` | `data/processed/manifests/` | `parsing/content_standardizer.py`, `parsing/vision_extractor.py`, `parsing/audio_extractor.py` | 3 |
| F2 Anchor | `enrichment` | `data/L1_enrichment/` | `enrichment/market_context.py`, `enrichment/sentiment_fusion.py` | 8 |
| F5 Execute | `extraction` | `data/L5_candidate/` | `extraction/extractor.py`, `intent_extractor.py`, `enriched_extractor.py`, `trade_action_extractor.py` | 4 |
| F6 Review | `review` | `data/L6_annotated/`, `data/rlhf/` | API routes `review.py`, `rlhf.py` | 10 |
| F8 Backtest | `backtest` | `data/backtests/`, `data/L8_metrics/` | `backtest/engine.py`, `backtest/prices.py` | 7 |

### 2.2 缺失的 F-Stage

| Stage | 概念定义 | 当前状态 |
|-------|---------|---------|
| F3 Intent | 投资意图标准化（NormalizedInvestmentIntent） | Schema 已定义（`investment_intent.py`），`intent_extractor.py` 可产出 intent，但独立 API 和 UI 视图不完整 |
| F4 Policy | 策略映射与风控规则 | **已实现 (3b99e81)**。`policy/policy_mapper.py` + `policy/global_base.py` + `schemas/policy.py`。StyleArchetype/KOLPersona 策略层待补。 |
| F7 Timeline | 时间线聚合与 KOL 对比 | 后端 `timeline/engine.py` 已实现，`opinion-timeline` 前端组件已实现，但未纳入主工作流导航 |

### 2.3 分层规则遵守情况

- **跨层调用检查**：`parsing/content_standardizer.py` 仅依赖 schema 层和 LLM 服务，不涉及 extraction 层 — 符合规范
- **违规项**：`ingestion/orchestrator.py` 直接调用 `enrichment/` 模块进行话题拆分和实体抽取（同步 Feishu 时）。这属于 F0 调用 F2，违反分层边界。实际情况是 orchestration 需要一站式处理，当前做法是务实折衷，但应在代码中标注 `# cross-layer orchestration`
- API routes 的薄层原则基本遵守，但 `extraction.py` 的 `run_full_pipeline` 端点在 route 中包含了部分编排逻辑

---

## 3. 模块功能详析

### 3.1 数据接入层（F0 Intake）

```
ingestion/
├── orchestrator.py      # 飞书同步主控：拉取消息→下载附件→分类→视觉分析→摘要→manifest→NLM同步→回执
├── feishu_poller.py     # lark-cli CLI 封装，消息拉取与附件下载
├── wechat_adapter.py    # 微信公众号三通道接入（直接API / 导出服务 / 混合）
├── wechat_exporter_client.py  # wechat-article-exporter HTTP 客户端
├── bilibili_adapter.py  # B站视频下载 + DashScope Paraformer 转写
├── bbdown_client.py     # BBDown .NET CLI 备选方案
├── classifier.py        # 5级优先级文件分类器（hashtag → regex → chat → AI → fallback）
├── nlm_sync.py          # NotebookLM 上传同步
├── receipt.py           # 飞书回执消息发送
└── vision_utils.py      # 多模型视觉描述（Qwen-VL-Max → Qwen-VL-Plus → cache fallback）
```

**数据流**：
```
Feishu/B站/微信 → poller → raw files → classifier → manifest → NLM sync
                                ↓
                          vision_utils → 图片描述文本
```

### 3.2 解析层（F1 Standardize）

```
parsing/
├── content_standardizer.py  # 纯规则文本→ContentEnvelope转换（H2章节分组、block类型检测）
├── vision_extractor.py      # Qwen-VL-Max 图片→结构化 Markdown + SegmentRecord
├── audio_extractor.py       # PDF sidecar 音频转文字（DocumentConverter）
├── context_summarizer.py    # LLM 全文摘要 + 滑动窗口局部上下文
├── sentiment_enricher.py    # SnowNLP 中文情感打分（0-1 强度）
├── slang.py                 # 金融黑话→正规实体映射（海公公→海力士，大A→上证）
├── slang_generator.py       # Excel→JSON 黑话字典生成器
├── funasr_client.py         # 本地 FunASR（Apple Silicon MPS 加速）
├── mimo_asr_client.py       # MiMo ASR（OpenAI 兼容 API）
└── mimo_asr_config.py       # MiMo 配置
```

**关键设计决策**：`content_standardizer.py` 采用纯规则引擎，不调用 LLM。这保证了标准化的确定性，避免了 LLM 的不稳定性和 token 成本。Block 类型分类基于 Markdown 语法标记和文本模式。

### 3.3 富化层（F2 Anchor）

```
enrichment/
├── market_context.py    # 市场数据融合（yfinance-data + funda-data）+ 价格区间验证
└── sentiment_fusion.py  # 多源情绪聚合（Reddit/Twitter/News/Polymarket）+ 反向信号检测
```

**数据依赖**：`finance_skills_client.py`（外部 HTTP 服务 `finance-skills.himself65.com`）
- 支持技能：yfinance-data, funda-data, sentiment-analysis, news-aggregator, options-flow
- 缓存策略：market_ttl=60s, fundamentals_ttl=300s, sentiment_ttl=300s
- 特性开关：market_data=true, sentiment=false, strategy=false（P1/P2 未启用）

### 3.4 提取层（F5 Execute）

```
extraction/
├── extractor.py               # Instructor + Qwen 结构化提取（EventWithActions）
├── intent_extractor.py        # 规则引擎：H2 章节分组 + entity_registry 匹配 → NormalizedInvestmentIntent
├── enriched_extractor.py      # 提取+富化一步完成
├── action_interpreter.py      # 提取上下文构建（全局摘要 + 局部上下文 + 黑话标签）
└── trade_action_extractor.py  # GLM-5.1 + Finance-Skills 混合提取 + 置信度路由
```

**四种提取策略对比**：

| 策略 | 模块 | 方法 | 输出 | 适用场景 |
|------|------|------|------|---------|
| Instructor结构化 | `extractor.py` | Instructor + Qwen-Max | EventWithActions | 通用文本提取 |
| 规则引擎 | `intent_extractor.py` | 关键词匹配 + 实体注册表 | NormalizedInvestmentIntent | 快速预筛、无LLM环境 |
| 提取+富化 | `enriched_extractor.py` | 提取后立即富化 | EnrichedEventWithActions | 需要市场数据的一站式场景 |
| 混合提取 | `trade_action_extractor.py` | GLM-5.1 + 外部数据 | TradeAction | 高精度生产环境 |

### 3.5 审核层（F6 Review）

- **`review.py`**：审核结果保存（draft/approved/rejected），输出到 `review_store/` 和 `approved_events/`
- **`rlhf.py`**：RLHF 反馈完整生命周期（提交/查询/更新/导出 DPO 训练数据），8 个端点
- **前端**：`AnnotationWorkbench`（双栏审阅工作站）+ `RLHFReviewPanel`（键盘快捷键驱动的审核面板）

### 3.6 回测层（F8 Backtest）

```
backtest/
├── engine.py  # PortfolioSimulator + BacktestEngine（日频循环、多空双向、止盈止损）
└── prices.py  # PriceProvider Protocol → CachedPriceProvider → Finance-Skills API
                # MockPriceProvider（几何随机游走 + 确定性种子）用于开发
```

**回测配置**：初始资金 100K、单仓上限 10%、总敞口 25%、佣金 0.1%、滑点 0.05%、止损 10%、止盈 20%、做空支持

### 3.7 Schema 体系（真相源）

```
schemas/
├── contract.py            # AssetFile — 前后端统一契约（Pydantic ↔ contracts.ts）
├── content.py             # ContentRecord — L0 摄入记录
├── content_envelope.py    # ContentEnvelope + ContentBlock — V0.5 标准化抽象
├── segment.py             # SegmentRecord — L3 解析片段
├── event.py               # EventWithActions + TradingAction — L5 提取事件
├── enriched_event.py      # EnrichedEventWithActions — 市场数据+情绪融合
├── investment_intent.py   # NormalizedInvestmentIntent — 预 TradeAction 意图抽象
├── trade_action.py        # TradeAction — 权威全生命周期交易动作
├── quality.py             # QualityCard — 六维质量评分 + 自动门控
├── temporal.py            # TemporalAnchor — 时间引用解析
├── entity_anchor.py       # EntityAnchor — 14 类实体解析
├── evidence.py            # EvidenceSpan — 字符级可追踪性
├── lineage.py             # DataLineage + VersionInfo — 完整流水线溯源
├── kol_profile.py         # KOLProfile — 跨平台 KOL 管理
├── text_analysis.py       # 14 维文本分析（zhiziX）
├── bbdown.py              # BBDown CLI 数据模型
└── wechat.py              # 微信集成数据模型
```

**Schema 依赖链**：
```
ContentRecord (L0)
  └→ ContentEnvelope (V0.5) { ContentBlock[], QualityCard, TemporalAnchor[], EntityAnchor[], EvidenceSpan[] }
       └→ SegmentRecord (L3)
            └→ EventWithActions (L5) { TradingAction[] }
                 └→ EnrichedEventWithActions (L5+L1) { MarketDataSnapshot, SentimentSnapshot, StrategyAssessment }
                      └→ NormalizedInvestmentIntent (F3) — 语义抽象
                           └→ TradeAction (L7+) { ActionStep[], MarketEnrichment, DataLineage, BacktestResult, RLHFFeedback }
```

### 3.8 服务层

| 服务 | 文件 | 职责 | 关键特性 |
|------|------|------|---------|
| LLM 客户端 | `llm/client.py` | 统一 LLM 调用 | 多 provider、自动 fallback |
| Finance-Skills | `services/finance_skills_client.py` | 外部金融数据 | TTL 缓存、并行批量、指数退避重试 |
| 摘要生成 | `services/summary_generator.py` | 文件摘要 | 文件哈希缓存、多源时间戳提取 |
| 质量门控 | `services/quality_gate.py` | 内容质量评估 | 三级门控（pass/review/reject）、可配置策略 |
| KOL 管理 | `services/kol_profile.py` | KOL 资料管理 | 跨平台身份映射、JSON 持久化 |
| KOL 评分 | `services/kol_rating_engine.py` | KOL 多维度评分 | 5 维度加权、Morningstar 勋章体系 |
| 溯源追踪 | `services/lineage.py` | 数据溯源 | 全链路追踪（content→segment→event→action→backtest） |
| 性能监控 | `services/performance.py` | 性能预算 | 8 个操作 p50/p95/p99、滚动窗口、预算告警 |
| 版本管理 | `services/versioning.py` | 可复现性 | 配置哈希、prompt 哈希、重提取检测 |
| 感知编排 | `services/perception.py` | 内容感知 | 文档转换→LLM感知→黑话标准化→九宫格评估 |
| 存储 | `services/storage.py` | SQLite 索引 | WAL 模式、线程本地连接、TradeAction 索引 |
| 存储仓库 | `services/repository.py` | 高级查询 | 按 KOL/Ticker/时间线查询、批量查询 |
| 转换器 | `services/converter.py` | 文档转换 | markitdown 封装、优雅降级 |

### 3.9 ML 子系统

```
ml/
├── dpo_trainer.py       # DPO 训练流水线（Qwen2.5-14B + LoRA）
├── export_dpo.py        # DPO 数据导出 CLI
├── kol_scorer.py        # KOL 多维度评分（V1: 5维, V2: 4维）
├── model_config.py      # 模型注册表（YAML 驱动 + 自动 fallback）
└── sentiment/
    ├── analyzer.py      # 多模式情绪分析（规则/LLM/混合）
    ├── emotion_arc.py   # 段落级情绪轨迹（12种情绪类型）
    ├── rules.py         # 规则引擎（关键词+否定检测+增强因子）
    ├── schemas.py       # 情绪子系统 Pydantic 模型
    ├── text_analysis_engine.py  # zhiziX 14维文本分析编排器
    └── text_dimensions/  # 8个独立分析器
        ├── surface_style.py     # 表层风格（代词比、口语化、形式度）
        ├── rhetoric.py          # 修辞手法
        ├── content_structure.py # 内容结构
        ├── argumentation.py     # 论证分析
        ├── cognitive_pattern.py # 认知模式
        ├── rhythm.py            # 文本韵律
        ├── reader_engagement.py # 读者互动
        └── audience_target.py   # 目标受众
```

**注意**：zhiziX 14 维文本分析是一个深度实现，但其产出的 `TextAnalysisResult` 在当前流水线中缺少消费端 — 分析结果未传递给下游 enrichment 或 extraction 模块，也未在前端可视化。

---

## 4. 前端架构

### 4.1 页面结构

```
/ (主页)                             → Sidebar + MainBoard + InspectorPanel
├── F0 Intake                        → grid/list of raw files
├── F1 Standardize                   → grid/list of manifests
├── F2 Anchor (enrichment entities)  → entity folders + topic files
├── F5 Execute (candidate events)    → review payload cards
├── F6 Review                        → approved/needs-review events
└── F8 Backtest                      → backtest artifacts

/kol                                → KOL 列表页
/kol/[id]                           → KOL 详情（timeline + 维度评分 + 收益曲线）
/kol/[id]/backtest                  → 单 KOL 回测结果
/kol/compare                        → 多 KOL 对比
/backtest                           → 回测任务管理
/settings                           → 设置（数据源/KOL管理/系统）
/demo/kol-rating                    → KOL 评分卡片 Demo
```

### 4.2 组件树

```
AppShell
├── Header (所有次级页面共用)
└── main

Layout (主页专用)
├── Sidebar
│   ├── 6 个 workflow 按钮 (F0-F8)
│   ├── Integrations/Sync Hub 入口
│   ├── DataSource 入口
│   └── Pipeline Pulse (GET /api/stats)
├── MainBoard
│   ├── Search + Bell + Avatar
│   ├── SourceFilter + Grid/List toggle + UploadButton
│   └── children (grid/list cards)
├── InspectorPanel (右侧滑出)
│   ├── Selected Asset 卡片
│   ├── Enrichment 关联内容 (F2)
│   ├── Provenance Timeline (F0-F8 步骤指示器)
│   ├── Evidence Readiness
│   ├── Machine Notes
│   ├── Semantic Anchors
│   ├── Physical Paths
│   └── Preview 模态框
└── AnnotationWorkbench (全屏覆盖)
    ├── 左栏：Source Evidence
    │   ├── Content Identity
    │   ├── Evidence Text (高亮)
    │   └── Provenance & Machine Clues
    └── 右栏：Field Correction & Intent Calibration
        ├── Ticker / Time Horizon / Sentiment Bias
        ├── Rationale
        ├── Action Chain Editor
        ├── Reviewer Notes
        └── Save/Action buttons
```

### 4.3 前端 API 代理现状

| 前端代理文件 | 代理目标 | 状态 |
|-------------|---------|------|
| `api/files/route.ts` | `/api/files` | 完整 |
| `api/files/enrichment/[...path]/route.ts` | `/api/files/enrichment/<entity>` | 完整 |
| `api/integrations/[...path]/route.ts` | `/api/integrations/<path>` | 完整 |
| `api/streams/download/route.ts` | `/api/streams/download?path=` | 完整 |
| `api/opinions/[[...path]]/route.ts` | `/api/opinions/<path>` | 完整 |
| `api/wechat/[...path]/route.ts` | `/api/wechat/<path>` | 完整 |
| `api/sources/[...path]/route.ts` | `/api/sources/<path>` | 完整 |
| `api/review/route.ts` | `/api/review` | 完整 |
| `api/stats/route.ts` | `/api/stats` | 完整 |
| **缺失** | `/api/bilibili/*` | **无代理文件** |
| **缺失** | `/api/kol/rating/*` | **无代理文件** |
| **缺失** | `/api/rlhf/*` | **无代理文件** |

BilibiliConfig、KOLRatingCard、RLHFReviewPanel 组件直接 fetch 到 localhost:8000 或使用 mock 数据，存在跨域风险和前后端分离不彻底的问题。

### 4.4 Mock 数据使用情况

| 页面/组件 | 数据来源 | 备注 |
|----------|---------|------|
| 主 Dashboard (page.tsx) | 真实 API | GET /api/files, POST /api/sources/refresh |
| BilibiliConfig | 真实 API | 直接请求 localhost:8000 |
| WeChatConfig | 真实 API | 通过代理 |
| IntegrationsHub | 真实 API | 通过代理 |
| KOLRatingCard | API + mock fallback | 先尝试 GET /api/kol/rating，失败用 mock |
| OpinionTimeline | API + mock fallback | 先尝试 API，失败用 mock |
| RLHFReviewPanel | API | 直接请求 localhost:8000（无代理） |
| KOL 列表/详情/对比 | 纯 mock | `mock-data.ts` 硬编码数据 |
| Backtest 页面 | 纯 mock | 3 个硬编码任务 |
| Settings 页面 | 纯 mock | 硬编码数据源和 KOL 配置 |
| Demo 页面 | 纯 mock | 展示用 |

---

## 5. 测试覆盖

### 5.1 测试统计

```
tests/
├── test_schemas.py                     (673 行) — Schema 序列化/反序列化
├── test_content_envelope_schema.py     (512 行) — ContentEnvelope 契约
├── test_content_standardizer.py        (480 行) — F1 标准化
├── test_enrichment.py                  (635 行) — F2 富化
├── test_extraction.py                  (702 行) — F5 提取
├── test_intent_extractor.py            (296 行) — F3 意图提取
├── test_investment_intent_schema.py    (721 行) — Intent schema
├── test_quality_temporal_evidence_schema.py (789 行) — Quality/Temporal/Evidence
├── test_backtest.py                    (297 行) — F8 回测
├── test_backtest_extended.py           (461 行) — 回测扩展测试
├── test_timeline.py                    (390 行) — F7 时间线
├── test_lineage.py                     (438 行) — 溯源追踪
├── test_sentiment.py                   (345 行) — 情绪分析
├── test_emotion_arc.py                 (327 行) — 情绪轨迹
├── test_quality_gate.py                (470 行) — 质量门控
├── test_performance.py                 (352 行) — 性能监控
├── test_kol_scorer.py                  (602 行) — KOL 评分
├── test_kol_profile.py                 (270 行) — KOL 档案
├── test_auth.py                        (212 行) — 认证
├── test_security.py                    (240 行) — 安全
├── test_aggregation_storage.py         (273 行) — 聚合存储
├── test_cat_lord_fixture_contract.py   (336 行) — 满猫 fixture
├── test_cat_lord_image_fixture_contract.py (332 行) — 图片 fixture
├── test_cat_lord_v0_pipeline.py        (199 行) — V0 流水线
├── test_cat_lord_image_v0_pipeline.py  (195 行) — V0 图片流水线
├── test_cat_lord_pipeline_integration.py (178 行) — 集成测试
└── test_cli_smoke.py                   (16 行) — CLI 冒烟测试
```

**测试金字塔**：619 passed / 21 skipped / 0 failed

- 关键路径模块（schemas, extraction, enrichment, parsing）均有良好覆盖
- 缺少：`ingestion/` 模块的集成测试（依赖外部服务，仅 smoke test）、`ml/` 模块测试
- 21 skipped 主要是需要外部 LLM API key 的测试

---

## 6. 改进建议

### 6.1 高优先级（影响功能正确性和安全性）

#### 6.1.1 补齐缺失的前端 API 代理
**问题**：`BilibiliConfig`、`RLHFReviewPanel`、`KOLRatingCard` 直接请求 `localhost:8000`，缺少 Next.js 代理层。

**建议**：
- 新增 `src/finer_dashboard/src/app/api/bilibili/[...path]/route.ts`
- 新增 `src/finer_dashboard/src/app/api/kol/[...path]/route.ts`
- 新增 `src/finer_dashboard/src/app/api/rlhf/[...path]/route.ts`

#### 6.1.2 数据目录名统一为 F-stage
**问题**：代码使用 `data/L0_ingest`、`data/L1_enrichment` 等旧命名，与 F-stage 架构不一致。

**建议**：
- 保持 `WORKFLOW_BY_TIER` 和 `STAGE_BADGE_BY_WORKFLOW` 映射不变
- 在 `paths.py` 中定义 `WORKFLOW_DIRS` 常量映射：`{"intake": "F0_ingest", "enrichment": "F2_enrichment", ...}`
- 分阶段迁移目录（先新建 F 目录，再逐步废弃旧目录，避免破坏性迁移）

#### 6.1.3 pipeline/orchestrator.py 内部使用 L-stage 命名
**问题**：`src/finer/pipeline/orchestrator.py` 中的 stage 实现函数命名为 `_run_l0_stage`、`_run_l1_stage` 等，与 F-stage 体系不一致。

**建议**：重命名为 `_run_f0_stage`、`_run_f2_stage` 等，数据目录引用改为 `paths.py` 统一管理。

### 6.2 中优先级（影响功能完整性和开发体验）

#### 6.2.1 F3 Intent 和 F4 Policy 层的落地
**问题**（2026-04-29 更新）：F3（Intent）的 schema 和 LLMIntentExtractor 已实现 (4ef6c20)，F4（Policy）的 GlobalBasePolicy / PolicyMapper / schema 已实现 (3b99e81)，F4 spec-code 已对齐 (3b99e81)。剩余缺口：F3 独立 API 和前端视图、F4 StyleArchetype/KOLPersona 高阶策略层。

**后续建议**：
- F3：新增 `api/routes/intent.py`，提供 `/api/intent/extract` 端点；前端 Sidebar 新增 F3 入口
- F4：补全 StyleArchetype/KOLPersona 高阶策略层，新增独立 API 和前端视图

#### 6.2.2 F7 Timeline 纳入主导航
**问题**：Timeline 引擎和后端 API 已实现，`opinion-timeline` 前端组件已完成，但 `/kol/*` 页面独立于六层工作流之外。

**建议**：在 Sidebar 中将 F7 Timeline 添加为第七个工作流入口，`OpinionTimeline` 组件作为 F7 的主视图，替代当前 `/kol/*` 的 mock 页面。

#### 6.2.3 前端 mock 数据替换
**问题**：KOL 列表/详情/对比、Backtest、Settings 页面全部使用硬编码 mock 数据（`mock-data.ts`），用户看到的不是真实数据。

**建议**：
- KOL 列表：已有 `GET /api/kol/list`，直接替换 mock
- KOL 详情：已有 `GET /api/kol/rating/<id>`，替换 mock
- Backtest：已有 `GET /api/backtest/results`、`POST /api/backtest/run`，替换 mock
- Settings 数据源列表：已有 `GET /api/integrations/feishu/chats` 等，替换 mock

### 6.3 低优先级（架构优化和长期改进）

#### 6.3.1 ASR 后端简化
**问题**：三个 ASR 后端（FunASR 本地、MiMo API、DashScope Paraformer），维护成本高。

**建议**：以 MiMo ASR（OpenAI 兼容，部署灵活）为主，Paraformer 保留给 B站视频场景（已集成 DashScope），FunASR 可标记为 deprecated（macOS 本地推理效果不如云端方案）。

#### 6.3.2 提取策略收敛
**问题**：四种提取器（Instructor/Qwen、规则引擎、提取+富化、GLM+Finance-Skills），功能重叠。

**建议**：
- `extractor.py`（Instructor+Qwen）和 `trade_action_extractor.py`（GLM+Finance-Skills）合并为统一的 `ActionExtractor`，通过配置切换后端
- `intent_extractor.py` 作为独立的前置规则预筛层保留
- `enriched_extractor.py` 合并到提取流水线中作为后处理步骤

#### 6.3.3 zhiziX 文本分析的消费端
**问题**：`ml/sentiment/text_analysis_engine.py` 产出的 14 维文本分析结果在当前流水线中无消费端。

**建议**：将 `TextAnalysisResult` 的 `kol_fingerprint` 写入 `KOLProfile`，将 `surface_style` / `rhetoric` 等维度的分数纳入 F6 Review 的参考面板，供审核员参考 KOL 表达特征。

#### 6.3.4 配置管理集中化
**问题**：配置分散在 `config.py`、`model_config.py`、`ml/model_config.py`（两个 model_config 文件）、`ml_models.yaml`、`finance_skills.yaml`、`feishu.yaml`、`wechat.yaml` 等多处。

**建议**：统一为一个 `ConfigManager` 类，加载 `configs/` 下所有 YAML，提供类型安全的属性访问，消除重复的配置定义。

#### 6.3.5 `src/finer/services/repository.py` 的 SQLite 索引与文件系统同步
**问题**：`TradeActionRepository` 使用 SQLite 索引加速查询，但 `save()` 仅写入文件系统且更新索引。如果文件被手动删除或索引损坏，会产生数据不一致。

**建议**：添加 `verify_index()` 方法，定期或在启动时校验索引与文件系统的一致性。在 `rebuild_index()` 中增加异常文件的处理逻辑。

---

## 7. 关键数据流总结

### 7.1 飞书内容完整流程

```
Feishu 群聊
  → lark-cli 拉取消息
  → FeishuPoller.poll_chat()
  → orchestrator.sync_chat()
    ├→ 下载附件 → data/raw/{creator}/unclassified/
    ├→ 判断文件类型 → classifier.classify()
    ├→ 图片 → vision_utils.describe_image()
    ├→ 写 ContentManifest → processed/manifests/
    ├→ NLM 同步 → nlm_sync.sync_file()
    └→ 飞书回执 → receipt.send_sync_receipt()
  → API GET /api/files?tier=F0 可见
```

### 7.2 事件提取完整流程

```
ContentEnvelope (F1标准化产出)
  → intent_extractor.extract_intents_from_envelope()
    → 按 H2 分组 → entity_registry 查实体 → 关键词检测方向 → 计算置信度
    → NormalizedInvestmentIntent[]
  → extractor.extract_events() / trade_action_extractor.extract_from_text()
    → LLM 结构化提取
    → EventWithActions[] { TradingAction[] }
  → enriched_extractor.enrich_events()
    → MarketContextEnricher.enrich_event()
      → finance_skills_client.get_market_data(ticker)
      → PriceRangeValidator.validate(action, market_data)
      → SentimentFusionEnricher.enrich_event()
    → EnrichedEventWithActions
  → TradeAction { ActionStep[], MarketEnrichment, DataLineage }
```

### 7.3 回测流程

```
TradeAction[]
  → TimelineEngine.build_timeline(kol_id)
    → KOLTimeline { entries[], summary }
  → BacktestEngine.run_backtest(kol_id, date_range, config)
    → 日频循环
      → 检查出场条件（止盈/止损/时间/信号反转）
      → 处理新入场
      → 每日快照
    → BacktestResult { total_return, sharpe, max_drawdown, trades[] }
```

---

## 8. 项目健康度评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构设计 | ★★★★☆ | 六层流水线边界清晰，Schema 即真相源，但 F3/F4 未落地、目录命名不一致 |
| 代码质量 | ★★★★☆ | 类型注解完整，Pydantic 验证充分，少量违反了分层规则（orchestrator 跨层调用） |
| 测试覆盖 | ★★★★★ | 619 passed，0 failed，关键路径全覆盖，fixture 测试设计完善 |
| 前后端对齐 | ★★★☆☆ | 核心 API 代理完整，但 3 个前端组件缺少代理，合同层的 contracts.ts 与后端 schema 一致 |
| 数据完整性 | ★★★★☆ | Manifest 系统 + SQLite 索引 + 文件系统三层，但缺少一致性校验 |
| 文档完整度 | ★★★☆☆ | ARCHITECTURE.md 较完善，但模块级 README 缺失，API_REFERENCE.md 仅覆盖部分端点 |
| 部署就绪度 | ★★☆☆☆ | 两个 model_config.py 文件需要合并，无 CI/CD 配置，依赖外部服务（lark-cli, nlm, BBDown） |

---

## 9. 文件路径速查索引

### Schema 层
- `src/finer/schemas/contract.py` — 前后端统一契约 AssetFile
- `src/finer/schemas/content_envelope.py` — ContentEnvelope + ContentBlock
- `src/finer/schemas/trade_action.py` — TradeAction 全生命周期模型
- `src/finer/schemas/investment_intent.py` — NormalizedInvestmentIntent
- `src/finer/entity_registry.py` — 实体注册表（~100+ 条目）

### API 层
- `src/finer/api/server.py` — FastAPI 应用工厂
- `src/finer/api/routes/files.py` — 核心文件 API
- `src/finer/api/routes/files_utils.py` — WORKFLOW_BY_TIER / STAGE_BADGE_BY_WORKFLOW 映射
- `src/finer/api/routes/asset_builder.py` — 资产构建引擎
- `src/finer/api/routes/streams.py` — 文件下载/预览服务

### 流水线层
- `src/finer/ingestion/orchestrator.py` — F0 飞书同步主控
- `src/finer/parsing/content_standardizer.py` — F1 文本标准化
- `src/finer/enrichment/market_context.py` — F2 市场数据融合
- `src/finer/extraction/trade_action_extractor.py` — F5 混合提取
- `src/finer/extraction/intent_extractor.py` — F3 意图提取
- `src/finer/backtest/engine.py` — F8 回测引擎

### 前端层
- `src/finer_dashboard/src/app/page.tsx` — 主 Dashboard 工作流视图
- `src/finer_dashboard/src/components/layout/sidebar.tsx` — 侧边导航
- `src/finer_dashboard/src/components/layout/inspector-panel.tsx` — 资产溯源面板
- `src/finer_dashboard/src/components/studio/annotation-workbench.tsx` — 审阅工作站
- `src/finer_dashboard/src/lib/contracts.ts` — TypeScript 类型定义

### 配置层
- `src/finer/config.py` — 服务配置
- `src/finer/paths.py` — 目录结构定义
- `src/finer/model_config.py` — 模型注册表（多 provider fallback）
- `configs/feishu.yaml` — 飞书群组配置
- `configs/ml_models.yaml` — ML 模型与回测配置
- `configs/finance_skills.yaml` — 外部金融数据服务配置

### 测试
- `tests/test_cat_lord_pipeline_integration.py` — 满猫 fixture 完整流水线集成测试（新增）
- `tests/test_content_standardizer.py` — F1 标准化测试
- `tests/test_extraction.py` — F5 提取测试
- `tests/test_enrichment.py` — F2 富化测试
- `tests/test_schemas.py` — Schema 序列化测试
