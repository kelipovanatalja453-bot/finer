## F8: Backtest — MVP Contract

Stage: F8
MVP responsibility: Replay a single KOL's canonical TradeActions against historical market prices to produce per-trade returns, an equity curve, and aggregate performance metrics.

---

### Input Contract

F8 receives two inputs:

1. **Ordered TradeAction sequence** — a list of `TradeAction` objects from F5, sorted by `execution_timing.action_executable_at` ascending. For MVP, only `canonical_trace_status == "canonical"` actions are eligible. Actions with `partial` or `non_canonical` status are skipped with a logged skip-reason; they are not silently dropped.

2. **Market price table** — a flat file (CSV or in-memory DataFrame) with daily OHLCV bars. Required columns:

| Column | Type | Description |
|--------|------|-------------|
| `date` | `date` (YYYY-MM-DD) | Trading calendar date |
| `ticker` | `str` | Normalized ticker (must match `TradeAction.target.ticker_normalized`) |
| `open` | `float` | Session open price |
| `high` | `float` | Session high |
| `low` | `float` | Session low |
| `close` | `float` | Session close |
| `volume` | `int` | Session volume |

Date range must cover all `action_executable_at` dates plus a configurable look-forward window (default 90 trading days) for max-hold exit resolution.

---

### Output Contract

F8 produces a `BacktestReport` containing:

| Field | Type | Description |
|-------|------|-------------|
| `backtest_id` | `str` | UUID for this run |
| `run_timestamp` | `datetime` | When F8 executed |
| `kol_id` | `str` | KOL being backtested |
| `total_actions_in` | `int` | TradeActions received |
| `actions_backtested` | `int` | Actions that actually entered a position (non-skipped) |
| `actions_skipped` | `int` | Skipped actions with reasons |
| `initial_capital` | `float` | Starting capital (default 100,000) |
| `final_equity` | `float` | Portfolio value at end of period |
| `total_return_pct` | `float` | `(final_equity - initial_capital) / initial_capital * 100` |
| `max_drawdown_pct` | `float` | Worst peak-to-trough decline on equity curve |
| `sharpe_ratio` | `float` | Annualized Sharpe (risk-free rate = 0 for MVP) |
| `win_rate` | `float` | Fraction of closed trades with `return_pct > 0` |
| `trade_count` | `int` | Number of closed trades |
| `avg_holding_days` | `float` | Mean holding period across closed trades |
| `equity_curve` | `List[EquityPoint]` | Daily portfolio value series |
| `trade_details` | `List[TradeDetail]` | Per-trade breakdown |

`EquityPoint`:

| Field | Type |
|-------|------|
| `date` | `date` |
| `equity_value` | `float` |
| `drawdown_pct` | `float` |
| `open_positions` | `int` |

`TradeDetail`:

| Field | Type | Description |
|-------|------|-------------|
| `trade_action_id` | `str` | Back-reference to source TradeAction |
| `ticker` | `str` | Normalized ticker |
| `direction` | `str` | `long` / `short` |
| `entry_date` | `date` | Date position was opened |
| `entry_price` | `float` | Fill price at entry |
| `exit_date` | `date` | Date position was closed |
| `exit_price` | `float` | Fill price at exit |
| `exit_reason` | `ExitReason` | Why the position was closed |
| `return_pct` | `float` | Per-trade return |
| `holding_days` | `int` | Calendar days held |
| `max_drawdown_pct` | `float` | Worst intra-trade drawdown |
| `position_size_pct` | `float` | Portfolio fraction allocated |
| `pnl_absolute` | `float` | Dollar gain/loss |

---

### Execution Price Rules

MVP uses a deterministic "next-open" fill model to prevent look-ahead bias:

| Scenario | Entry price | Exit price |
|----------|-------------|------------|
| KOL content published before market open (market_session_at_publish in {pre_market, non_trading_day}) | Next trading day open | Next signal's entry or exit-day open |
| KOL content published during or after close (market_session_at_publish in {regular, after_close}) | Next trading day open | Next signal's entry or exit-day open |

In both cases, `action_executable_at` already encodes the earliest executable session from F5's timing policy. F8 uses the **open price of the first trading date >= `action_executable_at.date()`** as the entry fill.

Exit fills use the same convention: open price of the exit date.

If `execution_timing` is missing (should not happen for canonical actions), the action is skipped with reason `missing_execution_timing`.

---

### Position Sizing

- **Initial capital**: configurable, default 100,000 (currency unit matches price data).
- **Per-trade allocation**: `position_size_pct` from `ActionStep` (range 0-1). If absent, default to 0.10 (10% of current equity).
- **Capital is recycled**: realized PnL from closed trades returns to available cash. No leverage for MVP.
- **Max concurrent positions**: not capped for MVP. Each new entry allocates from current available equity.
- **Portfolio-level constraint**: if a new entry would exceed 100% allocated, reduce the position to fit remaining equity and log a warning.

---

### Holding and Exit Rules

MVP exit strategy (in priority order):

1. **Signal reversal**: A new TradeAction for the same `ticker_normalized` with an opposite `direction` (bullish -> bearish or vice versa) closes the existing position on the reversal signal's entry date. The reversal action simultaneously opens a new position in the opposite direction.

2. **Max-hold exit**: If no exit signal arrives within `max_hold_days` (default 90 trading days), close the position at the open price of the 91st trading day. Exit reason: `TIME_EXIT`.

3. **End-of-period**: At the end of the price data window, close all open positions at the last available close price. Exit reason: `END_OF_PERIOD`.

4. **Hold / Watch / Neutral signals**: Actions with `direction` in {`neutral`, `watchlist`, `risk_warning`} or `action_type` in {`hold`, `watch`} do not open or close positions. They are logged as observed-but-no-op.

For MVP, there are **no stop-loss or take-profit** mechanisms. The KOL's own signal reversal is the only active exit trigger.

---

### Edge Cases

| Case | Handling |
|------|----------|
| Ticker has no price data on entry date | Skip action, reason: `no_price_data` |
| Ticker has no price data on exit date | Use last available price before exit date; if none exist, skip, reason: `no_exit_price_data` |
| Ambiguous timing (action_executable_at is a non-trading day) | Roll forward to next trading day open |
| Contradictory signals (bullish then bearish within same session) | Both are processed in chronological order; the later one triggers reversal |
| Duplicate trade_action_id | Deduplicate by ID; keep first occurrence |
| direction = bearish + action_type = short | Open a short position (profit when price falls). For MVP, short PnL = `(entry_price - exit_price) / entry_price * 100` |
| direction = bearish, no explicit short action_type | Treat as no-op for MVP (no short-selling by default unless action_type explicitly says `short`) |
| position_size_pct = None | Default to 0.10 |
| Multiple action_chain steps | Only `sequence == 1` is used for MVP; multi-step chains are not executed |

---

### Required Fields from TradeAction

F8 requires these fields to be present and valid on each incoming TradeAction:

| Field | Validation |
|-------|------------|
| `trade_action_id` | Non-empty string |
| `target.ticker_normalized` | Non-empty, matches price data |
| `direction` | Must be one of: bullish, bearish, neutral, watchlist, risk_warning |
| `action_chain[0].action_type` | Must be determinable (first step exists) |
| `execution_timing.action_executable_at` | Valid datetime |
| `execution_timing.market` | Non-empty string |
| `canonical_trace_status` | Must be `"canonical"` |

If any required field is missing or invalid, the action is skipped (not fatal to the run) with a structured skip record containing `trade_action_id`, `skip_reason`, and `missing_field`.

---

### Forbidden Responsibilities

F8 must NOT:

- Fetch live or real-time market data (prices are provided as input)
- Modify TradeAction records (read-only)
- Generate new TradeActions or signals
- Compute slippage, commissions, or transaction costs (MVP)
- Handle dividends, splits, or delistings
- Support multi-KOL ranking or portfolio optimization
- Run LLM calls
- Write to F0-F7 data directories
- Expose a live trading API

---

### Failure Cases

| Failure | Severity | Handling |
|---------|----------|----------|
| No TradeActions provided | Fatal | Return empty BacktestReport with `actions_backtested = 0` |
| All actions skipped | Non-fatal | Return BacktestReport with zero trades, populate `actions_skipped` |
| Price data file missing or malformed | Fatal | Raise `FinerError` with stage=F8, code=`INVALID_PRICE_DATA` |
| Price data date range insufficient | Non-fatal | Backtest what is possible, log insufficient range warning |
| Ticker normalization mismatch between TradeAction and price data | Non-fatal per action | Skip affected actions, reason: `ticker_not_in_price_data` |

---

### Open Questions

1. **Short-selling model**: Should MVP support short positions at all, or only long? If short, do we need a borrowing cost model?
2. **Currency alignment**: TradeAction may target US/HK/CN tickers with different currencies. Should F8 convert to a single currency, or assume all prices are in the same unit for MVP?
3. **Intraday prices**: MVP uses daily OHLCV. If a KOL says "sell at 150" and the stock gaps from 149 to 151, should we model that the limit order fills? (Current design: no, we use open price only.)
4. **Equity curve granularity**: Daily is assumed. Should we support weekly/monthly aggregation?
5. **Backtest reproducibility**: Should `BacktestReport` include a hash of the price data + TradeAction list so results can be independently verified?
6. **Confidence-weighted sizing**: Should `TradeAction.confidence` influence position size? (Current design: no, MVP uses raw `position_size_pct`.)
