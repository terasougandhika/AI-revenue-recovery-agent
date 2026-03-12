# ⚡ Real-Time AI Agentic Revenue Recovery Engine

> Detects customer friction signals from a live data stream and triggers RAG-powered AI interventions to protect high-value MRR before churn occurs.

---

## 🧠 What It Does

Most SaaS companies discover churn **after** a customer leaves. This system detects the warning signs **before** the decision is made — and automatically intervenes.

It watches every customer interaction in real time, scores churn risk, and deploys AI agents to take action — all while keeping a human in the loop for high-stakes decisions.

---

## 🏗️ Architecture

```
Customer Events (logins · errors · support tickets)
            ↓
    Python → Redpanda (live event stream)
            ↓
    PySpark (pattern detection + risk scoring)
            ↓
    PostgreSQL + pgvector (alerts + knowledge base)
            ↓
    Ollama Agent          LangGraph + Gemini Agent
    (low/medium alerts)   (high/critical + RAG)
            ↓
    Streamlit Dashboard (Human in the Loop)
```

---

## 🚨 Three Alert Types

| Alert | Trigger | Response |
|---|---|---|
| 🔇 **Silent Churn** | Login drop, inactivity | Re-engagement outreach |
| 🚨 **Incident** | Errors, system failures | Immediate intervention |
| 🎫 **Support Tickets** | Unresolved, escalating | Escalation + ownership |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Event Streaming | Python · Redpanda (Kafka-compatible) |
| Stream Processing | PySpark Structured Streaming |
| Database | PostgreSQL · pgvector |
| Proactive AI Agent | Ollama (local LLM — Llama3) |
| Reactive RAG Agent | LangGraph · Google Gemini |
| Dashboard | Streamlit |
| Infrastructure | Docker Compose |

---

## 🚀 Quick Start

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up database
python scripts/setup_db.py
python scripts/seed_knowledge_base.py

# 4. Run (each in a separate terminal)
python -m src.event_generator.generator
python -m src.stream_processor.processor
python -m src.agents.proactive_agent
python -m src.agents.reactive_agent
streamlit run src/dashboard/app.py
```

Open **http://localhost:8501** to view the dashboard.

---

## 📁 Project Structure

```
├── src/
│   ├── event_generator/    # Customer event simulation + circuit breaker
│   ├── stream_processor/   # PySpark real-time churn detection
│   ├── database/           # PostgreSQL models + pgvector queries
│   ├── agents/             # Ollama + LangGraph/Gemini AI agents
│   ├── rag/                # Embeddings + semantic search
│   └── dashboard/          # Streamlit human-in-the-loop UI
├── scripts/                # DB setup + knowledge base seeding
├── docker-compose.yml      # Redpanda + PostgreSQL
├── requirements.txt
└── .env.example
```

---

## ⚙️ Environment Variables

Copy `.env.example` to `.env` and fill in:

```
REDPANDA_BROKERS=localhost:19092
POSTGRES_URL=postgresql://user:pass@localhost:5432/recovery_db
GEMINI_API_KEY=your_key_here
OLLAMA_MODEL=llama3
```

---

## 📄 License

MIT License
