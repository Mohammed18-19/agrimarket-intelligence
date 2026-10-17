"""Evaluate crop forecasts on a chronological holdout not used for selection."""

from pathlib import Path

import pandas as pd

from agrimarket.analytics.forecasting import (
    forecast_production,
    select_best_method,
)

DATA_PATH = Path("data/processed/faostat_morocco_production.csv")
OUTPUT_DIR = Path("data/processed")

FINAL_HOLDOUT_SIZE = 2
SELECTION_TEST_SIZE = 2
MIN_SELECTION_TRAIN_SIZE = 4
METHODS = ("naive", "linear_trend")


def calculate_metrics(actual, predicted):
    errors = [a - p for a, p in zip(actual, predicted)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = (sum(error**2 for error in errors) / len(errors)) ** 0.5
    return mae, rmse


def main():
    df = pd.read_csv(DATA_PATH)
    required = {"Item", "Year", "Unit", "Value"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    results = []
    excluded = []

    for crop, group in df.groupby("Item"):
        series = group[["Item", "Year", "Unit", "Value"]].copy()
        series["Year"] = pd.to_numeric(series["Year"], errors="coerce")
        series["Value"] = pd.to_numeric(series["Value"], errors="coerce")
        series = series.dropna().sort_values("Year").reset_index(drop=True)

        if len(series) < (
            MIN_SELECTION_TRAIN_SIZE
            + SELECTION_TEST_SIZE
            + FINAL_HOLDOUT_SIZE
        ):
            excluded.append((crop, "not enough observations"))
            continue

        if series["Year"].duplicated().any():
            excluded.append((crop, "duplicate years"))
            continue

        if not (series["Year"] % 1 == 0).all():
            excluded.append((crop, "non-integer year"))
            continue

        years = series["Year"].astype(int).tolist()
        if years != list(range(years[0], years[-1] + 1)):
            excluded.append((crop, "missing years"))
            continue

        if (series["Value"] < 0).any():
            excluded.append((crop, "negative production"))
            continue

        if series["Unit"].nunique() != 1:
            excluded.append((crop, "inconsistent units"))
            continue

        # Keep the final two years completely out of method selection.
        selection_data = series.iloc[:-FINAL_HOLDOUT_SIZE].copy()
        holdout = series.iloc[-FINAL_HOLDOUT_SIZE:].copy()

        try:
            selection = select_best_method(
                selection_data,
                crop,
                selection_test_size=SELECTION_TEST_SIZE,
            )
        except (ValueError, TypeError) as exc:
            excluded.append((crop, str(exc)))
            continue

        actual_values = []
        predictions = {method: [] for method in METHODS}

        # Expanding-window forecasts; the selected method remains fixed.
        for index in range(len(series) - FINAL_HOLDOUT_SIZE, len(series)):
            history = series.iloc[:index].copy()
            actual_row = series.iloc[index]
            actual_values.append(float(actual_row["Value"]))

            for method in METHODS:
                try:
                    prediction = forecast_production(
                        history,
                        crop=crop,
                        target_year=int(actual_row["Year"]),
                        method=method,
                    )
                    predictions[method].append(
                        prediction["predicted_production"]
                    )
                except (ValueError, TypeError) as exc:
                    raise RuntimeError(
                        f"Evaluation failed for {crop}, "
                        f"{int(actual_row['Year'])}, {method}"
                    ) from exc

        row = {
            "crop": crop,
            "unit": str(series["Unit"].iloc[0]),
            "selection_method": selection["best_method"],
            "selection_validation_mae": selection["validation_mae"],
            "selection_train_end_year": selection["selection_training_end_year"],
            "selection_validation_start_year": selection["validation_start_year"],
            "selection_validation_end_year": selection["validation_end_year"],
            "holdout_start_year": int(holdout["Year"].iloc[0]),
            "holdout_end_year": int(holdout["Year"].iloc[-1]),
            "holdout_observations": len(actual_values),
        }

        method_metrics = {}
        for method in METHODS:
            mae, rmse = calculate_metrics(
                actual_values,
                predictions[method],
            )
            method_metrics[method] = (mae, rmse)
            row[f"{method}_holdout_mae"] = mae
            row[f"{method}_holdout_rmse"] = rmse

        selected_mae, selected_rmse = method_metrics[selection["best_method"]]
        row["selected_holdout_mae"] = selected_mae
        row["selected_holdout_rmse"] = selected_rmse
        results.append(row)

    if not results:
        raise SystemExit(
            "No crops were eligible. Check the dataset and forecasting rules."
        )

    report = pd.DataFrame(results).sort_values("crop")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = OUTPUT_DIR / "forecast_holdout_evaluation.csv"
    report.to_csv(report_path, index=False)

    metric_columns = [
        "naive_holdout_mae",
        "linear_trend_holdout_mae",
        "selected_holdout_mae",
        "naive_holdout_rmse",
        "linear_trend_holdout_rmse",
        "selected_holdout_rmse",
    ]
    summary = report[metric_columns].median().rename("median_across_crops")
    summary_path = OUTPUT_DIR / "forecast_holdout_summary.csv"
    summary.to_frame().to_csv(summary_path)

    print(f"Crops evaluated: {len(report)}")
    print(f"Crops excluded: {len(excluded)}")
    print("\nMedian error across crops (units vary by crop):")
    print(summary.to_string())
    print("\nSelected methods:")
    print(report["selection_method"].value_counts().to_string())
    print(f"\nSaved: {report_path}")
    print(f"Saved: {summary_path}")

    if excluded:
        print("\nFirst excluded crops:")
        for crop, reason in excluded[:10]:
            print(f"- {crop}: {reason}")


if __name__ == "__main__":
    main()
