"""
Database Setup Script — run this ONCE to create all tables.

Usage: python scripts/setup_db.py
"""

import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://recovery_user:recovery_pass@localhost:5432/recovery_db"
)

SCHEMA_SQL = """
-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- ─── CUSTOMERS ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    id          VARCHAR(20)     PRIMARY KEY,
    name        VARCHAR(100)    NOT NULL,
    mrr         DECIMAL(10,2)   NOT NULL DEFAULT 0,
    plan        VARCHAR(20)     NOT NULL DEFAULT 'starter',
    industry    VARCHAR(50),
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ
);

-- ─── ALERTS ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id           SERIAL          PRIMARY KEY,
    customer_id  VARCHAR(20)     NOT NULL REFERENCES customers(id),
    alert_type   VARCHAR(30)     NOT NULL,
    -- 'silent_churn' | 'incident' | 'support'
    severity     VARCHAR(20)     NOT NULL DEFAULT 'low',
    -- 'low' | 'medium' | 'high' | 'critical'
    risk_score   INTEGER         NOT NULL DEFAULT 0 CHECK (risk_score BETWEEN 0 AND 100),
    details      JSONB,
    status       VARCHAR(20)     NOT NULL DEFAULT 'open',
    -- 'open' | 'closed' | 'in_progress'
    created_at   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_alerts_status
    ON alerts(status, severity, customer_id);

CREATE INDEX IF NOT EXISTS idx_alerts_customer
    ON alerts(customer_id, created_at DESC);

-- ─── INTERVENTIONS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS interventions (
    id              SERIAL          PRIMARY KEY,
    alert_id        INTEGER         NOT NULL REFERENCES alerts(id),
    action          TEXT            NOT NULL,
    ai_reasoning    TEXT,
    approved_by     VARCHAR(50)     NOT NULL DEFAULT 'auto',
    -- 'auto' | 'pending_human_review' | actual username
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending',
    -- 'pending' | 'approved' | 'rejected' | 'sent'
    outcome         VARCHAR(30),
    -- 'retained' | 'churned' | 'no_response' | 'rejected'
    approved_at     TIMESTAMPTZ,
    outcome_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interventions_status
    ON interventions(status, created_at DESC);

-- ─── KNOWLEDGE BASE ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_base (
    id          SERIAL          PRIMARY KEY,
    content     TEXT            NOT NULL,
    category    VARCHAR(50)     NOT NULL,
    -- 'playbook' | 'past_case' | 'offer_template' | 'product_doc'
    embedding   VECTOR(384),    -- sentence-transformers all-MiniLM-L6-v2 dimension
    metadata    JSONB,
    created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- HNSW index for fast approximate nearest-neighbor search
-- m=16, ef_construction=64 are standard starting values
CREATE INDEX IF NOT EXISTS idx_knowledge_embedding
    ON knowledge_base USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_knowledge_category
    ON knowledge_base(category);

-- ─── EVENT LOG (optional — for debugging) ───────────────────
CREATE TABLE IF NOT EXISTS event_log (
    id          BIGSERIAL       PRIMARY KEY,
    customer_id VARCHAR(20)     NOT NULL,
    event_type  VARCHAR(30)     NOT NULL,
    severity    VARCHAR(20),
    payload     JSONB,
    received_at TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- Partition by month in production for performance
-- CREATE INDEX IF NOT EXISTS idx_event_log_customer
--     ON event_log(customer_id, received_at DESC);
"""


def setup():
    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(POSTGRES_URL)
    conn.autocommit = True
    cur = conn.cursor()

    print("Creating schema...")
    cur.execute(SCHEMA_SQL)

    # Seed customer data from the event generator's customer list
    from src.event_generator.customers import CUSTOMERS
    print(f"Seeding {len(CUSTOMERS)} customers...")
    for c in CUSTOMERS:
        cur.execute("""
            INSERT INTO customers (id, name, mrr, plan, industry)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE
                SET name=EXCLUDED.name, mrr=EXCLUDED.mrr,
                    plan=EXCLUDED.plan, industry=EXCLUDED.industry
        """, (c["id"], c["name"], c["mrr"], c["plan"], c["industry"]))

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database setup complete!")
    print("\nTables created: customers, alerts, interventions, knowledge_base, event_log")
    print("Extensions: pgvector")
    print("Indexes: HNSW on knowledge_base.embedding")


if __name__ == "__main__":
    setup()
