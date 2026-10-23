import pandas as pd
import pytest

from agrimarket.api import create_app


@pytest.fixture
def api_client(tmp_path):
    production_path = tmp_path / "production.csv"
    forecast_path = tmp_path / "forecasts.csv"

    pd.DataFrame([
        {"Item": "Wheat", "Year": 2022, "Unit": "t", "Value": 100.0},
        {"Item": "Wheat", "Year": 2023, "Unit": "t", "Value": 120.0},
        {"Item": "Wheat", "Year": 2024, "Unit": "t", "Value": 90.0},
        {"Item": "Barley", "Year": 2024, "Unit": "t", "Value": 50.0},
    ]).to_csv(production_path, index=False)

    pd.DataFrame([
        {
            "crop": "Wheat",
            "forecast_year": 2025,
            "predicted_production": 95.0,
            "selected_method": "naive",
        }
    ]).to_csv(forecast_path, index=False)

    climate_path = tmp_path / "climate.csv"
    pd.DataFrame([
        {
            "location": "Agadir",
            "latitude": 30.4278,
            "longitude": -9.5981,
            "year": 2023,
            "mean_temperature_c": 21.0,
            "mean_daily_max_temperature_c": 28.0,
            "mean_daily_min_temperature_c": 15.0,
            "total_precipitation": 250.0,
            "mean_daily_solar_radiation": 20.5,
            "days_observed": 365,
        },
        {
            "location": "Agadir",
            "latitude": 30.4278,
            "longitude": -9.5981,
            "year": 2024,
            "mean_temperature_c": 22.0,
            "mean_daily_max_temperature_c": 29.0,
            "mean_daily_min_temperature_c": 16.0,
            "total_precipitation": 200.0,
            "mean_daily_solar_radiation": 21.0,
            "days_observed": 366,
        },
        {
            "location": "Fes",
            "latitude": 34.0331,
            "longitude": -5.0003,
            "year": 2024,
            "mean_temperature_c": 19.0,
            "mean_daily_max_temperature_c": 26.0,
            "mean_daily_min_temperature_c": 12.0,
            "total_precipitation": 300.0,
            "mean_daily_solar_radiation": 19.0,
            "days_observed": 366,
        },
    ]).to_csv(climate_path, index=False)

    app = create_app(
        production_path=production_path,
        forecast_path=forecast_path,
        climate_path=climate_path,
    )
    app.config["TESTING"] = True

    return app.test_client()


def test_health_returns_ok(api_client):
    response = api_client.get("/api/health")

    assert response.status_code == 200
    assert response.json["status"] == "ok"
    assert response.json["datasets"]["production"] is True
    assert response.json["datasets"]["forecasts"] is True


def test_list_crops(api_client):
    response = api_client.get("/api/crops")

    assert response.status_code == 200
    assert response.json["count"] == 2
    assert response.json["crops"] == ["Barley", "Wheat"]


def test_crop_history_is_sorted_by_year(api_client):
    response = api_client.get("/api/crops/Wheat/history")

    assert response.status_code == 200
    assert response.json["count"] == 3
    assert [row["Year"] for row in response.json["history"]] == [
        2022, 2023, 2024
    ]


def test_crop_summary_calculates_year_over_year_change(api_client):
    response = api_client.get("/api/crops/Wheat/summary")

    assert response.status_code == 200
    data = response.json

    assert data["latest_year"] == 2024
    assert data["latest_production"] == 90.0
    assert data["year_over_year"]["previous_year_production"] == 120.0
    assert data["year_over_year"]["change_in_production"] == -30.0
    assert data["year_over_year"]["change_percentage"] == pytest.approx(-25.0)


def test_crop_forecast_returns_matching_forecast(api_client):
    response = api_client.get("/api/crops/Wheat/forecast")

    assert response.status_code == 200
    assert response.json["count"] == 1
    assert response.json["forecasts"][0]["forecast_year"] == 2025
    assert response.json["forecasts"][0]["predicted_production"] == 95.0


def test_unknown_crop_history_returns_404(api_client):
    response = api_client.get("/api/crops/UnknownCrop/history")

    assert response.status_code == 404
    assert "error" in response.json


def test_unknown_crop_summary_returns_404(api_client):
    response = api_client.get("/api/crops/UnknownCrop/summary")

    assert response.status_code == 404
    assert "error" in response.json


def test_missing_forecast_file_returns_503(tmp_path):
    production_path = tmp_path / "production.csv"
    missing_forecast_path = tmp_path / "missing_forecasts.csv"

    pd.DataFrame([
        {"Item": "Wheat", "Year": 2024, "Unit": "t", "Value": 90.0}
    ]).to_csv(production_path, index=False)

    app = create_app(
        production_path=production_path,
        forecast_path=missing_forecast_path,
    )
    app.config["TESTING"] = True

    response = app.test_client().get("/api/crops/Wheat/forecast")

    assert response.status_code == 503
    assert "error" in response.json


def test_climate_returns_sorted_annual_records(api_client):
    response = api_client.get("/api/climate")

    assert response.status_code == 200
    assert response.json["count"] == 3
    assert response.json["locations"] == ["Agadir", "Fes"]
    assert [row["year"] for row in response.json["records"][:2]] == [
        2023, 2024
    ]


def test_climate_can_filter_by_location_and_year(api_client):
    response = api_client.get("/api/climate?location=Agadir&year=2024")

    assert response.status_code == 200
    assert response.json["count"] == 1
    record = response.json["records"][0]
    assert record["location"] == "Agadir"
    assert record["year"] == 2024
    assert record["mean_temperature_c"] == 22.0
    assert record["total_precipitation"] == 200.0


def test_climate_unknown_location_returns_404(api_client):
    response = api_client.get("/api/climate?location=Unknown")

    assert response.status_code == 404
    assert "available_locations" in response.json


def test_climate_invalid_year_returns_400(api_client):
    response = api_client.get("/api/climate?year=twenty")

    assert response.status_code == 400
    assert "error" in response.json


def test_climate_unknown_year_returns_404(api_client):
    response = api_client.get("/api/climate?year=1900")

    assert response.status_code == 404


def test_health_reports_climate_dataset(api_client):
    response = api_client.get("/api/health")

    assert response.status_code == 200
    assert response.json["datasets"]["climate"] is True
