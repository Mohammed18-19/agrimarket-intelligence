from agrimarket.ai.workflow import ask_agricultural_question, route_question


def test_router_selects_climate_and_forecasting():
    result = route_question({
        "question": "Compare rainfall and the wheat production forecast",
        "messages": [],
    })

    assert "climate" in result["tasks"]
    assert "forecasting" in result["tasks"]
    assert "production" in result["tasks"]


def test_router_uses_all_specialists_for_general_question():
    result = route_question({
        "question": "What should I know?",
        "messages": [],
    })

    assert result["tasks"] == ["production", "climate", "forecasting"]



def test_suitability_router_prefers_explicit_agadir_over_morocco_and_clears_crop():
    from agrimarket.ai.workflow import route_question

    result = route_question({
        "question": (
            "I'm a farmer in the Agadir region of Morocco. Which crops "
            "would be most suitable, and what climate risks should I consider?"
        ),
        "location": "Morocco",
        "crop": "Wheat",
        "messages": [],
    })

    assert result["location"] == "Agadir"
    assert result["crop"] == ""
    assert "climate" in result["tasks"]
    assert "production" in result["tasks"]


def test_suitability_fallback_compares_crops_and_uses_agadir_climate():
    from agrimarket.ai.workflow import route_question, run_agents

    state = {
        "question": (
            "I'm a farmer in the Agadir region of Morocco. Based on historical "
            "climate data and agricultural production trends, which crops "
            "would be most suitable for my region, and what climate risks "
            "should I consider before planting?"
        ),
        "location": "Morocco",
        "crop": "Wheat",
        "messages": [],
    }
    state.update(route_question(state))
    state.update(run_agents(state))

    production = state["evidence"]["production"]
    climate = state["evidence"]["climate"]

    assert production["status"] == "ok"
    assert production["crop_count"] == 92
    assert climate["status"] == "ok"
    assert climate["locations"] == ["Agadir"]
    assert climate["years"] == [2015, 2024]


def test_empty_question_is_rejected():
    try:
        ask_agricultural_question("   ")
    except ValueError as exc:
        assert "cannot be empty" in str(exc)
    else:
        raise AssertionError("Expected empty question to be rejected")


def test_agent_allows_last_configured_tool_round():
    from langchain_core.messages import AIMessage
    from agrimarket.ai.workflow import MAX_TOOL_ROUNDS, _after_model

    response = AIMessage(
        content="",
        tool_calls=[{
            "name": "get_crop_production",
            "args": {"crop": "Wheat"},
            "id": "test-call",
            "type": "tool_call",
        }],
    )

    assert _after_model({
        "messages": [response],
        "tool_rounds": MAX_TOOL_ROUNDS,
    }) == "tools"


def test_agent_stops_tool_calls_after_max_rounds():
    from langchain_core.messages import AIMessage
    from agrimarket.ai.workflow import MAX_TOOL_ROUNDS, _after_model

    response = AIMessage(
        content="",
        tool_calls=[{
            "name": "get_crop_production",
            "args": {"crop": "Wheat"},
            "id": "test-call",
            "type": "tool_call",
        }],
    )

    assert _after_model({
        "messages": [response],
        "tool_rounds": MAX_TOOL_ROUNDS + 1,
    }) == "agent_finalize"



def test_forecast_metric_context_uses_evidence_and_discloses_unknown_years():
    from agrimarket.ai.workflow import _format_forecast_metric_context

    evidence = {
        "forecasting": {
            "status": "ok",
            "crop": "Wheat",
            "records": [{
                "crop": "Wheat",
                "forecast_year": 2025,
                "selected_method": "linear_trend",
                "validation_mae": 677522.541964,
                "validation_start_year": 2023,
                "validation_end_year": 2024,
                "unit": "t",
            }],
            "evaluation": [{
                "method": "linear_trend",
                "MAE": 2122436.841766858,
                "test_observations": 5,
                "unit": "t",
            }],
        }
    }

    result = _format_forecast_metric_context(evidence)

    assert "677,522.54 t" in result
    assert "validation period 2023–2024" in result
    assert "2,122,436.84 t" in result
    assert "5 test observations" in result
    assert "do not specify the test years" in result
    assert "overlap the validation period" in result
    assert "independent observations" not in result


def test_forecast_metric_context_is_empty_without_forecast_evidence():
    from agrimarket.ai.workflow import _format_forecast_metric_context

    assert _format_forecast_metric_context({}) == ""
    assert _format_forecast_metric_context({
        "forecasting": {"status": "error"}
    }) == ""


def test_finalize_keeps_production_comparison_separate_from_crop_history():
    import json
    from langchain_core.messages import AIMessage, ToolMessage
    from agrimarket.ai.workflow import _finalize_agent_turn

    messages = [
        ToolMessage(
            name="get_crop_production_comparison",
            tool_call_id="comparison-call",
            content=json.dumps({
                "agent": "production_comparison",
                "status": "ok",
                "crop_count": 92,
                "records": [{"crop": "Wheat", "latest_production": 100}],
            }),
        ),
        ToolMessage(
            name="get_crop_production",
            tool_call_id="wheat-call",
            content=json.dumps({
                "agent": "production",
                "status": "ok",
                "crop": "Wheat",
                "records": [{"Item": "Wheat", "Value": 100}],
            }),
        ),
        AIMessage(content="Comparison and crop history retrieved."),
    ]

    result = _finalize_agent_turn({
        "question": "Compare crops and inspect Wheat production",
        "messages": messages,
        "turn_start": 0,
    })

    evidence = result["answer"]["evidence"]
    assert evidence["production"]["crop"] == "Wheat"
    assert evidence["production_comparison"]["crop_count"] == 92


def test_finalize_does_not_let_no_data_erase_successful_production():
    import json
    from langchain_core.messages import AIMessage, ToolMessage
    from agrimarket.ai.workflow import _finalize_agent_turn

    messages = [
        ToolMessage(
            name="get_crop_production",
            tool_call_id="success-call",
            content=json.dumps({
                "agent": "production",
                "status": "ok",
                "crop": "Wheat",
                "records": [{"Item": "Wheat", "Value": 100}],
            }),
        ),
        ToolMessage(
            name="get_crop_production",
            tool_call_id="empty-call",
            content=json.dumps({
                "agent": "production",
                "status": "no_data",
                "records": [],
            }),
        ),
        AIMessage(content="Production evidence was retrieved."),
    ]

    result = _finalize_agent_turn({
        "question": "Check Wheat production",
        "messages": messages,
        "turn_start": 0,
    })

    production = result["answer"]["evidence"]["production"]
    assert production["status"] == "ok"
    assert production["crop"] == "Wheat"
    assert result["answer"]["analysis_source"] == "openrouter"


def test_climate_numeric_guard_replaces_contradictory_rainfall_claim():
    from agrimarket.ai.workflow import _ground_climate_numeric_claims

    evidence = {
        "climate": {
            "status": "ok",
            "records": [
                {
                    "location": "Agadir",
                    "year": 2018,
                    "mean_temperature_c": 20.0371,
                    "total_precipitation": 284.22,
                }
            ],
        }
    }

    answer, conflict = _ground_climate_numeric_claims(
        "Agadir received 245.6 mm of rainfall in 2018.",
        evidence,
    )

    assert conflict is True
    assert "245.6 mm" not in answer
    assert "284.22 mm" in answer
    assert "evidence-based summary" in answer


def test_climate_numeric_guard_preserves_matching_claim():
    from agrimarket.ai.workflow import _ground_climate_numeric_claims

    evidence = {
        "climate": {
            "status": "ok",
            "records": [
                {
                    "location": "Agadir",
                    "year": 2018,
                    "mean_temperature_c": 20.0371,
                    "total_precipitation": 284.22,
                }
            ],
        }
    }

    original = "Agadir received 284.22 mm of rainfall in 2018."
    answer, conflict = _ground_climate_numeric_claims(original, evidence)

    assert conflict is False
    assert answer == original
