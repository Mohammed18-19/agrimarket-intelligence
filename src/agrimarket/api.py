"""Flask REST API for agricultural production analytics."""

from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, request

from agrimarket.analytics.production import calculate_production_trends


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRODUCTION_PATH = (
    PROJECT_ROOT / "data" / "processed" / "faostat_morocco_production.csv"
)
DEFAULT_FORECAST_PATH = (
    PROJECT_ROOT / "data" / "processed" / "crop_production_forecasts.csv"
)


def create_app(
    production_path=None,
    forecast_path=None,
):
    app = Flask(__name__)

    app.config["PRODUCTION_PATH"] = Path(
        production_path or DEFAULT_PRODUCTION_PATH
    )
    app.config["FORECAST_PATH"] = Path(
        forecast_path or DEFAULT_FORECAST_PATH
    )

    def load_production():
        path = app.config["PRODUCTION_PATH"]
        if not path.is_file():
            raise FileNotFoundError(f"Production dataset not found: {path}")

        df = pd.read_csv(path)
        required = {"Item", "Year", "Unit", "Value"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                f"Production dataset is missing columns: {sorted(missing)}"
            )

        df = df[["Item", "Year", "Unit", "Value"]].copy()
        df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
        df["Value"] = pd.to_numeric(df["Value"], errors="coerce")
        df = df.dropna(subset=["Item", "Year", "Unit", "Value"])
        df["Year"] = df["Year"].astype(int)
        return df

    def json_records(df):
        """Convert pandas records into JSON-safe Python values."""
        return df.astype(object).where(pd.notna(df), None).to_dict(
            orient="records"
        )

    @app.get("/api/health")
    def health():
        production_exists = app.config["PRODUCTION_PATH"].is_file()
        forecast_exists = app.config["FORECAST_PATH"].is_file()

        return jsonify({
            "status": "ok" if production_exists else "degraded",
            "datasets": {
                "production": production_exists,
                "forecasts": forecast_exists,
            },
        }), (200 if production_exists else 503)

    @app.get("/api/crops")
    def list_crops():
        try:
            df = load_production()
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 503
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 500

        crops = sorted(df["Item"].astype(str).unique().tolist())
        return jsonify({"count": len(crops), "crops": crops})

    @app.get("/api/crops/<path:crop>/history")
    def crop_history(crop):
        try:
            df = load_production()
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 503
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 500

        history = df.loc[df["Item"] == crop].sort_values("Year")

        if history.empty:
            return jsonify({"error": f"Crop not found: {crop}"}), 404

        return jsonify({
            "crop": crop,
            "count": len(history),
            "history": json_records(history),
        })

    @app.get("/api/crops/<path:crop>/summary")
    def crop_summary(crop):
        try:
            df = load_production()
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 503
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 500

        history = df.loc[df["Item"] == crop].sort_values("Year")

        if history.empty:
            return jsonify({"error": f"Crop not found: {crop}"}), 404

        if history["Unit"].nunique() != 1:
            return jsonify({
                "error": "Crop has inconsistent production units"
            }), 422

        latest = history.iloc[-1]
        result = {
            "crop": crop,
            "latest_year": int(latest["Year"]),
            "latest_production": float(latest["Value"]),
            "unit": str(latest["Unit"]),
            "observations": len(history),
            "first_year": int(history["Year"].min()),
        }

        trends = calculate_production_trends(history)
        latest_trend = trends.loc[trends["Year"] == latest["Year"]].iloc[-1]

        previous = latest_trend["previous_year_production"]
        change = latest_trend["change_in_production"]
        percentage = latest_trend["change_percentage"]

        result["year_over_year"] = {
            "previous_year_production": (
                float(previous) if pd.notna(previous) else None
            ),
            "change_in_production": (
                float(change) if pd.notna(change) else None
            ),
            "change_percentage": (
                float(percentage) if pd.notna(percentage) else None
            ),
        }

        return jsonify(result)

    @app.get("/api/crops/<path:crop>/forecast")
    def crop_forecast(crop):
        path = app.config["FORECAST_PATH"]

        if not path.is_file():
            return jsonify({"error": "Forecast dataset not found"}), 503

        try:
            forecasts = pd.read_csv(path)
        except (OSError, pd.errors.ParserError) as exc:
            return jsonify({"error": f"Could not read forecasts: {exc}"}), 500

        crop_column = "crop" if "crop" in forecasts.columns else "Item"
        if crop_column not in forecasts.columns:
            return jsonify({
                "error": "Forecast dataset has no crop identifier column"
            }), 500

        selected = forecasts.loc[forecasts[crop_column] == crop].copy()

        if selected.empty:
            return jsonify({"error": f"No forecast found for crop: {crop}"}), 404

        if "target_year" in selected.columns:
            selected = selected.sort_values("target_year")
        elif "Year" in selected.columns:
            selected = selected.sort_values("Year")

        return jsonify({
            "crop": crop,
            "count": len(selected),
            "forecasts": json_records(selected),
        })

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
