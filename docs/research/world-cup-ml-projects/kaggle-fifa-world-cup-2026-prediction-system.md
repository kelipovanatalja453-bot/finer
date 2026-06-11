# Kaggle: FIFA World Cup 2026 Prediction System

Source: https://www.kaggle.com/datasets/rauffauzanrambe/fifa-world-cup-2026-prediction-system
Author: Ra'uf Fauzan Rambe
Platform type: Kaggle dataset with Python pipeline
Language: Python
Verified on: 2026-05-27

## Project Positioning

This project is a Kaggle dataset plus an included machine learning pipeline. It is useful as a compact end-to-end ML exercise for predicting 2026 World Cup winner probabilities.

It should be treated as an educational dataset and baseline pipeline, not as a reliable forecast source.

## Dataset Contents

The downloaded dataset includes:

- `train (1).csv`,
- `test (2).csv`,
- `submission (17).csv`,
- `fifa_wc2026_pipeline.py`.

The training file has about 1000 rows. The test file has about 250 rows.

## Problem Definition

The target is:

```text
winner
```

The pipeline trains a binary classifier:

```text
team/tournament row becomes winner / not winner
```

Then it predicts:

```text
winner_probability
```

for rows in the test set.

## Feature Design

The raw columns include:

- `team_name`,
- `country_code`,
- `confederation`,
- `fifa_rank`,
- `fifa_points`,
- `wins_last_10_matches`,
- `losses_last_10_matches`,
- `draws_last_10_matches`,
- `win_rate_last_year`,
- `goals_scored_avg`,
- `goals_conceded_avg`,
- `clean_sheets_last_10`,
- `shots_per_game`,
- `shots_on_target_ratio`,
- `avg_player_rating`,
- `star_players_count`,
- `market_value_million_eur`,
- `experience_avg_caps`,
- `coach_experience_years`,
- `recent_form_score`,
- `possession_avg`,
- `passing_accuracy`,
- `host_advantage`,
- `travel_distance_avg`,
- `climate_similarity_score`.

The pipeline then adds engineered features such as:

- `strength_index`,
- `goal_efficiency`,
- `attack_potency`,
- `defensive_solidity`,
- `squad_quality`,
- `form_consistency`,
- `possession_dominance`,
- `star_power`,
- `contextual_advantage`.

## Modeling Principle

The core model is an ensemble:

- XGBoost classifier,
- Random Forest classifier,
- blended probability:

```text
final_probability = 0.6 * xgb_probability + 0.4 * rf_probability
```

The pipeline also attempts probability calibration with isotonic calibration.

## Implementation Workflow

### 1. Load Data

The script reads train and test CSV files.

### 2. Select Numeric Features

Object columns such as team name and confederation are excluded from the model. Numeric features are used.

### 3. Fill Missing Values

Missing values are filled with column means.

### 4. Engineer Features

Domain-inspired composite metrics are created, for example:

```text
strength_index = fifa_points + recent_form_score * 50 + avg_player_rating * 10
```

### 5. Train and Validate

The script uses:

- train-validation split,
- accuracy,
- AUC-ROC,
- classification report,
- feature importance.

### 6. Train Ensemble

XGBoost and Random Forest are trained separately. Their predicted probabilities are blended.

### 7. Generate Submission

The output CSV contains:

```text
id, winner_probability
```

### 8. Print Top Predicted Winners

The script groups predictions by `team_name` and prints top teams by average winner probability.

## How To Use This Project

On Kaggle:

1. Create a notebook using this dataset.
2. Run `fifa_wc2026_pipeline.py`.
3. Adjust file paths to Kaggle input paths.
4. Inspect feature importance.
5. Export `submission.csv`.

Locally:

1. Download the dataset ZIP from Kaggle.
2. Extract the CSV and Python files.
3. Install dependencies:

```bash
pip install pandas numpy scikit-learn xgboost
```

4. Edit `TRAIN_PATH`, `TEST_PATH`, and `submission_path`.
5. Run:

```bash
python fifa_wc2026_pipeline.py
```

## Quality Assessment

Strengths:

- Complete pipeline in one script.
- Good feature-engineering exercise.
- Includes XGBoost, Random Forest, blending, calibration, and cross-validation.
- Easy to run and modify.

Weaknesses:

- Dataset appears heavily synthetic or manually feature-engineered.
- The target construction is not independently verified.
- It predicts row-level winner probability, not full tournament path probability.
- It does not model bracket draw, group-stage qualification, or knockout dependencies.
- Numeric-only feature selection discards potentially useful categorical structure.

## Recommended Improvements

To make this more serious:

- use real historical World Cup editions as training rows,
- split by tournament year, not random rows,
- keep 2026 data strictly out of training labels,
- model group and knockout paths explicitly,
- calibrate probabilities on held-out tournaments,
- include uncertainty intervals.

## What Finer Can Learn

This is a useful example of fast baseline construction:

```text
raw features -> engineered features -> model ensemble -> probability output
```

The main lesson is that an end-to-end pipeline can be technically complete while still lacking a reliable causal or temporal evaluation design.

