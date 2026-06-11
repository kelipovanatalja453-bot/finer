# Kaggle: FIFA World Cup Prediction DNN TensorFlow

Source: https://www.kaggle.com/code/buntyshah/fifa-world-cup-prediction-dnn-tensorflow
Author: Bunty Shah
Platform type: Kaggle notebook
Language: Python
Verified on: 2026-05-27

## Project Positioning

This is a classic 2018-era deep learning example for FIFA World Cup prediction. It uses TensorFlow DNN classifiers on tabular international football data.

It is useful for understanding how neural networks were applied to this problem, but it is not the strongest modeling approach among the projects reviewed.

## Problem Definition

The project predicts whether the home team wins a match. Draws are treated as not winning in part of the workflow:

```python
is_won = score_difference > 0
```

This converts the problem into binary classification:

```text
home team wins / home team does not win
```

The trained model is then used to simulate 2018 World Cup matches.

## Data Inputs

The project uses:

- international football results from 1872 to 2018,
- FIFA world ranking data,
- World Cup 2018 fixture data.

The data is cleaned by standardizing team names, forward-filling ranking data, and combining match results with ranking-derived features.

## Feature Design

The DNN uses a compact feature set:

- `average_rank`,
- `rank_difference`,
- `point_difference`,
- `is_stake`.

The feature set is intentionally simple. This helps demonstrate the model, but it limits predictive power.

## Modeling Principle

The model uses TensorFlow's DNN classifier pattern.

The notebook builds numeric feature columns:

```python
tf.feature_column.numeric_column(feature_name)
```

Then trains a DNN classifier over the engineered match features.

The intended intuition:

- stronger ranking should increase win probability,
- larger point difference should increase win probability,
- high-stakes matches may behave differently than friendlies.

## Implementation Workflow

### 1. Build Match-Level Dataset

The notebook loads match results and rankings, then creates match-level features.

### 2. Split Train and Validation

The notebook uses an ordered split:

```text
training_examples = matches.head(...)
validation_examples = matches.tail(...)
```

This is better than random split for time-series-like sports data, but still needs careful date validation.

### 3. Define TensorFlow Input Function

The notebook uses a TensorFlow Dataset input function:

```python
Dataset.from_tensor_slices((features, targets))
```

### 4. Train DNN Classifier

The model is trained with chosen batch size, learning rate, and hidden layers.

The notebook notes that increasing neural depth to four levels improved reported accuracy.

### 5. Evaluate AUC and Accuracy

The notebook reports validation AUC and accuracy around 0.7 in its description.

### 6. Simulate World Cup Matches

The trained model outputs probabilities for matchups, then the notebook advances winners through the tournament bracket.

## How To Use This Project

Use it as a deep-learning comparison baseline:

1. Open the Kaggle notebook.
2. Run data preparation cells.
3. Confirm that ranking joins are correct.
4. Train the DNN classifier.
5. Compare DNN validation AUC and accuracy against Logistic Regression, Random Forest, and XGBoost.
6. Use the DNN only if it beats simpler baselines under time-based validation.

## Modernization Notes

This notebook uses older TensorFlow patterns. If rebuilding today:

- replace old estimator APIs with Keras or scikit-learn-compatible wrappers,
- use `tf.keras.Sequential`,
- add proper probability calibration,
- use time-based cross-validation,
- keep draw as a separate class instead of merging it with losses,
- compare against XGBoost and LightGBM.

## Quality Assessment

Strengths:

- Demonstrates a complete TensorFlow workflow.
- Uses ranking and match context features.
- Produces match probabilities that can feed tournament simulation.

Weaknesses:

- Deep learning is not obviously justified for a small tabular dataset.
- Draw handling is too coarse.
- Feature set is narrow.
- Old TensorFlow API makes reuse harder.
- Reported accuracy around 0.7 needs stricter validation before trust.

## What Finer Can Learn

The project is useful mainly as a negative control:

```text
Do not assume neural networks improve small structured prediction problems.
```

For future modeling, start with transparent baselines, then justify deep learning only when feature volume, sample size, and temporal validation support it.

