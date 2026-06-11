# GitHub: FIFA-World-Cup-Prediction

Source: https://github.com/mrthlinh/FIFA-World-Cup-Prediction
Author: mrthlinh
Repository stars at verification: 60
Primary language: Jupyter Notebook and Python
Verified on: 2026-05-27

## Project Positioning

This is the most research-report-like GitHub project in the set. It is valuable because it documents feature groups, experiments, metrics, and conclusions in a full report rather than only publishing a notebook.

The project predicts international football match results and applies the models to FIFA World Cup 2018.

## Problem Definition

The project studies two prediction tasks:

1. Match outcome classification:

```text
Win / Draw / Lose
```

2. Goal difference classification:

```text
goal difference bucket
```

It then applies trained models to the 2018 World Cup.

## Data Inputs

The project combines multiple sources:

- FIFA World Cup 2018 data,
- international match results,
- FIFA rankings,
- betting odds,
- squad strength from SoFIFA,
- squad strength from FIFA Index.

The training period focuses mostly on matches from 2000 to 2018, with some experiments after 2005 because betting odds are not available earlier.

## Feature Design

The project defines four main feature groups.

### 1. Head-to-Head History

Examples:

- head-to-head win difference,
- number of draws between the two teams.

### 2. Recent Form

Recent form is based on the last 10 matches:

- goal-for difference,
- goal-against difference,
- win-count difference,
- draw-count difference.

### 3. Betting Odds

Examples:

- win odds difference,
- draw odds.

The report finds that betting odds are strong features for winner prediction but weak for draw detection.

### 4. Squad Strength

Examples:

- FIFA rank difference,
- overall strength difference,
- attack strength difference,
- midfield strength difference,
- defense strength difference,
- prestige difference,
- age of starting players,
- build-up play speed,
- chance creation,
- defensive pressure.

## Modeling Principle

The project compares simple baselines with multiple machine learning algorithms:

- odd-based decision tree,
- head-to-head and form decision tree,
- squad-strength decision tree,
- Logistic Regression,
- Random Forest,
- Gradient Boosting Tree,
- AdaBoost,
- Neural Network,
- LightGBM.

This is an important project because it does not assume that more complex models win. It explicitly finds that simple odds-based and strength-based trees are competitive.

## Evaluation Results

The report gives structured results.

### Experiment 1: Win / Draw / Lose

Best results are around 59 percent 10-fold cross-validation accuracy.

Selected results:

- Logistic Regression: 59.37 percent accuracy.
- Gradient Boosting Tree: 58.60 percent accuracy.
- Neural Net: 58.96 percent accuracy.
- LightGBM: 59.49 percent accuracy.
- Odd-based Decision Tree: 59.28 percent accuracy.

The report emphasizes that most classifiers struggle to predict draws.

### Experiment 2: Goal Difference

The best simple model is a squad-strength-based decision tree at about 31.64 percent 10-fold accuracy.

This low score is realistic. Exact goal-difference style prediction is much harder than winner prediction.

### Experiment 3: World Cup 2018 Application

Selected results:

- Logistic Regression: 57.81 percent Win/Draw/Lose accuracy.
- Random Forest: 56.25 percent Win/Draw/Lose accuracy.
- LightGBM: 56.25 percent Win/Draw/Lose accuracy.
- Goal Difference accuracy is around 20 to 33 percent depending on the model.

## Implementation Workflow

### 1. Data Crawling and Assembly

The repository includes data and web-crawler-related directories. It assembles match, odds, ranking, and squad datasets.

### 2. Feature Engineering

The project creates difference features:

```text
feature_diff = team_1_feature - team_2_feature
```

This makes the model focus on relative strength rather than absolute raw values.

### 3. Exploratory Data Analysis

The report includes correlation analysis and hypothesis tests. It specifically investigates whether goal-for and win-count differences matter.

### 4. Modeling Experiments

The project runs three experiments:

- outcome classification,
- goal-difference classification,
- World Cup 2018 application.

### 5. Evaluation

Metrics include:

- 10-fold cross-validation accuracy,
- F1 micro average,
- area under ROC,
- confusion matrix.

## How To Use This Project

Clone the repository:

```bash
git clone https://github.com/mrthlinh/FIFA-World-Cup-Prediction.git
cd FIFA-World-Cup-Prediction
```

The README lists three executable experiments:

```bash
python experiment1-W-D-L.py
python experiment2-GoalDiff.py
python experiment3-WorldCup.py
```

Before running:

1. Inspect the `data/` directory.
2. Confirm local Python package versions.
3. Install scikit-learn, pandas, numpy, matplotlib, and LightGBM if needed.
4. Read `report.md` first. It explains assumptions better than the scripts alone.

## How To Adapt It

For a new World Cup:

1. Rebuild match results through the latest available date.
2. Refresh ranking and squad strength data.
3. Rebuild odds features only if you are willing to use market-implied information.
4. Split validation by time, not random rows.
5. Re-run the feature importance and draw-error analysis.

## Quality Assessment

Strengths:

- Strong documentation.
- Multiple feature groups.
- Multiple models.
- Honest metrics.
- Clear conclusion that complexity does not automatically win.
- Explicit analysis of draw prediction weakness.

Weaknesses:

- Betting odds are powerful but can be considered market leakage depending on the use case.
- Some data sources are old or may require unavailable crawling.
- Exact reproducibility may depend on historical scraped files.
- The project is focused on 2018 and needs data refresh for current use.

## What Finer Can Learn

This project is the best reminder that a useful model report should compare:

```text
simple baseline vs complex model
```

For Finer, the equivalent discipline is to benchmark LLM-heavy extraction or prediction against rule-based and market-implied baselines before claiming improvement.

