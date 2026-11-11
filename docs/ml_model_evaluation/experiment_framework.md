# Experiment framework

A small framework for changing a forecasting model by hand, evaluating it
under fixed rules, and comparing runs in MLflow. **Only yearly forecasting
has real data today**, so yearly is the only frequency with a script and a
model. The evaluation engine itself also supports daily, weekly and monthly
data, for when such data is added.

- [Files](#files)
- [How the pieces communicate](#how-the-pieces-communicate)
- [Which frequencies can run](#which-frequencies-can-run)
- [Install and run the yearly evaluation](#install-and-run-the-yearly-evaluation)
- [Open the MLflow dashboard](#open-the-mlflow-dashboard)
- [Change a model or its hyperparameters](#change-a-model-or-its-hyperparameters)
- [How a model is evaluated](#how-a-model-is-evaluated)
- [Metrics](#metrics)
- [What is saved and where](#what-is-saved-and-where)
- [What MLflow records](#what-mlflow-records)
- [Add data or a model later](#add-data-or-a-model-later)
- [Status and limitations](#status-and-limitations)

## Files

| File | Purpose |
|---|---|
| [`src/agrimarket/evaluation/models.py`](../../src/agrimarket/evaluation/models.py) | `YearlyModel` (production quantity) and `YearlyPriceModel` (producer price). **This is the file you edit** to change an architecture or hyperparameters. |
| [`src/agrimarket/evaluation/evaluation.py`](../../src/agrimarket/evaluation/evaluation.py) | The single evaluation engine: input checks, expanding-window splits, metric formulas, aggregation, plots, saving tables. Does not use MLflow. |
| [`src/agrimarket/evaluation/tracking.py`](../../src/agrimarket/evaluation/tracking.py) | `log_experiment`: one MLflow run per execution. The only file that imports MLflow. |
| [`scripts/evaluate_yearly.py`](../../scripts/evaluate_yearly.py) | Settings and wiring for yearly production forecasting. Runs on the FAOSTAT production data. |
| [`scripts/evaluate_yearly_prices.py`](../../scripts/evaluate_yearly_prices.py) | Same wiring for annual producer prices. Separate model, data file and MLflow experiment. |
| [`tests/test_experiment_evaluation.py`](../../tests/test_experiment_evaluation.py) | Tests on synthetic data. |

This framework is the only evaluation code in the project. It replaced
`scripts/evaluate_forecasting.py`, `scripts/validate_forecasting.py` and the
function `evaluate_forecast`, which were removed.

Forecast generation is separate: `scripts/generate_forecasts.py` and
`src/agrimarket/analytics/forecasting.py` produce the published forecasts.
The production model is an explicit, version-controlled choice in that
script (`naive-v1` today), based on reviewed experiment results; it is not
selected automatically per crop. `YearlyModel` calls `forecast_production`
from the same module, so it uses the same candidate methods as the
application.

## How the pieces communicate

```text
scripts/evaluate_yearly.py
   │  1. load data (adapt FAOSTAT to entity_id, timestamp, target)
   │  2. model = YearlyModel()                           models.py
   │  3. result = evaluate(data, model, frequency,       evaluation.py
   │                       horizon, settings, metrics)
   │  4. run_dir = save_outputs(result, new_run_dir())   evaluation.py  -> experiment_runs/
   │  5. log_experiment(result, model, dataset, run_dir) tracking.py    -> mlflow.db, mlartifacts/
   └─ 6. print format_summary(result)
```

The script holds only constants and this sequence. The metric formulas and
the backtesting loop exist once, in `evaluation.py`.

Every model has `fit(train_data)`, `predict(horizon)`, `get_params()` and
`describe()`. It forecasts one entity (for example one crop) at a time.
`train_data` has the columns `timestamp` and `target`, oldest first.
`predict(h)` returns `h` values for the periods right after the last training
timestamp.

## Which frequencies can run

| Frequency | Real dataset | Status | Metrics | Horizon | Min. training | Holdout | MLflow experiment |
|---|---|---|---|---|---:|---:|---|
| Yearly | `data/processed/faostat_morocco_production.csv` (92 crops, 2015–2024) | **Runs** | MAE, RMSE, MASE | 1 year | 4 | 2 years | `agrimarket-yearly` |
| Yearly prices | `data/raw/faostat_morocco_producer_prices_annual.csv` (77 crops, 1991–2024, USD/tonne; git-ignored, downloaded by hand from FAOSTAT) | **Runs** | MAE, RMSE, MASE | 1 year | 4 | 2 years | `agrimarket-yearly-prices` |
| Monthly, weekly, daily | none | No script or model; the engine accepts such data | MAE, RMSE | set when added | set when added | set when added | `agrimarket-monthly`, `-weekly`, `-daily` |

The repository only contains annual data. Annual values are never resampled
into finer targets. No monthly price data was found for Morocco: WFP Global
Food Prices has no Morocco records, and the FAOSTAT price download that is
available is annual.

### Annual producer prices

```bash
python scripts/evaluate_yearly_prices.py                  # naive, validation years
python scripts/evaluate_yearly_prices.py --method drift   # last price + average yearly change
python scripts/evaluate_yearly_prices.py --final-test     # reserved holdout, final reporting only
```

The CSV is downloaded by hand from FAOSTAT (Prices, Producer Prices) and is
not committed. The script refuses a file that mixes areas, price elements
(currency or unit) or periods, and takes the unit from the element name. A
price series is never combined with another crop. Crops with missing years
or fewer than seven annual values are excluded and listed in `excluded.csv`.
Runs are logged to the `agrimarket-yearly-prices` MLflow experiment, so they
do not mix with the production-quantity runs. The engine's handling of daily, weekly and monthly data
is covered by tests on synthetic data only; no result exists for those
frequencies.

## Install and run the yearly evaluation

From the repository root:

```bash
pip install -e ".[dev,experiments]"
python scripts/evaluate_yearly.py
```

The scripts add `src/` to the import path themselves, so they also work
without the editable install if pandas, NumPy, Matplotlib and MLflow are
installed.

Example output (the `naive` baseline, validation years 2019–2022):

```text
yearly evaluation, stage=validation, horizon=1
  entities evaluated: 92 of 92 (0 excluded), predictions: 368
  scored 2019-01-01 to 2022-01-01; holdout 2023-01-01 to 2024-01-01 (not used)
  MAE   median 6,643.5450  mean 87,991.9347
  RMSE  median 7,610.8403  mean 97,835.4465
  MASE  median 0.9454  mean 1.3783  share below 1: 57.1%  (defined for 91 of 92)
  MAE/RMSE are in target units and are not comparable across entities.
```

To score the reserved final holdout (2023–2024), once, for a model that is
already chosen:

```bash
python scripts/evaluate_yearly.py --final-test
```

**Never use `--final-test` scores to pick a model or a hyperparameter.** The
default run never reads those two years.

Run the tests (synthetic data only; they verify the machinery, not model
quality):

```bash
python -m pytest tests/test_experiment_evaluation.py -q
```

## Open the MLflow dashboard

```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db --port 5001
```

Open <http://127.0.0.1:5001>. Run it from the repository root. Port 5001 is
used because the project's Flask API uses 5000. Select the
`agrimarket-yearly` experiment, tick runs, and press **Compare** to compare
parameters, metrics and artifacts such as plots.

The database is `mlflow.db` in the repository root and artifacts are in
`mlartifacts/`. Both are Git-ignored.

> **Windows Application Control.** Some policies block SQLAlchemy's compiled
> extension, which makes MLflow fail with *"DLL load failed ... An
> Application Control policy has blocked this file"*. `tracking.py` sets
> `DISABLE_SQLALCHEMY_CEXT_RUNTIME=1` itself. For the `mlflow ui`
> command, set it first. In PowerShell: `$env:DISABLE_SQLALCHEMY_CEXT_RUNTIME = "1"`.
> In bash: `export DISABLE_SQLALCHEMY_CEXT_RUNTIME=1`. It only makes
> SQLAlchemy slightly slower.

## Change a model or its hyperparameters

Open `src/agrimarket/evaluation/models.py`, edit the class, and run the
script again. Each run is a new MLflow run, and the class source is stored
with it.

**Change a hyperparameter.** Change the default or the value the script
passes. For example, in `scripts/evaluate_yearly.py`:

```python
model = YearlyModel(method="linear_trend")
```

**Change the architecture.** Rewrite `fit`, `predict`, `get_params` and
`describe` in the class. For example, a scikit-learn estimator:

```python
from sklearn.linear_model import Ridge

class YearlyModel:
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha

    def fit(self, train_data):
        self._first = int(train_data["timestamp"].dt.year.iloc[0])
        self._last = int(train_data["timestamp"].dt.year.iloc[-1])
        years = train_data["timestamp"].dt.year.to_numpy().reshape(-1, 1)
        self._model = Ridge(alpha=self.alpha).fit(years, train_data["target"])
        return self

    def predict(self, horizon):
        years = [[self._last + step] for step in range(1, horizon + 1)]
        return self._model.predict(years)

    def get_params(self):
        return {"alpha": self.alpha}

    def describe(self):
        return "Ridge regression on the year"
```

Keep `get_params` complete: it is what MLflow records as the
hyperparameters. If a model uses randomness, include `"random_seed"` in
`get_params`; it is then logged as `random_seed` (otherwise the value
`not applicable` is logged). If a trainable model keeps
genuine training and validation losses, expose them as
`self.loss_history = {"train_loss": [...], "val_loss": [...]}` and they are
logged as `loss.<name>` metrics (the history of the last fit only). Nothing is
logged for baselines, because they have no loss curves.

Compare models only if they were evaluated with the same dataset hash,
horizon, `min_train_size`, `holdout_size` and stage. These are logged as
parameters.

## How a model is evaluated

Implemented in `evaluate()` in `evaluation.py`. For each entity:

1. Sort by time. Exclude the entity, with a recorded reason, if it has
   duplicate periods, missing periods, missing or non-finite targets, too few
   observations, a model error, or a non-finite or wrongly shaped prediction.
2. Reserve the last `holdout_size` observations as the holdout.
3. **Validation stage (default):** the first scored point is observation
   number `min_train_size + 1`, and the last is the one before the holdout.
   For each origin, fit on everything before it (an expanding window) and
   predict the next `horizon` periods. The holdout rows are never read.
4. **Holdout stage:** the same loop over the reserved points. Training
   windows may include the validation years but never the point being
   predicted.

For a crop with 2015–2024 and the current settings (4, 2, one year ahead):

| Predicted year | Trained on |
|---|---|
| 2019 | 2015–2018 |
| 2020 | 2015–2019 |
| 2021 | 2015–2020 |
| 2022 | 2015–2021 |
| *holdout* 2023 | 2015–2022 |
| *holdout* 2024 | 2015–2023 |

Each model is a local model: it is refitted for every crop and every window
and never sees another crop's data.

## Metrics

Formulas are defined once, at the top of `evaluation.py`.

| Metric | Definition | Scale-free |
|---|---|---|
| MAE | mean of the absolute errors | No (target units) |
| RMSE | square root of the mean squared error | No (target units) |
| MASE | MAE divided by the mean absolute one-step change of the entity's training data before the first scored point | Yes |

- **MASE is undefined, not zero, when the denominator is zero.** This happens
  for a constant history (for example *Soya beans*, 1,000 t in every year) or
  fewer than two training points. The value is left empty in
  `entity_metrics.csv`, counted in `n_mase_undefined`, left out of MASE
  aggregates, and never logged to MLflow.
- MASE below 1 means the error is smaller than the average one-step change in
  the initial training window. It is not a comparison with the naive
  forecast's own out-of-sample error, so a naive model does not score exactly 1.
- MAE and RMSE are in each crop's unit and are dominated by large crops. Use
  MASE for cross-entity comparison.

**Aggregation.** Per entity, then median and mean across entities. MASE also
reports the share of entities below 1. If the data has a `group` column the
same statistics are repeated for each group. For yearly data the group is
the FAOSTAT provenance of the crop: `official` (every value flagged A),
`no_official`, or `mixed`. Phase 1 showed that the 32 `no_official` crops are
nearly smooth series that make pooled results look better than they are.
The per-observation FAOSTAT `flag` is also kept in `predictions.csv`.

## What is saved and where

Every run writes to `experiment_runs/<frequency>/<UTC timestamp>/`
(Git-ignored) and uploads the same files to MLflow:

| File | Content |
|---|---|
| `predictions.csv` | One row per entity, origin and step: `actual`, `predicted`, `error`, `abs_error`, optional `flag` |
| `entity_metrics.csv` | Per-entity metrics, MASE scale, constant-series flag, optional `group` |
| `summary.csv` | Median, mean, defined counts and MASE share, overall and per group |
| `excluded.csv` | Entities that could not be evaluated, with the reason |
| `plots/actual_vs_predicted.png` | Predictions against actuals (symmetric log axes) |
| `plots/error_distribution.png` | Scale-free forecast error histogram |
| `plots/error_by_entity.png` | The 20 entities with the largest MASE (or the first metric if MASE is not used) |
| `model_source.py` | Source code of the model class used |
| `experiment_metadata.json` | The parameters and metrics logged to MLflow |

## What MLflow records

| Group | Logged as | Content |
|---|---|---|
| Model | params | `model_class`, `model_description`, `model.<hyperparameter>` |
| Setup | params | `frequency`, `horizon`, `training_scope`, `evaluation_strategy`, `evaluation_stage`, `metrics`, `min_train_size`, `holdout_size`, `random_seed`, `target_name`, `target_unit` |
| Reproducibility | params | `git_commit`, `git_uncommitted_changes`, `dataset_path`, `dataset_hash`, `model_source_hash` |
| Periods | params | `train_start`, `first_train_end`, `scored_start`, `scored_end`, `holdout_start`, `holdout_end`, `holdout_used` |
| Performance | metrics | `validation_<metric>_median` / `_mean` / `_n_defined`, `validation_mase_share_below_1`, the same for each group, `validation_n_entities`, `_n_predictions`, `_n_excluded`, `_n_constant_series`, `_n_mase_undefined` |
| Files | artifacts | The table above |

The metric prefix is `validation_` or `holdout_`, so the two can never be
mixed up. Undefined metrics are omitted.

`git_uncommitted_changes` is `True` during development. The source hash and
the stored class source identify the model code. Changes to
`forecast_production` are identified through the commit, so commit before a
run that you want to be able to reproduce exactly.

## Add data or a model later

**A dataset for monthly, weekly or daily forecasting.**

1. Put a real dataset in `data/processed/` with the columns `entity_id`,
   `timestamp` and `target`, and optionally `flag` and `group`.
2. Add a model class to `models.py` (for example `MonthlyModel`) with the
   same four methods as `YearlyModel`.
3. Copy `scripts/evaluate_yearly.py` to `scripts/evaluate_monthly.py`.
   Change `FREQUENCY` (`"daily"`, `"weekly"` or `"monthly"`), `DATA_PATH`,
   `TARGET_NAME`, the model, and set `HORIZON`, `SETTINGS` and `METRICS`
   (`("mae", "rmse")`). Replace `load_yearly_data` with a loader that reads
   the CSV. The evaluation and logging calls stay the same.
4. Run `python scripts/evaluate_monthly.py`.

Timestamps may be any date inside a period. Months, weeks and years are
detected by period, so `2021-03-01` and `2021-03-15` are the same month.

**A different model for yearly data.** Edit `YearlyModel`, or change its
hyperparameters, as shown above. Keep one model per run so that runs remain
comparable in MLflow.

## Status and limitations

- Only yearly evaluation has real data. Daily, weekly and monthly support in
  the engine has only been tested on synthetic data and no result exists
  for those frequencies.
- The framework implements part of the Phase 1
  [recommendations](EDA_yearly/findings_and_recommendations.md):
  one-step evaluation with refitting (P0-1), a holdout that validation never
  reads (P0-2), MASE (P0-4), results by provenance (P0-5), exclusion reasons
  and undefined-MASE reporting (parts of P1-4 and P1-5), and a reproducibility
  record (part of P1-8; it has no list of eligible crops or method list).
  Not done: rolling-origin model selection (P0-3), relabelling of the
  published scores (P0-6), the drift baseline, win rate and uncertainty
  intervals (P1-1 to P1-3). The formal protocol decisions of Phase 2 are
  still open, and the settings here are provisional. The yearly validation
  window has only four scored years per crop.
- It evaluates one model per run. After validation runs are compared and the
  final holdout is scored once, production adoption is a separate reviewed
  code change to `PRODUCTION_METHOD` and `PRODUCTION_MODEL_VERSION` in
  `scripts/generate_forecasts.py`. MLflow does not deploy a model
  automatically.
- The historical per-crop selection strategy reported in
  [`docs/forecasting.md`](../forecasting.md) has been removed and is not
  reproduced by the framework.
- MLflow is a local viewer. There is no model registry or model serving.
- `mlflow.db` and `mlartifacts/` are local state. Delete them to start with
  an empty tracking history.
