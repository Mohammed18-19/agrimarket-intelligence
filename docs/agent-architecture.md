# Agricultural AI Agent Architecture

## Request flow

```text
Next.js AI Advisor
   | POST /api/ai/ask (question, selected crop/location, conversation_id)
   v
Flask API
   v
LangGraph router
   |-- GROQ_API_KEY + langchain-groq installed --> LLM agent
   |                                                |
   |                                                v
   |                                      LangChain tool calls
   |                                      /       |       \\
   |                               production   climate   forecast
   |                                      \\       |       /
   |                                                v
   |                                      Tool results -> LLM
   |                                                |
   |                                      bounded tool loop
   |                                                v
   |                                      evidence validation
   |
   |-- no provider --> keyword router -> relevant specialist tools
                                                |
                                                v
                                      evidence validation
                                                |
                                                v
                                  existing evidence-based summary
                                                |
                                                v
                                     Next.js analysis + evidence
```

## Available tools

- `get_crop_production(crop)`: real cleaned FAOSTAT observations, annual changes, and period coverage.
- `get_climate_observations(location)`: annual NASA POWER summaries for locations represented in the processed dataset.
- `get_crop_forecasts(crop)`: saved experimental forecasts and validation metrics.

The tools read existing project datasets. They do not create new observations, run a new forecast, or provide crop-suitability conclusions unsupported by the available data.

## State and memory

The graph state includes the current question, selected crop/location, message history, tool-round count, specialist evidence, and validation result. A session-scoped `conversation_id` maps to LangGraph's in-memory checkpointer. This supports conversational context during the current backend process, but memory is lost on restart and is not shared across separate worker processes.

## Guardrails

- Tool calls are bounded by `MAX_TOOL_ROUNDS`.
- Tool failures are converted into structured evidence errors where possible.
- The evidence validator flags empty or unusable specialist results.
- The model prompt requires tool use for factual data questions and prohibits invented numbers and unsupported causal claims.
- Without a provider key, deterministic specialist routing and the existing fallback remain available.

## Configure hosted tool calling

```bash
pip install -e ".[llm]"
export GROQ_API_KEY="your-key"
export AGRIMARKET_LLM_MODEL="openai/gpt-oss-120b"
```

Never expose `GROQ_API_KEY` in frontend code or commit it to version control.
