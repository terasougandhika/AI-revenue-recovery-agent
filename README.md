# ⚡ Real-Time AI Agentic Revenue Recovery Engine

> Detects customer friction signals from a live data stream and triggers RAG-powered AI interventions to protect high-value MRR before churn occurs.

---

## 💼 The Problem

Most SaaS companies discover churn **after** a customer has already left. By then it's too late — and acquiring a new customer costs **5–7× more** than retaining an existing one.

Silent churners don't complain. They just fade away — logging in less, using fewer features, and one day cancelling without warning. At scale, no human team can monitor every customer account 24/7.

**This system does.**

---

## 💡 The Solution

A fully automated, real-time pipeline that:

- **Watches** every customer interaction the moment it happens
- **Scores** churn risk continuously based on behavioral patterns
- **Alerts** on three types of friction signals
- **Intervenes** automatically with AI-generated, personalized actions
- **Escalates** high-value accounts to humans before it's too late

---

## 🏗️ Architecture

```
Customer Events (logins · errors · support tickets)
                        ↓
         Python → Redpanda (live event stream)
                        ↓
          PySpark (pattern detection · risk scoring)
                        ↓
       PostgreSQL + pgvector (alerts · knowledge base)
                ↙                     ↘
   Ollama Agent                  LangGraph + Gemini
  (low/medium alerts)            (high/critical + RAG)
                ↘                     ↙
          Streamlit Dashboard (Human in the Loop)
```

---

## 🚨 Alert Types

| Alert | What It Means | How It's Triggered |
|---|---|---|
| 🔇 **Silent Churn** | Customer quietly disengaging | Login drop ≥80% · No activity 7+ days |
| 🚨 **Incident** | Product actively broken for customer | 5+ errors/hr · Critical system failure |
| 🎫 **Support Tickets** | Customer struggling, help not arriving | 3+ open tickets · SLA breach |

---

## 🛠️ Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Event Streaming | **Python · Redpanda** | Kafka-compatible, zero data loss, simple ops |
| Stream Processing | **PySpark** | Real-time pattern detection at any scale |
| Database | **PostgreSQL · pgvector** | Relational data + vector search in one place |
| Proactive Agent | **Ollama (Llama3)** | Local LLM — private, no API cost, fast |
| Reactive Agent | **LangGraph · Gemini** | Complex RAG reasoning for high-stakes alerts |
| Dashboard | **Streamlit** | Human review + approval interface |
| Infrastructure | **Docker Compose** | One command to spin up everything |

---

## 🎬 Real Scenario

**Acme Corp — $3,500/month customer**

```
Day 3  → First data export error logged                     [Watching]
Day 4  → 3 errors + login frequency drops 50%              [MEDIUM Alert]
         Ollama sends a helpful feature tip automatically
Day 5  → No response · another error · no login in 36hrs   [HIGH Alert]
         RAG agent searches knowledge base
         Gemini drafts executive apology + 30-day credit
         CSM reviews and approves in Streamlit dashboard
Day 6  → Customer responds positively · issue resolved      [Retained ✅]
```

---

## 🤖 Two AI Agents

**Proactive Agent (Ollama)**
Runs locally. Handles LOW and MEDIUM alerts automatically — feature tips, check-in emails, re-engagement nudges. No human approval needed. Covers 90% of alert volume.

**Reactive RAG Agent (LangGraph + Gemini)**
Handles HIGH and CRITICAL alerts. Searches the company knowledge base using semantic similarity (pgvector), retrieves the most relevant past cases and playbooks, then uses Gemini to generate a precise, grounded intervention. Sent to the Streamlit dashboard for human approval before action.

---

## 💰 Business Impact

- Catch disengaging customers **hours or days** before they decide to leave
- Prioritize by MRR — highest value accounts get the fastest, smartest response
- AI handles routine cases automatically — humans focus only where it matters
- Every outcome feeds back into the knowledge base, making the system smarter over time

---


