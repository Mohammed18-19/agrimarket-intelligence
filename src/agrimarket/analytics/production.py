
import pandas as pd


def calculate_production_trends(
    df: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate strict year-over-year production changes."""

    required_columns = ["Item", "Year", "Unit", "Value"]
    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    if df.empty:
        raise ValueError("Production data cannot be empty")

    result = df[required_columns].copy()
    result["Year"] = pd.to_numeric(result["Year"], errors="raise")
    result["Value"] = pd.to_numeric(result["Value"], errors="raise")

    if result[required_columns].isna().any().any():
        raise ValueError("Production data contains missing values")

    if not result["Year"].mod(1).eq(0).all():
        raise ValueError("Year values must be integers")

    if not result["Year"].map(float).map(
        lambda value: abs(value) != float("inf")
    ).all():
        raise ValueError("Year values must be finite")

    if not result["Value"].map(float).map(
        lambda value: abs(value) != float("inf")
    ).all():
        raise ValueError("Production values must be finite")

    if (result["Value"] < 0).any():
        raise ValueError("Production values cannot be negative")

    if result.duplicated(["Item", "Year", "Unit"]).any():
        raise ValueError("Duplicate crop-year-unit records found")

    result = result.sort_values(
        ["Item", "Unit", "Year"]
    ).reset_index(drop=True)

    groups = result.groupby(["Item", "Unit"], sort=False)

    result["previous_year_production"] = groups["Value"].shift(1)
    previous_year = groups["Year"].shift(1)

    consecutive = result["Year"].sub(previous_year).eq(1)

    result.loc[
        ~consecutive, "previous_year_production"
    ] = float("nan")

    result["change_in_production"] = (
        result["Value"] - result["previous_year_production"]
    )

    previous = result["previous_year_production"]
    result["change_percentage"] = (
        result["change_in_production"]
        .div(previous.where(previous.ne(0)))
        .mul(100)
    )

    return result


def rank_crops_by_production(
    df: pd.DataFrame,
    year: int,
    top_n: int = 10,
) -> pd.DataFrame:
    """Rank crops by production for a selected year and common unit."""

    required_columns = ["Item", "Year", "Unit", "Value"]
    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    if df.empty:
        raise ValueError("Production data cannot be empty")

    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 1:
        raise ValueError("top_n must be a positive integer")

    if isinstance(year, bool) or not isinstance(year, int):
        raise ValueError("year must be an integer")

    data = df[required_columns].copy()
    data["Year"] = pd.to_numeric(data["Year"], errors="raise")
    data["Value"] = pd.to_numeric(data["Value"], errors="raise")

    if data[required_columns].isna().any().any():
        raise ValueError("Production data contains missing values")

    if not data["Year"].map(float).map(
        lambda value: abs(value) != float("inf")
    ).all():
        raise ValueError("Year values must be finite")

    if not data["Year"].mod(1).eq(0).all():
        raise ValueError("Year values must be integers")

    if not data["Value"].map(float).map(
        lambda value: abs(value) != float("inf")
    ).all():
        raise ValueError("Production values must be finite")

    if (data["Value"] < 0).any():
        raise ValueError("Production values cannot be negative")

    if data["Item"].astype(str).str.strip().eq("").any():
        raise ValueError("Crop names cannot be empty")

    if data["Unit"].astype(str).str.strip().eq("").any():
        raise ValueError("Production units cannot be empty")

    if data.duplicated(["Item", "Year", "Unit"]).any():
        raise ValueError("Duplicate crop-year-unit records found")

    selected_year = data.loc[data["Year"] == year].copy()

    if selected_year.empty:
        raise ValueError(f"No production data found for year {year}")

    if selected_year["Unit"].nunique() > 1:
        raise ValueError(
            "Cannot rank production values with different units"
        )

    return (
        selected_year
        .sort_values(
            ["Value", "Item"],
            ascending=[False, True],
            kind="mergesort",
        )
        .head(top_n)
        .reset_index(drop=True)
        .assign(rank=lambda result: range(1, len(result) + 1))
        [["rank", "Item", "Year", "Unit", "Value"]]
    )
