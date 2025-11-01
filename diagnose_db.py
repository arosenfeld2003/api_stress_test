#!/usr/bin/env python3
"""Diagnostic script to investigate database connection issues."""

import os
import sys
from dotenv import load_dotenv
from pathlib import Path

# Load environment
load_dotenv(override=False)
root_env = Path(__file__).resolve().parent / ".env"
if root_env.exists():
    load_dotenv(dotenv_path=root_env, override=False)

def diagnose_motherduck():
    """Diagnose MotherDuck connection issues."""
    print("=== MotherDuck Connection Diagnostic ===\n")
    
    # Check environment variables
    mode = os.getenv("DB_MODE", "NOT SET").strip().lower()
    db_name = os.getenv("MOTHERDUCK_DATABASE", "NOT SET").strip()
    token = os.getenv("MOTHERDUCK_TOKEN", "")
    
    print(f"DB_MODE: {mode}")
    print(f"MOTHERDUCK_DATABASE: {db_name if db_name else '(not set - will use default context)'}")
    print(f"MOTHERDUCK_TOKEN: {'SET' if token else 'NOT SET'}\n")
    
    if mode != "motherduck":
        print("✓ DB_MODE is not 'motherduck', so MotherDuck connection won't be attempted.")
        return
    
    if not token:
        print("✗ MOTHERDUCK_TOKEN is not set!")
        print("  Set it with: export MOTHERDUCK_TOKEN=your_token")
        return
    
    # Try to connect
    try:
        import duckdb
        
        # Test connection with default context first
        print("Testing connection to default MotherDuck context...")
        os.environ.setdefault("MOTHERDUCK_TOKEN", token)
        con_default = duckdb.connect("md:", read_only=True)
        print("✓ Successfully connected to default MotherDuck context")
        con_default.close()
        
        # If database name is specified, test that
        if db_name and db_name != "NOT SET":
            connect_str = f"md:{db_name}"
            print(f"\nTesting connection to specific database: {connect_str}")
            try:
                con_named = duckdb.connect(connect_str, read_only=True)
                print(f"✓ Successfully connected to database '{db_name}'")
                con_named.close()
            except Exception as e:
                print(f"✗ Failed to connect to database '{db_name}'")
                print(f"  Error: {e}")
                print(f"\n  Options:")
                print(f"  1. Create the database '{db_name}' in MotherDuck")
                print(f"  2. Remove MOTHERDUCK_DATABASE from .env to use default context")
                print(f"  3. Change DB_MODE to 'local' to use local DuckDB file")
        else:
            print("\n✓ No specific database name set - using default MotherDuck context")
            
    except ImportError:
        print("✗ duckdb module not installed")
        print("  Install with: pip install duckdb")
    except Exception as e:
        print(f"✗ Failed to connect to MotherDuck")
        print(f"  Error: {e}")
        print(f"\n  Possible issues:")
        print(f"  - Invalid MOTHERDUCK_TOKEN")
        print(f"  - Network connectivity issues")
        print(f"  - MotherDuck service unavailable")

def diagnose_local():
    """Diagnose local DuckDB connection."""
    print("\n=== Local DuckDB Connection Diagnostic ===\n")
    
    db_path = os.getenv("LOCAL_DUCKDB_PATH", "./data/app.duckdb")
    print(f"LOCAL_DUCKDB_PATH: {db_path}")
    
    try:
        import duckdb
        from pathlib import Path
        
        path = Path(db_path)
        if path.exists():
            print(f"✓ Database file exists: {path.resolve()}")
            # Try to open it
            con = duckdb.connect(db_path, read_only=True)
            print("✓ Successfully opened database file")
            con.close()
        else:
            print(f"⚠ Database file does not exist yet: {path.resolve()}")
            print("  It will be created automatically on first connection")
            
    except ImportError:
        print("✗ duckdb module not installed")
    except Exception as e:
        print(f"✗ Failed to access local database")
        print(f"  Error: {e}")

if __name__ == "__main__":
    diagnose_motherduck()
    diagnose_local()

