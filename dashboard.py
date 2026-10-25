"""AgriMarket Intelligence interactive dashboard."""

import os

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st


API_URL = os.getenv("AGRIMARKET_API_URL", "http://127.0.0.1:5000")

st.set_page_config(
    page_title="AgriMarket Intelligence",
    page_icon="🌱",
    layout="wide",
)

st.title("🌱 AgriMarket Intelligence")
st.caption(
    "Morocco · Crop production · Climate observations · Forecasts · AI analysis"
)


@st.cache_data(ttl=60)
def get_json(path: str):
    response = requests.get(f"{API_URL}{path}", timeout=15)
    response.raise_for_status()
    return response.json()


def show_error(message):
    st.error(message)


try:
    health = get_json("/api/health")
    crops_payload = get_json("/api/crops")
    crops = crops_payload.get("crops", [])
except Exception as exc:
    st.error(f"Cannot reach the Flask API at {API_URL}: {exc}")
    st.info(
        "Start the API in another terminal with:\n\n"
        "`python -m agrimarket.api`"
    )
    st.stop()

if not crops:
    st.warning("The API returned no crops.")
    st.stop()

with st.sidebar:
    st.header("Explore")
    crop = st.selectbox(
        "Crop",
        crops,
        index=crops.index("Wheat") if "Wheat" in crops else 0,
    )
    st.caption(f"API status: {health.get('status', 'available')}")
    st.caption(f"{len(crops)} crops available")
    if st.button("Refresh data"):
        get_json.clear()
        st.rerun()

try:
    encoded_crop = requests.utils.quote(crop, safe="")
    summary = get_json(f"/api/crops/{encoded_crop}/summary")
    history_payload = get_json(f"/api/crops/{encoded_crop}/history")
    history = pd.DataFrame(history_payload.get("history", []))

    try:
        forecast_payload = get_json(f"/api/crops/{encoded_crop}/forecast")
        forecasts = forecast_payload.get("forecasts", [])
    except Exception:
        forecasts = []

except Exception as exc:
    show_error(f"Could not load analytics for {crop}: {exc}")
    st.stop()

st.subheader(f"{crop} production")

# Support the current API summary schema.
year_change = summary.get("year_over_year", {})
latest_value = summary.get("latest_production")
latest_year = summary.get("latest_year", "—")
unit = summary.get("unit", "t")
change_pct = year_change.get("change_percentage")

col1, col2, col3, col4 = st.columns(4)
col1.metric(
    "Latest production",
    f"{latest_value:,.0f} {unit}" if isinstance(latest_value, (int, float)) else "—",
)
col2.metric("Latest year", str(latest_year))
col3.metric(
    "Year-on-year change",
    f"{change_pct:+.1f}%" if isinstance(change_pct, (int, float)) else "N/A",
)
col4.metric("Historical observations", str(summary.get("observations", len(history))))

left, right = st.columns([1.6, 1])

with left:
    st.subheader("Historical production")
    if not history.empty and {"Year", "Value"}.issubset(history.columns):
        history["Year"] = pd.to_numeric(history["Year"], errors="coerce")
        history["Value"] = pd.to_numeric(history["Value"], errors="coerce")
        history = history.dropna(subset=["Year", "Value"]).sort_values("Year")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=history["Year"],
            y=history["Value"],
            mode="lines+markers",
            name="Observed production",
            line={"width": 3},
        ))
        fig.update_layout(
            xaxis_title="Year",
            yaxis_title=f"Production ({unit})",
            template="plotly_white",
            margin={"l": 10, "r": 10, "t": 20, "b": 10},
            height=360,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No historical observations are available for this crop.")

with right:
    st.subheader("Available forecasts")
    if forecasts:
        forecast_df = pd.DataFrame(forecasts)
        st.dataframe(forecast_df, use_container_width=True, hide_index=True)
        st.caption(
            "Forecasts are model outputs and are not guaranteed future outcomes."
        )
    else:
        st.info("No forecast records are available for this crop.")

st.divider()
st.subheader("Climate observations")

try:
    climate_payload = get_json("/api/climate")
    climate_records = pd.DataFrame(climate_payload.get("records", []))
    if not climate_records.empty:
        if "location" in climate_records.columns:
            locations = sorted(climate_records["location"].dropna().unique().tolist())
            selected_location = st.selectbox("Climate location", locations)
            climate_records = climate_records[
                climate_records["location"] == selected_location
            ]
        st.dataframe(climate_records, use_container_width=True, hide_index=True)
    else:
        st.info("The climate endpoint returned no records.")
except Exception as exc:
    st.warning(f"Climate data is currently unavailable: {exc}")

st.divider()
st.subheader("AI Agricultural Analyst")
st.write(
    "Ask a question about production, climate, or forecasts. "
    "The analysis is grounded in retrieved project evidence."
)

with st.form("ai_question_form"):
    question = st.text_area(
        "Your question",
        value=f"Analyze {crop} production trends and available forecasts",
        placeholder="For example: How has wheat production changed, and what forecasts are available?",
        height=100,
    )
    submitted = st.form_submit_button("Analyze", type="primary")

if submitted:
    if not question.strip():
        st.warning("Enter a question first.")
    else:
        with st.spinner("Retrieving evidence and analyzing..."):
            try:
                response = requests.post(
                    f"{API_URL}/api/ai/ask",
                    json={"question": question, "crop": crop},
                    timeout=120,
                )
                payload = response.json()
                response.raise_for_status()

                st.markdown("#### Analysis")
                st.write(payload.get("analysis", "No analysis was returned."))

                validation = payload.get("validation", {})
                if validation.get("approved"):
                    st.success("Evidence validation passed.")
                else:
                    st.warning("Evidence needs review.")
                    if validation.get("issues"):
                        st.write(validation["issues"])

                with st.expander("Inspect evidence records"):
                    st.json(payload.get("evidence", {}))

                with st.expander("Workflow details"):
                    st.write("Agents used:", payload.get("agents_used", []))
                    st.write(payload.get("note", ""))
            except Exception as exc:
                st.error(f"AI analysis failed: {exc}")

st.divider()
st.caption(
    "Data sources: FAOSTAT production observations and NASA POWER annual climate "
    "aggregates. Forecasts are estimates; observational relationships do not "
    "establish causation."
)
