# Phase 1 findings and recommendations

This document summarises what Phase 1 found and what Phase 2 should
decide. Items marked **Recommendation** are proposals for Phase 2 to accept,
change, or reject. Nothing here is a final design decision.

Evidence: [dataset_eda.md](dataset_eda.md) and
[forecasting_code_audit.md](forecasting_code_audit.md). Issue numbers
(I-1 … I-11) refer to the audit.

## Main findings

### Data

- One target: annual national production in tonnes for 92 crops, 2015–2024.
  The panel is complete, with no missing, duplicate, zero, or negative
  values.
- Every series has exactly **10 points**. At least 4 are needed to train,
  so at most 6 years can be shared between method selection and testing.
- Scale spans five orders of magnitude (45.73 t to 4.09 million t median
  per crop).
- **32 crops have no officially reported value.** Their series are nearly
  smooth (median coefficient of variation 0.023 versus 0.277 for official
  crops) and are much easier to forecast.
- Officially reported cereals and pulses swing by a factor of two or more
  from year to year. There are 64 such changes in 22 crops.

### Evaluation code

- Four procedures score forecasts, each with its own windows, horizons, and
  metrics. For Wheat, linear trend, they report MAEs from 677,523 t to
  2,505,181 t (I-1).
- Method selection scores one- and two-year-ahead forecasts from a single
  fit, while every evaluation scores one-year-ahead forecasts with refitting
  (I-2).
- `evaluate_forecasting.py` chooses a winner on the years it reports (I-3).
  The `validation_mae` shown in the dashboard is the winning score on the
  selection years, not an independent estimate (I-4).
- On the holdout, always using naive (median MAE 4,171 t) beats the selected
  method (6,320 t). Selection matches the holdout winner for 64% of crops,
  less often than naive alone does (67%) (I-5).
- Pooled metrics mix scales and provenance. Measured as a percentage of
  production, naive holdout error is 23.2% on official crops and 0.28% on
  crops without official values (I-6).
- Evaluation outputs carry no dataset version, code version, or parameters,
  and are not shipped with the deployment (I-9).

## Recommendations

### P0 — Critical: required before any model comparison is meaningful

| ID | Recommendation | Addresses |
|---|---|---|
| P0-1 | Define **one** forecasting task for evaluation: one-year-ahead annual production per crop, refitted at each origin. Selection, validation, and test should all score this same task. | I-1, I-2 |
| P0-2 | Keep a **final holdout that selection never sees**, as `validate_forecasting.py` does, and forbid choosing any method, parameter, or reporting rule from holdout errors. | I-3, I-4 |
| P0-3 | Select models with a **rolling origin on the pre-holdout years** using the same one-step procedure as P0-1. Do not use the fixed-origin scores from `select_best_method`. | I-2, I-5 |
| P0-4 | Use a **scale-free primary metric**. MASE scales each crop's MAE by the in-sample one-step naive MAE on that crop's training data. It is defined for most crops and directly answers "better than naive?". Keep MAE and RMSE in tonnes as per-crop secondary metrics. | I-6 |
| P0-5 | **Report by provenance.** Headline results should use crops with official values, or report official, no-official, and mixed crops separately. Pooled results across all 92 crops may be shown, but not as the headline. | I-6 |
| P0-6 | Rename or relabel published scores so that a **selection score is never presented as accuracy**. Each metric should state its window, horizon, and role (selection, validation, or test). | I-4 |

### P1 — Important for a reliable, usable framework

| ID | Recommendation | Addresses |
|---|---|---|
| P1-1 | Maintain **naive** as the required baseline. Add **drift**, the naive forecast plus the average historical change, as a cheap trend baseline. Keep **linear trend** for continuity. | I-5 |
| P1-2 | Evaluate the **"always naive"** policy as a competitor to per-crop selection. A selection rule should only be adopted if it beats this policy on rolling origins. | I-5 |
| P1-3 | Aggregate across crops with the **median and the mean of MASE**, plus **win rate against naive**. Add a bootstrap interval or paired test across crops. With 2–6 test years per crop, differences need uncertainty bars. | I-6, I-7 |
| P1-4 | Define **one eligibility rule** (minimum length, contiguity, unit, non-negativity) in one place. Report every excluded crop with a reason in every output. | I-8 |
| P1-5 | Define handling for **degenerate series**. A constant series, or one whose naive MAE is zero, makes MASE undefined. Report such crops separately rather than dividing by zero or dropping them silently. | Data |
| P1-6 | Replace the four scoring loops with **one evaluation engine** in `src/agrimarket/analytics/`. `evaluate_forecasting.py`, `validate_forecasting.py`, and `generate_forecasts.py` should become thin callers. Keep the existing CSV column names until their consumers are updated on purpose (Section 5 of the audit). | I-1, I-10 |
| P1-7 | Add **tests** for: split years and horizons on a hand-built series; the holdout never reaching selection (assert on the years passed to the model); metric values on known inputs; identical crop sets for every method; eligibility and exclusion reasons; regression against the current naive and linear-trend outputs with a tolerance. | I-8, I-10, I-11 |
| P1-8 | Record a **run manifest** with every evaluation: dataset hash, git commit, parameters, method list, eligible and excluded crops, and timestamp. | I-9 |

### P2 — Future, when experimentation grows

| ID | Recommendation |
|---|---|
| P2-1 | Pooled or global models across crops, trained on scale-normalised series. This is the main way to get more training data from a 10-year panel. |
| P2-2 | Damped-trend exponential smoothing as a next local model, compared against naive and drift. |
| P2-3 | Prediction intervals, with interval coverage as a metric. |
| P2-4 | Climate covariates, only with an explicit rule that forecast-year climate is not known at forecast time, and with a documented mapping from locations to national production. |
| P2-5 | A model interface and configuration files, so a new method plugs into the engine without new loops (Phase 5). |
| P2-6 | Experiment tracking such as MLflow over the manifests and reports, once runs are frequent enough to need it (Phase 6). |

## Answers to the Phase 1 questions

1. **Most suitable methodology.** One-step-ahead rolling-origin evaluation
   with expanding windows, plus a final holdout that selection never sees
   (P0-1 to P0-3).
2. **Is the current holdout sufficient?** Its isolation is correct, but two
   years give two errors per crop and one pair of calendar years overall.
   It is sufficient as a final check, not as the only evidence (P1-3).
3. **Selection without leakage.** Rolling origins on pre-holdout years only,
   scored on the same task as the test (P0-3). Policies chosen after looking
   at the holdout, including "always naive", must be confirmed on new data
   or on rolling origins.
4. **Comparing crops of different scales.** MASE as the primary metric,
   raw-unit metrics per crop only, results split by provenance (P0-4, P0-5).
5. **Metrics.** MASE (primary), MAE and RMSE in tonnes (per crop), win rate
   against naive, and later interval coverage. MAPE and sMAPE are not
   recommended as primary metrics: small crops swing by more than 100% and
   percentage errors explode.
6. **Baselines.** Naive (required), drift, and linear trend (P1-1).
7. **Short and incomplete series.** All current series have 10 points and
   no gaps. The eligibility rule should still be explicit and tested
   (P1-4, P1-5), because new data will not necessarily be complete.
8. **What to unify.** Series validation, splitting, the one-step loop,
   metrics, aggregation, exclusion reporting, and output writing (P1-6).
9. **Testing.** As listed in P1-7.
10. **To decide before Phase 2 starts:**
    - Number of selection and holdout years. Three plus three is the
      maximum with a 4-year training minimum; two plus two is the current
      design.
    - Whether the 32 crops without official values are excluded from
      headline metrics or reported as a separate group.
    - Whether MASE uses the in-sample naive scale (standard) or the naive
      forecast's error on the same test years (relative MAE).
    - How the published 2025 forecast and its displayed metric should change,
      if at all. This affects the API, the dashboard, and the AI agent.
    - Whether per-crop method selection is kept, or replaced by one policy
      for all crops chosen on rolling origins.
