# Kaggle: World Cup 2022 Simulator

Source: https://www.kaggle.com/code/dropries/world-cup-2022-simulator
Author: Dorian Chauvin
Platform type: Kaggle notebook
Language: R
Verified on: 2026-05-27

## Project Positioning

This is a high-quality R notebook for probabilistic World Cup simulation. It is more careful than many simple winner-prediction notebooks because it uses cross-validation by World Cup edition and reports a tournament simulation distribution instead of only a fixed bracket.

## Problem Definition

The project predicts 2022 World Cup outcomes by:

- training a match outcome model,
- predicting group-stage win/draw/loss probabilities,
- sampling match results from predicted probabilities,
- simulating knockout rounds,
- repeating the whole tournament many times.

The model target is:

```text
Win / Draw / Lose
```

from the perspective of one team in a match.

## Data Inputs

The author intentionally restricts training data:

- only World Cup matches,
- only matches after 2006,
- FIFA team/player score features.

This creates a small dataset of about 256 matches, but it reduces competition mismatch. The author explicitly acknowledges that the small sample limits reliability.

## Feature Design

The feature set includes:

- host indicator,
- confederation,
- FIFA ranking,
- total FIFA points,
- goalkeeper score,
- defense score,
- midfield score,
- offense score,
- previous World Cup performance indicators.

Feature examples from the notebook include:

```text
home_team_goalkeeper_score
away_team_goalkeeper_score
home_team_mean_defense_score
away_team_mean_defense_score
home_team_mean_offense_score
away_team_mean_offense_score
home_team_mean_midfield_score
away_team_mean_midfield_score
```

## Modeling Principle

The model is a penalized multinomial regression trained with cross-validation.

Multinomial regression is appropriate because the target has three classes:

```text
Win / Draw / Lose
```

The key implementation choice is to use predicted class probabilities, not just the most likely class.

For a match:

```text
P(Win), P(Draw), P(Lose)
```

are used to sample outcomes. This lets the same tournament produce different plausible paths across repeated simulations.

## Validation Method

The notebook uses cross-validation folds defined by World Cup edition. This is better than random row splitting because tournament matches from the same edition are not independent.

The metric is OvRauc, a one-versus-rest AUC average across the three classes.

The notebook reports final OvRauc around 66%.

## Implementation Workflow

### 1. Load and Filter World Cup Matches

The notebook starts from historical World Cup match data and team score features.

### 2. Create Modeling Table

It transforms each match into a feature vector and a three-class result label.

### 3. Train Penalized Multinomial Model

The R `caret` workflow is used with cross-validation. Candidate feature combinations are selected using forward selection.

### 4. Predict Probabilities

For a future fixture, the model outputs probabilities for win, draw, and loss.

### 5. Simulate One Tournament

The simulator applies group rules, advances teams, then simulates knockout rounds.

### 6. Run 1000 Tournaments

Repeated simulations estimate probabilities of reaching each stage.

## How To Use This Project

Use the Kaggle notebook directly if you are comfortable with R:

1. Open the notebook in Kaggle.
2. Run package installation and library cells.
3. Re-run data preparation.
4. Inspect the feature list selected by the forward-selection step.
5. Run the model training section.
6. Run one simulation first.
7. Run 1000 simulations only after confirming the single simulation works.

To adapt it:

- replace the 2022 fixture with 2026 fixtures,
- update FIFA/player score features,
- expand or revise cross-validation folds for the 48-team format,
- report stage probabilities instead of only final winners.

## Quality Assessment

Strengths:

- Honest about small sample size.
- Uses World Cup-edition cross-validation.
- Uses probabilities for simulation.
- Separates group-stage draw handling from knockout win-only handling.
- Includes stage reach probabilities.

Weaknesses:

- Only 256 World Cup matches after filtering, so model variance is high.
- FIFA game player ratings are a proxy, not official football performance.
- Team strength features may lag real squad form.
- The model is tournament-specific and may not generalize to qualifiers or friendlies.

## What Finer Can Learn

This project is a strong example of scenario simulation after probabilistic classification.

The key reusable idea is:

```text
classification probability is an input to simulation, not the final product
```

For any event pipeline, this means downstream systems should consume calibrated probability distributions, not just labels.

