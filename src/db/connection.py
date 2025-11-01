from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

import duckdb
from dotenv import load_dotenv

# Load variables from .env if present (robust across working directories)
from typing import Optional as _OptionalTyp

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

DEFAULT_LOCAL_PATH = "./data/app.duckdb"


def _ensure_parent_dir(db_path: str) -> None:
    path = Path(db_path)
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _motherduck_connect_str() -> str:
    db_name = os.getenv("MOTHERDUCK_DATABASE", "").strip()
    # "md:" uses your default MotherDuck context; "md:<db>" targets a specific DB
    return f"md:{db_name}" if db_name else "md:"


def _apply_schema(con: duckdb.DuckDBPyConnection) -> None:
    # Execute schema.sql next to this file
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    con.execute(sql)


@contextmanager
def get_connection(read_only: bool = False, apply_schema: bool = False) -> Iterator[duckdb.DuckDBPyConnection]:
    """
    Context manager returning a DuckDB connection.

    Controlled by env vars (load via .env or process env):
      - DB_MODE: "local" (default) or "motherduck"
      - LOCAL_DUCKDB_PATH: path to .duckdb file (local mode)
      - MOTHERDUCK_TOKEN: MotherDuck auth token (motherduck mode)
      - MOTHERDUCK_DATABASE: target DB name on MotherDuck (optional)
    
    Falls back to local mode if MotherDuck connection fails.
    """
    mode = os.getenv("DB_MODE", "local").strip().lower()

    if mode not in ("local", "motherduck"):
        raise ValueError(f"Unsupported DB_MODE: {mode}. Use 'local' or 'motherduck'.")

    con: Optional[duckdb.DuckDBPyConnection] = None
    try:
        if mode == "local":
            db_path = os.getenv("LOCAL_DUCKDB_PATH", DEFAULT_LOCAL_PATH)
            _ensure_parent_dir(db_path)
            con = duckdb.connect(db_path, read_only=read_only)
        else:
            # Try MotherDuck connection, fall back to local if it fails
            token = os.getenv("MOTHERDUCK_TOKEN", "").strip()
            if not token:
                raise EnvironmentError(
                    "MOTHERDUCK_TOKEN is not set. Export it securely or place it in .env (not recommended)."
                )
            # Ensure the token is visible to DuckDB's MotherDuck connector
            os.environ.setdefault("MOTHERDUCK_TOKEN", token)
            try:
                con = duckdb.connect(_motherduck_connect_str(), read_only=read_only)
            except Exception as e:
                # Fall back to local mode if MotherDuck connection fails
                import warnings
                warnings.warn(
                    f"Failed to connect to MotherDuck ({e}). Falling back to local database.",
                    UserWarning
                )
                db_path = os.getenv("LOCAL_DUCKDB_PATH", DEFAULT_LOCAL_PATH)
                _ensure_parent_dir(db_path)
                con = duckdb.connect(db_path, read_only=read_only)

        if apply_schema and not read_only:
            _apply_schema(con)

        yield con
    finally:
        if con is not None:
            con.close()
