# Kaggle: Predicting Game Scores FIFA 2022 World Cup

Source: https://www.kaggle.com/code/tiagosalvador/predicting-game-scores-fifa-2022-world-cup
Author: Tiago Salvador
Platform type: Kaggle notebook
Language: Python
Verified on: 2026-05-27

## Project Positioning

This is one of the best learning examples among the searched Kaggle projects because it models the score itself, not only a binary winner label.

The project predicts FIFA World Cup match scores using Poisson distributions, then uses those score distributions to simulate group stages, knockout stages, and champion probabilities.

## Problem Definition

The project tries to answer three related questions:

1. What is the most likely score for a match between two national teams?
2. What is the win, draw, and loss probability implied by those score distributions?
3. If the whole World Cup is simulated many times, which teams most often reach each tournament stage?

The target is not a single deterministic champion. The better output is a distribution over possible tournament outcomes.

## Data Inputs

The project uses:

- International football results from 1872 onward.
- FIFA World Ranking data from 1992 onward.
- 2018 and 2022 World Cup group and fixture structure.
- Wikipedia-derived tournament group information.

The notebook explicitly notes that very old matches are not always relevant. It narrows the effective training window because national teams change after each World Cup cycle.

## Core Modeling Principle

The main statistical assumption is:

```text
goals_scored_by_team ~ Poisson(lambda_team)
```

For a given match, the model estimates expected goals for both teams. Once each side has a Poisson expected-goal parameter, the model can enumerate or sample possible scorelines.

Example concept:

```text
P(team A scores x and team B scores y)
= PoissonPMF(x, lambda_A) * PoissonPMF(y, lambda_B)
```

Then:

- if `x > y`, team A wins;
- if `x == y`, draw;
- if `x < y`, team B wins.

## Model Variants

The notebook compares two main approaches.

### Goal-Based Poisson Model

This version estimates team attack and defense strength from historical goals:

- home attacking strength,
- away attacking strength,
- home defensive strength,
- away defensive strength.

Neutral-field games are used carefully because many international matches are not true home-away league matches.

### FIFA-Rank-Based Poisson Model

This version estimates expected goals from FIFA ranking difference.

The notebook finds that the rank-based version performs better than a pure goal-statistics version in some cases. The reason is practical: raw goal statistics can overrate teams that dominate weaker confederation opponents.

## Implementation Workflow

The implementation can be understood as five layers.

### 1. Data Preparation

The notebook loads match result data and ranking data, standardizes team names, and filters to relevant tournament periods.

Important implementation concern:

- Team-name alignment is not trivial.
- FIFA rankings must be joined by date or nearest available ranking period.
- Old matches should not be weighted equally with recent matches.

### 2. Forecaster Interface

The notebook defines a base class pattern where each forecasting model implements:

```python
predict_game(team1, team2, n_sim)
```

This is a useful abstraction. It allows the rest of the tournament simulator to ignore whether the underlying model is Poisson-by-goals, Poisson-by-rank, or another model.

### 3. Match Simulation

For each match:

- draw many score samples,
- aggregate score frequencies,
- compute most likely score,
- compute win/draw/loss probabilities.

### 4. Group Stage Simulation

For each group:

- simulate all group matches,
- assign points,
- rank teams by simulated group outcomes,
- compute probability of each team finishing in each position.

### 5. Knockout Simulation

For knockout matches:

- simulate until there is a winner,
- advance winners through bracket,
- repeat tournament simulations many times.

## How To Use This Project

Use it as a reference notebook rather than a plug-and-play package.

Suggested workflow:

1. Open the Kaggle notebook.
2. Run all cells with the original Kaggle datasets attached.
3. Inspect the `BaseForecaster`, `PoissonGoals`, and `PoissonFifaRank` classes.
4. Start by changing only the training time window, for example using only matches after the previous World Cup.
5. Compare model performance on 2018 before predicting 2022 or 2026.
6. Add your own features only after the baseline score model is reproducible.

## How To Adapt It For 2026

To adapt the idea for 2026:

1. Replace tournament fixtures with the 2026 expanded 48-team structure.
2. Update international results through the latest available pre-tournament date.
3. Update FIFA ranking data.
4. Decide how to handle unknown playoff teams.
5. Run simulations under multiple assumptions instead of producing one champion.

Recommended outputs:

- most likely score per match,
- win/draw/loss probability,
- group qualification probability,
- quarterfinal/semifinal/final probability,
- champion probability.

## Quality Assessment

Strengths:

- Uses a transparent score-generating model.
- Separates model logic from tournament simulation.
- Includes backtesting on 2018 before applying to 2022.
- Explains why raw goal statistics can mislead.

Weaknesses:

- Poisson independence is a simplification. Real scores are correlated.
- FIFA rank is itself an imperfect and lagging strength signal.
- Knockout tie-breaking and penalty shootouts are simplified.
- Player availability, injuries, squad selection, fatigue, and tactical matchups are not modeled.

## What Finer Can Learn

The most reusable idea is the separation between:

```text
match probability model -> tournament simulator -> scenario distribution
```

For investment-event systems, this maps well to:

```text
single-event probability -> path simulation -> portfolio outcome distribution
```

The project is valuable because it treats prediction as probabilistic scenario generation rather than a single confident label.

