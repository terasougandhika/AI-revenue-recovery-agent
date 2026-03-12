"""
Database models — all SQL queries in one place.
"""

from datetime import datetime
from src.database.connection import get_cursor


# ─── ALERTS ────────────────────────────────────────────────────

def get_open_alerts(limit: int = 100) -> list[dict]:
    """Fetch open alerts sorted by risk (severity × MRR)."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                a.id,
                a.customer_id,
                c.name          AS customer_name,
                c.mrr,
                c.plan,
                a.alert_type,
                a.severity,
                a.risk_score,
                a.details,
                a.status,
                a.created_at,
                -- Priority score: risk_score × log(mrr) for ranking
                (a.risk_score * ln(c.mrr + 1)) AS priority_score
            FROM   alerts a
            JOIN   customers c ON c.id = a.customer_id
            WHERE  a.status = 'open'
            ORDER  BY priority_score DESC
            LIMIT  %s
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]


def create_alert(
    customer_id: str,
    alert_type: str,
    severity: str,
    risk_score: int,
    details: dict,
) -> int:
    """Insert a new alert. Returns the new alert ID."""
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO alerts
                (customer_id, alert_type, severity, risk_score, details, status, created_at)
            VALUES
                (%s, %s, %s, %s, %s::jsonb, 'open', NOW())
            RETURNING id
        """, (customer_id, alert_type, severity, risk_score, str(details)))
        row = cur.fetchone()
        return row["id"]


def close_alert(alert_id: int) -> None:
    with get_cursor() as cur:
        cur.execute(
            "UPDATE alerts SET status='closed', updated_at=NOW() WHERE id=%s",
            (alert_id,)
        )


# ─── INTERVENTIONS ─────────────────────────────────────────────

def create_intervention(
    alert_id: int,
    action: str,
    ai_reasoning: str,
    approved_by: str = "auto",
) -> int:
    """Log an AI-generated intervention."""
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO interventions
                (alert_id, action, ai_reasoning, approved_by, status, created_at)
            VALUES
                (%s, %s, %s, %s, 'pending', NOW())
            RETURNING id
        """, (alert_id, action, ai_reasoning, approved_by))
        return cur.fetchone()["id"]


def approve_intervention(intervention_id: int, approved_by: str) -> None:
    with get_cursor() as cur:
        cur.execute("""
            UPDATE interventions
            SET    status='approved', approved_by=%s, approved_at=NOW()
            WHERE  id=%s
        """, (approved_by, intervention_id))


def record_outcome(intervention_id: int, outcome: str) -> None:
    """Record whether the intervention worked. outcome = 'retained' | 'churned' | 'no_response'"""
    with get_cursor() as cur:
        cur.execute(
            "UPDATE interventions SET outcome=%s, outcome_at=NOW() WHERE id=%s",
            (outcome, intervention_id)
        )


def get_pending_interventions() -> list[dict]:
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                i.*,
                a.alert_type,
                a.severity,
                a.risk_score,
                c.name  AS customer_name,
                c.mrr
            FROM   interventions i
            JOIN   alerts        a ON a.id = i.alert_id
            JOIN   customers     c ON c.id = a.customer_id
            WHERE  i.status = 'pending'
            ORDER  BY i.created_at DESC
        """)
        return [dict(row) for row in cur.fetchall()]


# ─── CUSTOMERS ─────────────────────────────────────────────────

def upsert_customer(customer: dict) -> None:
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO customers (id, name, mrr, plan, industry, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (id) DO UPDATE
                SET name=EXCLUDED.name,
                    mrr=EXCLUDED.mrr,
                    plan=EXCLUDED.plan,
                    industry=EXCLUDED.industry,
                    updated_at=NOW()
        """, (
            customer["id"], customer["name"], customer["mrr"],
            customer["plan"], customer["industry"],
        ))


def get_mrr_at_risk() -> float:
    """Total MRR from customers with open alerts."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT COALESCE(SUM(DISTINCT c.mrr), 0) AS total
            FROM   alerts a
            JOIN   customers c ON c.id = a.customer_id
            WHERE  a.status = 'open'
        """)
        return float(cur.fetchone()["total"])


# ─── KNOWLEDGE BASE ────────────────────────────────────────────

def insert_knowledge_doc(content: str, category: str, embedding: list[float]) -> int:
    """Store a knowledge base document with its embedding vector."""
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO knowledge_base (content, category, embedding, created_at)
            VALUES (%s, %s, %s::vector, NOW())
            RETURNING id
        """, (content, category, str(embedding)))
        return cur.fetchone()["id"]


def semantic_search(query_embedding: list[float], limit: int = 5) -> list[dict]:
    """
    Find the most semantically similar knowledge base documents.
    Uses pgvector cosine distance (<->) — smaller = more similar.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                id,
                content,
                category,
                1 - (embedding <-> %s::vector) AS similarity
            FROM   knowledge_base
            ORDER  BY embedding <-> %s::vector
            LIMIT  %s
        """, (str(query_embedding), str(query_embedding), limit))
        return [dict(row) for row in cur.fetchall()]


# ─── DASHBOARD STATS ───────────────────────────────────────────

def get_dashboard_stats() -> dict:
    """All stats needed for the dashboard header."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*)                                             AS total_open_alerts,
                COUNT(*) FILTER (WHERE severity = 'critical')       AS critical_alerts,
                COUNT(*) FILTER (WHERE severity = 'high')           AS high_alerts,
                COUNT(*) FILTER (WHERE severity = 'medium')         AS medium_alerts,
                COUNT(*) FILTER (WHERE severity = 'low')            AS low_alerts,
                COUNT(*) FILTER (WHERE alert_type = 'silent_churn') AS silent_churn,
                COUNT(*) FILTER (WHERE alert_type = 'incident')     AS incidents,
                COUNT(*) FILTER (WHERE alert_type = 'support')      AS support_tickets
            FROM alerts
            WHERE status = 'open'
        """)
        return dict(cur.fetchone())
