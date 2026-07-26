import os
from pathlib import Path
from prefect import flow, task
from openai import OpenAI
from webdav4.client import Client
from prefect.blocks.system import Secret

from src.config import load_settings, root_path
from src.pipeline.ingestion import run_ingestion_pipeline
from src.pipeline.knowledge import run_knowledge_pipeline
from src.pipeline.recovery import run_snapshot_audit

@task
def task_ingest(db_path, nc_mount, sources, llm, webdav, model):
    return run_ingestion_pipeline(db_path, nc_mount, sources, llm, webdav, model)

@task
def task_knowledge(db_path, nc_mount):
    return run_knowledge_pipeline(db_path, nc_mount)

@task
def task_audit(snapshot_dir):
    return run_snapshot_audit(snapshot_dir)

@flow(name="Agentic-NAS-Pipeline", log_prints=True)
def main_workflow():
    settings = load_settings()
    db_path = root_path(settings["paths"]["ledger_db"])
    snapshot_dir = root_path(settings["paths"]["snapshots"])
    nextcloud_mount = Path("/mnt/Tank/Nextcloud_Data")
    
    cloud_sources = {
        "Google Drive": "/cloud_ingest/gdrive_ahabib9387",
        "OneDrive": "/cloud_ingest/onedrive"
    }
    
    # Init Clients
    nc_user = Secret.load("nextcloud-username").get()
    nc_pass = Secret.load("nextcloud-password").get()
    webdav_client = Client(os.getenv("NEXTCLOUD_URL", "http://192.168.1.55:30027/remote.php/webdav"), auth=(nc_user, nc_pass))
    
    llm_key = Secret.load("nas-gemini-api-key").get()
    llm_client = OpenAI(api_key=llm_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    
    # 1. ELT Ingestion
    ingest_result = task_ingest(db_path, nextcloud_mount, cloud_sources, llm_client, webdav_client, settings["llm"]["model"])
    
    # 2. Conditional Knowledge Substrate
    if ingest_result.get("ingested", 0) > 0:
        print("New files detected! Rebuilding Knowledge Graph...")
        task_knowledge(db_path, nextcloud_mount, wait_for=[ingest_result])
    else:
        print("No new files ingested. Skipping Knowledge Graph rebuild to save compute.")
        
    # 3. SRE Audit
    task_audit(snapshot_dir)

if __name__ == "__main__":
    main_workflow()