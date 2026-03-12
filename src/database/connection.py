"""
Database connection pool and core query helpers.
Uses psycopg2 directly for performance-critical paths.
"""

import os
from contextlib import contextmanager

import psycopg2
import psycopg2.pool
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://recovery_user:recovery_pass@localhost:5432/recovery_db",
)

# Connection pool — reuses connections instead of creating new ones
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=POSTGRES_URL,
        )
        logger.info("PostgreSQL connection pool created")
    return _pool


@contextmanager
def get_db():
    """Context manager — gets a connection from pool, auto-returns it."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        conn.autocommit = False
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def get_cursor():
    """Convenience: get a dict cursor directly."""
    with get_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
