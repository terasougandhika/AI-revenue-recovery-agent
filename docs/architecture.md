# Real-Time AI Agentic Revenue Recovery Engine
# System Architecture

## Component Responsibilities

### Event Generator (src/event_generator/)
- Generates customer events: login, error, support_ticket
- Publishes to Redpanda topic: customer-events
- Circuit breaker: stops retrying when Redpanda is down
- SQLite buffer: persists events locally during outages
- Auto-recovers: drains buffer when Redpanda comes back

### Stream Processor (src/stream_processor/)
- Reads from Redpanda using PySpark Structured Streaming
- 3 parallel aggregation streams:
  * Error stream: 1-hour sliding window, flags 5+ errors/hr
  * Ticket stream: 24-hour window, flags 3+ open tickets
  * Login stream: 7-day window, flags login frequency drops
- Calculates risk score (0-100) per customer
- Classifies severity: low / medium / high / critical
- Writes alert records to PostgreSQL

### Database (src/database/)
- PostgreSQL with pgvector extension
- Tables: customers, alerts, interventions, knowledge_base, event_log
- HNSW index on knowledge_base.embedding for fast vector search
- All components read/write through this central store

### Proactive Agent (src/agents/proactive_agent.py)
- Polls for LOW and MEDIUM severity alerts every 30s
- Uses Ollama (local Llama3) — no data leaves infrastructure
- Auto-approves and logs interventions (no human review needed)
- Handles 90-95% of alert volume

### Reactive RAG Agent (src/agents/reactive_agent.py)
- Polls for HIGH and CRITICAL severity alerts every 10s
- LangGraph pipeline: assess → retrieve → generate → save
- Semantic search on knowledge base (pgvector cosine similarity)
- Calls Gemini with alert context + retrieved playbooks
- Saves recommendations as 'pending' for human review

### Dashboard (src/dashboard/app.py)
- Streamlit web dashboard: http://localhost:8501
- Live alert feed sorted by priority (severity × MRR)
- AI recommendation review panel with approve/reject
- Intervention history and outcome tracking
- MRR at risk metrics

## Data Flow

```
Python → Redpanda → PySpark → PostgreSQL ← AI Agents ← Alerts
                                        ↑
                              Streamlit reads here
```

## Key Design Decisions

1. PostgreSQL as single source of truth (not separate systems)
2. pgvector eliminates need for separate vector database
3. Tiered AI: cheap local (Ollama) for routine, premium cloud (Gemini) for critical
4. Circuit breaker prevents cascading failures during Redpanda outages
5. Human in the loop for HIGH/CRITICAL alerts — AI assists, human decides
