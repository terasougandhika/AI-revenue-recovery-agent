"""
Reactive RAG Agent — LangGraph + Gemini for HIGH and CRITICAL alerts.

Flow:
  read_alert → assess_severity → retrieve_knowledge →
  build_prompt → call_gemini → format_action → save_recommendation

Run with: python -m src.agents.reactive_agent
"""

import os
import time
from typing import TypedDict, Annotated
from dotenv import load_dotenv
from loguru import logger

from langgraph.graph import StateGraph, END
import google.generativeai as genai

from src.database.models import (
    get_open_alerts,
    create_intervention,
    semantic_search,
)
from src.rag.embeddings import embed_text, build_alert_query

load_dotenv()

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
POLL_INTERVAL   = int(os.getenv("REACTIVE_AGENT_POLL_INTERVAL", "10"))
HANDLED_SEVERITIES = {"high", "critical"}

genai.configure(api_key=GEMINI_API_KEY)


# ─── AGENT STATE ───────────────────────────────────────────────
# LangGraph passes this state dict between every node in the graph
class AgentState(TypedDict):
    alert:               dict
    retrieved_docs:      list[dict]
    reasoning:           str
    recommendation:      str
    confidence:          float
    error:               str | None


# ─── GRAPH NODES ───────────────────────────────────────────────

def node_assess_severity(state: AgentState) -> AgentState:
    """
    Node 1: Assess the alert and decide if we should proceed.
    For very low-confidence cases, flag for human review.
    """
    alert = state["alert"]
    logger.info(
        f"Assessing: {alert['alert_type']} | "
        f"{alert['severity']} | score={alert['risk_score']}"
    )

    # Build initial reasoning
    state["reasoning"] = (
        f"Alert Analysis:\n"
        f"- Customer: {alert['customer_name']} ({alert['plan']}, ${alert['mrr']}/mo)\n"
        f"- Alert type: {alert['alert_type']}\n"
        f"- Severity: {alert['severity']}\n"
        f"- Risk score: {alert['risk_score']}/100\n"
    )
    return state


def node_retrieve_knowledge(state: AgentState) -> AgentState:
    """
    Node 2: RAG retrieval — find relevant playbooks and past cases.
    Converts the alert to a query vector, searches pgvector knowledge base.
    """
    alert       = state["alert"]
    query_text  = build_alert_query(alert)
    query_vec   = embed_text(query_text)

    # Semantic search — find top 5 most similar knowledge base docs
    docs = semantic_search(query_embedding=query_vec, limit=5)
    state["retrieved_docs"] = docs

    state["reasoning"] += (
        f"\nKnowledge Retrieval:\n"
        f"- Query: {query_text[:100]}...\n"
        f"- Found {len(docs)} relevant documents\n"
    )

    for i, doc in enumerate(docs[:3], 1):
        state["reasoning"] += (
            f"  [{i}] {doc['category']} | similarity={doc['similarity']:.2f}\n"
        )

    logger.info(f"Retrieved {len(docs)} knowledge docs (top similarity: "
                f"{docs[0]['similarity']:.2f if docs else 'N/A'})")
    return state


def node_call_gemini(state: AgentState) -> AgentState:
    """
    Node 3: Call Gemini with alert context + retrieved knowledge.
    This is the core RAG generation step.
    """
    alert = state["alert"]
    docs  = state["retrieved_docs"]

    # Build the RAG-augmented context from retrieved docs
    knowledge_context = "\n\n".join([
        f"[Playbook: {doc['category']}]\n{doc['content']}"
        for doc in docs
    ]) if docs else "No specific playbooks found — use general best practices."

    prompt = f"""You are an expert Customer Success AI at a SaaS company.

CUSTOMER ALERT:
- Customer: {alert['customer_name']}
- Plan: {alert['plan']} | MRR: ${alert['mrr']}/month
- Alert Type: {alert['alert_type'].replace('_', ' ').title()}
- Severity: {alert['severity'].upper()}
- Risk Score: {alert['risk_score']}/100

RELEVANT COMPANY PLAYBOOKS AND PAST CASES:
{knowledge_context}

Based on this alert AND our company-specific playbooks above, provide:

1. SITUATION SUMMARY (2 sentences): What is happening and why it matters
2. RECOMMENDED ACTION: Exactly what to do (email, call, engineer escalation, offer)
3. CUSTOMER MESSAGE: Draft the actual message to send the customer (personalized, warm, under 200 words)
4. OFFER/REMEDY: What to offer if appropriate (credit, call, dedicated support, feature walkthrough)
5. FOLLOW-UP: What to do in 48 hours if no response
6. CONFIDENCE: Your confidence this intervention will retain the customer (0-100)

Be specific, not generic. Reference the customer's plan and MRR tier in your approach."""

    try:
        model    = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        state["recommendation"] = response.text.strip()

        # Extract confidence score from response (simple heuristic)
        import re
        match = re.search(r"confidence[:\s]+(\d+)", response.text, re.IGNORECASE)
        state["confidence"] = float(match.group(1)) / 100 if match else 0.75

        logger.success(
            f"Gemini recommendation generated | "
            f"confidence={state['confidence']:.0%}"
        )

    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        state["error"]          = str(e)
        state["recommendation"] = f"Error generating recommendation: {e}"
        state["confidence"]     = 0.0

    return state


def node_save_recommendation(state: AgentState) -> AgentState:
    """
    Node 4: Save the recommendation to the database.
    Status = 'pending' — awaits human approval in Streamlit dashboard.
    """
    if state.get("error"):
        logger.warning("Skipping save — error in previous step")
        return state

    alert = state["alert"]

    intervention_id = create_intervention(
        alert_id     = alert["id"],
        action       = state["recommendation"],
        ai_reasoning = (
            f"{state['reasoning']}\n\n"
            f"Confidence: {state['confidence']:.0%}\n"
            f"Knowledge docs used: {len(state['retrieved_docs'])}"
        ),
        approved_by  = "pending_human_review",
    )

    logger.success(
        f"✅ Recommendation saved (id={intervention_id}) | "
        f"awaiting human approval in dashboard"
    )
    return state


# ─── BUILD THE LANGGRAPH ───────────────────────────────────────
def build_agent() -> object:
    """
    Construct the LangGraph state machine.

    Graph structure:
      assess_severity → retrieve_knowledge → call_gemini → save_recommendation → END
    """
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("assess_severity",      node_assess_severity)
    graph.add_node("retrieve_knowledge",   node_retrieve_knowledge)
    graph.add_node("call_gemini",          node_call_gemini)
    graph.add_node("save_recommendation",  node_save_recommendation)

    # Define edges (execution order)
    graph.set_entry_point("assess_severity")
    graph.add_edge("assess_severity",     "retrieve_knowledge")
    graph.add_edge("retrieve_knowledge",  "call_gemini")
    graph.add_edge("call_gemini",         "save_recommendation")
    graph.add_edge("save_recommendation", END)

    return graph.compile()


# ─── MAIN LOOP ─────────────────────────────────────────────────
def main():
    logger.info(f"Reactive RAG Agent starting — model: {GEMINI_MODEL}")
    logger.info(f"Polling every {POLL_INTERVAL}s for HIGH/CRITICAL alerts")

    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set in .env file!")
        return

    agent        = build_agent()
    processed_ids = set()

    while True:
        alerts = get_open_alerts(limit=20)

        actionable = [
            a for a in alerts
            if a["severity"] in HANDLED_SEVERITIES
            and a["id"] not in processed_ids
        ]

        if actionable:
            logger.info(
                f"Found {len(actionable)} HIGH/CRITICAL alerts to process"
            )

            for alert in actionable:
                logger.info(
                    f"─── Processing alert #{alert['id']}: "
                    f"{alert['customer_name']} | "
                    f"{alert['severity'].upper()} ───"
                )

                initial_state: AgentState = {
                    "alert":           alert,
                    "retrieved_docs":  [],
                    "reasoning":       "",
                    "recommendation":  "",
                    "confidence":      0.0,
                    "error":           None,
                }

                # Run the full LangGraph pipeline
                final_state = agent.invoke(initial_state)
                processed_ids.add(alert["id"])

                time.sleep(3)   # brief pause between Gemini calls

        else:
            logger.debug("No new HIGH/CRITICAL alerts — sleeping...")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
