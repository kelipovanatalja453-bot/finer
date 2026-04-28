# Label Studio Event Labeling Spec

## Purpose

Review candidate investment events extracted from creator content.

## Required reviewer decisions

For each candidate event, the reviewer must confirm or correct:

- market
- sector
- direction
- horizon
- tradeable flag
- proxy symbol

## Direction labels

- `bullish`
- `bearish`
- `neutral`
- `watchlist`
- `risk_warning`

## Horizon labels

- `intraday`
- `daily`
- `weekly`
- `swing`
- `longer_term`

## Review rules

- reject segments that are only background context without a directional implication
- prefer sector/theme labels over stock labels when the content is broad
- if there is no clear trade proxy, set `tradeable_flag=false`
- if the claim is conditional, keep the condition in `rationale`
