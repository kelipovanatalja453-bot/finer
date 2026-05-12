## F5: TradeAction Generation — MVP Contract

Stage: F5
MVP responsibility: Convert each PolicyMappedIntent into exactly one canonical TradeAction with complete provenance chain (intent_id + policy_id + evidence_span_ids + execution_timing).
Input contract: PolicyMappedIntent[] + EvidenceSpan[] + TemporalAnchor[] + ContentEnvelope.published_at
Output contract: TradeAction[] (every item with `canonical_trace_status = "canonical"`)
Required fields: (see table below)
Forbidden responsibilities: Intent extraction (F3), policy evaluation (F4), market data enrichment, backtesting (F8), human review routing (F6)
Failure cases: (see section below)
Open questions: (see section below)

---

### 1. Canonical Trace Rule

A TradeAction is canonical if and only if all four provenance elements are present and valid:

| Element | Source | Validation |
|---------|--------|------------|
| `intent_id` | `PolicyMappedIntent.intent_id` | Must resolve to a valid `NormalizedInvestmentIntent.intent_id` in the F3 output set |
| `policy_id` | `PolicyMappedIntent.policy_id` | Must resolve to a valid `PolicyMappingResult.policy_id` in the F4 output set |
| `evidence_span_ids` | `NormalizedInvestmentIntent.evidence_span_ids` (looked up via `intent_id`) | Length >= 1; each ID must resolve to a valid `EvidenceSpan.evidence_span_id` in the F2 output set |
| `execution_timing` | Computed by F5 (see section 3) | All four clocks populated; `timing_policy_id` set; `market` and `timezone` set |

The `canonical_trace_status` field is auto-derived by the TradeAction model validator — F5 does not set it explicitly. If any of the four elements is missing, the validator sets status to `partial` or `non_canonical`. For MVP, F5 MUST reject any PolicyMappedIntent that would produce a non-canonical TradeAction (see section 2).

F5 MUST NOT use the legacy `TradeActionExtractor.extract_from_text()` path. Every TradeAction must flow through F3 → F4 → F5.

---

### 2. Non-Canonical Rejection Rule

Before generating a TradeAction, F5 validates each PolicyMappedIntent against upstream data. If any check fails, F5 rejects the intent and logs a structured rejection record.

| Check | Failure Condition | Rejection Action |
|-------|-------------------|------------------|
| Intent lookup | `PolicyMappedIntent.intent_id` not found in F3 output | Skip with reason `intent_not_found` |
| Policy lookup | `PolicyMappedIntent.policy_id` not found in F4 output | Skip with reason `policy_not_found` |
| Evidence binding | `NormalizedInvestmentIntent.evidence_span_ids` is empty | Skip with reason `no_evidence_spans` |
| Evidence resolution | Any `evidence_span_id` not found in F2 output | Skip with reason `evidence_span_missing` |
| Ticker resolution | `NormalizedInvestmentIntent.target_symbol` is None or empty | Skip with reason `no_ticker_symbol` |
| Temporal resolution | No TemporalAnchor exists for this intent AND ContentEnvelope.published_at is missing | Skip with reason `no_temporal_anchor` |

Rejection records are written to the F5 output manifest as `rejected_intents[]` with fields: `intent_id`, `policy_id`, `reason`, `timestamp`. Rejected intents do NOT produce TradeActions. They are not silently dropped — they are auditable.

---

### 3. ExecutionTiming Four Clock Rule

Every TradeAction's `ExecutionTiming` contains four timestamps. F5 populates them as follows:

| Clock | Field | Source | Rule |
|-------|-------|--------|------|
| **Clock 1: Publication** | `intent_published_at` | `ContentEnvelope.published_at` (from F1) | Direct copy. This is when the KOL published the source content. Must be a valid `datetime`. |
| **Clock 2: Effectiveness** | `intent_effective_at` | `TemporalAnchor` with `anchor_type = "effective_trade_at"` or `anchor_type = "mentioned_at"` | If a TemporalAnchor with `resolved_time` exists for this intent, use its `resolved_time`. If multiple anchors exist, prefer `effective_trade_at` over `mentioned_at`. If none resolved, set to `None`. |
| **Clock 3: Decision** | `action_decision_at` | System clock | Timestamp when F5 generates this TradeAction. For MVP batch mode, this is the pipeline processing time. |
| **Clock 4: Executable** | `action_executable_at` | Computed from market calendar | See computation rule below. |

**Clock 4 Computation Rule:**

```
base_time = intent_effective_at if intent_effective_at is not None else intent_published_at
action_executable_at = next_market_open(base_time, market)
```

Where `next_market_open(t, market)` returns the opening time of the first trading session at or after datetime `t` for the given market. The market calendar is determined by `TradeAction.execution_timing.market` (sourced from `NormalizedInvestmentIntent.market` or KOL Profile default).

If `base_time` falls during a trading session (pre_market or regular), `action_executable_at` = next trading day's open (the signal cannot be acted upon within the same session for MVP).

If `base_time` falls after close or on a non-trading day, `action_executable_at` = next trading day's open.

The `timing_policy_id` field MUST be set to `"market-calendar-next-open-v1"` for all MVP TradeActions.

The `market_session_at_publish` field is determined by checking `intent_published_at` against the market calendar:
- Before market open → `pre_market`
- During regular hours → `regular`
- After close → `after_close`
- Non-trading day → `non_trading_day`

The `execution_delay_reason` field is populated when `action_executable_at > action_decision_at`, with a human-readable explanation (e.g., "published after market close, next open is Monday 09:30").

---

### 4. Action Step Mapping

F5 maps `PolicyMappedIntent.action_hint` → `ActionStep.action_type` using the F3 intent's `direction` to resolve ambiguity.

**Mapping Table:**

| `action_hint` | `direction = bullish` | `direction = bearish` | `direction = neutral/mixed/unknown` |
|---------------|----------------------|----------------------|-------------------------------------|
| `open_position` | `long` | `short` | `long` (default, with warning) |
| `add_position` | `long` | `short` | Skip: `ambiguous_direction_for_add` |
| `reduce_position` | `close_long` | `close_short` | Skip: `ambiguous_direction_for_reduce` |
| `close_position` | `close_long` | `close_short` | Skip: `ambiguous_direction_for_close` |
| `hold_position` | `hold` | `hold` | `hold` |
| `watch_only` | `watch` | `watch` | `watch` |
| `watch_or_no_trade` | `watch` | `watch` | `watch` |
| `avoid_or_watch_risk` | `watch` | `watch` | `watch` |
| `review_required` | Skipped by F4 filter — should not reach F5 | — | — |

**direction → TradeDirection mapping:**

| F3 `direction` | TradeAction `direction` |
|----------------|------------------------|
| `bullish` | `BULLISH` |
| `bearish` | `BEARISH` |
| `neutral` | `NEUTRAL` |
| `mixed` | `NEUTRAL` (with warning) |
| `unknown` | `NEUTRAL` (with warning) |

**Position size mapping (`position_sizing_hint` → `ActionStep.position_size_pct`):**

| `position_sizing_hint` | `position_size_pct` |
|------------------------|---------------------|
| `none` | `0.0` (no-op, but TradeAction is still generated as `watch`) |
| `small` | `0.05` |
| `medium` | `0.15` |
| `large` | `0.30` |
| `review_required` | Skipped by F4 filter — should not reach F5 |

If `risk_constraints.max_position_hint` is tighter than the mapped value, F5 clamps `position_size_pct` to the risk ceiling:

| `max_position_hint` | Ceiling |
|---------------------|---------|
| `none` | 0.0 |
| `small` | 0.10 |
| `medium` | 0.25 |
| `large` | 0.50 |

**Holding period mapping (`holding_period_hint` → `TradeAction.time_horizon`):**

| `holding_period_hint` | `time_horizon` |
|-----------------------|----------------|
| `intraday` | `"intraday"` |
| `short_term` | `"short_term"` |
| `medium_term` | `"medium_term"` |
| `long_term` | `"long_term"` |
| `review_required` | Skipped by F4 filter |

**Action chain structure:**

For MVP, every TradeAction has exactly one `ActionStep` with `sequence = 1`. Multi-step chains are post-MVP.

---

### 5. Evidence Binding

F5 selects which `EvidenceSpan` IDs to attach to a TradeAction using a deterministic, auditable process.

**Rule: Inherit all evidence from the F3 intent.**

```
TradeAction.evidence_span_ids = NormalizedInvestmentIntent.evidence_span_ids
```

F5 looks up the NormalizedInvestmentIntent via `PolicyMappedIntent.intent_id`, then copies its `evidence_span_ids` list verbatim. F5 does NOT filter, add, or re-rank evidence spans.

**Validation:** Every ID in the list must resolve to a valid `EvidenceSpan` in the F2 output. If any ID is unresolvable, the entire PolicyMappedIntent is rejected (see section 2).

**Minimum count:** `len(evidence_span_ids) >= 1`. This is enforced by the rejection rule (section 2: `no_evidence_spans` check).

**Source attribution:** The `TradeAction.source.evidence_text` field is populated by concatenating the `text` fields of all referenced EvidenceSpans, joined by `" | "`. If the concatenated text exceeds 500 characters, truncate to 500 with `"..."` suffix.

**Source content_id:** Populated from `NormalizedInvestmentIntent.envelope_id` (which traces back to the ContentEnvelope).

---

### 6. One-to-One Mapping Rule

For MVP, F5 produces **exactly one TradeAction per PolicyMappedIntent**. There is no fan-out (one intent → multiple actions) or fan-in (multiple intents → one action).

If a single content block expresses multiple intents (e.g., "buy AAPL, sell TSLA"), F3 produces multiple NormalizedInvestmentIntents, F4 produces multiple PolicyMappedIntents, and F5 produces one TradeAction per PolicyMappedIntent. The 1:1 relationship is maintained.

---

### 7. Required Fields Table

| TradeAction Field | Source | Required | Default |
|-------------------|--------|----------|---------|
| `trade_action_id` | Generated | Yes | UUID4 |
| `timestamp` | System clock | Yes | `datetime.now()` |
| `source.content_id` | `NormalizedInvestmentIntent.envelope_id` | Yes | — |
| `source.evidence_text` | Concatenated EvidenceSpan texts | Yes | — |
| `target.ticker` | `NormalizedInvestmentIntent.target_name` | Yes | — |
| `target.ticker_normalized` | `NormalizedInvestmentIntent.target_symbol` | Yes | Auto-normalized if None |
| `target.market` | `NormalizedInvestmentIntent.market` | Yes | — |
| `direction` | Mapped from F3 `direction` | Yes | — |
| `action_chain[0].action_type` | Mapped from `action_hint` + `direction` | Yes | — |
| `action_chain[0].position_size_pct` | Mapped from `position_sizing_hint`, clamped by risk | Yes | — |
| `intent_id` | `PolicyMappedIntent.intent_id` | Yes | — |
| `policy_id` | `PolicyMappedIntent.policy_id` | Yes | — |
| `evidence_span_ids` | Inherited from F3 intent | Yes | len >= 1 |
| `execution_timing` | Computed (see section 3) | Yes | — |
| `canonical_trace_status` | Auto-derived by validator | Yes | `"canonical"` |
| `confidence` | `PolicyMappedIntent.mapping_confidence` | Yes | — |
| `requires_manual_review` | `PolicyMappedIntent.requires_human_review` | Yes | `False` |
| `time_horizon` | Mapped from `holding_period_hint` | No | `None` |
| `rationale` | `PolicyMappedIntent.mapping_rationale` | No | `None` |

---

### 8. Failure Cases

| # | Condition | Severity | Handling |
|---|-----------|----------|----------|
| F5-1 | Zero PolicyMappedIntents received from F4 | Fatal | Return empty TradeAction[] with rejection log |
| F5-2 | All PolicyMappedIntents rejected | Non-fatal | Return empty TradeAction[] with full rejection log |
| F5-3 | Market calendar unavailable for target market | Fatal | Raise error `MARKET_CALENDAR_UNAVAILABLE` |
| F5-4 | ContentEnvelope.published_at is None | Fatal for that intent | Reject with reason `no_temporal_anchor` |
| F5-5 | NormalizedInvestmentIntent.target_symbol is None | Fatal for that intent | Reject with reason `no_ticker_symbol` |
| F5-6 | Evidence span ID resolution failure | Fatal for that intent | Reject with reason `evidence_span_missing` |
| F5-7 | Conflicting action_hint and direction (e.g., `open_position` + `bearish`) | Non-fatal | Generate TradeAction with appropriate action_type (`short`), log warning |
| F5-8 | `position_sizing_hint = "review_required"` bypasses F4 filter | Should not happen | Reject with reason `review_required_bypassed` |

---

### 9. Open Questions

| # | Question | Impact | Default if Unresolved |
|---|----------|--------|----------------------|
| O1 | How does F5 handle `action_hint = "add_position"` when no prior position exists for the ticker? Should it treat as `open_position` or reject? | Trade generation logic | Treat as `open_position` for MVP. F5 does not track portfolio state — that is F8's responsibility. |
| O2 | Should F5 populate `TradeAction.enrichment` (market data at time of action) or leave it for F8? | Schema completeness | Leave `enrichment = None` for MVP. F8 has access to market_prices.csv and can populate if needed. |
| O3 | What happens when `position_sizing_hint = "none"` but `action_hint` is `open_position`? Should F5 generate a TradeAction with `position_size_pct = 0` or skip? | Trade volume | Generate as `watch` action_type with `position_size_pct = 0`. The TradeAction exists for audit but has no position impact. |
| O4 | Should F5 validate that `target.ticker_normalized` exists in the market price data before generating the TradeAction? | Error detection timing | No. F5 does not have access to market_prices.csv. F8 handles ticker-not-found in price data. |
| O5 | How does F5 handle timezone for `action_executable_at` when KOL is in one timezone and market is in another? | Cross-market accuracy | Use the market's timezone (from `NormalizedInvestmentIntent.market` or KOL Profile default). All times in ExecutionTiming are in the market's timezone. |
| O6 | Should `reduce_position` generate a `close_long`/`close_short` with partial `position_size_pct`, or should it generate a separate "reduce" action type? | Action semantics | Generate `close_long`/`close_short` with the reduced position size. For MVP, there is no partial-close logic in F8 — it treats any close as full exit. Post-MVP, `position_size_pct` on close actions would indicate partial close. |
