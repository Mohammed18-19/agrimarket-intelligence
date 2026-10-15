from pathlib import Path

from agrimarket.ingestion.nasa_power import (
    fetch_nasa_power_for_locations,
)

ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT_DIR / "data" / "raw" / "nasa_power_morocco.csv"

START_DATE = "20150101"
END_DATE = "20241231"

PARAMETERS = [
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "PRECTOTCORR",
    "ALLSKY_SFC_SW_DWN",
]


def main() -> None:
    print("Collecting NASA POWER climate data...")
    print(f"Period: {START_DATE} to {END_DATE}")

    df = fetch_nasa_power_for_locations(
        start_date=START_DATE,
        end_date=END_DATE,
        parameters=PARAMETERS,
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)

    print(f"\nSaved {len(df)} observations to:")
    print(OUTPUT_PATH)
    print("\nObservations per location:")
    print(df.groupby("location").size())
    print("\nMissing values per column:")
    print(df.isna().sum())
    print("\nPreview:")
    print(df.head())


if __name__ == "__main__":
    main()
