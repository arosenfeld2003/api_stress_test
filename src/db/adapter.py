"""
Database adapter that switches between DuckDB and PostgreSQL based on DB_MODE.
This allows seamless migration without changing route code.
"""

import os
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

# Get DB mode from environment
DB_MODE = os.getenv("DB_MODE", "local").strip().lower()

if DB_MODE == "postgresql":
    # Use PostgreSQL
    from src.db.connection_postgres import get_pooled_connection
    from src.db.warrior_postgres import (
        create_warrior as _create_warrior,
        get_warrior as _get_warrior,
        search_warriors as _search_warriors,
        count_warriors as _count_warriors,
    )
else:
    # Use DuckDB (local mode)
    from src.db.pool import get_pooled_connection
    from src.db.warrior import (
        create_warrior as _create_warrior,
        get_warrior as _get_warrior,
        search_warriors as _search_warriors,
        count_warriors as _count_warriors,
    )


# Export unified interface
__all__ = [
    "get_pooled_connection",
    "create_warrior",
    "get_warrior",
    "search_warriors",
    "count_warriors",
]


def create_warrior(con, *, id: str, name: str, dob: str, fight_skills: List[str]) -> None:
    """Create a warrior (works with both DuckDB and PostgreSQL)."""
    return _create_warrior(con, id=id, name=name, dob=dob, fight_skills=fight_skills)


def get_warrior(con, *, id: str) -> Optional[Dict[str, Any]]:
    """Get warrior by ID (works with both DuckDB and PostgreSQL)."""
    return _get_warrior(con, id=id)


def search_warriors(con, *, term: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search warriors (works with both DuckDB and PostgreSQL)."""
    return _search_warriors(con, term=term, limit=limit)


def count_warriors(con) -> int:
    """Count warriors (works with both DuckDB and PostgreSQL)."""
    return _count_warriors(con)


# Print which database we're using
print(f"📊 Database mode: {DB_MODE.upper()}")
if DB_MODE == "postgresql":
    print(f"   Using PostgreSQL at {os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}")
else:
    print(f"   Using DuckDB at {os.getenv('LOCAL_DUCKDB_PATH', './data/app.duckdb')}")

