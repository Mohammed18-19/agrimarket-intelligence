"""Compare pooled regression and baseline forecasts on a shared holdout."""

from pathlib import Path

import numpy as np
import pandas as pd

from agrimarket.analytics.forecasting import (
    _get_crop_series,
    forecast_production,
    select_best_method,
)
from agrimarket.analytics.pooled_regression import (
    build_supervised_dataset,
    predict_pooled_regressor,
    train_pooled_regressor,
)

DATA_PATH = Path("data/processed/faostat_morocco_production.csv")
OUTPUT_DIR = Path("data/processed")
HOLDOUT_SIZE = 2
METHODS = ("naive", "linear_trend", "selected_baseline", "pooled_random_forest")


def main():
    raw = pd.read_csv(DATA_PATH)
    required = {"Item", "Year", "Unit", "Value"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    raw["Year"] = pd.to_numeric(raw["Year"], errors="coerce")
    raw["Value"] = pd.to_numeric(raw["Value"], errors="coerce")
    years = sorted(raw["Year"].dropna().astype(int).unique())
    if len(years) < HOLDOUT_SIZE:
        raise ValueError("At least two distinct production years are required")
    holdout_years = years[-HOLDOUT_SIZE:]
    first_holdout = holdout_years[0]

    eligible_parts = []
    excluded = []
    for crop, group in raw.groupby("Item", sort=True):
        try:
            series = _get_crop_series(group, crop)
            if not set(holdout_years).issubset(set(series["Year"])):
                raise ValueError("missing one or more common holdout years")
            if int(series.loc[series["Year"] < first_holdout, "Year"].count()) < 6:
                raise ValueError("fewer than six pre-holdout observations for baseline selection")
            eligible_parts.append(series)
        except (TypeError, ValueError, KeyError) as exc:
            excluded.append((crop, str(exc)))

    if not eligible_parts:
        raise SystemExit("No crops meet the shared holdout requirements.")

    eligible_data = pd.concat(eligible_parts, ignore_index=True)
    supervised = build_supervised_dataset(eligible_data)
    selected_methods = {}
    for crop, group in eligible_data.groupby("Item", sort=True):
        pre_holdout = group[group["Year"] < first_holdout]
        selected_methods[crop] = select_best_method(
            pre_holdout, crop, selection_test_size=2
        )["best_method"]
    detail_rows = []

    for target_year in holdout_years:
        testing = supervised[supervised["year"] == target_year].reset_index(drop=True)
        model = train_pooled_regressor(supervised, train_through_year=target_year - 1)
        pooled_predictions = predict_pooled_regressor(model, testing)

        for position, sample in testing.iterrows():
            crop = sample["crop"]
            actual = float(sample["target"])
            history = eligible_data[
                (eligible_data["Item"] == crop)
                & (eligible_data["Year"] < target_year)
            ][["Item", "Year", "Unit", "Value"]]
            predictions = {
                "pooled_random_forest": float(pooled_predictions[position])
            }
            for method in ("naive", "linear_trend"):
                result = forecast_production(history, crop, target_year, method)
                predictions[method] = result["predicted_production"]
            selected_result = forecast_production(
                history, crop, target_year, selected_methods[crop]
            )
            predictions["selected_baseline"] = selected_result["predicted_production"]

            for method, predicted in predictions.items():
                detail_rows.append({
                    "crop": crop,
                    "year": target_year,
                    "method": method,
                    "actual": actual,
                    "predicted": predicted,
                    "absolute_error": abs(actual - predicted),
                    "squared_error": (actual - predicted) ** 2,
                    "unit": str(sample.get("unit", history["Unit"].iloc[-1])),
                })

        print(
            f"Evaluated {target_year}: {len(testing)} crops; "
            f"training labels through {target_year - 1}"
        )

    details = pd.DataFrame(detail_rows)
    per_crop_rows = []
    for (crop, method), group in details.groupby(["crop", "method"], sort=True):
        actual = group["actual"].to_numpy(dtype=float)
        errors = group["absolute_error"].to_numpy(dtype=float)
        denominator = float(np.abs(actual).sum())
        per_crop_rows.append({
            "crop": crop,
            "method": method,
            "unit": group["unit"].iloc[0],
            "holdout_observations": len(group),
            "mae": float(errors.mean()),
            "rmse": float(np.sqrt(group["squared_error"].mean())),
            # WAPE is scale-normalized within a crop; undefined for all-zero actuals.
            "wape_pct": float(errors.sum() / denominator * 100) if denominator else np.nan,
        })
    per_crop = pd.DataFrame(per_crop_rows)

    valid_wape = per_crop.dropna(subset=["wape_pct"])
    wape_matrix = valid_wape.pivot(index="crop", columns="method", values="wape_pct")
    unique_winners = []
    tied_crops = 0
    for _, scores in wape_matrix.iterrows():
        best = scores.min()
        methods_at_best = scores.index[np.isclose(scores.to_numpy(), best)].tolist()
        if len(methods_at_best) == 1:
            unique_winners.append(methods_at_best[0])
        else:
            tied_crops += 1
    winners = pd.Series(unique_winners).value_counts()
    summary = per_crop.groupby("method").agg(
        median_crop_mae=("mae", "median"),
        mean_crop_mae=("mae", "mean"),
        median_crop_rmse=("rmse", "median"),
        median_crop_wape_pct=("wape_pct", "median"),
        mean_crop_wape_pct=("wape_pct", "mean"),
        eligible_crop_count=("crop", "nunique"),
    )
    summary["crops_won_by_wape"] = winners.reindex(METHODS, fill_value=0)
    summary["tied_crops_by_wape"] = tied_crops
    summary["holdout_years"] = ",".join(map(str, holdout_years))
    summary["holdout_observations_per_crop"] = HOLDOUT_SIZE
    summary = summary.reindex(METHODS).reset_index()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    details.to_csv(OUTPUT_DIR / "pooled_regression_holdout_details.csv", index=False)
    per_crop.to_csv(OUTPUT_DIR / "pooled_regression_crop_metrics.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "pooled_regression_summary.csv", index=False)

    print(f"Holdout years: {holdout_years[0]}–{holdout_years[-1]}")
    print(f"Eligible crops: {per_crop['crop'].nunique()}; excluded: {len(excluded)}")
    print("\nComparable method summary:")
    print(summary.to_string(index=False))
    if excluded:
        print("\nExcluded crops:")
        for crop, reason in excluded:
            print(f"- {crop}: {reason}")
    print("\nSaved pooled_regression_holdout_details.csv, "
          "pooled_regression_crop_metrics.csv, and pooled_regression_summary.csv")


if __name__ == "__main__":
    main()
