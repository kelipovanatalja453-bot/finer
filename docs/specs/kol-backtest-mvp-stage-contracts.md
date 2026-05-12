# KOL Backtest MVP — Stage Contracts (Consolidated)

> Version: 1.0.0 | Created: 2026-05-11
> Status: **Design** — pending team review
> Source: Individual stage contract sections merged into this consolidated document.

This document contains the per-stage contracts for the KOL Backtest MVP pipeline (F1 -> F1.5 -> F2 -> F3 -> F4 -> F5 -> F8). Each stage section defines its input, output, required fields, forbidden responsibilities, failure cases, and open questions.

---

## F1: Standardize — MVP Contract

Stage: F1
MVP responsibility: Convert each frozen ContentRecord into a ContentEnvelope with ContentBlocks, populating quality cards and provenance metadata.

### Input Contract

| Schema | Source | Notes |
|--------|--------|-------|
| `ContentRecord` | F0 (frozen, read-only from disk) | Provides `content_id`, `source_type`, `raw_path`, `published_at`, `creator_id` |
| Raw file | F0 (frozen on disk) | The original content file (markdown, HTML, etc.) |

### Output Contract

| Schema | Required? | Downstream consumer |
|--------|-----------|---------------------|
| `ContentEnvelope` | Yes | F1.5, F2 |
| `ContentBlock[]` | Yes | F1.5, F2 |
| `BlockQuality` (per block) | Yes | F2 (may use as input) |
| `BlockProvenance` (per block) | Yes | Audit trail |

### Required Fields

| Field | Source | Required | MVP Rule |
|-------|--------|----------|----------|
| `envelope_id` | Generated | Yes | Deterministic from content_id: `env_{content_id}` |
| `schema_version` | Config | Yes | `"1.0"` |
| `source_content_id` | `ContentRecord.content_id` | Yes | Direct copy |
| `published_at` | `ContentRecord.published_at` | Yes | ISO 8601 with timezone |
| `blocks[].block_id` | Generated | Yes | Non-empty string |
| `blocks[].text` | Extracted from raw file | Yes | Non-empty |
| `blocks[].block_type` | Determined by adapter | Yes | `"text"` for MVP markdown content |
| `blocks[].quality.readability` | Computed | Yes | Within [0,1] |
| `blocks[].quality.extraction_confidence` | Computed | Yes | Within [0,1] |
| `blocks[].quality.structural_confidence` | Computed | Yes | Within [0,1] |
| `blocks[].quality.completeness` | Computed | Yes | Within [0,1] |

### Forbidden Responsibilities

F1 MUST NOT:
- Extract investment intents (F3)
- Resolve entities or time references (F2)
- Assemble topics (F1.5)
- Generate TradeActions (F5)
- Modify raw files on disk

### Failure Cases

| Failure | Handling |
|---------|----------|
| ContentRecord has no raw file at `raw_path` | Fail with `MISSING_RAW_FILE` error |
| Raw file is empty or unreadable | Fail with `EMPTY_RAW_FILE` error |
| `published_at` is null or invalid format | Fail with `INVALID_PUBLISHED_AT` error |
| Zero ContentBlocks extracted | Fail with `NO_BLOCKS_EXTRACTED` error |

### Open Questions

| # | Question | Default if Unresolved |
|---|----------|----------------------|
| O1 | How should F1 handle content types not yet production-ready (e.g., audio, video)? | Fail the run with a clear error if unsupported source_type is encountered. No silent skip. |

---

## F1.5: Topic Assembly — MVP Contract

Stage: F1.5
MVP responsibility: Assemble ContentBlocks into TopicBlocks. F1.5 ALWAYS outputs TopicBlock[]. For single-topic content, a single TopicBlock wrapping all blocks is created (no reorganization). F3 ONLY receives TopicBlock[], never raw ContentBlock[].

### Input Contract

| Schema | Source | Notes |
|--------|--------|-------|
| `ContentBlock[]` | F1 output | Provides `block_id`, `text`, `order_index`, `speaker`, `timestamp` |
| `ContentEnvelope` | F1 output | Provides `envelope_id`, `source_content_id` |

### Output Contract

| Schema | Required? | Downstream consumer |
|--------|-----------|---------------------|
| `TopicBlock[]` | Yes | F2, F3 |
| `TopicAssemblyResult` | Yes | Container with metadata |

### Activation Rule

F1.5 ALWAYS produces TopicBlock[] — it is a mandatory sub-stage. For single-topic content (1-2 blocks or uniform topic), a single TopicBlock wrapping all blocks is created. For multi-topic content (>= 3 blocks with mixed topic signals), blocks are reorganized into multiple TopicBlocks. The key invariant: F3 ONLY receives TopicBlock[], never raw ContentBlock[].

### Required Fields per TopicBlock

| Field | Type | Required | MVP Rule |
|-------|------|----------|----------|
| `topic_block_id` | `str` | Yes | Deterministic: `tb_{content_id}_{idx}` |
| `topic_type` | `enum` | Yes | `"single_stock"`, `"multi_stock"`, `"market_commentary"`, `"other"` |
| `source_block_ids` | `List[str]` | Yes | Non-empty, each references a valid F1 block_id |
| `primary_entity_ids` | `List[str]` | Yes | Free-text entity hints (e.g., `["TSLA", "NVDA"]`) |
| `raw_text` | `str` | Yes | Concatenated text from source blocks |
| `confidence` | `float` | Yes | 0.0-1.0 |

### Forbidden Responsibilities

F1.5 MUST NOT:
- Parse F1 raw format details (markdown headings, HTML wrappers, OCR bboxes, ASR timestamps)
- Resolve entities to symbols (F2)
- Extract investment intents (F3)
- Modify ContentBlock text

### Failure Cases

| Failure | Handling |
|---------|----------|
| Zero TopicBlocks produced | Fail with `NO_TOPIC_BLOCKS` error |
| TopicBlock references non-existent block_id | Fail with `INVALID_BLOCK_REFERENCE` error |

### Open Questions

| # | Question | Default if Unresolved |
|---|----------|----------------------|
| O1 | Should F1.5 be mandatory or optional for MVP? | **Resolved**: Mandatory. F1.5 ALWAYS outputs TopicBlock[]. Single-topic content gets one wrapping TopicBlock; multi-topic content gets reorganized TopicBlocks. F3 only consumes TopicBlock[]. |

---

## F2: Anchor — MVP Contract

Stage: F2
MVP responsibility: Resolve entities to tradeable symbols, anchor time references to ISO 8601 datetimes, and create traceable evidence spans — so that F3 can produce intents with `target_symbol` and F5 can produce TradeActions with `execution_timing`.

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
| **Entity Resolution** | Takes F1.5 `primary_entity_ids` (free text) + scans blocks for entity mentions -> resolves to `EntityAnchor` with `resolved_symbol` | `EntityAnchor[]` | After F1.5, before F3 |
| **Temporal Resolution** | Extracts time references from text + uses F1 `published_at` -> resolves to `TemporalAnchor` with `resolved_time` | `TemporalAnchor[]` | After F1.5, before F5 |
| **Evidence Span Creation** | Records the exact character offsets of entity/temporal mentions in source blocks for traceability | `EvidenceSpan[]` | During entity/temporal resolution |

These can be three functions, one class, or three separate modules — the contract only specifies the output.

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

### EntityAnchor — MVP Fields

| Field | Type | Required | MVP Notes |
|-------|------|----------|-----------|
| `entity_anchor_id` | `str` (UUID) | Yes | Unique identifier |
| `entity_type` | `enum` | Yes | MVP values: `stock`, `etf`, `index`, `crypto`, `sector`, `company`. Others (`person`, `bond`, `fund`, etc.) are post-MVP |
| `raw_text` | `str` | Yes | Original mention text (e.g., "苹果公司", "TSLA", "新能源") |
| `resolved_symbol` | `str` | **Yes** | **MVP hard constraint**: every EntityAnchor MUST have this set. E.g., "AAPL", "TSLA", "300750.SZ" |
| `resolved_name` | `str` | Yes | Canonical name (e.g., "Apple Inc.", "Tesla, Inc.") |
| `market` | `str` | **Yes** | **MVP hard constraint**: every EntityAnchor MUST have this set. Values: "US", "HK", "CN", "CRYPTO" |
| `confidence` | `float` (0-1) | Yes | Must be >= 0.5 (MVP threshold). Below 0.5 -> entity is dropped |
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
4. Sector entities: resolve to a canonical sector ID (e.g., "semiconductor" -> `"SECTOR:SEMICONDUCTOR"`). `entity_type = "sector"`.
5. Entities that cannot be resolved to a symbol after all strategies are **dropped** (not included in output). The pipeline fails if zero EntityAnchors remain.

**How F1.5 `primary_entity_ids` feeds F2:**

F1.5's `primary_entity_ids` are free-text strings (e.g., `["TSLA", "苹果", "新能源板块"]`). F2 treats these as **hints** — they get priority for resolution, but F2 also scans the topic's `raw_text` (or source blocks' `text`) for additional entity mentions that F1.5 may have missed. The final `EntityAnchor[]` is the union of resolved entities from both sources, deduplicated by `resolved_symbol`.

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
| `mentioned_at` | An explicit or relative time reference in the text | Extracted from block text | "下周一" -> 2024-01-22, "明天开盘" -> 2024-01-16T09:30:00 |
| `effective_trade_at` | When the KOL intends the trade to take effect | Derived from `mentioned_at` or defaulted to `published_at` | "明天开盘买入" -> effective_trade_at = next trading day open |

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

### Open Questions

| # | Question | Default if Unresolved |
|---|----------|----------------------|
| O1 | Should F2 entity resolution use a lookup table, LLM, or both? | Hybrid: lookup table for known tickers (loaded from entity_registry), LLM for ambiguous or unknown entities. Lookup table takes priority. |
| O2 | How should sector entities be represented? | `entity_type = "sector"`, `resolved_symbol = "SECTOR:SEMICONDUCTOR"` (namespaced). F3/F4 decide whether to produce a tradeable signal. |
| O3 | Should F2 create `mentioned_at` anchors for vague time references? | Only for references that resolve to a specific date with confidence >= 0.5. Vague references are logged but do not produce anchors. |
| O4 | For `effective_trade_at`, when the text says "明天买入", should the resolved time be market-open or midnight? | Market-open time for the target market. F5 computes `action_executable_at` from this. |
| O5 | Should F2 validate that `resolved_symbol` corresponds to a real, currently-traded instrument? | Format validation only for MVP. Existence validation is deferred to F5/F8 when market data is joined. |
| O6 | How should F2 handle entities that are companies but not publicly traded? | Include as `entity_type = "company"` with `resolved_symbol = "COMPANY:BYTEDANCE"` (namespaced). Mark with `confidence -= 0.2`. |

---

## F3: Intent — MVP Contract

Stage: F3 (Intent Extraction)
MVP responsibility: Extract normalized investment intents from TopicBlocks, resolving each intent to a target entity with direction, actionability, and evidence traceability — without generating TradeActions or position sizing decisions.

### Input Contract

F3 receives the following from upstream stages:

| Source | Schema | Key fields consumed by F3 |
|--------|--------|---------------------------|
| F1.5 | `TopicBlock[]` | `topic_block_id`, `source_block_ids[]`, `topic_type`, `primary_entity_ids[]`, `raw_text`, `confidence` |
| F2 | `EvidenceSpan[]` | `evidence_span_id`, `block_id`, `char_start`, `char_end`, `text`, `confidence` |
| F2 | `EntityAnchor[]` | `entity_anchor_id`, `entity_type`, `raw_text`, `resolved_symbol`, `market`, `confidence`, `evidence_span_id` |
| F2 | `TemporalAnchor[]` | `anchor_id`, `anchor_type`, `raw_text`, `resolved_time`, `confidence`, `timezone` |

F3 ONLY receives `TopicBlock[]` from F1.5 — it does NOT receive raw `ContentBlock[]` directly. F1.5 is a mandatory sub-stage that always produces TopicBlock[]. For single-topic content, F1.5 wraps all blocks into one TopicBlock; F3 operates on this wrapper unchanged. For multi-topic content, F1.5 reorganizes blocks into multiple TopicBlocks.

### Output Contract

F3 produces `NormalizedInvestmentIntent[]`. Each intent is a semantic abstraction — it captures *what the KOL means*, not *what to do about it*. F4 translates intents into policy-guided action hints; F5 generates executable TradeActions.

**Container:** `IntentExtractionResult`

| Field | Type | Description |
|-------|------|-------------|
| `intents` | `List[NormalizedInvestmentIntent]` | Extracted intents |
| `envelope_id` | `str` | Parent content envelope ID |
| `extraction_timestamp` | `datetime` | When extraction ran |
| `model_version` | `str` | Model version for reproducibility |
| `total_intents` | `int` | Auto-computed count |
| `actionable_count` | `int` | Intents passing actionability filter |

### Required Fields per Intent

Every `NormalizedInvestmentIntent` produced by F3 MVP MUST have these fields populated:

| Field | Type | Required | MVP Rule |
|-------|------|----------|----------|
| `intent_id` | `str` | YES | UUID, auto-generated |
| `envelope_id` | `str` | YES | Must match input envelope |
| `block_ids` | `List[str]` | YES | At least one source block ID from TopicBlock |
| `target_type` | `Literal` | YES | One of: `stock`, `sector`, `index`, `macro`, `commodity`, `crypto`, `unknown` |
| `target_name` | `str` | YES | Human-readable name (e.g., "宁德时代") |
| `target_symbol` | `str` | YES (MVP) | MUST be populated for MVP. Copied from EntityAnchor.resolved_symbol. If unresolvable, set actionability=`review_required` |
| `market` | `str` | YES | Market identifier from EntityAnchor (CN, US, HK, CRYPTO) |
| `direction` | `Literal` | YES | `bullish`, `bearish`, `neutral`, `mixed`, `unknown` |
| `actionability` | `Literal` | YES | `opinion`, `watch`, `explicit_action`, `review_required` |
| `position_delta_hint` | `Literal` | YES | `open`, `add`, `reduce`, `hold`, `exit`, `none`, `unknown` |
| `conviction` | `float` | YES | 0.0-1.0, semantic strength of the KOL's belief |
| `confidence` | `float` | YES | 0.0-1.0, model extraction confidence |
| `evidence_span_ids` | `List[str]` | YES | At least one evidence span ID |

Optional fields that F3 MAY populate: `creator_id`, `sentiment_score`, `risk_preference_hint`, `time_horizon_hint`, `temporal_anchor_ids`, `ambiguity_flags`, `metadata`.

### Forbidden Responsibilities

F3 MUST NOT:

1. **Generate TradeAction** — F5 produces TradeActions, not F3
2. **Decide position sizing** — position_delta_hint is a semantic *hint*, not a sizing instruction
3. **Make backtest assumptions** — F3 does not assume execution price, timing, or slippage
4. **Resolve symbols from scratch** — symbol resolution is F2's job; F3 consumes EntityAnchor.resolved_symbol
5. **Deduplicate intents across TopicBlocks** — deduplication is an optional post-F3 concern, not F3's job
6. **Apply KOL-specific policy** — policy mapping is F4's job
7. **Parse markdown headings, HTML wrappers, OCR bboxes, or ASR timestamps** — that's F1's job
8. **Output legacy SegmentRecord** — canonical output is NormalizedInvestmentIntent only

### Failure Cases

| Case | Behavior |
|------|----------|
| TopicBlock has no EntityAnchors | Produce zero intents; log warning. F3 cannot create an intent without a target entity. |
| EntityAnchor has no resolved_symbol | Set `actionability=review_required`, `ambiguity_flags=["unresolved_symbol"]`. Intent passes through but F4 will escalate. |
| Text is pure opinion with no actionable signal | Produce intent with `actionability=opinion`, `position_delta_hint=none`. F4 maps it to a non-executable action hint (e.g., `watch_only` or `watch_or_no_trade`). Excluded at F4 executable gate; does NOT enter F5. |
| Contradictory signals in one TopicBlock | Produce a single intent with `direction=mixed`, `ambiguity_flags=["contradictory_signals"]`. Do NOT split into two opposing intents. |
| Confidence below threshold (< 0.5) | Still produce the intent but with `actionability=review_required`. F4 will not map it to an actionable policy. |
| Multiple entities in one TopicBlock | Produce one intent per entity. Each intent references the evidence spans relevant to that entity. |
| TemporalAnchor has no resolved_time | Intent still produced; `temporal_anchor_ids` references the anchor, but `time_horizon_hint` defaults to `unknown`. |

### Intent Direction Taxonomy

**Valid directions for MVP:**

| Direction | Meaning | When to use |
|-----------|---------|-------------|
| `bullish` | KOL expresses positive outlook or recommends buying/holding | "我看好宁德时代", "继续加仓" |
| `bearish` | KOL expresses negative outlook or recommends selling/avoiding | "新能源要跌", "减仓腾讯" |
| `neutral` | KOL acknowledges the entity without clear directional bias | "腾讯目前估值合理" |
| `mixed` | KOL expresses both positive and negative signals in the same TopicBlock | "短期看空但长期看好" |
| `unknown` | Direction cannot be determined from the text | Ambiguous or insufficient context |

**MVP rule:** F3 MUST classify every intent. Default to `unknown` only when text genuinely lacks directional signal — never as a fallback for extraction failure (use `review_required` actionability instead).

### Actionability Rules

F3 decides actionability by analyzing the text semantics of the TopicBlock. The decision is based on what the KOL *says*, not what the model *infers*.

**Classification rules:**

| Actionability | Criteria | Text pattern signals |
|---------------|----------|---------------------|
| `explicit_action` | KOL uses imperative or declarative language about their own trading action | "我加仓了", "买入", "清仓", "已减持", "准备建仓", "今天开盘买" |
| `watch` | KOL expresses interest or signals potential future action without committing | "关注", "观察", "看好", "值得留意", "列入自选", "可以考虑" |
| `opinion` | KOL shares analysis, commentary, or belief without any action implication | "我认为", "估值偏高", "业绩不错", "行业趋势向上" |
| `review_required` | Ambiguous signal, unresolved entity, or confidence too low | Default when target_symbol is missing, confidence < 0.5, or text is contradictory |

**Decision procedure (ordered):**

1. If `target_symbol` is not resolvable from EntityAnchor -> `review_required`
2. If `confidence` < 0.5 -> `review_required`
3. If text contains explicit action verbs (buy/sell/add/reduce/close) referring to the KOL's own position -> `explicit_action`
4. If text contains watchlist/interest signals without commitment -> `watch`
5. Otherwise -> `opinion`

**MVP filter:** ALL intents pass to F4 regardless of actionability. F4 produces a PolicyMappingResult for every intent (audit trail). The filtering happens at F4's executable gate: only PolicyMappedIntents with `action_hint in ("open_position", "add_position", "reduce_position", "close_position", "hold_position")` pass to F5. Intents with `opinion`, `watch`, or `review_required` actionability are mapped to non-executable action hints (`watch_only`, `watch_or_no_trade`, `avoid_or_watch_risk`, `review_required`) and logged as audit records but do NOT enter F5.

### Position Delta Hint Semantics

Position delta hint captures the *semantic category* of the KOL's stated action. It is NOT a trading instruction — it is a classification that helps F4 understand what kind of policy mapping to apply.

| Hint | Meaning | Typical F4 mapping |
|------|---------|-------------------|
| `open` | KOL is establishing a new position | `action_hint=open_position` |
| `add` | KOL is increasing an existing position | `action_hint=add_position` |
| `reduce` | KOL is decreasing an existing position | `action_hint=reduce_position` |
| `hold` | KOL is maintaining current position | `action_hint=hold_position` |
| `exit` | KOL is closing out a position entirely | `action_hint=close_position` |
| `none` | No position change implied (pure opinion/watch) | `action_hint=watch_only` |
| `unknown` | Cannot determine from text | `action_hint=review_required` |

**Mapping rules:**

- `actionability=opinion` -> `position_delta_hint=none` (opinion never implies position change)
- `actionability=explicit_action` -> map from verb semantics: "加仓"->`add`, "清仓"->`exit`, "建仓"->`open`, "持有"->`hold`, "减持"->`reduce`
- `actionability=watch` -> `position_delta_hint=none` (watching is not acting)
- Bearish direction + `open`/`add` -> flag `ambiguity_flags=["bearish_position_mismatch"]` (may indicate short-selling, which is out of MVP scope)

### Evidence Trace Rule

Every intent MUST reference at least one `evidence_span_id`. This is a hard requirement — no intent exists without textual evidence.

**Rules:**

1. `evidence_span_ids` MUST contain at least one ID that maps to a valid EvidenceSpan in the F2 output
2. Each referenced EvidenceSpan's `block_id` MUST be in the intent's `block_ids` list
3. Evidence spans SHOULD cover the text that supports the direction classification (the bullish/bearish statement itself)
4. Evidence spans SHOULD cover the text that supports the actionability classification (the action verb, if present)
5. If an intent is derived from multiple evidence spans (e.g., entity mention in one span, direction in another), ALL supporting spans must be listed

**Auditability:** The evidence chain must be complete enough that a human reviewer can read the referenced EvidenceSpan texts and understand why F3 classified the intent as it did. This is the foundation of the "auditable TradeActions" requirement in the MVP definition.

### Intent Timing Semantics

F3 does NOT resolve timing — that is F2's job via TemporalAnchor. F3's role is to *link* intents to temporal anchors when they exist, and to classify the implied time horizon.

**TemporalAnchor linkage:**

- `temporal_anchor_ids` lists TemporalAnchor IDs that are contextually relevant to the intent
- An intent MAY have zero temporal anchors (many investment statements lack explicit timing)
- An intent MAY reference multiple temporal anchors (e.g., "下周减仓，月底清仓")

**Time horizon classification (`time_horizon_hint`):**

| Horizon | Meaning | Typical signals |
|---------|---------|----------------|
| `intraday` | Within the same trading day | "今天", "开盘", "尾盘" |
| `short_term` | Days to weeks | "这周", "下周", "短期" |
| `medium_term` | Weeks to months | "这个季度", "中期", "半年" |
| `long_term` | Months to years | "长期", "明年", "五年" |
| `unknown` | No temporal signal present | Default when no TemporalAnchor is linked |

**Rule:** `time_horizon_hint` is derived from the linked TemporalAnchors' `raw_text` and `anchor_type`. F3 does NOT perform its own date resolution — it classifies based on the semantic category of the time reference.

### Design Decisions and Rationale

**Q1: How does F3 decide actionability?**
A: By ordered rule evaluation over text semantics, not LLM classification alone. The procedure is: symbol resolvability -> confidence threshold -> action verb detection -> watchlist signal detection -> default to opinion. This makes actionability deterministic and auditable.

**Q2: Does F3 resolve symbols or does F2?**
A: F2 resolves symbols. F3 consumes EntityAnchor.resolved_symbol. If F2 could not resolve, F3 sets actionability=review_required. F3 NEVER performs its own symbol lookup.

**Q3: How many intents can one TopicBlock produce?**
A: One intent per target entity. A TopicBlock discussing 3 stocks produces 3 intents, each with its own evidence spans and direction. The MVP assumption (single KOL, frozen content) means most TopicBlocks will produce 0-2 intents.

**Q4: What confidence/conviction thresholds filter noise?**
A: confidence < 0.5 -> review_required (filtered from F4 pipeline). For conviction, no hard floor — low-conviction intents pass through with their conviction score intact for F4 to weigh.

**Q5: How does F3 handle contradictory signals?**
A: Produce a single intent with direction=mixed and ambiguity_flags=["contradictory_signals"]. Do NOT split into opposing intents — that would create two TradeActions that cancel each other, which is noise. F4 sees the mixed flag and can apply appropriate policy (e.g., watch_only or review_required).

### Open Questions

| # | Question | Default if Unresolved |
|---|----------|----------------------|
| O1 | Sector-level intents for MVP? | Keep but mark actionability=watch (sector-level actions are rarely explicit trades). |
| O2 | Conviction calibration. | Revisit post-MVP. F4 uses conviction bands but no calibration anchors yet. |
| O3 | Crypto/commodity targets. | Yes, if EntityAnchor resolves the symbol — F4 policy can filter by market. |
| O4 | Intent merging across TopicBlocks. | Keep both for MVP — merging is lossy and can mask temporal ordering. |
| O5 | Minimum evidence span length. | No hard minimum, but flag short spans (< 10 chars) in ambiguity_flags. |

---

## F4: Policy — MVP Contract

Stage: F4
MVP responsibility: Map each F3 NormalizedInvestmentIntent to policy-guided action hints via deterministic rule table, filtering non-executable intents.

```
Stage: F4
Input contract:  NormalizedInvestmentIntent[] (from F3) + PolicyContext (from KOL Profile)
Output contract: PolicyMappingResult[] + PolicyMappedIntent[] (to F5)
Required fields: policy_id, intent_id, action_hint, position_sizing_hint, holding_period_hint, risk_constraints, mapping_rationale, confidence
Forbidden responsibilities: LLM calls, raw text reading, TradeAction generation, execution price determination, multi-layer policy stack, strategy marketplace
Failure cases: Zero PolicyMappedIntents with executable action_hint; intent references invalid intent_id
```

### Stage Overview

F4 is a pure rule-based mapping layer that converts F3 intents into policy-guided hints for F5. It answers: "Given what the KOL said and how they said it, what action should a follower consider, and at what scale?"

For MVP, F4 uses only the `GlobalBasePolicy` — a single deterministic rule table. Higher layers (StyleArchetype, RiskPreference, KOLPersona, ContentCorrection) are post-MVP.

### Input Contract

F4 receives:

| Field | Source | Description |
|---|---|---|
| `NormalizedInvestmentIntent[]` | F3 | List of extracted intents, each with actionability, direction, position_delta_hint, conviction, confidence, evidence_span_ids |
| `PolicyContext` | KOL Profile config | kol_id, style_archetype (default: "mixed"), risk_preference (default: "balanced") |

**Pre-filter:** None. F4 receives ALL F3 intents regardless of actionability. F4 produces a `PolicyMappingResult` and `PolicyMappedIntent` for every intent (audit trail). The executable gate then filters: only `PolicyMappedIntent`s with `action_hint in ("open_position", "add_position", "reduce_position", "close_position", "hold_position")` pass to F5.

### Output Contract

F4 produces two linked records per intent:

**PolicyMappingResult** (full audit record, one per intent):

| Field | Type | Required | Description |
|---|---|---|---|
| `policy_id` | `str` (UUID) | Yes | Unique identifier for this mapping result |
| `intent_id` | `str` | Yes | Back-reference to F3 NormalizedInvestmentIntent.intent_id |
| `policy_version` | `str` | Yes | "global-base-v1" for MVP |
| `policy_layers_applied` | `List[str]` | Yes | ["GlobalBase"] for MVP |
| `action_hint` | `ACTION_HINT_LITERAL` | Yes | Policy-guided action (see mapping table) |
| `position_sizing_hint` | `POSITION_SIZING_HINT_LITERAL` | Yes | none / small / medium |
| `holding_period_hint` | `HOLDING_PERIOD_HINT_LITERAL` | Yes | short_term / medium_term |
| `risk_constraints` | `PolicyRiskConstraints` | Yes | Risk bounds |
| `mapping_rationale` | `str` | Yes | Human-readable explanation of mapping decision |
| `confidence` | `float` (0-1) | Yes | Mapping confidence (derived from F3 confidence) |
| `layer_traces` | `List[PolicyLayerTrace]` | No | Per-layer audit trail (one entry for GlobalBase) |
| `decisions` | `List[PolicyDecision]` | No | Atomic policy decisions |

**PolicyMappedIntent** (compact output consumed by F5, one per intent):

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

### Action Hint Mapping

F4 maps the F3 intent triple `(actionability, direction, position_delta_hint)` to an `action_hint` using a deterministic lookup table.

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

### Executable Gate

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

### Minimum Sizing Rule

**Conviction-Based Sizing:**

| Conviction Range | position_sizing_hint |
|---|---|
| `< 0.35` | `none` |
| `0.35 – 0.70` | `small` |
| `> 0.70` | `medium` |

**Global base ceiling**: The GlobalBasePolicy never outputs `large`. That requires higher policy layers (post-MVP).

**Non-Trade Override:** For any `action_hint` that is not a trade action, `position_sizing_hint` is forced to `none` regardless of conviction.

**Ambiguity Override:** If the F3 intent has `len(ambiguity_flags) >= 2`, `position_sizing_hint` is forced to `review_required` regardless of conviction.

### Minimum Timing Rule

**Holding Period Assignment:**

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

**Interpretation:**
- `short_term` = days to weeks (F5 uses `BacktestConfig.max_holding_days` default of 30)
- `medium_term` = weeks to months (F5 uses `max_holding_days` of 30 for MVP; longer holding periods are post-MVP)

### Policy ID Generation

`policy_id` is a UUID v4 generated at mapping time. Each `PolicyMappingResult` gets a unique `policy_id`. Tracking: `PolicyMappingResult.policy_id` -> `PolicyMappedIntent.policy_id` -> `TradeAction.policy_id`.

MVP does not maintain a policy registry. `policy_version = "global-base-v1"` is a label for reproducibility, not a lookup key.

### Risk Constraints

F4 attaches a `PolicyRiskConstraints` to every `PolicyMappingResult`:

| Field | Rule | Description |
|---|---|---|
| `max_position_hint` | `none` if non-trade; `medium` if conviction >= 0.7; else `small` | Upper bound on position size |
| `requires_human_review` | True if action_hint is `review_required`, or ambiguity_flags >= 2, or conviction < 0.3 on trade actions | Whether human must review before F5 |
| `risk_notes` | Auto-generated list | Human-readable risk annotations |
| `max_concentration_pct` | `None` (not set in MVP) | Post-MVP: sector/ticker concentration cap |
| `stop_loss_hint` | `None` (not set in MVP) | Post-MVP: natural-language stop-loss |
| `time_decay_days` | `None` (not set in MVP) | Post-MVP: conviction decay window |

### Confidence Computation

```
mapping_confidence = F3.confidence
if action_hint == "review_required": mapping_confidence = min(mapping_confidence, 0.6)
if ambiguity_flags: mapping_confidence -= min(0.15, 0.05 * len(ambiguity_flags))
mapping_confidence = max(0.2, mapping_confidence)
```

### Forbidden Responsibilities

F4 MVP MUST NOT:

1. **Call any LLM** — all mapping is deterministic rule-based
2. **Read raw text** — F4 operates on structured NormalizedInvestmentIntent only
3. **Generate TradeAction** — that is F5's responsibility
4. **Determine execution prices** — F4 provides hints, not execution facts
5. **Modify intent direction** — F4 preserves the original direction unchanged
6. **Use multi-layer policy stack** — only GlobalBase in MVP
7. **Apply `large` position sizing** — GlobalBase ceiling is `medium`
8. **Execute the pipeline** — F4 is a pure function, no side effects

### Failure Cases

| # | Condition | Handling |
|---|---|---|
| F4-1 | Input list is empty | Return empty PolicyMappingBatch (not an error) |
| F4-2 | Intent has `actionability = "opinion"` or `"review_required"` | Map normally via rule table (produces `watch_only`, `watch_or_no_trade`, `avoid_or_watch_risk`, or `review_required`). Logged as audit record. Excluded at executable gate. |
| F4-3 | Zero PolicyMappedIntents with executable action_hint | Log warning. Not a hard error — F5 will produce zero TradeActions |
| F4-4 | Intent has no target_symbol | Map normally; F5 will handle missing symbol |
| F4-5 | PolicyContext is missing or incomplete | Use defaults: style_archetype="mixed", risk_preference="balanced" |

### Open Questions

| # | Question | Resolution |
|---|----------|------------|
| O1 | Should `actionability = "watch"` intents enter F4? | **Resolved**: ALL intents enter F4 regardless of actionability. F4 produces PolicyMappingResult for every intent (audit trail). Watch/opinion/review_required intents produce non-executable action hints and are excluded at the executable gate before F5. |
| O2 | Should holding period be conviction-adjusted? | **Default**: No. Holding period follows action semantics, not conviction. |
| O3 | Should MVP support `actionability = "review_required"` from F3? | **Default**: Pass through as `action_hint = "review_required"`. Logged and excluded at the executable gate. |
| O4 | Does `hold_position` require an existing position? | **MVP assumption**: No. `hold_position` means "the KOL is holding / recommends holding." F5 resolves whether this maps to an actual trade or a no-op. |

### Existing Implementation Reference

| File | Purpose |
|---|---|
| `src/finer/schemas/policy.py` | All F4 Pydantic models |
| `src/finer/policy/policy_mapper.py` | PolicyMapper — canonical entry point |
| `src/finer/policy/global_base.py` | GlobalBasePolicy — the deterministic rule table |

---

## F5: TradeAction Generation — MVP Contract

Stage: F5
MVP responsibility: Convert each PolicyMappedIntent into exactly one canonical TradeAction with complete provenance chain (intent_id + policy_id + evidence_span_ids + execution_timing).
Input contract: PolicyMappedIntent[] + EvidenceSpan[] + TemporalAnchor[] + ContentEnvelope.published_at
Output contract: TradeAction[] (every item with `canonical_trace_status = "canonical"`)
Forbidden responsibilities: Intent extraction (F3), policy evaluation (F4), market data enrichment, backtesting (F8), human review routing (F6)

### Canonical Trace Rule

A TradeAction is canonical if and only if all four provenance elements are present and valid:

| Element | Source | Validation |
|---------|--------|------------|
| `intent_id` | `PolicyMappedIntent.intent_id` | Must resolve to a valid `NormalizedInvestmentIntent.intent_id` in the F3 output set |
| `policy_id` | `PolicyMappedIntent.policy_id` | Must resolve to a valid `PolicyMappingResult.policy_id` in the F4 output set |
| `evidence_span_ids` | `NormalizedInvestmentIntent.evidence_span_ids` (looked up via `intent_id`) | Length >= 1; each ID must resolve to a valid `EvidenceSpan.evidence_span_id` in the F2 output set |
| `execution_timing` | Computed by F5 (see ExecutionTiming section) | All four clocks populated; `timing_policy_id` set; `market` and `timezone` set |

The `canonical_trace_status` field is auto-derived by the TradeAction model validator — F5 does not set it explicitly. If any of the four elements is missing, the validator sets status to `partial` or `non_canonical`. For MVP, F5 MUST reject any PolicyMappedIntent that would produce a non-canonical TradeAction.

F5 MUST NOT use the legacy `TradeActionExtractor.extract_from_text()` path. Every TradeAction must flow through F3 -> F4 -> F5.

### Non-Canonical Rejection Rule

Before generating a TradeAction, F5 validates each PolicyMappedIntent against upstream data. If any check fails, F5 rejects the intent and logs a structured rejection record.

| Check | Failure Condition | Rejection Action |
|-------|-------------------|------------------|
| Intent lookup | `PolicyMappedIntent.intent_id` not found in F3 output | Skip with reason `intent_not_found` |
| Policy lookup | `PolicyMappedIntent.policy_id` not found in F4 output | Skip with reason `policy_not_found` |
| Evidence binding | `NormalizedInvestmentIntent.evidence_span_ids` is empty | Skip with reason `no_evidence_spans` |
| Evidence resolution | Any `evidence_span_id` not found in F2 output | Skip with reason `evidence_span_missing` |
| Ticker resolution | `NormalizedInvestmentIntent.target_symbol` is None or empty | Skip with reason `no_ticker_symbol` |
| Temporal resolution | No TemporalAnchor exists for this intent AND ContentEnvelope.published_at is missing | Skip with reason `no_temporal_anchor` |

Rejection records are written to the F5 output manifest as `rejected_intents[]` with fields: `intent_id`, `policy_id`, `reason`, `timestamp`.

### ExecutionTiming Four Clock Rule

Every TradeAction's `ExecutionTiming` contains four timestamps:

| Clock | Field | Source | Rule |
|-------|-------|--------|------|
| **Clock 1: Publication** | `intent_published_at` | `ContentEnvelope.published_at` (from F1) | Direct copy. Must be a valid `datetime`. |
| **Clock 2: Effectiveness** | `intent_effective_at` | `TemporalAnchor` with `anchor_type = "effective_trade_at"` or `anchor_type = "mentioned_at"` | If a TemporalAnchor with `resolved_time` exists, use its `resolved_time`. Prefer `effective_trade_at` over `mentioned_at`. If none resolved, set to `None`. |
| **Clock 3: Decision** | `action_decision_at` | System clock | Timestamp when F5 generates this TradeAction. For MVP batch mode, this is the pipeline processing time. |
| **Clock 4: Executable** | `action_executable_at` | Computed from market calendar | See computation rule below. |

**Clock 4 Computation Rule:**

```
base_time = intent_effective_at if intent_effective_at is not None else intent_published_at
action_executable_at = next_market_open(base_time, market)
```

Where `next_market_open(t, market)` returns the opening time of the first trading session at or after datetime `t` for the given market.

If `base_time` falls during a trading session (pre_market or regular), `action_executable_at` = next trading day's open (the signal cannot be acted upon within the same session for MVP).

If `base_time` falls after close or on a non-trading day, `action_executable_at` = next trading day's open.

The `timing_policy_id` field MUST be set to `"market-calendar-next-open-v1"` for all MVP TradeActions.

The `market_session_at_publish` field is determined by checking `intent_published_at` against the market calendar:
- Before market open -> `pre_market`
- During regular hours -> `regular`
- After close -> `after_close`
- Non-trading day -> `non_trading_day`

The `execution_delay_reason` field is populated when `action_executable_at > action_decision_at`, with a human-readable explanation.

### Action Step Mapping

F5 maps `PolicyMappedIntent.action_hint` -> `ActionStep.action_type` using the F3 intent's `direction` to resolve ambiguity.

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
| `review_required` | Skipped by F4 filter | — | — |

**direction -> TradeDirection mapping:**

| F3 `direction` | TradeAction `direction` |
|----------------|------------------------|
| `bullish` | `BULLISH` |
| `bearish` | `BEARISH` |
| `neutral` | `NEUTRAL` |
| `mixed` | `NEUTRAL` (with warning) |
| `unknown` | `NEUTRAL` (with warning) |

**Position size mapping (`position_sizing_hint` -> `ActionStep.position_size_pct`):**

| `position_sizing_hint` | `position_size_pct` |
|------------------------|---------------------|
| `none` | `0.0` (no-op, but TradeAction is still generated as `watch`) |
| `small` | `0.05` |
| `medium` | `0.15` |
| `large` | `0.30` |
| `review_required` | Skipped by F4 filter |

If `risk_constraints.max_position_hint` is tighter than the mapped value, F5 clamps `position_size_pct` to the risk ceiling:

| `max_position_hint` | Ceiling |
|---------------------|---------|
| `none` | 0.0 |
| `small` | 0.10 |
| `medium` | 0.25 |
| `large` | 0.50 |

**Holding period mapping (`holding_period_hint` -> `TradeAction.time_horizon`):**

| `holding_period_hint` | `time_horizon` |
|-----------------------|----------------|
| `intraday` | `"intraday"` |
| `short_term` | `"short_term"` |
| `medium_term` | `"medium_term"` |
| `long_term` | `"long_term"` |
| `review_required` | Skipped by F4 filter |

**Action chain structure:** For MVP, every TradeAction has exactly one `ActionStep` with `sequence = 1`. Multi-step chains are post-MVP.

### Evidence Binding

F5 selects which `EvidenceSpan` IDs to attach to a TradeAction using a deterministic, auditable process.

**Rule: Inherit all evidence from the F3 intent.**

```
TradeAction.evidence_span_ids = NormalizedInvestmentIntent.evidence_span_ids
```

F5 looks up the NormalizedInvestmentIntent via `PolicyMappedIntent.intent_id`, then copies its `evidence_span_ids` list verbatim. F5 does NOT filter, add, or re-rank evidence spans.

**Validation:** Every ID in the list must resolve to a valid `EvidenceSpan` in the F2 output. If any ID is unresolvable, the entire PolicyMappedIntent is rejected.

**Minimum count:** `len(evidence_span_ids) >= 1`. This is enforced by the rejection rule.

**Source attribution:** The `TradeAction.source.evidence_text` field is populated by concatenating the `text` fields of all referenced EvidenceSpans, joined by `" | "`. If the concatenated text exceeds 500 characters, truncate to 500 with `"..."` suffix.

**Source content_id:** Populated from `NormalizedInvestmentIntent.envelope_id`.

### One-to-One Mapping Rule

For MVP, F5 produces **exactly one TradeAction per PolicyMappedIntent**. There is no fan-out or fan-in.

### Required Fields Table

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
| `execution_timing` | Computed | Yes | — |
| `canonical_trace_status` | Auto-derived by validator | Yes | `"canonical"` |
| `confidence` | `PolicyMappedIntent.mapping_confidence` | Yes | — |
| `requires_manual_review` | `PolicyMappedIntent.requires_human_review` | Yes | `False` |
| `time_horizon` | Mapped from `holding_period_hint` | No | `None` |
| `rationale` | `PolicyMappedIntent.mapping_rationale` | No | `None` |

### Failure Cases

| # | Condition | Severity | Handling |
|---|-----------|----------|----------|
| F5-1 | Zero PolicyMappedIntents received from F4 | Fatal | Return empty TradeAction[] with rejection log |
| F5-2 | All PolicyMappedIntents rejected | Non-fatal | Return empty TradeAction[] with full rejection log |
| F5-3 | Market calendar unavailable for target market | Fatal | Raise error `MARKET_CALENDAR_UNAVAILABLE` |
| F5-4 | ContentEnvelope.published_at is None | Fatal for that intent | Reject with reason `no_temporal_anchor` |
| F5-5 | NormalizedInvestmentIntent.target_symbol is None | Fatal for that intent | Reject with reason `no_ticker_symbol` |
| F5-6 | Evidence span ID resolution failure | Fatal for that intent | Reject with reason `evidence_span_missing` |
| F5-7 | Conflicting action_hint and direction | Non-fatal | Generate TradeAction with appropriate action_type, log warning |
| F5-8 | `position_sizing_hint = "review_required"` bypasses F4 filter | Should not happen | Reject with reason `review_required_bypassed` |

### Forbidden Responsibilities

F5 must NOT:

- Extract investment intents (F3 responsibility)
- Evaluate policy rules or risk constraints (F4 responsibility)
- Fetch market data or compute enrichment (post-MVP / F8 responsibility)
- Run backtesting or compute returns (F8 responsibility)
- Route to human review or collect RLHF feedback (F6 responsibility)
- Modify upstream schemas
- Generate TradeActions by direct text extraction (bypassing F3+F4)
- Produce multiple TradeActions from a single PolicyMappedIntent (for MVP)
- Use the legacy `TradeActionExtractor.extract_from_text()` path

### Open Questions

| # | Question | Default if Unresolved |
|---|----------|----------------------|
| O1 | How does F5 handle `action_hint = "add_position"` when no prior position exists? | Treat as `open_position` for MVP. F5 does not track portfolio state — that is F8's responsibility. |
| O2 | Should F5 populate `TradeAction.enrichment`? | Leave `enrichment = None` for MVP. F8 has access to market_prices.csv. |
| O3 | What happens when `position_sizing_hint = "none"` but `action_hint` is `open_position`? | Generate as `watch` action_type with `position_size_pct = 0`. |
| O4 | Should F5 validate ticker exists in price data? | No. F5 does not have access to market_prices.csv. F8 handles ticker-not-found. |
| O5 | How does F5 handle timezone for cross-market scenarios? | Use the market's timezone. All times in ExecutionTiming are in the market's timezone. |
| O6 | Should `reduce_position` generate partial close or full close? | Generate `close_long`/`close_short` with the reduced position size. For MVP, F8 treats any close as full exit. |

---

## F8: Backtest — MVP Contract

Stage: F8
MVP responsibility: Replay a single KOL's canonical TradeActions against historical market prices to produce per-trade returns, an equity curve, and aggregate performance metrics.

### Input Contract

F8 receives two inputs:

1. **Ordered TradeAction sequence** — a list of `TradeAction` objects from F5, sorted by `execution_timing.action_executable_at` ascending. For MVP, only `canonical_trace_status == "canonical"` actions are eligible. Actions with `partial` or `non_canonical` status are skipped with a logged skip-reason.

2. **Market price table** — a flat file (CSV or in-memory DataFrame) with daily OHLCV bars:

| Column | Type | Description |
|--------|------|-------------|
| `date` | `date` (YYYY-MM-DD) | Trading calendar date |
| `ticker` | `str` | Normalized ticker (must match `TradeAction.target.ticker_normalized`) |
| `open` | `float` | Session open price |
| `high` | `float` | Session high |
| `low` | `float` | Session low |
| `close` | `float` | Session close |
| `volume` | `int` | Session volume |

Date range must cover all `action_executable_at` dates plus a configurable look-forward window (default 30 trading days) for max-hold exit resolution.

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

**EquityPoint:**

| Field | Type |
|-------|------|
| `date` | `date` |
| `equity_value` | `float` |
| `drawdown_pct` | `float` |
| `open_positions` | `int` |

**TradeDetail:**

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

### Execution Price Rules

MVP uses a deterministic "next-open" fill model to prevent look-ahead bias:

| Scenario | Entry price | Exit price |
|----------|-------------|------------|
| Published before market open | Next trading day open | Next signal's entry or exit-day open |
| Published during or after close | Next trading day open | Next signal's entry or exit-day open |

F8 uses the **open price of the first trading date >= `action_executable_at.date()`** as the entry fill. Exit fills use the same convention.

If `execution_timing` is missing (should not happen for canonical actions), the action is skipped with reason `missing_execution_timing`.

### Position Sizing

- **Initial capital**: configurable, default 100,000.
- **Per-trade allocation**: `position_size_pct` from `ActionStep` (range 0-1). If absent, default to 0.10 (10% of current equity).
- **Capital is recycled**: realized PnL from closed trades returns to available cash. No leverage for MVP.
- **Max concurrent positions**: not capped for MVP.
- **Portfolio-level constraint**: if a new entry would exceed 100% allocated, reduce the position to fit remaining equity and log a warning.

### Holding and Exit Rules

MVP exit strategy (in priority order):

1. **Signal reversal**: A new TradeAction for the same `ticker_normalized` with an opposite `direction` closes the existing position on the reversal signal's entry date.

2. **Max-hold exit**: If no exit signal arrives within `max_hold_days` (default 30 trading days), close the position at the open price of the 31st trading day. Exit reason: `TIME_EXIT`.

3. **End-of-period**: At the end of the price data window, close all open positions at the last available close price. Exit reason: `END_OF_PERIOD`.

4. **Hold / Watch / Neutral signals**: Actions with `direction` in {`neutral`, `watchlist`, `risk_warning`} or `action_type` in {`hold`, `watch`} do not open or close positions.

For MVP, there are **no stop-loss or take-profit** mechanisms.

### Edge Cases

| Case | Handling |
|------|----------|
| Ticker has no price data on entry date | Skip action, reason: `no_price_data` |
| Ticker has no price data on exit date | Use last available price before exit date; if none exist, skip |
| Ambiguous timing (non-trading day) | Roll forward to next trading day open |
| Contradictory signals in same session | Both processed in chronological order; later one triggers reversal |
| Duplicate trade_action_id | Deduplicate by ID; keep first occurrence |
| direction = bearish + action_type = short | Open a short position |
| direction = bearish, no explicit short action_type | Treat as no-op for MVP |
| position_size_pct = None | Default to 0.10 |
| Multiple action_chain steps | Only `sequence == 1` is used for MVP |

### Required Fields from TradeAction

| Field | Validation |
|-------|------------|
| `trade_action_id` | Non-empty string |
| `target.ticker_normalized` | Non-empty, matches price data |
| `direction` | Must be one of: bullish, bearish, neutral, watchlist, risk_warning |
| `action_chain[0].action_type` | Must be determinable (first step exists) |
| `execution_timing.action_executable_at` | Valid datetime |
| `execution_timing.market` | Non-empty string |
| `canonical_trace_status` | Must be `"canonical"` |

If any required field is missing or invalid, the action is skipped with a structured skip record.

### Forbidden Responsibilities

F8 must NOT:

- Fetch live or real-time market data
- Modify TradeAction records (read-only)
- Generate new TradeActions or signals
- Compute slippage, commissions, or transaction costs (`commission_pct=0`, `slippage_pct=0` for MVP; transaction costs are post-MVP)
- Handle dividends, splits, or delistings
- Support multi-KOL ranking or portfolio optimization
- Run LLM calls
- Write to F0-F7 data directories
- Expose a live trading API

### Failure Cases

| Failure | Severity | Handling |
|---------|----------|----------|
| No TradeActions provided | Fatal | Return empty BacktestReport with `actions_backtested = 0` |
| All actions skipped | Non-fatal | Return BacktestReport with zero trades |
| Price data file missing or malformed | Fatal | Raise `FinerError` with stage=F8, code=`INVALID_PRICE_DATA` |
| Price data date range insufficient | Non-fatal | Backtest what is possible, log warning |
| Ticker normalization mismatch | Non-fatal per action | Skip affected actions |

### Open Questions

| # | Question | Default if Unresolved |
|---|----------|----------------------|
| O1 | Short-selling model: long-only or with shorts? | MVP supports short positions. No borrowing cost model. |
| O2 | Currency alignment for multi-market? | Assume all prices are in the same unit for MVP. |
| O3 | Intraday prices vs limit orders? | No. MVP uses daily OHLCV with open price only. |
| O4 | Equity curve granularity? | Daily. |
| O5 | Backtest reproducibility hash? | Out of scope for MVP. |
| O6 | Confidence-weighted sizing? | No. MVP uses raw `position_size_pct`. |
