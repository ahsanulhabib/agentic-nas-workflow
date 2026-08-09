import sys
from pathlib import Path

from prefect import flow, task

# Resolve project root (one level up from flows/)
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

from src.config import load_settings, root_path

from src.pipeline.knowledge import run_knowledge_pipeline


@task(name="Rebuild-Knowledge-Substrate-Task", retries=2)
def task_refresh_knowledge(db_path: Path, nextcloud_mount: Path):
    """Prefect Task wrapper to execute Phase 4 Knowledge Substrate Build."""
    return run_knowledge_pipeline(db_path, nextcloud_mount)

@flow(name="Knowledge-Refresh-Flow", log_prints=True)
def knowledge_refresh_workflow():
    """
    Standalone / On-Demand Prefect Flow:
    Rebuilds Parquet analytics, OKF Markdown Wiki, Apache Jena RDF Graph,
    and Qdrant Multimodal Vectors directly from production_inventory.
    
    Does NOT execute cloud scanning or physical file ingestion.
    """
    print("="*60)
    print("🧠 INITIATING ON-DEMAND KNOWLEDGE SUBSTRATE REFRESH")
    print("="*60)

    settings = load_settings()
    db_path = root_path(settings["paths"]["ledger_db"])
    nextcloud_mount = Path("/nextcloud_data")
    result = task_refresh_knowledge(db_path, nextcloud_mount)
    
    print("\n" + "="*60)
    print("✅ Knowledge Substrate successfully refreshed across OKF, Jena, and Qdrant!")
    print("="*60)
    
    return result

if __name__ == "__main__":
    knowledge_refresh_workflow()