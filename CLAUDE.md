# CLAUDE.md — Local Agent

## Project overview
AI browser automation tool. Runs Chromium in Docker with noVNC. Uses LLM (Anthropic Computer Use or Ollama vision models) to screenshot -> analyze -> act in a loop.

## Build & Run
```bash
cd docker && HOST_API_PORT=8001 docker compose up --build
# Health check:
curl http://localhost:8001/health
# Submit task:
curl -X POST http://localhost:8001/task -H "Content-Type: application/json" \
  -d '{"instruction":"...", "url":"https://..."}'
```

## Architecture
- `src/local_agent/agent/` — loop.py (core loop), actions.py (Playwright executor), prompts.py
- `src/local_agent/browser/` — manager.py (lifecycle, headless=False), screenshot.py (capture/resize/scale), session.py (cookie persistence via storage_state)
- `src/local_agent/llm/` — base.py (abstract LLMProvider, AgentAction, AgentResponse), anthropic.py (Claude Computer Use), ollama.py (single-turn vision), factory.py
- `src/local_agent/api/` — FastAPI app with lifespan, routes, models, websocket broadcasting
- `src/local_agent/config.py` — Pydantic Settings, all config via env vars
- `cli/client.py` — Typer CLI
- `docker/` — Dockerfile (Playwright base + venv), docker-compose, supervisord (5 processes)

## Key patterns
- **Anthropic provider**: `computer_20250124` tool, `betas=["computer-use-2025-01-24"]` for Sonnet. Schema-less tool — Claude knows all actions natively.
- **Ollama provider**: Single-turn approach (NOT multi-turn). Each call sends system prompt + task + action history summary + latest screenshot. Small models can't handle long conversation histories.
- Screenshots resized to max 1568px before sending to API, coordinates scaled back proportionally on execution.
- Errors sent as `tool_result` with `is_error: true` — Claude self-corrects.
- Loop detection: 4 identical consecutive actions triggers warning.
- WebSocket at `/ws` broadcasts live task progress.
- Browser session persisted via Playwright `storage_state` (cookies + localStorage).

## Docker gotchas
- Playwright base image needs `python3.12-venv` apt package to create venvs (system Python is externally-managed).
- supervisord Xvfb resolution string: NO spaces around `x` (e.g. `1280x800x24`).
- noVNC web files at `/usr/share/novnc` in Ubuntu noble.
- `host.docker.internal` to reach Ollama on the host machine.
- Port 8000 may be occupied; use `HOST_API_PORT` env var in docker-compose.

## LLM provider comparison (tested)
| Model | Simple nav (Wikipedia) | Complex UI (Gmail) | Speed/step |
|-------|----------------------|-------------------|------------|
| Claude Sonnet 4.5 | 6 steps OK | 20 steps OK | ~2-3s |
| gemma3:4b | 4 steps OK | Failed | ~3s |
| qwen2.5vl:7b | 5 steps OK | Failed | ~12s |
| llama3.2-vision 11B | Failed (bad coords) | Not tested | ~30s |

## Ollama prompt engineering lessons
- NEVER use `[x, y]` as placeholder coordinates — small models copy them literally. Always use real numbers like `[300, 500]`.
- Small models return `{}` (empty JSON) often. Code must handle this as retry, not task completion.
- After 4+ actions, explicitly ask "Has the task been completed?" in the prompt to trigger `done`.
- `num_predict: 100` limits output length, preventing models from writing paragraphs instead of JSON.
- Single-turn is better than multi-turn for small models: send task + history summary + latest screenshot each time.

## Environment
- `LLM_PROVIDER`: `anthropic` or `ollama`
- `OLLAMA_MODEL`: vision model name (e.g. `gemma3:4b`, `qwen2.5vl:7b`)
- Needs `.env` file — copy from `.env.example`
- All config via Pydantic Settings (auto-reads .env)

## Tech stack
Python 3.12, FastAPI, Playwright, anthropic SDK, httpx, Pillow, Typer, Pydantic Settings, websockets
