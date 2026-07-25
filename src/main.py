import os
import time
from src.config import INGEST_DIR
from src.dedupe.crypto import calculate_blake3
from src.storage.webdav import create_webdav_client, upload_file
from src.state.ledger import FileLedger
from prefect import flow, task
from prefect.cache_policies import NO_CACHE


@task(retries=2, retry_delay_seconds=5)
def task_hash_file(file_path: str) -> str:
    return calculate_blake3(file_path)

@task(retries=3, retry_delay_seconds=5, cache_policy=NO_CACHE)
def task_upload_file(client, local_path: str, remote_path: str):
    upload_file(client, local_path, remote_path)

@flow(name="Agentic-NAS-Pipeline", log_prints=True)
def run_pipeline():
    print(f"Starting SRE Pipeline on directory: {INGEST_DIR}")
    
    if not os.path.exists(INGEST_DIR):
        print(f"ERROR: {INGEST_DIR} not found. Check TrueNAS volume mounts.")
        return

    # Dependency Injection
    webdav_client = create_webdav_client()
    
    # 2. Instantiate the Persistent SQLite Ledger (Replaces the ephemeral set)
    ledger = FileLedger(db_path="data/ledger.db")
    print("SCD2 Ledger successfully connected.")

    stats = {"scanned": 0, "uploaded": 0, "duplicates": 0, "modifications": 0, "errors": 0, "bytes_uploaded": 0}
    remote_base_dir = "/Documents/GDriveIngestionTest"

    print(f"Scanning Ingest Directory: {INGEST_DIR}")
    print("="*50)

    start_time = time.time()
    for root, _, files in os.walk(INGEST_DIR):
        for file in files:
            local_path = os.path.join(root, file)
            file_size = os.path.getsize(local_path)
            stats["scanned"] += 1
            
            relative_path = os.path.relpath(local_path, INGEST_DIR)
            remote_path = f"{remote_base_dir}/{relative_path}".replace("\\", "/")
            
            print(f"\n📄 Testing File: {relative_path} ({(file_size / 1024 / 1024):.2f} MB)")
            
            # --- TEST 1: Cryptographic Hashing ---
            try:
                file_hash = task_hash_file(local_path)
                
                # 3. Consult the Persistent Ledger
                evaluation = ledger.evaluate_file(cloud_path=relative_path, file_hash=file_hash)
                status = evaluation["status"]
                print(f"   [Ledger] Status: {status} | {evaluation['msg']}")
                
                if status == "EXACT_MATCH":
                    print("   [Action] Ignoring. Already synced.")
                    continue
                    
                elif status == "DUPLICATE_PATH":
                    print("   [Action] 🛑 DENIED. File is a duplicate copy. Skipping upload.")
                    stats["duplicates"] += 1
                    continue
                    
            except Exception as e:
                print(f"   [Error] Hashing failed: {e}")
                stats["errors"] += 1
                continue 

            # --- TEST 2: WebDAV Upload ---
            if status in ["NEW", "MODIFIED"]:
                try:
                    task_upload_file(webdav_client, local_path, remote_path)
                    
                    # 4. Commit the transaction to the SQLite Ledger
                    ledger.record_transaction(
                        cloud_path=relative_path, 
                        file_hash=file_hash, 
                        nextcloud_path=remote_path, 
                        status=status
                    )
                    
                    if status == "NEW":
                        stats["uploaded"] += 1
                    else:
                        stats["modifications"] += 1
                        
                    stats["bytes_uploaded"] += file_size
                    
                except Exception as e:
                    print(f"   [Error] Upload failed: {e}")
                    stats["errors"] += 1

    # Print SRE Telemetry Summary
    end_time = time.time()
    duration = end_time - start_time
    mb_uploaded = stats["bytes_uploaded"] / (1024 * 1024)

    print("\n" + "="*50)
    print("📊 PIPELINE EXECUTION TELEMETRY")
    print("="*50)
    print(f"⏱️  Total Time:       {duration:.2f} seconds")
    print(f"📁 Files Scanned:    {stats['scanned']}")
    print(f"✅ Files Uploaded:   {stats['uploaded']} ({mb_uploaded:.2f} MB)")
    print(f"🔄 Files Updated:    {stats['modifications']}")
    print(f"🛑 Duplicates Saved: {stats['duplicates']}")
    print(f"⚠️  Errors:           {stats['errors']}")
    print("="*50)

if __name__ == "__main__":
    run_pipeline()

    # For nightly GitOps schedule:
    run_pipeline.serve(
        name="daily-dedupe-job",
        cron="0 2 * * *",
        tags=["production", "nas"],
        description="Pulls from Google Drive and executes WebDAV deduplication."
    )