"""Bull Strangle newsletter ingestion package."""

from .database import DEFAULT_DB_PATH
from .ingestion import ingest_newsletter

__all__ = ["DEFAULT_DB_PATH", "ingest_newsletter"]
