# F4: Policy — MVP Contract

> Version: 1.0.0 | Created: 2026-05-11
> Status: **Design** — pending team review
> Depends on: kol-backtest-mvp-contract.md (frozen), F3 Intent Contract

---

```
Stage: F4
MVP responsibility: Map each F3 NormalizedInvestmentIntent to policy-guided action hints via deterministic rule table, filtering non-executable intents
Input contract:  NormalizedInvestmentIntent[] (from F3) + PolicyContext (from KOL Profile)
Output contract: PolicyMappingResult[] + PolicyMappedIntent[] (to F5)
Required fields: policy_id, intent_id, action_hint, position_sizing_hint, holding_period_hint, risk_constraints, mapping_rationale, confidence
Forbidden responsibilities: LLM calls, raw text reading, TradeAction generation, execution price determination, multi-layer policy stack, strategy marketplace
Failure cases: Zero PolicyMappedIntents with executable action_hint; intent references invalid intent_id
Open questions: O1 (watch signal handling — resolved below), O2 (holding period tuning)
```

---

## 1. Stage Overview

F4 is a pure rule-based mapping layer that converts F3 intents into policy-guided hints for F5. It answers: "Given what the KOL said and how they said it, what action should a follower consider, and at what scale?"

For MVP, F4 uses only the `GlobalBasePolicy` — a single deterministic rule table. Higher layers (StyleArchetype, RiskPreference, KOLPersona, ContentCorrection) are post-MVP.

---

## 2. Input Contract

F4 receives:

| Field | Source | Description |
|---|---|---|
| `NormalizedInvestmentIntent[]` | F3 | List of extracted intents, each with actionability, direction, position_delta_hint, conviction, confidence, evidence_span_ids |
| `PolicyContext` | KOL Profile config | kol_id, style_archetype (default: "mixed"), risk_preference (default: "balanced") |

### Pre-filter (F3 gate)

Only intents with `actionability in ("explicit_action", "watch")` enter F4. `opinion`-only intents are excluded upstream in F3. This is defined in the MVP contract Section 5 (F3 row).

---

## 3. Output Contract

F4 produces two linked records per intent:

### 3.1 PolicyMappingResult

The full audit record. One per intent.

| Field | Type | Required | Description |
|---|---|---|---|
| `policy_id` | `str` (UUID) | Yes | Unique identifier for this mapping result |
| `intent_id` | `str` | Yes | Back-reference to F3 NormalizedInvestmentIntent.intent_id |
| `policy_version` | `str` | Yes | "global-base-v1" for MVP |
| `policy_layers_applied` | `List[str]` | Yes | ["GlobalBase"] for MVP |
| `action_hint` | `ACTION_HINT_LITERAL` | Yes | Policy-guided action (see Section 4) |
| `position_sizing_hint` | `POSITION_SIZING_HINT_LITERAL` | Yes | none / small / medium (see Section 5) |
| `holding_period_hint` | `HOLDING_PERIOD_HINT_LITERAL` | Yes | short_term / medium_term (see Section 6) |
| `risk_constraints` | `PolicyRiskConstraints` | Yes | Risk bounds (see Section 8) |
| `mapping_rationale` | `str` | Yes | Human-readable explanation of mapping decision |
| `confidence` | `float` (0-1) | Yes | Mapping confidence (derived from F3 confidence) |
| `layer_traces` | `List[PolicyLayerTrace]` | No | Per-layer audit trail (one entry for GlobalBase) |
| `decisions` | `List[PolicyDecision]` | No | Atomic policy decisions |

### 3.2 PolicyMappedIntent

The compact output consumed by F5. One per intent.

| Field | Type | Required | Description |
|---|---|---|---|
| `mapped_id` | `str` (UUID) | Yes | Unique identifier for this mapping |
| `intent_id` | `str` | Yes | Back-reference to F3 intent |
| `policy_id` | `str` | Yes | Back-reference to PolicyMappingResult |
| `original_intent_summary` | `str` | Yes | Human-readable summary of the F3 intent |
| `action_hint` | `ACTION_HINT_LITERAL` | Yes | Copied from PolicyMappingResult |
| `position_sizing_hint` | `POSITION_SIZING_HINT_LITERAL` | Yes | Copied from PolicyMappingResult |
| `holding_period_hint` | `HOLDING_PERIOD_HINT_LITERAL` | Yes | Copied from PolicyMappingResult |
| `risk_notes` | `List[str]` | No | Risk notes from policy evaluation |
| `mapping_confidence` | `float` (0-1) | Yes | Copied from PolicyMappingResult.confidence |
| `requires_human_review` | `bool` | Yes | True if action_hint or sizing is review_required |

---

## 4. Executable / Rejected Decision Rule

### 4.1 Action Hint Mapping

F4 maps the F3 intent triple `(actionability, direction, position_delta_hint)` to an `action_hint` using a deterministic lookup table. The complete table is defined in `src/finer/policy/global_base.py:_ACTION_RULES`.

**Key mapping rules for MVP:**

| actionability | direction | position_delta_hint | action_hint |
|---|---|---|---|
| `explicit_action` | `bullish` | `open` | `open_position` |
| `explicit_action` | `bullish` | `add` | `add_position` |
| `explicit_action` | `bullish`/`bearish`/`neutral`/`mixed` | `reduce` | `reduce_position` |
| `explicit_action` | `bullish`/`bearish`/`neutral`/`mixed` | `hold` | `hold_position` |
| `explicit_action` | `bullish`/`bearish`/`neutral`/`mixed` | `exit` | `close_position` |
| `explicit_action` | `bearish` | `open` | `review_required` |
| `explicit_action` | any | `none`/`unknown` | `review_required` |
| `watch` | any | any | `watch_only` |
| `opinion` | `bullish` | any | `watch_or_no_trade` |
| `opinion` | `bearish` | any | `avoid_or_watch_risk` |
| `opinion` | `neutral`/`mixed`/`unknown` | any | `watch_only` |

**Fallback**: If no rule matches, `explicit_action` defaults to `review_required`; `opinion`/`watch` defaults to `watch_only`.

### 4.2 Executable Gate

After mapping, F4 applies the MVP executable gate:

**Executable** (passed to F5):
- `open_position`
- `add_position`
- `reduce_position`
- `close_position`
- `hold_position`

**Rejected** (logged but excluded from F5):
- `watch_only` — observation signal, no trade warranted
- `watch_or_no_trade` — opinion-level, no action
- `avoid_or_watch_risk` — risk avoidance signal
- `review_required` — ambiguous or requires human judgment

Rejected intents still produce `PolicyMappingResult` and `PolicyMappedIntent` records for audit trail, but F5 does not receive them.

### 4.3 Design Rationale

The executable gate is binary: either the intent is clear enough to simulate a trade, or it is not. There is no partial execution or "soft" gate in MVP. This keeps the backtest deterministic and auditable — every TradeAction has a clear F3→F4→F5 lineage with no ambiguity about why a signal was included or excluded.

---

## 5. Minimum Sizing Rule

### 5.1 Conviction-Based Sizing

Position sizing is derived from the F3 `conviction` score (0.0–1.0) through fixed bands:

| Conviction Range | position_sizing_hint |
|---|---|
| `< 0.35` | `none` |
| `0.35 – 0.70` | `small` |
| `> 0.70` | `medium` |

**Global base ceiling**: The GlobalBasePolicy never outputs `large`. That requires higher policy layers (post-MVP). Even if conviction is 1.0, the maximum sizing hint is `medium`.

### 5.2 Non-Trade Override

For any `action_hint` that is not a trade action (`watch_only`, `watch_or_no_trade`, `avoid_or_watch_risk`, `review_required`), `position_sizing_hint` is forced to `none` regardless of conviction.

### 5.3 Ambiguity Override

If the F3 intent has `len(ambiguity_flags) >= 2`, `position_sizing_hint` is forced to `review_required` regardless of conviction.

### 5.4 What position_sizing_hint Is NOT

`position_sizing_hint` is a qualitative band (none/small/medium), not a percentage. F5 resolves it to an actual portfolio weight using `BacktestConfig.default_position_pct` and the hint as a multiplier. F4 does not know the portfolio size, current positions, or available cash.

---

## 6. Minimum Timing Rule

### 6.1 Holding Period Assignment

Holding period is derived from `action_hint` alone — conviction does not affect it:

| action_hint | holding_period_hint |
|---|---|
| `open_position` | `medium_term` |
| `add_position` | `medium_term` |
| `reduce_position` | `short_term` |
| `hold_position` | `medium_term` |
| `close_position` | `short_term` |
| `watch_only` | `review_required` |
| `watch_or_no_trade` | `review_required` |
| `avoid_or_watch_risk` | `review_required` |
| `review_required` | `review_required` |

### 6.2 Interpretation

- `short_term` = days to weeks (F5 uses `BacktestConfig.max_holding_days` default of 30)
- `medium_term` = weeks to months (F5 may use up to 90 days or signal reversal)

The actual exit timing is determined by F5 (signal reversal, stop-loss, or max holding period). F4 only sets the expectation.

### 6.3 Why Not Conviction-Based Timing

High conviction does not imply longer holding. A high-conviction day-trade signal should be `short_term`, not `medium_term`. The action semantics (open = build, exit = close) are more informative than conviction for holding period.

---

## 7. Policy ID Generation

### 7.1 Generation Method

`policy_id` is a UUID v4 generated at mapping time. Each `PolicyMappingResult` gets a unique `policy_id`.

### 7.2 Tracking

- `PolicyMappingResult.policy_id` — the canonical identifier
- `PolicyMappedIntent.policy_id` — references the same ID
- Downstream `TradeAction.policy_id` — references the same ID

The `policy_id` enables full traceability: given a TradeAction, you can look up the PolicyMappingResult, which references the F3 intent, which references the F2 evidence spans.

### 7.3 No Policy Registry in MVP

MVP does not maintain a policy registry or policy version history. `policy_version = "global-base-v1"` is a label for reproducibility, not a lookup key. Post-MVP, multiple policy versions may coexist.

---

## 8. Risk Constraints

### 8.1 MVP Risk Bounds

F4 attaches a `PolicyRiskConstraints` to every `PolicyMappingResult`:

| Field | Rule | Description |
|---|---|---|
| `max_position_hint` | `none` if non-trade; `medium` if conviction >= 0.7; else `small` | Upper bound on position size |
| `requires_human_review` | True if action_hint is `review_required`, or ambiguity_flags >= 2, or conviction < 0.3 on trade actions | Whether human must review before F5 |
| `risk_notes` | Auto-generated list | Human-readable risk annotations |
| `max_concentration_pct` | `None` (not set in MVP) | Post-MVP: sector/ticker concentration cap |
| `stop_loss_hint` | `None` (not set in MVP) | Post-MVP: natural-language stop-loss |
| `time_decay_days` | `None` (not set in MVP) | Post-MVP: conviction decay window |

### 8.2 Risk Notes Generation

Risk notes are auto-generated based on mapping conditions:

- `"Flagged for human review by GlobalBasePolicy"` — if `requires_human_review = True`
- `"Low conviction — consider tighter risk controls"` — if conviction < 0.4
- `"New position opened — monitor closely for first 72h"` — if action is `open_position` or `add_position`
- `"Position exit — verify against current holdings in F5"` — if action is `close_position`
- `"Ambiguity: {flag}"` — for each ambiguity flag

### 8.3 What Risk Constraints Are NOT

Risk constraints are bounds (ceilings), not targets. `max_position_hint = "medium"` means "do not exceed medium" — F5 may still choose `small` or `none`. F4 does not set stop-loss prices, take-profit targets, or position percentages.

---

## 9. Confidence Computation

### 9.1 Formula

```
mapping_confidence = F3.confidence
if action_hint == "review_required": mapping_confidence = min(mapping_confidence, 0.6)
if ambiguity_flags: mapping_confidence -= min(0.15, 0.05 * len(ambiguity_flags))
mapping_confidence = max(0.2, mapping_confidence)
```

### 9.2 Rationale

- `review_required` caps confidence because the policy layer could not make a clear decision.
- Ambiguity flags reduce confidence proportionally (each flag costs 0.05, capped at 0.15).
- Floor of 0.2 prevents zero-confidence records that would be meaningless.

---

## 10. Forbidden Responsibilities

F4 MVP MUST NOT:

1. **Call any LLM** — all mapping is deterministic rule-based
2. **Read raw text** — F4 operates on structured NormalizedInvestmentIntent only
3. **Generate TradeAction** — that is F5's responsibility
4. **Determine execution prices** — F4 provides hints, not execution facts
5. **Modify intent direction** — F4 preserves the original direction unchanged
6. **Use multi-layer policy stack** — only GlobalBase in MVP (StyleArchetype, RiskPreference, KOLPersona, ContentCorrection are post-MVP)
7. **Apply `large` position sizing** — GlobalBase ceiling is `medium`
8. **Execute the pipeline** — F4 is a pure function, no side effects

---

## 11. Failure Cases

| # | Condition | Handling |
|---|---|---|
| F4-1 | Input list is empty | Return empty PolicyMappingBatch (not an error — upstream F3 may have filtered all intents) |
| F4-2 | Intent has actionability not in ("explicit_action", "watch") | Should not happen (F3 gate), but if it does: map as `review_required` and log warning |
| F4-3 | Zero PolicyMappedIntents with executable action_hint | Log warning. Not a hard error — F5 will produce zero TradeActions, which is caught by the MVP failure condition F4 in the main contract |
| F4-4 | Intent has no target_symbol | F4 does not validate target_symbol (that is F2's responsibility). Map normally; F5 will handle missing symbol |
| F4-5 | PolicyContext is missing or incomplete | Use defaults: style_archetype="mixed", risk_preference="balanced". MVP does not use these fields anyway |

---

## 12. Open Questions

| # | Question | Impact | Resolution |
|---|---|---|---|
| O1 | Should `actionability = "watch"` intents enter F4? | Trade volume | **Resolved**: Yes, they enter F4 but produce `action_hint = "watch_only"` which is excluded at the executable gate. This provides audit trail without generating trades. |
| O2 | Should holding period be conviction-adjusted? | Trade duration | **Default**: No. Holding period follows action semantics, not conviction. A high-conviction exit is still `short_term`. Revisit post-MVP if backtest shows systematic over-holding. |
| O3 | Should MVP support `actionability = "review_required"` from F3? | Error handling | **Default**: Pass through as `action_hint = "review_required"`. Logged and excluded at the executable gate. |
| O4 | Does `hold_position` require an existing position? | Portfolio state | **MVP assumption**: No. `hold_position` means "the KOL is holding / recommends holding." F5 resolves whether this maps to an actual trade or a no-op based on current portfolio state. |

---

## Appendix: Existing Implementation Reference

The following files already implement the F4 contract and can be used as reference:

| File | Purpose |
|---|---|
| `src/finer/schemas/policy.py` | All F4 Pydantic models (PolicyMappingResult, PolicyMappedIntent, PolicyContext, PolicyRiskConstraints, PolicyLayerTrace, PolicyDecision) |
| `src/finer/policy/policy_mapper.py` | PolicyMapper — canonical entry point for F3→F4 mapping |
| `src/finer/policy/global_base.py` | GlobalBasePolicy — the deterministic rule table (action rules, conviction bands, holding period map, risk constraints) |

The MVP F4 contract is fully implemented by `GlobalBasePolicy` + `PolicyMapper`. No new code is required for the contract itself — only integration wiring into the MVP pipeline.
