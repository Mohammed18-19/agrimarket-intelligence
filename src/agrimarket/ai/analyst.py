"""Evidence-grounded agricultural analyst using LangGraph and Groq."""

import os
from pathlib import Path
from typing import TypedDict

import pandas as pd
from langgraph.graph import END, START, StateGraph


ROOT = Path(
    os.environ.get("AGRIMARKET_PROJECT_ROOT", Path.cwd())
).resolve()
DATA = ROOT / "data" / "processed"


class AnalystState(TypedDict, total=False):
    question: str
    evidence: str
    answer: str
    error: str


def retrieve_evidence(state: AnalystState) -> dict:
    """Retrieve matching records from the project's real datasets."""
    question = state["question"].strip()
    if not question:
        return {"evidence": "", "error": "Question cannot be empty."}

    files = {
        "production": DATA / "faostat_morocco_production.csv",
        "climate": DATA / "nasa_power_annual.csv",
        "forecasts": DATA / "crop_production_forecasts.csv",
    }

    evidence = []
    terms = question.lower()

    for name, path in files.items():
        if not path.is_file():
            continue

        try:
            df = pd.read_csv(path)
        except (OSError, pd.errors.ParserError):
            continue

        # Match crop names and climate locations mentioned in the question.
        searchable = [
            c for c in ("Item", "crop", "location")
            if c in df.columns
        ]
        mask = pd.Series(False, index=df.index)

        for column in searchable:
            values = df[column].fillna("").astype(str)
            for value in values.unique():
                if len(value) >= 3 and value.lower() in terms:
                    mask |= values.eq(value)

        # General questions may use a small sample, never the entire dataset.
        matched = df.loc[mask] if mask.any() else df.head(5)
        evidence.append(
            f"{name.upper()} DATA ({path.name}):\n"
            f"{matched.head(8).to_json(orient='records')}"
        )

    if not evidence:
        return {
            "evidence": "",
            "error": "No project datasets could be read.",
        }

    return {"evidence": "\n\n".join(evidence)}


def generate_answer(state: AnalystState) -> dict:
    """Generate an answer grounded in retrieved evidence."""
    if state.get("error"):
        return {"answer": state["error"]}

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "answer": (
                "AI provider is not configured. Set GROQ_API_KEY to enable "
                "LLM analysis. Retrieved evidence:\n\n"
                + state.get("evidence", "")
            )
        }

    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import HumanMessage, SystemMessage

        model = ChatGroq(
            model=os.getenv("AGRIMARKET_LLM_MODEL", "openai/gpt-oss-120b"),
            temperature=0,
            api_key=api_key,
        )

        response = model.invoke([
            SystemMessage(content=(
                "You are an agricultural data analyst for Morocco. "
                "Answer using only the supplied dataset evidence. "
                "Do not invent measurements, causes, or recommendations. "
                "State when evidence is insufficient. Distinguish historical "
                "observations from model forecasts and explain limitations."
            )),
            HumanMessage(content=(
                f"Question: {state['question']}\n\n"
                f"Retrieved evidence:\n{state.get('evidence', '')}"
            )),
        ])
        return {"answer": str(response.content)}

    except Exception:
        return {
            "error": "AI provider request failed. Check the API key and provider.",
            "answer": "AI analysis is temporarily unavailable.",
        }


def build_graph():
    graph = StateGraph(AnalystState)
    graph.add_node("retrieve_evidence", retrieve_evidence)
    graph.add_node("generate_answer", generate_answer)
    graph.add_edge(START, "retrieve_evidence")
    graph.add_edge("retrieve_evidence", "generate_answer")
    graph.add_edge("generate_answer", END)
    return graph.compile()


analyst = build_graph()


def ask(question: str) -> dict:
    """Run the agricultural analyst workflow."""
    result = analyst.invoke({"question": question})
    return {
        "answer": result.get("answer", ""),
        "error": result.get("error"),
        "evidence": result.get("evidence", ""),
    }



def summarize_evidence_with_metadata(question: str, evidence: dict) -> dict:
    """Return the analysis and disclose whether Groq or the local fallback produced it."""
    model_name = os.getenv("AGRIMARKET_LLM_MODEL", "openai/gpt-oss-120b")
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return {
            "analysis": summarize_evidence(question, evidence),
            "analysis_source": "fallback",
            "analysis_model": None,
            "analysis_fallback_reason": "GROQ_API_KEY is not configured.",
        }

    try:
        from langchain_groq import ChatGroq
        from langchain_core.messages import HumanMessage, SystemMessage
        import json

        model = ChatGroq(
            model=model_name,
            temperature=0,
            api_key=api_key,
        )
        response = model.invoke([
            SystemMessage(content=(
                "You are an agricultural data analyst for Morocco. "
                "Answer using only the supplied evidence. Distinguish "
                "observations from predictions, report available metrics, "
                "explain limitations, and never invent missing data."
            )),
            HumanMessage(content=(
                f"Question: {question}\n\n"
                f"Evidence JSON:\n"
                f"{json.dumps(evidence, ensure_ascii=False, default=str)}"
            )),
        ])
        return {
            "analysis": str(response.content),
            "analysis_source": "groq",
            "analysis_model": model_name,
            "analysis_fallback_reason": None,
        }
    except Exception:
        return {
            "analysis": summarize_evidence(question, evidence, _allow_llm=False),
            "analysis_source": "fallback",
            "analysis_model": model_name,
            "analysis_fallback_reason": "Groq generation failed; local evidence-based analysis was used.",
        }


def summarize_evidence(question: str, evidence: dict, *, _allow_llm: bool = True) -> str:
    """Produce a detailed, evidence-grounded fallback analysis."""
    if not question.strip():
        raise ValueError("Question cannot be empty.")

    import json

    api_key = os.getenv("GROQ_API_KEY")
    if api_key and _allow_llm:
        try:
            from langchain_groq import ChatGroq
            from langchain_core.messages import HumanMessage, SystemMessage

            model = ChatGroq(
                model=os.getenv(
                    "AGRIMARKET_LLM_MODEL",
                    "openai/gpt-oss-120b",
                ),
                temperature=0,
                api_key=api_key,
            )
            response = model.invoke([
                SystemMessage(content=(
                    "You are an agricultural data analyst for Morocco. "
                    "Answer every part of the question using only the "
                    "supplied evidence. Report actual forecast values, "
                    "methods and error metrics when available. Distinguish "
                    "observations from predictions. Never infer causation "
                    "from climate summaries alone. Explain limitations and "
                    "do not invent missing data."
                )),
                HumanMessage(content=(
                    f"Question: {question}\\n\\n"
                    f"Evidence JSON:\\n"
                    f"{json.dumps(evidence, ensure_ascii=False, default=str)}"
                )),
            ])
            return str(response.content)
        except Exception:
            pass

    lines = [
        "Evidence-based agricultural analysis",
        "",
        "This answer is generated from the project's retrieved datasets. "
        "Observed values and model predictions are reported separately.",
    ]

    production = evidence.get("production", {})
    crop_name = (
        production.get("crop")
        or evidence.get("forecasting", {}).get("crop")
        or "Selected crop"
    )

    if production.get("status") == "ok":
        rows = production.get("records", [])
        rows = sorted(
            [
                row for row in rows
                if row.get("Year") is not None and row.get("Value") is not None
            ],
            key=lambda row: float(row["Year"]),
        )

        lines.extend(["", f"## Historical production: {crop_name}"])
        lines.append(
            f"- Latest observation: {production.get('latest_production'):,.2f} "
            f"{production.get('unit', '')} in {production.get('latest_year')}."
        )

        if production.get("change_percentage") is not None:
            lines.append(
                f"- Change from the previous observation: "
                f"{production['change_percentage']:+.2f}% "
                f"({production.get('change', 0):+,.2f} "
                f"{production.get('unit', '')})."
            )

        if rows:
            lines.append(
                f"- Available historical coverage: {int(float(rows[0]['Year']))}"
                f"–{int(float(rows[-1]['Year']))}, "
                f"{len(rows)} annual observations returned."
            )

            changes = []
            for previous, current in zip(rows, rows[1:]):
                previous_value = float(previous["Value"])
                current_value = float(current["Value"])
                absolute_change = current_value - previous_value
                percentage = (
                    absolute_change / previous_value * 100
                    if previous_value else None
                )
                changes.append({
                    "from_year": int(float(previous["Year"])),
                    "to_year": int(float(current["Year"])),
                    "change": absolute_change,
                    "percentage": percentage,
                })

            for label, ordered in (
                ("Largest increase", sorted(changes, key=lambda x: x["change"], reverse=True)),
                ("Largest decrease", sorted(changes, key=lambda x: x["change"])),
            ):
                if ordered:
                    item = ordered[0]
                    pct = (
                        f" ({item['percentage']:+.2f}%)"
                        if item["percentage"] is not None else ""
                    )
                    lines.append(
                        f"- {label}: {item['from_year']} to {item['to_year']}, "
                        f"{item['change']:+,.2f} {production.get('unit', '')}{pct}."
                    )

            if len(rows) >= 2:
                first_value = float(rows[0]["Value"])
                last_value = float(rows[-1]["Value"])
                if first_value:
                    lines.append(
                        f"- Net change across the returned period: "
                        f"{last_value - first_value:+,.2f} "
                        f"{production.get('unit', '')} "
                        f"({(last_value - first_value) / first_value * 100:+.2f}%)."
                    )
    elif "production" in evidence:
        lines.extend(["", "## Historical production", "No usable matching production observations were returned."])

    if production.get("status") == "ok" and rows:
        highest = max(rows, key=lambda row: float(row["Value"]))
        lowest = min(rows, key=lambda row: float(row["Value"]))
        lines.append(
            f"- Highest recorded year: {int(float(highest['Year']))}, "
            f"{float(highest['Value']):,.2f} {production.get('unit', '')}."
        )
        lines.append(
            f"- Lowest recorded year: {int(float(lowest['Year']))}, "
            f"{float(lowest['Value']):,.2f} {production.get('unit', '')}."
        )

    forecast = evidence.get("forecasting", {})
    if forecast.get("status") == "ok":
        lines.extend(["", f"## Forecast and model evaluation: {crop_name}"])
        records = forecast.get("records", [])
        for record in records:
            year = record.get("forecast_year", record.get("Year"))
            value = record.get("predicted_production", record.get("prediction"))
            method = record.get("selected_method", record.get("method", "unspecified"))
            unit = record.get("unit", production.get("unit", ""))
            if value is not None:
                lines.append(
                    f"- Forecast for {year}: {float(value):,.2f} {unit}, "
                    f"using {method}."
                )
            if record.get("validation_mae") is not None:
                lines.append(
                    f"- Forecast validation MAE: "
                    f"{float(record['validation_mae']):,.2f} {unit} "
                    f"(validation period "
                    f"{record.get('validation_start_year', '?')}–"
                    f"{record.get('validation_end_year', '?')})."
                )

        evaluations = forecast.get("evaluation", [])
        valid_errors = []
        for item in evaluations:
            method = item.get("method", "unspecified")
            mae = item.get("MAE", item.get("mae"))
            unit = item.get("unit", production.get("unit", ""))
            if mae is not None:
                mae = float(mae)
                valid_errors.append((method, mae, unit))
                lines.append(
                    f"- Evaluation MAE — {method}: {mae:,.2f} {unit}; "
                    f"{item.get('test_observations', '?')} test observations."
                )

        # The validation selection period and final holdout are different evaluations.
        try:
            holdout_path = DATA / "forecast_holdout_evaluation.csv"
            if holdout_path.is_file():
                holdout_df = pd.read_csv(holdout_path)
                crop_col = holdout_df["crop"].astype(str).str.casefold()
                matching = holdout_df.loc[crop_col == str(crop_name).casefold()]
                if not matching.empty:
                    h = matching.iloc[0]
                    lines.append(
                        "- Separate holdout evaluation: "
                        f"{int(h['holdout_start_year'])}–{int(h['holdout_end_year'])}, "
                        f"{int(h['holdout_observations'])} observations."
                    )
                    for key, label in (
                        ("naive_holdout_mae", "naive"),
                        ("linear_trend_holdout_mae", "linear_trend"),
                        ("selected_holdout_mae", "selected method"),
                    ):
                        value = h.get(key)
                        if pd.notna(value):
                            lines.append(
                                f"- Holdout MAE ({label}): {float(value):,.2f} "
                                f"{h.get('unit', production.get('unit', ''))}."
                            )
        except (OSError, KeyError, ValueError, pd.errors.ParserError):
            lines.append("- Separate holdout evaluation was unavailable.")

        if len(valid_errors) >= 2:
            best = min(valid_errors, key=lambda item: item[1])
            worst = max(valid_errors, key=lambda item: item[1])
            if worst[1] > 0:
                improvement = (worst[1] - best[1]) / worst[1] * 100
                lines.append(
                    f"- Among the listed evaluations, {best[0]} has the lower "
                    f"MAE, about {improvement:.1f}% lower than {worst[0]}. "
                    "This comparison does not guarantee future accuracy."
                )

        lines.append(
            "- Reliability limitation: MAE is the average absolute prediction "
            "error on the stated evaluation data, not a confidence interval. "
            "Errors can be large relative to actual production."
        )
        lines.append(
            "- Forecasts are model outputs, not observed production or guaranteed outcomes."
        )
    elif "forecasting" in evidence:
        lines.extend(["", "## Forecast", "No usable matching forecast records were returned."])

    climate = evidence.get("climate", {})
    if climate.get("status") == "ok":
        lines.extend(["", "## 🌦️ Climate analysis"])
        locations = climate.get("locations", [])
        location = locations[0] if locations else "Agadir"
        lines.append(
            f"- Climate dataset locations: {', '.join(locations) if locations else 'not specified'}."
        )

        # Calculate correlations from matched annual source records.
        # Never infer causation from correlations.
        try:
            production_path = DATA / "faostat_morocco_production.csv"
            climate_path = DATA / "nasa_power_annual.csv"
            prod_df = pd.read_csv(production_path)
            climate_df = pd.read_csv(climate_path)

            prod_crop = (
                production.get("crop")
                or evidence.get("forecasting", {}).get("crop")
                or crop_name
            )
            prod_df = prod_df.loc[
                prod_df["Item"].astype(str).str.casefold()
                == str(prod_crop).casefold(),
                ["Year", "Value"],
            ].copy()
            prod_df["year"] = pd.to_numeric(prod_df["Year"], errors="coerce")
            prod_df["production"] = pd.to_numeric(prod_df["Value"], errors="coerce")
            prod_df = prod_df[["year", "production"]].dropna()

            climate_df = climate_df.loc[
                climate_df["location"].astype(str).str.casefold()
                == str(location).casefold()
            ].copy()
            climate_df["year"] = pd.to_numeric(climate_df["year"], errors="coerce")

            joined = prod_df.merge(
                climate_df[
                    ["year", "mean_temperature_c", "total_precipitation"]
                ],
                on="year",
                how="inner",
            ).dropna(subset=["production"])
            lines.append(
                f"- Location used for comparison: {location}. "
                "National production is compared with this location only."
            )

            for column, label, unit in (
                ("mean_temperature_c", "mean temperature", "°C"),
                ("total_precipitation", "annual precipitation", "mm"),
            ):
                pairs = joined[["production", column]].copy()
                pairs[column] = pd.to_numeric(pairs[column], errors="coerce")
                pairs = pairs.dropna()
                n = len(pairs)
                if n >= 3 and pairs["production"].nunique() > 1 and pairs[column].nunique() > 1:
                    r = pairs["production"].corr(pairs[column], method="pearson")
                    lines.append(
                        f"- Pearson correlation with {label}: r = {r:+.3f} "
                        f"(n = {n} matched years; {unit})."
                    )
                    lines.append(
                        "  This describes association in the matched sample, "
                        "not causation or a reliable national climate effect."
                    )
                else:
                    lines.append(
                        f"- Pearson correlation with {label}: not calculated; "
                        f"only {n} matched usable annual observations are available "
                        "or the values have insufficient variation (at least 3 "
                        "matched observations with variation are required)."
                    )

            if not joined.empty:
                lines.append(
                    f"- Matched year range: {int(joined['year'].min())}–"
                    f"{int(joined['year'].max())}; {len(joined)} matched annual records."
                )
            else:
                lines.append(
                    "- No matching annual production and climate records were found; "
                    "a correlation cannot be calculated."
                )
        except (OSError, KeyError, ValueError, pd.errors.ParserError) as exc:
            lines.append(
                "- Correlation unavailable because the source files could not be "
                f"joined safely ({type(exc).__name__}). No correlation was invented."
            )

        averages = climate.get("annual_averages", [])
        for item in averages:
            loc = item.get("location", "Unknown location")
            details = []
            for key, label, unit in (
                ("mean_temperature_c", "mean temperature", "°C"),
                ("total_precipitation", "mean annual precipitation", "mm"),
            ):
                if item.get(key) is not None:
                    details.append(f"{label}: {float(item[key]):,.2f} {unit}")
            if details:
                lines.append(f"- Reported climate summary for {loc}: " + "; ".join(details) + ".")

        lines.append(
            "- Limitation: Agadir is one location and is not representative of every "
            "wheat-growing region. Correlation does not establish causation."
        )
    elif "climate" in evidence:
        lines.extend([
            "",
            "## 🌦️ Climate analysis",
            "No usable matching climate records were returned; climate correlations cannot be calculated.",
        ])

    validation = evidence.get("validation", {})
    if validation:
        lines.extend([
            "",
            "## Evidence and limitations",
            f"- Evidence validation: {'approved' if validation.get('approved') else 'needs review'}.",
        ])
        for issue in validation.get("issues", []):
            lines.append(f"- Validation note: {issue}")

    lines.extend([
        "- Historical production is variable; year-to-year changes alone do not identify their causes.",
        "- Forecast performance should be judged on held-out data and compared against simple baselines.",
        "- Missing observations, limited climate-location coverage, and the small evaluation sample may limit conclusions.",
    ])

    lines.extend([
        "",
        "## 💡 Practical recommendations",
        "1. **Plan for rainfall variability:** use local seasonal rainfall and soil-moisture monitoring to inform sowing and irrigation decisions; do not use Agadir data alone for every region.",
        "2. **Reduce production risk:** evaluate locally suitable drought-tolerant varieties, diversified planting dates, and soil-moisture conservation with agricultural extension services.",
        "3. **Use forecasts cautiously:** combine the statistical forecast with current seasonal forecasts, regional field observations, and updated official production data; compare predictions against observed harvests each year.",
    ])

    return "\n".join(lines)
