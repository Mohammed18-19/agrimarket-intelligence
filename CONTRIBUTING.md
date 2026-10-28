# Contributing to AgriMarket Intelligence

Thank you for your interest in contributing to AgriMarket Intelligence.

This project explores agricultural production, climate indicators, forecasting,
and evidence-grounded AI investigations for Morocco. Contributions that improve
correctness, reproducibility, documentation, accessibility, or evaluation are
welcome.

## Before you start

- Python 3.12 or newer
- Node.js and npm
- Git

## Set up the project

Clone the repository and enter its directory:

```bash
git clone https://github.com/Mohammed18-19/agrimarket-intelligence.git
cd agrimarket-intelligence
```

Create and activate a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the backend and development dependencies:

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

To enable the optional Groq integration, install the LLM extra:

```bash
pip install -e ".[dev,llm]"
```

A valid Groq API key is required for features that use the live Groq service.
Never commit API keys, passwords, or other secrets.

## Run the application

Start the API from the repository root:

```bash
PYTHONPATH=src python -m agrimarket.api
```

In another terminal, start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Check the README for the current API and frontend configuration.

## Run checks before submitting

From the repository root, run the Python tests:

```bash
PYTHONPATH=src pytest -q
```

Check the frontend types and production build:

```bash
cd frontend
npx tsc --noEmit
npm run build
```

Include the results of the checks you ran in your pull request. If a check
fails for an unrelated reason, explain the failure clearly.

## Contribution workflow

1. Open an issue or discussion before making a large or breaking change.
2. Create a focused branch from the latest `main` branch.
3. Make a small, clearly scoped change.
4. Add or update tests when changing behavior.
5. Update documentation when commands, APIs, configuration, or behavior change.
6. Run the relevant checks.
7. Open a pull request explaining the problem, the solution, and how it was tested.

Example branch names:

- `fix/forecast-validation`
- `docs/setup-instructions`
- `feat/investigation-evidence`

## Data and forecasting standards

- Preserve the provenance of external datasets.
- Do not present correlations as proof of causation.
- Describe forecast limitations and evaluation methodology accurately.
- Do not introduce fabricated data, results, or performance claims.
- Keep changes reproducible and document important assumptions.

## AI investigation standards

- Prefer evidence-grounded answers over unsupported claims.
- Make uncertainty and missing evidence explicit.
- Do not expose secrets or personal information in logs, reports, or tests.
- Add tests for relevant failure cases when modifying investigation behavior.

## Pull request expectations

A good pull request should:

- Address one main problem.
- Explain the motivation and the change.
- Include tests or a clear explanation of why tests were not added.
- Update relevant documentation.
- Avoid unrelated formatting changes or generated files.

By contributing, you agree to follow the project's existing license, if one is
added, and applicable third-party dataset and dependency terms.
