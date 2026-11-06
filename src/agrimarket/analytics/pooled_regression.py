"""Pooled supervised regression for annual crop production."""

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from agrimarket.analytics.forecasting import _get_crop_series


FEATURE_COLUMNS = [
    "crop",
    "year",
    "log_lag_1",
    "log_lag_2",
    "log_mean_last_3",
    "log_growth_1y",
    "log_growth_3y",
    "trend_slope",
]

NUMERIC_FEATURES = [
    "year",
    "log_lag_1",
    "log_lag_2",
    "log_mean_last_3",
    "log_growth_1y",
    "log_growth_3y",
    "trend_slope",
]


def _build_historical_features(values: np.ndarray) -> dict:
    """Calculate features from exactly three historical observations."""
    if len(values) != 3:
        raise ValueError("Exactly three historical observations are required")

    log_values = np.log1p(values)

    return {
        "log_lag_1": float(log_values[-1]),
        "log_lag_2": float(log_values[-2]),
        "log_mean_last_3": float(np.log1p(np.mean(values))),
        "log_growth_1y": float(log_values[-1] - log_values[-2]),
        "log_growth_3y": float(log_values[-1] - log_values[0]),
        "trend_slope": float(np.polyfit([0, 1, 2], log_values, 1)[0]),
    }


def build_supervised_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Create leakage-safe supervised samples from historical observations."""
    if "Item" not in df.columns:
        raise ValueError("Missing required column: Item")

    samples = []

    for crop in sorted(df["Item"].dropna().unique()):
        series = _get_crop_series(df, crop)
        values = series["Value"].to_numpy(dtype=float)
        years = series["Year"].to_numpy(dtype=int)

        for index in range(3, len(series)):
            history = values[index - 3:index]

            samples.append({
                "crop": crop,
                "year": int(years[index]),
                **_build_historical_features(history),
                "target": float(values[index]),
            })

    if not samples:
        raise ValueError("No supervised training samples could be created")

    return pd.DataFrame(samples)


def train_pooled_regressor(
    training_data: pd.DataFrame,
    train_through_year: int,
) -> Pipeline:
    """Train a pooled Random Forest using labels up to a specified year."""
    if not isinstance(train_through_year, (int, np.integer)):
        raise ValueError("train_through_year must be an integer")

    required = FEATURE_COLUMNS + ["target"]
    missing = set(required) - set(training_data.columns)

    if missing:
        raise ValueError(f"Missing training columns: {sorted(missing)}")

    train = training_data.loc[
        training_data["year"] <= train_through_year
    ].copy()

    if train.empty:
        raise ValueError("No training samples available before cutoff")

    if train[required].isna().any().any():
        raise ValueError("Training data contains missing values")

    if not np.isfinite(train[required].select_dtypes(include=np.number)).all().all():
        raise ValueError("Training data contains non-finite numeric values")

    if (train["target"] < 0).any():
        raise ValueError("Training targets cannot be negative")

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "crop",
                OneHotEncoder(handle_unknown="ignore"),
                ["crop"],
            ),
            ("numeric", "passthrough", NUMERIC_FEATURES),
        ]
    )

    model = Pipeline([
        ("preprocessor", preprocessor),
        (
            "regressor",
            RandomForestRegressor(
                n_estimators=300,
                min_samples_leaf=3,
                max_features=0.8,
                random_state=42,
                n_jobs=-1,
            ),
        ),
    ])

    model.fit(
        train[FEATURE_COLUMNS],
        np.log1p(train["target"].to_numpy(dtype=float)),
    )

    return model


def predict_pooled_regressor(
    model: Pipeline,
    features: pd.DataFrame,
) -> np.ndarray:
    """Predict non-negative production values in the original unit."""
    missing = set(FEATURE_COLUMNS) - set(features.columns)

    if missing:
        raise ValueError(f"Missing feature columns: {sorted(missing)}")

    predictions_log = model.predict(features[FEATURE_COLUMNS])
    predictions = np.expm1(predictions_log)

    return np.maximum(predictions, 0.0)


def build_features_for_next_year(
    history: pd.DataFrame,
    crop: str,
    target_year: int,
) -> pd.DataFrame:
    """Build one next-year prediction row using historical data only."""
    series = _get_crop_series(history, crop)

    last_year = int(series["Year"].iloc[-1])

    if target_year != last_year + 1:
        raise ValueError(
            "target_year must be exactly one year after the latest observation"
        )

    values = series["Value"].to_numpy(dtype=float)
    last_three = values[-3:]

    return pd.DataFrame([{
        "crop": crop,
        "year": int(target_year),
        **_build_historical_features(last_three),
    }])
