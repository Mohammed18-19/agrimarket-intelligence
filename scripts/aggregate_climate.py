from pathlib import Path

import pandas as pd

from agrimarket.analytics.climate import aggregate_daily_climate

ROOT_DIR = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT_DIR / "data" / "raw" / "nasa_power_morocco.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "processed" / "nasa_power_annual.csv"


def main() -> None:
    df = pd.read_csv(INPUT_PATH, parse_dates=["date"])
    annual = aggregate_daily_climate(df)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    annual.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved annual climate indicators to:\n{OUTPUT_PATH}")
    print(f"\nAnnual rows: {len(annual)}")
    print(annual.to_string(index=False))


if __name__ == "__main__":
    main()
