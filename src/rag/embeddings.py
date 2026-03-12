"""
Embeddings — converts text into vector representations for RAG.
Uses sentence-transformers (runs locally, no API needed).
"""

import os
from functools import lru_cache
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

EMBEDDING_MODEL     = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))


@lru_cache(maxsize=1)
def get_embedding_model():
    """Load model once and cache it — expensive to load each time."""
    from sentence_transformers import SentenceTransformer
    logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
    model = SentenceTransformer(EMBEDDING_MODEL)
    logger.success(f"Embedding model loaded — dimension: {EMBEDDING_DIMENSION}")
    return model


def embed_text(text: str) -> list[float]:
    """Convert a single string to a vector embedding."""
    model  = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Convert a list of strings to embeddings in one efficient batch call."""
    model   = get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vectors]


def build_alert_query(alert: dict) -> str:
    """
    Build a natural-language description of an alert for semantic search.
    The more descriptive this text, the better the RAG retrieval.
    """
    return (
        f"Customer {alert.get('customer_name', 'unknown')} "
        f"on {alert.get('plan', 'unknown')} plan "
        f"with MRR ${alert.get('mrr', 0)} "
        f"has {alert.get('alert_type', 'unknown').replace('_', ' ')} alert. "
        f"Severity: {alert.get('severity', 'unknown')}. "
        f"Risk score: {alert.get('risk_score', 0)}/100. "
        f"Details: {alert.get('details', '')}"
    )
