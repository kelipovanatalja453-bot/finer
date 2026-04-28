# Quality Gate Contract Specification

> Version: v1.0
> Last Updated: 2026-04-27
> Status: Implemented

---

## Overview

Quality Gate Contract provides task-oriented quality gate evaluation for determining whether content is ready for V1 intent extraction, needs manual review, or should be rejected.

---

## Core Concepts

### QualityGatePolicy

Configuration for quality gate evaluation thresholds.

| Field | Default | Description |
|-------|---------|-------------|
| `pass_threshold` | 0.75 | Minimum overall score for PASS |
| `review_threshold` | 0.45 | Minimum overall score for REVIEW |
| `financial_relevance_min` | 0.6 | Minimum financial_relevance for PASS |
| `evidence_traceability_min` | 0.6 | Minimum evidence_traceability for PASS |
| `reject_financial_max` | 0.3 | Maximum financial_relevance for REJECT |
| `critical_dimension_min` | 0.3 | Critical threshold for key dimensions |
| `warn_dimension_min` | 0.5 | Warning threshold for dimensions |

### QualityGateDecision

Result of quality gate evaluation.

| Field | Type | Description |
|-------|------|-------------|
| `status` | `Literal["pass", "review", "reject"]` | Gate decision |
| `score` | `float` | Overall quality score (0.0-1.0) |
| `reasons` | `List[str]` | Reasons for the decision |
| `recommended_next_step` | `Literal["extract_intent", "manual_review", "reprocess_source", "drop"]` | Recommended action |
| `block_decisions` | `Optional[List[QualityGateDecision]]` | Per-block decisions for envelope |
| `metadata` | `dict` | Additional context |

---

## Gate Decision Logic

### PASS Condition

```
overall >= 0.75
AND financial_relevance >= 0.6
AND evidence_traceability >= 0.6
AND no critical dimension failures
```

**Recommended Next Step**: `extract_intent`

### REJECT Condition

```
overall < 0.45
AND financial_relevance < 0.3
```

**Recommended Next Step**: `drop`

### REVIEW Condition

Any case that doesn't meet PASS or REJECT conditions.

**Recommended Next Step**:
- `reprocess_source` if readability issues detected
- `manual_review` otherwise

---

## Cat's Image Strategy (猫大人图片策略)

For image-based content, OCR issues should not immediately trigger rejection. Evaluate by block:

| Block Type | Condition | Decision |
|------------|-----------|----------|
| Large strategy text | Readable + high financial relevance | PASS (→ V1) |
| Table/Chart | Low OCR but clear position | REVIEW |
| Social media UI noise | Unrecognizable | DROP |

---

## API Functions

### evaluate_quality_card

Evaluate a single QualityCard against the gate policy.

```python
def evaluate_quality_card(
    card: QualityCard,
    policy: Optional[QualityGatePolicy] = None,
) -> QualityGateDecision
```

### evaluate_envelope_quality

Evaluate a ContentEnvelope with block-level aggregation.

```python
def evaluate_envelope_quality(
    envelope: ContentEnvelope,
    policy: Optional[QualityGatePolicy] = None,
) -> QualityGateDecision
```

---

## Policy Variants

### Default Policy

Standard thresholds for most use cases.

```python
policy = get_default_policy()
```

### Strict Policy

Higher thresholds for production/critical paths.

```python
policy = create_strict_policy()
# pass_threshold=0.85, financial_relevance_min=0.7
```

### Lenient Policy

Lower thresholds for experimental/development use.

```python
policy = create_lenient_policy()
# pass_threshold=0.65, financial_relevance_min=0.5
```

---

## Examples

### Example 1: High Quality Card

```python
card = QualityCard(
    readability_score=0.9,
    semantic_completeness_score=0.85,
    financial_relevance_score=0.95,
    entity_resolution_score=0.8,
    temporal_resolution_score=0.7,
    evidence_traceability_score=0.85,
)

decision = evaluate_quality_card(card)
# decision.status = "pass"
# decision.recommended_next_step = "extract_intent"
```

### Example 2: Low Financial Relevance

```python
card = QualityCard(
    readability_score=0.9,
    semantic_completeness_score=0.9,
    financial_relevance_score=0.4,  # Low
    entity_resolution_score=0.8,
    temporal_resolution_score=0.8,
    evidence_traceability_score=0.8,
)

decision = evaluate_quality_card(card)
# decision.status = "review"
# decision.reasons contains financial_relevance warning
```

### Example 3: Envelope with Mixed Blocks

```python
envelope = ContentEnvelope(
    source_type="image",
    blocks=[
        high_quality_text_block,  # pass
        low_ocr_table_block,      # review
        noise_block,              # reject
    ],
    quality_card=QualityCard.create_default(0.6),
)

decision = evaluate_envelope_quality(envelope)
# decision.status = "pass" (majority)
# decision.block_decisions[0].status = "pass"
# decision.block_decisions[1].status = "review"
# decision.block_decisions[2].status = "reject"
```

---

## Implementation Notes

1. **Schema Independence**: QualityGate uses existing QualityCard from `schemas.quality`, not a new schema.

2. **Block Aggregation**: Envelope evaluation aggregates block decisions based on majority vote (>60% pass = overall pass).

3. **Critical Failures**: Dimensions below `critical_dimension_min` trigger reprocessing suggestion.

4. **Metadata Tracking**: Decisions include `weakest_dimension` and `critical_failures` count for debugging.

5. **Service Registration**: Functions registered in `services/__init__.py` with lazy import.
