import pandas as pd
import pytest

from agrimarket.analytics.forecasting import (
    evaluate_forecast,
    forecast_production,
    select_best_method,
)


@pytest.fixture
def wheat_data():
    return pd.DataFrame({
        "Item": ["Wheat"] * 6,
        "Year": [2015, 2016, 2017, 2018, 2019, 2020],
        "Unit": ["t"] * 6,
        "Value": [100.0, 110.0, 105.0, 120.0, 115.0, 130.0],
    })


def test_naive_forecast_uses_last_observation(wheat_data):
    result = forecast_production(wheat_data, "Wheat", 2021)
    assert result["predicted_production"] == 130.0
    assert result["training_end_year"] == 2020
    assert result["unit"] == "t"


def test_linear_trend_returns_nonnegative_forecast(wheat_data):
    result = forecast_production(
        wheat_data, "Wheat", 2021, method="linear_trend"
    )
    assert result["predicted_production"] >= 0
    assert result["method"] == "linear_trend"


def test_unknown_crop_is_rejected(wheat_data):
    with pytest.raises(ValueError, match="No production data"):
        forecast_production(wheat_data, "Rice", 2021)


def test_target_year_must_be_future(wheat_data):
    with pytest.raises(ValueError, match="later than"):
        forecast_production(wheat_data, "Wheat", 2020)


def test_unknown_method_is_rejected(wheat_data):
    with pytest.raises(ValueError, match="method must be"):
        forecast_production(wheat_data, "Wheat", 2021, method="random_forest")


def test_missing_year_is_rejected(wheat_data):
    broken = wheat_data[wheat_data["Year"] != 2017]
    with pytest.raises(ValueError, match="missing years"):
        forecast_production(broken, "Wheat", 2021)


def test_negative_production_is_rejected(wheat_data):
    broken = wheat_data.copy()
    broken.loc[0, "Value"] = -1
    with pytest.raises(ValueError, match="negative production"):
        forecast_production(broken, "Wheat", 2021)


def test_chronological_evaluation_returns_metrics(wheat_data):
    result = evaluate_forecast(wheat_data, "Wheat", method="naive", test_size=2)
    assert result["test_size"] == 2
    assert result["mae"] >= 0
    assert result["rmse"] >= result["mae"]
    assert [row["year"] for row in result["predictions"]] == [2019, 2020]


def test_select_best_method_returns_valid_result(wheat_data):
    result = select_best_method(wheat_data, "Wheat", selection_test_size=2)
    assert result["best_method"] in {"naive", "linear_trend"}
    assert result["validation_mae"] >= 0
    assert set(result["validation_scores"]) == {"naive", "linear_trend"}
    assert result["selection_training_end_year"] < result["validation_start_year"]


def test_select_best_method_rejects_unknown_crop(wheat_data):
    with pytest.raises(ValueError, match="No production data"):
        select_best_method(wheat_data, "Rice")


def test_select_best_method_rejects_invalid_test_size(wheat_data):
    with pytest.raises(ValueError, match="positive integer"):
        select_best_method(wheat_data, "Wheat", selection_test_size=0)
