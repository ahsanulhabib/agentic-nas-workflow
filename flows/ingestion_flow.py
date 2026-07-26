import os
import time
from prefect import flow, task
from prefect.cache_policies import NO_CACHE
from src.dedupe.crypto import calculate_blake3
from src.storage.webdav import create_webdav_client, upload_file

@task(retries=2, retry_delay_seconds=5)
def task_hash_file(file_path: str) -> str:
    return calculate_blake3(file_path)

@task(retries=3, retry_delay_seconds=5, cache_policy=NO_CACHE)
def task_upload_file(client, local_path: str, remote_path: str):
    upload_file(client, local_path, remote_path)

@flow(name="Agentic-NAS-Ingestion-Pipeline", log_prints=True)
def run_ingestion(ingest_dir: str = "/cloud_ingest/gdrive_ahabib9387", remote_base_dir: str = "/Auto_Organized"):
    print(f"Starting Active Ingestion from: {ingest_dir}")
    
    if not os.path.exists(ingest_dir):
        print(f"ERROR: {ingest_dir} not found.")
        return

    webdav_client = create_webdav_client()
    processed_hashes = set()
    stats = {"scanned": 0, "uploaded": 0, "duplicates": 0, "errors": 0}

    for root, _, files in os.walk(ingest_dir):
        for file in files:
            local_path = os.path.join(root, file)
            stats["scanned"] += 1
            
            relative_path = os.path.relpath(local_path, ingest_dir)
            remote_path = f"{remote_base_dir}/{relative_path}".replace("\\", "/")
            
            print(f"\n📄 Processing: {relative_path}")
            
            try:
                file_hash = task_hash_file(local_path)
                if file_hash in processed_hashes:
                    print("   [Dedupe] 🛑 EXACT DUPLICATE DETECTED. Skipping.")
                    stats["duplicates"] += 1
                    continue
            except Exception as e:
                print(f"   [Error] Hashing failed: {e}")
                stats["errors"] += 1
                continue 

            try:
                task_upload_file(webdav_client, local_path, remote_path)
                processed_hashes.add(file_hash)
                stats["uploaded"] += 1
            except Exception as e:
                print(f"   [Error] Upload failed: {e}")
                stats["errors"] += 1

    print("\n" + "="*50)
    print(f"✅ Uploaded: {stats['uploaded']} | 🛑 Duplicates: {stats['duplicates']} | ⚠️ Errors: {stats['errors']}")
    print("="*50)

if __name__ == "__main__":
    run_ingestion()