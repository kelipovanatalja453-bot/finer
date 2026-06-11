# GitHub: FIFA-World-Cup-2022

Source: https://github.com/jieguangzhou/FIFA-World-Cup-2022
Author: jieguangzhou
Repository stars at verification: 9
Primary language: Python
Verified on: 2026-05-27

## Project Positioning

This project is notable because it is not just a notebook. It wraps model training, prediction, simulation, and daily betting strategy into a DolphinScheduler workflow.

It is useful for learning how to turn a sports prediction model into an automated pipeline.

## Problem Definition

The project predicts:

- 2022 World Cup champion probabilities,
- top four teams,
- daily match outcomes,
- betting strategy outputs.

The README reports two types of forecasts.

Simulation-based champion probabilities:

```text
Brazil       0.193
Argentina    0.160
France       0.140
Spain        0.137
England      0.131
```

Top-four simulation result:

```text
Brazil
France
Argentina
Belgium
```

## Data Inputs

The repository includes:

- `international_matches.csv`,
- 2022 teams and schedule data,
- last-match feature table,
- odds data retrieval script,
- prediction result outputs.

Important files:

- `prepare_data.py`,
- `training.py`,
- `predict_match.py`,
- `predict_today_match.py`,
- `betting_strategy.py`,
- `pyds.py`,
- `config.yaml`,
- `Dockerfile`,
- `requirements.txt`.

## Feature Design

The training data includes pairwise differences between teams:

- FIFA rank difference,
- total FIFA points difference,
- goalkeeper score difference,
- defense score difference,
- offense score difference,
- midfield score difference.

Example from `prepare_data.py`:

```text
rank_diff
total_fifa_points
goalkeeper_score_diff
mean_defense_score_diff
mean_offense_score_diff
mean_midfield_score_diff
```

The label is binary after dropping draws:

```text
home_team_result == Win -> 1
home_team_result == Lose -> 0
```

## Modeling Principle

The project uses FLAML AutoML:

```python
automl.fit(X_train, y_train, task="classification", time_budget=train_time)
```

FLAML selects and tunes a classifier within the configured time budget. The trained model is saved with pickle.

This makes the modeling layer flexible, but it also means the exact chosen model depends on FLAML and runtime budget.

## Implementation Workflow

### 1. Data Preparation

`prepare_data.py`:

- loads match data,
- filters matches after 2012,
- fills missing FIFA and squad score data,
- removes draws,
- creates difference features,
- writes `training.csv`,
- writes `last_match.csv` for inference.

### 2. Model Training

`training.py`:

- loads `training.csv`,
- splits train/test,
- runs FLAML AutoML,
- prints classification report,
- saves `model.pkl`.

### 3. Full Tournament Prediction

`predict_match.py`:

- loads schedule,
- loads `last_match.csv`,
- loads `model.pkl`,
- predicts each group match,
- advances group winners and runners-up,
- predicts knockout rounds,
- writes top-four simulation result.

### 4. Workflow Automation

The README describes a DolphinScheduler setup:

- training workflow,
- predict workflow,
- betting-strategy workflow.

It provides Docker-based DolphinScheduler startup instructions.

## How To Use This Project

### Basic Python Use

Clone the repository:

```bash
git clone https://github.com/jieguangzhou/FIFA-World-Cup-2022.git
cd FIFA-World-Cup-2022
```

Install dependencies:

```bash
pip install pandas flaml requests
```

Expected workflow:

```bash
python prepare_data.py
python training.py
python predict_match.py
```

The scripts expect data under `/tmp/fifa/`, so either:

- create that directory and copy files there, or
- modify the path constants in the scripts.

### DolphinScheduler Use

The README gives a Docker command for starting a DolphinScheduler standalone server:

```bash
docker run --name dolphinscheduler-standalone-server -p 12345:12345 -p 25333:25333 -d jalonzjg/dolphinscheduler-fifa
```

Then it uses:

```bash
pip install apache-dolphinscheduler==3.1.1
export PYDS_HOME=./
python3 pyds.py
```

This creates the scheduled workflows.

## How To Adapt It

For another tournament:

1. Replace `schedule.csv`.
2. Update team list.
3. Rebuild `international_matches.csv`.
4. Refresh FIFA rank and squad features.
5. Re-run `prepare_data.py`.
6. Increase FLAML `time_budget`.
7. Run repeated simulations with different seeds.

For 2026, the bracket logic must be modified because the tournament has 48 teams and a different knockout structure.

## Quality Assessment

Strengths:

- Real Python scripts, not only notebooks.
- Automated workflow design.
- Uses AutoML for quick model search.
- Includes simulation and top-four outputs.
- Useful example of scheduled prediction operations.

Weaknesses:

- Draws are removed from training, then draw is approximated by probability threshold in group prediction.
- The default training time budget is short.
- Script paths are hard-coded to `/tmp/fifa/`.
- Betting-strategy framing requires caution.
- Exact model selection depends on FLAML runtime conditions.

## What Finer Can Learn

This project is valuable for orchestration:

```text
prepare data -> train -> predict -> strategy output
```

For Finer, the analogous lesson is to separate:

- data refresh,
- model training,
- inference,
- decision output,
- scheduled automation.

The workflow shape matters as much as the model.

