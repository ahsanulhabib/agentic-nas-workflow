import os
from prefect import flow, task
from src.config import INGEST_DIR
from src.dedupe.crypto import calculate_blake3
from src.storage.webdav import create_webdav_client, upload_file

processed_hashes = set()

@task(retries=2, retry_delay_seconds=5)
def task_hash_file(file_path: str) -> str:
    return calculate_blake3(file_path)

# 1. Update the task to accept the client dependency
@task(retries=3, retry_delay_seconds=5)
def task_upload_file(client, local_path: str, remote_path: str):
    upload_file(client, local_path, remote_path)

@flow(name="Agentic-NAS-Pipeline", log_prints=True)
def run_pipeline():
    print(f"Starting SRE Pipeline on directory: {INGEST_DIR}")
    
    if not os.path.exists(INGEST_DIR):
        print(f"ERROR: {INGEST_DIR} not found.")
        return

    # 2. Dependency Injection: Create the client ONCE per flow run
    webdav_client = create_webdav_client()

    for root, _, files in os.walk(INGEST_DIR):
        for file in files:
            local_path = os.path.join(root, file)
            print(f"\nProcessing: {file}")
            
            file_hash = task_hash_file(local_path)
            if file_hash in processed_hashes:
                print(f"DUPLICATE DETECTED: '{file}'. Skipping.")
                continue 
                
            remote_path = f"/Auto_Organized/{file}"
            
            try:
                # 3. Inject the client into the upload task
                task_upload_file(webdav_client, local_path, remote_path)
                processed_hashes.add(file_hash)
            except Exception as e:
                print(f"FAILED to upload {file}: {e}")

if __name__ == "__main__":
    run_pipeline()