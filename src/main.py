import os
from prefect import flow, task
from src.config import INGEST_DIR
from src.dedupe.crypto import calculate_blake3
from src.storage.webdav import upload_file

# In-memory database for sandbox testing
processed_hashes = set()

@task(retries=2, retry_delay_seconds=5)
def task_hash_file(file_path: str) -> str:
    return calculate_blake3(file_path)

@task(retries=3, retry_delay_seconds=5)
def task_upload_file(local_path: str, remote_path: str):
    upload_file(local_path, remote_path)

@flow(name="Agentic-NAS-Pipeline", log_prints=True)
def run_pipeline():
    print(f"Starting SRE Pipeline on directory: {INGEST_DIR}")
    
    if not os.path.exists(INGEST_DIR):
        print(f"ERROR: {INGEST_DIR} not found. Check TrueNAS volume mounts.")
        return

    for root, _, files in os.walk(INGEST_DIR):
        for file in files:
            local_path = os.path.join(root, file)
            print(f"\nProcessing: {file}")
            
            # 1. Dedupe
            file_hash = task_hash_file(local_path)
            if file_hash in processed_hashes:
                print(f"DUPLICATE DETECTED: '{file}'. Skipping.")
                continue 
                
            # 2. Route & Upload
            remote_path = f"/Auto_Organized/{file}"
            
            try:
                task_upload_file(local_path, remote_path)
                processed_hashes.add(file_hash)
            except Exception as e:
                print(f"FAILED to upload {file}: {e}")

if __name__ == "__main__":
    # Run the pipeline immediately for testing
    run_pipeline()