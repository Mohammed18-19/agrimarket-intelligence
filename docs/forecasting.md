# Agricultural Production Forecasting

## Overview

AgriMarket Intelligence generates baseline annual production forecasts for Moroccan crops from historical FAOSTAT data.

The current dataset contains 92 crops with annual production observations from 2015 through 2024. The forecast-generation script produces estimates for 2025.

## Forecasting methods

- `naive`: predicts production using the last observed value.
- `linear_trend`: fits a linear trend to historical production observations.

The selection procedure compares both methods on an earlier chronological validation window, then uses the selected method with the available historical observations to forecast the next year.

## Evaluation

The chronological holdout evaluation reserves the final two years from method selection. The current results cover 92 crops.

| Method | Median MAE | Median RMSE |
|---|---:|---:|
| Naive baseline | 4,171.38 | 4,831.67 |
| Linear trend | 7,701.79 | 8,463.84 |
| Selected method | 6,319.88 | 6,903.60 |

Errors are measured in each crop’s production unit. Because crop production scales vary, these raw-error medians are an initial comparison, not a scale-normalized measure of forecasting quality.

The naive baseline performed better on median holdout error than either the linear trend or the selected-method strategy. Model selection does not guarantee better performance on unseen data.

The holdout contains only two years, so results are preliminary and may be sensitive to unusual production conditions.

## Commands

Run the automated tests:

`PYTHONPATH=src:. pytest -q`

Evaluate forecasting methods:

`PYTHONPATH=src:. python scripts/validate_forecasting.py`

Generate next-year forecasts:

`PYTHONPATH=src:. python scripts/generate_forecasts.py`

## Outputs

The scripts write local CSV reports under `data/processed/`:

- `forecast_holdout_evaluation.csv`
- `forecast_holdout_summary.csv`
- `crop_production_forecasts.csv`

Generated reports do not need to be committed to Git.

## Limitations

- Forecasts use historical annual production only; climate, soil, prices, irrigation, and other explanatory variables are not included.
- The two candidate methods are simple baselines, not advanced time-series models.
- Validation and holdout results are based on a short historical series.
- Forecasts are estimates, not guarantees or recommendations for agricultural or financial decisions.
