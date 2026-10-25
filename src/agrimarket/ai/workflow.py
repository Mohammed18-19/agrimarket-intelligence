"""LangGraph orchestration for agricultural intelligence."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agrimarket.ai.agents import (
    climate_agent,
    forecasting_agent,
    production_agent,
    validation_agent,
)


class WorkflowState(TypedDict, total=False):
    question: str
    crop: str
    location: str
    tasks: list[str]
    evidence: dict
    validation: dict
    answer: dict


def route_question(state: WorkflowState) -> dict:
    """Choose relevant agents using transparent routing rules."""
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

    # General agricultural questions should retrieve more than one source.
    if not tasks:
        tasks = ["production", "climate", "forecasting"]

    return {"tasks": list(dict.fromkeys(tasks))}


def run_agents(state: WorkflowState) -> dict:
    """Run selected specialist agents and collect their evidence."""
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
    """Check whether specialist outputs contain usable evidence."""
    return {"validation": validation_agent(state.get("evidence", {}))}


def summarize(state: WorkflowState) -> dict:
    """Return a structured, evidence-grounded result for the API or LLM."""
    return {
        "answer": {
            "question": state["question"],
            "agents_used": state.get("tasks", []),
            "evidence": state.get("evidence", {}),
            "validation": state.get("validation", {}),
            "note": (
                "This response contains retrieved data, not an automatic "
                "causal explanation. Interpret conclusions within the "
                "limitations of each dataset."
            ),
        }
    }


def build_workflow():
    graph = StateGraph(WorkflowState)
    graph.add_node("route", route_question)
    graph.add_node("specialists", run_agents)
    graph.add_node("validate", validate_evidence)
    graph.add_node("summarize", summarize)

    graph.add_edge(START, "route")
    graph.add_edge("route", "specialists")
    graph.add_edge("specialists", "validate")
    graph.add_edge("validate", "summarize")
    graph.add_edge("summarize", END)

    return graph.compile()


agricultural_workflow = build_workflow()


def ask_agricultural_question(
    question: str,
    crop: str | None = None,
    location: str | None = None,
) -> dict:
    """Run the specialist workflow for a natural-language question."""
    if not question.strip():
        raise ValueError("Question cannot be empty.")

    result = agricultural_workflow.invoke({
        "question": question,
        "crop": crop or "",
        "location": location or "",
    })
    return result["answer"]
