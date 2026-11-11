# ML evaluation roadmap

This roadmap is provisional. Each phase's findings may change the phases
that follow; changes should be recorded here.

| Phase | Title | Status |
|---|---|---|
| 1 | [Dataset EDA and existing evaluation audit](#phase-1-dataset-eda-and-existing-evaluation-audit) | Not part of this change |
| 2 | [Evaluation protocol design](#phase-2-evaluation-protocol-design) | Planned |
| 3 | [Unified evaluation implementation](#phase-3-unified-evaluation-implementation) | Early implementation |
| 4 | [Experiment reporting and reproducibility](#phase-4-experiment-reporting-and-reproducibility) | Early implementation |
| 5 | [Extensible experiment interface](#phase-5-extensible-experiment-interface) | Early implementation |
| 6 | [Optional MLflow integration](#phase-6-optional-mlflow-integration) | Early implementation |

**Early implementation.** A first lightweight framework in
`src/agrimarket/evaluation/` and `scripts/evaluate_yearly.py` touches
Phases 3 to 6 at once, before the Phase 2 specification exists. See
[experiment_framework.md](experiment_framework.md). Its rules (windows,
minimum history, holdout size) are provisional and Phase 2 may change them.
It does not change the existing evaluation scripts, `select_best_method` or
`generate_forecasts.py`. The framework deliberately uses plain Python
constants and model classes instead of the configuration files and
configuration entries mentioned under Phases 4 and 5. Each phase
below notes what exists and what is still open.

---

## Phase 1: Dataset EDA and existing evaluation audit

**Status:** Not part of this change. No EDA or audit material is included
here; the objective and tasks below are kept so the later phases still read
in order.

**Objective:** Understand the forecasting data, models, preprocessing, and
current evaluation methodology.

**Motivation:** An evaluation framework designed without knowing the data
and the existing code would encode wrong assumptions, for example about
series length, scale, or what the published metrics mean.

**Key tasks**

- Explore datasets and target variables.
- Analyse data quality and historical coverage.
- Investigate time-series characteristics.
- Audit existing evaluation functions and scripts.
- Identify inconsistent evaluations, potential leakage, and unreliable metrics.
- Assess the feasibility of different model families.
- Document findings and recommendations.

**Deliverables:** dataset analysis, code audit, prioritised
recommendations.

**Depends on:** nothing.

**Done when:** every evaluation entry point is documented with its splits,
horizon, metrics, and consumers; data limitations are quantified; and the
recommendations have been reviewed.

---

## Phase 2: Evaluation protocol design

**Status:** Planned.

**Objective:** Define a sound, consistent forecasting evaluation method.

**Motivation:** The existing scripts score forecasts with different splits,
horizons and metrics, selection is scored differently from testing, and
pooled metrics are dominated by scale and data provenance.

**Key tasks**

- Define the forecasting task and prediction horizon.
- Choose chronological training, validation, and test strategies.
- Decide whether rolling-origin evaluation and a final holdout are both used.
- Establish a model-selection method.
- Define baseline models.
- Select metrics and aggregation rules.
- Define eligibility and leakage-prevention rules.
- Specify evaluation outputs.

**Deliverables:** evaluation specification, metric definitions, benchmark
rules, and requirements for the Phase 3 implementation.

**Depends on:** Phase 1.

**Done when:** a contributor could implement the evaluation engine from the
specification alone, and every open design question above is decided with
a reason.

---

## Phase 3: Unified evaluation implementation

**Status:** Early implementation. `evaluation.py` provides one engine
(expanding-window backtesting, MAE, RMSE, MASE, leakage and input checks) with
tests on synthetic data, used by `scripts/evaluate_yearly.py`. It supports
daily, weekly and monthly data in principle, but no such data exists, so there
are no scripts for them. The old evaluation scripts are not yet refactored
onto it, and the old `select_best_method` procedure is unchanged. Still open:
moving them onto the engine and aligning it with the Phase 2 specification.

**Objective:** One evaluation engine used by every forecasting method.

**Motivation:** Today each script has its own loop and eligibility rules.

**Key tasks**

- Refactor existing evaluation code.
- Remove inconsistent evaluation implementations.
- Introduce reusable model evaluation functions.
- Standardise backtesting and metric computation.
- Preserve compatibility with existing forecasting outputs and their
  consumers.
- Add unit tests for metrics, leakage prevention, splits, and
  reproducibility.

**Deliverables:** reusable evaluation module, updated scripts, automated
tests.

**Depends on:** Phase 2 specification.

**Done when:** all evaluation scripts call the engine, its tests encode the
Phase 2 rules, and existing outputs either match or differ only where the
specification says they should.

---

## Phase 4: Experiment reporting and reproducibility

**Status:** Early implementation. Each run writes predictions, entity
metrics, summaries, exclusions, plots, the model source and metadata (dataset
hash, git commit, parameters) to a new directory. Still open: a manifest
that lists eligible crops and methods, a reproduction tolerance, and a
documented decision on configuration files.

**Objective:** Make every experiment repeatable, traceable, and comparable.

**Motivation:** Current evaluation outputs are overwritten in place, with no
record of data version, code version, or parameters.

**Key tasks**

- Introduce configuration files.
- Record experiment parameters.
- Save individual predictions and actual values.
- Generate standard metric tables.
- Generate diagnostic plots.
- Save run metadata such as the dataset hash and git commit.
- Create structured experiment output directories.
- Document how to run and reproduce experiments.

**Deliverables:** evaluation command-line interface, configuration format,
plots, summary reports, run manifests.

**Depends on:** Phase 3 engine.

**Done when:** any reported number can be traced to a manifest, and
re-running a manifest reproduces it within a stated tolerance.

---

## Phase 5: Extensible experiment interface

**Status:** Early implementation. `models.py` has two classes, `YearlyModel`
(production) and `YearlyPriceModel` (annual producer price, with `naive` and
`drift`), each with `fit`, `predict`, `get_params` and `describe`, edited by
hand. `YearlyModel` wraps the existing baselines. A model for another frequency
is added as another plain class when data for it exists. Still open: further
baselines, hyperparameter search, and a decision on whether a registry is
ever needed.

**Objective:** Let new models be added and compared without changing
evaluation code.

**Motivation:** Feasible next model families (drift, damped exponential
smoothing, pooled models) should share one evaluation path.

**Key tasks**

- Define a common forecasting model interface.
- Support new models without rewriting evaluation logic.
- Support model-specific configuration.
- Design optional logging of training and validation loss.
- Provide consistent model and experiment comparisons.
- Prepare for hyperparameter search.

**Deliverables:** model interface, model integration guide, comparison
workflow.

**Depends on:** Phases 3 and 4.

**Done when:** a new baseline can be added by implementing the interface
and a configuration entry only, and appears in the standard report.

---

## Phase 6: Optional MLflow integration

**Status:** Early implementation. `tracking.py` logs one local MLflow run
per execution (SQLite backend, one experiment per frequency). The evaluation
engine does not import MLflow. Still open: judging whether MLflow gives
practical benefits over file-based reports, once more models and datasets exist.

**Objective:** Add richer experiment tracking and visualisation once the
framework is mature.

**Motivation:** Useful only when runs are frequent enough that manifests
and reports become hard to compare by hand.

**Key tasks**

- Evaluate whether MLflow provides practical benefits over Phase 4 reports.
- Add optional local tracking.
- Log parameters, metrics, plots, and artefacts.
- Compare experiments in the MLflow interface.
- Keep the core evaluation independent of MLflow.

**Deliverables:** optional MLflow integration and its documentation, or a
documented decision not to adopt it.

**Depends on:** Phases 4 and 5.

**Done when:** the evaluation runs identically with and without MLflow
installed, and a logged run can be traced to its manifest.
