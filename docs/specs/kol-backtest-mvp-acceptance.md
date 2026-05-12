# KOL Backtest MVP — Acceptance Criteria

> Version: 1.0.0 | Created: 2026-05-11
> Status: **Design** — pending team review
> References: `kol-backtest-mvp-contract.md`, `kol-backtest-mvp-stage-contracts.md`, `kol-backtest-mvp-fixture-contract.md`

---

## 1. End-to-End Pass Definition

An MVP run is **passing** if and only if ALL of the following hold:

1. The pipeline completes F1 -> F1.5 -> F2 -> F3 -> F4 -> F5 -> F8 without unhandled exceptions.
2. At least one `TradeAction` with `canonical_trace_status = "canonical"` is produced by F5.
3. The F8 `BacktestResult` has `trade_count >= 1`.
4. Every `TradeAction` in the final output has `canonical_trace_status = "canonical"`.
5. The equity curve has no gaps > 5 trading days (weekends/holidays excluded).
6. All metrics are within sane bounds: `max_drawdown_pct <= 100%`, `total_return_pct >= -100%`.
7. No `FinerError` or unhandled exception is raised at any stage.

An MVP run is **failed** if ANY of the failure conditions from `kol-backtest-mvp-contract.md` Section 7 are triggered:

| # | Condition | Why it fails |
|---|---|---|
| F1 | Zero ContentEnvelopes produced | Pipeline has no content to process |
| F2 | Zero EntityAnchors with `resolved_symbol` | No tradeable targets identified |
| F3 | Zero intents produced | Pipeline has no intents to process |
| F4 | Zero PolicyMappedIntents with executable `action_hint` | Policy filtered all signals |
| F5 | Zero TradeActions with `canonical_trace_status = "canonical"` | No canonical trades produced |
| F8 | `trade_count = 0` | Nothing to backtest |
| ANY | Any TradeAction has `canonical_trace_status != "canonical"` in final output | Provenance chain broken |
| ANY | Unhandled exception at any stage | Pipeline crash |
| ANY | Equity curve gap > 5 trading days without explanation | Suspicious data gap |
| ANY | `max_drawdown_pct > 100%` or `total_return_pct < -100%` | Portfolio went negative |

---

## 2. Stage-by-Stage Assertions

### 2.1 F1: Standardize

**Must-pass (run fails if any assertion fails):**

| # | Assertion | Validation |
|---|-----------|-----------|
| F1-M1 | At least 1 ContentEnvelope produced | `len(envelopes) >= 1` |
| F1-M2 | Every envelope has non-empty `envelope_id` | `envelope_id` is a non-empty string |
| F1-M3 | Every envelope has `published_at` as valid ISO 8601 | Parseable datetime with timezone |
| F1-M4 | Every envelope has at least 1 ContentBlock | `len(blocks) >= 1` |
| F1-M5 | Every ContentBlock has non-empty `text` | `len(text) > 0` |
| F1-M6 | Every ContentBlock has `quality` with all fields in [0,1] | `0 <= quality.* <= 1` |

**Should-pass (warnings, not failures):**

| # | Assertion | Validation |
|---|-----------|-----------|
| F1-S1 | `schema_version` matches expected value | `"1.0"` |
| F1-S2 | Quality scores are reasonable (not all 0 or all 1) | At least one score differs from others |
| F1-S3 | Block count matches expected for content type | Compare against fixture expectation |

### 2.2 F1.5: Topic Assembly

**Must-pass:**

| # | Assertion | Validation |
|---|-----------|-----------|
| F1.5-M1 | At least 1 TopicBlock produced per envelope | `len(topic_blocks) >= 1` |
| F1.5-M2 | Every TopicBlock has non-empty `topic_block_id` | Non-empty string |
| F1.5-M3 | Every TopicBlock has non-empty `source_block_ids` | `len(source_block_ids) >= 1` |
| F1.5-M4 | Every `source_block_ids` entry references a valid F1 block_id | Cross-reference check |
| F1.5-M5 | Every TopicBlock has non-empty `raw_text` | `len(raw_text) > 0` |

**Should-pass:**

| # | Assertion | Validation |
|---|-----------|-----------|
| F1.5-S1 | TopicBlock `topic_type` is semantically correct | Compare against fixture expectation |
| F1.5-S2 | `primary_entity_ids` contains expected entities | Compare against fixture expectation |
| F1.5-S3 | Multi-topic content produces > 1 TopicBlock | Only for c_007, c_010 fixtures |

### 2.3 F2: Anchor

**Must-pass:**

| # | Assertion | Validation |
|---|-----------|-----------|
| F2-M1 | At least 1 EntityAnchor with `resolved_symbol` across all envelopes | Pipeline-level check |
| F2-M2 | Every EntityAnchor has non-null `resolved_symbol` | Drop if null, fail if all dropped |
| F2-M3 | Every EntityAnchor has non-null `market` | Drop if null |
| F2-M4 | Every EntityAnchor has `confidence >= 0.5` | Drop below threshold |
| F2-M5 | At least 1 TemporalAnchor with `anchor_type = "published_at"` per envelope | Always created from published_at |
| F2-M6 | Every TemporalAnchor has non-null `resolved_time` (ISO 8601) | Drop if unresolvable |
| F2-M7 | Every TemporalAnchor has `confidence >= 0.5` | Drop below threshold |
| F2-M8 | Every EntityAnchor references a valid EvidenceSpan | `evidence_span_id` resolves |
| F2-M9 | Every EvidenceSpan `text` equals `block_text[char_start:char_end]` | Substring validation |

**Should-pass:**

| # | Assertion | Validation |
|---|-----------|-----------|
| F2-S1 | Entity count matches expected per content item | Compare against fixture |
| F2-S2 | TemporalAnchor types match expected | Compare against fixture |
| F2-S3 | EvidenceSpan count >= EntityAnchor count | At least one span per entity |

### 2.4 F3: Intent

**Must-pass:**

| # | Assertion | Validation |
|---|-----------|-----------|
| F3-M1 | At least 1 intent produced per content item with entities | `len(intents) >= 1` (except c_006) |
| F3-M2 | Every intent has non-empty `intent_id` | UUID format |
| F3-M3 | Every intent has non-empty `target_symbol` (MVP hard constraint) | Non-null, non-empty |
| F3-M4 | Every intent has `direction` in valid set | `bullish`, `bearish`, `neutral`, `mixed`, `unknown` |
| F3-M5 | Every intent has `actionability` in valid set | `opinion`, `watch`, `explicit_action`, `review_required` |
| F3-M6 | Every intent has `evidence_span_ids` with len >= 1 | Non-empty list |
| F3-M7 | Every `evidence_span_id` references a valid F2 EvidenceSpan | Cross-reference check |
| F3-M8 | Intents with `actionability = "explicit_action"` have `position_delta_hint` in {`open`, `add`, `reduce`, `hold`, `exit`} | Not `none` or `unknown` |
| F3-M9 | Intents with `actionability in ("opinion", "review_required")` have `position_delta_hint = "none"` | Consistency check |

**Should-pass:**

| # | Assertion | Validation |
|---|-----------|-----------|
| F3-S1 | Direction matches expected per content item | Compare against fixture |
| F3-S2 | Actionability matches expected per content item | Compare against fixture |
| F3-S3 | Conviction within tolerance (+/- 0.15) | Compare against fixture |
| F3-S4 | Confidence within tolerance (+/- 0.15) | Compare against fixture |
| F3-S5 | Multi-ticker content (c_007, c_010) produces correct intent count | 2 intents expected |

### 2.5 F4: Policy

**Must-pass:**

| # | Assertion | Validation |
|---|-----------|-----------|
| F4-M1 | Every F3 intent produces a PolicyMappingResult and PolicyMappedIntent (1:1 mapping, all actionability levels) | 1:1 mapping |
| F4-M2 | Every PolicyMappingResult has non-empty `policy_id` | UUID format |
| F4-M3 | Every PolicyMappingResult has `intent_id` referencing a valid F3 intent | Cross-reference check |
| F4-M4 | Every PolicyMappedIntent has `action_hint` in valid set | All defined action hints |
| F4-M5 | Every PolicyMappedIntent has `position_sizing_hint` in valid set | `none`, `small`, `medium`, `review_required` |
| F4-M6 | `action_hint` matches deterministic mapping from (actionability, direction, position_delta_hint) | Rule table lookup |
| F4-M7 | Executable gate correctly filters: only executable hints pass to F5. All other intents produce audit records but do NOT enter F5. | `open_position`, `add_position`, `reduce_position`, `close_position`, `hold_position` pass; `watch_only`, `watch_or_no_trade`, `avoid_or_watch_risk`, `review_required` are logged and excluded |

**Should-pass:**

| # | Assertion | Validation |
|---|-----------|-----------|
| F4-S1 | `holding_period_hint` matches expected per action_hint | Compare against rule table |
| F4-S2 | `confidence` within tolerance (+/- 0.15) | Compare against fixture |
| F4-S3 | `mapping_rationale` is non-empty and human-readable | String check |

### 2.6 F5: TradeAction

**Must-pass:**

| # | Assertion | Validation |
|---|-----------|-----------|
| F5-M1 | Every executable PolicyMappedIntent produces exactly 1 TradeAction | 1:1 mapping |
| F5-M2 | Every TradeAction has `canonical_trace_status = "canonical"` | Hard requirement for MVP |
| F5-M3 | Every TradeAction has non-empty `trade_action_id` | UUID format |
| F5-M4 | Every TradeAction has `intent_id` referencing a valid F3 intent | Cross-reference check |
| F5-M5 | Every TradeAction has `policy_id` referencing a valid F4 policy | Cross-reference check |
| F5-M6 | Every TradeAction has `evidence_span_ids` with len >= 1 | Non-empty list |
| F5-M7 | Every `evidence_span_id` references a valid F2 EvidenceSpan | Cross-reference check |
| F5-M8 | Every TradeAction has `execution_timing` with all 4 clocks populated | Non-null datetimes |
| F5-M9 | `execution_timing.timing_policy_id = "market-calendar-next-open-v1"` | Exact match |
| F5-M10 | `execution_timing.market` is non-empty | String check |
| F5-M11 | `execution_timing.timezone` is non-empty | String check |
| F5-M12 | `action_chain[0].action_type` is in valid set | `long`, `short`, `close_long`, `close_short`, `hold`, `watch` |
| F5-M13 | `direction` does not contradict F3 direction | Consistency check |
| F5-M14 | Only PolicyMappedIntents with executable `action_hint` produce TradeActions. Non-executable intents (watch_only, review_required, avoid_or_watch_risk, watch_or_no_trade) are excluded and logged as rejections. | Executable gate check |

**Should-pass:**

| # | Assertion | Validation |
|---|-----------|-----------|
| F5-S1 | `action_type` matches expected per content item | Compare against fixture |
| F5-S2 | `confidence` within tolerance (+/- 0.15) | Compare against fixture |
| F5-S3 | Rejection records are present for rejected intents | `rejected_intents[]` non-empty when applicable |
| F5-S4 | `source.evidence_text` is non-empty and a substring of raw content | Text validation |

### 2.7 F8: Backtest

**Must-pass:**

| # | Assertion | Validation |
|---|-----------|-----------|
| F8-M1 | `BacktestResult` is produced | Non-null |
| F8-M2 | `trade_count >= 1` | At least one trade executed |
| F8-M3 | `equity_curve` has no gaps > 5 trading days | Gap detection |
| F8-M4 | `max_drawdown_pct <= 100%` | Sane bounds |
| F8-M5 | `total_return_pct >= -100%` | Sane bounds |
| F8-M6 | Every TradeDetail has valid `entry_date`, `exit_date`, `entry_price`, `exit_price` | Non-null, sane values |
| F8-M7 | `entry_date <= exit_date` for every closed trade | Temporal consistency |
| F8-M8 | `initial_capital = 100000`, `commission_pct = 0`, `slippage_pct = 0`, `max_holding_days = 30` | Default BacktestConfig values |
| F8-M9 | Only `canonical_trace_status = "canonical"` actions enter backtest | Filter check |

**Should-pass:**

| # | Assertion | Validation |
|---|-----------|-----------|
| F8-S1 | `total_return_pct` within tolerance (+/- 0.5%) | Compare against fixture |
| F8-S2 | `max_drawdown_pct` within tolerance (+/- 1.0%) | Compare against fixture |
| F8-S3 | `sharpe_ratio` within tolerance (+/- 0.1) | Compare against fixture |
| F8-S4 | `win_rate` within tolerance (+/- 0.05) | Compare against fixture |
| F8-S5 | Equity curve row count matches trading days in range | 50 business days for fixture |

---

## 3. Cross-Stage Integrity Checks

These checks verify that the provenance chain is intact across stage boundaries.

### 3.1 F0 -> F1: source_record_id chain

| # | Check | Validation |
|---|-------|-----------|
| X-01 | Every ContentEnvelope's `source_content_id` matches a ContentRecord's `content_id` | 1:1 mapping |
| X-02 | `published_at` is preserved from ContentRecord to ContentEnvelope | Exact match |
| X-03 | `creator_id` is preserved from ContentRecord to ContentEnvelope | Exact match |

### 3.2 F1 -> F1.5: block_id references

| # | Check | Validation |
|---|-------|-----------|
| X-04 | Every TopicBlock's `source_block_ids` entries reference valid F1 ContentBlock `block_id` values | No orphan references |
| X-05 | TopicBlock `raw_text` is a concatenation of referenced blocks' `text` | Substring/content check |

### 3.3 F1.5 -> F3: source_block_ids -> evidence_span_ids

| # | Check | Validation |
|---|-------|-----------|
| X-06 | Every intent's `block_ids` entries reference valid F1 ContentBlock `block_id` values | No orphan references |
| X-07 | Every intent's `evidence_span_ids` entries reference valid F2 EvidenceSpan IDs | No orphan references |
| X-08 | Every referenced EvidenceSpan's `block_id` is in the intent's `block_ids` list | Evidence must come from intent's source blocks |

### 3.4 F2 -> F3: EntityAnchor -> target_symbol

| # | Check | Validation |
|---|-------|-----------|
| X-09 | Every intent's `target_symbol` matches an EntityAnchor's `resolved_symbol` from the same envelope | Symbol provenance |
| X-10 | Every intent's `market` matches the EntityAnchor's `market` | Market provenance |
| X-11 | Intents with `actionability != "review_required"` have `target_symbol` from an EntityAnchor with `confidence >= 0.5` | Quality threshold |

### 3.5 F2 -> F5: TemporalAnchor -> execution_timing

| # | Check | Validation |
|---|-------|-----------|
| X-12 | `TradeAction.execution_timing.intent_published_at` equals `ContentEnvelope.published_at` | Clock 1 provenance |
| X-13 | `TradeAction.execution_timing.intent_effective_at` (if non-null) matches a TemporalAnchor's `resolved_time` | Clock 2 provenance |
| X-14 | `action_executable_at >= intent_effective_at` (when both non-null) | Temporal ordering |
| X-15 | `action_executable_at >= intent_published_at` | Temporal ordering |

### 3.6 F3 -> F4 -> F5: intent_id -> policy_id -> TradeAction

| # | Check | Validation |
|---|-------|-----------|
| X-16 | Every `PolicyMappingResult.intent_id` resolves to a valid `NormalizedInvestmentIntent.intent_id` | FK integrity |
| X-17 | Every `PolicyMappedIntent.policy_id` resolves to a valid `PolicyMappingResult.policy_id` | FK integrity |
| X-18 | Every `TradeAction.intent_id` resolves to a valid `NormalizedInvestmentIntent.intent_id` | FK integrity |
| X-19 | Every `TradeAction.policy_id` resolves to a valid `PolicyMappingResult.policy_id` | FK integrity |
| X-20 | `TradeAction.direction` does not contradict the F3 intent's `direction` | Semantic consistency |
| X-21 | `TradeAction.action_chain[0].action_type` is consistent with `PolicyMappedIntent.action_hint` | Mapping consistency |

### 3.7 F5 -> F8: canonical TradeAction -> BacktestResult

| # | Check | Validation |
|---|-------|-----------|
| X-22 | Every TradeDetail's `trade_action_id` references a valid TradeAction | FK integrity |
| X-23 | Every TradeDetail's `ticker` matches the TradeAction's `target.ticker_normalized` | Ticker consistency |
| X-24 | Every TradeDetail's `entry_date` matches `execution_timing.action_executable_at.date()` (or later) | Entry timing |
| X-25 | `BacktestResult.actions_backtested + BacktestResult.actions_skipped == BacktestResult.total_actions_in` | Accounting check |
| X-26 | Equity curve first date <= earliest entry date | Timeline start |
| X-27 | Equity curve last date >= latest exit date | Timeline end |

---

## 4. Output Validation Rules

### 4.1 TradeAction Canonical Status

Every TradeAction in the final F5 output MUST have `canonical_trace_status = "canonical"`. This is validated by checking:

```
assert action.canonical_trace_status == "canonical"
assert action.intent_id is not None
assert action.policy_id is not None
assert len(action.evidence_span_ids) >= 1
assert action.execution_timing is not None
assert action.execution_timing.intent_published_at is not None
assert action.execution_timing.action_decision_at is not None
assert action.execution_timing.action_executable_at is not None
assert action.execution_timing.market is not None
assert action.execution_timing.timezone is not None
assert action.execution_timing.timing_policy_id is not None
```

### 4.2 Equity Curve Integrity

The equity curve must satisfy:

1. **No gaps > 5 trading days**: consecutive `date` values must not skip more than 5 trading days (weekends and holidays are excluded by the trading calendar).
2. **Monotonic dates**: `date[i] < date[i+1]` for all i.
3. **Positive equity**: `equity_value > 0` for all points (portfolio cannot go negative without leverage).
4. **Consistent accounting**: `equity_value = cash + positions_value` at every point.
5. **First point**: `equity_value == initial_capital` and `positions_value == 0`.

### 4.3 Metric Bounds

| Metric | Lower Bound | Upper Bound | Rationale |
|--------|-------------|-------------|-----------|
| `max_drawdown_pct` | 0.0 | 100.0 | Cannot be negative; cannot exceed total loss |
| `total_return_pct` | -100.0 | No hard cap | Cannot lose more than 100% without leverage |
| `sharpe_ratio` | No hard cap | No hard cap | Depends on return distribution |
| `win_rate` | 0.0 | 1.0 | Fraction of winning trades |
| `trade_count` | 0 | `total_actions_in` | Cannot exceed input count |
| `avg_holding_days` | 0 | `max_hold_days` | Bounded by exit policy |

### 4.4 Provenance Chain Completeness

For every canonical TradeAction, the full provenance chain must be traversable:

```
TradeAction
  -> intent_id -> NormalizedInvestmentIntent
    -> envelope_id -> ContentEnvelope
      -> source_content_id -> ContentRecord
    -> block_ids -> ContentBlock[]
    -> evidence_span_ids -> EvidenceSpan[]
      -> block_id -> ContentBlock
  -> policy_id -> PolicyMappingResult
    -> intent_id -> (back to NormalizedInvestmentIntent)
  -> execution_timing
    -> intent_published_at -> ContentEnvelope.published_at
    -> intent_effective_at -> TemporalAnchor.resolved_time (if exists)
```

---

## 5. Future Test Design: `test_kol_backtest_mvp.py`

### 5.1 Test Structure — Parametrized Dual-KOL

```python
import pytest
from pathlib import Path

KOL_FIXTURES = ["cat_lord", "trader_ji"]

@pytest.fixture(params=KOL_FIXTURES, ids=KOL_FIXTURES)
def kol_fixture_dir(request):
    """Parametrized fixture: each KOL runs independently."""
    return Path(f"tests/fixtures/kol-backtest-mvp/{request.param}")

@pytest.fixture
def kol_profile(kol_fixture_dir):
    return load_json(kol_fixture_dir / "kol_profile.json")

@pytest.fixture
def market_prices(kol_fixture_dir):
    return load_csv(kol_fixture_dir / "market_prices.csv")

@pytest.fixture
def content_records(kol_fixture_dir):
    return [load_manifest(p) for p in sorted(kol_fixture_dir.glob("content/*.manifest.json"))]
```

**Test execution**:
```
pytest tests/test_kol_backtest_mvp.py -v
# Runs:
#   test_kol_backtest_mvp[cat_lord] — full pipeline on Cat Lord fixtures
#   test_kol_backtest_mvp[trader_ji] — full pipeline on Trader Ji fixtures
```

**Pass condition**: Both KOLs independently produce canonical TradeActions, BacktestResult, and equity curve. No cross-KOL assertions.

### 5.2 Per-Stage Tests

**F1 test:**
```python
def test_f1_standardize(self, content_records):
    envelopes = [f1_standardize(cr) for cr in content_records]
    for envelope in envelopes:
        assert envelope.envelope_id is not None
        assert envelope.published_at is not None
        assert len(envelope.blocks) >= 1
        for block in envelope.blocks:
            assert len(block.text) > 0
            assert 0 <= block.quality.readability <= 1
```

**F1.5 test:**
```python
def test_f15_topic_assembly(self, envelopes):
    results = [f15_assemble(env) for env in envelopes]
    for result in results:
        assert len(result.topic_blocks) >= 1
        for tb in result.topic_blocks:
            assert tb.topic_block_id is not None
            assert len(tb.source_block_ids) >= 1
            assert len(tb.raw_text) > 0
```

**F2 test:**
```python
def test_f2_anchor(self, envelopes, topic_blocks, kol_profile):
    anchored = [f2_anchor(env, tbs, kol_profile) for env, tbs in zip(envelopes, topic_blocks)]
    for result in anchored:
        assert len(result.entity_anchors) >= 1  # except c_006
        for ea in result.entity_anchors:
            assert ea.resolved_symbol is not None
            assert ea.market is not None
            assert ea.confidence >= 0.5
        for ta in result.temporal_anchors:
            assert ta.resolved_time is not None
            assert ta.confidence >= 0.5
```

**F3 test:**
```python
def test_f3_intent(self, topic_blocks, entity_anchors, temporal_anchors, evidence_spans):
    results = [f3_extract(tb, ea, ta, es) for tb, ea, ta, es in ...]
    for result in results:
        for intent in result.intents:
            assert intent.intent_id is not None
            assert intent.target_symbol is not None
            assert intent.direction in ("bullish", "bearish", "neutral", "mixed", "unknown")
            assert len(intent.evidence_span_ids) >= 1
```

**F4 test:**
```python
def test_f4_policy(self, intents, policy_context):
    # F4 receives ALL intents, not just actionable ones
    results = [f4_map(intent, policy_context) for intent in intents]
    for result in results:
        assert result.policy_id is not None
        assert result.action_hint in VALID_ACTION_HINTS
        assert result.position_sizing_hint in VALID_SIZING_HINTS
    # Verify executable gate: only executable hints should pass to F5
    executable = [r for r in results if r.action_hint in EXECUTABLE_HINTS]
    assert len(executable) >= 1  # At least one executable action
```

**F5 test:**
```python
def test_f5_trade_action(self, policy_mapped_intents, evidence_spans, temporal_anchors, envelope):
    actions, rejections = f5_execute(policy_mapped_intents, evidence_spans, temporal_anchors, envelope)
    # All produced actions must be canonical
    for action in actions:
        assert action.canonical_trace_status == "canonical"
        assert action.intent_id is not None
        assert action.policy_id is not None
        assert len(action.evidence_span_ids) >= 1
        assert action.execution_timing is not None
        assert action.execution_timing.timing_policy_id == "market-calendar-next-open-v1"
    # Rejection records must have structured reasons
    for rej in rejections:
        assert rej.intent_id is not None
        assert rej.rejection_reason is not None
        assert rej.rejection_stage in ("F4", "F5")
```

**F8 test:**
```python
def test_f8_backtest(self, canonical_actions, market_prices, backtest_config):
    result = f8_backtest(canonical_actions, market_prices, backtest_config)
    assert result.trade_count >= 1
    assert result.max_drawdown_pct <= 100
    assert result.total_return_pct >= -100
    # Verify equity curve gaps
    dates = [p.date for p in result.equity_curve]
    for i in range(1, len(dates)):
        gap = count_trading_days(dates[i-1], dates[i])
        assert gap <= 5
```

### 5.3 End-to-End Test

```python
def test_e2e_pipeline(self, content_records, kol_profile, market_prices, backtest_config):
    """Full pipeline: F0 input -> F8 output."""
    # F1
    envelopes = [f1_standardize(cr) for cr in content_records]

    # F1.5
    topic_results = [f15_assemble(env) for env in envelopes]

    # F2
    anchor_results = [f2_anchor(env, tr, kol_profile) for env, tr in zip(envelopes, topic_results)]

    # F3
    intent_results = [f3_extract(tr, ar) for tr, ar in zip(topic_results, anchor_results)]

    # F4 — ALL intents enter F4, not just actionable ones
    all_intents = [i for r in intent_results for i in r.intents]
    policy_results = [f4_map(intent, kol_profile) for intent in all_intents]
    executable_policies = [p for p in policy_results
                           if p.action_hint in EXECUTABLE_HINTS]

    # F5
    all_actions = []
    for pm in executable_policies:
        actions = f5_execute(pm, evidence_spans, temporal_anchors, envelope)
        all_actions.extend(actions)

    canonical_actions = [a for a in all_actions if a.canonical_trace_status == "canonical"]
    assert len(canonical_actions) >= 1

    # F8
    backtest_result = f8_backtest(canonical_actions, market_prices, backtest_config)
    assert backtest_result.trade_count >= 1
    assert backtest_result.max_drawdown_pct <= 100
    assert backtest_result.total_return_pct >= -100
```

### 5.4 Cross-Stage Integrity Test

```python
def test_provenance_chain(self, all_stage_outputs):
    """Verify full provenance chain from TradeAction back to ContentRecord."""
    for action in all_stage_outputs.f5_actions:
        if action.canonical_trace_status != "canonical":
            continue

        # intent_id resolves
        intent = find_by_id(all_stage_outputs.f3_intents, action.intent_id)
        assert intent is not None

        # policy_id resolves
        policy = find_by_id(all_stage_outputs.f4_policies, action.policy_id)
        assert policy is not None
        assert policy.intent_id == action.intent_id

        # evidence_span_ids resolve
        for span_id in action.evidence_span_ids:
            span = find_by_id(all_stage_outputs.f2_spans, span_id)
            assert span is not None

        # envelope_id resolves
        envelope = find_by_id(all_stage_outputs.f1_envelopes, intent.envelope_id)
        assert envelope is not None

        # execution_timing provenance
        assert action.execution_timing.intent_published_at == envelope.published_at
```

---

## 6. Acceptance Checklist

### 6.1 Contract Completeness

- [ ] `kol-backtest-mvp-contract.md` — MVP total contract is frozen
- [ ] `kol-backtest-mvp-stage-contracts.md` — All 7 stage contracts (F1, F1.5, F2, F3, F4, F5, F8) are consolidated
- [ ] `kol-backtest-mvp-fixture-contract.md` — Fixture contract defines 10 content items, 5 tickers, expected outputs per stage

### 6.2 Schema Readiness

- [ ] `ContentEnvelope` schema supports all F1 output fields
- [ ] `TopicBlock` schema supports all F1.5 output fields
- [ ] `EntityAnchor`, `TemporalAnchor`, `EvidenceSpan` schemas support all F2 output fields
- [ ] `NormalizedInvestmentIntent` schema supports all F3 output fields
- [ ] `PolicyMappingResult`, `PolicyMappedIntent` schemas support all F4 output fields
- [ ] `TradeAction`, `ExecutionTiming` schemas support all F5 output fields
- [ ] `BacktestResult`, `EquityPoint`, `TradeDetail` schemas support all F8 output fields

### 6.3 Implementation Readiness

- [ ] F1 standardizer handles at least `feishu_chat` and `wechat` source types
- [ ] F1.5 topic assembler handles single-topic and multi-topic content
- [ ] F2 entity resolution produces `resolved_symbol` and `market` for all MVP entity types
- [ ] F2 temporal resolution produces `resolved_time` for `published_at` anchors
- [ ] F2 evidence span creation produces valid `char_start`/`char_end` offsets
- [ ] F3 intent extraction produces intents with `target_symbol` populated
- [ ] F3 actionability classification uses the ordered rule procedure
- [ ] F4 policy mapping uses `GlobalBasePolicy` deterministic rule table
- [ ] F4 executable gate correctly filters non-executable hints
- [ ] F5 TradeAction generation produces `canonical_trace_status = "canonical"` for all executable intents
- [ ] F5 ExecutionTiming four-clock rule is implemented
- [ ] F5 evidence binding inherits from F3 intent
- [ ] F8 backtest engine uses next-open fill model
- [ ] F8 exit rules handle signal reversal, max-hold, and end-of-period
- [ ] F8 equity curve has no gaps > 5 trading days

### 6.4 Fixture Readiness — Cat Lord

- [ ] `cat_lord/kol_profile.json` is created with Cat Lord (猫大人FIRE) persona
- [ ] `cat_lord/content/` has 10 content items (manifests + raw files)
- [ ] `cat_lord/market_prices.csv` covers 2026-03-01 to 2026-05-09 for 6 tickers (CSIQ, LI, TME, TSLA, 600989, NVDA)
- [ ] Expected F1-F5 outputs (10 per stage) are created
- [ ] Expected F5 rejections (5 records) are created
- [ ] Expected F8 outputs (backtest result + equity curve) are created

### 6.4b Fixture Readiness — Trader Ji

- [ ] `trader_ji/kol_profile.json` is created with Trader Ji (9友) persona
- [ ] `trader_ji/content/` has 15 content items (manifests + raw files)
- [ ] `trader_ji/market_prices.csv` covers 2026-03-01 to 2026-05-09 for 8 tickers (510300, 159915, 600519, 000858, 601318, 000001, 601012, 399006)
- [ ] Expected F1-F5 outputs (15 per stage) are created
- [ ] Expected F5 rejections (7 records) are created
- [ ] Expected F8 outputs (backtest result + equity curve) are created

### 6.5 Test Readiness

- [ ] `test_kol_backtest_mvp.py` exists with per-stage tests
- [ ] End-to-end pipeline test passes
- [ ] Cross-stage integrity test passes
- [ ] All must-pass assertions pass
- [ ] Should-pass assertions are documented (warnings allowed)

### 6.6 Acceptance Sign-off

| Criterion | Status | Sign-off |
|-----------|--------|----------|
| All stage contracts consolidated | [ ] | |
| Fixture contract complete | [ ] | |
| MVP contract frozen | [ ] | |
| Schema readiness verified | [ ] | |
| Implementation readiness verified | [ ] | |
| Fixture data created | [ ] | |
| Tests written and passing | [ ] | |
| No open blocking questions | [ ] | |

---

## Appendix: Open Questions Summary

The following open questions across all stage contracts may affect acceptance. Each has a default resolution if left unresolved.

| Stage | # | Question | Default |
|-------|---|----------|---------|
| F2 | O1 | Entity resolution method (lookup vs LLM vs hybrid) | Hybrid: lookup first, LLM fallback |
| F2 | O5 | Symbol existence validation | Format only for MVP |
| F3 | O1 | Sector-level intents in MVP | Keep, mark as `watch` |
| F3 | O4 | Intent merging across TopicBlocks | Keep separate for MVP |
| F4 | O1 | All intents entering F4 | Yes, ALL intents enter F4. Non-executable hints filtered at executable gate before F5. |
| F4 | O2 | Holding period conviction-adjusted | No |
| F5 | O1 | add_position with no prior position | Treat as open_position |
| F5 | O2 | F5 populating enrichment | Leave for F8 |
| F5 | O5 | Cross-market timezone handling | Use market timezone |
| F8 | O1 | Short-selling model | Support shorts, no borrow cost |
| F8 | O2 | Currency alignment | Same unit assumed |
| F8 | O6 | Confidence-weighted sizing | No for MVP |

None of these are blocking for MVP acceptance — all have reasonable defaults. They may be revisited post-MVP.
