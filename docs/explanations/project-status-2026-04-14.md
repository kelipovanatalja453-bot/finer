# Project Status Snapshot (2026-04-14)

## 1. Project identity

`finer` is positioned as an AI-native investment research pipeline that turns non-standard creator content into structured, backtestable investment events.

The intended end-to-end path is:

1. ingestion
2. multimodal parsing
3. cleaning and normalization
4. event extraction
5. human review / alignment
6. backtesting

The documentation still presents `trader韭` as the original Phase 1 anchor creator, but the actual data folder already contains broader experiments around `9you`, `maodaren`, and report-style datasets.

## 2. What is already real

### 2.1 Python package skeleton exists

The Python package under `src/finer/` already has:

- CLI entrypoints in `src/finer/cli.py`
- storage bootstrap logic in `src/finer/paths.py`
- content manifest registration in `src/finer/manifests.py`
- creator / Feishu config loading in `src/finer/config.py`
- schema definitions in `src/finer/schemas/`
- a Feishu polling / classification / archive / NotebookLM sync orchestrator in `src/finer/ingestion/`

### 2.2 Feishu ingestion is the most mature implemented lane

The most developed code path today is:

Feishu chat polling -> attachment download -> rule or AI classification -> archive to canonical path -> manifest writing -> optional NotebookLM sync -> receipt sending

This is more mature than the README suggests.

### 2.3 There is already real experimental data

Current `data/` highlights:

- `data/L0_ingest/`: 371 files
- `data/L3_aligned/manifests/`: 60 manifest JSON files
- `data/L3_aligned/transcripts/`: 61 transcript / vision markdown files
- `data/L4_parsed/candidate_events/`: 1 candidate event file

Manifest distribution currently sampled from:

- `9you`: 44
- `maodaren`: 16

There are also aggregated research/report JSON assets such as:

- `data/comprehensive_reports_db.json`
- `data/comprehensive_semantic_db.json`
- `data/full_2025_harvest.json`

This means the repository is already serving as both:

- a product codebase
- an experiment and dataset workspace

## 3. What is still mostly scaffold or prototype

### 3.1 Core research pipeline is not fully wired

`dry-run` still returns these stages as not implemented:

- OCR
- ASR
- extraction
- backtest

The code and docs both describe these stages, but the true end-to-end creator-event pipeline is not yet complete.

### 3.2 Perception layer is partially mocked

`src/finer/services/perception.py` and `src/finer/services/llm.py` already define a "perception" abstraction, but the current LLM/VLM call path is mocked rather than production-grade.

### 3.3 Frontend dashboard is mostly concept UI

`src/finer_dashboard/` provides a polished prototype UI, but several panels are still static or loosely connected:

- hard-coded tier mapping (`L0` to `L8`) does not match the Python-side canonical storage layout
- inspector and annotation studio contain mocked content
- the Next.js README is mostly stock scaffold text

The frontend currently behaves more like a visual operating model for the future system than a faithful view of the backend state.

## 4. Important inconsistencies to remember

Several parts of the repository describe different generations of the project:

### 4.1 Version and maturity mismatch

- `README.md` shows version `0.2.0`
- `pyproject.toml` shows version `0.1.0`

### 4.2 Data layout mismatch

Python-side storage helper expects:

- `data/raw/...`
- `data/processed/...`
- `data/backtests`

Frontend API expects:

- `data/L0_ingest`
- `data/L1_inbox`
- `data/L2_standardized`
- ...
- `data/L8_metrics`

The repo therefore contains two parallel mental models of the pipeline.

### 4.3 Review stack changed in docs

Earlier docs / configs still reference `Label Studio`, but the newer architecture doc strongly recommends moving toward `Argilla` for SFT + RLHF.

### 4.4 Planned parser stack changed in docs

Older MVP docs emphasize `PaddleOCR` and `WhisperX`.
Newer architecture notes increasingly favor cloud VLM parsing and stronger action-chain extraction logic.

### 4.5 Schema ambition exceeds current outputs

The event schema now includes `TradingAction` and action chains, but current candidate event outputs are still relatively shallow:

- repeated entries exist
- directions remain simple
- trigger conditions and multi-step actions are not yet really realized

## 5. Stable product direction

Despite the inconsistencies, the project direction is coherent:

### 5.1 Core thesis

The system is trying to transform noisy creator or research content into:

- normalized content records
- standardized segments
- structured investment events
- later reviewable and backtestable actions

### 5.2 High-value differentiator

The strongest differentiator is no longer generic event extraction alone.

The real long-term bet is:

- extracting multi-step trading intent
- preserving trigger conditions
- collecting preference data from reviewers
- using that loop for domain alignment / RLHF

### 5.3 Human-in-the-loop remains central

The repository consistently treats human review as part of the product, not just a temporary debugging stage.

## 6. Current practical status

As of 2026-04-14, the repository is best understood as:

- a strong architecture and product blueprint
- a partially implemented ingestion and normalization system
- a growing experiment dataset
- a prototype UI for future operations
- an incomplete but directionally clear research-event platform

## 7. Best next steps

If continuing development, the highest-leverage next steps are:

1. unify the storage contract between Python backend and Next.js frontend
2. choose one canonical pipeline model and retire the duplicate terminology
3. finish one real end-to-end lane on a single creator or content type
4. improve event extraction quality before expanding evaluation complexity
5. decide whether review remains in Label Studio or fully moves to Argilla
6. separate stable product code from ad hoc research datasets and report experiments

## 8. Domain memory worth keeping

The file `词语个人理解（持续更新）.xlsx` is an important project asset.

Its current role is a user-maintained slang dictionary that maps KOL expressions to canonical meanings, for example:

- `LABUBU / 娃娃` -> `泡泡玛特`
- `爸爸 / 88 / baba / 马爸爸` -> `阿里巴巴`
- `鹅 / 企鹅 / 绿泡泡` -> `腾讯`
- `爱国` -> `中国国债`

This dictionary should be treated as a first-layer semantic alignment resource for later parsing and extraction.
