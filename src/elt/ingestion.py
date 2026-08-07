#!/usr/bin/env python3
import os
import shutil
import sqlite3
from pathlib import Path

import docker

from src.elt.strategy import FileRoute

CONTAINER_UID = int(os.getenv("PUID", "33"))
CONTAINER_GID = int(os.getenv("PGID", "33"))

def execute_ingestion(db_path: Path, nextcloud_mount: Path, routings: list[FileRoute]):
    """
    Phase 3: Physically copies files and defensively sets ownership to www-data.
    """
    conn = sqlite3.connect(db_path, timeout=20.0)
    conn.row_factory = sqlite3.Row
    
    success_count, duplicate_count, error_count = 0, 0, 0
    
    for route in routings:
        table_name = route.source_table
        if not table_name.startswith("staging_"):
            table_name = f"staging_{table_name}"
            
        cursor = conn.execute(
            f"SELECT original_path, blake3_hash, file_size FROM {table_name} WHERE id = ?", 
            (route.staging_id,)
        )
        record = cursor.fetchone()
        
        if not record: continue
            
        local_path = Path(record["original_path"])
        remote_path = route.proposed_path.lstrip("/") 
        target_zfs_path = nextcloud_mount / "admin" / "files" / remote_path
        file_hash = record["blake3_hash"]

        
        print(f"🚀 Ingesting: {os.path.basename(local_path)} -> /{remote_path}")

        existing_prod = conn.execute(
            "SELECT 1 FROM production_inventory WHERE blake3_hash = ?", 
            (file_hash,)
        ).fetchone()

        if existing_prod or target_zfs_path.exists():
            print("   [Dedupe] 🛑 File or Hash already exists in production. Skipping copy.")
            conn.execute(f"UPDATE {table_name} SET status = 'duplicate' WHERE id = ?", (route.staging_id,))
            duplicate_count += 1
            continue
        
        try:
            # 1. Create directory (This will now succeed without sudo)
            target_zfs_path.parent.mkdir(parents=True, exist_ok=True)

            # 2. Physically copy the file
            shutil.copy(local_path, target_zfs_path)

            # 3. Update Production Inventory
            conn.execute("""
                INSERT INTO production_inventory (blake3_hash, nextcloud_path, file_size)
                VALUES (?, ?, ?)
            """, (record["blake3_hash"], f"/{remote_path}", record["file_size"]))
            
            # 4. Mark Staging as Ingested
            conn.execute(f"UPDATE {table_name} SET status = 'ingested' WHERE id = ?", (route.staging_id,))
            
            success_count += 1
            
        except sqlite3.IntegrityError:
            conn.execute(f"UPDATE {table_name} SET status = 'duplicate' WHERE id = ?", (route.staging_id,))
            duplicate_count += 1
        except Exception as e:  # noqa: BLE001
            print(f"   [Error] Failed to ingest {local_path}: {e}")
            conn.execute(f"UPDATE {table_name} SET status = 'error' WHERE id = ?", (route.staging_id,))
            error_count += 1
            
    conn.commit()
    conn.close()
    
    print("\n" + "="*50)
    print(f"✅ Ingestion Complete | Success: {success_count} | Duplicate: {duplicate_count} | Errors: {error_count}")
    print("="*50)

def trigger_nextcloud_occ_scan(container_name: str = "ix-nextcloud-nextcloud-1") -> bool:
    """Zero-Trust OCC Scan via Restricted Socket Proxy."""
    try:
        # Connect to the Proxy on Port 2375 instead of the Unix file!
        client = docker.DockerClient(base_url='http://192.168.1.55:2375')
        container = client.containers.get(container_name)
        
        container.exec_run(
            cmd="/usr/local/bin/php /var/www/html/occ files:scan --all",
            user="33"
        )
        print("✅ Nextcloud OCC Scan completed via Zero-Trust Proxy!")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"❌ Proxy request denied or failed: {e}")
        return False