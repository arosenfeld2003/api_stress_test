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
    Insert a new warrior.
    - id: UUID string (any version)
    - dob: 'YYYY-MM-DD'
    - fight_skills: list of strings
    """
    con.execute(
        """
        INSERT INTO warrior (id, name, dob, fight_skills)
        VALUES (CAST(? AS UUID), ?, CAST(? AS DATE), ?)
        """,
        [id, name, dob, fight_skills],
    )


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
    rows = con.execute(
        """
        SELECT CAST(id AS TEXT) AS id,
               name,
               strftime(dob, '%Y-%m-%d') AS dob,
               fight_skills
        FROM warrior w
        WHERE name ILIKE '%' || ? || '%'
           OR CAST(dob AS TEXT) ILIKE '%' || ? || '%'
           OR EXISTS (
                SELECT 1
                FROM UNNEST(w.fight_skills) fs(value)
                WHERE value ILIKE '%' || ? || '%'
           )
        ORDER BY name
        LIMIT ?
        """,
        [term, term, term, limit],
    ).fetchall()
    return [
        {"id": r[0], "name": r[1], "dob": r[2], "fight_skills": r[3]}
        for r in rows
    ]


def count_warriors(con: duckdb.DuckDBPyConnection) -> int:
    (cnt,) = con.execute("SELECT COUNT(*) FROM warrior").fetchone()
    return int(cnt)
