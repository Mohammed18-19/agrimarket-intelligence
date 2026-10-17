
import pandas as pd
import pytest

from agrimarket.analytics.production import (
    calculate_production_trends,
    rank_crops_by_production,
)


def test_calculates_annual_production_changes():
    df = pd.DataFrame({
        "Item": ["Wheat", "Wheat", "Wheat"],
        "Year": [2020, 2021, 2022],
        "Unit": ["t", "t", "t"],
        "Value": [100.0, 150.0, 120.0],
    })

    result = calculate_production_trends(df)

    assert pd.isna(result.loc[0, "change_percentage"])
    assert result.loc[1, "change_in_production"] == 50.0
    assert result.loc[1, "change_percentage"] == 50.0
    assert result.loc[2, "change_in_production"] == -30.0
    assert result.loc[2, "change_percentage"] == -20.0


def test_handles_missing_years():
    df = pd.DataFrame({
        "Item": ["Wheat", "Wheat", "Wheat"],
        "Year": [2020, 2022, 2023],
        "Unit": ["t", "t", "t"],
        "Value": [100.0, 120.0, 150.0],
    })

    result = calculate_production_trends(df)

    # 2020 has no previous year in the dataset.
    assert pd.isna(result.loc[0, "previous_year_production"])
    assert pd.isna(result.loc[0, "change_in_production"])
    assert pd.isna(result.loc[0, "change_percentage"])

    # 2021 is missing, so 2022 has no valid year-over-year comparison.
    assert pd.isna(result.loc[1, "previous_year_production"])
    assert pd.isna(result.loc[1, "change_in_production"])
    assert pd.isna(result.loc[1, "change_percentage"])

    # Consecutive years resume a valid comparison in 2023.
    assert result.loc[2, "previous_year_production"] == 120.0
    assert result.loc[2, "change_in_production"] == 30.0
    assert result.loc[2, "change_percentage"] == 25.0
def test_rejects_missing_required_columns():
    df = pd.DataFrame({
        "Item": ["Wheat"],
        "Year": [2020],
        "Value": [100.0],
    })

    with pytest.raises(ValueError, match="Missing required columns"):
        calculate_production_trends(df)


def test_rejects_empty_dataframe():
    df = pd.DataFrame(
        columns=["Item", "Year", "Unit", "Value"]
    )

    with pytest.raises(ValueError, match="cannot be empty"):
        calculate_production_trends(df)


def test_rejects_negative_production():
    df = pd.DataFrame({
        "Item": ["Wheat"],
        "Year": [2020],
        "Unit": ["t"],
        "Value": [-10.0],
    })

    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_production_trends(df)


def test_rejects_duplicate_crop_year_unit():
    df = pd.DataFrame({
        "Item": ["Wheat", "Wheat"],
        "Year": [2020, 2020],
        "Unit": ["t", "t"],
        "Value": [100.0, 110.0],
    })

    with pytest.raises(ValueError, match="Duplicate"):
        calculate_production_trends(df)


def test_ranks_crops_by_production():
    df = pd.DataFrame({
        "Item": ["Wheat", "Potatoes", "Tomatoes"],
        "Year": [2024, 2024, 2024],
        "Unit": ["t", "t", "t"],
        "Value": [100.0, 300.0, 200.0],
    })

    result = rank_crops_by_production(df, year=2024, top_n=2)

    assert result["Item"].tolist() == ["Potatoes", "Tomatoes"]
    assert result["rank"].tolist() == [1, 2]
    assert result["Value"].tolist() == [300.0, 200.0]


def test_ranking_rejects_unknown_year():
    df = pd.DataFrame({
        "Item": ["Wheat"],
        "Year": [2024],
        "Unit": ["t"],
        "Value": [100.0],
    })

    with pytest.raises(ValueError, match="No production data"):
        rank_crops_by_production(df, year=2020)


def test_ranking_rejects_different_units():
    df = pd.DataFrame({
        "Item": ["Wheat", "Tomatoes"],
        "Year": [2024, 2024],
        "Unit": ["t", "kg"],
        "Value": [100.0, 200.0],
    })

    with pytest.raises(ValueError, match="different units"):
        rank_crops_by_production(df, year=2024)


def test_zero_previous_production_has_no_percentage():
    df = pd.DataFrame({
        "Item": ["Wheat", "Wheat"],
        "Year": [2020, 2021],
        "Unit": ["t", "t"],
        "Value": [0.0, 10.0],
    })

    result = calculate_production_trends(df)

    assert result.loc[1, "previous_year_production"] == 0.0
    assert result.loc[1, "change_in_production"] == 10.0
    assert pd.isna(result.loc[1, "change_percentage"])


def test_rejects_non_finite_production_values():
    df = pd.DataFrame({
        "Item": ["Wheat", "Wheat"],
        "Year": [2020, 2021],
        "Unit": ["t", "t"],
        "Value": [100.0, float("inf")],
    })

    try:
        calculate_production_trends(df)
    except ValueError:
        pass
    else:
        raise AssertionError("Non-finite production values must be rejected")


def test_rejects_non_integer_years():
    df = pd.DataFrame({
        "Item": ["Wheat", "Wheat"],
        "Year": [2020, 2021.5],
        "Unit": ["t", "t"],
        "Value": [100.0, 120.0],
    })

    try:
        calculate_production_trends(df)
    except ValueError:
        pass
    else:
        raise AssertionError("Non-integer years must be rejected")


def test_sorts_unsorted_years_before_calculating_changes():
    df = pd.DataFrame({
        "Item": ["Wheat", "Wheat", "Wheat"],
        "Year": [2022, 2020, 2021],
        "Unit": ["t", "t", "t"],
        "Value": [150.0, 100.0, 120.0],
    })

    result = calculate_production_trends(df).reset_index(drop=True)

    assert result["Year"].tolist() == [2020, 2021, 2022]
    assert pd.isna(result.loc[0, "change_in_production"])
    assert result.loc[1, "change_in_production"] == 20.0
    assert result.loc[2, "change_in_production"] == 30.0

