#!/usr/bin/env python3
import hashlib
import os
import sqlite3
from pathlib import Path

import blake3


def calculate_sha256(filepath: str) -> str:
    """High-speed cryptographic hashing."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()

def calculate_blake3(filepath: str) -> str:
    """High-speed BLAKE3 cryptographic hashing."""
    blake3_hash = blake3.blake3()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            blake3_hash.update(chunk)
    return blake3_hash.hexdigest()

def scan_sources(db_path: Path, sources: dict[str, str | Path]):
    """Phase 1: Scans cloud folders using pathlib.Path.rglob() and populates staging."""
    conn = sqlite3.connect(db_path)
    
    for source_name, source_path_raw in sources.items():
        source_path = Path(source_path_raw)
        print(f"🔍 Scanning source: {source_name} at {source_path}...")
        
        if not source_path.exists():
            print(f"   [Warning] Path {source_path} not found. Skipping.")
            continue
            
        safe_source = source_name.replace(" ", "_").replace("-", "_").lower()
        table_name = f"staging_{safe_source}"
        
        scanned_count = 0

        for file_path in source_path.rglob("*"):
            if file_path.is_file():
                file_hash = calculate_blake3(file_path)
                stat = file_path.stat()
                mtime = stat.st_mtime
                size = stat.st_size

                if size == 0:
                    conn.execute(f"""
                        INSERT INTO {table_name} (original_path, filename, file_size, blake3_hash, mtime, status)
                        VALUES (?, ?, 0, 'ZERO_BYTE_FILE', ?, 'zero_byte')
                        ON CONFLICT(original_path) DO NOTHING
                    """, (str(file_path), file_path.name, stat.st_mtime))
                    continue
                
                conn.execute(f"""
                    INSERT INTO {table_name} (original_path, filename, file_size, blake3_hash, mtime, status)
                    VALUES (?, ?, ?, ?, ?, 'pending')
                    ON CONFLICT(original_path) 
                    DO UPDATE SET 
                        blake3_hash=excluded.blake3_hash, 
                        mtime=excluded.mtime, 
                        file_size=excluded.file_size,
                        status='pending'
                """, (str(file_path), file_path.name, size, file_hash, mtime))
                scanned_count += 1
                
        print(f"   ✅ {source_name}: {scanned_count} files staged.")
        
    conn.commit()
    conn.close()