# Open-Source Selection

This document records which GitHub projects are suitable for the MVP, which are deferred, and why.

## Selection criteria

A project is included in the MVP only if it:

- solves a direct bottleneck in the current pipeline
- reduces implementation time materially
- does not force the architecture in the wrong direction
- has manageable operational and license risk

## MVP selections

### 1. `nilaoda/BBDown`

- Role: Bilibili download pipeline
- Use in this project: fetch `trader韭` videos, livestream replays, and audio source files
- Why selected:
  - directly solves Bilibili ingestion
  - widely used
  - lower engineering cost than building a downloader
- Risks:
  - copyright and platform terms still need to be handled separately
- Decision: `Use in MVP`

### 2. `yt-dlp/yt-dlp`

- Role: generic video downloader
- Use in this project: fallback and future multi-platform expansion
- Why selected:
  - robust downloader
  - broad platform coverage
  - useful as fallback when BBDown is insufficient
- Risks:
  - also subject to source platform usage constraints
- Decision: `Use in MVP as fallback`

### 3. `PaddlePaddle/PaddleOCR`

- Role: OCR and document parsing for image-based content
- Use in this project: weekly strategy long images, screenshot-based notes, image-heavy content
- Why selected:
  - strong Chinese OCR support
  - directly relevant to current `trader韭` workflow
  - better short-term fit than starting with a generic document framework
- Risks:
  - complex layouts still need post-processing
- Decision: `Use in MVP`

### 4. `m-bain/whisperX`

- Role: ASR with timestamps
- Use in this project: videos, livestreams, audio notes
- Why selected:
  - word-level timestamps
  - supports diarization workflow
  - directly useful for event-time alignment
- Risks:
  - GPU environment and model runtime need to be managed later
- Decision: `Use in MVP`

### 5. `pyannote/pyannote-audio`

- Role: speaker diarization
- Use in this project: multi-speaker content, Q&A live sessions
- Why selected:
  - best fit for speaker segmentation requirement
  - complements WhisperX well
- Risks:
  - not essential for single-speaker content
- Decision: `Use in MVP where needed`

### 6. `HumanSignal/label-studio`

- Role: multimodal annotation and human review
- Use in this project:
  - OCR text review
  - event validation
  - sector / direction / horizon / proxy labeling
- Why selected:
  - supports text, image, audio, video, and time series
  - best fit for the human-in-the-loop stage
  - materially reduces custom UI effort
- Risks:
  - requires config design for task schema
- Decision: `Use in MVP`

## Deferred but valuable

### 7. `microsoft/qlib`

- Role: quant research platform
- Use later:
  - signal research
  - feature studies
  - richer backtest workflows
- Why deferred:
  - MVP needs event-driven backtesting, not a full quant stack
  - a custom event backtester will be faster initially
- Decision: `Phase 2`

### 8. `docling-project/docling`

- Role: unified multi-format document ingestion
- Use later:
  - one parser layer for PDF, images, office docs, audio
- Why deferred:
  - strong long-term fit
  - unnecessary abstraction for the first OCR-first MVP
- Decision: `Phase 2`

### 9. `opendatalab/MinerU`

- Role: complex document to Markdown/JSON
- Use later:
  - image-heavy reports
  - layout-rich market notes
- Why deferred:
  - useful, but not needed before PaddleOCR pipeline stabilizes
- Decision: `Phase 2`

### 10. `datalab-to/marker`

- Role: PDF to Markdown/JSON
- Use later:
  - scanned reports, PDF research docs
- Why deferred:
  - not the highest-priority input format right now
- Decision: `Phase 2`

### 11. `datajuicer/data-juicer`

- Role: dataset cleaning, filtering, deduplication
- Use later:
  - training corpus preparation
  - OCR/ASR artifact filtering
- Why deferred:
  - only becomes valuable after enough data is accumulated
- Decision: `Phase 2`

### 12. `argilla-io/argilla`

- Role: dataset curation and collaboration
- Use later:
  - model training dataset operations
  - structured review workflows
- Why deferred:
  - Label Studio covers the immediate review need
- Decision: `Phase 2`

## Not selected for the MVP path

### 13. `AI4Finance-Foundation/FinGPT`

- Reason:
  - good reference for financial NLP tasks
  - not the right application backbone for this project
- Decision: `Reference only`

### 14. `deepset-ai/haystack`

- Reason:
  - useful for future retrieval and Q&A
  - not needed before the event store exists
- Decision: `Reference only for Phase 2`

### 15. `run-llama/llama_index`

- Reason:
  - similar to Haystack
  - useful later for retrieval over documents and events
- Decision: `Reference only for Phase 2`

### 16. `langgenius/dify`

- Reason:
  - useful as an app shell
  - does not solve ingestion, extraction, annotation, or backtesting
- Decision: `Not part of MVP`

### 17. `polakowo/vectorbt`

- Reason:
  - strong for generic quant experiments
  - current problem is event-driven research, not indicator-first backtesting
- Decision: `Not part of MVP`

### 18. `kernc/backtesting.py`

- Reason:
  - lightweight, but not aligned with the event-study style engine needed first
- Decision: `Not part of MVP`

## Final MVP stack

- Ingestion: `BBDown` + `yt-dlp`
- OCR: `PaddleOCR`
- Audio transcription: `WhisperX` + `pyannote-audio`
- Review and labeling: `Label Studio`
- Storage: local filesystem + SQLite/Postgres
- Backtesting: custom event backtester

## Implementation implication

The initial system should be built around canonical schemas and process boundaries, not around a single framework.

That means:

- OCR output must be normalized into our own document schema
- ASR output must be normalized into our own segment schema
- review output must be normalized into our own event schema
- backtesting should consume the event schema, not tool-specific output
