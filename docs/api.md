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
