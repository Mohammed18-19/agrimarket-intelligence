# AgriMarket Intelligence — Agentic Workspace Upgrade

This is a **targeted patch**, not a complete replacement of the repository. It contains only modified/new files, so extract it into the root of your existing `agrimarket-intelligence` repository.

## What changes

- Moves the agent workspace to the first workspace section after navigation.
- Uses a left-side navigation rail on desktop and sticky horizontal navigation on smaller screens.
- Adds a Flask `POST /api/ai/stream` Server-Sent Events endpoint.
- Streams actual LangGraph node updates and tool-call/tool-result events; the UI displays events emitted by the backend instead of simulated agent progress.
- Adds a Next.js route at `/api/ai/stream` that proxies the stream to Flask.
- Preserves the existing `/api/ai/ask` endpoint and existing analytics sections.

## Apply on macOS

From the root of your existing project:

```bash
cd ~/Desktop/Development/agrimarket-intelligence

# Back up files that this patch changes
mkdir -p .backup-agentic-upgrade
cp frontend/app/page.tsx .backup-agentic-upgrade/page.tsx
cp frontend/app/globals.css .backup-agentic-upgrade/globals.css
cp src/agrimarket/api.py .backup-agentic-upgrade/api.py
cp src/agrimarket/ai/workflow.py .backup-agentic-upgrade/workflow.py

# Put the downloaded ZIP on Desktop, then apply it:
unzip -o ~/Desktop/agrimarket-agentic-upgrade.zip -d .

# Check Python syntax
python -m compileall src/agrimarket

# Run backend tests using the project's activated venv
pytest -q

# In one terminal, start the Flask API from the project root
python -m agrimarket.api
```

The last command depends on how the existing project starts Flask. If it does not launch the server, use your existing Flask startup command; do not change the project's run configuration just for this patch.

In a second terminal:

```bash
cd ~/Desktop/Development/agrimarket-intelligence/frontend
npm run build
npm run dev
```

Open http://localhost:3000 and submit an investigation in the Agent Workspace.

## Backend URL

The Next.js proxy defaults to `http://127.0.0.1:5000`. If your Flask API uses a different URL, set `AGRIMARKET_API_URL` in the frontend environment, for example:

```bash
AGRIMARKET_API_URL=http://127.0.0.1:5000
```

Restart the Next.js server after changing environment variables.

## Honest limitations

- Agent activity is streamed from real LangGraph graph updates. In the no-LLM-key fallback, the deterministic specialist path still runs; it is not an autonomous LLM planner.
- The existing project only exposes production, climate, and forecast data tools. This patch does not invent a crop-suitability model, external live-data integration, durable database-backed memory, or human approval actions.
- The existing `InMemorySaver` is process-local and is not durable across backend restarts.
- Run the test suite and production build on your machine; this patch was syntax-checked here, but its Python/Next dependencies and full project data were not included in the uploaded ZIP, so a full end-to-end build could not be verified in this environment.
