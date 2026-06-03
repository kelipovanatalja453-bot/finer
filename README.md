# Finer OS — KOL 投资观点结构化与回测系统

**中文** · [English](README.en.md)

<p align="center">
  <a href="https://github.com/kelipovanatalja453-bot/finer/actions/workflows/ci.yml"><img src="https://github.com/kelipovanatalja453-bot/finer/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="python">
  <img src="https://img.shields.io/badge/Next.js-16-black.svg" alt="next.js">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="license">
  <img src="https://img.shields.io/badge/status-research%20prototype-orange.svg" alt="status">
</p>

> **把财经 KOL 的内容，变成可回测、可审计的投资事件。**

Finer OS 沿 F0–F8 流水线，将任意平台的 KOL 社交媒体内容——聊天记录、图片策略、飞书文档、PDF、音视频转录——统一清洗为标准化内容块，抽取可追溯证据的投资意图，映射为可复核的交易动作，并以**完全跟单者视角**回测，验证「跟随这个 KOL」的真实收益、风险与稳定性。

[快速开始](#快速开始) · [核心能力](#四个核心能力) · [回测证据](#回测证据收益曲线背后是完整证据链) · [架构设计](#架构设计) · [API 文档](docs/API_REFERENCE.md)

<p align="center">
  <img src="src/finer_dashboard/public/landing/research.png" alt="Finer OS KOL 研究视图：对象中心三栏，收益曲线与证据溯源" width="900">
  <br>
  <em>KOL 研究视图 — 评分、收益曲线、证据溯源（示例数据）</em>
</p>

---

## 为什么是 Finer

财经创作者把高信号的投资推理，藏在嘈杂的时间轴里：冗长的聊天记录、图片形式的策略帖、飞书文档、PDF、直播转录、碎片化的盘面点评。一个简单的情绪分类器回答不了真正的问题：

> 如果有人长期跟随这个 KOL，组合的真实结果会是什么？

Finer OS 就是围绕这个问题构建的。它把非结构化的 KOL 内容转成**证据链可追溯**的投资意图，把意图映射为**可复核**的交易动作，再接入时间线分析与回测——每一个结论都能反查到原始出处。

---

## 一条内容，走完 F0 → F8

每一阶段都有冻结的输入/输出契约。原始内容进来，结构化判断出去，中间产物逐层落盘可供人工复核——**不是黑箱**。

```mermaid
flowchart LR
    S0[Raw Sources] --> F0[F0 Intake / ContentRecord]
    F0 --> F1[F1 Standardize / ContentEnvelope]
    F1 --> F15[F1.5 Topic Assembly / TopicBlock]
    F15 --> F2[F2 Anchor / Quality + TemporalAnchor + EvidenceSpan]
    F2 --> F3[F3 Intent / NormalizedInvestmentIntent]
    F3 --> F4[F4 Policy / PolicyMappingResult]
    F4 --> F5[F5 Execute / TradeAction]
    F5 --> F6[F6 Review / Human + RLHF]
    F6 --> F7[F7 Timeline / ViewpointState]
    F7 --> F8[F8 Backtest / KOL Evaluation]
    F8 -.-> FT[F+ Training Loop / SFT + DPO]
```

---

## 回测证据：收益曲线背后是完整证据链

<p align="center">
  <img src="src/finer_dashboard/public/landing/backtest.png" alt="Finer OS F8 回测审计：累计收益曲线、关键绩效指标与年度审计表" width="900">
  <br>
  <em>F8 回测审计 — 累计收益、绩效指标与年度审计表（示例数据）</em>
</p>

每条进入回测的 TradeAction 都满足 canonical 契约：可反查到 F3 投资意图、F4 策略映射、F2 证据片段，以及四个明确区分的执行时钟。

- 累计收益、年化、夏普、最大回撤、胜率**全部可审计**
- 次开盘成交模型 + **显式费用 / 滑点假设**
- `intent_id` / `policy_id` / `evidence_span_ids` 全程贯穿
- 每个数字都可回溯到原始 KOL 内容

---

## 四个核心能力

| 阶段 | 能力 | 说明 |
|:---|:---|:---|
| **F0 · F1** | 采集与归一化 | 飞书、微信公众号、B站等多源 KOL 内容统一接入，标准化为 `ContentEnvelope` + `ContentBlock`，保留来源锚点与原始归档。 |
| **F2** | 锚定证据链 | 实体解析、时间锚定、证据片段（`EvidenceSpan`）抽取。每个判断都能反查到原文的字符区间与来源时间。 |
| **F3 · F4 · F5** | 意图 → 策略 → 执行 | 投资意图提取 → Policy 映射 → 生成 `TradeAction`。每条交易动作携带 `intent_id` / `policy_id` / `evidence_span_ids` 与四时钟执行时间。 |
| **F8** | 回测与评分 | 把语言观点映射到市场结果，模拟完全跟单者的收益曲线，输出夏普、回撤、胜率等可审计绩效指标。 |

---

## AI · 人在环

AI 在每个阶段做**具体可验证**的事；每一条 AI 输出在进入回测前都必须经过 F6 复核台被人类裁决；裁决以结构化字段记录，导出为 DPO 训练数据——这是 Finer 对「黑箱 AI」最具体的反话术。

<table>
<tr>
<th>🤖 AI 做什么</th>
<th>🧑‍⚖️ 人在哪儿介入</th>
<th>🔄 反馈如何沉淀</th>
</tr>
<tr>
<td valign="top">

- `F1` 视觉/OCR：MiMo-V2.5 处理图片、PDF、截图
- `F1.5` 主题组装：constrained LLM 提议 + 确定性 validator 兜底
- `F3` 投资意图：LLM 从证据片段提取 stance / conviction
- `F5` TradeAction：LLM + 规则共同构造 canonical 动作

</td>
<td valign="top">

`F6` RLHF 复核台。每条进入回测的 TradeAction 都必须经过：

- 整体 1–5 星评分 + `is_correct` 判断
- 字段级修正：direction / ticker / action chain
- 自由文本备注 + 快捷标签
- `reviewer_id` / `reviewed_at` 全程可审计

</td>
<td valign="top">

- 持久化为 `RLHFFeedback` 记录
- `GET /api/rlhf/export` 导出为 DPO 训练数据
- 训练循环为 **contract-only**：数据格式已就绪，模型微调**尚未启动**（不夸大）

</td>
</tr>
</table>

```
AI 抽取            人工裁决           结构化记录          导出训练数据
F1–F5 LLM    →    F6 RLHF Panel  →   RLHFFeedback   →   DPO JSONL pairs
                  POST /api/rlhf/submit  →  GET /api/rlhf/export
```

<p align="center">
  <img src="src/finer_dashboard/public/landing/review.png" alt="Finer OS F6 RLHF 审核台：标记为 NEEDS REVIEW 的资产队列与审核工作台入口" width="900">
  <br>
  <em>F6 RLHF 复核台 — 待审队列与人工裁决入口</em>
</p>

---

## 各阶段状态

我们更愿意把**已建成**与**未建成**都说清楚。

| Stage | 名称 | 核心 Schema | 状态 |
|:---|:---|:---|:---|
| **F0** | Intake | `ContentRecord` | ✅ implemented |
| **F1** | Standardize | `ContentEnvelope` / `ContentBlock` / `BlockQuality` / `BlockProvenance` | 🟡 alpha（契约重置中） |
| **F1.5** | Topic Assembly | `TopicBlock` / `TopicAssemblyResult` | 🟡 alpha |
| **F2** | Anchor | `QualityCard` / `TemporalAnchor` / `EntityAnchor` / `EvidenceSpan` | 🟠 partial |
| **F3** | Intent | `NormalizedInvestmentIntent` | 🟠 partial |
| **F4** | Policy | `PolicyMappingResult` / `PolicyMappedIntent` | 🟠 partial |
| **F5** | Execute | `TradeAction` / `ExecutionTiming` | 🟠 partial |
| **F6** | Review | `RLHFFeedback` | ✅ implemented |
| **F7** | Timeline | `KOLTimeline` / `ViewpointState` | 🟠 partial |
| **F8** | Backtest | `BacktestResult` | 🟠 partial |
| **F+** | Training | — | ⚪ contract-only |

---

## 工作台即产品

<p align="center">
  <img src="src/finer_dashboard/public/landing/workbench.png" alt="Finer OS 工作台：F0-F8 工作流导航、资产网格与证据溯源面板" width="900">
  <br>
  <em>F0–F8 工作台 — 工作流导航、资产网格与证据溯源面板</em>
</p>

---

## 技术栈

| 层级 | 技术选型 | 用途 |
|:---|:---|:---|
| **核心语言** | Python 3.11+ / TypeScript | 后端逻辑 + 前端交互 |
| **Web 框架** | FastAPI + Pydantic V2 | API 服务 + 数据校验 |
| **前端框架** | Next.js 16 + React 19 + TailwindCSS 4 | Dashboard 工作台 |
| **大模型** | MiMo-V2.5 / GLM-5.1 / Qwen | 视觉解析（F1 OCR）+ 富化 + 结构化提取 |
| **结构约束** | Instructor | Contract-first 强类型输出 |
| **数据处理** | Data-Juicer / Polars | 数据清洗 + 回测引擎 |
| **可视化** | ECharts | 收益曲线 + 绩效图表 |
| **RLHF 平台** | 自研 Dashboard | 人工标注 + 偏好收集 |

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- Redis（可选，用于缓存）

### 安装

```bash
# 1. 克隆项目
git clone https://github.com/kelipovanatalja453-bot/finer.git
cd finer

# 2. 安装 Python 依赖
pip install -e .

# 3. 安装前端依赖
cd src/finer_dashboard
npm install
```

### 配置

```bash
# 复制配置模板
cp configs/feishu.yaml.example configs/feishu.yaml

# 设置环境变量
export OPENAI_API_KEY="your-key"
export MIMO_API_KEY="your-key"          # MiMo-V2.5，F1 图片/PDF OCR
export MIMO_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"  # 仅 tp-* Token Plan key 需要
export DASHSCOPE_API_KEY="your-key"     # 通义千问
export FINANCE_SKILLS_API_KEY="your-key"  # 可选
```

### 运行

```bash
# 启动后端 API（终端 1）
cd src
uvicorn finer.api.server:app --port 8000 --reload

# 启动前端 Dashboard（终端 2）
cd src/finer_dashboard
npm run dev
```

访问 http://localhost:3000 打开 Dashboard。

### 可选：微信视频号 F0 半成品依赖

`POST /api/wechat/channels/import` 依赖 `scripts/wx_channels_download` 的本地 API 或 CLI 获取视频号 profile 和下载视频。该目录随本仓库作为 F0 半成品交接源码保留；运行时产物、DB、日志、私钥与本地构建出的 binary 不应进入版本控制。接手者需先确认该外部项目的授权、构建方式与安全边界。

---

## 架构设计

### 数据流

```
原始 KOL 内容
    ↓
F0 Intake — 多源内容接入（飞书/B站/微信/PDF），统一写入 ContentRecord
    ↓
F1 Standardize — 内容块标准化（ContentEnvelope / ContentBlock + standardization quality + provenance）
    ↓
F1.5 Topic Assembly — 长聊天/长文档语义主题组装（TopicBlock / TopicAssemblyResult）
    ↓
F2 Anchor — 质量评估 + 时间锚 + 证据跨度（QualityCard / TemporalAnchor / EvidenceSpan）
    ↓
F3 Intent — 投资意图抽取（direction / actionability / position_delta_hint / conviction）
    ↓
F4 Policy — 策略映射 hint（GlobalBase → StyleArchetype → KOLPersona）
    ↓
F5 Execute — 可追溯 TradeAction + ExecutionTiming（intent_id + policy_id + evidence_span_ids）
    ↓
F6 Review + F7 Timeline — 人工复核、观点状态机、时间线分析
    ↓
F8 Backtest — 跟随交易模拟与 KOL 收益评估
    ↓
F+ Training Loop — SFT / DPO / RLHF 模型改进（跨阶段闭环，contract-only）
```

### 核心模块

| F-Stage | 模块 | 职责 | 关键文件 |
|:---|:---|:---|:---|
| **F0** | 接入层 | 多源数据导入 | `ingestion/feishu_poller.py` |
| **F1** | 标准化层 | 内容容器、质量卡、证据链 | `schemas/content_envelope.py`, `schemas/quality.py` |
| **F1.5** | 主题组装层 | 长聊天/长文档拆分为 TopicBlock | `schemas/topic_block.py`, `parsing/topic_assembler.py` |
| **F2** | 锚定层 | TemporalAnchor 时间解析、EvidenceSpan 锚定 | `schemas/temporal.py` |
| **F3** | 意图层 | 投资意图抽取（四轴输出） | `schemas/investment_intent.py`, `extraction/intent_extractor.py` |
| **F4** | 策略层 | Policy 映射（hint，不生成 TradeAction） | `policy/policy_mapper.py`, `schemas/policy.py` |
| **F5** | 执行层 | Canonical TradeAction + ExecutionTiming 生成 | `extraction/trade_action_extractor.py` |
| **F6** | 复核层 | 人工校准、RLHF | `api/routes/rlhf.py` |
| **F7** | 时间线层 | ViewpointState、KOL 观点演化 | `timeline/` |
| **F8** | 回测层 | 跟随交易模拟与 KOL 评估 | `backtest/` |

完整架构见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

---

## API 文档

详细参考见 [docs/API_REFERENCE.md](docs/API_REFERENCE.md)。

| 端点 | 方法 | 用途 |
|:---|:---|:---|
| `/api/files` | GET | 获取资产列表 |
| `/api/enrichment/split` | POST | 话题分割/锚定（legacy API name，对应 F1.5/F2） |
| `/api/enrichment/extract` | POST | 实体抽取 |
| `/api/review/save` | POST | 保存复核结果 |
| `/api/rlhf/submit` | POST | 提交 RLHF 反馈 |
| `/api/rlhf/export` | GET | 导出 DPO 训练数据 |

---

## 开发指南

### 项目结构

```
src/finer/
├── api/              # FastAPI 路由
│   ├── routes/       # 各模块端点
│   └── server.py     # 应用入口
├── enrichment/       # F2 锚定层
├── extraction/       # F3/F5 抽取层
├── ingestion/        # F0 数据接入
├── parsing/          # F1 标准化 + F1.5 主题组装
├── policy/           # F4 策略映射
├── backtest/         # F8 回测引擎
├── timeline/         # F7 时间线引擎
├── schemas/          # Pydantic 模型（唯一真相源）
└── services/         # 外部服务

src/finer_dashboard/  # Next.js 16 Dashboard
```

### 常用命令

```bash
# 运行测试
pytest tests/ -v

# 前端构建 / 类型检查
cd src/finer_dashboard && npm run build
cd src/finer_dashboard && npx tsc --noEmit
```

---

## 贡献指南

欢迎贡献代码、报告问题或提出建议。

1. Fork 本仓库
2. 创建特性分支（`git checkout -b feature/amazing-feature`）
3. 提交更改（`git commit -m 'feat: add amazing feature'`）
4. 推送并创建 Pull Request

请确保：代码通过 `pytest`、遵循 `black` 格式规范、新功能有对应测试。

---

## 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

## 致谢

本项目受以下开源项目启发：
[Instructor](https://github.com/jxnl/instructor)（结构化输出）·
[Data-Juicer](https://github.com/modelscope/data-juicer)（数据清洗）·
[Argilla](https://github.com/argilla-io/argilla)（RLHF 标注）·
[MinerU](https://github.com/opendatalab/MinerU)（文档解析）

---

> ⚠️ **免责声明**：Finer OS 是内部研究系统原型。数据与回测结果（含本页截图中的收益数字）均为示例，仅供研究，**不构成任何投资建议**。
