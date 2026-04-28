# Execution Plan

## Objective

Stand up the first usable pipeline for `trader韭` weekly strategy content.

## Milestone 1: raw content intake

Deliverables:

- image file intake convention
- content manifest records
- normalized directory layout

Tasks:

1. implement content manifest writer
2. define creator config for `trader韭`
3. move sample March weekly strategy images into canonical `data/raw/` paths

## Milestone 2: OCR parsing

Deliverables:

- OCR output JSON per content item
- normalized document segments

Tasks:

1. integrate `PaddleOCR`
2. store OCR blocks as segment records
3. keep source page/block positions

## Milestone 3: event extraction

Deliverables:

- candidate event records with sector, direction, horizon, proxy placeholders

Tasks:

1. build sector taxonomy
2. build proxy mapping table
3. implement candidate event generation

## Milestone 4: human review

Deliverables:

- Label Studio task export/import workflow
- approved event records

Tasks:

1. define Label Studio task schema
2. export candidate events
3. import reviewed events back into canonical schema

## Milestone 5: backtesting

Deliverables:

- first event-study report for March weekly strategy content

Tasks:

1. define event timing rule
2. define proxy lookup rule
3. implement return windows
4. generate grouped metrics

## Stop conditions

Pause and re-evaluate if any of these happen:

- OCR quality is too poor to recover with light cleanup
- event schema cannot stably represent creator content
- proxy mapping is too ambiguous to support backtesting

Those are product-definition failures, not implementation failures.
