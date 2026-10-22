"""MySQL connection pool and transaction helpers for FoodBridge.

Usage
-----
    from database.database import get_connection, query_one, query_all, execute

Configuration is read from environment variables (or a .env file loaded by
dotenv if python-dotenv is installed).  Defaults are provided for local dev.

    FOODBRIDGE_DB_HOST     default: 127.0.0.1
    FOODBRIDGE_DB_PORT     default: 3306
    FOODBRIDGE_DB_USER     default: root
    FOODBRIDGE_DB_PASSWORD default: (empty)
    FOODBRIDGE_DB_NAME     default: foodbridge
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator

import mysql.connector
from mysql.connector import pooling

# ------------------------------------------------------------------ config
try:
    from dotenv import load_dotenv  # optional dependency
    load_dotenv()
except ImportError:
    pass

_DB_CONFIG = {
    "host":     os.getenv("FOODBRIDGE_DB_HOST",     "127.0.0.1"),
    "port":     int(os.getenv("FOODBRIDGE_DB_PORT", "3306")),
    "user":     os.getenv("FOODBRIDGE_DB_USER",     "root"),
    "password": os.getenv("FOODBRIDGE_DB_PASSWORD", ""),
    "database": os.getenv("FOODBRIDGE_DB_NAME",     "foodbridge"),
    "charset":  "utf8mb4",
    "time_zone": "+00:00",
    "autocommit": False,
    "use_unicode": True,
}

_POOL_SIZE = int(os.getenv("FOODBRIDGE_DB_POOL_SIZE", "5"))

# Lazy-initialised singleton pool
_pool: pooling.MySQLConnectionPool | None = None


def _get_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="foodbridge",
            pool_size=_POOL_SIZE,
            **_DB_CONFIG,
        )
    return _pool


def get_connection() -> mysql.connector.MySQLConnection:
    """Return a raw connection from the pool.  Caller must close it."""
    return _get_pool().get_connection()


# ---------------------------------------------------------------- helpers
@contextmanager
def _conn() -> Generator[mysql.connector.MySQLConnection, None, None]:
    """Internal context manager: yields a connection and closes it."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction() -> Generator[mysql.connector.connection.MySQLCursor, None, None]:
    """Yield a cursor inside a transaction.  Commits on success, rolls back on error."""
    with _conn() as conn:
        cur = conn.cursor(dictionary=True)
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def query_one(sql: str, params: tuple | dict | None = None) -> dict | None:
    """Execute *sql* and return the first row as a dict, or None."""
    with _conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params or ())
        row = cur.fetchone()
        cur.close()
        return row


def query_all(sql: str, params: tuple | dict | None = None) -> list[dict]:
    """Execute *sql* and return all rows as a list of dicts."""
    with _conn() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        cur.close()
        return rows


def execute(sql: str, params: tuple | dict | None = None) -> int:
    """Execute a single DML statement in its own auto-committed transaction.
    Returns lastrowid (useful for INSERT)."""
    with _conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        conn.commit()
        last_id = cur.lastrowid
        cur.close()
        return last_id
