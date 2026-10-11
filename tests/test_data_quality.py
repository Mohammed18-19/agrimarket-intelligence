import pandas as pd
import pytest

from agrimarket.data_quality import (
    validate_required_columns,
    validate_no_missing_values,
    validate_no_duplicate_rows,
    validate_numeric_columns,
    validate_minimum_value,
    validate_dataset,
)


def test_required_columns_exist():
    df = pd.DataFrame({
        "Year": [2023],
        "Value": [500],
    })

    validate_required_columns(df, ["Year", "Value"])


def test_missing_required_column():
    df = pd.DataFrame({
        "Year": [2023],
    })

    with pytest.raises(ValueError, match="Value"):
        validate_required_columns(df, ["Year", "Value"])


def test_no_missing_values():
    df = pd.DataFrame({
        "Year": [2023, 2024],
        "Value": [500, 600],
    })

    validate_no_missing_values(df)


def test_missing_values():
    df = pd.DataFrame({
        "Year": [2023, 2024],
        "Value": [500, None],
    })

    with pytest.raises(
        ValueError,
        match="DataFrame contains missing values",
    ):
        validate_no_missing_values(df)


def test_no_duplicate_rows():
    df = pd.DataFrame({
        "Year": [2023, 2024],
        "Value": [500, 600],
    })

    validate_no_duplicate_rows(df)


def test_duplicate_rows():
    df = pd.DataFrame({
        "Year": [2023, 2023],
        "Value": [500, 500],
    })

    with pytest.raises(
        ValueError,
        match="DataFrame contains duplicate rows",
    ):
        validate_no_duplicate_rows(df)


def test_numeric_columns():
    df = pd.DataFrame({
        "Year": [2023, 2024],
        "Value": [500, 600],
    })

    validate_numeric_columns(df, ["Year", "Value"])


def test_non_numeric_column():
    df = pd.DataFrame({
        "Year": [2023, 2024],
        "Value": ["five hundred", "six hundred"],
    })

    with pytest.raises(
        ValueError,
        match="must contain numeric data",
    ):
        validate_numeric_columns(df, ["Value"])


def test_minimum_value_passes():
    df = pd.DataFrame({
        "Production": [0, 100, 500],
    })

    validate_minimum_value(df, "Production", 0)


def test_minimum_value_fails():
    df = pd.DataFrame({
        "Production": [100, -5, 500],
    })

    with pytest.raises(
        ValueError,
        match="contains values below",
    ):
        validate_minimum_value(df, "Production", 0)


def test_validate_dataset_passes():
    df = pd.DataFrame({
        "Year": [2023, 2024],
        "Production": [100, 200],
    })

    validate_dataset(
        df,
        required_columns=["Year", "Production"],
        numeric_columns=["Year", "Production"],
        minimum_values={"Production": 0},
    )


def test_validate_dataset_rejects_negative_production():
    df = pd.DataFrame({
        "Year": [2023, 2024],
        "Production": [100, -5],
    })

    with pytest.raises(
        ValueError,
        match="contains values below",
    ):
        validate_dataset(
            df,
            required_columns=["Year", "Production"],
            numeric_columns=["Year", "Production"],
            minimum_values={"Production": 0},
        )