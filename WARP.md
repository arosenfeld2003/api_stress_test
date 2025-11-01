# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

Project overview
- Purpose: API stress test scaffolding with a minimal Flask app and a DuckDB/MotherDuck persistence layer.
- Language: Python 3
- Key modules:
  - limiter.py: Flask app with IP-based rate limiting and a /health endpoint.
  - src/db/connection.py: Database connection context manager for local DuckDB or MotherDuck, with optional schema application from src/db/schema.sql.
  - src/db/warrior.py: Minimal DAO with create/get/search/count helpers for warriors.
  - src/db/schema.sql: Defines request_log, metric_rollup, and warrior tables plus indexes.

Setup and environment
- Python virtual environment is recommended.
- Dependencies in requirements.txt: duckdb, python-dotenv, flask, flask-limiter.
- Environment configuration is loaded from .env (see .env.example). Key variables:
  - DB_MODE: local (default) or motherduck
  - LOCAL_DUCKDB_PATH: path to the local .duckdb file
  - MOTHERDUCK_TOKEN: required when using MotherDuck (set securely in your shell)
  - MOTHERDUCK_DATABASE: optional MotherDuck DB name

Common commands
- Create and activate a virtual environment:
```bash path=null start=null
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

- Install dependencies:
```bash path=null start=null
pip install -r requirements.txt
```

- Run the Flask app locally on port 5000:
```bash path=null start=null
python limiter.py
```

- Health check once the server is running:
```bash path=null start=null
curl -sS http://localhost:5000/health | jq .
```

- Initialize or migrate the local DuckDB schema (creates ./data/app.duckdb if needed and applies schema.sql):
```bash path=null start=null
python -c "from src.db.connection import get_connection;\
    
from contextlib import suppress;\
    
with get_connection(read_only=False, apply_schema=True) as con:\
    
    pass"
```

- Use MotherDuck instead of local DuckDB (requires secure token export in your shell):
```bash path=null start=null
# Example (macOS Keychain):
# export MOTHERDUCK_TOKEN=$(security find-generic-password -s motherduck_token -w)
export DB_MODE=motherduck
# Optionally target a specific DB name
export MOTHERDUCK_DATABASE=api_stress_test_dev
# Then run your code normally, e.g.
python -c "from src.db.connection import get_connection;\
    
with get_connection(read_only=True) as con:\
    
    print(con.execute('select 1').fetchone())"
```

- Linting/formatting:
  - No linter/formatter configuration is present in this repo.

- Tests:
  - No tests or test configuration are present in this repo.

High-level architecture
- Web tier (limiter.py):
  - Flask app with a global error handler and graceful shutdown via SIGINT/SIGTERM.
  - IP-based rate limiting configured at 100 requests per minute using flask-limiter and get_remote_address.
  - Exposes /health for readiness checks.
  - Note: As of now, the web layer does not call into the db module.

- Data access layer (src/db):
  - connection.py provides get_connection(read_only=False, apply_schema=False):
    - Mode is selected via DB_MODE env var: local (DuckDB file) or motherduck.
    - Local mode ensures the parent directory for the DuckDB file exists and connects to LOCAL_DUCKDB_PATH (default ./data/app.duckdb).
    - MotherDuck mode requires MOTHERDUCK_TOKEN; optional MOTHERDUCK_DATABASE chooses a specific database; falls back to your default context if unset.
    - When apply_schema=True and not read_only, the SQL in schema.sql is executed against the current connection.
  - schema.sql defines domain tables:
    - request_log: raw request/response logs with method, path, status, latency_ms, client_ip, user_agent, payload_bytes, error; indexed by ts, path, method.
    - metric_rollup: pre-aggregated metrics keyed by window_start, window (e.g., 1m/5m), path, method, with p50/p90/p99 and error_rate.
    - warrior: domain entity for upcoming routes with columns id (UUID, PK), name (TEXT), dob (DATE), fight_skills (TEXT[]); indexes on name and dob.

Notes taken from repository docs
- README.md: "Qwasar MSCS Engineering Lab - Project 2" (no further operational instructions provided).
- .env.example: provides a template for DB configuration; avoid committing real secrets and prefer secure export of MOTHERDUCK_TOKEN in your shell session.

Repo-specific guidance for Warp
- Prefer local development with a virtual environment.
- If you need persistence for stress-test logs, initialize the schema using the provided Python one-liner before running load tests.
- When switching to MotherDuck, ensure MOTHERDUCK_TOKEN is set securely in the environment; do not print or commit secrets.
