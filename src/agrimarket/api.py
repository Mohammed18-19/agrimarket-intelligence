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
DEFAULT_CLIMATE_PATH = (
    PROJECT_ROOT / "data" / "processed" / "nasa_power_annual.csv"
)


def create_app(
    production_path=None,
    forecast_path=None,
    climate_path=None,
):
    app = Flask(__name__)

    app.config["PRODUCTION_PATH"] = Path(
        production_path or DEFAULT_PRODUCTION_PATH
    )
    app.config["FORECAST_PATH"] = Path(
        forecast_path or DEFAULT_FORECAST_PATH
    )
    app.config["CLIMATE_PATH"] = Path(
        climate_path or DEFAULT_CLIMATE_PATH
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
        climate_exists = app.config["CLIMATE_PATH"].is_file()

        return jsonify({
            "status": (
                "ok" if production_exists and climate_exists else "degraded"
            ),
            "datasets": {
                "production": production_exists,
                "forecasts": forecast_exists,
                "climate": climate_exists,
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


    @app.get("/api/climate")
    def climate():
        """Return annual NASA POWER climate observations."""
        path = app.config["CLIMATE_PATH"]

        if not path.is_file():
            return jsonify({"error": "Climate dataset not found"}), 503

        location = request.args.get("location")
        year_param = request.args.get("year")

        try:
            df = pd.read_csv(path)
        except (OSError, pd.errors.ParserError):
            return jsonify({"error": "Could not read climate dataset"}), 500

        required = {
            "location",
            "latitude",
            "longitude",
            "year",
            "mean_temperature_c",
            "mean_daily_max_temperature_c",
            "mean_daily_min_temperature_c",
            "total_precipitation",
            "mean_daily_solar_radiation",
            "days_observed",
        }
        missing = required - set(df.columns)
        if missing:
            return jsonify({
                "error": "Climate dataset is missing columns",
                "missing_columns": sorted(missing),
            }), 500

        df = df[list(required)].copy()
        df["location"] = df["location"].astype("string").str.strip()

        numeric_columns = [
            "latitude",
            "longitude",
            "year",
            "mean_temperature_c",
            "mean_daily_max_temperature_c",
            "mean_daily_min_temperature_c",
            "total_precipitation",
            "mean_daily_solar_radiation",
            "days_observed",
        ]
        for column in numeric_columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

        df = df.dropna(subset=["location", "year"])
        df["year"] = df["year"].astype(int)

        if location:
            location = location.strip()
            available_locations = sorted(df["location"].unique().tolist())
            if location not in available_locations:
                return jsonify({
                    "error": f"Unknown climate location: {location}",
                    "available_locations": available_locations,
                }), 404
            df = df.loc[df["location"] == location]

        if year_param is not None:
            try:
                year = int(year_param)
            except ValueError:
                return jsonify({
                    "error": "Year must be an integer",
                }), 400
            df = df.loc[df["year"] == year]

        if df.empty:
            return jsonify({"error": "No climate records found"}), 404

        df = df.sort_values(["location", "year"])

        return jsonify({
            "count": len(df),
            "locations": sorted(df["location"].unique().tolist()),
            "years": sorted(df["year"].unique().tolist()),
            "records": json_records(df),
        })

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
