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

def test_climate_national_overview_includes_latest_record_for_every_location():
    result = climate_agent()
    assert result["status"] == "ok"
    assert result["records_scope"] == "latest_year_all_locations"
    assert result["records_count"] == len(result["locations"])
    assert len(result["records"]) == len(result["locations"])
    assert {record["year"] for record in result["records"]} == {
        result["latest_year"]
    }


def test_climate_location_request_returns_full_history():
    result = climate_agent("Agadir")
    assert result["status"] == "ok"
    assert result["records_scope"] == "full_location_history"
    assert len(result["records"]) == 10
    assert {record["location"] for record in result["records"]} == {"Agadir"}
    assert {record["year"] for record in result["records"]} == set(
        range(2015, 2025)
    )


def test_climate_averages_disclose_their_period():
    result = climate_agent()
    assert result["averages_period"] == "2015-2024"
    assert "not values for one year" in result["averages_description"]


def test_production_agent_does_not_compare_nonconsecutive_years(monkeypatch):
    import agrimarket.ai.agents as agents

    sample = pd.DataFrame([
        {"Item": "Wheat", "Year": 2020, "Unit": "t", "Value": 100},
        {"Item": "Wheat", "Year": 2022, "Unit": "t", "Value": 150},
    ])

    monkeypatch.setattr(agents, "_read", lambda filename: sample.copy())

    result = agents.production_agent("Wheat")

    assert result["status"] == "ok"
    assert result["latest_year"] == 2022
    assert result["previous_year_production"] is None
    assert result["change"] is None
    assert result["change_percentage"] is None


def test_production_agent_calculates_change_for_consecutive_years(monkeypatch):
    import agrimarket.ai.agents as agents

    sample = pd.DataFrame([
        {"Item": "Wheat", "Year": 2022, "Unit": "t", "Value": 100},
        {"Item": "Wheat", "Year": 2023, "Unit": "t", "Value": 125},
        {"Item": "Wheat", "Year": 2024, "Unit": "t", "Value": 150},
    ])

    monkeypatch.setattr(agents, "_read", lambda filename: sample.copy())

    result = agents.production_agent("Wheat")

    assert result["latest_year"] == 2024
    assert result["previous_year_production"] == 125.0
    assert result["change"] == 25.0
    assert result["change_percentage"] == 20.0


def test_production_comparison_does_not_compare_nonconsecutive_years(
    monkeypatch,
):
    import agrimarket.ai.production_comparison as comparison

    sample = pd.DataFrame([
        {"Item": "Wheat", "Year": 2020, "Unit": "t", "Value": 100},
        {"Item": "Wheat", "Year": 2022, "Unit": "t", "Value": 150},
        {"Item": "Barley", "Year": 2021, "Unit": "t", "Value": 80},
        {"Item": "Barley", "Year": 2022, "Unit": "t", "Value": 100},
    ])

    monkeypatch.setattr(comparison, "_read", lambda filename: sample.copy())

    result = comparison.production_comparison_agent()
    crops = {record["crop"]: record for record in result["records"]}

    assert result["status"] == "ok"

    assert crops["Wheat"]["latest_year"] == 2022
    assert crops["Wheat"]["previous_year"] is None
    assert crops["Wheat"]["change"] is None
    assert crops["Wheat"]["change_percentage"] is None

    assert crops["Barley"]["previous_year"] == 2021
    assert crops["Barley"]["change"] == 20.0
    assert crops["Barley"]["change_percentage"] == 25.0


def test_validation_does_not_claim_generated_answer_was_verified():
    result = validation_agent({
        "climate": {
            "status": "ok",
            "records": [
                {
                    "location": "Agadir",
                    "year": 2018,
                    "total_precipitation": 284.22,
                }
            ],
        }
    })

    assert result["approved"] is True
    assert result["validation_scope"] == "evidence_structure_only"
    assert result["answer_verified"] is False
    assert "does not verify numerical claims" in result["note"]


def test_production_overview_does_not_report_cross_crop_change():
    result = production_agent()

    assert result["status"] == "ok"
    assert result["scope"] == "latest_record_per_crop"
    assert result["crop"] is None
    assert result["crops_count"] > 1
    assert "change_percentage" not in result
    assert len(result["records"]) == result["crops_count"]
