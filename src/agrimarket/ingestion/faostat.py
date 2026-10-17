from pathlib import Path

import pandas as pd


FAOSTAT_REQUIRED_COLUMNS = [
    "Area",
    "Item",
    "Element",
    "Year",
    "Unit",
    "Value",
    "Flag",
    "Flag Description",
]


def load_faostat_csv(path: str | Path) -> pd.DataFrame:
    """Load a local FAOSTAT CSV and validate its required columns."""

    csv_path = Path(path)

    if not csv_path.is_file():
        raise FileNotFoundError(
            f"FAOSTAT CSV file not found: {csv_path}"
        )

    try:
        df = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError as exc:
        raise ValueError(
            f"FAOSTAT CSV file is empty: {csv_path}"
        ) from exc

    if df.empty:
        raise ValueError(
            f"FAOSTAT CSV contains no data rows: {csv_path}"
        )

    missing_columns = [
        column
        for column in FAOSTAT_REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"FAOSTAT CSV is missing required columns: {missing_columns}"
        )

    return df
