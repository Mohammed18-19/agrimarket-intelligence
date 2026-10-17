
from pathlib import Path

import pandas as pd

from agrimarket.analytics.production import (
    calculate_production_trends,
)


ROOT_DIR = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT_DIR
    / "data"
    / "processed"
    / "faostat_morocco_production.csv"
)

OUTPUT_FILE = (
    ROOT_DIR
    / "data"
    / "processed"
    / "faostat_production_trends.csv"
)


def main() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Production dataset not found: {INPUT_FILE}"
        )

    production = pd.read_csv(INPUT_FILE)

    trends = calculate_production_trends(production)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    trends.to_csv(OUTPUT_FILE, index=False)

    print("Production analytics completed.")
    print(f"Input records: {len(production)}")
    print(f"Output records: {len(trends)}")
    print(f"Unique crops: {trends['Item'].nunique()}")
    print(f"Output saved to: {OUTPUT_FILE}")

    print("\nLatest production records:")
    latest = (
        trends.sort_values(["Item", "Year"])
        .groupby("Item", sort=False)
        .tail(1)[
            [
                "Item",
                "Year",
                "Unit",
                "Value",
                "change_percentage",
            ]
        ]
        .head(10)
    )

    print(
        latest.to_string(
            index=False,
            col_space=12,
            formatters={
                "Value": "{:,.2f}".format,
                "change_percentage": "{:+.2f}%".format,
            },
        )
    )


if __name__ == "__main__":
    main()
