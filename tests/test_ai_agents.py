import pandas as pd

from agrimarket.ai.agents import (
    climate_agent,
    forecasting_agent,
    production_agent,
    validation_agent,
)


def test_production_agent_returns_real_dataset():
    result = production_agent("Wheat")
    assert result["agent"] == "production"
    assert result["status"] == "ok"
    assert result["observations"] > 0
    assert result["latest_year"] >= result["first_year"]


def test_production_agent_handles_unknown_crop():
    result = production_agent("Crop That Does Not Exist")
    assert result["status"] == "no_data"


def test_climate_agent_returns_locations():
    result = climate_agent()
    assert result["agent"] == "climate"
    assert result["status"] == "ok"
    assert result["locations"]


def test_forecasting_agent_handles_unknown_crop():
    result = forecasting_agent("Crop That Does Not Exist")
    assert result["status"] == "no_data"


def test_validation_rejects_empty_evidence():
    result = validation_agent({})
    assert result["approved"] is False
    assert result["status"] == "insufficient_evidence"


def test_validation_accepts_structured_evidence():
    result = validation_agent({
        "production": {
            "status": "ok",
            "records": [{"Item": "Wheat", "Value": 100}],
        }
    })
    assert result["approved"] is True
    assert result["status"] == "ok"
