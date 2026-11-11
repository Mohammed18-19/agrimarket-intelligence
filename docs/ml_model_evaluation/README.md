# ML model evaluation

This directory documents the work to give AgriMarket Intelligence a
reliable, reproducible way to evaluate and compare crop production
forecasting models.

## Background

The project publishes one-year-ahead production forecasts for 92 Moroccan
crops, built from FAOSTAT data for 2015–2024 using two simple methods:
last value (`naive`) and a straight-line trend (`linear_trend`). The
forecasts and their error metrics are shown in the API, the dashboard, and
the AI advisor. See [docs/forecasting.md](../forecasting.md) for the
current user-facing description.

## Objective

The goal is not, in the first place, to make forecasts more accurate. It is
to make sure that any model, existing or future, is evaluated on the same
task, with the same data splits and the same metrics, so that a reported
improvement is real and a published error figure means what it says.

## Why this is needed

Before this framework, forecasts were scored by separate scripts
(`scripts/evaluate_forecasting.py`, `scripts/validate_forecasting.py` and the
method selection used by `scripts/generate_forecasts.py`), each with its own
years, horizon and metrics. Their error figures are therefore not comparable
with each other, and the error shown next to a forecast comes from method
selection rather than from an independent test. Cross-crop medians also mix
scales from tens of tonnes to millions of tonnes.

With only ten annual observations per crop, every evaluation choice has a
large effect on the conclusions. That is why the methodology is fixed
before new models are added.

## Intended outcomes

- One documented evaluation protocol.
- One evaluation engine, with tests that enforce the protocol.
- Reports with predictions, metrics, plots, and a manifest that ties them to
  a dataset hash and git commit.
- An interface for adding models without new evaluation code.
- Optional experiment tracking on top of the above.

## Phases

| Phase | Focus | Status |
|---|---|---|
| 1 | Dataset EDA and audit of existing evaluation | Not part of this change |
| 2 | Evaluation protocol design | Planned |
| 3 | Unified evaluation engine and tests | Early implementation (yearly only, provisional) |
| 4 | Reporting and reproducibility | Early implementation (run files and metadata) |
| 5 | Extensible experiment interface | Early implementation (plain model classes) |
| 6 | Optional MLflow integration | Early implementation (local tracking) |

Objectives, dependencies, and completion criteria for each phase are in the
[roadmap](roadmap.md).

## Experiment framework (early implementation)

A first lightweight framework exists for trying models by hand under fixed
rules and comparing runs in MLflow: see
[experiment_framework.md](experiment_framework.md) for the files, the
commands, how to change a model, and the current limitations. Only yearly
forecasting has real data. It was built before Phase 2 was written, so its
rules are provisional.

## Navigating this directory

```text
ml_model_evaluation/
├── README.md                     this page
├── roadmap.md                    all phases, status, completion criteria
└── experiment_framework.md       models, evaluation, tracking: how to run it
```

Directories for later phases are created when that phase starts.

- Want to run an evaluation? Read
  [experiment_framework.md](experiment_framework.md).
- Planning evaluation work? Read the [roadmap](roadmap.md).
