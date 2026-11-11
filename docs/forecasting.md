# Agricultural Production Forecasting

## Overview

AgriMarket Intelligence generates baseline annual production forecasts for Moroccan crops from historical FAOSTAT data.

The current dataset contains 92 crops with annual production observations from 2015 through 2024. The forecast-generation script produces estimates for 2025.

## Forecasting methods

- `naive`: predicts production using the last observed value.
- `linear_trend`: fits a linear trend to historical production observations.

Candidate methods are evaluated separately with the experiment framework.
The reviewed production choice is explicit in `scripts/generate_forecasts.py`;
it is currently `naive-v1` (`naive`) for every crop. Production does not
automatically select a method per crop.

## Evaluation

The chronological evaluation reserves the final two years (2023–2024) as a
holdout. The current results cover 92 crops.

| Method | Median MAE | Median RMSE |
|---|---:|---:|
| Naive baseline | 4,171.38 | 4,831.67 |
| Linear trend | 7,701.79 | 8,463.84 |
| Historical per-crop selection strategy | 6,319.88 | 6,903.60 |

Errors are measured in each crop’s production unit. Because crop production scales vary, these raw-error medians are an initial comparison, not a scale-normalized measure of forecasting quality.

The naive baseline performed better on median holdout error than either the
linear trend or the historical per-crop selection strategy. This evidence
supports the current reviewed production choice; it does not guarantee future
accuracy.

The holdout contains only two years, so results are preliminary and may be sensitive to unusual production conditions.

## Commands

Run the automated tests:

`PYTHONPATH=src:. pytest -q`

Evaluate a forecasting method on the validation years (2019–2022):

`pip install -e ".[experiments]"`

`python scripts/evaluate_yearly.py`

Score the final holdout (2023–2024), once, for a method that is already chosen:

`python scripts/evaluate_yearly.py --final-test`

This evaluates one method per run, set in `YearlyModel` in
`src/agrimarket/evaluation/models.py` (`naive` by default; use
`YearlyModel(method="linear_trend")` for the other). It reproduces the naive
and linear-trend holdout medians in the table above. The historical per-crop
selection row came from the removed selection strategy, so it is retained as
a historical result and is not reproduced. See
[ml_model_evaluation/experiment_framework.md](ml_model_evaluation/experiment_framework.md)
for details and for the MLflow dashboard.

Generate next-year forecasts:

`PYTHONPATH=src:. python scripts/generate_forecasts.py`

## Outputs

`scripts/generate_forecasts.py` writes `data/processed/crop_production_forecasts.csv`.
The file records `method` and `model_version` alongside each forecast.
Each evaluation run writes its tables and plots to
`experiment_runs/yearly/<timestamp>/` and to a local MLflow database. These
are local and Git-ignored.

Generated reports do not need to be committed to Git.

## Limitations

- Forecasts use historical annual production only; climate, soil, prices, irrigation, and other explanatory variables are not included.
- The two candidate methods are simple baselines, not advanced time-series models.
- Validation and holdout results are based on a short historical series.
- Forecasts are estimates, not guarantees or recommendations for agricultural or financial decisions.

An audit of the evaluation methodology and the ongoing work to standardise it are documented in [ml_model_evaluation/](ml_model_evaluation/README.md).
