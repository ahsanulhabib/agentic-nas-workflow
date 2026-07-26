import sqlite3
from pathlib import Path

def init_schema(db_path: Path, sources: list[str]):
    """
    Initializes the ELT Database Schema.
    Dynamically creates isolated staging tables for each cloud source.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute('pragma journal_mode=wal')
    cursor = conn.cursor()

    # 1. Create the Production Inventory (The Source of Truth)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS production_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sha256_hash TEXT NOT NULL UNIQUE,
            nextcloud_path TEXT NOT NULL,
            file_size INTEGER,
            ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            kg_indexed BOOLEAN DEFAULT 0,
            vector_indexed BOOLEAN DEFAULT 0
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_hash ON production_inventory(sha256_hash)")

    # 2. Dynamically Create Isolated Staging Tables
    for source in sources:
        # Sanitize table name (e.g., 'Google Drive' -> 'staging_google_drive')
        safe_source = source.replace(" ", "_").replace("-", "_").lower()
        table_name = f"staging_{safe_source}"
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_path TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                file_size INTEGER,
                sha256_hash TEXT NOT NULL,
                mtime DATETIME,
                scanned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending' -- pending, ingested, duplicate, error
            )
        """)
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_hash ON {table_name}(sha256_hash)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_status ON {table_name}(status)")

    conn.commit()
    conn.close()
    print(f"Schema initialized. Staging tables created for: {sources}")

def get_unified_staging_view(db_path: Path, sources: list[str]) -> list[dict]:
    """
    SRE MAGIC: Cross-Table Deduplication Query.
    Unions all dynamic staging tables and filters out hashes that already exist in Production.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Build a UNION ALL query dynamically based on active sources
    union_queries = []
    for source in sources:
        safe_source = source.replace(" ", "_").replace("-", "_").lower()
        table_name = f"staging_{safe_source}"
        
        # Check if table exists (in case it was added after init)
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone()
        
        if table_exists:
            union_queries.append(f"""
                SELECT '{safe_source}' as source_table, id, original_path, filename, file_size, sha256_hash, mtime 
                FROM {table_name} 
                WHERE status = 'pending'
            """)
            
    if not union_queries:
        return []

    full_query = f"""
        WITH unified_staging AS (
            {' UNION ALL '.join(union_queries)}
        )
        SELECT MIN(id) as staging_id, source_table, original_path, filename, file_size, sha256_hash
        FROM unified_staging
        WHERE sha256_hash NOT IN (SELECT sha256_hash FROM production_inventory)
        GROUP BY sha256_hash
    """
    
    results = [dict(row) for row in conn.execute(full_query).fetchall()]
    conn.close()
    return results