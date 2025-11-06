"""
Database connection pool for high-performance stress testing.
Maintains a pool of connections to reduce connection overhead.
"""

import threading
import time
from contextlib import contextmanager
from queue import Queue, Empty
from typing import Iterator, Optional
import duckdb
import os
from pathlib import Path

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
            # Ensure parent directory exists
            path = Path(self.db_path)
            if path.parent and not path.parent.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
            
            con = duckdb.connect(self.db_path)
            
            # Apply performance optimizations
            import multiprocessing
            thread_count = min(multiprocessing.cpu_count(), 4)
            con.execute(f"PRAGMA threads={thread_count}")
            con.execute("PRAGMA enable_progress_bar=false")
            con.execute("PRAGMA memory_limit='256MB'")
            con.execute("PRAGMA checkpoint_threshold='32MB'")
            con.execute("PRAGMA wal_autocheckpoint=5000")
            con.execute("PRAGMA synchronous=NORMAL")
            con.execute("PRAGMA journal_mode=WAL")
            
            return con
        except Exception as e:
            print(f"Failed to create database connection: {e}")
            return None
    
    @contextmanager
    def get_connection(self, timeout: float = 30.0) -> Iterator[Optional[duckdb.DuckDBPyConnection]]:
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
                    if hasattr(conn, 'execute'):
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