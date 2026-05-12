# KOL Backtest MVP — F2: Anchor Contract

> This section will be merged into `kol-backtest-mvp-stage-contracts.md` after team review.

---

## F2: Anchor — MVP Contract

**Stage:** F2
**MVP responsibility:** Resolve entities to tradeable symbols, anchor time references to ISO 8601 datetimes, and create traceable evidence spans — so that F3 can produce intents with `target_symbol` and F5 can produce TradeActions with `execution_timing`.

### Position in the Pipeline

```
F1 (ContentEnvelope + ContentBlock[])
  + F1.5 (TopicBlock[] with primary_entity_ids as free text)
    |
    v
F2 Anchor
  |  Reads: ContentEnvelope, ContentBlock[], TopicBlock[]
  |  Produces: EvidenceSpan[], EntityAnchor[], TemporalAnchor[]
  |  Writes onto: ContentEnvelope.entity_anchors, ContentEnvelope.temporal_anchors
  |               ContentBlock[].evidence_spans
    |
    v
F3 (needs EntityAnchor[].resolved_symbol + EvidenceSpan[])
F5 (needs TemporalAnchor[] + EvidenceSpan[])
```

### Design Decision: F2 Is a Contract, Not a Monolithic Module

MVP F2 does NOT need a single `F2AnchorExtractor` class. Instead, F2 defines the **output contract** that three focused operations must satisfy:

| Operation | What it does | Schema produced | When it runs |
|-----------|-------------|-----------------|-------------|
| **Entity Resolution** | Takes F1.5 `primary_entity_ids` (free text) + scans blocks for entity mentions → resolves to `EntityAnchor` with `resolved_symbol` | `EntityAnchor[]` | After F1.5, before F3 |
| **Temporal Resolution** | Extracts time references from text + uses F1 `published_at` → resolves to `TemporalAnchor` with `resolved_time` | `TemporalAnchor[]` | After F1.5, before F5 |
| **Evidence Span Creation** | Records the exact character offsets of entity/temporal mentions in source blocks for traceability | `EvidenceSpan[]` | During entity/temporal resolution |

These can be three functions, one class, or three separate modules — the contract only specifies the output.

---

### Input Contract

| Schema | Source | Notes |
|--------|--------|-------|
| `ContentEnvelope` | F1 output | Provides `published_at`, `blocks[]`, `creator_id` |
| `ContentBlock[]` | F1 output | Provides `block_id`, `text`, `order_index`, `speaker`, `timestamp`, `quality` |
| `TopicBlock[]` | F1.5 output | Provides `primary_entity_ids` (free text), `source_block_ids`, `topic_type`, `raw_text` |
| KOL Profile | Config | Provides `default_market` for disambiguation (e.g., "CN", "US", "HK") |

### Output Contract

| Schema | Required? | Written to | Downstream consumer |
|--------|-----------|-----------|---------------------|
| `EntityAnchor[]` | Yes | `ContentEnvelope.entity_anchors` | F3 (`target_symbol`, `market`) |
| `TemporalAnchor[]` | Yes | `ContentEnvelope.temporal_anchors` | F5 (`ExecutionTiming.intent_effective_at`) |
| `EvidenceSpan[]` | Yes | `ContentBlock[].evidence_spans` | F3 (`evidence_span_ids`), F5 (`TradeAction.evidence_span_ids`) |

---

### EntityAnchor — MVP Fields

| Field | Type | Required | MVP Notes |
|-------|------|----------|-----------|
| `entity_anchor_id` | `str` (UUID) | Yes | Unique identifier |
| `entity_type` | `enum` | Yes | MVP values: `stock`, `etf`, `index`, `crypto`, `sector`, `company`. Others (`person`, `bond`, `fund`, etc.) are post-MVP |
| `raw_text` | `str` | Yes | Original mention text (e.g., "苹果公司", "TSLA", "新能源") |
| `resolved_symbol` | `str` | **Yes** | **MVP hard constraint**: every EntityAnchor MUST have this set. E.g., "AAPL", "TSLA", "300750.SZ" |
| `resolved_name` | `str` | Yes | Canonical name (e.g., "Apple Inc.", "Tesla, Inc.") |
| `market` | `str` | **Yes** | **MVP hard constraint**: every EntityAnchor MUST have this set. Values: "US", "HK", "CN", "CRYPTO" |
| `confidence` | `float` (0-1) | Yes | Must be >= 0.5 (MVP threshold). Below 0.5 → entity is dropped |
| `evidence_span_id` | `str` | Yes | FK to the EvidenceSpan that captured this mention |
| `aliases` | `List[str]` | No | Alternative names (e.g., `["Apple", "苹果", "AAPL"]`) |

**MVP entity_type values:**

| `entity_type` | When to use | Example |
|---------------|-------------|---------|
| `stock` | Individual equity | AAPL, 300750.SZ, 0700.HK |
| `etf` | Exchange-traded fund | SPY, QQQ, 510300.SS |
| `index` | Market index | S&P 500, CSI 300, HSI |
| `crypto` | Cryptocurrency | BTC, ETH |
| `sector` | Industry/sector theme | "semiconductor", "new energy" — resolved_symbol is a canonical sector ID |
| `company` | Company mentioned without clear ticker | Only when no ticker can be resolved; `resolved_symbol` uses a best-guess or the company name as ID |

**Resolution rules:**

1. If the entity text is already a ticker symbol (e.g., "AAPL", "TSLA"), validate it exists. If valid, use it directly as `resolved_symbol`.
2. If the entity text is a company/entity name (e.g., "苹果公司", "Tesla"), resolve via lookup table or LLM. Map to ticker + market.
3. If ambiguous (e.g., "Apple" could be the fruit), use `default_market` from KOL Profile to disambiguate. If still ambiguous, set `confidence < 0.7` and flag.
4. Sector entities: resolve to a canonical sector ID (e.g., "semiconductor" → `"SECTOR:SEMICONDUCTOR"`). `entity_type = "sector"`.
5. Entities that cannot be resolved to a symbol after all strategies are **dropped** (not included in output). The pipeline fails if zero EntityAnchors remain.

**How F1.5 `primary_entity_ids` feeds F2:**

F1.5's `primary_entity_ids` are free-text strings (e.g., `["TSLA", "苹果", "新能源板块"]`). F2 treats these as **hints** — they get priority for resolution, but F2 also scans the topic's `raw_text` (or source blocks' `text`) for additional entity mentions that F1.5 may have missed. The final `EntityAnchor[]` is the union of resolved entities from both sources, deduplicated by `resolved_symbol`.

---

### TemporalAnchor — MVP Fields

| Field | Type | Required | MVP Notes |
|-------|------|----------|-----------|
| `anchor_id` | `str` (UUID) | Yes | Unique identifier |
| `anchor_type` | `enum` | Yes | MVP values: `published_at`, `mentioned_at`, `effective_trade_at` |
| `raw_text` | `str` | Yes | Original text containing the time reference |
| `resolved_time` | `datetime` | **Yes** | **MVP hard constraint**: every TemporalAnchor MUST have this set (ISO 8601) |
| `confidence` | `float` (0-1) | Yes | Must be >= 0.5 (MVP threshold) |
| `resolution_strategy` | `enum` | Yes | How the time was resolved (see table below) |
| `timezone` | `str` | Yes | IANA timezone (e.g., "Asia/Shanghai", "America/New_York") |
| `evidence_span_id` | `str` | No | FK to EvidenceSpan if the anchor was extracted from text |

**MVP anchor_type values:**

| `anchor_type` | When to use | Source | Example |
|---------------|-------------|--------|---------|
| `published_at` | When the content was published | F1 `ContentEnvelope.published_at` | "2024-01-15T09:30:00+08:00" |
| `mentioned_at` | An explicit or relative time reference in the text | Extracted from block text | "下周一" → 2024-01-22, "明天开盘" → 2024-01-16T09:30:00 |
| `effective_trade_at` | When the KOL intends the trade to take effect | Derived from `mentioned_at` or defaulted to `published_at` | "明天开盘买入" → effective_trade_at = next trading day open |

**Resolution rules:**

1. **`published_at`**: Always created. Source is `ContentEnvelope.published_at`. `resolution_strategy = "explicit_date"`. `confidence = 1.0`. One per envelope.
2. **`mentioned_at`**: Created only when the text contains explicit time references (dates, relative times like "明天", "下周一", "after earnings"). If no time references found, this anchor type is omitted. `resolution_strategy` depends on the reference type.
3. **`effective_trade_at`**: Created when there is a clear action-oriented time signal (e.g., "明天开盘买入", "earnings后加仓"). If no explicit timing, defaults to `published_at` with `confidence -= 0.2`. If `mentioned_at` exists, derived from it.

**Resolution strategy values:**

| `resolution_strategy` | When used |
|----------------------|-----------|
| `explicit_date` | Text contains an absolute date (e.g., "2024年1月15日") |
| `relative_date` | Text contains a relative reference (e.g., "明天", "下周一", "三天后") |
| `fiscal_period` | Text references a fiscal period (e.g., "Q1财报后", "年报发布后") |
| `market_hours` | Text references market session (e.g., "开盘", "收盘后", "pre-market") |
| `llm_inference` | Ambiguous time reference resolved by LLM |
| `rule_based` | Default/fallback derived from `published_at` |

**How temporal anchors connect to F5 ExecutionTiming:**

F5's `ExecutionTiming` consumes temporal anchors as follows:

| ExecutionTiming field | Source |
|----------------------|--------|
| `intent_published_at` | F1 `ContentEnvelope.published_at` (not a TemporalAnchor, but same value) |
| `intent_effective_at` | F2 `TemporalAnchor(anchor_type="effective_trade_at").resolved_time` — null if no effective_trade_at anchor |
| `action_decision_at` | System processing timestamp (set by F5) |
| `action_executable_at` | Computed by F5 from market calendar + `intent_effective_at` or `intent_published_at` |

---

### EvidenceSpan — MVP Fields

| Field | Type | Required | MVP Notes |
|-------|------|----------|-----------|
| `evidence_span_id` | `str` (UUID) | Yes | Unique identifier |
| `block_id` | `str` | Yes | FK to the ContentBlock containing this span |
| `char_start` | `int` (>= 0) | Yes | Start character offset in `ContentBlock.text` |
| `char_end` | `int` (> char_start) | Yes | End character offset in `ContentBlock.text` |
| `text` | `str` | Yes | Extracted substring (must equal `block_text[char_start:char_end]`) |
| `confidence` | `float` (0-1) | Yes | Confidence that this span is relevant evidence |
| `span_type` | `str` | Yes | `"entity"` or `"temporal"` for MVP |

**What needs evidence spans:**

- Every `EntityAnchor` MUST reference one `EvidenceSpan` via `evidence_span_id`
- Every `TemporalAnchor` that was extracted from text (not defaulted from `published_at`) SHOULD reference one `EvidenceSpan`
- F3 and F5 use `evidence_span_ids` to trace their outputs back to source text

**What does NOT need evidence spans for MVP:**

- Not every `ContentBlock` needs spans — only blocks that contribute entity or temporal mentions
- F3 may create additional spans during intent extraction (this is F3's responsibility, not F2's)

**Span creation rules:**

1. When an entity mention is found in a block's text, create an `EvidenceSpan` with `span_type = "entity"` covering the mention's character range.
2. When a temporal reference is found, create an `EvidenceSpan` with `span_type = "temporal"` covering the reference's character range.
3. The span's `text` MUST be an exact substring of the block's `text` at the specified offsets.
4. Overlapping spans are allowed (e.g., "明天开盘买入" could have a temporal span for "明天开盘" and an entity span if "AAPL" is nearby).
5. Span IDs are globally unique (UUID-based).

---

### Required Fields Summary

**F2 output MUST satisfy ALL of the following:**

| Constraint | Validation |
|-----------|-----------|
| At least 1 `EntityAnchor` with `resolved_symbol` across all envelopes | Pipeline fails with `NO_RESOLVED_ENTITIES` if zero |
| Every `EntityAnchor.resolved_symbol` is non-null | Anchor is dropped (not included) if symbol cannot be resolved |
| Every `EntityAnchor.market` is non-null | Anchor is dropped if market cannot be determined |
| Every `EntityAnchor.confidence >= 0.5` | Anchors below threshold are dropped |
| Every `TemporalAnchor.resolved_time` is non-null (ISO 8601) | Anchor is dropped if time cannot be resolved |
| Every `TemporalAnchor.confidence >= 0.5` | Anchors below threshold are dropped |
| At least 1 `TemporalAnchor` with `anchor_type = "published_at"` per envelope | Always created from `ContentEnvelope.published_at` |
| At least 1 `EvidenceSpan` per `EntityAnchor` | Each entity anchor references exactly one evidence span |
| Every `EvidenceSpan.text` == `ContentBlock.text[char_start:char_end]` | Validation check at output |
| `ContentEnvelope.entity_anchors` and `temporal_anchors` are populated | F2 writes its outputs onto the envelope |

---

### Forbidden Responsibilities

F2 MUST NOT:

- **Extract investment intents** — that is F3's job. F2 identifies *what entities exist* and *when things happened*, not *what the KOL wants to do*.
- **Classify sentiment or direction** — F2 does not determine if the KOL is bullish or bearish.
- **Generate TradeActions** — that is F5's job.
- **Modify ContentBlock text** — F2 reads text, never alters it.
- **Perform topic assembly** — that is F1.5's job. F2 operates on F1.5's output.
- **Assess content quality** — that is F1's job (BlockQuality). F2 may use quality scores as input but does not modify them.
- **Create new ContentBlocks** — F2 only annotates existing blocks with evidence spans.
- **Handle cross-envelope entity linking** — post-MVP. Each envelope is anchored independently.
- **Resolve ambiguous entities without dropping them** — if confidence < 0.5 after all resolution strategies, the entity is excluded. F2 does not keep low-confidence anchors for downstream to "figure out".

---

### Failure Cases

| Failure | Handling |
|---------|----------|
| Zero entities found in any block or topic | Fail with `NO_ENTITIES_FOUND` error. Pipeline cannot produce TradeActions without tradeable targets. |
| Entity found but cannot be resolved to any symbol | Drop the entity. If ALL entities are dropped, fail with `NO_RESOLVED_ENTITIES`. |
| Entity resolves to symbol not in market data | Log warning. F8 will fail later if price data is missing — F2 does not pre-check market data. |
| `published_at` is null on ContentEnvelope | Fail with `MISSING_PUBLISHED_AT`. This was required by F1 contract; if missing, F1 failed. |
| Relative time reference cannot be resolved (e.g., "soon", "eventually") | Do not create a `mentioned_at` anchor. If `effective_trade_at` is needed, fall back to `published_at` with reduced confidence. |
| LLM timeout during entity/temporal resolution | Fall back to rule-based resolution (keyword matching, regex dates). Set `resolution_strategy = "rule_based"`. |
| Multiple entities with same resolved symbol in one envelope | Deduplicate: keep the one with highest confidence. Merge evidence spans if they overlap. |
| Text contains dates in conflicting formats | Use the most specific resolution. If ambiguous (e.g., "01/02/2024" could be Jan 2 or Feb 1), use `default_market` timezone convention. If still ambiguous, set `confidence < 0.7`. |

---

### Open Questions

| # | Question | Impact | Default if Unresolved |
|---|----------|--------|----------------------|
| O1 | Should F2 entity resolution use a lookup table, LLM, or both? Lookup tables are deterministic but limited; LLMs are flexible but non-deterministic. | Resolution accuracy and determinism | Hybrid: lookup table for known tickers (loaded from entity_registry), LLM for ambiguous or unknown entities. Lookup table takes priority. |
| O2 | How should sector entities be represented? A sector like "semiconductor" is not a tradeable symbol — but F3 may produce sector-level intents. | Downstream intent extraction | `entity_type = "sector"`, `resolved_symbol = "SECTOR:SEMICONDUCTOR"` (namespaced). F3/F4 decide whether to produce a tradeable signal. |
| O3 | Should F2 create `mentioned_at` anchors for vague time references ("soon", "in the coming weeks") or only for resolvable ones? | Anchor count and quality | Only for references that resolve to a specific date with confidence >= 0.5. Vague references are logged but do not produce anchors. |
| O4 | For `effective_trade_at`, when the text says "明天买入" (buy tomorrow), should the resolved time be market-open (09:30) or midnight (00:00)? | Backtest entry price | Market-open time for the target market (e.g., 09:30 CST for CN, 09:30 EST for US). F5 computes `action_executable_at` from this. |
| O5 | Should F2 validate that `resolved_symbol` corresponds to a real, currently-traded instrument? Or is format validation sufficient? | Data quality vs speed | Format validation only for MVP (e.g., matches pattern `[A-Z]{1,5}` or `\d{6}\.\w{2}`). Existence validation is deferred to F5/F8 when market data is joined. |
| O6 | How should F2 handle entities that are companies but not publicly traded (e.g., "ByteDance" before IPO)? | Entity coverage | Include as `entity_type = "company"` with `resolved_symbol = "COMPANY:BYTEDANCE"` (namespaced). Mark with `confidence -= 0.2`. F3/F4 may or may not produce intents for non-tradeable entities. |
