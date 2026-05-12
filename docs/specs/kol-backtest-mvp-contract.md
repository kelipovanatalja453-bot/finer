# KOL Backtest MVP Contract

> Version: 1.0.0 | Created: 2026-05-11
> Status: **Design** — pending team review

---

```
Stage: MVP (cross-cutting)
MVP responsibility: Define what constitutes a valid MVP run
Input contract: KOL profile + frozen ContentRecords + market_prices.csv
Output contract: BacktestResult + equity_curve + TradeAction[]
Required fields: (listed per stage)
Forbidden responsibilities: F6, F7, F+, real trading, multi-KOL, strategy marketplace
Failure cases: (listed)
Open questions: (listed)
```

---

## 1. MVP Definition

The KOL Backtest MVP is a deterministic, end-to-end pipeline run that takes a single KOL's frozen content set (pre-collected, immutable ContentRecords) through the canonical F1 -> F1.5 -> F2 -> F3 -> F4 -> F5 -> F8 path, producing a set of auditable TradeActions (each with `canonical_trace_status = "canonical"`) and an equity curve representing a simulated follower portfolio over the content publication period. The final acceptance artifact is a `BacktestResult` JSON file containing the full TradeAction chain, portfolio equity time series, and summary performance metrics — all reproducible given the same frozen inputs.

**Validation strategy**: The MVP product capability is "one KOL can produce an auditable equity curve." To prove this is not overfitted to a single sample, the contract is validated against **two independent frozen KOL fixtures**: `cat_lord` (投研分析型) and `trader_ji` (交易信号型). Each KOL runs independently through F1→F8. No cross-KOL data flow, no multi-KOL ranking, no portfolio comparison.

---

## 2. Input

| Input | Description | Format | Source |
|---|---|---|---|
| **KOL Profile** | Creator metadata, trading style archetype, risk preference tier | `KOLProfile` object or equivalent YAML/config | Pre-configured by analyst |
| **Frozen ContentRecords** | Pre-collected, immutable set of ContentRecords for one KOL | JSON files in `data/F0_intake/` | Already on disk from F0 — not re-ingested |
| **Market Price Data** | Daily OHLCV prices for all referenced tickers over the content period | `market_prices.csv` (columns: `date`, `ticker`, `open`, `high`, `low`, `close`, `volume`) | Externally sourced, frozen at run start |

### Constraints on Input

- ContentRecords are **read-only** during the MVP run. F0 does not execute.
- Exactly one `creator_id` across all ContentRecords in the run set.
- Market price data MUST cover the full date range from earliest `published_at` to latest `published_at` + max holding period for every ticker referenced.
- Missing price data for a ticker on a date is a hard error (not a skip).

---

## 3. Output

| Output | Description | Schema |
|---|---|---|
| **TradeActions** | Ordered list of canonical TradeActions, one per extracted investment intent that passes policy | `List[TradeAction]` — each with `canonical_trace_status = "canonical"` |
| **Equity Curve** | Daily portfolio value time series from first trade to last exit | `List[EquityPoint]` where each point has `date`, `portfolio_value`, `cash`, `positions_value` |
| **BacktestResult** | Summary metrics + full trace | `BacktestResult` containing `total_return_pct`, `max_drawdown_pct`, `sharpe_ratio`, `win_rate`, `trade_count`, `equity_curve`, `trade_actions[]`, `config`, `run_metadata` |

### Output Integrity Requirements

- Every TradeAction in the output MUST have `intent_id`, `policy_id`, `evidence_span_ids` (len >= 1), and `execution_timing` all populated.
- Every TradeAction MUST have `canonical_trace_status = "canonical"` (auto-derived by the schema validator).
- The equity curve MUST have no gaps larger than 5 trading days (weekends/holidays excluded).
- All dates in the output MUST be ISO 8601 with explicit timezone.

---

## 4. Canonical Path

```
F0 (frozen, read-only)
  |
  v
F1 Standardize
  |  ContentRecord -> ContentEnvelope + ContentBlock[]
  v
F1.5 Topic Assembly
  |  ContentBlock[] -> TopicBlock[] (always; single-topic wraps all blocks in one TopicBlock)
  v
F2 Anchor
  |  ContentBlock[] -> EvidenceSpan[] + EntityAnchor[] + TemporalAnchor[]
  v
F3 Intent
  |  TopicBlock[] + EvidenceSpan[] -> NormalizedInvestmentIntent[]
  v
F4 Policy
  |  NormalizedInvestmentIntent[] -> PolicyMappingResult[] + PolicyMappedIntent[]
  v
F5 Execute
  |  PolicyMappedIntent[] + EvidenceSpan[] + TemporalAnchor[] -> TradeAction[]
  v
F8 Backtest
  |  TradeAction[] + market_prices.csv -> BacktestResult + equity_curve
```

**Excluded stages**: F6 (Review/RLHF), F7 (Timeline/ViewpointState), F+ (Training Loop). These are post-MVP.

---

## 5. Stage Participation Table

| Stage | Required | MVP Responsibility | Input Schema | Output Schema | MVP Specifics |
|---|---|---|---|---|---|
| **F0** | Read-only | Provide frozen ContentRecords + raw files | N/A (pre-existing) | N/A (pre-existing) | F0 code does NOT execute. ContentRecords are read from disk. |
| **F1** | **Required** | Standardize each ContentRecord into ContentEnvelope + ContentBlocks | `ContentRecord` + raw file | `ContentEnvelope` with `ContentBlock[]` | Must handle the source_types present in the frozen set (at minimum: `feishu_chat`). Quality card populated. |
| **F1.5** | **Required** | Assemble ContentBlocks into TopicBlocks | `ContentBlock[]` from F1 | `TopicBlock[]` | F1.5 ALWAYS outputs TopicBlock[]. For single-topic content, a single TopicBlock wrapping all blocks is created. Multi-topic content (>= 3 blocks with mixed signals) is reorganized into multiple TopicBlocks. |
| **F2** | **Required** | Extract evidence spans, entity anchors, temporal anchors | `ContentEnvelope` + `ContentBlock[]` | `EvidenceSpan[]`, `EntityAnchor[]`, `TemporalAnchor[]` | Every EntityAnchor MUST have `resolved_symbol`. Every TemporalAnchor MUST have `resolved_time` (ISO 8601). Confidence >= 0.5 threshold. |
| **F3** | **Required** | Extract investment intents from anchored content | `TopicBlock[]` + `EvidenceSpan[]` + `EntityAnchor[]` + `TemporalAnchor[]` | `NormalizedInvestmentIntent[]` | Every intent MUST have `target_symbol` populated. F3 produces intents for ALL content, regardless of actionability. All intents pass to F4 for audit trail. |
| **F4** | **Required** | Map intents to policy-guided action hints | `NormalizedInvestmentIntent[]` + `PolicyContext` (from KOL Profile) | `PolicyMappingResult[]` + `PolicyMappedIntent[]` | F4 receives ALL F3 intents and produces a PolicyMappingResult for every one (audit trail). Only PolicyMappedIntents with `action_hint in ("open_position", "add_position", "reduce_position", "close_position", "hold_position")` pass to F5. `watch_only`, `review_required`, `avoid_or_watch_risk`, `watch_or_no_trade` are logged as audit records but do NOT enter F5. |
| **F5** | **Required** | Generate canonical TradeActions from policy-mapped intents | `PolicyMappedIntent[]` + `EvidenceSpan[]` + `TemporalAnchor[]` | `TradeAction[]` | Every TradeAction MUST have `execution_timing` populated. `action_executable_at` derived from market calendar. `canonical_trace_status` auto-set to `"canonical"` by validator. |
| **F6** | **Excluded** | — | — | — | No RLHF, no human review, no DPO. |
| **F7** | **Excluded** | — | — | — | No viewpoint state, no timeline aggregation. |
| **F8** | **Required** | Simulate portfolio from TradeActions + prices | `TradeAction[]` + `market_prices.csv` + `BacktestConfig` | `BacktestResult` + `equity_curve` | Entry at `action_executable_at` next-open price. Exit per policy holding period or signal reversal. `commission_pct=0`, `slippage_pct=0` for MVP (transaction costs are post-MVP). `max_holding_days=30`. |
| **F+** | **Excluded** | — | — | — | No training loop, no model fine-tuning. |

---

## 6. Hard Constraints

### 6.1 TradeAction Provenance Chain

Every TradeAction in the MVP output MUST satisfy:

```
TradeAction.intent_id         -> valid NormalizedInvestmentIntent.intent_id
TradeAction.policy_id         -> valid PolicyMappingResult.policy_id
TradeAction.evidence_span_ids -> len >= 1, each maps to valid EvidenceSpan.evidence_span_id
TradeAction.execution_timing  -> non-null ExecutionTiming with all required fields populated
TradeAction.canonical_trace_status -> "canonical" (auto-derived, not manually set)
```

A TradeAction generated by direct extraction from raw text (bypassing F3 + F4) is **forbidden** in the MVP. The legacy `TradeActionExtractor.extract_from_text()` path MUST NOT be used.

### 6.2 ExecutionTiming Requirements

Every `ExecutionTiming` MUST have:

- `intent_published_at`: from F1 `ContentEnvelope.published_at`
- `intent_effective_at`: from F2 `TemporalAnchor` (if resolved; null if no temporal anchor)
- `action_decision_at`: system processing timestamp
- `action_executable_at`: computed from market calendar (next market open after `intent_effective_at` or `intent_published_at`)
- `market`, `timezone`, `timing_policy_id`: all populated

### 6.3 F0 Boundary

F0 code does NOT execute during the MVP run. ContentRecords are read from disk as frozen inputs. The MVP MUST NOT:

- Re-ingest content from any source
- Call any F0 ingestion API
- Modify ContentRecords or raw files

### 6.4 Stage Isolation

- Each stage reads only from its allowed input schemas.
- No stage may skip upstream stages (e.g., F5 cannot bypass F3/F4).
- Cross-stage direct calls are forbidden (e.g., F5 calling F1 code).

### 6.5 Determinism

Given identical frozen inputs (ContentRecords, raw files, market_prices.csv, KOL Profile, BacktestConfig), the MVP MUST produce identical TradeActions and equity curve. LLM calls MUST use `temperature=0` and fixed seeds where supported.

---

## 7. Failure Conditions

An MVP run is considered **failed** if ANY of the following holds:

| # | Condition | Why it fails |
|---|---|---|
| F1 | Zero ContentEnvelopes produced from the frozen ContentRecords | Pipeline has no content to process |
| F2 | Zero EntityAnchors with `resolved_symbol` across all envelopes | No tradeable targets identified |
| F3 | Zero NormalizedInvestmentIntents with `actionability in ("explicit_action", "watch")` | No actionable signals extracted |
| F4 | Zero PolicyMappedIntents with `action_hint` allowing trade generation | Policy filtered out all signals |
| F5 | Zero TradeActions with `canonical_trace_status = "canonical"` | No canonical trades produced |
| F8 | BacktestResult has `trade_count = 0` | Nothing to backtest |
| ANY | Any TradeAction has `canonical_trace_status != "canonical"` in the final output | Provenance chain broken |
| ANY | Any stage raises an unhandled exception | Pipeline crash |
| ANY | Equity curve has a gap > 5 trading days that is not explained by `no_signal_period` metadata | Suspicious data gap |
| ANY | `max_drawdown_pct > 100%` or `total_return_pct < -100%` | Portfolio went negative (invalid simulation) |

---

## 8. Non-Goals

The MVP explicitly does NOT:

1. **Multi-KOL support** — Exactly one KOL per run. No cross-KOL comparison.
2. **Real trading** — No live orders, no broker integration, no paper trading.
3. **F6 Review / RLHF** — No human review loop, no DPO training data collection.
4. **F7 Timeline / ViewpointState** — No temporal opinion aggregation, no "KOL changed mind" detection.
5. **F+ Training Loop** — No model fine-tuning, no continuous learning.
6. **Strategy marketplace** — No reusable strategy configs, no strategy sharing.
7. **Real-time execution** — The MVP is batch-only, run against frozen historical data.
8. **Options / derivatives** — MVP handles equities only. Options pricing is out of scope.
9. **Multi-market arbitrage** — Single-market trades only per KOL content.
10. **Automated KOL discovery** — KOL profile is manually configured.
11. **Content quality scoring** — F1 standardization quality is used; no additional quality gates.
12. **Sentiment fusion** — No market sentiment overlay, no social signal aggregation.
13. **Look-ahead bias detection** — The timing chain prevents it by construction; no separate detector.

---

## 9. Open Questions

| # | Question | Impact | Default if Unresolved |
|---|---|---|---|
| O1 | Should MVP support `actionability = "watch"` intents entering F4, or only `explicit_action`? | Trade volume and noise level | **Resolved**: F4 receives ALL F3 intents (including opinion, watch, review_required) and produces a PolicyMappingResult for every one (audit trail). Only PolicyMappedIntents with executable `action_hint` (open_position, add_position, reduce_position, close_position, hold_position) pass to F5. |
| O2 | What is the default `BacktestConfig`? (initial capital, position sizing, commission, slippage, max holding days) | Equity curve shape and comparability | `initial_capital=100000`, `default_position_pct=0.10`, `commission_pct=0`, `slippage_pct=0`, `max_holding_days=30`. Transaction costs are post-MVP. |
| O3 | How should F1 handle content types not yet production-ready (e.g., audio, video)? | F1 adapter coverage | Fail the run with a clear error if unsupported source_type is encountered. No silent skip. |
| O4 | Should the equity curve track a benchmark (e.g., SPY) for relative performance? | Output completeness | Out of scope for MVP. `total_return_pct` is absolute only. Benchmark comparison is post-MVP. |
| O5 | What is the minimum content set size for a valid MVP run? A KOL with 3 posts may produce unreliable results. | Statistical validity | No minimum enforced. Run completes even with 1 TradeAction, but output metadata flags `insufficient_data` if `trade_count < 5`. |
| O6 | Should `F1.5 Topic Assembly` be mandatory or optional for the MVP? | Pipeline complexity | **Resolved**: F1.5 is mandatory — it ALWAYS outputs TopicBlock[]. For single-topic content, it creates one TopicBlock wrapping all blocks (no reorganization). Multi-topic content (>= 3 blocks with mixed signals) is reorganized into multiple TopicBlocks. F3 ONLY receives TopicBlock[], never raw ContentBlock[]. |
| O7 | How to handle tickers that resolve to multiple markets (e.g., `AAPL` on NASDAQ vs OTC)? | Entity resolution accuracy | Use the market from the KOL Profile's default market. If ambiguous and no KOL default, fail with `AMBIGUOUS_TICKER` error. |
| O8 | Should the MVP produce per-trade `BacktestResult` (on each TradeAction) or only the aggregate result? | Schema usage | Both. Each TradeAction gets a `backtest_result` with per-trade metrics. F8 also produces the aggregate `BacktestResult` with equity curve. |

---

## Appendix A: Schema Quick Reference

All schemas referenced above are defined in `src/finer/schemas/`:

| Schema | File |
|---|---|
| `ContentRecord` | `schemas/content.py` |
| `ContentEnvelope`, `ContentBlock`, `BlockQuality`, `BlockProvenance` | `schemas/content_envelope.py` |
| `TopicBlock` | `schemas/topic_block.py` |
| `EvidenceSpan` | `schemas/evidence.py` |
| `EntityAnchor` | `schemas/entity_anchor.py` |
| `TemporalAnchor` | `schemas/temporal.py` |
| `NormalizedInvestmentIntent` | `schemas/investment_intent.py` |
| `PolicyMappingResult`, `PolicyMappedIntent`, `PolicyContext` | `schemas/policy.py` |
| `TradeAction`, `ExecutionTiming`, `BacktestResult` | `schemas/trade_action.py` |
| `BacktestConfig`, `EquityPoint` | `backtest/engine.py` |

---

## Appendix B: MVP Run Lifecycle

```
1. Load inputs
   - Read KOL Profile from config
   - Read frozen ContentRecords from configured data path (default: data/F0_intake/; tests use tests/fixtures/kol-backtest-mvp/)
   - Read market_prices.csv

2. Execute pipeline (F1 -> F1.5 -> F2 -> F3 -> F4 -> F5)
   - Each stage produces artifacts on disk under data/F{N}_*/
   - Each stage logs provenance metadata

3. Execute backtest (F8)
   - Read TradeActions from F5 output
   - Join with market_prices.csv
   - Simulate portfolio
   - Write BacktestResult + equity_curve

4. Validate output
   - Every TradeAction has canonical_trace_status = "canonical"
   - Equity curve has no invalid gaps
   - Metrics are within sane bounds

5. Report
   - Write final BacktestResult to data/F8_metrics/
   - Print summary: trade count, total return, max drawdown, Sharpe
```
