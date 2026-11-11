"""Tests for the experiment framework.

All data here is synthetic and only checks behaviour. None of these numbers
are project results.
"""

import hashlib
import math

import numpy as np
import pandas as pd
import pytest

from agrimarket.analytics.forecasting import forecast_production
from agrimarket.evaluation import evaluation as ev
from agrimarket.evaluation.evaluation import EvaluationSettings, evaluate
from agrimarket.evaluation.models import YearlyModel, YearlyPriceModel

SETTINGS = EvaluationSettings(min_train_size=4, holdout_size=2)


def toy_data(entities=("a", "b"), n=10, first_year=2015):
    rows = []
    for number, name in enumerate(entities, start=1):
        for i in range(n):
            rows.append({
                "entity_id": name,
                "timestamp": pd.Timestamp(year=first_year + i, month=1, day=1),
                "target": 100.0 * number + 10.0 * i + 5.0 * (i % 3),
            })
    return pd.DataFrame(rows)


class SpyModel:
    """Last-value model that records what each fit() call was given."""

    def __init__(self):
        self.calls = []
        self._last = None

    def fit(self, train_data):
        self.calls.append({
            "entity": train_data["entity_id"].iloc[0],
            "first": train_data["timestamp"].min(),
            "last": train_data["timestamp"].max(),
            "size": len(train_data),
        })
        self._last = float(train_data["target"].iloc[-1])
        return self

    def predict(self, horizon):
        return np.full(horizon, self._last)

    def get_params(self):
        return {}


def run(data, model=None, horizon=1, settings=SETTINGS, stage="validation",
        metrics=("mae", "rmse", "mase"), frequency="yearly"):
    return evaluate(data, model or SpyModel(), frequency, horizon, settings, metrics, stage)


# --------------------------------------------------------------------------
# Splits and leakage
# --------------------------------------------------------------------------


def test_validation_splits_are_chronological_and_leave_holdout_unused():
    model = SpyModel()
    result = run(toy_data(), model)

    for entity in ("a", "b"):
        rows = result.predictions[result.predictions["entity_id"] == entity]
        assert rows["timestamp"].dt.year.tolist() == [2019, 2020, 2021, 2022]
        assert rows["origin"].dt.year.tolist() == [2018, 2019, 2020, 2021]
        calls = [c for c in model.calls if c["entity"] == entity]
        assert [c["size"] for c in calls] == [4, 5, 6, 7]  # expanding window
        assert all(c["first"].year == 2015 for c in calls)
    assert max(c["last"].year for c in model.calls) == 2021  # 2023-2024 never used
    assert result.diagnostics["holdout_used"] is False


def test_holdout_stage_scores_only_reserved_years():
    model = SpyModel()
    result = run(toy_data(), model, stage="holdout")

    rows = result.predictions[result.predictions["entity_id"] == "a"]
    assert rows["timestamp"].dt.year.tolist() == [2023, 2024]
    assert [c["size"] for c in model.calls if c["entity"] == "a"] == [8, 9]
    assert result.diagnostics["holdout_used"] is True


def test_training_never_contains_the_period_being_predicted():
    model = SpyModel()
    result = run(toy_data(), model, horizon=2)

    origins = result.predictions[["entity_id", "origin"]].drop_duplicates()
    assert len(origins) == len(model.calls)
    for call, (_, origin) in zip(model.calls, origins.iterrows()):
        assert call["last"] == origin["origin"]
    assert (result.predictions["origin"] < result.predictions["timestamp"]).all()


def test_validation_results_do_not_depend_on_holdout_values():
    data = toy_data()
    poisoned = data.copy()
    poisoned.loc[poisoned["timestamp"] >= "2023-01-01", "target"] = 1e12

    clean, changed = run(data), run(poisoned)

    pd.testing.assert_frame_equal(clean.predictions, changed.predictions)
    pd.testing.assert_frame_equal(clean.entity_metrics, changed.entity_metrics)


def test_horizon_two_scores_two_steps_inside_the_validation_region():
    result = run(toy_data(("a",)), horizon=2)

    rows = result.predictions
    assert rows["step"].tolist() == [1, 2, 1, 2, 1, 2]
    assert rows["timestamp"].dt.year.max() == 2022
    assert len(rows) == 6


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def test_mae_and_rmse_values():
    actual, predicted = [1.0, 2.0, 3.0], [2.0, 2.0, 5.0]
    assert ev.mae(actual, predicted) == pytest.approx(1.0)
    assert ev.rmse(actual, predicted) == pytest.approx(math.sqrt(5 / 3))


def test_mase_value_and_zero_denominator():
    assert ev.naive_scale([1, 3, 6]) == pytest.approx(2.5)
    assert ev.mase([4.0], [6.0], 2.5) == pytest.approx(0.8)

    for history in ([5, 5, 5], [5], []):
        scale = ev.naive_scale(history)
        assert math.isnan(scale)
        assert math.isnan(ev.mase([4.0], [6.0], scale))  # never 0 or inf


def test_unknown_metric_is_rejected():
    with pytest.raises(ValueError, match="Unknown metrics"):
        ev.compute_metrics([1.0], [1.0], 1.0, ("mae", "mape"))
    with pytest.raises(ValueError, match="Unknown metrics"):
        run(toy_data(), metrics=("mape",))


def test_constant_series_has_undefined_mase_and_is_left_out_of_its_aggregate():
    data = pd.concat([toy_data(("a", "b")), toy_data(("flat",)).assign(target=7.0)])
    result = run(data)

    flat = result.entity_metrics.set_index("entity_id").loc["flat"]
    assert flat["constant_series"]
    assert flat["mae"] == 0.0
    assert math.isnan(flat["mase"])
    assert result.diagnostics["n_mase_undefined"] == 1
    assert result.aggregates["mase_n_defined"] == 2
    assert result.aggregates["mae_n_defined"] == 3
    expected = result.entity_metrics.dropna(subset=["mase"])["mase"].median()
    assert result.aggregates["mase_median"] == pytest.approx(expected)


def test_entity_metrics_match_a_manual_calculation():
    # one entity, values 10, 20, 30, 40, 50, 60, 70, 80, 90, 100; last-value forecast
    data = toy_data(("a",)).assign(target=[10.0 * (i + 1) for i in range(10)])
    row = run(data).entity_metrics.iloc[0]

    # validation targets 50, 60, 70, 80 are each predicted by the value 10 lower
    assert row["mae"] == pytest.approx(10.0)
    assert row["rmse"] == pytest.approx(10.0)
    assert row["scale"] == pytest.approx(10.0)  # mean |diff| of the first four values
    assert row["mase"] == pytest.approx(1.0)


# --------------------------------------------------------------------------
# Reproducibility, output format, grouping
# --------------------------------------------------------------------------


def test_identical_inputs_give_identical_results():
    data = toy_data(("a", "b", "c"))
    first = run(data, YearlyModel("linear_trend"))
    second = run(data, YearlyModel("linear_trend"))

    pd.testing.assert_frame_equal(first.predictions, second.predictions)
    pd.testing.assert_frame_equal(first.entity_metrics, second.entity_metrics)
    pd.testing.assert_frame_equal(first.summary, second.summary)
    assert first.aggregates == second.aggregates


def test_prediction_table_has_a_consistent_format():
    result = run(toy_data())

    expected = ["entity_id", "origin", "timestamp", "step", "actual", "predicted",
                "error", "abs_error"]
    assert list(result.predictions.columns) == expected
    assert (result.predictions["error"]
            == result.predictions["predicted"] - result.predictions["actual"]).all()
    assert result.predictions["abs_error"].ge(0).all()
    assert result.predictions.equals(
        result.predictions.sort_values(["entity_id", "timestamp"]).reset_index(drop=True)
    )
    assert list(result.entity_metrics.columns) == [
        "entity_id", "n_predictions", "n_train_initial", "scale",
        "constant_series", "mae", "rmse", "mase",
    ]
    assert result.diagnostics["n_predictions"] == len(result.predictions) == 8


def test_flag_and_group_columns_are_kept_and_summarised():
    data = toy_data(("a", "b", "c"))
    data["flag"] = "A"
    data["group"] = data["entity_id"].map({"a": "official", "b": "official", "c": "estimated"})
    result = run(data)

    assert "flag" in result.predictions.columns
    assert set(result.entity_metrics["group"]) == {"official", "estimated"}
    assert set(result.summary["group"]) == {"all", "official", "estimated"}
    assert "official_mase_median" in result.aggregates
    assert "estimated_mae_median" in result.aggregates


# --------------------------------------------------------------------------
# Input problems
# --------------------------------------------------------------------------


def test_insufficient_data_excludes_only_the_short_entity():
    data = pd.concat([toy_data(("a",)), toy_data(("short",), n=6)])
    result = run(data)

    assert result.entity_metrics["entity_id"].tolist() == ["a"]
    assert result.excluded["entity_id"].tolist() == ["short"]
    assert "insufficient observations" in result.excluded["reason"].iloc[0]
    assert result.diagnostics["n_excluded"] == 1


def test_nothing_evaluable_raises_a_clear_error():
    with pytest.raises(ValueError, match="No entity could be evaluated.*insufficient"):
        run(toy_data(n=6))


@pytest.mark.parametrize("damage, reason", [
    ("duplicate", "duplicate timestamps"),
    ("gap", "missing timestamps"),
    ("nan", "missing or non-finite target"),
    ("inf", "missing or non-finite target"),
])
def test_bad_series_are_excluded_with_a_reason(damage, reason):
    data = toy_data(("good", "bad"))
    bad = data["entity_id"] == "bad"
    if damage == "duplicate":
        data = pd.concat([data, data[bad].iloc[[3]]])
    elif damage == "gap":
        data = data[~(bad & (data["timestamp"].dt.year == 2018))]
    elif damage == "nan":
        data.loc[bad & (data["timestamp"].dt.year == 2017), "target"] = np.nan
    else:
        data.loc[bad & (data["timestamp"].dt.year == 2017), "target"] = np.inf

    result = run(data)

    assert result.entity_metrics["entity_id"].tolist() == ["good"]
    assert reason in result.excluded.set_index("entity_id").loc["bad", "reason"]


def test_unsorted_input_is_sorted_chronologically():
    data = toy_data(("a",))
    shuffled = data.sample(frac=1.0, random_state=0)

    pd.testing.assert_frame_equal(run(data).predictions, run(shuffled).predictions)


class NanModel(SpyModel):
    def predict(self, horizon):
        return np.full(horizon, np.nan)


class FailingModel(SpyModel):
    def fit(self, train_data):
        raise ValueError("cannot fit this series")


def test_non_finite_predictions_are_never_scored():
    with pytest.raises(ValueError, match="non-finite prediction"):
        run(toy_data(), NanModel())


def test_model_errors_are_reported_as_exclusions():
    with pytest.raises(ValueError, match="cannot fit this series"):
        run(toy_data(), FailingModel())


@pytest.mark.parametrize("kwargs, message", [
    ({"frequency": "hourly"}, "frequency must be"),
    ({"stage": "test"}, "stage must be"),
    ({"horizon": 0}, "horizon must be"),
    ({"horizon": 3}, "holdout_size must be at least"),
])
def test_invalid_arguments_are_rejected(kwargs, message):
    with pytest.raises(ValueError, match=message):
        run(toy_data(), **kwargs)


def test_missing_columns_and_empty_data_are_rejected():
    with pytest.raises(ValueError, match="missing required columns"):
        run(toy_data().drop(columns="target"))
    with pytest.raises(ValueError, match="no rows"):
        run(toy_data().iloc[0:0])
    with pytest.raises(ValueError, match="positive integer"):
        EvaluationSettings(min_train_size=0)


# --------------------------------------------------------------------------
# Models and frequencies
# --------------------------------------------------------------------------


def test_yearly_model_wraps_the_existing_baselines():
    series = toy_data(("a",)).iloc[:8]
    frame = pd.DataFrame({
        "Item": "x", "Year": series["timestamp"].dt.year, "Unit": "t", "Value": series["target"],
    })

    naive = YearlyModel("naive").fit(series)
    assert naive.predict(2)[0] == series["target"].iloc[-1]

    trend = YearlyModel("linear_trend").fit(series)
    expected = [forecast_production(frame, "x", 2023 + step, "linear_trend")["predicted_production"]
                for step in range(2)]
    assert trend.predict(2) == pytest.approx(expected)
    assert trend.get_params() == {"method": "linear_trend"}
    assert "trend" in trend.describe().lower()


def test_fitting_again_replaces_the_previous_fit():
    model = YearlyModel("naive")
    data = toy_data(("a",))
    model.fit(data.iloc[:5])
    first = model.predict(1)[0]
    model.fit(data.iloc[:8])
    assert model.predict(1)[0] != first


@pytest.mark.parametrize("frequency, date_freq", [
    ("daily", "D"),
    ("weekly", "W"),
    ("monthly", "MS"),
])
def test_other_frequencies_run_on_synthetic_data(frequency, date_freq):
    dates = pd.date_range("2020-01-01", periods=12, freq=date_freq)
    data = pd.DataFrame({"entity_id": "s", "timestamp": dates, "target": np.arange(12.0) ** 1.5})

    result = run(data, SpyModel(), frequency=frequency, metrics=("mae", "rmse"))

    assert result.diagnostics["n_predictions"] == 6
    assert set(result.entity_metrics.columns) >= {"mae", "rmse"}
    assert "mase" not in result.entity_metrics.columns


def test_a_missing_month_is_detected_for_monthly_data():
    dates = pd.date_range("2020-01-01", periods=14, freq="MS").delete(5)
    data = pd.DataFrame({"entity_id": "s", "timestamp": dates, "target": np.arange(13.0)})

    with pytest.raises(ValueError, match="missing timestamps"):
        run(data, SpyModel(), frequency="monthly")


# --------------------------------------------------------------------------
# Saved outputs and MLflow
# --------------------------------------------------------------------------


def test_outputs_and_plots_are_written(tmp_path):
    pytest.importorskip("matplotlib")
    run_dir = ev.save_outputs(run(toy_data()), tmp_path / "run")

    for name in ("predictions.csv", "entity_metrics.csv", "summary.csv", "excluded.csv",
                 "plots/actual_vs_predicted.png", "plots/error_distribution.png",
                 "plots/error_by_entity.png"):
        assert (run_dir / name).is_file(), name
    saved = pd.read_csv(run_dir / "predictions.csv")
    assert len(saved) == 8


def test_summary_text_is_available():
    text = ev.format_summary(run(toy_data()))
    assert "entities evaluated: 2 of 2" in text and "MASE" in text


def test_mlflow_logging(tmp_path):
    tracking = pytest.importorskip("agrimarket.evaluation.tracking")
    mlflow = pytest.importorskip("mlflow")
    pytest.importorskip("matplotlib")

    dataset = tmp_path / "toy.csv"
    toy_data(("a", "b")).to_csv(dataset, index=False)
    uri = f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}"

    def log_once():
        model = YearlyModel("linear_trend")
        result = run(toy_data(("a", "b", "flat")).assign(
            target=lambda d: d["target"].where(d["entity_id"] != "flat", 3.0)), model)
        run_dir = ev.save_outputs(result, ev.new_run_dir("yearly", tmp_path / "runs"))
        return tracking.log_experiment(
            result, model, dataset, run_dir, "toy_target", "units",
            tracking_uri=uri, artifact_root=tmp_path / "artifacts",
        )

    first, second = log_once(), log_once()
    assert first != second  # every execution is a new run

    client = mlflow.MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name("agrimarket-yearly")
    assert len(client.search_runs([experiment.experiment_id])) == 2

    run_data = client.get_run(first).data
    params = run_data.params
    assert params["model_class"] == "YearlyModel"
    assert params["model.method"] == "linear_trend"
    assert params["frequency"] == "yearly" and params["horizon"] == "1"
    assert params["evaluation_stage"] == "validation"
    assert params["min_train_size"] == "4" and params["holdout_size"] == "2"
    assert params["dataset_hash"] == hashlib.sha256(dataset.read_bytes()).hexdigest()
    assert params["git_commit"] and params["git_uncommitted_changes"] in {"True", "False", "unknown"}
    assert params["scored_start"] == "2019-01-01" and params["holdout_start"] == "2023-01-01"
    assert params["target_name"] == "toy_target"

    metrics = run_data.metrics
    assert metrics["validation_n_entities"] == 3
    assert metrics["validation_n_predictions"] == 12
    assert metrics["validation_mae_median"] >= 0
    assert metrics["validation_n_mase_undefined"] == 1
    assert not any(name.startswith("holdout_") for name in metrics)
    assert all(math.isfinite(value) for value in metrics.values())  # no NaN logged

    names = {item.path for item in client.list_artifacts(first)}
    assert {"predictions.csv", "entity_metrics.csv", "model_source.py",
            "experiment_metadata.json", "plots"} <= names


# --------------------------------------------------------------------------
# Yearly price model and script
# --------------------------------------------------------------------------


def test_price_model_naive_and_drift_forecasts():
    series = pd.DataFrame({
        "timestamp": pd.date_range("2015-01-01", periods=5, freq="YS"),
        "target": [100.0, 110.0, 120.0, 130.0, 140.0],
    })

    assert YearlyPriceModel("naive").fit(series).predict(3) == pytest.approx([140.0] * 3)
    # Average change is 10 per year, so the line continues from the last value.
    assert YearlyPriceModel("drift").fit(series).predict(3) == pytest.approx([150.0, 160.0, 170.0])

    model = YearlyPriceModel("drift")
    assert model.get_params() == {"method": "drift"}
    assert "change" in model.describe().lower()
    # Refitting replaces the previous fit.
    model.fit(series.iloc[:3])
    assert model.predict(1) == pytest.approx([130.0])


def test_price_model_rejects_unknown_method():
    with pytest.raises(ValueError, match="method"):
        YearlyPriceModel("magic")


def test_drift_follows_a_straight_line_exactly_while_naive_does_not():
    data = pd.DataFrame({
        "entity_id": "crop",
        "timestamp": pd.date_range("2015-01-01", periods=10, freq="YS"),
        "target": 50.0 + 5.0 * np.arange(10),
    })

    drift = run(data, YearlyPriceModel("drift"))
    naive = run(data, YearlyPriceModel("naive"))

    assert drift.aggregates["mae_median"] == pytest.approx(0.0)
    assert naive.aggregates["mae_median"] == pytest.approx(5.0)


def _price_file(path, **overrides):
    rows = []
    for item in ("Wheat", "Olives"):
        for year in range(2015, 2025):
            rows.append({
                "Area": "Morocco",
                "Element": "Producer Price (USD/tonne)",
                "Item": item,
                "Year": year,
                "Months": "Annual value",
                "Unit": "USD",
                "Value": 100.0 + year - 2015,
                "Flag": "A",
            })
    frame = pd.DataFrame(rows)
    for column, value in overrides.items():
        frame.loc[frame.index[0], column] = value
    frame.to_csv(path, index=False)
    return path


def _load_price_script():
    import importlib.util
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_yearly_prices.py"
    spec = importlib.util.spec_from_file_location("evaluate_yearly_prices", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_price_loader_adapts_columns_and_reads_the_unit(tmp_path):
    script = _load_price_script()
    data, unit = script.load_price_data(_price_file(tmp_path / "prices.csv"))

    assert unit == "USD/tonne"
    assert list(data.columns) == ["entity_id", "timestamp", "target", "flag", "group"]
    assert sorted(data["entity_id"].unique()) == ["Olives", "Wheat"]
    assert data["timestamp"].min() == pd.Timestamp("2015-01-01")
    assert set(data["group"]) == {"official"}


@pytest.mark.parametrize("column, value, message", [
    ("Months", "January", "annual"),
    ("Area", "Elsewhere", "Area"),
    ("Element", "Producer Price (LCU/tonne)", "Element"),
])
def test_price_loader_refuses_mixed_areas_units_or_periods(tmp_path, column, value, message):
    script = _load_price_script()
    path = _price_file(tmp_path / "prices.csv", **{column: value})

    with pytest.raises(ValueError, match=message):
        script.load_price_data(path)


def test_price_experiment_has_its_own_mlflow_experiment(tmp_path):
    tracking = pytest.importorskip("agrimarket.evaluation.tracking")
    mlflow = pytest.importorskip("mlflow")
    pytest.importorskip("matplotlib")

    dataset = tmp_path / "prices.csv"
    toy_data(("a", "b")).to_csv(dataset, index=False)
    uri = f"sqlite:///{(tmp_path / 'mlflow.db').as_posix()}"

    model = YearlyPriceModel("drift")
    result = run(toy_data(("a", "b")), model)
    run_dir = ev.save_outputs(result, ev.new_run_dir("yearly_prices", tmp_path / "runs"))
    run_id = tracking.log_experiment(
        result, model, dataset, run_dir, "producer_price", "USD/tonne",
        tracking_uri=uri, artifact_root=tmp_path / "artifacts",
        experiment_name="agrimarket-yearly-prices",
    )

    client = mlflow.MlflowClient(tracking_uri=uri)
    experiment = client.get_experiment_by_name("agrimarket-yearly-prices")
    assert [r.info.run_id for r in client.search_runs([experiment.experiment_id])] == [run_id]
    assert client.get_experiment_by_name("agrimarket-yearly") is None
    params = client.get_run(run_id).data.params
    assert params["model_class"] == "YearlyPriceModel"
    assert params["target_unit"] == "USD/tonne"
