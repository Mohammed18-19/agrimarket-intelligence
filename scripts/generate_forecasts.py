"""Generate next-year production forecasts for eligible crops."""

from pathlib import Path

import pandas as pd

from agrimarket.analytics.forecasting import forecast_production

DATA_PATH = Path("data/processed/faostat_morocco_production.csv")
OUTPUT_PATH = Path("data/processed/crop_production_forecasts.csv")

# Reviewed production choice. Candidate models are compared separately with
# scripts/evaluate_yearly.py and MLflow. Changing production requires an
# explicit, version-controlled edit here.
PRODUCTION_METHOD = "naive"
PRODUCTION_MODEL_VERSION = "naive-v1"


def main():
    df = pd.read_csv(DATA_PATH)
    results = []
    excluded = []

    for crop, group in df.groupby("Item"):
        series = group[["Item", "Year", "Unit", "Value"]].copy()
        series["Year"] = pd.to_numeric(series["Year"], errors="coerce")
        series["Value"] = pd.to_numeric(series["Value"], errors="coerce")
        series = series.dropna().sort_values("Year").reset_index(drop=True)

        try:
            target_year = int(series["Year"].max()) + 1

            forecast = forecast_production(
                series,
                crop=crop,
                target_year=target_year,
                method=PRODUCTION_METHOD,
            )

            results.append({
                "crop": crop,
                "forecast_year": target_year,
                "predicted_production": forecast["predicted_production"],
                "unit": forecast["unit"],
                "method": PRODUCTION_METHOD,
                "model_version": PRODUCTION_MODEL_VERSION,
                "training_start_year": forecast["training_start_year"],
                "training_end_year": forecast["training_end_year"],
                "training_observations": forecast["training_observations"],
            })

        except (ValueError, TypeError, KeyError) as exc:
            excluded.append((crop, str(exc)))

    if not results:
        raise SystemExit("No eligible crops could be forecast.")

    report = pd.DataFrame(results).sort_values("crop")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(OUTPUT_PATH, index=False)

    print(f"Forecasts generated: {len(report)}")
    print(f"Crops excluded: {len(excluded)}")
    print("\nForecast years:")
    print(report["forecast_year"].value_counts().sort_index().to_string())
    print(f"\nProduction model: {PRODUCTION_MODEL_VERSION} ({PRODUCTION_METHOD})")
    print(f"\nSaved: {OUTPUT_PATH}")

    if excluded:
        print("\nExcluded crops:")
        for crop, reason in excluded:
            print(f"- {crop}: {reason}")


if __name__ == "__main__":
    main()
