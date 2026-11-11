# Forecasting code audit

This document describes how forecasts are produced, evaluated, and consumed
today, and lists the evaluation issues confirmed by reading the code and by
re-running it. It does not change any forecasting behaviour.

Numbers quoted here come from an audit script that ran the three existing
scripts unmodified inside a temporary directory and wrote
[`results/audit_checks.csv`](results/audit_checks.csv) and
[`results/audit_per_crop_metrics.csv`](results/audit_per_crop_metrics.csv).
The audit describes the code as it was in commit `20af93f`. Line numbers
refer to the files at that commit. `evaluate_forecasting.py`,
`validate_forecasting.py`, `evaluate_forecast` and the audit script were
removed afterwards; see the note in the [Phase 1 README](README.md#note-code-removed-after-this-audit).

- [1. Forecasting problem](#1-forecasting-problem)
- [2. Data flow](#2-data-flow)
- [3. Models](#3-models)
- [4. Evaluation entry points](#4-evaluation-entry-points)
- [5. Consumers of forecasting outputs](#5-consumers-of-forecasting-outputs)
- [6. Confirmed issues](#6-confirmed-issues)
- [7. What is already sound](#7-what-is-already-sound)
- [8. Reproducing the audit](#8-reproducing-the-audit)

## 1. Forecasting problem

| Aspect | Current implementation |
|---|---|
| Target | `Value` (annual production) for one `Item` (crop), Morocco, FAOSTAT element *Production* |
| Unit | Tonnes (`t`) for every crop in the current data |
| Granularity | One value per crop per calendar year |
| Model scope | Local: every crop is fitted independently |
| Inputs | The crop's own history only; no climate, area, price, or other features |
| Published horizon | One year ahead (forecast year 2025 from data ending 2024) |
| Output | A point forecast; no interval or uncertainty estimate |

## 2. Data flow

```text
data/raw/faostat_morocco_crops.csv              (not in the repository)
  └─ scripts/process_faostat.py
       load_faostat_csv()          src/agrimarket/ingestion/faostat.py
       clean_faostat_production()  src/agrimarket/ingestion/cleaning.py
         keeps Element == "Production", drops missing Value
       validate_processed_data()   rejects empty data, missing values,
                                   duplicate rows, years outside 2015–2024
  └─ data/processed/faostat_morocco_production.csv   (committed)
       ├─ scripts/generate_forecasts.py   → crop_production_forecasts.csv (committed)
       ├─ scripts/evaluate_forecasting.py → forecast_evaluation.csv
       │                                    forecast_model_comparison.csv
       └─ scripts/validate_forecasting.py → forecast_holdout_evaluation.csv
                                            forecast_holdout_summary.csv
```

Only the production file and the forecast file are committed.
`.gitignore` excludes everything else in `data/processed/`, so the four
evaluation CSVs exist only on a machine where the scripts were run.

The data itself is described in [dataset_eda.md](dataset_eda.md).

## 3. Models

Both models are in `forecast_production` in
[`src/agrimarket/analytics/forecasting.py`](../../../src/agrimarket/analytics/forecasting.py)
(lines 50–79).

| Method | Prediction for `target_year` |
|---|---|
| `naive` | Last observed value |
| `linear_trend` | `np.polyfit(years, values, 1)` evaluated at `target_year`, clipped at 0 |

Before fitting, `_get_crop_series` (lines 10–47) rejects a crop with missing
required columns, non-numeric or non-integer years, duplicate years, gaps in
the year sequence, negative values, more than one unit, or fewer than
`MIN_TRAINING_OBSERVATIONS = 4` observations. All 92 crops in the current
data pass these checks.

`forecast_production` accepts any `target_year` after the last training
year, so the same function produces one-step and multi-step forecasts.

## 4. Evaluation entry points

There are four places where forecast errors are computed. None of them
calls another's scoring loop; each script has its own.

### 4.1 Side-by-side comparison

Years are those produced by the current 2015–2024 data. "Expanding" means
the model is refitted with each new year before forecasting the next one.
"Fixed origin" means one fit is used to forecast several years ahead.

| | `evaluate_forecast` | `select_best_method` | `scripts/evaluate_forecasting.py` | `scripts/validate_forecasting.py` |
|---|---|---|---|---|
| Location | `forecasting.py` 82–115 | `forecasting.py` 118–178 | script, top-level code | script, `main()` |
| Purpose | Score one method on one crop | Pick a method for one crop | Compare both methods on all crops | Score a pre-selected method on unseen years |
| Called by | `tests/test_forecasting.py` only | `generate_forecasts.py`, `validate_forecasting.py` | run manually | run manually |
| Minimum observations | 6 | 6 | 5 | 8 |
| Training window | Expanding | Fixed | Expanding | Selection: fixed; holdout: expanding |
| Scored years | 2023–2024 | 2023–2024 (from `generate_forecasts.py`) or 2021–2022 (from `validate_forecasting.py`) | 2020–2024 | Selection 2021–2022, holdout 2023–2024 |
| Forecast horizon | 1 year | 1 and 2 years | 1 year | Selection 1 and 2 years; holdout 1 year |
| Metrics | MAE, RMSE | MAE | MAE | MAE, RMSE |
| Model selection | None | Lower MAE wins | Lower MAE on the **reported** years | Chosen on 2021–2022, kept fixed for 2023–2024 |
| Aggregation across crops | n/a | n/a | Median MAE | Median MAE and RMSE |
| Ineligible crops | Raises `ValueError` | Raises `ValueError` | Silently skipped | Listed with a reason |
| Output | Return value | Return value | `forecast_evaluation.csv`, `forecast_model_comparison.csv` | `forecast_holdout_evaluation.csv`, `forecast_holdout_summary.csv` |

### 4.2 `generate_forecasts.py`

For each crop, `select_best_method(series, crop, selection_test_size=2)`
fits on 2015–2022 and forecasts 2023 and 2024 from that single fit
(lines 28–32). The method with the lower mean absolute error is then refitted
on 2015–2024 to forecast 2025 (lines 36–41). The selection score is written
as `validation_mae`, together with `validation_start_year = 2023` and
`validation_end_year = 2024`.

### 4.3 `evaluate_forecasting.py`

The script has no `main()` and runs at import. It uses
`MIN_TRAIN_SIZE = 4` and `MAX_TEST_SIZE = 5` (lines 8–9). For a 10-year
series `first_test_index = max(4, 10 - 5) = 5` (line 33), so it forecasts
2020, 2021, 2022, 2023, and 2024, refitting each year. It records absolute
errors only (line 51) and writes per-method MAE to `forecast_evaluation.csv`.
It then labels the lower-MAE method `best_method` (lines 77–81) and writes
`forecast_model_comparison.csv`.

### 4.4 `validate_forecasting.py`

The final two years (2023–2024) are removed before selection (lines 74–75).
`select_best_method` runs on 2015–2022, so it trains on 2015–2020 and scores
2021–2022 from that fit (lines 78–82). On the holdout, both methods and the
selected one are forecast one step ahead with refitting (lines 91–111).
Medians across crops are written to `forecast_holdout_summary.csv`
(line 159). These are the figures published in
[`docs/forecasting.md`](../../forecasting.md).

## 5. Consumers of forecasting outputs

| Consumer | Reads | Shows |
|---|---|---|
| `GET /api/crops/<crop>/forecast` — `src/agrimarket/api.py` 183–215 | `crop_production_forecasts.csv` | Every column of the crop's forecast row |
| Next.js dashboard, Forecasting section — `frontend/app/components/DashboardSections.tsx` 291–294 | API above | `validation_mae` labelled "Validation MAE", and `selected_method` described as "Method selected by existing evaluation" |
| Streamlit dashboard — `dashboard.py` 72–139 | API above | Forecast table |
| `forecasting_agent` — `src/agrimarket/ai/agents.py` 198–237 | `crop_production_forecasts.csv`, and `forecast_evaluation.csv` if present (line 226) | Tool evidence for the AI workflow |
| `_format_forecast_metric_context` — `src/agrimarket/ai/workflow.py` 376–433 | Agent evidence | Appends `validation_mae` and backtest MAE as separate figures; states that the evaluation years are not specified |
| `summarize_evidence` — `src/agrimarket/ai/analyst.py` 380–404 | `forecast_holdout_evaluation.csv` if present | Holdout MAE lines in the fallback written answer |

`forecast_model_comparison.csv` and `forecast_holdout_summary.csv` are not
read by any application code.

## 6. Confirmed issues

Severity describes the effect on fair model comparison: **High** means a
comparison or a published accuracy figure can be wrong; **Medium** means it
can mislead or become wrong when data or models change; **Low** is a
maintenance risk.

### I-1. Four scoring procedures, four answers for the same crop — High

The same method on the same crop gets a different MAE depending on which
entry point is used. For Wheat, linear trend:

| Source | Years | Horizon | MAE (t) |
|---|---|---|---:|
| `validation_mae` in `crop_production_forecasts.csv` | 2023–2024 | 1 and 2 | 677,523 |
| `evaluate_forecast(test_size=2)` / holdout in `validate_forecasting.py` | 2023–2024 | 1 | 795,163 |
| `forecast_evaluation.csv` | 2020–2024 | 1 | 2,122,437 |
| `selection_validation_mae` in `forecast_holdout_evaluation.csv` | 2021–2022 | 1 and 2 | 2,505,181 |

Source: [`results/audit_per_crop_metrics.csv`](results/audit_per_crop_metrics.csv).
None of the four is wrong for its own definition, but they are not
interchangeable, and the files do not record which definition was used.
The AI system prompt (`workflow.py` lines 155–164) already has to tell the
model not to mix them up.

### I-2. Selection scores use a different procedure from evaluation — High

`select_best_method` forecasts both validation years from one fit
(`forecasting.py` lines 142–160). The second year is therefore a two-year-ahead
forecast. Every evaluation loop refits each year and scores one-year-ahead
forecasts only. Across the 92 crops, the selection score differs from a
one-step score over the same two years for 89 crops (naive) and 90 crops
(linear trend) (`fixed_origin_vs_one_step_*` in `audit_checks.csv`).

A method is therefore chosen with one procedure, judged with another, and
published for a third: the 2025 forecast is one step ahead.

### I-3. A winner is chosen on the years it is reported on — High

`evaluate_forecasting.py` assigns `best_method` from the same 2020–2024
errors that it reports (lines 77–81). The median MAE of "the better of the
two per crop" on those years is 6,368 t. That is lower than either method's
own median, 6,425 t for naive and 8,005 t for linear trend. Picking the
winner after looking at the test years makes the combination look better
than any rule that could be applied before seeing those years.

The same effect inside the holdout: if each crop's winner were chosen on
2023–2024, the median MAE would be 4,034 t, compared with 6,320 t for the
method that was actually chosen beforehand.

`forecast_model_comparison.csv` is not consumed by the application, so
this is a reporting risk rather than a live-product bug. The pattern must
not be reused in Phase 3.

### I-4. Published `validation_mae` is an optimistic, in-sample selection score — High

`validation_mae` is the minimum of two candidate scores on 2023–2024, the
same two years used to choose the published method. It is not an
independent estimate of the published forecast's error. Its horizon mix
(see I-2) also differs from the one-step 2025 forecast. The dashboard
labels it "Validation MAE" next to "Method selected by existing evaluation",
which a reader can easily take as expected accuracy.

### I-5. Selection does not beat the naive baseline on the holdout — High

From `validate_forecasting.py` (matching `docs/forecasting.md`):

| Strategy | Median holdout MAE (t) | Median holdout RMSE (t) |
|---|---:|---:|
| Always naive | 4,171.38 | 4,831.67 |
| Always linear trend | 7,701.79 | 8,463.84 |
| Selected on 2021–2022 | 6,319.88 | 6,903.60 |

The method chosen on 2021–2022 is also the 2023–2024 winner for 64.1% of
crops. Naive alone is the winner for 62 of 92 crops (67.4%). With
two selection years and two methods, the selection step adds noise rather
than information. This is a property of the data and design, not a bug,
but it means the current pipeline publishes a linear trend for 29 crops
without evidence that this is better than naive.

### I-6. Cross-crop aggregation is dominated by scale and by data provenance — High

All values are in tonnes, but crop medians range from 45.73 t to
4,091,887 t. The median raw MAE describes a mid-sized crop, and a mean
would be dominated by the largest crops: Wheat, Barley, Olives, Sugar beet,
and Oranges account for 63.1% of the summed naive holdout MAE.

Dividing each crop's holdout MAE by its mean 2023–2024 production gives a
scale-free comparison. The pooled ranking is unchanged, but the pooled
figure blends two very different groups:

| Crops | Count | Naive | Linear trend | Selected |
|---|---:|---:|---:|---:|
| Every value flagged official (A) | 57 | 23.2% | 26.4% | 23.2% |
| No value flagged official | 32 | 0.28% | 1.32% | 0.26% |
| Mixed | 3 | 17.9% | 26.2% | 17.9% |
| All | 92 | 9.99% | 14.1% | 13.6% |

The 32 crops without official values are smooth imputed or estimated series
(see [dataset_eda.md](dataset_eda.md#4-data-provenance)). Including them in
one pooled median makes every method look several times more accurate than
it is on officially reported crops.

### I-7. Two test points per crop — Medium

The holdout and the selection window are two years each. A per-crop MAE is
the mean of two errors, and the published medians rest on 184 one-step
forecasts concentrated in 2023 and 2024. Any comparison of two methods on
this design has very wide uncertainty that is not reported today.

### I-8. Different eligibility rules per entry point — Medium

The scripts require 5, 6, or 8 observations and handle failures
differently: `evaluate_forecasting.py` silently skips a forecast that raises
(lines 52–53) and a crop with no errors (line 55). With the current data
every crop qualifies everywhere, so the populations happen to match. If a
crop with a gap or a shorter history is added, each script will evaluate a
different set of crops without saying so in its outputs.

`evaluate_forecasting.py` also does not check that both methods produced the
same number of test errors before comparing them.

### I-9. Evaluation results are not shipped or versioned — Medium

The four evaluation CSVs are gitignored, and the Render build
(`render.yaml`) only runs `pip install .`. In a fresh deployment,
`forecasting_agent` therefore returns an empty `evaluation` list, and the
analyst's holdout section is skipped. This is inferred from configuration;
the live deployment was not inspected.

Locally, each script overwrites its outputs in place. Nothing records the
dataset version, code version, parameters, or run time, so an existing CSV
cannot be tied back to the code that produced it.

### I-10. Duplicated scoring code and untested scripts — Low

Validation and the expanding-window loop are re-implemented in
`evaluate_forecasting.py` and `validate_forecasting.py` instead of calling
`evaluate_forecast` or `_get_crop_series`. `evaluate_forecasting.py`
executes on import. Neither script has tests. `tests/test_forecasting.py`
covers the library functions only, and no test pins the evaluation years,
the horizon, or the absence of holdout data during selection.

### I-11. Not bit-identical between runs — Low

Re-running `generate_forecasts.py` reproduces the committed forecast file
with the same methods for all 92 crops. Linear-trend values differ between
runs by at most a few 10⁻⁷ t, which is floating-point noise from
`np.polyfit`. Future regression tests should compare with a tolerance
rather than exact equality.

## 7. What is already sound

- No look-ahead inside a forecast: every loop trains on `series.iloc[:index]`,
  strictly before the year being predicted.
- `validate_forecasting.py` keeps 2023–2024 out of method selection and
  compares the selected method against both baselines, which is the right
  shape for an honest holdout.
- The naive baseline is always reported next to linear trend.
- Series validation in `_get_crop_series` is strict and explicit.
- `docs/forecasting.md` already states that raw-unit medians are only an
  initial comparison and that the holdout is short.
- The committed forecasts and the documented holdout medians reproduce
  from the committed production data (`regenerated_forecasts.*` and
  `holdout_matches_docs.*` in `audit_checks.csv`).
- `evaluate_forecast(test_size=2)` gives the same numbers as the holdout loop
  in `validate_forecasting.py`, so the library already contains a correct
  one-step evaluator that the scripts could share.

## 8. Reproducing the audit

The audit script was removed together with the scripts it ran, and it was
never committed, so it cannot be recovered from the repository history. The
results it produced are kept in [`results/`](results/). The three scripts it
ran (`generate_forecasts.py`, `evaluate_forecasting.py` and
`validate_forecasting.py`) exist in commit `20af93f`, so the checks can be
repeated by running them there on
`data/processed/faostat_morocco_production.csv`.
