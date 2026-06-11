# GitHub: qatar_2022_prediction

Source: https://github.com/davidcamilo0710/qatar_2022_prediction
Author: davidcamilo0710
Repository stars at verification: 32
Primary language: Jupyter Notebook
Verified on: 2026-05-27

## Project Positioning

This is one of the stronger GitHub projects found in the search. It has a complete machine learning workflow for Qatar 2022:

- data preparation,
- player and squad strength extraction,
- exploratory analysis,
- model comparison,
- hyperparameter tuning,
- saved model pipelines,
- group-stage and knockout-stage prediction.

It is a better learning target than many high-star beginner notebooks because it separates group-stage and knockout-stage modeling.

## Problem Definition

The project predicts World Cup match outcomes for Qatar 2022.

It uses two different prediction settings:

1. Group stage:

```text
home win / draw / away win
```

2. Knockout stage:

```text
team A wins / team B wins
```

This split is correct because draws are allowed in the group stage but not as final outcomes in knockout matches.

## Data Inputs

The repository uses:

- `international_matches.csv`, based on international soccer matches since the 1990s,
- FIFA ranking and team strength columns,
- `players_22.csv`, based on FIFA 22 player data,
- derived squad statistics,
- prepared training and inference datasets.

Important files:

- `QATAR22_EDA+Data_Preparation.ipynb`,
- `Getting_Squads_Stats.ipynb`,
- `Modeling+Tuning.ipynb`,
- `Predictions.ipynb`,
- `data/training.csv`,
- `data/last_team_scores.csv`,
- `data/squad_stats.csv`.

## Feature Design

The project builds features from both team-level and squad-level information:

- FIFA ranking,
- recent team performance,
- team defense rating,
- team midfield rating,
- team offense rating,
- squad potential,
- home/away designation,
- last available team scores.

The repository uses squad strength to decide which team is treated as home in neutral World Cup fixtures. This is a modeling convention rather than a real home-field assumption.

## Modeling Principle

The project compares several algorithms:

- Random Forest,
- AdaBoost Classifier,
- XGBoost,
- Neural Network.

The README says XGBoost performs best for both group-stage and knockout-stage modeling. The notebook outputs show:

- group-stage three-class accuracy around 0.61 to 0.62 after tuning,
- knockout binary accuracy around 0.77 to 0.78.

These are plausible for this domain and more honest than projects claiming near-perfect performance.

## Implementation Workflow

### 1. Data Preparation

The data preparation notebook cleans international match data and player data. It removes or fixes missing values and creates datasets limited to World Cup teams.

### 2. Squad Statistics

The squad notebook aggregates FIFA 22 player data into national team-level metrics:

- defense,
- midfield,
- offense,
- player quality,
- potential.

### 3. Model Selection

The modeling notebook runs multiple classifiers for group-stage data and knockout-stage data.

For group-stage classification:

```text
labels = loss / draw / win
```

For knockout-stage classification:

```text
labels = loss / win
```

### 4. Hyperparameter Tuning

The project uses `GridSearchCV` for tuning.

Documented XGBoost group-stage parameters include:

```text
gamma = 0.01
learning_rate = 0.01
n_estimators = 300
max_depth = 4
```

Documented XGBoost knockout parameters include:

```text
gamma = 0.01
learning_rate = 0.01
max_depth = 5
n_estimators = 500
```

### 5. Pipeline Export

The project creates scikit-learn pipelines using:

- one-hot encoding,
- standard scaling,
- XGBoost classifier.

Models are saved with `joblib`.

### 6. Prediction Notebook

`Predictions.ipynb` loads the saved pipelines and runs:

- group-stage predictions,
- round-of-16 predictions,
- quarterfinal predictions,
- semifinal predictions,
- final prediction,
- third-place prediction.

The notebook output predicted France as champion, Argentina as runner-up, and Germany as third. The real 2022 champion was Argentina.

## How To Use This Project

### Reproduce Original Workflow

1. Clone the repository:

```bash
git clone https://github.com/davidcamilo0710/qatar_2022_prediction.git
cd qatar_2022_prediction
```

2. Open notebooks in order:

```text
QATAR22_EDA+Data_Preparation.ipynb
Getting_Squads_Stats.ipynb
Modeling+Tuning.ipynb
Predictions.ipynb
```

3. If running outside Google Colab, replace `/content/drive/MyDrive/...` paths with local paths.
4. Install required packages:

```bash
pip install pandas numpy scikit-learn xgboost tensorflow keras seaborn matplotlib joblib
```

5. Run modeling before prediction because `Predictions.ipynb` expects saved `.pkl` model files.

### Adapt For 2026

1. Replace Qatar 2022 fixtures with 2026 fixtures.
2. Replace FIFA 22 player data with a current player or squad dataset.
3. Update international match data through the latest pre-tournament date.
4. Rebuild `training.csv`.
5. Keep group and knockout models separate.
6. Evaluate on past tournaments before using 2026 predictions.

## Quality Assessment

Strengths:

- Complete workflow.
- Uses both historical match data and squad strength.
- Separates group and knockout prediction.
- Compares multiple models.
- Saves reusable pipelines.
- Reports realistic accuracy ranges.

Weaknesses:

- The home-team assignment for neutral matches is artificial.
- FIFA video-game player ratings are a proxy, not direct performance data.
- Saved models depend on Google Drive paths in the original notebooks.
- It predicted France over Argentina, so it should be viewed as probabilistic analysis, not a precise oracle.

## What Finer Can Learn

The best reusable pattern is stage-specific modeling:

```text
group-stage model != knockout-stage model
```

For Finer, an analogous pattern is:

```text
pre-event probability model != post-trigger execution model
```

Different decision stages deserve different labels, features, and evaluation metrics.

