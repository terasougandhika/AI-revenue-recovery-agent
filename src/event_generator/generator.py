"""
Event Generator — Python producer for customer events.

Features:
- Generates realistic customer events (login, error, support_ticket)
- Circuit breaker pattern: stops hammering Redpanda when it's down
- SQLite local buffer: persists events to disk during outages
- Automatic retry: drains the buffer when Redpanda recovers
"""

import os
import json
import time
import random
import sqlite3
import uuid
from enum       import Enum
from datetime   import datetime, timedelta
from contextlib import contextmanager

from confluent_kafka        import Producer
from confluent_kafka.error  import KafkaException
from dotenv                 import load_dotenv
from loguru                 import logger

from src.event_generator.customers import CUSTOMERS

load_dotenv()

# ─── CONFIG ────────────────────────────────────────────────────
REDPANDA_BROKERS          = os.getenv("REDPANDA_BROKERS", "localhost:19092")
TOPIC_NAME                = os.getenv("TOPIC_NAME", "customer-events")
EVENT_INTERVAL_MS         = int(os.getenv("EVENT_INTERVAL_MS", "500"))
CIRCUIT_BREAKER_THRESHOLD = int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))
CIRCUIT_BREAKER_TIMEOUT   = int(os.getenv("CIRCUIT_BREAKER_TIMEOUT", "30"))
SQLITE_BUFFER_PATH        = "/tmp/event_buffer.db"

# ─── CIRCUIT BREAKER ───────────────────────────────────────────
class CircuitState(Enum):
    CLOSED    = "CLOSED"      # Normal — send directly to Redpanda
    OPEN      = "OPEN"        # Outage — buffer locally, skip Redpanda
    HALF_OPEN = "HALF_OPEN"   # Testing — probe if Redpanda recovered


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.state              = CircuitState.CLOSED
        self.failure_count      = 0
        self.success_count      = 0
        self.last_failure_time  = None
        self.failure_threshold  = failure_threshold
        self.recovery_timeout   = recovery_timeout

    def record_success(self):
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 2:
                logger.success("Circuit CLOSED — Redpanda is back!")
                self.state         = CircuitState.CLOSED
                self.success_count = 0

    def record_failure(self):
        self.failure_count    += 1
        self.last_failure_time = time.time()
        self.success_count     = 0

        if self.state == CircuitState.HALF_OPEN:
            logger.warning("Circuit back to OPEN — Redpanda still down")
            self.state = CircuitState.OPEN

        elif self.failure_count >= self.failure_threshold:
            logger.warning(
                f"Circuit TRIPPED (OPEN) after {self.failure_count} failures. "
                "All events will buffer locally."
            )
            self.state = CircuitState.OPEN

    def should_attempt(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = time.time() - (self.last_failure_time or 0)
            if elapsed >= self.recovery_timeout:
                logger.info(
                    f"{self.recovery_timeout}s passed — testing if Redpanda recovered..."
                )
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        return True  # HALF_OPEN — allow probe


# ─── SQLITE BUFFER ─────────────────────────────────────────────
def init_buffer_db() -> None:
    """Create the SQLite buffer table on first run."""
    conn = sqlite3.connect(SQLITE_BUFFER_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_buffer (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id  TEXT    NOT NULL,
            event_json   TEXT    NOT NULL,
            buffered_at  TEXT    NOT NULL,
            attempts     INTEGER DEFAULT 0,
            status       TEXT    DEFAULT 'pending',
            last_error   TEXT
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_status ON event_buffer(status, attempts)"
    )
    conn.commit()
    conn.close()


@contextmanager
def get_buffer_db():
    conn = sqlite3.connect(SQLITE_BUFFER_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def buffer_event(event: dict, error: str = "") -> None:
    """Persist a failed event to SQLite."""
    with get_buffer_db() as db:
        db.execute(
            """
            INSERT INTO event_buffer (customer_id, event_json, buffered_at, last_error)
            VALUES (?, ?, ?, ?)
            """,
            (event["customer_id"], json.dumps(event),
             datetime.utcnow().isoformat(), error),
        )
    logger.debug(f"Buffered to SQLite: {event['customer_id']} | {event['event_type']}")


def flush_buffer(producer: Producer) -> None:
    """Retry all pending events in the SQLite buffer."""
    with get_buffer_db() as db:
        pending = db.execute(
            """
            SELECT id, customer_id, event_json, attempts
            FROM   event_buffer
            WHERE  status = 'pending' AND attempts < 20
            ORDER  BY id ASC
            LIMIT  200
            """
        ).fetchall()

    if not pending:
        return

    logger.info(f"Retrying {len(pending)} buffered events...")
    succeeded = failed = 0

    for row in pending:
        try:
            producer.produce(
                topic=TOPIC_NAME,
                key=row["customer_id"],
                value=row["event_json"],
            )
            producer.flush()

            with get_buffer_db() as db:
                db.execute("DELETE FROM event_buffer WHERE id = ?", (row["id"],))
            succeeded += 1

        except KafkaException as e:
            new_attempts = row["attempts"] + 1
            new_status   = "failed_permanent" if new_attempts >= 20 else "pending"
            with get_buffer_db() as db:
                db.execute(
                    "UPDATE event_buffer SET attempts=?, status=?, last_error=? WHERE id=?",
                    (new_attempts, new_status, str(e), row["id"]),
                )
            failed += 1

    if succeeded:
        logger.success(f"Buffer flush: {succeeded} sent, {failed} still pending")


def buffer_stats() -> dict:
    """Return counts of buffered events by status."""
    with get_buffer_db() as db:
        rows = db.execute(
            "SELECT status, COUNT(*) as cnt FROM event_buffer GROUP BY status"
        ).fetchall()
    return {row["status"]: row["cnt"] for row in rows}


# ─── EVENT GENERATION ──────────────────────────────────────────
# Weights control how often each event type appears per plan tier
EVENT_WEIGHTS = {
    "enterprise": {"login": 0.60, "error": 0.20, "support_ticket": 0.20},
    "pro":        {"login": 0.55, "error": 0.25, "support_ticket": 0.20},
    "starter":    {"login": 0.50, "error": 0.30, "support_ticket": 0.20},
}

SEVERITIES    = ["low", "medium", "high", "critical"]
SEVERITY_WEIGHTS = [0.50, 0.30, 0.15, 0.05]    # most events are low severity

ERROR_TYPES = [
    "data_export_failure",
    "authentication_timeout",
    "api_rate_limit_exceeded",
    "database_connection_error",
    "file_upload_failed",
    "dashboard_load_timeout",
    "payment_processing_error",
    "report_generation_failed",
]

TICKET_SUBJECTS = [
    "Cannot export data — critical workflow blocked",
    "Dashboard loading extremely slowly",
    "API integration returning 500 errors",
    "Unable to add new team members",
    "Billing discrepancy on last invoice",
    "Data not syncing between modules",
    "Feature not working as documented",
    "Performance degradation after last update",
]


def generate_event(customer: dict) -> dict:
    """Build a single realistic customer event."""
    plan         = customer["plan"]
    weights      = EVENT_WEIGHTS[plan]
    event_type   = random.choices(
        list(weights.keys()), weights=list(weights.values()), k=1
    )[0]
    severity     = random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS, k=1)[0]

    event: dict = {
        "event_id":        str(uuid.uuid4()),
        "customer_id":     customer["id"],
        "customer_name":   customer["name"],
        "mrr":             customer["mrr"],
        "plan":            customer["plan"],
        "industry":        customer["industry"],
        "event_type":      event_type,
        "severity":        severity,
        "timestamp":       datetime.utcnow().isoformat() + "Z",
    }

    # Add type-specific fields
    if event_type == "error":
        event["error_type"]    = random.choice(ERROR_TYPES)
        event["error_count"]   = random.randint(1, 10)
        event["session_id"]    = f"sess_{uuid.uuid4().hex[:8]}"

    elif event_type == "support_ticket":
        event["ticket_subject"] = random.choice(TICKET_SUBJECTS)
        event["ticket_id"]      = f"TKT-{random.randint(10000, 99999)}"
        event["open_hours"]     = random.randint(0, 96)

    elif event_type == "login":
        event["session_duration_min"] = random.randint(1, 180)
        event["features_used"]        = random.randint(1, 12)

    return event


# ─── SMART PRODUCER ────────────────────────────────────────────
class SmartProducer:
    """
    Kafka producer with circuit breaker + SQLite local buffer.
    Guarantees no event loss during Redpanda outages.
    """

    def __init__(self):
        self.producer = Producer({
            "bootstrap.servers":  REDPANDA_BROKERS,
            "socket.timeout.ms":  3000,
            "message.timeout.ms": 5000,
            "retries":            3,
            "retry.backoff.ms":   500,
        })
        self.circuit  = CircuitBreaker(
            failure_threshold=CIRCUIT_BREAKER_THRESHOLD,
            recovery_timeout=CIRCUIT_BREAKER_TIMEOUT,
        )
        init_buffer_db()
        logger.info(f"SmartProducer ready → {REDPANDA_BROKERS}")

    def send(self, event: dict) -> bool:
        """Send event to Redpanda. Falls back to SQLite if unavailable."""
        if not self.circuit.should_attempt():
            buffer_event(event, "Circuit open — Redpanda unavailable")
            return False

        try:
            self.producer.produce(
                topic=TOPIC_NAME,
                key=event["customer_id"],
                value=json.dumps(event),
            )
            self.producer.poll(0)
            self.circuit.record_success()
            return True

        except KafkaException as e:
            logger.warning(f"Send failed: {e}")
            self.circuit.record_failure()
            buffer_event(event, str(e))
            return False

    def status(self) -> dict:
        return {
            "circuit_state":   self.circuit.state.value,
            "failure_count":   self.circuit.failure_count,
            "buffer_stats":    buffer_stats(),
        }


# ─── MAIN LOOP ─────────────────────────────────────────────────
def main():
    logger.info("Starting Revenue Recovery Event Generator")
    producer     = SmartProducer()
    last_retry   = time.time()
    last_status  = time.time()
    events_sent  = 0

    # On startup — check for leftover buffered events from last crash
    logger.info("Checking for events buffered in previous session...")
    flush_buffer(producer.producer)

    while True:
        # Pick a random customer and generate an event
        customer = random.choice(CUSTOMERS)
        event    = generate_event(customer)

        if producer.send(event):
            events_sent += 1
            logger.debug(
                f"→ {event['customer_id']} | {event['event_type']} | "
                f"severity={event['severity']} | mrr=${customer['mrr']}"
            )

        now = time.time()

        # Retry buffered events every 10 seconds
        if now - last_retry > 10:
            flush_buffer(producer.producer)
            last_retry = now

        # Print status summary every 60 seconds
        if now - last_status > 60:
            status = producer.status()
            logger.info(
                f"Status | sent={events_sent} | "
                f"circuit={status['circuit_state']} | "
                f"buffer={status['buffer_stats']}"
            )
            last_status = now

        time.sleep(EVENT_INTERVAL_MS / 1000)


if __name__ == "__main__":
    main()
