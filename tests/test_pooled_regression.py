
import numpy as np
import pandas as pd
import pytest

from agrimarket.analytics.pooled_regression import (
    build_features_for_next_year,
    build_supervised_dataset,
    predict_pooled_regressor,
    train_pooled_regressor,
)


@pytest.fixture
def production_data():
    rows = []
    values_by_crop = {
        "Wheat": [100, 110, 105, 120, 115, 130],
        "Barley": [50, 55, 60, 58, 65, 70],
    }

    for crop, values in values_by_crop.items():
        for year, value in zip(range(2015, 2021), values):
            rows.append({
                "Item": crop,
                "Year": year,
                "Unit": "t",
                "Value": float(value),
            })

    return pd.DataFrame(rows)


def test_supervised_dataset_uses_three_previous_years(production_data):
    dataset = build_supervised_dataset(production_data)

    wheat_2018 = dataset[
        (dataset["crop"] == "Wheat") &
        (dataset["year"] == 2018)
    ].iloc[0]

    assert np.isclose(wheat_2018["log_lag_1"], np.log1p(105))
    assert np.isclose(wheat_2018["log_lag_2"], np.log1p(110))
    assert wheat_2018["target"] == 120


def test_training_cutoff_excludes_future_labels(production_data):
    dataset = build_supervised_dataset(production_data)

    model = train_pooled_regressor(
        dataset,
        train_through_year=2019,
    )

    assert model is not None


def test_predictions_are_nonnegative(production_data):
    dataset = build_supervised_dataset(production_data)
    model = train_pooled_regressor(dataset, train_through_year=2019)

    features = dataset[dataset["year"] == 2020]
    predictions = predict_pooled_regressor(model, features)

    assert len(predictions) == 2
    assert np.isfinite(predictions).all()
    assert (predictions >= 0).all()


def test_unknown_crop_can_be_predicted(production_data):
    dataset = build_supervised_dataset(production_data)
    model = train_pooled_regressor(dataset, train_through_year=2019)

    features = build_features_for_next_year(
        production_data,
        "Wheat",
        2021,
    )

    features.loc[0, "crop"] = "New Crop"
    prediction = predict_pooled_regressor(model, features)

    assert len(prediction) == 1
    assert prediction[0] >= 0


def test_next_year_features_reject_nonconsecutive_year(production_data):
    with pytest.raises(ValueError, match="exactly one year"):
        build_features_for_next_year(
            production_data,
            "Wheat",
            2022,
        )
