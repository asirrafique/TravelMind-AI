# TravelMind AI ✈️

> A production-oriented multi-agent AI travel planner built with **LangGraph, MCP, FastAPI, Neon PostgreSQL, Redis, and Docker**.

TravelMind AI transforms natural-language travel requests into structured travel plans by coordinating specialized AI agents for flights, hotels, weather, itinerary planning, and final response synthesis.

## ✨ What It Does

Give TravelMind a request such as:

> **Plan a 5-day trip from Delhi to Paris for 2 people.**

TravelMind coordinates multiple specialized agents to produce:

* ✈️ Flight information
* 🏨 Hotel information
* 🌦️ Destination weather information
* 🗺️ Day-by-day itinerary
* 💰 Estimated travel budget
* 🧠 Final synthesized recommendations
* 🧵 Persistent LangGraph state

---

# 🏗️ Architecture

```text
                         ┌──────────────────────┐
                         │      Web UI           │
                         │   HTML / CSS / JS     │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │      FastAPI          │
                         │                      │
                         │ POST /api/travel     │
                         │ GET  /api/config     │
                         │ GET  /health         │
                         └──────────┬───────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────┐
                    │          LangGraph            │
                    │     Multi-Agent Workflow      │
                    └──────────────┬────────────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │   Flight Agent    │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │    Hotel Agent    │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │   Weather Agent   │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │ Itinerary Agent   │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │    Final Agent    │
                         └─────────┬─────────┘
                                   │
                                   ▼
                            Final Response


                 External / Tool Layer
        ┌─────────────────────────────────────────┐
        │                                         │
        │  Tavily MCP       AviationStack MCP     │
        │  Remote HTTP      Local stdio           │
        │                                         │
        │              Weather MCP                │
        │              Local stdio                │
        │                                         │
        └─────────────────────────────────────────┘


                  Persistence / Infrastructure

        ┌────────────────────┐
        │   Neon PostgreSQL  │
        │ LangGraph State    │
        │ Persistent         │
        │ Checkpointing      │
        └────────────────────┘

        ┌────────────────────┐
        │       Redis        │
        │       Cache        │
        └────────────────────┘
```

## 🔄 LangGraph Workflow

The current workflow is explicitly orchestrated as:

```text
START
  │
  ▼
Flight Agent
  │
  ▼
Hotel Agent
  │
  ▼
Weather Agent
  │
  ▼
Itinerary Agent
  │
  ▼
Final Agent
  │
  ▼
END
```

---

# 🤖 Multi-Agent System

| Agent                 | Responsibility                                                      |
| --------------------- | ------------------------------------------------------------------- |
| **Flight Agent**      | Retrieves and processes flight information using AviationStack MCP. |
| **Hotel Agent**       | Researches and processes hotel information.                         |
| **Weather Agent**     | Retrieves destination weather through the Weather MCP server.       |
| **Itinerary Agent**   | Builds a structured day-by-day travel itinerary.                    |
| **Final Agent**       | Synthesizes all agent outputs into the final travel response.       |
| **Destination Agent** | Provides destination-related functionality within the project.      |

---

# 🔌 Model Context Protocol (MCP)

TravelMind uses **MCP** to separate tool access from agent logic.

## Remote MCP

### Tavily MCP

Tavily MCP is accessed through streamable HTTP and provides web research capabilities.

## Local MCP

TravelMind also runs two local MCP servers through stdio:

### AviationStack MCP

The AviationStack MCP server is launched using:

```text
uvx --with mcp<2 aviationstack-mcp
```

The `mcp<2` constraint is used for compatibility with the current AviationStack MCP package.

### Weather MCP

TravelMind includes its own local Weather MCP server built using `FastMCP`.

The Weather MCP server communicates with OpenWeather.

---

# 🧠 AI Stack

TravelMind combines:

* **LangGraph** — multi-agent orchestration
* **LangChain** — LLM and tool integration
* **Groq** — LLM inference
* **MCP** — external tool integration
* **LangChain MCP Adapters** — MCP client integration

The graph uses a shared travel state that moves through the specialized agents.

---

# 🗄️ Neon PostgreSQL

TravelMind uses **Neon PostgreSQL** as its managed PostgreSQL database.

Neon is used for:

* LangGraph checkpoint persistence
* Thread-based state
* Durable workflow state

The application passes a `thread_id` to LangGraph so each planning session can maintain associated state.

```text
Travel Request
      │
      ▼
  LangGraph
      │
      ▼
PostgresSaver
      │
      ▼
Neon PostgreSQL
```

The database is external to the Docker environment.

Docker does **not** run a PostgreSQL container.

---

# ⚡ Redis Cache

Redis provides an optional caching layer.

Docker Compose runs Redis as a dedicated service:

```text
TravelMind App
      │
      ▼
Redis
      │
      ▼
Cache
```

Redis is configured through:

```env
REDIS_URL=redis://redis:6379/0
CACHE_ENABLED=true
```

The application is designed to gracefully fall back if caching is unavailable.

---

# 🐳 Docker Architecture

The Docker Compose environment contains two services:

```text
┌─────────────────────────────────────────┐
│              Docker Compose             │
│                                         │
│   ┌─────────────────┐                   │
│   │  TravelMind App │                   │
│   │     FastAPI     │                   │
│   └────────┬────────┘                   │
│            │                            │
│            ▼                            │
│   ┌─────────────────┐                   │
│   │      Redis      │                   │
│   │      Cache      │                   │
│   └─────────────────┘                   │
│                                         │
└─────────────────────────────────────────┘
              │
              │ PostgreSQL
              ▼
     ┌─────────────────────┐
     │   Neon PostgreSQL   │
     │ LangGraph Checkpoint│
     └─────────────────────┘
```

This keeps the application container lightweight while using Neon as the managed PostgreSQL backend.

---

# 🛠️ Technology Stack

## Backend

* Python 3.11+
* FastAPI
* Uvicorn
* Pydantic
* Jinja2

## Agentic AI

* LangGraph
* LangChain
* LangChain Groq
* Groq
* MCP
* LangChain MCP Adapters

## External APIs / Tools

* Tavily
* AviationStack
* OpenWeather

## Database / Cache

* Neon PostgreSQL
* PostgreSQL
* Redis
* psycopg
* psycopg-pool

## Infrastructure

* Docker
* Docker Compose
* uv

## Frontend

* HTML
* CSS
* JavaScript

---

# 📁 Project Structure

```text
TravelMind-AI/
│
├── app.py
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── uv.lock
├── .env.example
├── .dockerignore
├── .gitignore
│
├── frontend/
│   ├── templates/
│   │   └── index.html
│   │
│   └── static/
│       ├── css/
│       │   └── styles.css
│       │
│       └── js/
│           ├── app.js
│           └── markdown.js
│
├── src/
│   │
│   ├── agents/
│   │   ├── destination.py
│   │   ├── final_agent.py
│   │   ├── flight_agent.py
│   │   ├── hotel_agent.py
│   │   ├── itinerary_agent.py
│   │   ├── prompts.py
│   │   └── weather_agent.py
│   │
│   ├── api/
│   │   ├── sessions.py
│   │   └── validation.py
│   │
│   ├── clients/
│   │   ├── cache.py
│   │   ├── checkpointer.py
│   │   └── llm.py
│   │
│   ├── config/
│   │   ├── session.py
│   │   └── settings.py
│   │
│   ├── graph/
│   │   ├── graph.py
│   │   ├── runner.py
│   │   └── state.py
│   │
│   ├── mcp_servers/
│   │   ├── config.py
│   │   └── weather_server.py
│   │
│   └── utils/
│
└── scripts/
    └── build-frontend.sh
```

---

# 🔐 Environment Configuration

Create a `.env` file based on `.env.example`.

```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b

TAVILY_API_KEY=your_tavily_api_key_here
AVIATIONSTACK_API_KEY=your_aviationstack_api_key_here
OPENWEATHER_API_KEY=your_openweather_api_key_here

DATABASE_URL=your_neon_postgresql_connection_string

REDIS_URL=redis://redis:6379/0
CACHE_ENABLED=true

HOST=0.0.0.0
PORT=8000
RELOAD=false
```

### Security

Never commit:

```text
.env
```

Never expose:

* Groq API keys
* Tavily API keys
* AviationStack API keys
* OpenWeather API keys
* Neon database credentials

Use `.env.example` for placeholder values only.

---

# 🚀 Running with Docker

## 1. Clone the repository

```bash
git clone https://github.com/asirrafique/TravelMind-AI.git
cd TravelMind-AI
```

## 2. Create `.env`

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Add your real API credentials and Neon PostgreSQL connection string.

## 3. Build

```bash
docker compose build
```

## 4. Start

```bash
docker compose up
```

The application will be available at:

```text
http://localhost:8000
```

## 5. Run in background

```bash
docker compose up -d
```

## 6. Check containers

```bash
docker compose ps
```

## 7. Check application health

Open:

```text
http://localhost:8000/health
```

Or:

```bash
curl http://localhost:8000/health
```

## 8. Stop

```bash
docker compose down
```

To remove the Redis volume:

```bash
docker compose down -v
```

---

# 💻 Running Without Docker

Install Python 3.11+ and `uv`.

```bash
uv sync --frozen
```

Create `.env` and configure:

* Groq
* Tavily
* AviationStack
* OpenWeather
* Neon PostgreSQL

Then start:

```bash
uv run uvicorn app:app --host 127.0.0.1 --port 8000
```

---

# 🔗 API

## `GET /`

Serves the TravelMind web application.

## `POST /api/travel`

Runs the complete travel-planning workflow.

Example:

```json
{
  "message": "Plan a 5-day trip from Delhi to Paris for 2 people."
}
```

Response includes:

```text
answer
thread_id
flight_results
hotel_results
weather_results
itinerary
llm_calls
```

## `GET /api/config`

Returns configuration status without exposing secrets.

## `POST /api/config`

Allows supported credentials to be configured for the current browser session.

Credentials are validated before being accepted.

## `DELETE /api/config`

Clears session-specific credentials.

## `GET /health`

Returns:

* application status
* configuration readiness
* missing configuration
* cache status

---

# 🔒 Session-Based Credentials

TravelMind supports session-specific configuration for supported credentials.

The application:

* associates credentials with a browser session
* uses an HTTP-only session cookie
* validates supplied credentials
* never echoes secrets in API responses
* allows session credentials to be cleared

---

# 🧵 Stateful Agent Execution

TravelMind uses LangGraph's thread configuration:

```python
config = {
    "configurable": {
        "thread_id": thread_id
    }
}
```

This allows workflow execution to be associated with a persistent thread.

The PostgreSQL checkpointer stores the state in Neon PostgreSQL.

---

# 🧪 Verification

Validate the Docker Compose configuration:

```bash
docker compose config
```

Build:

```bash
docker compose build
```

Start:

```bash
docker compose up
```

Check:

```bash
docker compose ps
```

Health:

```bash
curl http://localhost:8000/health
```

Then test the complete planning workflow:

```text
Plan a 5-day trip from Delhi to Paris for 2 people.
```

---

# 🎯 Example Use Case

### User

```text
Plan a 5-day trip from Delhi to Paris for 2 people.

Include:
- flights
- hotels
- weather
- daily itinerary
- estimated budget
- recommendations
```

### TravelMind

```text
User Request
     │
     ▼
Flight Research
     │
     ▼
Hotel Research
     │
     ▼
Weather Research
     │
     ▼
Itinerary Generation
     │
     ▼
Final AI Synthesis
     │
     ▼
Complete Travel Plan
```

---

# 🧩 Engineering Highlights

TravelMind demonstrates production-oriented AI engineering concepts including:

* Multi-agent AI architecture
* LangGraph orchestration
* Stateful graph execution
* MCP tool integration
* Remote MCP communication
* Local MCP servers
* FastAPI REST APIs
* Neon PostgreSQL
* LangGraph PostgreSQL checkpointing
* Redis caching
* Session-based credential management
* API credential validation
* Docker containerization
* Docker Compose
* Health checks
* Environment-based configuration
* Dependency locking with `uv.lock`
* Modular backend architecture

---

# 📊 Why This Is More Than an LLM Wrapper

Traditional LLM application:

```text
User
 ↓
LLM
 ↓
Response
```

TravelMind:

```text
                         ┌── Flight Agent ── AviationStack
                         │
User → FastAPI → LangGraph├── Hotel Agent ─── Research
                         │
                         ├── Weather Agent ─ OpenWeather
                         │
                         ├── Itinerary Agent
                         │
                         └── Final Agent
                                  │
                                  ▼
                           Final Travel Plan
                                  │
                                  ▼
                          Neon PostgreSQL
```

This architecture demonstrates orchestration, tool calling, persistent state, caching, external API integration, and containerized deployment.

---

# 🔮 Future Improvements

Potential future improvements include:

* Parallel execution of independent research agents
* Structured output schemas
* Automated unit/integration tests
* Authentication and authorization
* API rate limiting
* Request tracing
* Observability and metrics
* GitHub Actions CI/CD
* Production Redis deployment
* Travel maps and route visualization
* More specialized destination agents

---

# 👨‍💻 Author

**Asir Rafique**

GitHub: [@asirrafique](https://github.com/asirrafique)

---
