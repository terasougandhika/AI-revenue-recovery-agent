# 🔴 Real-Time AI Agentic Revenue Recovery Engine

> Detects customer friction signals from a live data stream and triggers RAG-powered AI interventions to protect high-value MRR before churn occurs.

![Architecture](docs/architecture.png)

## 📋 Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Running the System](#running-the-system)
- [Component Deep Dives](#component-deep-dives)
- [Environment Variables](#environment-variables)

---

## Overview

This system solves **silent churn** in SaaS businesses. Most companies discover churn **after** a customer leaves. This engine detects the signals **before** the decision is made — and automatically intervenes.

### How It Works

```
Customer Events (logins, errors, tickets)
        ↓
Python Event Generator → Redpanda (Message Broker)
        ↓
PySpark Stream Processor (pattern detection + scoring)
        ↓
PostgreSQL + pgvector (alerts + knowledge base)
        ↓
AI Agents ──→ Proactive (Ollama) — low/medium severity
           └→ Reactive RAG (LangGraph + Gemini) — high/critical
        ↓
Streamlit Dashboard (Human in the Loop)
```

### Three Alert Types
| Alert | Trigger | Action |
|---|---|---|
| 🔇 **Silent Churn** | Login drop ≥80%, inactivity 7+ days | Re-engagement outreach |
| 🚨 **Incident** | 5+ errors/hr, system failure | Immediate technical intervention |
| 🎫 **Support Ticket** | 3+ open tickets, SLA breach | Escalation + ownership |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     EVENT INGESTION LAYER                        │
│  Python Generator → Redpanda (Kafka-compatible message broker)  │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓ Live Event Stream
┌─────────────────────────────────────────────────────────────────┐
│                    STREAM PROCESSING LAYER                       │
│         PySpark Structured Streaming (Analysis & Transform)      │
└──────────────────────────────┬──────────────────────────────────┘
                               ↓ Writes Alerts
┌─────────────────────────────────────────────────────────────────┐
│                       DATABASE LAYER                             │
│           PostgreSQL + pgvector (Alerts + Knowledge Base)        │
└───────────┬──────────────────────────────┬──────────────────────┘
            ↓ reads alerts                 ↓ reads alerts
┌───────────────────────┐    ┌─────────────────────────────────────┐
│   AGENTIC LAYER        │    │         DASHBOARD LAYER             │
│  Ollama (Proactive)    │    │   Streamlit (Human in the Loop)     │
│  LangGraph + Gemini    │    │                                     │
│  (Reactive RAG)        │    │                                     │
└───────────────────────┘    └─────────────────────────────────────┘
```

---

## Tech Stack

| Component | Technology | Purpose |
|---|---|---|
| Event Generation | Python + confluent-kafka | Simulate/capture customer events |
| Message Broker | Redpanda | Durable event streaming (Kafka-compatible) |
| Stream Processing | PySpark Structured Streaming | Real-time pattern detection |
| Database | PostgreSQL | Alerts, customers, interventions |
| Vector Search | pgvector | Semantic similarity for RAG |
| Proactive Agent | Ollama (Llama3) | Local LLM, low/medium alerts |
| Reactive Agent | LangGraph + Google Gemini | RAG-powered high/critical alerts |
| Dashboard | Streamlit | Human review + approval |

---

## Project Structure

```
revenue-recovery-engine/
│
├── src/
│   ├── event_generator/
│   │   ├── generator.py          # Main event loop with circuit breaker
│   │   └── customers.py          # Sample customer data
│   │
│   ├── stream_processor/
│   │   └── processor.py          # PySpark streaming job
│   │
│   ├── database/
│   │   ├── connection.py         # DB connection pool
│   │   └── models.py             # Table schemas + queries
│   │
│   ├── agents/
│   │   ├── proactive_agent.py    # Ollama agent (low/medium)
│   │   └── reactive_agent.py     # LangGraph + Gemini (high/critical)
│   │
│   ├── rag/
│   │   ├── embeddings.py         # Text → vector conversion
│   │   └── knowledge_base.py     # Knowledge base management
│   │
│   └── dashboard/
│       └── app.py                # Streamlit dashboard
│
├── scripts/
│   ├── setup_db.py               # Initialize PostgreSQL schema
│   └── seed_knowledge_base.py    # Populate knowledge base docs
│
├── tests/
│   ├── test_generator.py
│   ├── test_processor.py
│   └── test_agents.py
│
├── docs/
│   └── architecture.md
│
├── docker-compose.yml            # Redpanda + PostgreSQL
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- Docker + Docker Compose
- Java 11+ (for PySpark)
- Ollama installed locally

### Step 1 — Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/revenue-recovery-engine.git
cd revenue-recovery-engine
```

### Step 2 — Set Up Environment Variables
```bash
cp .env.example .env
# Edit .env with your values (Gemini API key, DB credentials)
```

### Step 3 — Start Infrastructure (Redpanda + PostgreSQL)
```bash
docker-compose up -d
# Wait ~30 seconds for services to be healthy
docker-compose ps    # verify all containers are running
```

### Step 4 — Install Python Dependencies
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 5 — Initialize the Database
```bash
python scripts/setup_db.py
```

### Step 6 — Seed the Knowledge Base
```bash
python scripts/seed_knowledge_base.py
```

### Step 7 — Pull Ollama Model
```bash
ollama pull llama3
```

---

## Running the System

Run each component in a separate terminal:

```bash
# Terminal 1 — Event Generator (with circuit breaker + SQLite buffer)
python -m src.event_generator.generator

# Terminal 2 — PySpark Stream Processor
python -m src.stream_processor.processor

# Terminal 3 — Proactive AI Agent (Ollama)
python -m src.agents.proactive_agent

# Terminal 4 — Reactive RAG Agent (LangGraph + Gemini)
python -m src.agents.reactive_agent

# Terminal 5 — Streamlit Dashboard
streamlit run src/dashboard/app.py
```

Then open: **http://localhost:8501**

---

## Component Deep Dives

### Event Generator
Generates 3 event types per customer: `login`, `error`, `support_ticket`.
Includes **circuit breaker + SQLite local buffer** — if Redpanda goes down, events are persisted locally and replayed when it recovers.

### PySpark Processor
- Reads from Redpanda topic `customer-events`
- Applies 1-hour sliding window aggregations per customer
- Calculates churn risk score (0–100)
- Classifies into 3 alert types
- Writes to PostgreSQL `alerts` table

### Proactive Agent (Ollama)
- Polls for LOW/MEDIUM alerts every 30 seconds
- Uses local Llama3 model — no data leaves your server
- Auto-sends feature tips, check-in messages
- Logs all actions to `interventions` table

### Reactive RAG Agent (LangGraph + Gemini)
- Triggers on HIGH/CRITICAL alerts
- Converts alert to embedding vector
- Semantic search on knowledge base (pgvector)
- Feeds top-5 relevant docs to Gemini
- Drafts intervention → sends to Streamlit for approval

### Streamlit Dashboard
- Live alert feed sorted by severity × MRR
- AI recommendation review panel
- One-click approve/reject interventions
- MRR at risk metrics
- Intervention history + outcome tracking

---

## Environment Variables

| Variable | Description | Example |
|---|---|---|
| `REDPANDA_BROKERS` | Redpanda connection string | `localhost:19092` |
| `POSTGRES_URL` | PostgreSQL connection URL | `postgresql://user:pass@localhost:5432/recovery` |
| `GEMINI_API_KEY` | Google Gemini API key | `AIza...` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | Model to use | `llama3` |
| `EMBEDDING_MODEL` | Sentence transformer model | `all-MiniLM-L6-v2` |
| `TOPIC_NAME` | Redpanda topic | `customer-events` |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit changes: `git commit -m 'Add your feature'`
4. Push: `git push origin feature/your-feature`
5. Open a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE) for details.
