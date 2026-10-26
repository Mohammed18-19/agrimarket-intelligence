# AgriMarket Intelligence API

Flask REST API for Moroccan crop production history and model-generated forecasts.

## Requirements

Install dependencies:

    pip install -e ".[dev]"

## Run the API

    python -m agrimarket.api

Base URL: http://127.0.0.1:5000

## Endpoints

### Health check

GET /api/health

    curl http://127.0.0.1:5000/api/health

Reports whether the production and forecast datasets are available.

### List crops

GET /api/crops

    curl http://127.0.0.1:5000/api/crops

Returns the sorted crop names and their count.

### Production history

GET /api/crops/<crop>/history

    curl http://127.0.0.1:5000/api/crops/Wheat/history

Returns annual production observations sorted by year.

### Production summary

GET /api/crops/<crop>/summary

    curl http://127.0.0.1:5000/api/crops/Wheat/summary

Returns latest production, observation period, unit, and year-over-year changes.

### Production forecast

GET /api/crops/<crop>/forecast

    curl http://127.0.0.1:5000/api/crops/Wheat/forecast

Returns saved forecast records and available model metadata.

**Important:** Forecasts are model estimates, not observed production figures.

### AI Advisor

POST /api/ai/ask

Example request:

```json
{
  "question": "How did wheat production change, and what does the forecast say?",
  "crop": "Wheat",
  "location": "Agadir",
  "conversation_id": "browser-session-id"
}
```

`conversation_id` is optional. The dashboard supplies a session-scoped ID so LangGraph can retain conversation context in the backend's in-memory checkpointer. This memory is lost on backend restart and is not shared between multiple workers.

With `GROQ_API_KEY` and the optional dependencies installed (`pip install -e ".[llm]"`), the LLM selects and calls the production, climate, and forecast tools. Without them, the API uses the deterministic specialist workflow and evidence-based fallback. Responses include `agents_used`, `evidence`, `validation`, `analysis`, and analysis-source metadata.

Never send the provider key from the browser. Configure it only in the backend environment.

## Error responses

Responses with errors contain an error field.

- 200: Request succeeded.
- 404: Crop or forecast not found.
- 422: Inconsistent production units.
- 500: Dataset structure or server-side error.
- 503: Required dataset unavailable.

## Data files

Production data: data/processed/faostat_morocco_production.csv

Forecast data: data/processed/crop_production_forecasts.csv

The API currently listens on 127.0.0.1 for local development.
