# Local Agent — AI Browser Automation

AI-gestuurde browser automation tool die draait in Docker. De agent maakt screenshots van een Chromium browser, stuurt ze naar een LLM (Claude API of lokaal via Ollama), en voert de teruggegeven acties uit (klikken, typen, scrollen). Je kijkt live mee via noVNC.

## Architectuur

```
Jouw Browser                       Docker Container
+------------------+               +------------------------------------------+
|  noVNC Client    |--- :6080 ---->|  Xvfb + fluxbox + x11vnc + noVNC        |
|  (meekijken &    |               |           |                              |
|   handmatig      |               |     Chromium (Playwright, headless=off)  |
|   inloggen)      |               |           ^                              |
+------------------+               |           | Playwright API               |
                                   |           |                              |
+------------------+               |     FastAPI ──> Agent Loop               |
|  CLI / curl      |--- :8000 ---->|          │ screenshot                    |
|  (taken geven)   |               |          │ send to LLM (Claude/Ollama)   |
+------------------+               |          │ get action (click/type/scroll)|
                                   |          │ execute via Playwright        |
                                   |          └─ repeat until done            |
                                   +------------------------------------------+
```

## Quick Start

### 1. Setup

```bash
cp .env.example .env
# Kies je provider in .env:
#   LLM_PROVIDER=anthropic  (+ vul ANTHROPIC_API_KEY in)
#   LLM_PROVIDER=ollama     (+ zorg dat Ollama lokaal draait)
```

### 2. Start

```bash
cd docker
docker compose up --build

# Of met custom API poort (als 8000 bezet is):
HOST_API_PORT=8001 docker compose up --build
```

### 3. Login handmatig

Open [http://localhost:6080](http://localhost:6080) (noVNC). Je ziet Chromium. Navigeer naar je doelwebsite en log handmatig in.

### 4. Sessie opslaan

```bash
curl -X POST http://localhost:8000/session/save
```

### 5. Geef de agent een taak

```bash
curl -X POST http://localhost:8000/task \
  -H "Content-Type: application/json" \
  -d '{"instruction": "Zoek op Wikipedia naar Amsterdam", "url": "https://www.wikipedia.org"}'
```

Kijk mee via noVNC terwijl de agent werkt.

## LLM Providers

### Anthropic (Claude Computer Use)

De primaire provider. Gebruikt Claude's native `computer_20250124` tool voor precieze browser automation. Snel (~2-3s per stap), nauwkeurig, kan complexe multi-stap taken aan (Gmail, formulieren).

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-5-20250929
```

### Ollama (lokale modellen)

Gratis en lokaal, geen API key nodig. Gebruikt een vision model via Ollama's HTTP API. De agent stuurt screenshots en ontvangt JSON-acties terug.

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5vl:7b
```

**Geteste modellen:**

| Model | Params | Wikipedia zoeken | Gmail e-mail | Snelheid/stap |
|-------|--------|-----------------|--------------|---------------|
| `claude-sonnet-4-5` | — | 6 stappen | 20 stappen | ~2-3s |
| `gemma3:4b` | 4B | 4 stappen | — | ~3s |
| `qwen2.5vl:7b` | 7B | 5 stappen | — | ~12s |
| `llama3.2-vision` | 11B | Faalde | — | ~30s |

> **Tip:** `gemma3:4b` is het snelst voor simpele taken. `qwen2.5vl:7b` heeft betere vision maar is trager. Geen van de lokale modellen kan complexe UI's (Gmail compose) betrouwbaar bedienen — gebruik daarvoor Anthropic.

**Ollama installeren:**
```bash
# macOS
brew install ollama
ollama serve

# Pull een vision model
ollama pull gemma3:4b        # snel, goed voor simpele taken
ollama pull qwen2.5vl:7b     # betere vision, trager
```

## API Endpoints

| Method | Path | Beschrijving |
|--------|------|-------------|
| GET | `/health` | Health check (`browser_ready: true/false`) |
| GET | `/screenshot` | Huidige browser screenshot (PNG) |
| POST | `/navigate` | Navigeer naar URL (`{"url": "..."}`) |
| POST | `/session/save` | Sla browser sessie op (cookies/localStorage) |
| POST | `/task` | Start een agent taak (`{"instruction": "...", "url": "..."}`) |
| GET | `/task/{id}` | Taak status opvragen |
| POST | `/task/{id}/cancel` | Taak annuleren |
| WS | `/ws` | Live progress updates via WebSocket |

## Configuratie (.env)

| Variable | Default | Beschrijving |
|----------|---------|-------------|
| `LLM_PROVIDER` | `anthropic` | `anthropic` of `ollama` |
| `ANTHROPIC_API_KEY` | — | Anthropic API key (bij provider=anthropic) |
| `LLM_MODEL` | `claude-sonnet-4-5-20250929` | Claude model |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Ollama URL |
| `OLLAMA_MODEL` | `llama3.2-vision` | Ollama vision model |
| `BROWSER_WIDTH` | `1280` | Browser viewport breedte |
| `BROWSER_HEIGHT` | `800` | Browser viewport hoogte |
| `AGENT_MAX_STEPS` | `50` | Max acties per taak |
| `AGENT_STEP_DELAY` | `0.5` | Seconden tussen acties |
| `HOST_API_PORT` | `8000` | Host poort voor API (docker-compose) |

## Hoe het werkt

1. **Screenshot**: Playwright maakt screenshot, resize naar max 1568px
2. **Naar LLM**: Screenshot + instructie naar Claude (Computer Use API) of Ollama (vision chat)
3. **Actie terug**: LLM retourneert gestructureerde actie (klik op x,y / type tekst / druk toets / scroll)
4. **Uitvoeren**: Playwright voert de actie uit op de echte browser
5. **Herhalen**: Nieuwe screenshot als `tool_result` terugsturen, tot de LLM "done" zegt

**Zelfcorrectie**: als een actie faalt, wordt de error met `is_error: true` teruggestuurd — Claude probeert een andere aanpak. Loop detectie voorkomt vastlopen op herhaalde acties.

## Projectstructuur

```
local_agent/
├── .env.example                 # Configuratie template
├── pyproject.toml               # Python project definitie
├── docker/
│   ├── Dockerfile               # Playwright + Xvfb + noVNC + Python venv
│   ├── docker-compose.yml       # Single service, 3 poorten
│   ├── supervisord.conf         # 5 processen: xvfb, fluxbox, x11vnc, novnc, api
│   └── entrypoint.sh
├── src/local_agent/
│   ├── config.py                # Pydantic settings (env vars)
│   ├── agent/
│   │   ├── loop.py              # Core: screenshot -> LLM -> actie -> herhaal
│   │   ├── actions.py           # Vertaalt acties naar Playwright calls
│   │   └── prompts.py           # System prompts
│   ├── browser/
│   │   ├── manager.py           # Browser lifecycle, headless=False
│   │   ├── screenshot.py        # Capture, resize, base64
│   │   └── session.py           # Cookie/localStorage persistence
│   ├── llm/
│   │   ├── base.py              # Abstract LLMProvider interface
│   │   ├── anthropic.py         # Claude Computer Use provider
│   │   ├── ollama.py            # Ollama vision provider (single-turn)
│   │   └── factory.py           # Provider selectie
│   ├── api/
│   │   ├── app.py               # FastAPI met lifespan
│   │   ├── routes.py            # Alle endpoints
│   │   ├── models.py            # Pydantic schemas
│   │   └── websocket.py         # Live progress broadcasting
│   └── utils/
│       ├── logging.py
│       └── errors.py
├── cli/
│   └── client.py                # Typer CLI client
└── data/                        # Docker volumes
    ├── sessions/                # Browser cookies
    ├── screenshots/             # Debug archief
    └── logs/                    # Applicatie logs
```

## Poorten

| Poort | Service |
|-------|---------|
| 8000 | FastAPI (taken, screenshots, health) |
| 5900 | VNC (voor VNC clients zoals TigerVNC) |
| 6080 | noVNC (browser-based VNC viewer) |

## Roadmap

### 1. React + Tailwind Frontend
Volledig control panel als React app met Tailwind CSS:
- **Dashboard**: taken starten, live status, screenshots bekijken, noVNC embedded
- **Recording Studio**: opnames beheren, YAML flows bewerken, variabelen instellen, replay starten
- **Instellingen**: LLM provider wisselen, model kiezen, configuratie aanpassen

### 2. Smart Recording & Replay
"Record & replay" systeem voor browser automation flows:
- **Opname**: gebruiker browst handmatig via noVNC, het systeem neemt acties op via Playwright event listeners (clicks, keystrokes, navigatie)
- **Opslag als YAML**: elke opname wordt een YAML bestand met stappen, beschrijvingen, en optionele variabelen
- **Slim replay**: de YAML wordt niet dom afgespeeld op exacte coördinaten, maar als instructieset aan de AI gegeven. De AI kijkt naar de huidige screenshot en voert de stappen uit op basis van beschrijvingen — robuust tegen UI-wijzigingen
- **Variabelen**: `{{ projectnaam }}`, `{{ datum }}` etc. zodat dezelfde flow herbruikbaar is met andere data

```yaml
name: "Weekplanning maken in Bouw7"
url: "https://bouw7.nl/planning"
variables:
  projectnaam: "Project Dijkstra"
  week: "10"
steps:
  - action: left_click
    description: "Klik op Nieuwe Planning knop"
  - action: type
    text: "{{ projectnaam }}"
    description: "Vul projectnaam in"
  - action: key
    text: "Tab"
  - action: type
    text: "Week {{ week }}"
    description: "Vul weeknummer in"
  - action: left_click
    description: "Klik op Opslaan"
```

### 3. Hybride LLM Modus
Ollama voor simpele taken, automatisch fallback naar Anthropic voor complexe flows. Als het lokale model 3x faalt, schakelt de agent automatisch over naar Claude.

### Backlog
- [ ] Parallel task execution
- [ ] Task queue met history
- [ ] Browser tab management
- [ ] Scheduling (cron-achtig taken herhalen)
