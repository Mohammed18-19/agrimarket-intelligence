
import pandas as pd
import pytest

from scripts.process_faostat import validate_processed_data


def valid_data():
    return pd.DataFrame({
        "Area": ["Morocco", "Morocco"],
        "Item": ["Wheat", "Barley"],
        "Element": ["Production", "Production"],
        "Year": [2022, 2023],
        "Unit": ["t", "t"],
        "Value": [1000.0, 800.0],
    })


def test_valid_data_passes():
    validate_processed_data(valid_data())


def test_empty_data_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        validate_processed_data(valid_data().iloc[0:0])


def test_missing_value_is_rejected():
    df = valid_data()
    df.loc[0, "Value"] = None

    with pytest.raises(ValueError, match="missing"):
        validate_processed_data(df)


def test_non_production_element_is_rejected():
    df = valid_data()
    df.loc[0, "Element"] = "Area harvested"

    with pytest.raises(ValueError, match="non-production"):
        validate_processed_data(df)


def test_duplicate_rows_are_rejected():
    df = valid_data()
    df = pd.concat([df, df.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="duplicate"):
        validate_processed_data(df)


def test_invalid_year_is_rejected():
    df = valid_data()
    df.loc[0, "Year"] = 2014

    with pytest.raises(ValueError, match="years"):
        validate_processed_data(df)
