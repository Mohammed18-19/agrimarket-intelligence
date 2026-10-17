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

    app = create_app(
        production_path=production_path,
        forecast_path=forecast_path,
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
