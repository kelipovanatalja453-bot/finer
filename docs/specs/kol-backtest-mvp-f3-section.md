## F3: Intent — MVP Contract

**Stage:** F3 (Intent Extraction)

**MVP responsibility:** Extract normalized investment intents from TopicBlocks, resolving each intent to a target entity with direction, actionability, and evidence traceability — without generating TradeActions or position sizing decisions.

---

### Input Contract

F3 receives the following from upstream stages:

| Source | Schema | Key fields consumed by F3 |
|--------|--------|---------------------------|
| F1.5 | `TopicBlock[]` | `topic_block_id`, `source_block_ids[]`, `topic_type`, `primary_entity_ids[]`, `raw_text`, `confidence` |
| F2 | `EvidenceSpan[]` | `evidence_span_id`, `block_id`, `char_start`, `char_end`, `text`, `confidence` |
| F2 | `EntityAnchor[]` | `entity_anchor_id`, `entity_type`, `raw_text`, `resolved_symbol`, `market`, `confidence`, `evidence_span_id` |
| F2 | `TemporalAnchor[]` | `anchor_id`, `anchor_type`, `raw_text`, `resolved_time`, `confidence`, `timezone` |

F3 does NOT receive raw ContentBlocks directly — it operates on the assembled TopicBlock graph from F1.5, enriched with F2 anchors.

---

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

---

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
| `conviction` | `float` | YES | 0.0–1.0, semantic strength of the KOL's belief |
| `confidence` | `float` | YES | 0.0–1.0, model extraction confidence |
| `evidence_span_ids` | `List[str]` | YES | At least one evidence span ID |

Optional fields that F3 MAY populate: `creator_id`, `sentiment_score`, `risk_preference_hint`, `time_horizon_hint`, `temporal_anchor_ids`, `ambiguity_flags`, `metadata`.

---

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

---

### Failure Cases

| Case | Behavior |
|------|----------|
| TopicBlock has no EntityAnchors | Produce zero intents; log warning. F3 cannot create an intent without a target entity. |
| EntityAnchor has no resolved_symbol | Set `actionability=review_required`, `ambiguity_flags=["unresolved_symbol"]`. Intent passes through but F4 will escalate. |
| Text is pure opinion with no actionable signal | Produce intent with `actionability=opinion`, `position_delta_hint=none`. F4 filters these out (only `explicit_action` and `watch` pass to F4 for MVP). |
| Contradictory signals in one TopicBlock | Produce a single intent with `direction=mixed`, `ambiguity_flags=["contradictory_signals"]`. Do NOT split into two opposing intents. |
| Confidence below threshold (< 0.5) | Still produce the intent but with `actionability=review_required`. F4 will not map it to an actionable policy. |
| Multiple entities in one TopicBlock | Produce one intent per entity. Each intent references the evidence spans relevant to that entity. |
| TemporalAnchor has no resolved_time | Intent still produced; `temporal_anchor_ids` references the anchor, but `time_horizon_hint` defaults to `unknown`. |

---

### 1. Intent Direction Taxonomy

**Valid directions for MVP:**

| Direction | Meaning | When to use |
|-----------|---------|-------------|
| `bullish` | KOL expresses positive outlook or recommends buying/holding | "我看好宁德时代", "继续加仓" |
| `bearish` | KOL expresses negative outlook or recommends selling/avoiding | "新能源要跌", "减仓腾讯" |
| `neutral` | KOL acknowledges the entity without clear directional bias | "腾讯目前估值合理" |
| `mixed` | KOL expresses both positive and negative signals in the same TopicBlock | "短期看空但长期看好" |
| `unknown` | Direction cannot be determined from the text | Ambiguous or insufficient context |

**MVP rule:** F3 MUST classify every intent. Default to `unknown` only when text genuinely lacks directional signal — never as a fallback for extraction failure (use `review_required` actionability instead).

---

### 2. Actionability Rules

F3 decides actionability by analyzing the text semantics of the TopicBlock. The decision is based on what the KOL *says*, not what the model *infers*.

**Classification rules:**

| Actionability | Criteria | Text pattern signals |
|---------------|----------|---------------------|
| `explicit_action` | KOL uses imperative or declarative language about their own trading action | "我加仓了", "买入", "清仓", "已减持", "准备建仓", "今天开盘买" |
| `watch` | KOL expresses interest or signals potential future action without committing | "关注", "观察", "看好", "值得留意", "列入自选", "可以考虑" |
| `opinion` | KOL shares analysis, commentary, or belief without any action implication | "我认为", "估值偏高", "业绩不错", "行业趋势向上" |
| `review_required` | Ambiguous signal, unresolved entity, or confidence too low | Default when target_symbol is missing, confidence < 0.5, or text is contradictory |

**Decision procedure (ordered):**

1. If `target_symbol` is not resolvable from EntityAnchor → `review_required`
2. If `confidence` < 0.5 → `review_required`
3. If text contains explicit action verbs (buy/sell/add/reduce/close) referring to the KOL's own position → `explicit_action`
4. If text contains watchlist/interest signals without commitment → `watch`
5. Otherwise → `opinion`

**MVP filter:** Only intents with `actionability in ("explicit_action", "watch")` pass to F4. Intents with `opinion` or `review_required` are retained in the IntentBatch for audit but do not enter the policy mapping pipeline.

---

### 3. Position Delta Hint Semantics

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

- `actionability=opinion` → `position_delta_hint=none` (opinion never implies position change)
- `actionability=explicit_action` → map from verb semantics: "加仓"→`add`, "清仓"→`exit`, "建仓"→`open`, "持有"→`hold`, "减持"→`reduce`
- `actionability=watch` → `position_delta_hint=none` (watching is not acting)
- Bearish direction + `open`/`add` → flag `ambiguity_flags=["bearish_position_mismatch"]` (may indicate short-selling, which is out of MVP scope)

---

### 4. Evidence Trace Rule

Every intent MUST reference at least one `evidence_span_id`. This is a hard requirement — no intent exists without textual evidence.

**Rules:**

1. `evidence_span_ids` MUST contain at least one ID that maps to a valid EvidenceSpan in the F2 output
2. Each referenced EvidenceSpan's `block_id` MUST be in the intent's `block_ids` list
3. Evidence spans SHOULD cover the text that supports the direction classification (the bullish/bearish statement itself)
4. Evidence spans SHOULD cover the text that supports the actionability classification (the action verb, if present)
5. If an intent is derived from multiple evidence spans (e.g., entity mention in one span, direction in another), ALL supporting spans must be listed

**Auditability:** The evidence chain must be complete enough that a human reviewer can read the referenced EvidenceSpan texts and understand why F3 classified the intent as it did. This is the foundation of the "auditable TradeActions" requirement in the MVP definition.

---

### 5. Intent Timing Semantics

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

---

### Design Decisions and Rationale

**Q1: How does F3 decide actionability?**
A: By ordered rule evaluation over text semantics, not LLM classification alone. The procedure is: symbol resolvability → confidence threshold → action verb detection → watchlist signal detection → default to opinion. This makes actionability deterministic and auditable.

**Q2: Does F3 resolve symbols or does F2?**
A: F2 resolves symbols. F3 consumes EntityAnchor.resolved_symbol. If F2 could not resolve, F3 sets actionability=review_required. F3 NEVER performs its own symbol lookup.

**Q3: How many intents can one TopicBlock produce?**
A: One intent per target entity. A TopicBlock discussing 3 stocks produces 3 intents, each with its own evidence spans and direction. The MVP assumption (single KOL, frozen content) means most TopicBlocks will produce 0-2 intents.

**Q4: What confidence/conviction thresholds filter noise?**
A: confidence < 0.5 → review_required (filtered from F4 pipeline). For conviction, no hard floor — low-conviction intents pass through with their conviction score intact for F4 to weigh. The existing `is_actionable()` method requires confidence >= 0.5 for explicit_action and >= 0.7 for watch.

**Q5: How does F3 handle contradictory signals?**
A: Produce a single intent with direction=mixed and ambiguity_flags=["contradictory_signals"]. Do NOT split into opposing intents — that would create two TradeActions that cancel each other, which is noise. F4 sees the mixed flag and can apply appropriate policy (e.g., watch_only or review_required).

---

### Open Questions

1. **Sector-level intents for MVP?** The schema supports target_type=sector, but the MVP scope says "single KOL → auditable TradeActions." Should sector intents be filtered out or kept? Recommendation: keep but mark actionability=watch (sector-level actions are rarely explicit trades).

2. **Conviction calibration.** The existing schema has conviction (0-1) but no guidance on what constitutes "high" vs "low." F4 needs this to map to position sizing. Should F3 define calibration anchors (e.g., "I'm 100% sure" = 0.9, "might go up" = 0.3)?

3. **Crypto/commodity targets.** EntityAnchor supports crypto and commodity types. Are these in MVP scope? If the KOL discusses BTC, should F3 produce an intent? Recommendation: yes, if EntityAnchor resolves the symbol — F4 policy can filter by market.

4. **Intent merging across TopicBlocks.** If the same KOL says "看好腾讯" in TopicBlock A and "加仓腾讯" in TopicBlock B, should F3 merge these into one intent or keep both? Recommendation: keep both for MVP — merging is lossy and can mask the temporal ordering of the KOL's evolving position.

5. **Minimum evidence span length.** Should there be a minimum character count for evidence spans? A 2-character span ("看好") is technically valid but provides minimal audit context. Recommendation: no hard minimum, but flag short spans (< 10 chars) in ambiguity_flags.
