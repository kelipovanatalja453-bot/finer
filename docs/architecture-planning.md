# Architecture Planning (Historical)

These were early planning stubs for a microservices decomposition.
The actual code lives in `src/finer/` as a monolith. Preserved here for reference.

## Apps (planned)

- **API**: Thin routing layer. List content, fetch docs, trigger backtests. Core logic in services.
- **Worker**: Run OCR/ASR/extraction/backtest jobs. Write canonical outputs to `data/processed/`.
- **Admin**: Optional thin ops layer. Content status, pipeline status, QA views. Annotation stays in Label Studio.

## Services (planned)

- **Ingestion**: Register source items, write manifests, move files, attach metadata.
- **Parsing**: OCR orchestration, ASR orchestration, normalize to segment records.
- **Extraction**: Detect sectors/themes, generate candidate events, attach confidence.
- **Review**: Export to Label Studio, import reviewer outputs, update event records.
- **Backtest**: Event-study backtests, grouped metrics, result artifacts.
