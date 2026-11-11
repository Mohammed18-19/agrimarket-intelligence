"""Shared evaluation for every forecasting frequency. Does not use MLflow.

Input is one long DataFrame with the columns

    entity_id   what is forecast, for example a crop
    timestamp   any date inside the period (day, week, month or year)
    target      the numeric value to forecast

and the optional columns ``flag`` (a label per observation, kept in the
predictions table) and ``group`` (a label per entity, used for extra
summary rows, for example data provenance).

Protocol, applied to each entity independently
----------------------------------------------
1. Sort by time and check for duplicate or missing periods.
2. Reserve the last ``holdout_size`` observations as the final holdout.
3. ``stage="validation"`` (default): the model is evaluated on the points
   between the first ``min_train_size`` observations and the holdout. The
   holdout is never read. ``stage="holdout"`` evaluates the reserved points.
   Use it for final reporting only, never to choose a model.
4. Expanding window: for each origin the model is fitted on everything
   before the origin and predicts the next ``horizon`` points.

Entities that cannot be evaluated (too short, gaps, missing values, model
errors, non-finite predictions) are listed in ``result.excluded``.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNS_DIR = PROJECT_ROOT / "experiment_runs"

REQUIRED_COLUMNS = ("entity_id", "timestamp", "target")
PERIOD_CODES = {"daily": "D", "weekly": "W", "monthly": "M", "yearly": "Y"}
STAGES = ("validation", "holdout")
TRAINING_SCOPE = "local: the model is refitted for each entity and each window"


# --------------------------------------------------------------------------
# Metrics (the only place where metric formulas are defined)
# --------------------------------------------------------------------------


def mae(actual, predicted) -> float:
    return float(np.mean(np.abs(np.asarray(actual) - np.asarray(predicted))))


def rmse(actual, predicted) -> float:
    return float(np.sqrt(np.mean((np.asarray(actual) - np.asarray(predicted)) ** 2)))


def naive_scale(history) -> float:
    """Mean absolute one-step change of the training history.

    This is the MASE denominator. It is NaN when it is undefined: fewer than
    two observations, or a constant history (zero denominator).
    """
    history = np.asarray(history, dtype=float)
    if len(history) < 2:
        return float("nan")
    scale = float(np.mean(np.abs(np.diff(history))))
    return scale if scale > 0 else float("nan")


def mase(actual, predicted, scale: float) -> float:
    """MAE divided by ``scale``; NaN, never 0 or inf, when scale is undefined."""
    if not np.isfinite(scale) or scale <= 0:
        return float("nan")
    return mae(actual, predicted) / scale


METRICS = {
    "mae": lambda actual, predicted, scale: mae(actual, predicted),
    "rmse": lambda actual, predicted, scale: rmse(actual, predicted),
    "mase": mase,
}


def compute_metrics(actual, predicted, scale: float, names) -> dict:
    unknown = [name for name in names if name not in METRICS]
    if unknown:
        raise ValueError(f"Unknown metrics {unknown}; available: {sorted(METRICS)}")
    return {name: METRICS[name](actual, predicted, scale) for name in names}


# --------------------------------------------------------------------------
# Settings and result containers
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationSettings:
    min_train_size: int = 4
    holdout_size: int = 2

    def __post_init__(self):
        for name in ("min_train_size", "holdout_size"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")


@dataclass
class EvaluationResult:
    frequency: str
    stage: str
    horizon: int
    settings: EvaluationSettings
    metric_names: tuple
    predictions: pd.DataFrame
    entity_metrics: pd.DataFrame
    summary: pd.DataFrame
    excluded: pd.DataFrame
    aggregates: dict
    diagnostics: dict


# --------------------------------------------------------------------------
# Data checks
# --------------------------------------------------------------------------


def _prepare(data) -> pd.DataFrame:
    if not isinstance(data, pd.DataFrame):
        raise ValueError("data must be a pandas DataFrame")
    missing = [c for c in REQUIRED_COLUMNS if c not in data.columns]
    if missing:
        raise ValueError(f"data is missing required columns: {missing}")
    if data.empty:
        raise ValueError("data has no rows")

    df = data.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="raise")
    if df["timestamp"].isna().any():
        raise ValueError("data contains missing timestamps")
    if df["entity_id"].isna().any():
        raise ValueError("data contains missing entity_id values")
    # Non-numeric targets become NaN and exclude only the affected entity.
    df["target"] = pd.to_numeric(df["target"], errors="coerce")
    return df


def _check_series(series: pd.DataFrame, frequency: str):
    """Return a reason string if the (sorted) series is unusable, else None."""
    target = series["target"]
    if target.isna().any() or not np.isfinite(target.to_numpy(dtype=float)).all():
        return "missing or non-finite target values"

    periods = pd.PeriodIndex(series["timestamp"].dt.to_period(PERIOD_CODES[frequency]))
    steps = np.diff(periods.asi8)
    if (steps == 0).any():
        return "duplicate timestamps"
    if (steps > 1).any():
        return f"missing timestamps ({int((steps - 1).sum())} absent periods)"
    return None


# --------------------------------------------------------------------------
# Evaluation
# --------------------------------------------------------------------------


def _evaluate_entity(series, model, horizon, settings, stage, metric_names):
    """Return (prediction rows, entity info, None) or (None, None, reason)."""
    n = len(series)
    timestamps = series["timestamp"]
    values = series["target"].to_numpy(dtype=float)
    if stage == "validation":
        first_origin, end = settings.min_train_size, n - settings.holdout_size
    else:
        first_origin, end = n - settings.holdout_size, n

    rows = []
    for origin in range(first_origin, end - horizon + 1):
        train = series.iloc[:origin][["entity_id", "timestamp", "target"]].copy()
        try:
            model.fit(train)
            predicted = np.asarray(model.predict(horizon), dtype=float)
        except ValueError as exc:
            return None, None, f"model error at origin {timestamps.iloc[origin - 1].date()}: {exc}"
        if predicted.shape != (horizon,):
            return None, None, f"prediction has shape {predicted.shape}, expected ({horizon},)"
        if not np.isfinite(predicted).all():
            return None, None, f"non-finite prediction at origin {timestamps.iloc[origin - 1].date()}"

        for step in range(horizon):
            index = origin + step
            row = {
                "entity_id": series["entity_id"].iloc[0],
                "origin": timestamps.iloc[origin - 1],
                "timestamp": timestamps.iloc[index],
                "step": step + 1,
                "actual": values[index],
                "predicted": predicted[step],
            }
            if "flag" in series.columns:
                row["flag"] = series["flag"].iloc[index]
            rows.append(row)

    actual = np.array([r["actual"] for r in rows])
    predicted = np.array([r["predicted"] for r in rows])
    scale = naive_scale(values[:first_origin])
    info = {
        "entity_id": series["entity_id"].iloc[0],
        "n_predictions": len(rows),
        "n_train_initial": first_origin,
        "scale": scale,
        # Only data up to the end of the stage is inspected, so a validation
        # run never looks at the reserved holdout.
        "constant_series": bool(np.ptp(values[:end]) == 0),
        **compute_metrics(actual, predicted, scale, metric_names),
        "_train_start": timestamps.iloc[0],
        "_first_train_end": timestamps.iloc[first_origin - 1],
        "_scored_start": timestamps.iloc[first_origin],
        "_scored_end": timestamps.iloc[end - 1],
        "_holdout_start": timestamps.iloc[n - settings.holdout_size],
        "_holdout_end": timestamps.iloc[n - 1],
    }
    if "group" in series.columns:
        info["group"] = series["group"].iloc[0]
    return rows, info, None


def _label(text) -> str:
    return re.sub(r"[^0-9A-Za-z_]+", "_", str(text)).strip("_") or "group"


def _summarize(entity_metrics: pd.DataFrame, metric_names):
    """Median and mean across entities; MASE also gets the share of entities below 1.

    MASE < 1 means the error is smaller than the average one-step change in
    the entity's initial training window. It is not a comparison with the
    naive forecast's out-of-sample error.
    """
    parts = [("all", entity_metrics)]
    if "group" in entity_metrics.columns:
        parts += [(label, sub) for label, sub in entity_metrics.groupby("group", sort=True)]

    rows, aggregates = [], {}
    for label, sub in parts:
        prefix = "" if label == "all" else f"{_label(label)}_"
        for name in metric_names:
            values = sub[name].dropna()
            row = {
                "group": label,
                "metric": name,
                "n_entities": len(sub),
                "n_defined": len(values),
                "median": float(values.median()) if len(values) else float("nan"),
                "mean": float(values.mean()) if len(values) else float("nan"),
                "share_mase_below_1": float("nan"),
            }
            if name == "mase" and len(values):
                row["share_mase_below_1"] = float((values < 1).mean())
            rows.append(row)
            aggregates[f"{prefix}{name}_median"] = row["median"]
            aggregates[f"{prefix}{name}_mean"] = row["mean"]
            aggregates[f"{prefix}{name}_n_defined"] = row["n_defined"]
            if name == "mase":
                aggregates[f"{prefix}mase_share_below_1"] = row["share_mase_below_1"]
    return pd.DataFrame(rows), aggregates


def evaluate(
    data,
    model,
    frequency: str,
    horizon: int,
    settings: EvaluationSettings,
    metrics=("mae", "rmse", "mase"),
    stage: str = "validation",
) -> EvaluationResult:
    """Evaluate ``model`` on ``data`` with an expanding window. See module doc."""
    if frequency not in PERIOD_CODES:
        raise ValueError(f"frequency must be one of {sorted(PERIOD_CODES)}")
    if stage not in STAGES:
        raise ValueError(f"stage must be one of {STAGES}")
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
        raise ValueError("horizon must be a positive integer")
    if settings.holdout_size < horizon:
        raise ValueError("holdout_size must be at least the forecast horizon")
    metrics = tuple(metrics)
    compute_metrics([0.0], [0.0], 1.0, metrics)  # rejects unknown names early

    df = _prepare(data)
    required_length = settings.min_train_size + settings.holdout_size + horizon

    prediction_rows, entity_rows, excluded = [], [], []
    for entity_id, group in df.groupby("entity_id", sort=True):
        series = group.sort_values("timestamp", kind="stable").reset_index(drop=True)
        reason = _check_series(series, frequency)
        if reason is None and len(series) < required_length:
            reason = (
                f"insufficient observations: {len(series)} available, "
                f"{required_length} required"
            )
        if reason is None:
            rows, info, reason = _evaluate_entity(
                series, model, horizon, settings, stage, metrics
            )
        if reason is not None:
            excluded.append({"entity_id": entity_id, "reason": reason})
            continue
        prediction_rows += rows
        entity_rows.append(info)

    if not entity_rows:
        sample = "; ".join(f"{e['entity_id']}: {e['reason']}" for e in excluded[:5])
        raise ValueError(f"No entity could be evaluated. First reasons: {sample}")

    predictions = pd.DataFrame(prediction_rows)
    predictions["error"] = predictions["predicted"] - predictions["actual"]
    predictions["abs_error"] = predictions["error"].abs()

    info = pd.DataFrame(entity_rows)
    stamp_columns = [c for c in info.columns if c.startswith("_")]
    stamps = info[stamp_columns]
    entity_metrics = info.drop(columns=stamp_columns)
    if "group" in entity_metrics.columns:
        entity_metrics.insert(1, "group", entity_metrics.pop("group"))

    summary, aggregates = _summarize(entity_metrics, metrics)
    excluded_df = pd.DataFrame(excluded, columns=["entity_id", "reason"])

    def day(ts):
        return str(pd.Timestamp(ts).date())

    diagnostics = {
        "n_entities_input": int(df["entity_id"].nunique()),
        "n_entities_evaluated": len(entity_metrics),
        "n_excluded": len(excluded_df),
        "n_predictions": len(predictions),
        "n_constant_series": int(entity_metrics["constant_series"].sum()),
        "n_mase_undefined": (
            int(entity_metrics["mase"].isna().sum()) if "mase" in metrics else 0
        ),
        "train_start": day(stamps["_train_start"].min()),
        "first_train_end": day(stamps["_first_train_end"].min()),
        "scored_start": day(stamps["_scored_start"].min()),
        "scored_end": day(stamps["_scored_end"].max()),
        "holdout_start": day(stamps["_holdout_start"].min()),
        "holdout_end": day(stamps["_holdout_end"].max()),
        "holdout_used": stage == "holdout",
    }
    aggregates.update({
        "n_entities": diagnostics["n_entities_evaluated"],
        "n_predictions": diagnostics["n_predictions"],
        "n_excluded": diagnostics["n_excluded"],
        "n_constant_series": diagnostics["n_constant_series"],
        "n_mase_undefined": diagnostics["n_mase_undefined"],
    })

    return EvaluationResult(
        frequency=frequency,
        stage=stage,
        horizon=horizon,
        settings=settings,
        metric_names=metrics,
        predictions=predictions,
        entity_metrics=entity_metrics,
        summary=summary,
        excluded=excluded_df,
        aggregates=aggregates,
        diagnostics=diagnostics,
    )


# --------------------------------------------------------------------------
# Outputs: run directory, tables, plots, text summary
# --------------------------------------------------------------------------


def new_run_dir(frequency: str, root=RUNS_DIR) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    run_dir = Path(root) / frequency / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def make_plots(result: EvaluationResult, out_dir) -> list[Path]:
    """Save the standard diagnostic plots and return their paths."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    title = f"{result.frequency}, {result.stage}"
    predictions, entities = result.predictions, result.entity_metrics
    paths = []

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.scatter(predictions["actual"], predictions["predicted"], s=12, alpha=0.6)
    low = min(predictions["actual"].min(), predictions["predicted"].min())
    high = max(predictions["actual"].max(), predictions["predicted"].max())
    ax.plot([low, high], [low, high], "k--", linewidth=0.8)
    ax.set_xscale("symlog", linthresh=1)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_xlabel("Actual")
    ax.set_ylabel("Predicted")
    ax.set_title(f"Actual vs predicted ({title})")
    paths.append(out_dir / "actual_vs_predicted.png")
    fig.savefig(paths[-1], dpi=110, bbox_inches="tight")
    plt.close(fig)

    scale = predictions["entity_id"].map(entities.set_index("entity_id")["scale"])
    usable = scale > 0
    if usable.any():
        errors = (predictions["error"] / scale)[usable]
        label = "Error / entity naive MAE (scale-free)"
    else:
        errors, label = predictions["error"], "Error (target units)"
    low, high = np.percentile(errors, [1, 99])
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(errors.clip(low, high), bins=30)
    ax.axvline(0, color="k", linewidth=0.8)
    ax.set_xlabel(label + " (clipped to 1st-99th percentile)")
    ax.set_ylabel("Predictions")
    ax.set_title(f"Forecast error distribution ({title})")
    paths.append(out_dir / "error_distribution.png")
    fig.savefig(paths[-1], dpi=110, bbox_inches="tight")
    plt.close(fig)

    primary = "mase" if "mase" in result.metric_names else result.metric_names[0]
    worst = entities.dropna(subset=[primary]).nlargest(20, primary).sort_values(primary)
    if not worst.empty:
        fig, ax = plt.subplots(figsize=(7, 5.5))
        ax.barh(worst["entity_id"].astype(str).str.slice(0, 40), worst[primary])
        ax.set_xlabel(primary.upper())
        ax.set_title(f"20 entities with the largest {primary.upper()} ({title})")
        paths.append(out_dir / "error_by_entity.png")
        fig.savefig(paths[-1], dpi=110, bbox_inches="tight")
        plt.close(fig)
    return paths


def save_outputs(result: EvaluationResult, run_dir, plots: bool = True) -> Path:
    """Write the result tables (and plots) as CSV/PNG files into ``run_dir``."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    result.predictions.to_csv(run_dir / "predictions.csv", index=False)
    result.entity_metrics.to_csv(run_dir / "entity_metrics.csv", index=False)
    result.summary.to_csv(run_dir / "summary.csv", index=False)
    result.excluded.to_csv(run_dir / "excluded.csv", index=False)
    if plots:
        make_plots(result, run_dir / "plots")
    return run_dir


def format_summary(result: EvaluationResult) -> str:
    d = result.diagnostics
    lines = [
        f"{result.frequency} evaluation, stage={result.stage}, horizon={result.horizon}",
        f"  entities evaluated: {d['n_entities_evaluated']} of {d['n_entities_input']} "
        f"({d['n_excluded']} excluded), predictions: {d['n_predictions']}",
        f"  scored {d['scored_start']} to {d['scored_end']}; "
        f"holdout {d['holdout_start']} to {d['holdout_end']} "
        f"({'used' if d['holdout_used'] else 'not used'})",
    ]
    for _, row in result.summary[result.summary["group"] == "all"].iterrows():
        text = f"  {row['metric'].upper():5s} median {row['median']:,.4f}  mean {row['mean']:,.4f}"
        if row["metric"] == "mase":
            text += (
                f"  share below 1: {row['share_mase_below_1']:.1%}"
                f"  (defined for {int(row['n_defined'])} of {int(row['n_entities'])})"
            )
        lines.append(text)
    if result.metric_names and any(m in ("mae", "rmse") for m in result.metric_names):
        lines.append("  MAE/RMSE are in target units and are not comparable across entities.")
    return "\n".join(lines)
