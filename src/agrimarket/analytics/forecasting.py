"""Forecast annual agricultural production."""

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {"Item", "Year", "Unit", "Value"}
MIN_TRAINING_OBSERVATIONS = 4


def _get_crop_series(df: pd.DataFrame, crop: str) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if not isinstance(crop, str) or not crop.strip():
        raise ValueError("crop must be a non-empty string")

    series = df.loc[df["Item"] == crop, ["Item", "Year", "Unit", "Value"]].copy()
    if series.empty:
        raise ValueError(f"No production data found for crop: {crop}")

    series["Year"] = pd.to_numeric(series["Year"], errors="coerce")
    series["Value"] = pd.to_numeric(series["Value"], errors="coerce")
    if series[["Year", "Value"]].isna().any().any():
        raise ValueError(f"{crop} contains missing or invalid years/values")

    years = series["Year"].to_numpy(dtype=float)
    values = series["Value"].to_numpy(dtype=float)
    if not np.isfinite(years).all() or not np.isfinite(values).all():
        raise ValueError(f"{crop} contains non-finite years or values")
    if not np.equal(years, np.floor(years)).all():
        raise ValueError("Years must be integers")

    series["Year"] = series["Year"].astype(int)
    series = series.sort_values("Year").reset_index(drop=True)
    if series["Year"].duplicated().any():
        raise ValueError(f"{crop} contains duplicate yearly observations")
    if (series["Value"] < 0).any():
        raise ValueError(f"{crop} contains negative production values")
    if series["Unit"].isna().any() or series["Unit"].nunique() != 1:
        raise ValueError(f"{crop} must have exactly one consistent unit")

    expected = list(range(int(series["Year"].iloc[0]), int(series["Year"].iloc[-1]) + 1))
    if series["Year"].tolist() != expected:
        raise ValueError(f"{crop} has missing years")
    if len(series) < MIN_TRAINING_OBSERVATIONS:
        raise ValueError(f"At least {MIN_TRAINING_OBSERVATIONS} observations are required")
    return series


def forecast_production(df: pd.DataFrame, crop: str, target_year: int, method: str = "naive") -> dict:
    if isinstance(target_year, bool) or not isinstance(target_year, (int, np.integer)):
        raise ValueError("target_year must be an integer")
    if method not in {"naive", "linear_trend"}:
        raise ValueError("method must be naive or linear_trend")

    series = _get_crop_series(df, crop)
    last_year = int(series["Year"].iloc[-1])
    if target_year <= last_year:
        raise ValueError("target_year must be later than the latest training year")

    years = series["Year"].to_numpy(dtype=float)
    values = series["Value"].to_numpy(dtype=float)
    if method == "naive":
        prediction = float(values[-1])
    else:
        slope, intercept = np.polyfit(years, values, deg=1)
        prediction = float(slope * target_year + intercept)
    prediction = max(0.0, prediction)

    return {
        "crop": crop,
        "target_year": int(target_year),
        "predicted_production": prediction,
        "unit": str(series["Unit"].iloc[0]),
        "method": method,
        "training_start_year": int(series["Year"].iloc[0]),
        "training_end_year": last_year,
        "training_observations": len(series),
    }


def evaluate_forecast(df: pd.DataFrame, crop: str, method: str = "naive", test_size: int = 2) -> dict:
    if isinstance(test_size, bool) or not isinstance(test_size, int) or test_size < 1:
        raise ValueError("test_size must be a positive integer")
    series = _get_crop_series(df, crop)
    if len(series) - test_size < MIN_TRAINING_OBSERVATIONS:
        raise ValueError("Not enough observations; keep at least four training observations")

    predictions = []
    for index in range(len(series) - test_size, len(series)):
        history = series.iloc[:index]
        actual_row = series.iloc[index]
        forecast = forecast_production(history, crop, int(actual_row["Year"]), method)
        actual = float(actual_row["Value"])
        predicted = forecast["predicted_production"]
        predictions.append({
            "year": int(actual_row["Year"]),
            "actual": actual,
            "predicted": predicted,
            "absolute_error": abs(actual - predicted),
            "squared_error": (actual - predicted) ** 2,
        })

    mae = float(np.mean([row["absolute_error"] for row in predictions]))
    rmse = float(np.sqrt(np.mean([row["squared_error"] for row in predictions])))
    return {
        "crop": crop,
        "method": method,
        "test_size": test_size,
        "mae": mae,
        "rmse": rmse,
        "unit": str(series["Unit"].iloc[0]),
        "predictions": predictions,
    }


def select_best_method(
    df: pd.DataFrame,
    crop: str,
    selection_test_size: int = 2,
) -> dict:
    """Select a method on an earlier validation window.

    The returned selection score is a validation score, not an
    unbiased estimate of future performance.
    """
    if (
        isinstance(selection_test_size, bool)
        or not isinstance(selection_test_size, int)
        or selection_test_size < 1
    ):
        raise ValueError("selection_test_size must be a positive integer")

    series = _get_crop_series(df, crop)

    if len(series) - selection_test_size < MIN_TRAINING_OBSERVATIONS:
        raise ValueError(
            "Not enough observations for model selection; "
            "keep at least four training observations"
        )

    validation_start = len(series) - selection_test_size
    validation_history = series.iloc[:validation_start]
    validation_rows = series.iloc[validation_start:]

    scores = {}

    for method in ("naive", "linear_trend"):
        errors = []

        for _, actual_row in validation_rows.iterrows():
            result = forecast_production(
                validation_history,
                crop=crop,
                target_year=int(actual_row["Year"]),
                method=method,
            )
            errors.append(
                abs(float(actual_row["Value"]) - result["predicted_production"])
            )

        scores[method] = float(np.mean(errors))

    best_method = min(scores, key=scores.get)

    return {
        "crop": crop,
        "best_method": best_method,
        "validation_mae": scores[best_method],
        "validation_scores": scores,
        "selection_training_end_year": int(
            validation_history["Year"].iloc[-1]
        ),
        "validation_start_year": int(validation_rows["Year"].iloc[0]),
        "validation_end_year": int(validation_rows["Year"].iloc[-1]),
        "selection_test_size": selection_test_size,
    }
