# Phase 1: Dataset EDA and forecasting evaluation audit

**Status:** In progress. The analysis is complete and awaiting review
before Phase 2 begins.

## Objective

Understand the data the forecasts are built on and how forecasts are
currently evaluated, then identify what must be decided before a common
evaluation framework is designed.

## Scope

Included:

- The production dataset read by the forecasting pipeline.
- `src/agrimarket/analytics/forecasting.py` and the three forecasting
  scripts.
- Every application component that reads forecasting outputs.

Excluded:

- Any change to forecasting or evaluation behaviour.
- New models.
- Evaluation protocol design (Phase 2).

## Documents

| Document | Content |
|---|---|
| [dataset_eda.md](dataset_eda.md) | Structure, data quality, provenance, time-series behaviour, feasibility of evaluation designs |
| [forecasting_code_audit.md](forecasting_code_audit.md) | Data flow, models, the four evaluation procedures compared, consumers, confirmed issues I-1 to I-11 |
| [findings_and_recommendations.md](findings_and_recommendations.md) | Summary and P0/P1/P2 recommendations for Phase 2 |
| [figures/](figures/) | Eight PNG figures used in the EDA report |
| [results/](results/) | Summary tables (CSV) behind every number in the documents |

## Scripts

The EDA script is read-only with respect to `data/`. It writes only to this
phase's `figures/` and `results/` directories.

| Script | Produces | Needs |
|---|---|---|
| [`scripts/forecasting/eda_forecasting.py`](../../../scripts/forecasting/eda_forecasting.py) | All figures; `dataset_overview`, `column_profile`, `crop_series_summary`, `year_summary`, `flag_summary`, `evaluation_eligibility`, `abrupt_changes`, `raw_vs_processed`, `climate_coverage` | pandas, NumPy, Matplotlib |

`audit_checks.csv` and `audit_per_crop_metrics.csv` were produced by an audit
script that ran the then-existing evaluation scripts. That script and those
scripts have since been removed (see the note below), so these two files are a
fixed record of the audit and are not regenerated.

Inputs:

- `data/processed/faostat_morocco_production.csv`, committed.
- `data/processed/nasa_power_annual.csv`, committed; used for coverage only.
- `data/raw/faostat_morocco_crops.csv`, optional; not in the repository.

## Reproduce

From the repository root, with the project installed:

```bash
pip install -e ".[dev,eda]"
python scripts/forecasting/eda_forecasting.py
```

The EDA script takes `--data`, `--raw`, `--climate`, and `--output-dir` to
point at other files. It produces identical files on repeated runs.

## Note: code removed after this audit

The audit describes the evaluation code as it was in commit `20af93f`.
Afterwards the old evaluation entry points were removed in favour of the
[experiment framework](../experiment_framework.md):

| Removed | Replaced by |
|---|---|
| `scripts/evaluate_forecasting.py` | `scripts/evaluate_yearly.py` |
| `scripts/validate_forecasting.py` | `scripts/evaluate_yearly.py` (`--final-test` for the holdout) |
| `forecasting.evaluate_forecast` and its test | `src/agrimarket/evaluation/evaluation.py` |
| `forecasting.select_best_method` and its tests | explicit production model constants in `scripts/generate_forecasts.py` |
| `scripts/forecasting/audit_forecasting_evaluation.py` | nothing; its results are kept in `results/` |

`scripts/generate_forecasts.py` still produces the published forecasts, but
now uses one reviewed model version for every crop. To re-run the removed
evaluation and selection code, check out commit `20af93f`. The audit script
was never committed, so it is not available there.

References below to the removed files, and the line numbers in the audit,
refer to that commit.

## Key findings

- **Data:** 92 crops × 10 years (2015–2024), complete, all in tonnes.
  32 crops have no official values and are nearly smooth. Officially
  reported cereals and pulses double or halve frequently.
- **Evaluation:** four independent scoring procedures that disagree on
  windows, horizons, and metrics. A selection score is published as
  "Validation MAE". One script picks a winner on its own test years. On
  the holdout, per-crop selection is worse than always using naive.
- **Reproducibility:** committed forecasts and documented holdout medians
  reproduce from the committed data. Evaluation outputs are not versioned
  or shipped.

See [findings_and_recommendations.md](findings_and_recommendations.md).

## Known limitations

- The raw FAOSTAT export is not in the repository, so what preprocessing
  removed could not be measured.
- The live deployment was not inspected. The statement that evaluation files
  are absent there is inferred from `render.yaml` and `.gitignore`.
- Explanations of production swings (for example drought) are not testable
  with this dataset and are marked as interpretation.
- The application's API and AI test modules were not run in this
  environment because their dependencies (`python-dotenv`, `requests`,
  LangGraph) were not installed. No application code was changed.

## Next steps

1. Review the recommendations and the open questions in
   [findings_and_recommendations.md](findings_and_recommendations.md#answers-to-the-phase-1-questions).
2. Start Phase 2:
   [evaluation protocol design](../roadmap.md#phase-2-evaluation-protocol-design).
