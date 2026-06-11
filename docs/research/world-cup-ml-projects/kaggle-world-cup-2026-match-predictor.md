# Kaggle: World Cup 2026 Match Predictor

Source: https://www.kaggle.com/code/sarazahran1/world-cup-2026-match-predictor
Author: Sara Zahran
Platform type: Kaggle notebook
Language: Python
Verified on: 2026-05-27

## Project Positioning

This is a large 2026-oriented Kaggle notebook. It combines exploratory analysis, ELO-style team ratings, machine learning classification, group-stage simulation, knockout simulation, Monte Carlo simulation, and visual reporting.

It is useful as an end-to-end notebook design reference. It should not be treated as a reliable betting or forecasting model without additional validation.

## Problem Definition

The notebook aims to predict:

- international match outcomes,
- 2026 World Cup group-stage results,
- knockout-stage winners,
- final appearance probabilities,
- semifinal appearance probabilities,
- likely champion candidates.

The intended classification target is typically:

```text
home win / draw / away win
```

The tournament-level result is produced by simulating match outcomes across the World Cup bracket.

## Data Inputs

The notebook references multiple football data surfaces:

- international football match results,
- World Cup historical match data,
- World Cup player and team data,
- team ELO ratings,
- 2026 group-stage fixture assumptions.

It also creates or fills missing team ratings in the notebook. In some places, missing ratings are replaced by group averages or default values such as 1600.

## Feature Design

The project uses or describes features such as:

- home team ELO,
- away team ELO,
- ELO difference,
- tournament context,
- historical performance,
- team strength category,
- group strength,
- match location or neutral-field context.

The key feature is ELO difference:

```text
elo_diff = home_elo - away_elo
```

In a standard ELO framework, expected win probability can be approximated as:

```text
P(home win) = 1 / (1 + 10 ** ((away_elo - home_elo) / 400))
```

The notebook uses this kind of rating-difference logic for simulation.

## Modeling Principle

The project has two modeling layers.

### ELO-Based Probability Layer

Team ratings are converted into match win probabilities. This creates a simple and interpretable foundation:

- stronger team has higher win probability,
- rating difference controls probability gap,
- probabilities can be sampled repeatedly for simulation.

### Machine Learning Layer

The notebook imports and uses scikit-learn models such as:

- Random Forest,
- Gradient Boosting,
- Logistic Regression,
- train-test split,
- classification report,
- confusion matrix.

It describes a broader model comparison including XGBoost and ensemble methods.

## Implementation Workflow

### 1. Inspect Data Structure

The notebook first inspects column names and available World Cup datasets. This is necessary because football datasets often use inconsistent team and score column naming.

### 2. Normalize Match Records

It standardizes home team, away team, home score, away score, and tournament labels into a common match table.

### 3. Build Team Ratings

The notebook builds a `team_ratings` dictionary. If a team lacks an ELO value, it uses a group average or default rating.

### 4. Simulate Group Stage

For each group match, it simulates outcomes and accumulates:

- points,
- wins,
- draws,
- losses,
- goals for,
- goals against,
- goal difference.

### 5. Simulate Knockout Stage

The knockout stage advances winners based on computed probabilities. Strong teams such as Brazil, France, Germany, Spain, and Belgium appear repeatedly in the generated scenarios.

### 6. Train ML Model

The ML section trains a model to classify match outcomes from engineered features. The notebook output showed very high training and testing accuracy in one section, which should be treated as a warning sign rather than proof of quality.

### 7. Monte Carlo Tournament Simulation

The notebook runs repeated tournament simulations and reports:

- final appearance probabilities,
- semifinal appearance probabilities,
- group winner probabilities,
- likely champion.

## How To Use This Project

Use it in Kaggle as a notebook:

1. Open the source notebook.
2. Attach the same input datasets listed in the notebook.
3. Run the data inspection cells first.
4. Confirm that team columns and score columns were correctly detected.
5. Run the rating construction cells.
6. Run group-stage and knockout simulation.
7. Only then run the machine learning section.

For serious use, do not accept the notebook's default predictions directly. Add these checks:

- verify team-name mappings,
- replace default ELO values with real current ratings,
- use time-based train-test split,
- remove any post-tournament features when predicting future tournaments,
- calibrate probabilities.

## Quality Assessment

Strengths:

- Complete notebook flow from data loading to report.
- Strong visualization and presentation layer.
- Useful demonstration of tournament simulation mechanics.
- Good for learning how to structure an analytics notebook.

Weaknesses:

- Some missing ratings are imputed with rough defaults.
- Random or placeholder-looking values appear in parts of the notebook.
- One output shows perfect training and testing accuracy, which is a serious overfitting or leakage warning.
- The champion simulation output had inconsistent signs in one run, including no champion recorded in simulations in one section while later reporting Brazil.

## Recommended Use

Use this as a product-design and notebook-structure reference:

- dashboard layout,
- tournament report sections,
- simulation outputs,
- visual communication.

Do not use it as the strongest modeling reference. For modeling discipline, prefer the Poisson and validated XGBoost projects in this directory.

## What Finer Can Learn

The project shows how to turn analytical predictions into a user-facing report:

- ranked team strength,
- group difficulty,
- stage probabilities,
- narrative summary.

For Finer, this is useful for designing explainable result pages where a model produces not just a label, but also scenario trees, confidence bands, and ranked alternatives.

