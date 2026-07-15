from __future__ import annotations

import os
from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def _postgres_dsn() -> str:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
        raise RuntimeError("LangGraph PostgresSaver requires a PostgreSQL DATABASE_URL.")
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache(maxsize=1)
def get_postgres_checkpointer() -> PostgresSaver:
    pool = ConnectionPool(
        conninfo=_postgres_dsn(),
        min_size=1,
        max_size=int(os.getenv("CHECKPOINT_POOL_SIZE", "5")),
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    return checkpointer


def initialize_checkpointer() -> None:
    get_postgres_checkpointer()
