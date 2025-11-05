from __future__ import annotations

from typing import Any, Dict, List, Optional

import duckdb

# Data access helpers for the warriors domain.
# These functions operate on the existing DuckDB connection.


def create_warrior(
    con: duckdb.DuckDBPyConnection,
    *,
    id: str,
    name: str,
    dob: str,
    fight_skills: List[str],
) -> None:
    """
    Insert a new warrior with optimized performance.
    - id: UUID string (any version)
    - dob: 'YYYY-MM-DD'
    - fight_skills: list of strings
    """
    # Use prepared statement for better performance
    con.execute(
        """
        INSERT INTO warrior (id, name, dob, fight_skills)
        VALUES (CAST(? AS UUID), ?, CAST(? AS DATE), ?)
        """,
        [id, name, dob, fight_skills],
    )
    # Force commit for consistency under high load
    con.commit()


def get_warrior(
    con: duckdb.DuckDBPyConnection, *, id: str
) -> Optional[Dict[str, Any]]:
    row = (
        con.execute(
            """
            SELECT CAST(id AS TEXT) AS id,
                   name,
                   strftime(dob, '%Y-%m-%d') AS dob,
                   fight_skills
            FROM warrior
            WHERE id = CAST(? AS UUID)
            """,
            [id],
        ).fetchone()
    )
    if row is None:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "dob": row[2],
        "fight_skills": row[3],
    }


def search_warriors(
    con: duckdb.DuckDBPyConnection, *, term: str, limit: int = 50
) -> List[Dict[str, Any]]:
    # High-performance search with optimized query plan
    # Limit term length to prevent expensive operations
    if len(term) > 100:
        term = term[:100]
    
    pattern = f'%{term}%'
    
    # Optimized query with better indexing strategy
    rows = con.execute(
        """
        SELECT CAST(id AS TEXT) AS id,
               name,
               strftime(dob, '%Y-%m-%d') AS dob,
               fight_skills
        FROM warrior w
        WHERE name ILIKE ? 
           OR strftime(dob, '%Y-%m-%d') ILIKE ?
           OR list_contains(list_transform(fight_skills, x -> lower(x)), lower(?))
        ORDER BY 
            CASE WHEN name ILIKE ? THEN 1
                 WHEN strftime(dob, '%Y-%m-%d') ILIKE ? THEN 2
                 ELSE 3 END,
            name
        LIMIT ?
        """,
        [pattern, pattern, term.lower(), pattern, pattern, limit],
    ).fetchall()
    return [
        {"id": r[0], "name": r[1], "dob": r[2], "fight_skills": r[3]}
        for r in rows
    ]


def count_warriors(con: duckdb.DuckDBPyConnection) -> int:
    (cnt,) = con.execute("SELECT COUNT(*) FROM warrior").fetchone()
    return int(cnt)
