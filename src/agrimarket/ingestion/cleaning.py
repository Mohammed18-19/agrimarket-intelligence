import pandas as pd


def clean_faostat_production(df: pd.DataFrame) -> pd.DataFrame:
    """Clean FAOSTAT production data without modifying the raw input."""

    required_columns = [
        "Area",
        "Item",
        "Element",
        "Year",
        "Unit",
        "Value",
        "Flag",
        "Flag Description",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}"
        )

    cleaned = df.copy()

    cleaned["Year"] = pd.to_numeric(
        cleaned["Year"],
        errors="raise",
    )

    cleaned["Value"] = pd.to_numeric(
        cleaned["Value"],
        errors="raise",
    )

    cleaned = cleaned.loc[
        cleaned["Value"].notna()
    ].copy()

    cleaned = cleaned.loc[
        cleaned["Element"] == "Production"
    ].copy()

    cleaned = cleaned.reset_index(drop=True)

    return cleaned
