# AGENTS.md — Finer OS

> **Canonical architecture: F0-F8.** 旧命名 L0-L8 和 V0-V6 已废弃。
> 所有 Agent 必须以 F0-F8 为唯一命名体系。任何新引入 L0-L8 或 V0-V6 的代码/文档/commit 必须被拒绝。

## 项目定位

AI-native 投研自动化流水线：将 KOL 社交媒体内容转化为结构化、可回测、可审计的投资事件。

## F0-F8 Canonical Pipeline

```
F0 INTAKE → F1 STANDARDIZE → F1.5 TOPIC ASSEMBLY → F2 ANCHOR → F3 INTENT → F4 POLICY → F5 EXECUTE → F6 REVIEW → F7 TIMELINE → F8 BACKTEST
                                                                                         ↑ F+ Training Loop ↑
```

| Stage | 名称 | 核心 Schema | 状态 |
|-------|------|------------|------|
| F0 | Intake | ContentRecord | implemented |
| F1 | Standardize | ContentEnvelope, ContentBlock | partial |
| F1.5 | Topic Assembly | TopicBlock, TopicAssemblyResult | contract-only |
| F2 | Anchor | QualityCard, TemporalAnchor, EntityAnchor, EvidenceSpan | partial |
| F3 | Intent | NormalizedInvestmentIntent | partial |
| F4 | Policy | PolicyMappingResult, PolicyMappedIntent | partial |
| F5 | Execute | TradeAction, ExecutionTiming | partial |
| F6 | Review | RLHFFeedback | implemented |
| F7 | Timeline | KOLTimeline, ViewpointState | partial |
| F8 | Backtest | BacktestResult | partial |
| F+ | Training | — | contract-only |

## 最严重架构断点

**F3 → F4 → F5 未闭环。** 当前 `trade_action_extractor.py` 仍从原始文本直接生成 TradeAction，绕过 F3 Intent 和 F4 Policy。F5 TradeAction schema 已补齐 `intent_id` / `policy_id` / `evidence_span_ids` 字段及 `canonical_trace_status` 校验器，但 canonical F3→F4→F5 pipeline constructor 尚未完成，legacy extractor 仍输出 `non_canonical` TradeAction。

**F1.5 Topic Assembly 仍是 contract-only。** 长聊天、长文档、音频转录稿等 multi-topic 内容目前还不能稳定拆成以标的/行业/宏观主题为单位的 `TopicBlock`。后续进入 F2/F3 前必须先补齐该子阶段，避免整篇复杂文件直接进入 Intent 抽取。

## Agent 执行规则

1. **每个 Agent 必须声明 F-stage。** 只能修改所属 stage 的 owning files。
2. **每个 Agent 必须声明输入输出 Schema。** 详见 `docs/specs/f-stage-contracts.md`。
3. **禁止跨 Stage 直接调用。** 如 F5 直接调 F1（架构违规）。
4. **F3 MUST NOT generate TradeAction。**
5. **F5 canonical TradeAction MUST include intent_id, policy_id, evidence_span_ids, execution_timing。**
6. **ExecutionTiming MUST distinguish four clocks。** `intent_published_at`、`intent_effective_at`、`action_decision_at`、`action_executable_at` 必须显式区分。

## 核心文件速查

| 文件 | F-stage | 说明 |
|------|---------|------|
| `ingestion/` | F0 | 多源接入 |
| `parsing/` | F1 | 内容标准化 |
| `parsing/topic_assembler.py` | F1.5 | 长篇复杂内容的主题块组装（待实现） |
| `schemas/topic_block.py` | F1.5 | TopicBlock / TopicAssemblyResult（待实现） |
| `enrichment/` | F2 | 实体/质量/时间锚定 |
| `extraction/intent_extractor.py` | F3 | Intent 提取（当前仅 rule-based） |
| `policy/` | F4 | Policy 映射（GlobalBasePolicy 已实现） |
| `schemas/policy.py` | F4 | PolicyMappingResult 等完整 Schema |
| `extraction/trade_action_extractor.py` | F5 | TradeAction 生成（legacy direct extraction；需接入 F3→F4→F5 canonical pipeline） |
| `api/routes/rlhf.py` | F6 | RLHF 反馈 |
| `timeline/` | F7 | 时间线引擎 |
| `backtest/` | F8 | 回测引擎 |
| `pipeline/orchestrator.py` | cross-stage | 流水线编排 |
| `schemas/` | cross-stage | 所有 Pydantic 数据契约 |
| `docs/specs/f-stage-contracts.md` | cross-stage | 每阶段输入/输出/Schema/禁止职责 |

## 技术栈

- 后端：Python 3.11+ / FastAPI / Pydantic V2
- 前端：TypeScript / Next.js 16 / React 19 / TailwindCSS 4
- LLM：GLM-5.1 (SVIPS) / Qwen-Plus (DashScope) / Qwen-VL-Plus

## 启动命令

```bash
uvicorn finer.api.server:app --reload --port 8000
cd src/finer_dashboard && npm run dev
pytest tests/ -v
```

## 配套文档

- `docs/ARCHITECTURE.md` — 完整架构文档（canonical）
- `docs/specs/f-stage-contracts.md` — 每阶段契约
- `docs/specs/canonical-path-test-plan.md` — 测试计划
- `CLAUDE.md` — 项目工程规范
