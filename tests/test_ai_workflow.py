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
