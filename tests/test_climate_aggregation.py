import pandas as pd
import pytest

from agrimarket.analytics.climate import aggregate_daily_climate


@pytest.fixture
def daily_data():
    return pd.DataFrame(
        {
            "date": ["2020-01-01", "2020-01-02", "2020-01-01"],
            "location": ["Meknes", "Meknes", "Fes"],
            "latitude": [33.8935, 33.8935, 34.0331],
            "longitude": [-5.5473, -5.5473, -5.0003],
            "T2M": [10.0, 20.0, 15.0],
            "T2M_MAX": [15.0, 25.0, 20.0],
            "T2M_MIN": [5.0, 15.0, 10.0],
            "PRECTOTCORR": [2.0, 3.0, 1.0],
            "ALLSKY_SFC_SW_DWN": [10.0, 20.0, 15.0],
        }
    )


def test_aggregates_temperature_precipitation_and_days(daily_data):
    result = aggregate_daily_climate(daily_data)
    meknes = result[result["location"] == "Meknes"].iloc[0]

    assert meknes["year"] == 2020
    assert meknes["mean_temperature_c"] == 15.0
    assert meknes["mean_daily_max_temperature_c"] == 20.0
    assert meknes["mean_daily_min_temperature_c"] == 10.0
    assert meknes["total_precipitation"] == 5.0
    assert meknes["mean_daily_solar_radiation"] == 15.0
    assert meknes["days_observed"] == 2
    assert len(result) == 2


def test_rejects_duplicate_date_location(daily_data):
    duplicated = pd.concat(
        [daily_data, daily_data.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="Duplicate date-location"):
        aggregate_daily_climate(duplicated)


def test_rejects_empty_dataframe(daily_data):
    with pytest.raises(ValueError, match="empty"):
        aggregate_daily_climate(daily_data.iloc[0:0])


def test_rejects_missing_required_column(daily_data):
    incomplete = daily_data.drop(columns=["T2M"])

    with pytest.raises(ValueError, match="T2M"):
        aggregate_daily_climate(incomplete)


def test_rejects_missing_climate_measurements(daily_data):
    incomplete = daily_data.copy()
    incomplete.loc[0, "T2M"] = float("nan")

    with pytest.raises(ValueError, match="missing"):
        aggregate_daily_climate(incomplete)


def test_rejects_non_numeric_climate_measurements(daily_data):
    invalid = daily_data.copy()
    invalid["T2M"] = invalid["T2M"].astype(object)
    invalid.loc[0, "T2M"] = "invalid"

    with pytest.raises(ValueError, match="numeric"):
        aggregate_daily_climate(invalid)

def test_rejects_infinite_climate_measurements(daily_data):
    invalid = daily_data.copy()
    invalid.loc[0, "T2M"] = float("inf")

    with pytest.raises(ValueError, match="finite"):
        aggregate_daily_climate(invalid)


def test_rejects_invalid_latitude(daily_data):
    invalid = daily_data.copy()
    invalid.loc[0, "latitude"] = 95.0

    with pytest.raises(ValueError, match="Latitude"):
        aggregate_daily_climate(invalid)


def test_rejects_maximum_temperature_below_minimum(daily_data):
    invalid = daily_data.copy()
    invalid.loc[0, "T2M_MAX"] = 0.0
    invalid.loc[0, "T2M_MIN"] = 5.0

    with pytest.raises(ValueError, match="Maximum temperature"):
        aggregate_daily_climate(invalid)
