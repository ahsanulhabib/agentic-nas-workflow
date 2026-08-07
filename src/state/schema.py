#!/usr/bin/env python3
import os
import sqlite3
from pathlib import Path

from src.elt.scanner import calculate_blake3


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
            blake3_hash TEXT NOT NULL UNIQUE,
            nextcloud_path TEXT NOT NULL,
            file_size INTEGER,
            ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            kg_indexed BOOLEAN DEFAULT 0,
            vector_indexed BOOLEAN DEFAULT 0
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prod_hash ON production_inventory(blake3_hash)")

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
                blake3_hash TEXT NOT NULL,
                mtime DATETIME,
                scanned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending' -- pending, ingested, duplicate, error
            )
        """)
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_hash ON {table_name}(blake3_hash)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_status ON {table_name}(status)")

    # 3. Create the Taxonomy Cache Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS taxonomy_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_parent_path TEXT NOT NULL UNIQUE,
            target_folder TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            hit_count INTEGER DEFAULT 1
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_parent ON taxonomy_cache(source_parent_path)")

    conn.commit()
    conn.close()
    print(f"Schema initialized. Staging tables created for: {sources}")

def get_unified_staging_view(db_path: Path, sources: list[str]) -> list[dict]:
    """
    Cross-Table Deduplication Query.
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
                SELECT '{table_name}' as source_table, id, original_path, filename, file_size, blake3_hash, mtime 
                FROM {table_name} 
                WHERE status = 'pending'
            """)
            
    if not union_queries:
        return []

    full_query = f"""
        WITH unified_staging AS (
            {' UNION ALL '.join(union_queries)}
        )
        SELECT MIN(id) as staging_id, source_table, original_path, filename, file_size, blake3_hash
        FROM unified_staging
        WHERE blake3_hash NOT IN (SELECT blake3_hash FROM production_inventory)
        GROUP BY blake3_hash
    """
    
    results = [dict(row) for row in conn.execute(full_query).fetchall()]
    conn.close()
    return results

def reconcile_deletions(prod_db_path: Path, nextcloud_mount: Path) -> int:
    """
    Scans production_inventory and checks if the physical files still exist on ZFS.
    If a file was manually deleted from Nextcloud, its ghost record is purged.
    """
    print("🛡️  Starting Reconciliation Phase: Checking ZFS for manual deletions...")
    
    conn = sqlite3.connect(prod_db_path)
    conn.row_factory = sqlite3.Row
    
    # 1. Fetch all records our inventory thinks exist
    inventory = conn.execute("SELECT id, nextcloud_path FROM production_inventory").fetchall()
    ghost_count = 0
    
    for row in inventory:
        # Construct the physical ZFS path inside Code Server
        remote_path = row['nextcloud_path'].lstrip("/")
        zfs_path = nextcloud_mount / "admin" / "files" / remote_path
        
        # 2. Check physical existence on the hard drive
        if not zfs_path.exists():
            print(f"   🔥 Manual deletion detected! Purging ghost record: {row['nextcloud_path']}")
            # conn.execute("DELETE FROM production_inventory WHERE id = ?", (row['id'],))
            conn.execute("INSERT INTO pending_restorations (nextcloud_path, blake3_hash, status) VALUES (?, ?, 'pending_action') ON CONFLICT(nextcloud_path) DO NOTHING", (row['nextcloud_path'], row['blake3_hash']))
            ghost_count += 1
            ghost_count += 1
            
    conn.commit()
    conn.close()
    
    if ghost_count == 0:
        print("   ✅ No state drift detected. Physical ZFS dataset matches Inventory.")
    else:
        print(f"   🧹 Reconciliation Complete. Purged {ghost_count} ghost records from inventory.")
        
    return ghost_count

def sync_production_inventory_from_disk(db_path: Path, nextcloud_mount: Path) -> int:
    """
    Scans physical files on the ZFS mount and populates production_inventory
    so the database matches physical reality.
    """
    user_files_dir = nextcloud_mount / "admin" / "files"
    
    if not user_files_dir.exists():
        print(f"❌ Nextcloud files directory not found at {user_files_dir}")
        return 0
        
    print(f"🔍 Syncing production_inventory from physical disk: {user_files_dir}")

    IGNORE_DIRECTORIES = ["/templates", "/photos"]

    conn = sqlite3.connect(db_path)
    adopted_count = 0
    skipped_count = 0
    
    for file_path in user_files_dir.rglob("*"):
        if file_path.is_file():

            rel_path = "/" + str(file_path.relative_to(user_files_dir)).replace("\\", "/")
            if any(rel_path.lower().startswith(d) for d in IGNORE_DIRECTORIES):
                continue

            file_size = file_path.stat().st_size
            file_hash = calculate_blake3(file_path)
            
            try:
                conn.execute("""
                    INSERT INTO production_inventory (blake3_hash, nextcloud_path, file_size)
                    VALUES (?, ?, ?)
                """, (file_hash, rel_path, file_size))
                print(f"   [Adopted] {rel_path}")
                adopted_count += 1
            except sqlite3.IntegrityError:
                # Hash already exists in production_inventory
                skipped_count += 1
                
    conn.commit()
    conn.close()
    
    print("\n" + "="*50)
    print(f"✅ Sync Complete | Adopted: {adopted_count} files | Already in DB: {skipped_count}")
    print("="*50)
    
    return adopted_count

def restore_deleted_file_from_cloud_ingest(db_path: Path, nextcloud_path: str) -> bool:
    """
    Restores an accidentally deleted Nextcloud file by looking up its BLAKE3 hash 
    in staging tables and copying the original file back from /cloud_ingest/.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # 1. Get the hash of the deleted file
    record = conn.execute(
        "SELECT blake3_hash FROM pending_restorations WHERE nextcloud_path = ?", 
        (nextcloud_path,)
    ).fetchone()
    
    if not record:
        conn.close()
        return False
        
    file_hash = record["blake3_hash"]
    
    # 2. Find where the original file lives in /cloud_ingest across all staging tables
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'staging_%'").fetchall()]
    
    original_source_path = None
    for table in tables:
        match = conn.execute(f"SELECT original_path FROM {table} WHERE blake3_hash = ?", (file_hash,)).fetchone()
        if match:
            original_source_path = match["original_path"]
            break
            
    if not original_source_path or not os.path.exists(original_source_path):
        print("❌ Cannot restore: Original backup file not found in /cloud_ingest")
        conn.close()
        return False

    # 3. Copy file BACK from /cloud_ingest to Nextcloud
    target_zfs_path = Path("/nextcloud_data/admin/files") / nextcloud_path.lstrip("/")
    target_zfs_path.parent.mkdir(parents=True, exist_ok=True)
    
    import shutil
    shutil.copy(original_source_path, target_zfs_path)
    
    # 4. Re-insert into production_inventory and clear pending restoration
    file_size = os.path.getsize(target_zfs_path)
    conn.execute("INSERT OR REPLACE INTO production_inventory (blake3_hash, nextcloud_path, file_size) VALUES (?, ?, ?)",
                 (file_hash, nextcloud_path, file_size))
    conn.execute("UPDATE pending_restorations SET status = 'restored' WHERE nextcloud_path = ?", (nextcloud_path,))
    
    conn.commit()
    conn.close()
    
    # 5. Trigger Nextcloud OCC Scan
    from src.elt.ingestion import trigger_nextcloud_occ_scan
    trigger_nextcloud_occ_scan("ix-nextcloud-nextcloud-1")
    
    print(f"✅ RESTORATION SUCCESSFUL: {nextcloud_path} restored from {original_source_path}")
    return True