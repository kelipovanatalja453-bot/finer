# GitHub: FIFA-2018-World-cup-predictions

Source: https://github.com/itsmuriuki/FIFA-2018-World-cup-predictions
Author: itsmuriuki
Repository stars at verification: 166
Primary language: Jupyter Notebook
Verified on: 2026-05-27

## Project Positioning

This is a classic beginner project for FIFA World Cup prediction with Logistic Regression. It is widely starred because it is simple and easy to follow.

It should be treated as an introductory machine learning notebook, not a high-accuracy forecasting system.

## Problem Definition

The project predicts:

- individual match outcomes,
- 2018 World Cup group matches,
- knockout outcomes,
- likely tournament winner.

The README states that the model predicted Brazil as the likely winner.

## Data Inputs

The project uses two main Kaggle datasets:

- historical match results since 1930,
- World Cup 2018 dataset.

It also uses:

- April 2018 FIFA rankings,
- 2018 group-stage fixture data.

## Feature Design

The notebook creates:

- winning team label,
- goal difference,
- match year,
- participating team filters,
- one-hot encoded team names,
- FIFA ranking-based fixture ordering.

The model represents teams as categorical dummy variables. This is easy to implement but weak for generalization because it learns team identities more than durable team-strength features.

## Modeling Principle

The model uses scikit-learn Logistic Regression.

The target label is encoded from match result:

```text
home team wins / draw / away team wins
```

The notebook reports:

```text
training accuracy: about 57.3 percent
test accuracy: about 55.1 percent
```

These numbers are realistic and show the difficulty of the task.

## Implementation Workflow

### 1. Load Historical Results

The notebook loads historical international or World Cup match results.

### 2. Create Winner Label

For each match:

- if home score is greater, winner is home team,
- if away score is greater, winner is away team,
- otherwise winner is draw.

### 3. Filter To World Cup Teams

The dataset is narrowed to teams participating in the 2018 World Cup.

### 4. One-Hot Encode Teams

Categorical team columns are converted into numeric dummy columns using pandas.

### 5. Train Logistic Regression

The dataset is split into train and test sets. Logistic Regression is fitted and scored.

### 6. Predict Fixtures

The model is applied to 2018 fixtures. For each match, the notebook prints winner probabilities and predicted winners.

### 7. Advance Knockout Rounds

Predicted winners are passed to the next manually defined round.

## How To Use This Project

Clone the repository:

```bash
git clone https://github.com/itsmuriuki/FIFA-2018-World-cup-predictions.git
cd FIFA-2018-World-cup-predictions
```

Open:

```text
Predicting Fifa 2018.ipynb
```

Install dependencies:

```bash
pip install pandas numpy matplotlib seaborn scikit-learn jupyter
```

Run all cells in order.

If you want to reuse it for another tournament:

1. Replace fixture data.
2. Replace FIFA ranking data.
3. Update participating teams.
4. Regenerate dummy columns.
5. Retrain the model.

## Quality Assessment

Strengths:

- Simple and readable.
- Good for learning pandas and scikit-learn.
- Reports realistic accuracy.
- Shows full match-to-bracket prediction flow.

Weaknesses:

- Feature representation is weak.
- One-hot team identity does not generalize well to future team strength changes.
- No probability calibration.
- No time-based validation.
- Knockout path is manually constructed.
- No Monte Carlo simulation.

## Recommended Use

Use it as a beginner baseline:

```text
historical results -> label creation -> one-hot teams -> Logistic Regression -> fixture prediction
```

Do not use it as the modeling foundation for a serious 2026 system. For that, use richer team-strength features and probabilistic simulation.

## What Finer Can Learn

The useful lesson is workflow clarity. Even a simple model should show:

- target construction,
- feature conversion,
- model training,
- evaluation,
- application to future fixtures.

The limitation is equally important: a clean notebook can still have weak modeling assumptions.

