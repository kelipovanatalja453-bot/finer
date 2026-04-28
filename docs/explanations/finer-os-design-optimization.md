# Finer OS Design Optimization

## 1. Design diagnosis

The current `Finer OS` frontend already has a strong visual instinct, but it is still mixing three different products into one screen:

1. a pipeline control surface
2. an annotation workstation
3. a research asset browser

That creates a polished interface, but not yet a trustworthy operating system.

The biggest design issues today are:

- navigation is organized around `L0-L8` internal tiers instead of real user tasks
- the frontend data model does not match the backend storage contract
- the main board, inspector, and annotation studio still behave like separate concept demos
- the interface is visually refined, but not yet evidence-first
- the user cannot quickly answer the most important operational questions:
  - what just arrived?
  - what failed?
  - what needs human judgment now?
  - what became a tradable event?
  - what produced measurable alpha?

## 2. Product framing

`Finer OS` should not present itself as a generic AI dashboard.

It should feel like:

- an editorial-grade research operations terminal
- a human-in-the-loop evidence lab
- a trading-intent calibration surface

The memorable idea should be:

`Every claim must stay attached to evidence, workflow state, and eventual outcome.`

That means the UI should be optimized around traceability, not just beautiful panels.

## 3. Recommended information architecture

Replace tier-first navigation with workflow-first navigation.

### 3.1 Primary navigation

Use these top-level areas:

1. `Intake`
2. `Parsing`
3. `Extraction`
4. `Review`
5. `Backtest`
6. `Library`
7. `System`

### 3.2 Where the old tiers go

Do not delete the medallion-style `L0-L8` model.
Demote it from primary navigation into a secondary pipeline-state language:

- as status chips
- as stage badges
- as filters in queue views
- as a compact provenance timeline on each asset

This keeps the internal pipeline vocabulary without forcing users to think in storage tiers.

## 4. Canonical object model for the UI

The interface should be built around user-facing objects, not folders.

Recommended canonical objects:

### 4.1 `Source Asset`

Represents a raw file or imported content item.

Fields:

- source id
- creator
- source platform
- modality
- publish time
- ingestion status

### 4.2 `Manifest`

Represents normalization and routing metadata.

Fields:

- content id
- canonical location
- classification confidence
- archive lineage

### 4.3 `Evidence Bundle`

Represents all parseable outputs tied to a source item.

Fields:

- transcript
- OCR blocks
- summaries
- slang tags
- structural context

### 4.4 `Event Candidate Set`

Represents extraction output from one evidence bundle.

Fields:

- extracted entities
- action chains
- rationale
- confidence
- duplicate flags
- review state

### 4.5 `Review Decision`

Represents human intervention.

Fields:

- accepted / corrected / rejected
- changed fields
- reviewer confidence
- ambiguity type

### 4.6 `Backtest Result`

Represents evaluation tied back to the event.

Fields:

- proxy
- entry rule
- exit rule
- return windows
- benchmark delta
- failure reason if not backtestable

## 5. Core screen redesign

## 5.1 Intake

Goal:
show what entered the system and whether routing is trustworthy.

Layout:

- left: source queues by creator / channel
- center: intake stream with thumbnails, file type, timestamp, tags
- right: routing confidence, manifest preview, chat context

Key actions:

- reclassify
- merge duplicates
- attach creator
- attach content type
- send to parsing

## 5.2 Parsing

Goal:
inspect the machine-readable reconstruction of content.

Layout:

- left: parse job queue and filters
- center: split view with original asset and parsed output
- right: block metadata, slang hits, context summaries, parser warnings

Key actions:

- rerun OCR / VLM
- compare parser versions
- mark layout failure
- trim noise blocks

## 5.3 Extraction

Goal:
turn parsed evidence into structured event candidates.

Layout:

- left: candidate list grouped by source
- center: evidence-to-event workbench
- right: schema validation, confidence, duplicate and ambiguity warnings

Key actions:

- compare extraction versions
- collapse duplicates
- inspect action chains
- promote to review

## 5.4 Review

Goal:
make human judgment the center of gravity.

Layout:

- left: review queue by ambiguity type
- center: evidence with highlighted supporting spans
- right: editable event form and action chain editor

The current annotation studio should evolve into this screen.

The review UI should explicitly support two modes:

- `Field Correction`
- `Intent Disambiguation`

That distinction matters because these are different training signals.

## 5.5 Backtest

Goal:
show whether extracted ideas survive market reality.

Layout:

- left: runs and filters
- center: event card + outcome chart + benchmark comparison
- right: execution assumptions and proxy mapping

Key actions:

- rerun with different entry windows
- inspect proxy rule
- mark not tradeable
- export report

## 5.6 Library

Goal:
be the memory palace of the system.

This is where cross-creator and report datasets belong.

Views:

- creator view
- symbol / sector view
- theme clusters
- report corpus
- semantic search

This should absorb the current `comprehensive_*` and report JSON assets more cleanly.

## 6. Interaction principles

## 6.1 Evidence-first

Any extracted claim should always keep a visible path back to:

- source asset
- parsed block or segment
- review history
- backtest result

## 6.2 Queue-first, not file-first

The system should guide work through queues:

- `new`
- `needs routing`
- `parse failed`
- `needs review`
- `ready for backtest`
- `closed`

## 6.3 Confidence is useful only with explanation

Do not show naked confidence numbers without nearby reasons.

Every confidence display should be adjacent to:

- extraction basis
- missing fields
- conflicting interpretations
- schema warnings

## 6.4 Make failure states dignified

This product will regularly encounter:

- noisy images
- weak OCR
- ambiguous slang
- non-tradeable commentary

These should feel like first-class states, not exceptions.

## 7. Visual direction

Keep the current editorial / financial atmosphere, but sharpen it.

### 7.1 Recommended aesthetic

Design direction:

- editorial command desk
- ivory paper background
- carbon text
- restrained crimson as decision accent
- muted brass and teal for state signals
- dense but elegant metadata

The interface should feel closer to:

- a financial editor's desk
- a litigation evidence board
- a market operations terminal

and less like:

- a generic SaaS AI dashboard
- a dark quant console
- a neon cyberpunk agent UI

### 7.2 Typography

Recommended pairing:

- display / Chinese serif: `Noto Serif SC`
- UI sans: `IBM Plex Sans`
- numeric / code: `IBM Plex Mono`

This fits the product much better than the current default `Geist + Inter-ish` stack.

### 7.3 Color system

Use semantic tokens instead of ad hoc colors:

- `--accent-critical`
- `--accent-active`
- `--accent-candidate`
- `--surface-elevated`
- `--surface-muted`
- `--ink-primary`
- `--ink-secondary`
- `--grid-line`

Crimson should mean:

- active decision
- required human attention
- selected evidence

Do not let crimson become a universal highlight color for everything.

### 7.4 Motion

Use motion sparingly:

- queue transitions
- evidence panel expand
- stage transitions
- subtle card hover lift

Avoid decorative motion in the annotation flow.
Review work should feel precise, not playful.

## 8. Specific improvements to current components

## 8.1 Sidebar

Current problem:
the sidebar elevates internal layers above user tasks.

Optimization:

- top section: `Workbench`
- middle section: workflow navigation
- lower section: creator filters and saved views
- bottom: system health

Add a compact pipeline pulse widget instead of the current plugin fantasy layer.

## 8.2 Main board

Current problem:
it behaves like a file gallery even when the user needs operational judgment.

Optimization:

- support three modes:
  - queue
  - gallery
  - evidence table
- default to queue in operational surfaces
- reserve gallery for image-heavy research browsing

## 8.3 Inspector panel

Current problem:
mostly mocked and too generic.

Optimization:

Make it a provenance rail:

- source metadata
- pipeline stage history
- parser version
- extraction version
- reviewer decisions
- linked symbols / sectors

## 8.4 Annotation studio

Current problem:
beautiful but still too static and not schema-aware enough.

Optimization:

- editable action-chain rows
- explicit ambiguity badges
- evidence span linking
- changed-field highlighting
- version compare mode
- reviewer shortcut keys

## 8.5 Upload flow

Current problem:
upload currently targets tiers, which leaks implementation detail.

Optimization:

Replace `UPLOAD TO Lx` with:

- `Import Asset`
- `Add Research File`
- `Attach Evidence`

Then let backend routing decide the real stage placement.

## 9. MVP implementation order

To improve design without overbuilding, use this order:

1. unify backend and frontend pipeline vocabulary
2. redesign navigation around workflow states
3. convert inspector into provenance rail
4. convert annotation studio into a real review workstation
5. add queue views before adding more decorative screens
6. only then build advanced library and analytics views

## 10. What to avoid

Do not spend early energy on:

- plugin marketplaces
- multi-agent theater UIs
- abstract AI orchestration diagrams as product chrome
- overly dark terminal aesthetics
- heavy charting before event reliability improves

The product wins if it becomes the best place to:

- ingest messy investment content
- preserve evidence
- calibrate intent
- judge tradeability
- connect language to outcome
