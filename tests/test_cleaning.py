
import pandas as pd
import pytest

from agrimarket.ingestion.cleaning import clean_faostat_production


def sample_data():
    return pd.DataFrame({
        "Area": ["Morocco", "Morocco", "Morocco"],
        "Item": ["Wheat", "Beans, dry", "Barley"],
        "Element": ["Production", "Production", "Area harvested"],
        "Year": [2022, 2023, 2024],
        "Unit": ["t", "t", "ha"],
        "Value": [1000.0, None, 500.0],
        "Flag": ["A", "M", "A"],
        "Flag Description": [
            "Official value",
            "Missing value; data cannot exist",
            "Official value",
        ],
    })


def test_cleaning_removes_missing_values_and_non_production():
    result = clean_faostat_production(sample_data())

    assert len(result) == 1
    assert result.iloc[0]["Item"] == "Wheat"
    assert result.iloc[0]["Value"] == 1000.0
    assert result["Value"].notna().all()
    assert (result["Element"] == "Production").all()


def test_cleaning_does_not_modify_raw_dataframe():
    original = sample_data()
    before = original.copy(deep=True)

    clean_faostat_production(original)

    pd.testing.assert_frame_equal(original, before)


def test_cleaning_rejects_missing_required_column():
    df = sample_data().drop(columns=["Value"])

    with pytest.raises(ValueError, match="Value"):
        clean_faostat_production(df)


def test_cleaning_rejects_non_numeric_year():
    df = sample_data()
    df["Year"] = ["2022", "bad-year", "2024"]

    with pytest.raises((ValueError, TypeError)):
        clean_faostat_production(df)
