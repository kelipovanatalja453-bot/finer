# Finer OS 全项目审阅报告

> **审阅日期**: 2026-06-03
> **审阅范围**: 全量代码、架构、测试、文档、数据
> **代码规模**: Python 188 文件 / 58,466 LOC + 测试 37,094 LOC + TypeScript 93 文件 / ~17k LOC

---

## 一、总体评价

**一句话判断**: Finer OS 是一个架构设计成熟、Schema 基础设施扎实、核心 pipeline 已端到端可运行的投研自动化系统。当前最关键的矛盾是 **canonical 路径（F3→F4→F5）已闭环，但 legacy 路径仍大量服务于前端 API**——两套执行路径共存未隔离，是项目当前最大的架构风险。

**测试健康度**: ✅ 2702 测试中 2687 通过，15 跳过，0 失败

---

## 二、代码规模全景

| 维度 | 数量 | 说明 |
|------|------|------|
| Python 源文件 | 188 | `src/finer/` |
| Python 总行数 | 58,466 | 含注释和空行 |
| Pydantic Schema | 86 models / 6,666 LOC | `schemas/` 目录 |
| API 路由 | 25 模块 / 8,001 LOC | `api/routes/` |
| 测试文件 | 80+ / 37,094 LOC | `tests/` |
| 测试用例 | 2,702 | 2,687 passed, 15 skipped |
| 前端 TS/TSX | 93 文件 | `finer_dashboard/src/` |
| 前端页面 | 17 页 | Next.js App Router |
| 文档 | 114+ md 文件 | `docs/` |
| 类/函数 | 474 classes / 1,707 functions | AST 分析 |
| Error Codes | 93 个 | `errors/codes.py` |

### Top 10 最大源文件

| 文件 | 行数 | F-stage | 说明 |
|------|------|---------|------|
| `ingestion/wechat_adapter.py` | 1,667 | F0 | 微信接入（含视频号） |
| `scripts/project_memory_backfill.py` | 1,461 | F0 | Project Memory 回填 |
| `ml/kol_scorer.py` | 1,185 | F7/F8 | KOL 评分模型 |
| `schemas/trade_action.py` | 956 | F5 | **设计质量最高的 Schema** |
| `services/kol_rating_engine.py` | 934 | F7/F8 | KOL 评级引擎 |
| `ml/dpo_trainer.py` | 912 | F+ | DPO 训练器 |
| `extraction/trade_action_extractor.py` | 873 | F5 (legacy) | Legacy 直提器 |
| `backtest/engine.py` | 868 | F8 | 回测引擎 |
| `parsing/pdf_standardizer.py` | 867 | F1 | PDF 标准化 |
| `ingestion/bbdown_client.py` | 852 | F0 | B站下载客户端 |

---

## 三、F0-F8 逐层审阅

### F0 Intake — `ingestion/` ✅ 实现完整度：高

| 维度 | 评估 |
|------|------|
| 渠道覆盖 | 飞书 ✅ / B站 ✅ / 微信公众号 ✅ / 微信视频号 ✅(新增) / NotebookLM ✅ / 手动上传 ✅ |
| 核心 Schema | `ContentRecord` — 已稳定 |
| Project Memory | SQLite 热索引（12 模块），含 migration 框架、integrity checker |
| Import Console | `api/routes/f0_index.py` — 导入状态和索引健康 |
| 测试覆盖 | 12 个测试文件，F0 契约测试 + 各渠道 contract 测试 |

**⚠️ 安全风险**: `scripts/wx_channels_download/pkg/certificate/certs/private.key` 存在于工作区但未 gitignore。

### F1 Standardize — `parsing/` 🟡 实现完整度：中高

| 维度 | 评估 |
|------|------|
| Canonical Adapters | 4 个：飞书聊天 / 手动文本 / 图片OCR / PDF |
| 标准 Router | `standardization_router.py` — 按 source_type 路由 |
| Vision/OCR | MiMo-V2.5 固定使用，不启用视觉模型 fallback |
| 测试覆盖 | 8 个测试文件，覆盖 router、fixtures、各 adapter |

**关键问题**: 5 个旧 parsing 模块（`content_standardizer.py`, `vision_extractor.py`, `audio_extractor.py`, `slang.py`, `context_summarizer.py`）标记为 DEPRECATED 仍输出 legacy `SegmentRecord`，与 canonical F1 混杂。

### F1.5 Topic Assembly — `parsing/topic_assembler.py` 🟡 实现完整度：中

| 维度 | 评估 |
|------|------|
| 规则版 Baseline | ✅ 已实现（确定性，作为 fallback） |
| LLM Adapter | ✅ 已实现（constrained LLM proposal） |
| Golden Fixture | ✅ Cat Lord 22-block 输入 / 5 topics + 7 unassigned 输出 |
| Pipeline 接入 | ❌ **未接入 canonical pipeline** |

**关键问题**: F1.5 设计正确、实现存在，但 canonical pipeline (`golden_path.py`) 跳过了 F1.5 和 F2，直接从 ContentEnvelope 进入 F3。

### F2 Anchor — `enrichment/` 🔴 实现完整度：低

| 维度 | 评估 |
|------|------|
| Schema 完整度 | ✅ QualityCard (7维度) + TemporalAnchor (4类) + EntityAnchor + EvidenceSpan |
| Quality Gate | ✅ `services/quality_gate.py` — 已接入 canonical pipeline |
| Entity Resolver | ❌ 无独立 canonical 实现 |
| Temporal Resolver | ❌ 无独立 canonical 实现 |
| Evidence Generator | ❌ 无独立 canonical 实现 |
| 测试覆盖 | 2 个测试文件 |

**🔴 这是整个 canonical pipeline 中最大的架构空洞。** 当前 evidence spans 由 F3 自行生成，temporal anchors 由 `timing_builder` 估算，entity anchors 依赖硬编码 registry。**F2 缺失的直接后果：canonical_trace_status 为 "canonical" 的 TradeAction，其 evidence 质量取决于 F3 的自我评估，而非独立锚定验证。**

### F3 Intent — `extraction/intent_extractor.py` ✅ 实现完整度：高

| 维度 | 评估 |
|------|------|
| 双轨实现 | RuleBasedIntentExtractor (keyword baseline) + LLMIntentExtractor (ModelRouter) |
| LLM 基础设施 | ModelRouter + PromptRegistry (Jinja2) |
| 输出契约 | IntentExtractionResult — 含 intents + evidence_spans + processing_notes |
| 契约遵守 | ✅ 严格遵守 "Intent ≠ Action" 原则 |
| 测试覆盖 | 5 个测试文件 |

**设计亮点**: `position_delta_hint` 是 hint 而非 instruction；`actionability` 区分 opinion/watch/explicit_action/review_required。

**关键问题**: F3 自行生成的 evidence_spans 不是来自独立 F2 层——F2 缺失的直接后果。

### F4 Policy — `policy/` 🟡 实现完整度：中高

| 维度 | 评估 |
|------|------|
| Schema | `PolicyMappingResult` 670 行，设计高质量 |
| GlobalBasePolicy | ✅ 第 1 层已实现 |
| PolicyMapper | ✅ 无状态 mapper，F3→F4 映射完整 |
| 上层 Policy | ❌ 第 2-5 层未实现（StyleArchetype / RiskPreference / KOLPersona / ContentCorrection） |
| 测试覆盖 | 2 个测试文件 |

**关键问题**: 所有 KOL 走同一条 GlobalBase 规则，不区分交易风格差异。这限制了回测的区分度。

### F5 Execute — `extraction/` + `pipeline/` ✅ 实现完整度：高

| 维度 | 评估 |
|------|------|
| CanonicalActionBuilder | ✅ 接受 structured inputs，强制类型校验 |
| canonical_runner.py | ✅ 两种策略（programmatic / llm_guided） |
| golden_path.py | ✅ 单 envelope F3→F4→F5 全链路 |
| TradeAction Schema | ✅ 957 行，设计质量最高 |
| ExecutionTiming | ✅ 四时钟模型，防前视偏差 |
| canonical_trace_status | ✅ model_validator 自动计算 |
| Legacy Extractor | ⚠️ 仍被 API 路由调用 |

**设计亮点**: 
- `canonical_trace_status` 通过 model_validator 自动计算（intent_id + policy_id + evidence_span_ids + execution_timing 全存在 → "canonical"）
- `_validate_types()` 拒绝 raw text / dict 输入，强制 structured-only

### F6 Review — `api/routes/rlhf.py` 🟡 实现完整度：中

| 维度 | 评估 |
|------|------|
| RLHF API | ✅ submit/pending/stats/export-DPO 端点完整 |
| 前端复核面板 | ✅ 方向/标的/操作链复核、快捷标签 |
| DPO 导出 | ✅ 可导出 |
| Legacy 目录引用 | ⚠️ 仍读取 `L0_ingestion/extractions` |

### F7 Timeline — `timeline/` 🔴 实现完整度：低

| 维度 | 评估 |
|------|------|
| 基础时间线 | ✅ TimelineEngine 可用 |
| ViewpointState | ❌ 未实现 |
| TargetOpinionGraph | ❌ 不支持多 KOL 同标的分歧图谱 |
| Mock Fallback | ⚠️ opinions.py API 在无数据时 fallback 到 `random.choice()` |
| 测试覆盖 | 仅 1 个测试文件 |

### F8 Backtest — `backtest/` ✅ 实现完整度：高

| 维度 | 评估 |
|------|------|
| BacktestEngine | ✅ 868 行，完整 portfolio simulation |
| 支持 | long/short, commission/slippage, stop-loss/take-profit, max holding days |
| 价格数据 | ⚠️ 默认 MockPriceProvider（随机数据），真实数据可选 |
| API 端点 | ✅ /run, /compare, /results, /delete |
| E2E 验证 | ✅ Cat Lord (7 actions → 5 trades) + Trader Ji (10 actions → 3 trades) |
| 测试覆盖 | 4 个测试文件 |

### F+ Training — `ml/` ⚪ 仅 contract

- DPO trainer 存在（912 行），RLHF 数据导出接口存在
- 训练数据量不足，未实际执行过训练

---

## 四、双轨执行路径——项目最核心的架构矛盾

### Canonical Path（新，推荐）

```
ContentEnvelope → QualityGate → F3 IntentExtractor → F4 PolicyMapper → F5 CanonicalActionBuilder → F8 BacktestEngine
```

入口点:
- `pipeline/golden_path.py` → `run_golden_path(envelope)` **(推荐)**
- `pipeline/canonical_runner.py` → `run_canonical_from_artifacts()` (结构化输入)
- `pipeline/canonical_runner.py` → `run_canonical_extraction()` (raw text, deprecated)

产出: `TradeAction.canonical_trace_status == "canonical"`

### Legacy Path（旧，deprecated 但仍活跃）

```
Raw Text → TradeActionExtractor(LLM) → TradeAction (non_canonical)
```

入口点:
- `pipeline/orchestrator.py` → `PipelineOrchestrator.run_full_pipeline()` (L0→L1→L3→L4→L5)
- `extraction/trade_action_extractor.py` → `TradeActionExtractor`

产出: `TradeAction.canonical_trace_status == "non_canonical"`

### 当前消费者映射

| 消费者 | 使用路径 | 风险 |
|--------|---------|------|
| `scripts/run_backtest_e2e.py` | ✅ Canonical | 无 |
| `api/routes/backtest.py` | ✅ Canonical | 无 |
| `api/routes/extraction.py` | ❌ **Legacy** | 调用 TradeActionExtractor |
| `pipeline/orchestrator.py` | ❌ **Legacy** | L5 直提 |
| `api/routes/kol.py` | ❌ **Legacy** | 读取 L5_candidate / L6_annotated |
| `api/routes/rlhf.py` | ❌ **Legacy** | 读取 L0_ingestion/extractions |
| `api/routes/asset_builder.py` | ❌ **Legacy** | 读取 L3/L4/L5 目录 |
| `api/routes/enrichment.py` | ❌ **Legacy** | 使用 L1_enrichment 目录 |

**8 个 API 路由模块中，5 个仍走 legacy 路径。** 这是前端仍能看到数据但数据不经过 canonical pipeline 的根因。

---

## 五、Schema 依赖链完整性

```
ContentRecord (F0) ✅ implemented
  └→ ContentEnvelope (F1) ✅ implemented
       └→ ContentBlock + BlockQuality + BlockProvenance (F1) ✅ implemented
            └→ TopicBlock / TopicAssemblyResult (F1.5) ✅ schema exists, ⚠️ not wired
                 └→ QualityCard + TemporalAnchor + EntityAnchor + EvidenceSpan (F2) ✅ schema, ❌ no resolver
                      └→ NormalizedInvestmentIntent (F3) ✅ implemented
                           └→ PolicyMappingResult (F4) ✅ implemented (GlobalBase only)
                                └→ TradeAction + ExecutionTiming (F5) ✅ implemented
                                     └→ ViewpointState (F7) ⚠️ partial
                                          └→ BacktestResult (F8) ✅ implemented
```

### Cross-Reference 自洽性

| 引用关系 | 状态 |
|----------|------|
| TradeAction.intent_id → NormalizedInvestmentIntent.intent_id | ✅ 语义一致 |
| TradeAction.policy_id → PolicyMappingResult.policy_id | ✅ 语义一致 |
| TradeAction.evidence_span_ids → EvidenceSpan.evidence_span_id | ⚠️ Schema 存在，F2 resolver 缺失 |
| PolicyMappingResult.intent_id → NormalizedInvestmentIntent.intent_id | ✅ 强制 min_length=1 |
| NormalizedInvestmentIntent.envelope_id → ContentEnvelope.envelope_id | ✅ 语义一致 |

### 前后端 Schema 同步风险

- `contracts.ts` 有 1,190 行 / 59 exports
- 后端 Schema 持续演化（canonical_trace_status、ExecutionTiming 是较新字段）
- **无自动生成机制**，依赖手动同步

---

## 六、测试覆盖分析

### 按层覆盖

| F-stage | 测试文件数 | 状态 |
|---------|-----------|------|
| F0 | 12 | ✅ 充分 |
| F1 | 8 | ✅ 充分 |
| F1.5 | 4 | ✅ 充分 |
| F2 | 2 | ⚠️ 仅 enrichment + quality_gate |
| F3 | 5 | ✅ 充分 |
| F4 | 2 | ✅ 充分 |
| F5 | 5 | ✅ 充分 |
| F6 | 1 | ⚠️ 依赖 API 级测试 |
| F7 | 1 | ❌ 不足 |
| F8 | 4 | ✅ 充分 |
| cross | 6 | ✅ |

### 测试空白

- **F2 Anchor**: 无独立的 entity/temporal resolver 测试（因为实现缺失）
- **F7 Timeline**: 仅 1 个测试文件
- **前端**: 无测试文件
- **E2E 集成**: 缺少从 F0 到 F8 的完整端到端自动化测试

---

## 七、技术债务清单

| ID | 严重度 | 位置 | 描述 |
|----|--------|------|------|
| TD-01 | 🔴 **高** | `scripts/wx_channels_download/pkg/certificate/certs/private.key` | 私钥文件未 gitignore，安全风险 |
| TD-02 | 🔴 **高** | F2 Anchor | 无独立 canonical resolver，evidence 质量依赖 F3 自评 |
| TD-03 | 🟠 **中高** | 5 个 legacy API 路由 | 前端仍通过 legacy 路径获取数据，双轨未隔离 |
| TD-04 | 🟡 **中** | `pipeline/orchestrator.py` | L0-L8 legacy orchestrator 仍可被调用 |
| TD-05 | 🟡 **中** | F4 Policy | 仅 GlobalBasePolicy，不区分 KOL 风格 |
| TD-06 | 🟡 **中** | `contracts.ts` | 手动同步 Pydantic→TypeScript，无自动生成 |
| TD-07 | 🟢 **低** | F1.5 Topic Assembly | 已实现但未接入 canonical pipeline |
| TD-08 | 🟢 **低** | 5 个 DEPRECATED parsing 模块 | 仍输出 legacy SegmentRecord |
| TD-09 | 🟢 **低** | `enrichment/` 命名 | 暗示 F2，内容更接近市场数据融合 |
| TD-10 | 🟢 **低** | F8 价格数据 | 默认 MockPriceProvider（随机数据） |

### Code Quality Markers

仅 11 处 TODO/FIXME/HACK/DEPRECATED 标记，代码整体干净：
- 6 处 legacy SegmentRecord DEPRECATED 标记
- 2 处 pipeline DEPRECATED 标记
- 1 处 B站 OSS TODO
- 1 处 KOL Rating 价格 TODO
- 1 处 legacy extraction endpoint DEPRECATED

---

## 八、设计优势与弱点

### ✅ 设计优势

1. **Schema-first 方法论**: 86 个 Pydantic V2 strict model，字段描述完整，validator 自动计算派生状态。整个项目最强的基础设施。

2. **四时钟模型**: `ExecutionTiming` 严格区分 intent_published_at / intent_effective_at / action_decision_at / action_executable_at，防止回测前视偏差。

3. **三重审计链**: F3 intent_id → F4 policy_id → F5 evidence_span_ids + PolicyLayerTrace per-layer audit，使每个 TradeAction 决策过程完全可追溯。

4. **Error Code Catalog**: 93 个 stable error codes，每个带 title/root_cause/fix_hint，前端 contracts 已对齐。比同规模项目成熟度高一个量级。

5. **Quality Gate as Pre-F3 Guard**: 在 F3 之前设置质量门控，避免低质量内容浪费 LLM 资源。

6. **Canonical Trace Auto-Validation**: `canonical_trace_status` 通过 model_validator 自动计算，无法伪造。

### ❌ 设计弱点

1. **F2 空洞**: canonical pipeline 中唯一没有独立实现的 stage。evidence 质量取决于 F3 自评而非独立验证。

2. **双轨共存未隔离**: canonical 和 legacy 在同一 codebase 中共存，前端仍走 legacy。无 feature flag 或路由前缀隔离。

3. **F4 单层 Policy**: 所有 KOL 走同一条 GlobalBase 规则，不区分风格差异——限制回测区分度。

4. **前端契约同步风险**: `contracts.ts` 1190 行手动维护，后端 Schema 持续演化。

5. **F7 ViewpointState 缺失**: 无法维护"同一 KOL 对同一标的的观点演化"和"多 KOL 同标的分歧图谱"。

---

## 九、架构建议优先级

| 优先级 | 建议 | 理由 | 预估工作量 |
|--------|------|------|-----------|
| **P0** | 将 `scripts/wx_channels_download/` 加入 `.gitignore` | 含 private.key，安全风险 | 5 分钟 |
| **P0** | 提交当前 uncommitted changes | Quality Gate + deprecation 标记方向正确 | 10 分钟 |
| **P1** | 为 legacy API 路由添加 `/legacy/` 前缀或 `X-Finer-Canonical: false` header | 隔离双轨，防止误用 | 1-2 天 |
| **P1** | 实现 F2 minimal viable entity resolver | 让 evidence_span_ids 来自独立验证 | 3-5 天 |
| **P2** | 添加 StyleArchetype policy layer | 至少两种 KOL 风格的差异化 policy | 2-3 天 |
| **P2** | 添加 contracts.ts 自动生成 | 从 Pydantic models 自动生成 TS types | 2-3 天 |
| **P2** | 将 F1.5 接入 canonical pipeline | 长文内容的 topic-level 粒度回测 | 1-2 天 |
| **P3** | 实现 F7 ViewpointState | 观点演化追踪和多 KOL 分歧分析 | 3-5 天 |
| **P3** | 替换 MockPriceProvider 为真实价格数据 | 回测结果才有实际意义 | 2-3 天 |

---

## 十、前端审阅

### 技术栈

| 技术 | 版本 |
|------|------|
| Next.js | 16.2.3 |
| React | 19.2.4 |
| TailwindCSS | 4 |
| ECharts | 6.0 |
| Framer Motion | 12.38 |

### 页面路由

| 路由 | 说明 |
|------|------|
| `/` | 首页/工作台 |
| `/landing` | 落地页 |
| `/research` | KOL 研究视图 |
| `/kol` | KOL 列表 |
| `/kol/[id]` | KOL 详情 |
| `/kol/[id]/backtest` | KOL 回测 |
| `/kol/[id]/backtest/[backtestId]` | 回测详情 |
| `/kol/compare` | KOL 对比 |
| `/backtest` | 回测台 |
| `/demo/kol-rating` | KOL 评级演示 |
| `/settings` | 设置 |

### 评估

- 前端代码规模适中，93 个 TS/TSX 文件
- 无独立测试文件（依赖 TypeScript 类型检查和 build）
- F3(Intent) 和 F4(Policy) 尚无对应前端视图
- 前端 API 调用仍走 legacy 路由（最关键问题）

---

## 十一、数据目录现状

| 目录 | 大小 | 说明 |
|------|------|------|
| `data/local` | 1.0 GB | 本地数据 |
| `data/L0_ingest` | 650 MB | 旧 F0 输出（未迁移到 F0_intake） |
| `data/raw` | 262 MB | 原始文件 |
| `data/feishu_sync_pool` | 46 MB | 飞书同步池 |
| `data/F1_validation_runs` | 4.3 MB | F1 验证 |
| `data/F1_standardized` | 1.2 MB | F1 标准化输出 |
| `data/F1_gold_sets` | 512 KB | F1 黄金集 |

**问题**: 磁盘目录仍混用 L0-L8 和 F0-F8 命名，`L0_ingest` (650MB) 是最大的未迁移目录。

---

## 十二、文档审阅

项目文档体系非常完善，114+ md 文件，总计 33,610 行：

| 文档 | 行数 | 说明 |
|------|------|------|
| `docs/specs/vibe-agent-operating-model.md` | 1,585 | Agent 操作模型 |
| `docs/ARCHITECTURE.md` | 1,177 | 架构文档（canonical） |
| `docs/specs/kol-backtest-mvp-stage-contracts.md` | 1,164 | KOL 回测 MVP 契约 |
| `docs/specs/2026-05-parallel-agent-execution.md` | 980 | 并行 Agent 执行规范 |
| `docs/specs/project-memory-storage-v1.md` | 960 | Project Memory 存储 |
| `docs/specs/f-stage-contracts.md` | 930 | F-stage 契约 |
| `docs/specs/ux-information-architecture-and-kol-rating-system.md` | 905 | UX 信息架构 |

**亮点**: 文档密度和规范性远超同规模项目，每个 F-stage 都有独立的 spec 文档。

---

## 十三、结论

Finer OS 在架构设计上展现出了远超一般研究原型的成熟度：

1. **Schema-first 方法论** + **三重审计链** + **四时钟模型** 构成了坚实的架构骨架
2. **Error Code Catalog** + **Quality Gate** + **Canonical Trace Auto-Validation** 提供了系统级的质量保障
3. **2,702 测试全量通过**，E2E 回测已可运行

但项目正处于从"架构搭建"向"生产就绪"过渡的关键阶段，三件事决定了项目能否突破当前瓶颈：

1. **F2 Anchor 独立实现** — 让证据链从"自述"变成"他证"
2. **Legacy 路径隔离与退役** — 让 canonical pipeline 真正成为唯一主链路
3. **F4 上层 Policy** — 让不同 KOL 的回测结果有差异化意义

*审阅完成。本报告基于对全部核心源文件、架构文档、测试结果和项目结构的直接分析生成。*
