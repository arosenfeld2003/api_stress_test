"""
Database connection pool for high-performance stress testing.
Maintains a pool of connections to reduce connection overhead.
"""

from __future__ import annotations

import threading
import time
import multiprocessing
from contextlib import contextmanager
from queue import Queue, Empty
from typing import Iterator, Optional
import duckdb
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present (robust across working directories)
def _load_env() -> None:
    """Load .env from both CWD chain and repo root if present without overriding real env.
    This allows storing MOTHERDUCK_TOKEN (and others) in a local .env for development.
    """
    try:
        # Load from current working directory upward (finds repo root in most cases)
        load_dotenv(override=False)
        # Additionally load .env relative to the repository root inferred from this file
        root_env = Path(__file__).resolve().parents[2] / ".env"
        if root_env.exists():
            load_dotenv(dotenv_path=root_env, override=False)
    except Exception:
        # Fail-open: environment loading should never break runtime
        pass

_load_env()


class DuckDBConnectionPool:
    def __init__(self, db_path: str, pool_size: int = 10, max_connections: int = 20):
        self.db_path = db_path
        self.pool_size = pool_size
        self.max_connections = max_connections
        self.pool = Queue(maxsize=max_connections)
        self.active_connections = 0
        self.lock = threading.Lock()

        # Pre-populate pool with connections
        self._initialize_pool()

    def _initialize_pool(self):
        """Pre-create connections for the pool."""
        for _ in range(self.pool_size):
            conn = self._create_connection()
            if conn:
                self.pool.put(conn)
                self.active_connections += 1

    def _create_connection(self) -> Optional[duckdb.DuckDBPyConnection]:
        """Create a new optimized DuckDB connection."""
        try:
            mode = os.getenv("DB_MODE", "local").strip().lower()
            if mode == "motherduck":
                # MotherDuck connection
                token = os.getenv("MOTHERDUCK_TOKEN", "").strip()
                if not token:
                    print("MOTHERDUCK_TOKEN not set, falling back to local mode")
                    mode = "local"
                else:
                    # Ensure the token is visible to DuckDB's MotherDuck connector
                    os.environ.setdefault("MOTHERDUCK_TOKEN", token)
                    db_name = os.getenv("MOTHERDUCK_DATABASE", "").strip()
                    connect_str = f"md:{db_name}" if db_name else "md:"
                    try:
                        con = duckdb.connect(connect_str)
                        # MotherDuck connections don't support all PRAGMAs
                        con.execute("PRAGMA enable_progress_bar=false")
                        return con
                    except Exception as e:
                        print(
                            f"Failed to connect to MotherDuck ({e}), falling back to local mode"
                        )
                        mode = "local"
            
            # Local connection (either mode was "local" or MotherDuck failed)
            if mode == "local":
                # Ensure parent directory exists
                path = Path(self.db_path)
                path.parent.mkdir(parents=True, exist_ok=True)
                con = duckdb.connect(self.db_path)
                # Apply performance optimizations for local DB
                thread_count = min(multiprocessing.cpu_count(), 4)
                con.execute(f"PRAGMA threads={thread_count}")
                con.execute("PRAGMA enable_progress_bar=false")
                con.execute("PRAGMA memory_limit='256MB'")
                con.execute("PRAGMA checkpoint_threshold='32MB'")
                con.execute("PRAGMA wal_autocheckpoint=5000")
                con.execute("PRAGMA synchronous=NORMAL")
                con.execute("PRAGMA journal_mode=WAL")
                return con
            
            return None
        except Exception as e:
            print(f"Failed to create database connection: {e}")
            return None

    @contextmanager
    def get_connection(
        self, timeout: float = 30.0
    ) -> Iterator[Optional[duckdb.DuckDBPyConnection]]:
        """Get a connection from the pool with timeout."""
        conn = None
        try:
            # Try to get from pool first
            try:
                conn = self.pool.get(timeout=timeout)
            except Empty:
                # Pool is empty, try to create a new connection if under limit
                with self.lock:
                    if self.active_connections < self.max_connections:
                        conn = self._create_connection()
                        if conn:
                            self.active_connections += 1
                        else:
                            raise Exception("Failed to create new connection")
                    else:
                        raise Exception("Connection pool exhausted")

            yield conn

        finally:
            if conn:
                try:
                    # Return connection to pool if healthy
                    if hasattr(conn, "execute"):
                        # Quick health check (commented out for performance)
                        # conn.execute("SELECT 1")
                        self.pool.put_nowait(conn)
                    else:
                        # Connection is bad, create a new one
                        with self.lock:
                            self.active_connections -= 1
                        new_conn = self._create_connection()
                        if new_conn:
                            with self.lock:
                                self.active_connections += 1
                            self.pool.put_nowait(new_conn)
                except Exception:
                    # Connection is bad, don't return to pool
                    with self.lock:
                        self.active_connections -= 1
                    # Try to create replacement
                    try:
                        new_conn = self._create_connection()
                        if new_conn:
                            with self.lock:
                                self.active_connections += 1
                            self.pool.put_nowait(new_conn)
                    except Exception:
                        pass  # Ignore replacement failures

    def close_all(self):
        """Close all connections in the pool."""
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                conn.close()
            except (Empty, Exception):
                pass
        self.active_connections = 0


# Global connection pool instance
_pool: Optional[DuckDBConnectionPool] = None
_pool_lock = threading.Lock()


def get_pool() -> DuckDBConnectionPool:
    """Get or create the global connection pool."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                db_path = os.getenv("LOCAL_DUCKDB_PATH", "./data/app.duckdb")
                pool_size = int(os.getenv("DB_POOL_SIZE", "20"))
                max_connections = int(os.getenv("DB_MAX_CONNECTIONS", "40"))
                _pool = DuckDBConnectionPool(db_path, pool_size, max_connections)
    return _pool


@contextmanager
def get_pooled_connection() -> Iterator[duckdb.DuckDBPyConnection]:
    """Get a connection from the global pool."""
    pool = get_pool()
    with pool.get_connection() as conn:
        if conn is None:
            raise Exception("Failed to get database connection from pool")
        yield conn


def verify_database_health() -> tuple[bool, str]:
    """
    Verify database connectivity and health.
    
    Returns:
        tuple: (success: bool, message: str)
        - If success is True, message contains success information
        - If success is False, message contains error details
    """
    try:
        # Test connection pool initialization
        pool = get_pool()
        
        # Get a connection from the pool
        with pool.get_connection(timeout=10.0) as conn:
            if conn is None:
                return False, "Failed to get connection from pool"
            
            # Execute a simple test query to verify connection works
            result = conn.execute("SELECT 1").fetchone()
            if result is None or result[0] != 1:
                return False, "Test query returned unexpected result"
            
            # Verify schema tables exist (warrior table should exist after schema initialization)
            try:
                table_check = conn.execute(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'warrior'"
                ).fetchone()
                if table_check is None or table_check[0] == 0:
                    # Schema might not be initialized yet, but connection pool is working
                    # This is a warning, not a failure - schema will be initialized by limiter.py
                    pass
            except Exception:
                # If information_schema is not available (e.g., older DuckDB versions),
                # try to query the warrior table directly
                try:
                    conn.execute("SELECT COUNT(*) FROM warrior LIMIT 1")
                except Exception:
                    # Table doesn't exist yet - this is OK, schema will be initialized
                    pass
        
        # Determine mode for success message
        mode = os.getenv("DB_MODE", "local").strip().lower()
        if mode == "motherduck":
            db_name = os.getenv("MOTHERDUCK_DATABASE", "").strip()
            db_info = f"MotherDuck database '{db_name}'" if db_name else "MotherDuck (default context)"
        else:
            db_path = os.getenv("LOCAL_DUCKDB_PATH", "./data/app.duckdb")
            db_info = f"local database at {db_path}"
        
        return True, f"Database health check passed - connected to {db_info}"
        
    except Exception as e:
        error_msg = str(e)
        mode = os.getenv("DB_MODE", "local").strip().lower()
        
        if mode == "motherduck":
            token_set = bool(os.getenv("MOTHERDUCK_TOKEN", "").strip())
            if not token_set:
                error_msg = "MOTHERDUCK_TOKEN is not set. " + error_msg
        else:
            db_path = os.getenv("LOCAL_DUCKDB_PATH", "./data/app.duckdb")
            error_msg = f"Failed to connect to local database at {db_path}. " + error_msg
        
        return False, f"Database health check failed: {error_msg}"
