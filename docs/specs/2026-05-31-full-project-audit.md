# Finer OS 全项目审阅文档

> **审阅日期**: 2026-05-31
> **基准 commit**: `38cc6484` (main HEAD)
> **工作区状态**: dirty — 12 files modified, 6 untracked
> **代码规模**: Python 58k LOC (src/finer) + 37k LOC (tests) + TypeScript 17k LOC (dashboard)

---

## 1. 概述

Finer OS 是一条 AI-native 投研自动化流水线，目标是将 KOL 社交媒体内容转化为结构化、可回测、可审计的投资事件。系统设计了 F0-F8 共 9 个 canonical stage，当前 **F0→F3→F4→F5→F8 主链路已形成可运行 MVP**，但存在两套并行的执行路径（canonical vs legacy）尚未完全收敛。

**一句话判断**: 后端核心 pipeline 已具备从内容接入到回测输出的端到端能力，Schema 设计成熟且自洽；但 legacy 路由仍在服务前端，F1/F1.5/F2 中间层尚未接入主链路，工作区有未提交改动。

---

## 2. F-Stage 逐层现状

### F0 Intake — `ingestion/`

| 维度 | 状态 |
|------|------|
| 实现完整度 | **高** |
| 渠道覆盖 | 飞书 (`feishu_poller.py`)、B站 (`bilibili_adapter.py`)、微信公众号 (`wechat_adapter.py`)、微信视频号 (新增, `wechat_adapter.py:1354+`)、NotebookLM (`nlm_sync.py`)、本地上传 |
| 核心 Schema | `ContentRecord` (`schemas/content.py`) — 已稳定 |
| Project Memory | SQLite 热索引 (`services/project_memory/`) — 12 个模块，含 migration 框架、integrity checker、artifact store |
| Import Console | `api/routes/f0_index.py` (256 行) — 展示导入状态和索引健康 |
| 测试覆盖 | `test_f0_contract.py`, `test_f0_project_memory.py`, `test_bilibili_f0_contract.py`, `test_wechat_f0_contract.py`, `test_wechat_channels_f0.py` |

**关键发现**:
- 微信视频号接入 (`wechat_adapter.py:1354+`) 边界清晰，只做 F0 import，不跨 F1-F8。方向正确。
- `scripts/wx_channels_download/` 是外部 Go 项目，含 `pkg/certificate/certs/private.key` — **敏感文件，禁止 git add**。
- Project Memory 抽象层完整（object_store → block_store → artifact_store → asset_index → identity → integrity），但依赖 SQLite 做热索引，重建逻辑在 `scripts/project_memory_backfill.py`。

### F1 Standardize — `parsing/`

| 维度 | 状态 |
|------|------|
| 实现完整度 | **中高** — 4 个 canonical adapter + router 已实现 |
| 核心 Schema | `ContentEnvelope`, `ContentBlock`, `BlockQuality`, `BlockProvenance` (`schemas/content_envelope.py`) |
| 标准化 Router | `standardization_router.py` — 按 source_type 路由到对应 adapter |
| Adapter 列表 | `feishu_chat_standardizer.py`, `manual_text_standardizer.py`, `image_ocr_standardizer.py` (MiMo-V2.5), `pdf_standardizer.py` |
| Vision/OCR | `vision_extractor.py` + `mimo_asr_client.py` — 固定使用 `mimo-v2.5`，不启用视觉模型 fallback |
| 测试覆盖 | `test_f1_standardization_router.py`, `test_f1_standardization_fixtures.py`, `test_content_standardizer.py`, `test_image_ocr_layout_standardizer.py`, `test_pdf_document_standardizer.py` |

**关键发现**:
- F1 契约已重置（详见 `docs/specs/f1-standardization-contract.md`），新代码必须输出 canonical `ContentEnvelope + ContentBlock[]`。
- 旧 `SegmentRecord`、L3 perception 路径与 canonical F1 混杂 — `services/perception.py` 仍被 `pipeline/orchestrator.py` 的 `_run_l3()` 调用。
- F1 → F1.5 的连接已定义（ContentEnvelope → TopicAssembler），但未在 canonical pipeline 中自动串联。

### F1.5 Topic Assembly — `parsing/topic_assembler.py`

| 维度 | 状态 |
|------|------|
| 实现完整度 | **中** — 规则版 baseline + LLM adapter 存在，未接入主链路 |
| 核心 Schema | `TopicBlock`, `TopicAssemblyResult` (`schemas/topic_block.py`) |
| 实现路径 | 规则版 `topic_assembler.py` (baseline/fallback) + `llm_topic_assembly_adapter.py` (constrained LLM) |
| 测试覆盖 | `test_topic_assembler.py`, `test_topic_block_schema.py`, `test_llm_topic_assembly_adapter.py`, `test_cat_lord_topic_assembly_llm.py` |

**关键发现**:
- F1.5 设计明确：只做语义 topic assembly，不解析 F1 原始格式细节。
- 但 canonical pipeline (`canonical_runner.py`, `golden_path.py`) **跳过了 F1.5 和 F2**，直接从 ContentEnvelope 进入 F3。这意味着当前 MVP 的 evidence_span_ids 是由 F3 intent extractor 自行生成的，而非来自 F2 的独立锚定。

### F2 Anchor — `enrichment/`

| 维度 | 状态 |
|------|------|
| 实现完整度 | **低** — Schema 完整，实现碎片化 |
| 核心 Schema | `QualityCard` (`schemas/quality.py`), `TemporalAnchor` (`schemas/temporal.py`), `EntityAnchor` (`schemas/entity_anchor.py`), `EvidenceSpan` (`schemas/evidence.py`) |
| 实现文件 | `enrichment/market_context.py`, `enrichment/sentiment_fusion.py` — 聚焦市场数据融合，不是 canonical entity anchoring |
| Quality Gate | `services/quality_gate.py` — 评估 ContentEnvelope 是否满足 F3 入门条件。**已接入 canonical pipeline**（uncommitted change）。 |

**关键发现**:
- F2 是当前最大的架构空洞。Schema 定义完整（QualityCard 有 7 个维度分数 + gate_status），但缺少独立的 canonical entity resolver / temporal resolver / evidence span generator。
- `entity_registry.py` 存在（硬编码的 ticker/company 映射表），但不是完整的 F2 实体锚定引擎。
- Quality Gate (`services/quality_gate.py`) 虽然逻辑上属于 F2，但已被 canonical_runner 和 golden_path 在 F3 前调用 — 这是正确的。

### F3 Intent — `extraction/intent_extractor.py`

| 维度 | 状态 |
|------|------|
| 实现完整度 | **高** |
| 双轨实现 | `RuleBasedIntentExtractor` (keyword baseline, 确定性) + `LLMIntentExtractor` (ModelRouter + PromptRegistry) |
| 核心 Schema | `NormalizedInvestmentIntent` (`schemas/investment_intent.py`) |
| LLM 基础设施 | `llm/router.py` (ModelRouter), `prompts/registry.py` (PromptRegistry, Jinja2 模板) |
| 输出契约 | `IntentExtractionResult` — 含 intents + evidence_spans + processing_notes |
| 测试覆盖 | `test_intent_extractor.py`, `test_intent_extractor_canonical.py`, `test_investment_intent_schema.py`, `test_model_router.py`, `test_prompt_registry.py` |

**关键发现**:
- F3 严格遵守了「Intent ≠ Action」原则：`NormalizedInvestmentIntent` 不含 position_size / stop_loss / target_price / TradeAction。
- `actionability` 字段区分 opinion / watch / explicit_action / review_required — 语义粒度足够。
- `position_delta_hint` 是 hint 而非 instruction — 设计正确。
- `IntentExtractionResult` 同时返回 `evidence_spans`，但这些 span 是 F3 自行生成的，不是来自独立 F2 层 — **F2 缺失的直接后果**。

### F4 Policy — `policy/`

| 维度 | 状态 |
|------|------|
| 实现完整度 | **中高** — GlobalBasePolicy 完整，上层 policy layers 未实现 |
| 核心 Schema | `PolicyMappingResult`, `PolicyMappedIntent`, `PolicyDecision`, `PolicyLayerTrace`, `PolicyRiskConstraints`, `PolicyContext` (`schemas/policy.py`, 670 行) |
| 实现 | `policy_mapper.py` (PolicyMapper) + `global_base.py` (GlobalBasePolicy) |
| Policy Layers 设计 | 5 层：GlobalBase → StyleArchetype → RiskPreference → KOLPersona → ContentCorrection — **仅 GlobalBase 已实现** |
| 测试覆盖 | `test_policy_mapper.py`, `test_policy_schema.py` |

**关键发现**:
- F4 Schema 设计高质量：每个 PolicyMappingResult 必须引用 valid F3 intent_id，不修改原始 direction，所有 hints（action_hint / position_sizing_hint / holding_period_hint）明确是 hint 而非 execution fact。
- PolicyLayerTrace 提供了完整的审计链，每层 policy 的 modifications 都被记录。
- 但 StyleArchetype / RiskPreference / KOLPersona / ContentCorrection 四层尚未实现 — 意味着所有 intent 走同一条 GlobalBase 规则，不区分 KOL 风格和风险偏好。

### F5 Execute — `extraction/canonical_action_builder.py` + `pipeline/canonical_runner.py`

| 维度 | 状态 |
|------|------|
| 实现完整度 | **高** — 两条路径均可用 |
| 路径 A | `CanonicalActionBuilder.build()` — 接受 structured inputs (Intent + PolicyMappedIntent + evidence_span_ids + ExecutionTiming)，产出 canonical TradeAction |
| 路径 B | `canonical_runner.py` — `run_canonical_from_artifacts()` (canonical) / `run_canonical_extraction()` (deprecated, 从 raw text) |
| 路径 C | `golden_path.py` — `run_golden_path(envelope)` 串联 F3→F4→F5 + artifact 写入 |
| 核心 Schema | `TradeAction` + `ExecutionTiming` (`schemas/trade_action.py`, 957 行) |
| Legacy | `trade_action_extractor.py` — 直接从文本生成 TradeAction（**所有公开方法已添加 DeprecationWarning，uncommitted**） |
| 测试覆盖 | `test_canonical_action_builder.py`, `test_canonical_f3_f4_f5_contract.py`, `test_golden_path.py`, `test_timing_builder.py`, `test_execution_timing_policy.py` |

**关键发现**:
- **TradeAction Schema 是整个项目设计质量最高的模型**（957 行）。`canonical_trace_status` 通过 model_validator 自动计算（intent_id + policy_id + evidence_span_ids + execution_timing 全部存在 → "canonical"），确保了 trace 完整性的自动校验。
- `ExecutionTiming` 严格区分四个时钟（intent_published_at / intent_effective_at / action_decision_at / action_executable_at），这对回测防止前视偏差至关重要。
- `CanonicalActionBuilder` 通过 `_validate_types()` 拒绝 raw text / dict 输入，强制 structured-only — 架构边界守卫正确。
- `canonical_runner.py` 提供了两种 F5 策略：programmatic（确定性，无 LLM）和 llm_guided（LLM 辅助 + policy context backfill）。

### F6 Review — `api/routes/rlhf.py`

| 维度 | 状态 |
|------|------|
| 实现完整度 | **中** — API 存在，但仍读取 legacy 目录 |
| 核心功能 | RLHF 反馈收集、human review queue |
| 问题 | `rlhf.py:343` 仍读取 `L0_ingestion/extractions` legacy 目录 |

### F7 Timeline — `timeline/`

| 维度 | 状态 |
|------|------|
| 实现完整度 | **低** |
| 核心 Schema | `KOLTimeline`, `ViewpointState` (`timeline/models.py`) |
| 实现 | `timeline/engine.py` — 基础时间线构建 |
| 测试覆盖 | `test_timeline.py` |

### F8 Backtest — `backtest/`

| 维度 | 状态 |
|------|------|
| 实现完整度 | **高** — E2E 可运行 |
| 核心模块 | `engine.py` (625+ 行, 完整的 portfolio simulation), `converter.py`, `validators.py`, `prices.py`, `storage.py` |
| API 端点 | `api/routes/backtest.py` (499 行) — `/run`, `/compare`, `/results`, `/delete` |
| Validator | `validators.py` — 统一 canonical action 校验 (intent_id + policy_id + evidence_span_ids + execution_timing) |
| E2E 验证 | `scripts/run_backtest_e2e.py` — Cat Lord (7 actions → 5 trades) + Trader Ji (10 actions → 3 trades) 均成功 |
| Storage | `storage.py` — 统一保存到 `data/review/{kol}/F8_backtest`，兼容读取 `data/F8_metrics` |
| 测试覆盖 | `test_backtest.py`, `test_backtest_canonical.py`, `test_backtest_extended.py`, `test_backtest_materializer.py` |

**关键发现**:
- F8 engine 设计完整：支持 long/short、commission/slippage、stop-loss/take-profit、max holding days。
- Trace retention 已实现：Position / Trade 带 intent_id, policy_id, evidence_span_ids。
- Canonical reject 统一使用 `FinerError(F8_IN_001)` — HTTP 400（非 422）。CATEGORY_STATUS 定义中 `"IN": 400`，这是自洽的（IN = invalid input → 400）。如果项目要求 schema violation 用 422，需要改 error code category 为 SCHEMA（`"SCHEMA": 422`）。

---

## 3. 错误反馈系统 (Line F)

| 维度 | 状态 |
|------|------|
| Error Code Catalog | `errors/codes.py` — 93 个 error codes，覆盖 SYS/API/F0-F8/LLM/WX/BILI/FEISHU/NLM |
| Error Envelope | `errors/exceptions.py` — FinerError 基类，to_payload() 输出 `{ok, error: {code, message, details}}` |
| HTTP Status 映射 | `CATEGORY_STATUS` dict — IN→400, AUTH→401, PERM→403, NTF→404, SCHEMA/PARSE/POLICY→422, EXT→502, TMO→504 |
| Error Handler | `errors/handler.py` — FastAPI exception handler 注册 |
| Frontend Contract | `contracts.ts` — `ApiErrorEnvelope` 类型与后端对齐 |

**关键发现**:
- Error code 设计质量高：每个 code 有 `ErrorCodeInfo` 包含 title, root_cause, fix_hint。
- `CATEGORY_STATUS` 映射一致且合理。
- 但大量 legacy 路由仍使用裸 `HTTPException` 而非 `FinerError` — 需要逐步迁移。

---

## 4. 双轨执行路径分析

**这是当前项目最核心的架构矛盾。**

### Canonical Path (新)

```
ContentEnvelope → QualityGate → F3 IntentExtractor → F4 PolicyMapper → F5 CanonicalActionBuilder → F8 BacktestEngine
```

入口点:
- `pipeline/canonical_runner.py` → `run_canonical_from_artifacts()` (结构化输入)
- `pipeline/golden_path.py` → `run_golden_path(envelope)` (单 envelope MVP)
- `pipeline/canonical_runner.py` → `run_canonical_extraction()` (raw text, **deprecated**)

产出: `TradeAction.canonical_trace_status == "canonical"`

### Legacy Path (旧)

```
Raw Text → L5 TradeActionExtractor.extract_from_text() → TradeAction (non_canonical)
```

入口点:
- `pipeline/orchestrator.py` → `PipelineOrchestrator.run_full_pipeline()` (L0→L1→L3→L4→L5)
- `extraction/trade_action_extractor.py` → `TradeActionExtractor` (直接 LLM extraction)

产出: `TradeAction.canonical_trace_status == "non_canonical"`

### 当前消费者映射

| 消费者 | 使用路径 | 说明 |
|--------|---------|------|
| `scripts/run_backtest_e2e.py` | Canonical | 读取 `data/review/{kol}/F5_actions` |
| `api/routes/backtest.py` | Canonical | 通过 `validate_canonical_action()` 强制要求 canonical |
| `api/routes/extraction.py` | **Legacy** | 仍调用 `TradeActionExtractor`（uncommitted: batch 端点已标 DEPRECATED） |
| `pipeline/orchestrator.py` | **Legacy** | `_run_l5()` 调用 `TradeActionExtractor.extract_from_text()` |
| `api/routes/kol.py` | **Legacy** | 读取 `L5_candidate` / `L6_annotated` 目录 |
| `api/routes/rlhf.py` | **Legacy** | 读取 `L0_ingestion/extractions` 目录 |
| `api/routes/asset_builder.py` | **Legacy** | 读取 `L3_aligned` / `L4_parsed` / `L5_candidate` 目录 |
| `api/routes/enrichment.py` | **Legacy** | 使用 `L1_enrichment` 目录 |

---

## 5. Schema 依赖链完整性

### Canonical Chain (设计 vs 实现)

```
ContentRecord (F0) ✅ implemented
  └→ ContentEnvelope (F1) ✅ implemented
       └→ ContentBlock + BlockQuality + BlockProvenance (F1) ✅ implemented
            └→ TopicBlock / TopicAssemblyResult (F1.5) ✅ schema exists, ⚠️ not wired into pipeline
                 └→ QualityCard + TemporalAnchor + EntityAnchor + EvidenceSpan (F2) ✅ schema exists, ❌ no canonical resolver
                      └→ NormalizedInvestmentIntent (F3) ✅ implemented
                           └→ PolicyMappingResult (F4) ✅ implemented (GlobalBase only)
                                └→ TradeAction + ExecutionTiming (F5) ✅ implemented
                                     └→ ViewpointState (F7) ⚠️ partial
                                          └→ BacktestResult (F8) ✅ implemented
```

### Schema 自洽性

所有 Schema 定义在 `src/finer/schemas/` 下，使用 Pydantic V2 + `ConfigDict(strict=True)`。关键 cross-reference 验证：

| 引用关系 | 状态 |
|----------|------|
| TradeAction.intent_id → NormalizedInvestmentIntent.intent_id | ✅ 语义一致 |
| TradeAction.policy_id → PolicyMappingResult.policy_id | ✅ 语义一致 |
| TradeAction.evidence_span_ids → EvidenceSpan.evidence_span_id | ✅ Schema 存在，但 F2 resolver 缺失 |
| PolicyMappingResult.intent_id → NormalizedInvestmentIntent.intent_id | ✅ 强制 min_length=1 |
| PolicyMappedIntent.policy_id → PolicyMappingResult.policy_id | ✅ 强制 min_length=1 |
| NormalizedInvestmentIntent.envelope_id → ContentEnvelope.envelope_id | ✅ 语义一致 |

### 前后端 Schema 同步

`src/finer_dashboard/src/lib/contracts.ts` (1190 行, 59 exports) 与后端 Pydantic models 对齐度:
- `ApiErrorEnvelope` ↔ `FinerError.to_payload()` — ✅ 完全对齐
- `TradeAction` 前端类型 — ⚠️ 需验证是否包含 intent_id / policy_id / canonical_trace_status 新字段
- `BacktestResult` 前端类型 — ⚠️ 需验证 trace retention 字段

---

## 6. API 路由审计

### 路由规模

22 个 route 模块，总计 8001 行。

| 模块 | 行数 | F-stage | 状态 |
|------|------|---------|------|
| `rlhf.py` | 666 | F6 | legacy 目录引用 |
| `opinions.py` | 628 | F7 | — |
| `bilibili.py` | 613 | F0 | — |
| `wechat.py` | 597 | F0 | — |
| `files_utils.py` | 585 | cross | legacy L-stage 目录映射 |
| `asset_builder.py` | 560 | cross | **大量 legacy 目录引用** |
| `backtest.py` | 499 | F8 | canonical — 使用 validators.py |
| `kol.py` | 451 | F7/F8 | **legacy L5/L6 目录引用** |
| `extraction.py` | 378 | F5 | **legacy extractor 调用** |

### Legacy 目录引用热图

| Legacy 目录 | 引用文件数 | 说明 |
|-------------|-----------|------|
| `L5_candidate` | 3 (kol.py, orchestrator.py, asset_builder.py) | 旧 F5 输出目录 |
| `L6_annotated` | 2 (kol.py, asset_builder.py) | 旧 F6 输出目录 |
| `L1_enrichment` | 2 (enrichment.py, asset_builder.py) | 旧 F2 输出目录 |
| `L0_ingestion` | 1 (rlhf.py) | 旧 F0 输出目录 |
| `L3_aligned` | 1 (asset_builder.py) | 旧 perception 输出 |
| `L4_parsed` | 1 (asset_builder.py, orchestrator.py) | 旧 aggregation 输出 |

---

## 7. 测试覆盖分析

### 测试规模

- 测试文件: 80+
- 测试行数: 36,870 LOC
- 已知通过: 171 passed (关键子集)
- E2E: Cat Lord + Trader Ji 双 KOL 回测通过

### 按 F-stage 覆盖

| F-stage | 测试文件数 | 关键测试 |
|---------|-----------|---------|
| F0 | 12 | f0_contract, f0_project_memory, bilibili_f0_contract, wechat_f0_contract, wechat_channels_f0 |
| F1 | 8 | f1_standardization_router, f1_standardization_fixtures, content_standardizer, image_ocr, pdf |
| F1.5 | 4 | topic_assembler, topic_block_schema, llm_topic_assembly_adapter, cat_lord_topic_assembly_llm |
| F2 | 2 | enrichment, quality_gate |
| F3 | 3 | intent_extractor, intent_extractor_canonical, investment_intent_schema |
| F4 | 2 | policy_mapper, policy_schema |
| F5 | 5 | canonical_action_builder, canonical_f3_f4_f5_contract, golden_path, timing_builder, execution_timing_policy |
| F6 | 1 | (covered by API tests) |
| F8 | 4 | backtest, backtest_canonical, backtest_extended, backtest_materializer |
| cross | 6 | schemas, errors, security, auth, model_router, prompt_registry |

### 测试空白

- **F2 Anchor**: 无独立的 entity resolver / temporal resolver 测试（因为实现本身缺失）
- **F7 Timeline**: 仅 `test_timeline.py` 一个测试文件
- **F6 RLHF**: 无独立测试文件，依赖 API route 级别测试
- **前端**: 无测试文件（预期通过 `npm run build` + TypeScript 类型检查覆盖）

---

## 8. 当前工作区状态

### Uncommitted Changes (12 files)

| 文件 | 变更性质 | 评估 |
|------|---------|------|
| `CLAUDE.md` | +3 行 | 规范补充 |
| `extraction/trade_action_extractor.py` | +21 行 | 4 个公开方法添加 DeprecationWarning — **正确方向** |
| `pipeline/canonical_runner.py` | +11 行 | deprecated 路径添加 Quality Gate — **正确** |
| `pipeline/golden_path.py` | +11 行 | golden_path 添加 Quality Gate — **正确** |
| `pipeline/orchestrator.py` | +1 行 | 微小 |
| `api/routes/extraction.py` | +1 行 | batch 端点标 DEPRECATED — **正确** |
| `tests/test_auth.py` | +1 行 | — |
| `tests/test_extraction.py` | +5/-2 行 | — |
| `tests/test_market_data_*.py` | +4 行 each × 4 文件 | — |

**评估**: 所有 uncommitted changes 方向正确（Quality Gate 接入、legacy deprecation），应提交。

### Untracked Files

| 路径 | 处置建议 |
|------|---------|
| `docs/research/` | 可提交（研究文档） |
| `docs/specs/2026-05-wx-channels-dependency-policy.md` | 可提交（spec 文档） |
| `scripts/wx_channels_download/` | **禁止整体 add** — 含 private.key |
| `tests/test_canonical_runner_quality_gate.py` | 应提交（新测试） |
| `tests/test_legacy_quarantine.py` | 应提交（legacy 隔离测试） |

---

## 9. 架构评估

### 设计优势

1. **Schema-first 方法论**: 所有 20 个 Schema 模块使用 Pydantic V2 strict mode，字段描述完整，validator 自动计算派生状态（如 canonical_trace_status）。这是整个项目最强的基础设施。

2. **四时钟模型**: `ExecutionTiming` 的 intent_published_at / intent_effective_at / action_decision_at / action_executable_at 设计精确，防止了回测中的前视偏差。

3. **审计链设计**: F3 intent_id → F4 policy_id → F5 evidence_span_ids 的三重追溯链，加上 PolicyLayerTrace 的 per-layer audit，使得每个 TradeAction 的决策过程完全可追溯。

4. **Error Code Catalog**: 93 个 stable error codes，每个带 title/root_cause/fix_hint，前端 contracts 已对齐。比大多数同规模项目的错误处理成熟度高一个量级。

5. **Quality Gate as Pre-F3 Guard**: 在 F3 之前设置 quality gate 评估 ContentEnvelope，避免低质量内容浪费 LLM 资源。

### 设计弱点

1. **F2 空洞**: F2 是 canonical pipeline 中唯一没有独立实现的 stage。当前 evidence spans 由 F3 自行生成，temporal anchors 由 timing_builder 估算，entity anchors 依赖硬编码 registry — 都不是独立的 F2 锚定。这意味着 canonical_trace_status 虽然是 "canonical"，但 evidence 质量取决于 F3 的自我评估而非独立验证。

2. **双轨共存未隔离**: canonical 和 legacy 路径在同一个 codebase 中共存，前端仍通过 legacy 路由获取数据。没有 feature flag 或路由前缀隔离。Agent 容易误接 legacy 路径当 canonical 主线。

3. **F4 单层 Policy**: 只有 GlobalBasePolicy，缺少 StyleArchetype / RiskPreference / KOLPersona / ContentCorrection。所有 KOL 走同一条规则，不区分交易风格差异 — 这限制了回测的区分度。

4. **前端契约同步风险**: `contracts.ts` 有 1190 行 / 59 exports，但后端 Schema 持续演化（如 canonical_trace_status、ExecutionTiming 是较新字段）。没有自动生成机制，依赖手动同步。

### 架构建议优先级

| 优先级 | 建议 | 理由 |
|--------|------|------|
| P0 | 提交当前 uncommitted changes | Quality Gate 和 deprecation 标记方向正确，不提交会丢失 |
| P0 | 将 `scripts/wx_channels_download/` 加入 `.gitignore` | 含 private.key，安全风险 |
| P1 | 为 legacy API 路由添加 `/legacy/` 前缀或 `X-Finer-Canonical: false` header | 隔离双轨，防止 agent 误用 |
| P1 | 实现 F2 minimal viable entity resolver | 让 evidence_span_ids 来自独立验证而非 F3 自我生成 |
| P2 | 添加 StyleArchetype policy layer | 最少实现两种 KOL 风格的差异化 policy |
| P2 | 添加 contracts.ts 自动生成 | 从 Pydantic models 自动生成 TypeScript types |
| P3 | 将 F1.5 接入 canonical pipeline | 对长文内容的 topic-level 粒度回测有价值 |

---

## 10. 核心文件索引（Agent 速查）

### Pipeline 入口点（按推荐度排序）

| 用途 | 文件 | 函数/类 | 说明 |
|------|------|---------|------|
| 单 envelope 全链路 | `pipeline/golden_path.py:50` | `run_golden_path(envelope)` | **推荐**: F3→F4→F5 + artifact 写入 |
| 结构化输入批量 | `pipeline/canonical_runner.py:128` | `run_canonical_from_artifacts()` | 接受 intents + policy_batch + evidence_spans |
| Raw text (deprecated) | `pipeline/canonical_runner.py:201` | `run_canonical_extraction()` | 仅 backward compatibility |
| Legacy L0-L5 | `pipeline/orchestrator.py:132` | `PipelineOrchestrator` | **已废弃，不要扩展** |

### Schema 定义（按 F-stage）

| Schema | 文件 | 行数 | 关键字段 |
|--------|------|------|---------|
| ContentRecord | `schemas/content.py` | — | content_id, source_type, raw_path |
| ContentEnvelope | `schemas/content_envelope.py` | — | envelope_id, blocks[], quality_card, temporal_anchors[], entity_anchors[] |
| TopicBlock | `schemas/topic_block.py` | — | topic_id, source_block_ids[], topic_label |
| QualityCard | `schemas/quality.py` | — | 7 dimension scores + overall_score + gate_status |
| EvidenceSpan | `schemas/evidence.py` | — | evidence_span_id, text, block_id, start_offset, end_offset |
| NormalizedInvestmentIntent | `schemas/investment_intent.py` | 419 | intent_id, target_*, direction, actionability, position_delta_hint, conviction, confidence |
| PolicyMappingResult | `schemas/policy.py` | 670 | policy_id, intent_id, action_hint, position_sizing_hint, holding_period_hint, risk_constraints |
| TradeAction | `schemas/trade_action.py` | 957 | trade_action_id, intent_id, policy_id, evidence_span_ids, execution_timing, canonical_trace_status |
| ExecutionTiming | `schemas/trade_action.py:392` | — | 四时钟: intent_published_at, intent_effective_at, action_decision_at, action_executable_at |

### LLM / Model 基础设施

| 模块 | 文件 | 说明 |
|------|------|------|
| LLM Client | `llm/client.py` | 统一 LLM 调用封装 |
| Model Router | `llm/router.py:35` | 按任务路由到不同模型（GLM-5.1 / Qwen / MiMo） |
| Prompt Registry | `prompts/registry.py:33` | Jinja2 模板管理，F3 使用 |
| DeepSeek Client | `llm/deepseek_client.py` | DeepSeek 模型客户端 |
| Model Config | `ml/model_config.py` | 模型注册表，含 SVIPS / DashScope 配置 |

### 外部服务集成

| 服务 | 文件 | F-stage |
|------|------|---------|
| Finance-Skills | `services/finance_skills_client.py` | F2/F5 — 金融数据 + TTL 缓存 |
| iFind | `utils/ifind_client.py` | F2 — 行情数据 |
| MiMo-V2.5 | `parsing/vision_extractor.py` | F1 — Vision/OCR |
| FunASR | `parsing/funasr_client.py` | F1 — 语音识别 |
| wechat-article-exporter | `ingestion/wechat_exporter_client.py` | F0 — 微信公众号 |
| BBDown | `ingestion/bbdown_client.py` | F0 — B站视频下载 |

---

## 11. 已知技术债务清单

| ID | 类型 | 位置 | 描述 | 风险等级 |
|----|------|------|------|---------|
| TD-01 | 安全 | `scripts/wx_channels_download/pkg/certificate/certs/private.key` | 未 gitignore 的私钥文件 | **高** |
| TD-02 | 架构 | `pipeline/orchestrator.py` | 整个 L0-L8 legacy orchestrator 仍可被调用 | 中 |
| TD-03 | 架构 | `api/routes/extraction.py` | extraction API 仍调用 legacy TradeActionExtractor | 中 |
| TD-04 | 数据 | `api/routes/kol.py`, `rlhf.py`, `asset_builder.py` | 读取 legacy L-stage 目录（L5_candidate, L6_annotated, L0_ingestion） | 中 |
| TD-05 | 架构 | F2 Anchor 层 | 无独立实现，evidence spans 由 F3 自行生成 | 中 |
| TD-06 | 架构 | F4 Policy 层 | 仅 GlobalBasePolicy，4 层 policy 未实现 | 低 |
| TD-07 | 工程 | `contracts.ts` | 手动同步 Pydantic → TypeScript，无自动生成 | 低 |
| TD-08 | 工程 | `api/routes/files.py` | CLAUDE.md 标注超 500 行需拆分，实际 322 行已合规 | 无 |
| TD-09 | 架构 | F1.5 Topic Assembly | 已实现但未接入 canonical pipeline | 低 |
| TD-10 | 代码 | `enrichment/` 目录 | 命名暗示 F2，但内容是市场数据融合（更接近 F2.5） | 低 |

---

## 12. 验证命令参考

```bash
# 全量测试
pytest tests/ -v

# 关键链路测试（F3→F4→F5→F8）
pytest tests/test_canonical_action_builder.py tests/test_canonical_f3_f4_f5_contract.py tests/test_golden_path.py tests/test_backtest_canonical.py -v

# F0 契约测试
pytest tests/test_f0_contract.py tests/test_f0_project_memory.py tests/test_wechat_f0_contract.py tests/test_bilibili_f0_contract.py -v

# F1 标准化测试
pytest tests/test_f1_standardization_router.py tests/test_f1_standardization_fixtures.py -v

# E2E 回测
python scripts/run_backtest_e2e.py

# 前端编译检查
cd src/finer_dashboard && npm run build

# Schema 一致性
pytest tests/test_schemas.py tests/test_policy_schema.py tests/test_investment_intent_schema.py tests/test_topic_block_schema.py -v
```

---

## 13. Agent 工作边界速查

**当一个 Agent 进入本仓库时，必须判断自己要修改的文件属于哪个 F-stage，并遵守以下规则:**

| 如果你要修改... | 属于 F-stage | 可调用 | 禁止调用 |
|-----------------|-------------|--------|---------|
| `ingestion/` | F0 | `services/llm.py`, `services/converter.py` | F1-F8 任何模块 |
| `parsing/` | F1 | `services/llm.py`, `services/perception.py` | `extraction/`, `policy/`, `backtest/` |
| `parsing/topic_assembler.py` | F1.5 | `schemas/content_envelope.py`, `schemas/topic_block.py` | F1 raw format parsing |
| `enrichment/` | F2 | `services/finance_skills_client.py`, `entity_registry.py` | `extraction/`, `policy/` |
| `extraction/intent_extractor.py` | F3 | `services/llm.py` | **禁止生成 TradeAction** |
| `policy/` | F4 | 规则引擎（无 LLM） | `extraction/trade_action_extractor.py` |
| `extraction/trade_action_extractor.py` | F5 (legacy) | — | **新主链路禁止依赖** |
| `extraction/canonical_action_builder.py` | F5 (canonical) | `schemas/trade_action.py`, `schemas/policy.py` | raw text |
| `pipeline/canonical_runner.py` | F3→F4→F5 | 所有 F3/F4/F5 模块 | `pipeline/orchestrator.py` |
| `backtest/` | F8 | `schemas/trade_action.py` | F0-F5 模块 |
| `api/routes/` | API 层 | `services/`, `schemas/` | **禁止写业务逻辑** |

---

*审阅完成。本文档基于对 ~30 个核心源文件的直接阅读和项目结构分析生成，独立于参考报告。*
