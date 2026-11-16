# Agricultural Production Forecasting

## Overview

The checked-in FAOSTAT production dataset contains 92 crops with annual observations from 2015 through 2024. The stored forecasts target 2025 and use observations through 2024. They are historical estimates, not current forecasts. A later forecast requires newer observed production data; rerunning the generator against the current dataset will still produce 2025 estimates.

Forecast generation selects between two simple methods using a chronological validation window:

- `naive`: repeats the latest observed production value.
- `linear_trend`: extrapolates a fitted linear trend.

Each saved record includes the forecast year, training period, selected method, validation period, and validation MAE. Validation MAE is the selection score, not an unbiased estimate of future performance.

## Evaluation

The pooled Random Forest remains experimental. Compare it with the naive baseline, linear trend, and a selected baseline (naive or trend chosen on a pre-holdout validation window) using the evaluation command below.

The evaluator uses the latest two distinct years in the production dataset as a shared chronological holdout. A crop is eligible only when its yearly series is valid and complete, it has both holdout years, and it has at least six pre-holdout observations (four for training and two for baseline selection). All methods are scored on the same crop/year pairs. The script reports eligible and excluded crop counts and the holdout years.

Current checked-in evaluation (92 crops, 2023–2024 holdout):

| Method | Median crop MAE (source units vary) | Median crop WAPE | Mean crop WAPE | Unique crop wins by WAPE |
|---|---:|---:|---:|---:|
| Naive | 4,171.38 | 9.99% | 20.62% | 15 |
| Linear trend | 7,701.79 | 14.10% | 25.63% | 13 |
| Selected baseline | 6,319.88 | 13.56% | 22.13% | 0 |
| Pooled Random Forest | 6,930.59 | 12.90% | 23.62% | 17 |

The naive baseline performed best by median crop MAE and median crop WAPE. The pooled model had lower median WAPE than the selected baseline and linear trend, but did not beat naive. Unique-win counts omit ties; 47 crops tied for best WAPE across at least two methods. See the per-crop CSV for crop-specific results.

WAPE is calculated within each crop as the sum of absolute errors divided by the sum of absolute actual values. It is undefined when all holdout actuals are zero; such values are excluded from WAPE summaries and crop-win counts. Ties are reported separately from unique crop wins. Raw MAE and RMSE remain useful within a crop but should not be treated as scale-comparable across crops or units. A lower holdout score is evidence on this particular short historical window, not proof of general model superiority.

## Commands

Evaluate the pooled model and baselines:

```bash
PYTHONPATH=src:. python scripts/evaluate_pooled_regression.py
```

Run the baseline-only evaluation:

```bash
PYTHONPATH=src:. python scripts/validate_forecasting.py
```

Generate the stored next-year forecasts:

```bash
PYTHONPATH=src:. python scripts/generate_forecasts.py
```

With the checked-in data, the generator targets 2025. The dashboard labels these stored results historical and does not present them as current forecasts.

## Outputs

Evaluation reports are written to `data/processed/`:

- `pooled_regression_holdout_details.csv`: actuals and predictions by crop, year, and method.
- `pooled_regression_crop_metrics.csv`: per-crop MAE and RMSE in that crop's source unit, plus WAPE.
- `pooled_regression_summary.csv`: aggregate metrics across crops, eligible crop counts, holdout years, and crop wins by WAPE.
- `forecast_holdout_evaluation.csv` and `forecast_holdout_summary.csv`: baseline-only holdout reports.
- `crop_production_forecasts.csv`: stored next-year forecast records.

## Limitations

- Production forecasts use annual production history alone; climate, harvested area, yield, prices, irrigation, and other explanatory variables are not included.
- The series are short, and the latest two-year holdout is sensitive to unusual conditions.
- The pooled model uses historical crop-level features and does not establish that pooled learning will generalize to future years.
- Forecasts are estimates, not guarantees or recommendations for agricultural or financial decisions.
