import os
import shutil
import sqlite3
from pathlib import Path
from src.elt.strategy import FileRoute

def execute_ingestion(db_path: Path, nextcloud_mount: Path, routings: list[FileRoute]):
    """
    Phase 3: Physically copies files to the Nextcloud ZFS dataset and updates the ledger.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    success_count = 0
    error_count = 0
    
    for route in routings:
        # Fetch the physical path and hash from the specific staging table
        cursor = conn.execute(
            f"SELECT original_path, sha256_hash, file_size FROM {route.source_table} WHERE id = ?", 
            (route.staging_id,)
        )
        record = cursor.fetchone()
        
        if not record:
            continue
            
        local_path = record["original_path"]
        remote_path = route.proposed_path.lstrip("/") # Remove leading slash for safe joining
        
        # Calculate the absolute ZFS path for Nextcloud
        # Assuming Nextcloud structure: /mnt/Tank/Nextcloud_Data/admin/files/...
        target_zfs_path = nextcloud_mount / "admin" / "files" / remote_path
        
        print(f"🚀 Ingesting: {os.path.basename(local_path)} -> /{remote_path}")
        
        try:
            # 1. ZFS Physical Operation: Ensure folders exist and COPY the file
            target_zfs_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local_path, target_zfs_path)
            
            # 2. Update Production Inventory (Source of Truth)
            conn.execute("""
                INSERT INTO production_inventory (sha256_hash, nextcloud_path, file_size)
                VALUES (?, ?, ?)
            """, (record["sha256_hash"], f"/{remote_path}", record["file_size"]))
            
            # 3. Mark Staging as Ingested
            conn.execute(
                f"UPDATE {route.source_table} SET status = 'ingested' WHERE id = ?", 
                (route.staging_id,)
            )
            
            success_count += 1
            
        except sqlite3.IntegrityError:
            print(f"   [Skip] Hash {record['sha256_hash']} already exists in production.")
            conn.execute(f"UPDATE {route.source_table} SET status = 'duplicate' WHERE id = ?", (route.staging_id,))
        except Exception as e:
            print(f"   [Error] Failed to ingest {local_path}: {e}")
            conn.execute(f"UPDATE {route.source_table} SET status = 'error' WHERE id = ?", (route.staging_id,))
            error_count += 1
            
    conn.commit()
    conn.close()
    
    print("\n" + "="*50)
    print(f"✅ Ingestion Complete | Success: {success_count} | Errors: {error_count}")
    print("="*50)
    
    # SRE CRITICAL WARNING FOR NEXTCLOUD:
    if success_count > 0:
        print("\n⚠️  ZFS Physical Moves Detected! ⚠️")
        print("To ensure Nextcloud sees these new files, you MUST run the OCC scanner on your TrueNAS host:")
        print("sudo docker exec -u www-data nextcloud php occ files:scan --all\n")