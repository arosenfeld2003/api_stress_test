from __future__ import annotations

from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


def create_warrior(
    con: psycopg2.extensions.connection,
    *,
    id: str,
    name: str,
    dob: str,
    fight_skills: List[str],
) -> None:
    """
    Insert a new warrior.
    
    Args:
        con: PostgreSQL connection
        id: UUID string
        name: Warrior name
        dob: Date of birth in YYYY-MM-DD format
        fight_skills: List of fighting skills
    """
    with con.cursor() as cur:
        cur.execute(
            """
            INSERT INTO warrior (id, name, dob, fight_skills)
            VALUES (%s::UUID, %s, %s::DATE, %s)
            """,
            (id, name, dob, fight_skills),
        )
    # Connection context manager handles commit


def get_warrior(
    con: psycopg2.extensions.connection, *, id: str
) -> Optional[Dict[str, Any]]:
    """
    Get warrior by ID.
    
    Args:
        con: PostgreSQL connection
        id: Warrior UUID
        
    Returns:
        Warrior dict or None if not found
    """
    with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT 
                id::TEXT,
                name,
                to_char(dob, 'YYYY-MM-DD') as dob,
                fight_skills
            FROM warrior
            WHERE id = %s::UUID
            """,
            (id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def search_warriors(
    con: psycopg2.extensions.connection, *, term: str, limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Search warriors by term (name, dob, or fight skills).
    
    Uses PostgreSQL's powerful indexing for fast searches even under load.
    
    Args:
        con: PostgreSQL connection
        term: Search term
        limit: Maximum results to return
        
    Returns:
        List of warrior dicts matching the search
    """
    # Limit term length to prevent abuse
    if len(term) > 100:
        term = term[:100]

    with con.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # Use PostgreSQL's ILIKE and array operations
        # This query is optimized with appropriate indexes
        cur.execute(
            """
            SELECT 
                id::TEXT,
                name,
                to_char(dob, 'YYYY-MM-DD') as dob,
                fight_skills
            FROM warrior
            WHERE 
                name ILIKE %s
                OR to_char(dob, 'YYYY-MM-DD') ILIKE %s
                OR %s = ANY(fight_skills)
                OR EXISTS (
                    SELECT 1 FROM unnest(fight_skills) AS skill
                    WHERE skill ILIKE %s
                )
            ORDER BY 
                CASE 
                    WHEN name ILIKE %s THEN 1
                    WHEN to_char(dob, 'YYYY-MM-DD') ILIKE %s THEN 2
                    ELSE 3 
                END,
                name
            LIMIT %s
            """,
            (
                f"%{term}%",  # name search
                f"%{term}%",  # dob search
                term,  # exact skill match
                f"%{term}%",  # skill substring match
                f"%{term}%",  # order by name match priority
                f"%{term}%",  # order by dob match priority
                limit,
            ),
        )
        return [dict(row) for row in cur.fetchall()]


def count_warriors(con: psycopg2.extensions.connection) -> int:
    """
    Count all warriors in the database.
    
    Args:
        con: PostgreSQL connection
        
    Returns:
        Total warrior count
    """
    with con.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM warrior")
        result = cur.fetchone()
        return int(result[0]) if result else 0

