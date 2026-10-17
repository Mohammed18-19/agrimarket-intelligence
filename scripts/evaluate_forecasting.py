"""Evaluate forecasting methods using expanding-window backtesting."""

import pandas as pd

from agrimarket.analytics.forecasting import forecast_production

DATA_PATH = "data/processed/faostat_morocco_production.csv"
MIN_TRAIN_SIZE = 4
MAX_TEST_SIZE = 5

df = pd.read_csv(DATA_PATH)
results = []

for crop, group in df.groupby("Item"):
    series = group[["Year", "Value", "Unit"]].copy()
    series["Year"] = pd.to_numeric(series["Year"], errors="coerce")
    series["Value"] = pd.to_numeric(series["Value"], errors="coerce")
    series = series.dropna().sort_values("Year").reset_index(drop=True)

    if len(series) < MIN_TRAIN_SIZE + 1:
        continue

    if series["Year"].duplicated().any():
        continue

    years = series["Year"].astype(int).tolist()
    if years != list(range(years[0], years[-1] + 1)):
        continue

    if (series["Value"] < 0).any() or series["Unit"].nunique() != 1:
        continue

    first_test_index = max(MIN_TRAIN_SIZE, len(series) - MAX_TEST_SIZE)
    errors = {"naive": [], "linear_trend": []}

    for index in range(first_test_index, len(series)):
        history = series.iloc[:index]
        actual_row = series.iloc[index]
        actual = float(actual_row["Value"])
        target_year = int(actual_row["Year"])

        for method in errors:
            try:
                forecast = forecast_production(
                    history.assign(Item=crop),
                    crop=crop,
                    target_year=target_year,
                    method=method,
                )
                predicted = forecast["predicted_production"]
                errors[method].append(abs(actual - predicted))
            except (ValueError, TypeError):
                continue

    if not errors["naive"] or not errors["linear_trend"]:
        continue

    for method, absolute_errors in errors.items():
        results.append({
            "crop": crop,
            "method": method,
            "test_observations": len(absolute_errors),
            "MAE": sum(absolute_errors) / len(absolute_errors),
            "unit": str(series["Unit"].iloc[0]),
        })

report = pd.DataFrame(results)
if report.empty:
    raise SystemExit("No crops were eligible for evaluation.")

report.to_csv("data/processed/forecast_evaluation.csv", index=False)

comparison = report.pivot(
    index="crop", columns="method", values="MAE"
).dropna()

comparison["best_method"] = comparison.apply(
    lambda row: "naive" if row["naive"] <= row["linear_trend"]
    else "linear_trend",
    axis=1,
)
comparison["linear_trend_improvement_pct"] = (
    (comparison["naive"] - comparison["linear_trend"])
    / comparison["naive"].replace(0, float("nan"))
    * 100
)

print(f"Crops evaluated: {len(comparison)}")
print("\nOverall median MAE:")
print(comparison[["naive", "linear_trend"]].median().to_string())

print("\nBest method counts:")
print(comparison["best_method"].value_counts().to_string())

print("\nWheat comparison:")
if "Wheat" in comparison.index:
    print(comparison.loc["Wheat"].to_string())
else:
    print("Wheat was not eligible.")

comparison.to_csv("data/processed/forecast_model_comparison.csv")
print("\nSaved:")
print("- data/processed/forecast_evaluation.csv")
print("- data/processed/forecast_model_comparison.csv")
