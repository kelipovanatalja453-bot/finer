# MVP Repository Structure

This repository should be implemented as a pipeline-oriented monorepo.

## Principles

- keep canonical schemas independent from specific tools
- separate raw data, processed data, and reviewed data
- isolate ingestion, parsing, extraction, and backtesting
- make every stage rerunnable

## Proposed structure

```text
finer/
  README.md
  docs/
    open-source-selection.md
    system-architecture.md
    mvp-repo-structure.md
    execution-plan.md
  schemas/
    content.schema.json
    segment.schema.json
    event.schema.json
  data/
    raw/
      trader_ji/
        weekly_strategy/
        daily_pre/
        daily_post/
        bilibili_video/
        livestream/
    processed/
      manifests/
      documents/
      transcripts/
      candidate_events/
      approved_events/
    backtests/
  apps/
    api/
    worker/
    admin/
  services/
    ingestion/
    parsing/
    extraction/
    review/
    backtest/
  scripts/
    bootstrap/
    ingestion/
    parsing/
    extraction/
    backtest/
  configs/
    creators/
    label_studio/
  tests/
```

## App responsibilities

### `apps/api`

- REST API for content, events, and backtests
- should be the single read/write interface for external clients

### `apps/worker`

- background job runner
- handles OCR, ASR, extraction, and backtest jobs

### `apps/admin`

- optional thin operations UI
- should remain minimal while Label Studio handles annotation

## Service responsibilities

### `services/ingestion`

- source registration
- file naming
- manifest creation
- raw file persistence

### `services/parsing`

- OCR orchestration
- ASR orchestration
- parser output normalization
- Markdown render generation if needed

### `services/extraction`

- sector detection
- event candidate generation
- proxy mapping
- extraction scoring

### `services/review`

- export/import tasks for Label Studio
- synchronize human-reviewed labels into canonical event records

### `services/backtest`

- event-study engine
- benchmark selection
- metric calculation
- report materialization

## Recommended implementation order

1. `schemas/`
2. `services/ingestion`
3. `services/parsing`
4. `services/extraction`
5. `services/backtest`
6. `services/review`
7. `apps/api`

## What should not be built first

- a generic chat UI
- multi-agent orchestration
- creator style simulation
- model fine-tuning infrastructure

Those are downstream features. The first milestone is a reliable event pipeline.
