from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import psycopg2
import psycopg2.pool
from dotenv import load_dotenv


# Load environment variables
def _load_env() -> None:
    """Load .env from both CWD chain and repo root if present."""
    try:
        load_dotenv(override=False)
        root_env = Path(__file__).resolve().parents[2] / ".env"
        if root_env.exists():
            load_dotenv(dotenv_path=root_env, override=False)
    except Exception:
        pass


_load_env()


class PostgreSQLConnectionPool:
    """Thread-safe connection pool for PostgreSQL."""

    _instance: Optional[PostgreSQLConnectionPool] = None
    _pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._pool is None:
            self._initialize_pool()

    def _initialize_pool(self):
        """Initialize the PostgreSQL connection pool."""
        # Connection parameters from environment
        db_host = os.getenv("POSTGRES_HOST", "localhost")
        db_port = os.getenv("POSTGRES_PORT", "5432")
        db_name = os.getenv("POSTGRES_DB", "warrior_api")
        db_user = os.getenv("POSTGRES_USER", "warrior")
        db_password = os.getenv("POSTGRES_PASSWORD", "warrior_dev_password")

        # Pool sizing (adjust based on gunicorn workers and expected load)
        min_connections = int(os.getenv("DB_POOL_MIN", "20"))
        max_connections = int(os.getenv("DB_POOL_MAX", "100"))

        # Create DSN (connection string)
        dsn = f"host={db_host} port={db_port} dbname={db_name} user={db_user} password={db_password}"

        # Create threaded connection pool
        # ThreadedConnectionPool is thread-safe and suitable for gunicorn sync workers
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=min_connections,
            maxconn=max_connections,
            dsn=dsn,
            connect_timeout=10,  # 10 second connection timeout
            options="-c statement_timeout=30000",  # 30 second query timeout
        )

        print(
            f"PostgreSQL connection pool initialized: {min_connections}-{max_connections} connections to {db_host}:{db_port}/{db_name}"
        )

    @contextmanager
    def get_connection(self) -> Iterator[psycopg2.extensions.connection]:
        """
        Get a connection from the pool.
        
        Automatically commits on success, rolls back on exception.
        Connection is returned to pool when done.
        """
        conn = None
        try:
            conn = self._pool.getconn()
            conn.autocommit = False  # Explicit transaction control
            yield conn
            conn.commit()  # Auto-commit on success
        except Exception as e:
            if conn:
                conn.rollback()  # Auto-rollback on error
            raise
        finally:
            if conn:
                self._pool.putconn(conn)

    def close_all(self):
        """Close all connections in the pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None


# Global pool instance
_pool: Optional[PostgreSQLConnectionPool] = None


def get_pool() -> PostgreSQLConnectionPool:
    """Get or create the global connection pool."""
    global _pool
    if _pool is None:
        _pool = PostgreSQLConnectionPool()
    return _pool


@contextmanager
def get_pooled_connection() -> Iterator[psycopg2.extensions.connection]:
    """
    Get a connection from the global pool.
    
    Usage:
        with get_pooled_connection() as conn:
            # Use conn...
            # Auto-commits on success, rolls back on exception
    """
    pool = get_pool()
    with pool.get_connection() as conn:
        yield conn


def verify_database_health() -> tuple[bool, str]:
    """
    Verify database connectivity and health.
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        pool = get_pool()
        
        with pool.get_connection() as conn:
            with conn.cursor() as cur:
                # Test basic query
                cur.execute("SELECT 1")
                result = cur.fetchone()
                if result is None or result[0] != 1:
                    return False, "Test query returned unexpected result"
                
                # Check if warrior table exists
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public'
                        AND table_name = 'warrior'
                    )
                """)
                table_exists = cur.fetchone()[0]
                
                if not table_exists:
                    return False, "Warrior table does not exist. Run schema initialization."
                
                # Get connection info
                cur.execute("""
                    SELECT 
                        current_database(),
                        inet_server_addr(),
                        inet_server_port()
                """)
                db_name, host, port = cur.fetchone()
        
        return True, f"PostgreSQL health check passed - connected to {db_name} at {host}:{port}"
        
    except psycopg2.OperationalError as e:
        return False, f"Database connection failed: {e}"
    except Exception as e:
        return False, f"Database health check failed: {e}"

