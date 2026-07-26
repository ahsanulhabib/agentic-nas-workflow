import os
import hashlib
import sqlite3
from pathlib import Path

def calculate_sha256(filepath: str) -> str:
    """High-speed cryptographic hashing."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def scan_sources(db_path: Path, sources: dict[str, str]):
    """
    Phase 1: Scans raw cloud folders and populates isolated staging tables.
    sources = {"gdrive": "/cloud_ingest/gdrive", "onedrive": "/cloud_ingest/onedrive"}
    """
    conn = sqlite3.connect(db_path)
    
    for source_name, source_path in sources.items():
        print(f"🔍 Scanning source: {source_name} at {source_path}...")
        if not os.path.exists(source_path):
            print(f"   [Warning] Path {source_path} not found. Skipping.")
            continue
            
        safe_source = source_name.replace(" ", "_").replace("-", "_").lower()
        table_name = f"staging_{safe_source}"
        
        scanned_count = 0
        for root, _, files in os.walk(source_path):
            for file in files:
                filepath = os.path.join(root, file)
                file_hash = calculate_sha256(filepath)
                mtime = os.path.getmtime(filepath)
                size = os.path.getsize(filepath)
                
                # SRE Idempotency: Upsert the record. If it exists, update the hash/mtime.
                conn.execute(f"""
                    INSERT INTO {table_name} (original_path, filename, file_size, sha256_hash, mtime, status)
                    VALUES (?, ?, ?, ?, ?, 'pending')
                    ON CONFLICT(original_path) 
                    DO UPDATE SET 
                        sha256_hash=excluded.sha256_hash, 
                        mtime=excluded.mtime, 
                        file_size=excluded.file_size,
                        status='pending'
                """, (filepath, file, size, file_hash, mtime))
                scanned_count += 1
                
        print(f"   ✅ {source_name}: {scanned_count} files staged.")
        
    conn.commit()
    conn.close()