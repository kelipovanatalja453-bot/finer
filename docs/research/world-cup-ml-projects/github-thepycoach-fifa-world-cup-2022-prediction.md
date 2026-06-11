# GitHub: fifa-world-cup-2022-prediction

Source: https://github.com/thepycoach/fifa-world-cup-2022-prediction
Author: thepycoach
Repository stars at verification: 198
Primary language: Jupyter Notebook and Python
Verified on: 2026-05-27

## Project Positioning

This is a popular beginner-friendly World Cup prediction project. It is not a machine learning classifier in the strict sense. It is a statistical Poisson baseline that predicts scores using historical World Cup goal averages.

Its main value is simplicity and reproducibility.

## Problem Definition

The project predicts the Qatar 2022 World Cup bracket:

- group-stage expected points,
- group winners and runners-up,
- knockout winners,
- final winner.

The project predicted Brazil as champion.

## Data Inputs

The repository includes scripts and notebooks to collect and clean:

- historical World Cup match results,
- 2022 fixtures,
- group-stage tables.

Important files:

- `1.get_results_and_fixture.py`,
- `1.get_missing_data.py`,
- `1.get_tables_groupstage.ipynb`,
- `2.data_cleaning.ipynb`,
- `3.data_visualization_best_lineup.ipynb`,
- `4.predict_world_cup.ipynb`,
- `data/`.

## Core Modeling Principle

The project uses average goals scored and conceded by team.

For each team:

```text
average_goals_scored
average_goals_conceded
```

For a match:

```text
lambda_home = home_goals_scored_avg * away_goals_conceded_avg
lambda_away = away_goals_scored_avg * home_goals_conceded_avg
```

Then it uses Poisson probability mass functions over scorelines from 0 to 10 goals:

```python
p = poisson.pmf(x, lambda_home) * poisson.pmf(y, lambda_away)
```

The project sums probabilities into:

- home win probability,
- draw probability,
- away win probability.

Expected points are computed as:

```text
points_home = 3 * P(home win) + P(draw)
points_away = 3 * P(away win) + P(draw)
```

## Implementation Workflow

### 1. Scrape or Load World Cup Data

The first scripts collect historical World Cup match results and the 2022 fixture.

### 2. Clean Data

The cleaning notebook standardizes columns:

- home team,
- away team,
- home goals,
- away goals,
- year.

### 3. Compute Team Strength

`4.predict_world_cup.ipynb` creates a `df_team_strength` table by averaging goals scored and conceded for each team.

### 4. Predict Group Points

For every group fixture, expected points are calculated using the Poisson-derived win/draw/loss probabilities.

### 5. Advance Knockout Bracket

The top two teams in each group are inserted into the knockout bracket.

### 6. Predict Knockout Winners

For each knockout match, the team with higher expected points advances.

## How To Use This Project

Clone the repository:

```bash
git clone https://github.com/thepycoach/fifa-world-cup-2022-prediction.git
cd fifa-world-cup-2022-prediction
```

Run notebooks in order:

```text
1.get_tables_groupstage.ipynb
2.data_cleaning.ipynb
4.predict_world_cup.ipynb
```

If using scripts:

```bash
python 1.get_results_and_fixture.py
python 1.get_missing_data.py
```

Install typical dependencies:

```bash
pip install pandas scipy beautifulsoup4 lxml
```

The core prediction is in `4.predict_world_cup.ipynb`. Start there if clean CSV files are already present.

## How To Adapt It

For 2026:

1. Replace fixture data with 2026 fixture data.
2. Update historical match results.
3. Decide whether to use all World Cup history or only recent editions.
4. Add current team strength signals such as FIFA rankings or ELO.
5. Replace deterministic knockout advancement with Monte Carlo sampling.

## Quality Assessment

Strengths:

- Very simple and readable.
- Good baseline for beginners.
- Easy to run and explain.
- Uses score probabilities instead of direct champion guessing.

Weaknesses:

- Uses only historical World Cup average goals.
- Does not consider current squad quality.
- Does not consider FIFA rankings, ELO, injuries, form, or confederation strength.
- Knockout logic is deterministic once expected points are computed.
- Team history can overrate historically strong teams and underrate improving teams.

## Recommended Use

Use this as the first baseline in any World Cup prediction project.

A proper project should be able to beat or at least explain differences from this baseline.

## What Finer Can Learn

This project shows the value of a minimal transparent baseline.

Before building complex models, define a baseline that can be written in one notebook:

```text
simple historical statistic -> probability -> scenario result
```

If a complex model cannot beat this, the extra complexity is not justified.

