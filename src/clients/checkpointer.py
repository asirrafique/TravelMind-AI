"""PostgreSQL checkpointer used by LangGraph to persist conversation threads."""

from functools import lru_cache

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

from src.config.session import require, resolve_database_url


@lru_cache(maxsize=4)
def get_connection_pool(database_url: str) -> ConnectionPool:
    """Create a resilient PostgreSQL connection pool."""

    return ConnectionPool(
        database_url,
        min_size=1,
        max_size=5,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            "prepare_threshold": 0,
        },
        check=ConnectionPool.check_connection,
        max_lifetime=1800,
        max_idle=300,
        reconnect_timeout=300,
        timeout=30,
        open=True,
    )


@lru_cache(maxsize=4)
def get_checkpointer(database_url: str) -> PostgresSaver:
    """Return a LangGraph PostgresSaver backed by a connection pool."""

    pool = get_connection_pool(database_url)

    checkpointer = PostgresSaver(pool)
    checkpointer.setup()

    return checkpointer


def get_session_checkpointer() -> PostgresSaver:
    """Checkpointer for whichever database URL the current session resolves to."""

    require("DATABASE_URL")

    return get_checkpointer(resolve_database_url())