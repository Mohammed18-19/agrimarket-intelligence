"""LangGraph orchestration for tool-using agricultural intelligence.

With GROQ_API_KEY configured, the model dynamically selects specialist tools.
Without a key, a deterministic workflow still returns real dataset evidence.
Conversation state is kept in an in-process checkpointer when conversation_id
is supplied; it is intentionally not durable across backend restarts.
"""

import importlib.util
import json
import os
from typing import Annotated, TypedDict, Iterator

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agrimarket.ai.agents import (
    climate_agent,
    forecasting_agent,
    production_agent,
    validation_agent,
)


MAX_TOOL_ROUNDS = 5
MODEL_NAME = os.getenv("AGRIMARKET_LLM_MODEL", "openai/gpt-oss-120b")


class WorkflowState(TypedDict, total=False):
    question: str
    crop: str
    location: str
    conversation_id: str
    tasks: list[str]
    evidence: dict
    validation: dict
    answer: dict
    messages: Annotated[list[AnyMessage], add_messages]
    tool_rounds: int
    turn_start: int


def _tool_result(agent_name, function, *args) -> str:
    """Serialize a specialist result while keeping tool failures inspectable."""
    try:
        result = function(*args)
    except (OSError, ValueError, KeyError) as exc:
        result = {
            "agent": agent_name,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return json.dumps(result, ensure_ascii=False, default=str)


@tool
def get_crop_production(crop: str = "") -> str:
    """Retrieve observed annual production and changes for a Moroccan crop.

    Use this for historical production, crop trends, harvest history, and
    year-over-year changes. Pass the crop name when known; use an empty string
    to retrieve a national overview.
    """
    return _tool_result("production", production_agent, crop.strip() or None)


@tool
def get_climate_observations(location: str = "") -> str:
    """Retrieve annual NASA POWER climate observations for Morocco.

    Use this for temperature, rainfall/precipitation, solar radiation, or
    climate-history questions. Pass a location such as Agadir when specified;
    use an empty string for available locations.
    """
    return _tool_result("climate", climate_agent, location.strip() or None)


@tool
def get_crop_forecasts(crop: str = "") -> str:
    """Retrieve existing experimental crop-production forecasts and evaluation.

    Use this for forecast/prediction questions. Forecasts are estimates, not
    observed values or guarantees. Pass the crop name when known.
    """
    return _tool_result("forecasting", forecasting_agent, crop.strip() or None)


AGRICULTURAL_TOOLS = [
    get_crop_production,
    get_climate_observations,
    get_crop_forecasts,
]

SYSTEM_PROMPT = """You are AgriMarket Intelligence, an agricultural data analyst
focused on Morocco. You can call tools that retrieve the project's real
FAOSTAT production data, NASA POWER annual climate observations, and existing
experimental forecasts.

For factual production, climate, or forecast questions, call the relevant
tools before answering. Use only relevant tools and base numeric claims on
their outputs. Distinguish observed values from forecasts and state the year,
unit, and method when available.

Forecast metric rules:
- validation_mae is the model-selection score for the period identified by
  validation_start_year and validation_end_year.
- An evaluation entry's MAE is a separate reported metric associated with its
  test_observations count. Never substitute one metric for the other.
- Do not infer evaluation years, sample independence, or overlap from the
  observation count alone. State when those details are unavailable.
- Never describe a forecast as an observed value.

Never invent data, infer causation from correlation, or claim that one climate
location represents all of Morocco. Explain important data limitations.
Evidence validation checks data availability and structure; it does not prove
that every generated statement is factually correct. Keep answers useful,
direct, and evidence-grounded."""


def route_question(state: WorkflowState) -> dict:
    """Route deterministically when no hosted model is configured."""
    question = state["question"].casefold()
    tasks = []

    if any(word in question for word in (
        "climate", "temperature", "rain", "rainfall", "precipitation",
        "weather", "solar", "drought", "climate risk",
    )):
        tasks.append("climate")

    if any(word in question for word in (
        "forecast", "predict", "prediction", "future", "expected",
        "projection",
    )):
        tasks.append("forecasting")

    if any(word in question for word in (
        "production", "produce", "harvest", "trend", "yield", "crop",
        "wheat", "barley", "tomato", "olive", "citrus",
    )):
        tasks.append("production")

    if not tasks:
        tasks = ["production", "climate", "forecasting"]

    updates = {"tasks": list(dict.fromkeys(tasks))}
    messages = state.get("messages", [])
    # The most recent message is the current user turn before tool calls begin.
    updates["turn_start"] = max(0, len(messages) - 1)
    updates["tool_rounds"] = 0
    return updates


def run_agents(state: WorkflowState) -> dict:
    """Execute the specialist data functions for the no-key fallback."""
    evidence = {}
    crop = state.get("crop") or None
    location = state.get("location") or None

    for task in state["tasks"]:
        try:
            if task == "production":
                evidence[task] = production_agent(crop)
            elif task == "climate":
                evidence[task] = climate_agent(location)
            elif task == "forecasting":
                evidence[task] = forecasting_agent(crop)
        except (OSError, ValueError, KeyError) as exc:
            evidence[task] = {
                "agent": task,
                "status": "error",
                "error": str(exc),
            }

    return {"evidence": evidence}


def validate_evidence(state: WorkflowState) -> dict:
    """Check specialist outputs for missing or unusable evidence."""
    return {"validation": validation_agent(state.get("evidence", {}))}


def summarize(state: WorkflowState) -> dict:
    """Return the structured evidence payload used by the existing API/UI."""
    return {
        "answer": {
            "question": state["question"],
            "agents_used": state.get("tasks", []),
            "evidence": state.get("evidence", {}),
            "validation": state.get("validation", {}),
            "note": (
                "This response uses retrieved project data. Forecasts are "
                "estimates, and climate associations do not establish causation."
            ),
        }
    }


def _model_agent(state: WorkflowState) -> dict:
    """Ask the configured model to select and invoke data tools."""
    from langchain_groq import ChatGroq

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    model = ChatGroq(
        model=os.getenv("AGRIMARKET_LLM_MODEL", MODEL_NAME),
        temperature=0,
        api_key=api_key,
    ).bind_tools(AGRICULTURAL_TOOLS)

    messages = state.get("messages", [])
    response = model.invoke([SystemMessage(content=SYSTEM_PROMPT), *messages])
    return {
        "messages": [response],
        "tool_rounds": int(state.get("tool_rounds", 0)) + 1,
    }


def _after_model(state: WorkflowState) -> str:
    """Continue tool use until the model answers or the bound is reached."""
    messages = state.get("messages", [])
    if not messages:
        return "agent_finalize"
    last = messages[-1]
    if getattr(last, "tool_calls", None) and state.get("tool_rounds", 0) <= MAX_TOOL_ROUNDS:
        return "tools"
    return "agent_finalize"


def _format_forecast_metric_context(evidence: dict) -> str:
    """Format forecast metrics directly from retrieved evidence."""
    forecast = evidence.get("forecasting", {})
    if not isinstance(forecast, dict) or forecast.get("status") != "ok":
        return ""

    lines = [
        "",
        "",
        "### Verified forecast metric context",
        "The following figures are copied from the retrieved project evidence.",
    ]

    for record in forecast.get("records", []):
        if not isinstance(record, dict):
            continue
        mae = record.get("validation_mae")
        if mae is None:
            continue
        crop = record.get("crop", forecast.get("crop", "Selected crop"))
        year = record.get("forecast_year", "unspecified")
        unit = record.get("unit", "")
        method = record.get("selected_method", "unspecified")
        start = record.get("validation_start_year")
        end = record.get("validation_end_year")
        period = f"{start}–{end}" if start is not None and end is not None else "not specified"
        lines.append(
            f"- {crop} forecast for {year}: validation MAE "
            f"{float(mae):,.2f} {unit}; validation period {period}; "
            f"selected method {method}."
        )

    evaluations = [
        item for item in forecast.get("evaluation", [])
        if isinstance(item, dict) and item.get("MAE", item.get("mae")) is not None
    ]
    if evaluations:
        lines.append(
            "- Separate evaluation metrics (not interchangeable with the "
            "forecast record's validation MAE):"
        )
        for item in evaluations:
            method = item.get("method", "unspecified")
            mae = float(item.get("MAE", item.get("mae")))
            unit = item.get("unit", "")
            count = item.get("test_observations", "unspecified")
            lines.append(
                f"  - {method}: MAE {mae:,.2f} {unit}; "
                f"{count} test observations."
            )
        lines.append(
            "- The available evaluation entries do not specify the test years "
            "or establish whether those observations overlap the validation "
            "period. Do not claim otherwise."
        )

    if len(lines) == 4:
        return ""
    return "\n".join(lines)


def _finalize_agent_turn(state: WorkflowState) -> dict:
    """Extract structured tool evidence and the final model answer."""
    messages = state.get("messages", [])
    start = state.get("turn_start", 0)
    current_messages = messages[start:]
    evidence = {}
    tool_to_agent = {
        "get_crop_production": "production",
        "get_climate_observations": "climate",
        "get_crop_forecasts": "forecasting",
    }

    for message in current_messages:
        if not isinstance(message, ToolMessage):
            continue
        key = tool_to_agent.get(getattr(message, "name", None))
        if not key:
            continue
        try:
            payload = json.loads(message.content)
            if isinstance(payload, dict):
                evidence[key] = payload
        except (TypeError, json.JSONDecodeError):
            evidence[key] = {
                "agent": key,
                "status": "error",
                "error": "Tool returned a non-JSON result.",
            }

    validation = validation_agent(evidence)
    final_message = next(
        (
            message for message in reversed(current_messages)
            if isinstance(message, AIMessage) and not getattr(message, "tool_calls", None)
        ),
        None,
    )
    analysis = ""
    if final_message is not None:
        content = final_message.content
        analysis = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)

    if not analysis.strip():
        analysis = (
            "I retrieved the available agricultural evidence, but the language "
            "model did not return a final explanation. Review the evidence and "
            "validation details below."
        )

    analysis += _format_forecast_metric_context(evidence)

    return {
        "evidence": evidence,
        "validation": validation,
        "tasks": list(evidence),
        "answer": {
            "question": state["question"],
            "agents_used": list(evidence),
            "evidence": evidence,
            "validation": validation,
            "analysis": analysis,
            "analysis_source": "groq",
            "analysis_model": os.getenv("AGRIMARKET_LLM_MODEL", MODEL_NAME),
            "analysis_fallback_reason": None,
            "note": (
                "Tool-grounded answer. Forecasts are estimates; climate "
                "observations do not by themselves establish causation."
            ),
        },
    }


def _route_mode(state: WorkflowState) -> str:
    # Do not crash if a user sets the key but has not installed the optional
    # provider package; the deterministic workflow remains available.
    provider_installed = importlib.util.find_spec("langchain_groq") is not None
    return (
        "agent"
        if os.getenv("GROQ_API_KEY") and provider_installed
        else "specialists"
    )


def build_workflow():
    graph = StateGraph(WorkflowState)
    graph.add_node("route", route_question)
    graph.add_node("specialists", run_agents)
    graph.add_node("validate", validate_evidence)
    graph.add_node("summarize", summarize)
    graph.add_node("agent", _model_agent)
    graph.add_node("tools", ToolNode(AGRICULTURAL_TOOLS))
    graph.add_node("agent_finalize", _finalize_agent_turn)

    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route",
        _route_mode,
        {"agent": "agent", "specialists": "specialists"},
    )
    graph.add_edge("specialists", "validate")
    graph.add_edge("validate", "summarize")
    graph.add_edge("summarize", END)
    graph.add_conditional_edges(
        "agent",
        _after_model,
        {"tools": "tools", "agent_finalize": "agent_finalize"},
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("agent_finalize", END)

    return graph.compile(checkpointer=InMemorySaver())


agricultural_workflow = build_workflow()


def ask_agricultural_question(
    question: str,
    crop: str | None = None,
    location: str | None = None,
    conversation_id: str | None = None,
) -> dict:
    """Run the tool-using workflow or deterministic data-backed fallback."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question cannot be empty.")

    selected_crop = crop.strip() if isinstance(crop, str) else ""
    selected_location = location.strip() if isinstance(location, str) else ""
    message_content = (
        f"Question: {question.strip()}\n"
        f"Selected crop context: {selected_crop or 'not specified'}\n"
        f"Selected climate location context: {selected_location or 'not specified'}"
    )
    config = {"configurable": {"thread_id": conversation_id or "default"}}
    # Avoid carrying conversation state between unrelated users when no ID is
    # provided by assigning a per-request thread. The default fallback remains
    # stateless from the API caller's perspective.
    if not conversation_id:
        import uuid
        config["configurable"]["thread_id"] = str(uuid.uuid4())

    config["recursion_limit"] = 2 * MAX_TOOL_ROUNDS + 8
    result = agricultural_workflow.invoke(
        {
            "question": question.strip(),
            "crop": selected_crop,
            "location": selected_location,
            "messages": [HumanMessage(content=message_content)],
        },
        config=config,
    )
    return result["answer"]



def stream_agricultural_question(
    question: str,
    crop: str | None = None,
    location: str | None = None,
    conversation_id: str | None = None,
) -> Iterator[dict]:
    """Yield real LangGraph node/tool events, followed by the final answer.

    Events are derived from graph stream updates; this does not simulate agent
    activity. The final event contains the same structured answer as the
    synchronous API. In-process checkpoint state is still not durable.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question cannot be empty.")

    selected_crop = crop.strip() if isinstance(crop, str) else ""
    selected_location = location.strip() if isinstance(location, str) else ""
    message_content = (
        f"Question: {question.strip()}\n"
        f"Selected crop context: {selected_crop or 'not specified'}\n"
        f"Selected climate location context: {selected_location or 'not specified'}"
    )
    config = {"configurable": {"thread_id": conversation_id or __import__("uuid").uuid4().hex}}
    config["recursion_limit"] = 2 * MAX_TOOL_ROUNDS + 8
    initial = {
        "question": question.strip(),
        "crop": selected_crop,
        "location": selected_location,
        "messages": [HumanMessage(content=message_content)],
    }

    final_answer = None
    for update in agricultural_workflow.stream(
        initial, config=config, stream_mode="updates"
    ):
        for node_name, node_update in update.items():
            messages = node_update.get("messages", []) if isinstance(node_update, dict) else []
            for message in messages:
                tool_calls = getattr(message, "tool_calls", None) or []
                for call in tool_calls:
                    yield {
                        "type": "tool_call",
                        "node": node_name,
                        "tool": call.get("name", "unknown_tool"),
                        "status": "requested",
                        "input": call.get("args", {}),
                    }
                if isinstance(message, ToolMessage):
                    yield {
                        "type": "tool_result",
                        "node": node_name,
                        "tool": getattr(message, "name", "unknown_tool"),
                        "status": "returned",
                        "content": str(message.content)[:12000],
                    }

            event = {
                "type": "node",
                "node": node_name,
                "status": "completed",
                "detail": _node_event_detail(node_name, node_update),
            }
            yield event
            if isinstance(node_update, dict) and isinstance(node_update.get("answer"), dict):
                final_answer = node_update["answer"]

    if final_answer is None:
        # Defensive fallback: the graph should emit a terminal answer update.
        final_answer = ask_agricultural_question(
            question, crop, location, conversation_id
        )
    if not final_answer.get("analysis"):
        from agrimarket.ai.analyst import summarize_evidence_with_metadata
        evidence_for_summary = {
            **final_answer.get("evidence", {}),
            "validation": final_answer.get("validation", {}),
        }
        final_answer.update(
            summarize_evidence_with_metadata(question.strip(), evidence_for_summary)
        )
    yield {"type": "final", "answer": final_answer}


def _node_event_detail(node_name: str, update: dict) -> str:
    """Human-readable detail grounded in the actual graph node update."""
    if node_name == "route":
        tasks = update.get("tasks", [])
        return "Selected specialists: " + (", ".join(tasks) if tasks else "none")
    if node_name == "specialists":
        evidence = update.get("evidence", {})
        return f"Retrieved evidence from {len(evidence)} specialist(s)"
    if node_name == "validate":
        validation = update.get("validation", {})
        return f"Evidence validation: {validation.get('status', 'unknown')}"
    if node_name == "tools":
        return "Tool execution node returned results"
    if node_name == "agent":
        messages = update.get("messages", [])
        calls = [
            call.get("name", "tool")
            for message in messages
            for call in (getattr(message, "tool_calls", None) or [])
        ]
        return "Model selected: " + (", ".join(calls) if calls else "next reasoning step")
    if node_name == "agent_finalize":
        answer = update.get("answer", {})
        return f"Final answer prepared; {len(answer.get('agents_used', []))} specialist(s) reported"
    if node_name == "summarize":
        answer = update.get("answer", {})
        return f"Evidence summary prepared; {len(answer.get('agents_used', []))} specialist(s)"
    return "Workflow node completed"
