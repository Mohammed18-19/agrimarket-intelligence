

from pathlib import Path

import pandas as pd

from agrimarket.ingestion.cleaning import clean_faostat_production
from agrimarket.ingestion.faostat import load_faostat_csv


PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_FILE = PROJECT_ROOT / "data/raw/faostat_morocco_crops.csv"
OUTPUT_FILE = PROJECT_ROOT / "data/processed/faostat_morocco_production.csv"


def validate_processed_data(df: pd.DataFrame) -> None:
    """Validate the cleaned FAOSTAT production dataset."""

    if df.empty:
        raise ValueError("Processed dataset is empty.")

    if df["Value"].isna().any():
        raise ValueError("Processed data contains missing production values.")

    if not (df["Element"] == "Production").all():
        raise ValueError("Processed data contains non-production elements.")

    if df.duplicated().any():
        raise ValueError("Processed data contains duplicate rows.")

    if not df["Year"].between(2015, 2024).all():
        raise ValueError("Processed data contains years outside 2015–2024.")



def main() -> None:
    # Read the original dataset without modifying it.
    raw_df = load_faostat_csv(RAW_FILE)

    # Clean the data for production analysis.
    cleaned_df = clean_faostat_production(raw_df)

    # Validate the cleaned dataset before saving.
    validate_processed_data(cleaned_df)

    # Create the output directory if it does not exist.
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Save the processed dataset.
    cleaned_df.to_csv(OUTPUT_FILE, index=False)

    print(f"Raw rows: {len(raw_df)}")
    print(f"Processed rows: {len(cleaned_df)}")
    print(f"Rows excluded: {len(raw_df) - len(cleaned_df)}")
    print(f"Years: {cleaned_df['Year'].min()}–{cleaned_df['Year'].max()}")
    print(f"Unique crops: {cleaned_df['Item'].nunique()}")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()