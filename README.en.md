# Finer OS — Structured & Backtestable KOL Investment Research

[中文](README.md) · **English**

<p align="center">
  <a href="https://github.com/kelipovanatalja453-bot/finer/actions/workflows/ci.yml"><img src="https://github.com/kelipovanatalja453-bot/finer/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="python">
  <img src="https://img.shields.io/badge/Next.js-16-black.svg" alt="next.js">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="license">
  <img src="https://img.shields.io/badge/status-research%20prototype-orange.svg" alt="status">
</p>

> **Turn financial KOL content into backtestable, auditable investment events.**

Finer OS runs an F0–F8 pipeline that ingests KOL social content from any platform — chat logs, image-based strategy posts, Feishu docs, PDFs, audio/video transcripts — normalizes it into structured content blocks, extracts evidence-linked investment intents, maps them into reviewable trade actions, and backtests them from a **full-follower's perspective** to verify the real return, risk, and stability of "following this KOL."

[Quick Start](#quick-start) · [Capabilities](#four-core-capabilities) · [Backtest Proof](#backtest-proof-an-evidence-chain-behind-every-return) · [Architecture](#architecture) · [API](docs/API_REFERENCE.md)

<p align="center">
  <img src="src/finer_dashboard/public/landing/research.png" alt="Finer OS KOL research view: object-centric three-column layout with return curve and evidence provenance" width="900">
  <br>
  <em>KOL Research View — scoring, return curve, evidence provenance (sample data)</em>
</p>

---

## Why Finer

Financial creators publish high-signal investment reasoning inside noisy timelines: long chat logs, image-based strategy posts, Feishu docs, PDFs, livestream transcripts, and short-form market comments. A simple sentiment classifier can't answer the real question:

> If someone had followed this KOL over time, what would the portfolio outcome have been?

Finer OS is built around that question. It turns unstructured KOL content into **evidence-traceable** investment intents, maps those intents into **reviewable** trade actions, and connects them to timeline analysis and backtesting — where every conclusion can be traced back to its original source.

---

## One Piece of Content, All the Way Through F0 → F8

Every stage has a frozen input/output contract. Raw content goes in, structured judgments come out, and intermediate artifacts are persisted layer by layer for human review — **not a black box**.

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

## Backtest Proof: An Evidence Chain Behind Every Return

<p align="center">
  <img src="src/finer_dashboard/public/landing/backtest.png" alt="Finer OS F8 backtest audit: cumulative return curve, key performance metrics, and annual audit table" width="900">
  <br>
  <em>F8 Backtest Audit — cumulative return, performance metrics, annual audit table (sample data)</em>
</p>

Every TradeAction that enters the backtest satisfies the canonical contract: it can be traced back to the F3 investment intent, the F4 policy mapping, the F2 evidence spans, and four explicitly distinguished execution clocks.

- Cumulative return, annualized, Sharpe, max drawdown, win rate — **all auditable**
- Next-open fill model + **explicit fee / slippage assumptions**
- `intent_id` / `policy_id` / `evidence_span_ids` threaded end to end
- Every number traces back to the original KOL content

---

## Four Core Capabilities

| Stage | Capability | Description |
|:---|:---|:---|
| **F0 · F1** | Ingest & Normalize | Unified intake of multi-source KOL content (Feishu, WeChat Official Accounts, Bilibili), standardized into `ContentEnvelope` + `ContentBlock` with source anchors and raw archives preserved. |
| **F2** | Anchor the Evidence Chain | Entity resolution, temporal anchoring, and evidence-span (`EvidenceSpan`) extraction. Every judgment traces back to the source's character range and original timestamp. |
| **F3 · F4 · F5** | Intent → Policy → Execute | Investment-intent extraction → policy mapping → `TradeAction` generation. Each action carries `intent_id` / `policy_id` / `evidence_span_ids` and four-clock execution timing. |
| **F8** | Backtest & Score | Map language opinions to market outcomes, simulate a full-follower's return curve, and output auditable metrics — Sharpe, drawdown, win rate. |

---

## AI · Human-in-the-Loop

AI does **concrete, verifiable** work at each stage; every AI output must pass the F6 review desk and be adjudicated by a human before it enters the backtest; that adjudication is recorded as structured fields and exported as DPO training data — Finer's most concrete answer to "black-box AI."

<table>
<tr>
<th>🤖 What AI does</th>
<th>🧑‍⚖️ Where humans step in</th>
<th>🔄 How feedback persists</th>
</tr>
<tr>
<td valign="top">

- `F1` Vision/OCR: MiMo-V2.5 handles images, PDFs, screenshots
- `F1.5` Topic assembly: constrained-LLM proposals + deterministic validator fallback
- `F3` Investment intent: LLM extracts stance / conviction from evidence spans
- `F5` TradeAction: LLM + rules jointly construct the canonical action

</td>
<td valign="top">

`F6` RLHF review desk. Every TradeAction entering the backtest must pass:

- Overall 1–5 star rating + `is_correct` judgment
- Field-level corrections: direction / ticker / action chain
- Free-text notes + quick tags
- `reviewer_id` / `reviewed_at` fully auditable

</td>
<td valign="top">

- Persisted as `RLHFFeedback` records
- `GET /api/rlhf/export` exports DPO training data
- The training loop is **contract-only**: the data format is ready, model fine-tuning **has not started** (no overclaiming)

</td>
</tr>
</table>

```
AI extracts        Human judges        Structured record    Export training data
F1–F5 LLM    →     F6 RLHF Panel  →    RLHFFeedback    →    DPO JSONL pairs
                   POST /api/rlhf/submit  →  GET /api/rlhf/export
```

<p align="center">
  <img src="src/finer_dashboard/public/landing/review.png" alt="Finer OS F6 RLHF review desk: queue of assets marked NEEDS REVIEW and entry to the review workbench" width="900">
  <br>
  <em>F6 RLHF Review Desk — review queue and human-adjudication entry</em>
</p>

---

## Stage Status

We'd rather be clear about what's **built** and what's **not**.

| Stage | Name | Core Schema | Status |
|:---|:---|:---|:---|
| **F0** | Intake | `ContentRecord` | ✅ implemented |
| **F1** | Standardize | `ContentEnvelope` / `ContentBlock` / `BlockQuality` / `BlockProvenance` | 🟡 alpha (contract reset) |
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

## The Workbench Is the Product

<p align="center">
  <img src="src/finer_dashboard/public/landing/workbench.png" alt="Finer OS workbench: F0-F8 workflow navigation, asset grid, and evidence provenance panel" width="900">
  <br>
  <em>F0–F8 Workbench — workflow navigation, asset grid, evidence provenance panel</em>
</p>

---

## Tech Stack

| Layer | Choice | Purpose |
|:---|:---|:---|
| **Core languages** | Python 3.11+ / TypeScript | Backend logic + frontend |
| **Web framework** | FastAPI + Pydantic V2 | API services + data validation |
| **Frontend** | Next.js 16 + React 19 + TailwindCSS 4 | Dashboard workbench |
| **LLMs** | MiMo-V2.5 / GLM-5.1 / Qwen | Vision parsing (F1 OCR) + enrichment + structured extraction |
| **Structured output** | Instructor | Contract-first strongly-typed output |
| **Data processing** | Data-Juicer / Polars | Data cleaning + backtest engine |
| **Visualization** | ECharts | Return curves + performance charts |
| **RLHF platform** | In-house Dashboard | Human annotation + preference collection |

---

## Quick Start

### Requirements

- Python 3.11+
- Node.js 18+
- Redis (optional, for caching)

### Install

```bash
# 1. Clone
git clone https://github.com/kelipovanatalja453-bot/finer.git
cd finer

# 2. Python deps
pip install -e .

# 3. Frontend deps
cd src/finer_dashboard
npm install
```

### Configure

```bash
# Copy config template
cp configs/feishu.yaml.example configs/feishu.yaml

# Environment variables
export OPENAI_API_KEY="your-key"
export MIMO_API_KEY="your-key"          # MiMo-V2.5, F1 image/PDF OCR
export MIMO_BASE_URL="https://token-plan-cn.xiaomimimo.com/v1"  # only for tp-* Token Plan keys
export DASHSCOPE_API_KEY="your-key"     # Qwen
export FINANCE_SKILLS_API_KEY="your-key"  # optional
```

### Run

```bash
# Backend API (terminal 1)
cd src
uvicorn finer.api.server:app --port 8000 --reload

# Frontend Dashboard (terminal 2)
cd src/finer_dashboard
npm run dev
```

Open http://localhost:3000 for the Dashboard.

### Optional: WeChat Channels F0 dependency (work-in-progress)

`POST /api/wechat/channels/import` depends on the local API or CLI under `scripts/wx_channels_download` to fetch Channels profiles and download videos. That directory is kept in this repo as WIP F0 handoff source; runtime artifacts, DBs, logs, private keys, and locally built binaries should not be version-controlled. Anyone picking it up should first confirm the external project's licensing, build process, and security boundaries.

---

## Architecture

### Data Flow

```
Raw KOL content
    ↓
F0 Intake — multi-source intake (Feishu/Bilibili/WeChat/PDF), unified into ContentRecord
    ↓
F1 Standardize — block normalization (ContentEnvelope / ContentBlock + standardization quality + provenance)
    ↓
F1.5 Topic Assembly — semantic topic assembly for long chats/docs (TopicBlock / TopicAssemblyResult)
    ↓
F2 Anchor — quality + temporal anchor + evidence spans (QualityCard / TemporalAnchor / EvidenceSpan)
    ↓
F3 Intent — investment-intent extraction (direction / actionability / position_delta_hint / conviction)
    ↓
F4 Policy — policy mapping hints (GlobalBase → StyleArchetype → KOLPersona)
    ↓
F5 Execute — traceable TradeAction + ExecutionTiming (intent_id + policy_id + evidence_span_ids)
    ↓
F6 Review + F7 Timeline — human review, viewpoint state machine, timeline analysis
    ↓
F8 Backtest — follow-trade simulation and KOL return evaluation
    ↓
F+ Training Loop — SFT / DPO / RLHF model improvement (cross-stage loop, contract-only)
```

### Core Modules

| F-Stage | Module | Responsibility | Key files |
|:---|:---|:---|:---|
| **F0** | Intake | Multi-source import | `ingestion/feishu_poller.py` |
| **F1** | Standardize | Content envelope, quality card, evidence chain | `schemas/content_envelope.py`, `schemas/quality.py` |
| **F1.5** | Topic Assembly | Split long chats/docs into TopicBlocks | `schemas/topic_block.py`, `parsing/topic_assembler.py` |
| **F2** | Anchor | TemporalAnchor parsing, EvidenceSpan anchoring | `schemas/temporal.py` |
| **F3** | Intent | Investment-intent extraction (four axes) | `schemas/investment_intent.py`, `extraction/intent_extractor.py` |
| **F4** | Policy | Policy mapping (hints, no TradeAction) | `policy/policy_mapper.py`, `schemas/policy.py` |
| **F5** | Execute | Canonical TradeAction + ExecutionTiming | `extraction/trade_action_extractor.py` |
| **F6** | Review | Human calibration, RLHF | `api/routes/rlhf.py` |
| **F7** | Timeline | ViewpointState, KOL opinion evolution | `timeline/` |
| **F8** | Backtest | Follow-trade simulation and KOL evaluation | `backtest/` |

Full architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## API

See [docs/API_REFERENCE.md](docs/API_REFERENCE.md) for details.

| Endpoint | Method | Purpose |
|:---|:---|:---|
| `/api/files` | GET | List assets |
| `/api/enrichment/split` | POST | Topic split / anchoring (legacy API name, maps to F1.5/F2) |
| `/api/enrichment/extract` | POST | Entity extraction |
| `/api/review/save` | POST | Save review result |
| `/api/rlhf/submit` | POST | Submit RLHF feedback |
| `/api/rlhf/export` | GET | Export DPO training data |

---

## Development

### Project Layout

```
src/finer/
├── api/              # FastAPI routes
│   ├── routes/       # Per-module endpoints
│   └── server.py     # App entry
├── enrichment/       # F2 anchoring
├── extraction/       # F3/F5 extraction
├── ingestion/        # F0 intake
├── parsing/          # F1 standardize + F1.5 topic assembly
├── policy/           # F4 policy mapping
├── backtest/         # F8 backtest engine
├── timeline/         # F7 timeline engine
├── schemas/          # Pydantic models (single source of truth)
└── services/         # External services

src/finer_dashboard/  # Next.js 16 Dashboard
```

### Common Commands

```bash
# Run tests
pytest tests/ -v

# Frontend build / type-check
cd src/finer_dashboard && npm run build
cd src/finer_dashboard && npx tsc --noEmit
```

---

## Contributing

Contributions, issues, and suggestions are welcome.

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push and open a Pull Request

Please make sure: code passes `pytest`, follows `black` formatting, and new features have tests.

---

## License

[MIT License](LICENSE).

## Acknowledgements

Inspired by:
[Instructor](https://github.com/jxnl/instructor) (structured output) ·
[Data-Juicer](https://github.com/modelscope/data-juicer) (data cleaning) ·
[Argilla](https://github.com/argilla-io/argilla) (RLHF annotation) ·
[MinerU](https://github.com/opendatalab/MinerU) (document parsing)

---

> ⚠️ **Disclaimer**: Finer OS is an internal research-system prototype. All data and backtest results (including the return figures in the screenshots above) are samples for research only and **do not constitute investment advice**.
