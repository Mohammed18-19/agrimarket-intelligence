"""Evaluate pooled regression against forecasting baselines."""

from pathlib import Path

import numpy as np
import pandas as pd

from agrimarket.analytics.forecasting import forecast_production
from agrimarket.analytics.pooled_regression import (
    build_supervised_dataset,
    predict_pooled_regressor,
    train_pooled_regressor,
)

DATA_PATH = Path("data/processed/faostat_morocco_production.csv")
OUTPUT_DIR = Path("data/processed")
HOLDOUT_YEARS = (2023, 2024)
METHODS = ("naive", "linear_trend", "pooled_random_forest")


def main():
    df = pd.read_csv(DATA_PATH)
    supervised = build_supervised_dataset(df)

    results = []

    for target_year in HOLDOUT_YEARS:
        cutoff_year = target_year - 1

        training = supervised[
            supervised["year"] <= cutoff_year
        ].copy()

        testing = supervised[
            supervised["year"] == target_year
        ].copy()

        if training.empty or testing.empty:
            raise ValueError(
                f"Missing training or testing samples for {target_year}"
            )

        model = train_pooled_regressor(
            supervised,
            train_through_year=cutoff_year,
        )

        rf_predictions = predict_pooled_regressor(
            model,
            testing,
        )

        for position, (_, sample) in enumerate(testing.iterrows()):
            crop = sample["crop"]
            actual = float(sample["target"])

            history = df[
                (df["Item"] == crop) &
                (df["Year"] < target_year)
            ][["Item", "Year", "Unit", "Value"]].copy()

            for method in ("naive", "linear_trend"):
                baseline = forecast_production(
                    history,
                    crop,
                    target_year,
                    method=method,
                )
                predicted = baseline["predicted_production"]

                results.append({
                    "crop": crop,
                    "year": target_year,
                    "method": method,
                    "actual": actual,
                    "predicted": predicted,
                    "absolute_error": abs(actual - predicted),
                })

            predicted = float(rf_predictions[position])

            results.append({
                "crop": crop,
                "year": target_year,
                "method": "pooled_random_forest",
                "actual": actual,
                "predicted": predicted,
                "absolute_error": abs(actual - predicted),
            })

        print(
            f"Evaluated {target_year}: "
            f"{len(testing)} crops | "
            f"training labels through {cutoff_year}"
        )

    report = pd.DataFrame(results)

    # Average the two annual errors for each crop and method.
    per_crop = (
        report.groupby(["crop", "method"])["absolute_error"]
        .mean()
        .unstack()
    )

    summary = pd.DataFrame({
        "median_crop_mae": per_crop.median(),
        "mean_crop_mae": per_crop.mean(),
        "crops_won": {
            method: int(
                (per_crop[method] == per_crop.min(axis=1)).sum()
            )
            for method in METHODS
        },
    })

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    detail_path = OUTPUT_DIR / "pooled_regression_holdout_details.csv"
    crop_path = OUTPUT_DIR / "pooled_regression_crop_metrics.csv"
    summary_path = OUTPUT_DIR / "pooled_regression_summary.csv"

    report.to_csv(detail_path, index=False)
    per_crop.to_csv(crop_path)
    summary.to_csv(summary_path)

    print("\nMedian MAE across crops:")
    print(summary.sort_values("median_crop_mae").to_string())

    print("\nSaved evaluation files:")
    print(detail_path)
    print(crop_path)
    print(summary_path)


if __name__ == "__main__":
    main()
