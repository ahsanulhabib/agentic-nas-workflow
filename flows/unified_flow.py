#!/usr/bin/env python3
import os
from pathlib import Path

from openai import OpenAI
from prefect import flow, task
from prefect.blocks.system import Secret
from src.config import load_settings, root_path
from webdav4.client import Client

from src.pipeline.ingestion import run_ingestion_pipeline
from src.pipeline.knowledge import run_knowledge_pipeline
from src.pipeline.recovery import run_snapshot_audit
from src.state.schema import init_schema, reconcile_deletions


@task
def task_ingest(db_path, nc_mount, sources, llm, webdav, model):
    return run_ingestion_pipeline(db_path, nc_mount, sources, llm, webdav, model)

@task
def task_knowledge(db_path, nc_mount):
    return run_knowledge_pipeline(db_path, nc_mount)

@task
def task_audit(snapshot_dir):
    return run_snapshot_audit(snapshot_dir)

@task
def task_reconcile(prod_db: Path, nc_ledger: Path):
    return reconcile_deletions(prod_db, nc_ledger)

@flow(name="Agentic-NAS-Pipeline", log_prints=True)
async def main_workflow():
    settings = load_settings()
    
    # 1. Load Paths from YAML
    db_path = root_path(settings["paths"]["ledger_db"])
    snapshot_dir = root_path(settings["paths"]["snapshots"])
    nextcloud_mount = Path("/mnt/spool/nextcloud_data")
    nextcloud_ledger_path = Path("/mnt/spool/nextcloud_data/nextcloud.db")
    
    # 2. Load Ingestion Sources from YAML
    cloud_sources = settings["ingestion"]["cloud_sources"]
    
    # 3. Load Nextcloud Auth from Prefect Vault (Using your new YAML structure!)
    print("🔐 Fetching Nextcloud Identity from Vault...")
    nc_user = await Secret.load(settings["nextcloud"]["secret_blocks"]["username"]).get()
    nc_pass = await Secret.load(settings["nextcloud"]["secret_blocks"]["password"]).get()
    webdav_client = Client(settings["nextcloud"]["url"], auth=(nc_user, nc_pass))
    
    # 4. Load LLM Auth
    print("🔐 Fetching LLM API Key from Vault...")
    llm_key = await Secret.load(settings["llm"]["secret_blocks"]["gemini_api_key"]).get()
    llm_client = OpenAI(api_key=llm_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    
    # --- EXECUTE PIPELINE ---
    task_reconcile(db_path, nextcloud_ledger_path)
    ingest_result = task_ingest(
        db_path=db_path, 
        nc_mount=nextcloud_mount, 
        sources=cloud_sources, 
        llm=llm_client, 
        webdav=webdav_client, 
        model=settings["llm"]["model"]
    )
    
    # Conditional Knowledge Substrate Build
    if ingest_result.get("ingested", 0) > 0:
        task_knowledge(db_path, nextcloud_mount, wait_for=[ingest_result])
    else:
        print("⏭️ No new files ingested. Skipping Knowledge Graph rebuild.")
        
    # SRE Audit
    task_audit(snapshot_dir, wait_for=[task_knowledge])

if __name__ == "__main__":
    main_workflow()