#!/usr/bin/env python3
"""
Migrate data from DuckDB to PostgreSQL.

Usage:
    python scripts/migrate_duckdb_to_postgres.py [--duckdb-path PATH] [--dry-run]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import duckdb
from src.db.connection_postgres import get_pooled_connection


def migrate(duckdb_path: str = "./data/app.duckdb", dry_run: bool = False):
    """Migrate warriors from DuckDB to PostgreSQL."""
    
    print(f"{'[DRY RUN] ' if dry_run else ''}Starting migration...")
    print(f"Source: {duckdb_path}")
    
    # Check if DuckDB file exists
    if not Path(duckdb_path).exists():
        print(f"Error: DuckDB file not found at {duckdb_path}")
        return False
    
    # Read from DuckDB
    print(f"\n1. Reading warriors from DuckDB...")
    try:
        duck_con = duckdb.connect(duckdb_path, read_only=True)
        warriors = duck_con.execute("""
            SELECT 
                CAST(id AS TEXT) as id,
                name,
                strftime(dob, '%Y-%m-%d') as dob,
                fight_skills
            FROM warrior
            ORDER BY name
        """).fetchall()
        duck_con.close()
        
        print(f"   ✓ Found {len(warriors)} warriors in DuckDB")
        
        if len(warriors) == 0:
            print("   No warriors to migrate.")
            return True
            
    except Exception as e:
        print(f"   ✗ Error reading from DuckDB: {e}")
        return False
    
    # Display sample
    if warriors:
        print(f"\n2. Sample data (first 3):")
        for i, warrior in enumerate(warriors[:3], 1):
            print(f"   {i}. {warrior[1]} (ID: {warrior[0][:8]}..., DOB: {warrior[2]}, Skills: {warrior[3]})")
    
    if dry_run:
        print(f"\n[DRY RUN] Would migrate {len(warriors)} warriors to PostgreSQL")
        return True
    
    # Write to PostgreSQL
    print(f"\n3. Writing to PostgreSQL...")
    try:
        with get_pooled_connection() as pg_con:
            with pg_con.cursor() as cur:
                inserted = 0
                skipped = 0
                
                for warrior in warriors:
                    try:
                        cur.execute("""
                            INSERT INTO warrior (id, name, dob, fight_skills)
                            VALUES (%s::UUID, %s, %s::DATE, %s)
                            ON CONFLICT (id) DO NOTHING
                        """, warrior)
                        
                        if cur.rowcount > 0:
                            inserted += 1
                        else:
                            skipped += 1
                            
                    except Exception as e:
                        print(f"   Warning: Failed to insert warrior {warrior[0]}: {e}")
                        skipped += 1
            
            # Connection context manager will auto-commit
        
        print(f"   ✓ Inserted: {inserted}")
        print(f"   ⊘ Skipped (duplicates): {skipped}")
        print(f"\n✅ Migration complete!")
        return True
        
    except Exception as e:
        print(f"   ✗ Error writing to PostgreSQL: {e}")
        print(f"\nMake sure:")
        print(f"  1. PostgreSQL is running (docker-compose up -d)")
        print(f"  2. Schema is initialized (psql < schema_postgresql.sql)")
        print(f"  3. Environment variables are set (POSTGRES_* in .env)")
        return False


def verify(duckdb_path: str = "./data/app.duckdb"):
    """Verify migration by comparing counts."""
    
    print("\nVerifying migration...")
    
    try:
        # Count in DuckDB
        duck_con = duckdb.connect(duckdb_path, read_only=True)
        duck_count = duck_con.execute("SELECT COUNT(*) FROM warrior").fetchone()[0]
        duck_con.close()
        
        # Count in PostgreSQL
        with get_pooled_connection() as pg_con:
            with pg_con.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM warrior")
                pg_count = cur.fetchone()[0]
        
        print(f"  DuckDB count: {duck_count}")
        print(f"  PostgreSQL count: {pg_count}")
        
        if duck_count == pg_count:
            print(f"  ✓ Counts match!")
            return True
        else:
            print(f"  ⚠ Counts differ by {abs(duck_count - pg_count)}")
            return False
            
    except Exception as e:
        print(f"  ✗ Verification failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Migrate warriors from DuckDB to PostgreSQL"
    )
    parser.add_argument(
        "--duckdb-path",
        default="./data/app.duckdb",
        help="Path to DuckDB file (default: ./data/app.duckdb)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually migrating",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify migration by comparing counts",
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("DuckDB → PostgreSQL Migration Tool")
    print("=" * 80)
    
    if args.verify:
        success = verify(args.duckdb_path)
    else:
        success = migrate(args.duckdb_path, args.dry_run)
    
    print("=" * 80)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

