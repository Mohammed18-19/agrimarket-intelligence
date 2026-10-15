import pandas as pd


TEMPERATURE_COLUMNS = ["T2M", "T2M_MAX", "T2M_MIN"]
SOLAR_COLUMN = "ALLSKY_SFC_SW_DWN"
PRECIPITATION_COLUMN = "PRECTOTCORR"


def aggregate_daily_climate(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate daily climate observations by location and year."""

    required_columns = {
        "date",
        "location",
        "latitude",
        "longitude",
        *TEMPERATURE_COLUMNS,
        PRECIPITATION_COLUMN,
        SOLAR_COLUMN,
    }

    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    if df.empty:
        raise ValueError("Climate dataset is empty.")

    result = df.copy()
    result["date"] = pd.to_datetime(result["date"], errors="raise")

    if result["date"].isna().any():
        raise ValueError("Climate dates cannot be missing.")

    if result["location"].isna().any():
        raise ValueError("Climate locations cannot be missing.")

    measurement_columns = [
        *TEMPERATURE_COLUMNS,
        PRECIPITATION_COLUMN,
        SOLAR_COLUMN,
    ]

    if result[measurement_columns].isna().any().any():
        raise ValueError("Climate measurements cannot be missing.")

    for column in measurement_columns:
        try:
            result[column] = pd.to_numeric(result[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Climate measurement column {column} must be numeric."
            ) from exc

    if result[measurement_columns].isna().any().any():
        raise ValueError("Climate measurements cannot be missing.")

    if result.duplicated(["date", "location"]).any():
        raise ValueError("Duplicate date-location records detected.")

    result["year"] = result["date"].dt.year

    return (
        result.groupby(
            ["location", "latitude", "longitude", "year"],
            as_index=False,
        )
        .agg(
            mean_temperature_c=("T2M", "mean"),
            mean_daily_max_temperature_c=("T2M_MAX", "mean"),
            mean_daily_min_temperature_c=("T2M_MIN", "mean"),
            total_precipitation=("PRECTOTCORR", "sum"),
            mean_daily_solar_radiation=(SOLAR_COLUMN, "mean"),
            days_observed=("date", "nunique"),
        )
    )
