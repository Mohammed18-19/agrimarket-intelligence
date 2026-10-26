# AgriMarket Intelligence

**Data-driven agricultural intelligence for Morocco.**

AgriMarket Intelligence is a data analytics platform for exploring Moroccan crop production, historical climate observations, and experimental forecasts through an interactive dashboard and an evidence-based AI Advisor.

## Dashboard Preview

![AgriMarket Intelligence dashboard preview](docs/images/agrimarket-preview.png)

## Key Features

- **Crop production analytics:** Explore cleaned FAOSTAT production data for 92 crops.
- **Interactive dashboard:** Examine historical production, forecasts, and climate indicators.
- **Statistical forecasting:** Compare naive baseline and linear-trend estimates.
- **Climate intelligence:** Explore processed NASA POWER observations for five Moroccan locations.
- **Tool-using AI agent:** A LangGraph loop lets a configured LLM choose among production, climate, and forecast tools, call them, and answer from their returned evidence.
- **Deterministic fallback:** Without a hosted API key, the workflow still retrieves real project datasets and produces an evidence-based analysis.
- **Evidence transparency:** Distinguish observed data from estimates and communicate limitations.
- **REST API:** Serve crop, production, and forecast data through Flask.

## Technology Stack

| Component | Technologies |
|---|---|
| Backend | Python, Flask, REST API |
| Frontend | Next.js, React, TypeScript |
| Data processing | pandas, NumPy |
| Forecasting | Naive baseline, linear trend |
| Agricultural data | FAOSTAT |
| Climate data | NASA POWER |
| AI orchestration | LangGraph stateful graph and bounded tool-calling loop |
| AI tools / model | LangChain tools, optional Groq ChatGroq |
| Conversation state | In-memory LangGraph checkpointer, session conversation ID |
| Testing | pytest |

## Data Sources

### FAOSTAT

Cleaned annual Moroccan crop-production records covering 2015–2024. The processed dataset currently includes 92 crops.

### NASA POWER

Daily climate observations aggregated into annual indicators for five Moroccan locations. The dashboard currently highlights Agadir.

Climate observations from one location should not be treated as representative of all Moroccan agricultural regions. The project does not assume climate and production are causally related.

## Forecasting

The project evaluates naive baseline and linear-trend forecasts using historical validation and chronological holdout evaluation.

Forecasts are experimental estimates, not observed production figures or guarantees of future harvests. Validation errors describe historical performance but cannot guarantee future accuracy.

## AI Advisor

The advisor is designed to answer agricultural questions using available project evidence. Its intended workflow is to interpret a question, retrieve relevant evidence, generate a grounded answer, and explain uncertainty or missing information.

The local evidence-based fallback can operate without a hosted model API key. Groq integration requires a valid `GROQ_API_KEY`.

Question-specific evidence retrieval and unsupported-question handling still need improvement. The current production data does not provide province-level wheat yield forecasts.

## Architecture

```text
FAOSTAT ───────┐
               ├──> Data processing ──> Processed datasets
NASA POWER ────┘                           │
                                           ├──> Forecasting and evaluation
                                           ├──> Flask REST API
                                           └──> AI evidence retrieval
                                                      │
                                                      v
                                              Next.js dashboard
```

## Getting Started

### Requirements

- Python and project dependencies
- Node.js and npm

### 1. Clone the repository

```bash
git clone https://github.com/Mohammed18-19/agrimarket-intelligence.git
cd agrimarket-intelligence
```

### 2. Set up Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
```

If the repository defines a different installation procedure, follow its dependency files.

### 3. Start the backend

From the project root:

```bash
source .venv/bin/activate
python -m flask --app src.agrimarket.api run --host 127.0.0.1 --port 5000
```

### 4. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### 5. Optional tool-calling AI provider

Install the optional LLM dependencies:

```bash
pip install -e ".[llm]"
```

Export the variables in the backend shell (the `.env.example` file is a template; the application does not automatically load `.env` files):

```bash
export GROQ_API_KEY="your-key"
export AGRIMARKET_LLM_MODEL="openai/gpt-oss-120b"
```

The model dynamically selects among three LangChain tools:
- `get_crop_production` — observed FAOSTAT crop production and annual changes.
- `get_climate_observations` — NASA POWER annual climate observations.
- `get_crop_forecasts` — existing experimental forecasts and evaluation records.

LangGraph bounds the tool loop and validates returned evidence before producing the API response. Never commit API keys or other secrets.

When no key or provider package is available, the deterministic specialist workflow remains usable. The dashboard sends a session conversation ID so the graph can retain conversation context in memory. This memory is process-local and is lost when the backend restarts; it is not a durable database or cross-worker memory store.

## Testing

From the project root, with the Python environment activated:

```bash
pytest
```

To check the frontend production build:

```bash
cd frontend
npm run build
```

## Current Limitations

- Production data is national-level, not province-level yield data.
- Forecast accuracy varies by crop and historical pattern.
- Climate coverage is limited to locations in the processed dataset.
- Tool selection and natural-language synthesis require the optional Groq provider configuration; without it, question routing uses transparent keyword rules.
- Conversation memory is in-process only and is not shared between multiple backend workers.
- Crop suitability, market-price analysis, and regional risk assessment are not implemented because the current datasets do not support those claims.

## Roadmap

- [x] Add LangChain tools and a bounded LangGraph tool-calling loop.
- [x] Validate tool evidence and preserve a no-key deterministic fallback.
- [x] Pass a session conversation ID for in-memory conversation context.
- [ ] Add automated evaluation for AI answer grounding, tool selection, and unsupported questions.
- [ ] Strengthen chronological forecast evaluation.
- [ ] Expand regional agricultural data using reliable sources.
- [ ] Explore crop suitability and agricultural risk analysis.
- [ ] Add market-price analysis when suitable datasets are available.
- [ ] Improve deployment and end-to-end testing.

## Project Goals

This portfolio project demonstrates practical work in Python backend development, data processing, time-series forecasting, interactive dashboards, and evidence-grounded AI applications.

## Responsible Use

This project is intended for analytical exploration and educational purposes. Forecasts should not replace official agricultural statistics, local agronomic expertise, or field-level assessment.

## Author

**Mohammed Ain Tomar**

- GitHub: [Mohammed18-19](https://github.com/Mohammed18-19)
- LinkedIn: [Mohammed Ain Tomar](https://linkedin.com/in/mohammed-aintomar-a94a37262)

---

*Exploring how agricultural data and evidence-based AI can support better-informed decisions in Morocco.*