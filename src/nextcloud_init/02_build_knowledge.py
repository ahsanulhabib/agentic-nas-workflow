import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

from src.configs import load_settings, root_path
from src.pipeline.knowledge import run_knowledge_pipeline


def main():
    print("="*60)
    print("🧠 NEXTCLOUD INIT STEP 2: INITIAL KNOWLEDGE SUBSTRATE BUILD")
    print("="*60)

    settings = load_settings()
    db_path = root_path(settings["paths"]["ledger_db"])
    nextcloud_mount = Path("/nextcloud_data")

    # Run full Phase 4 pipeline
    run_knowledge_pipeline(db_path, nextcloud_mount)

    print("\n" + "="*60)
    print("🎉 Day 0 Knowledge Substrate Complete.")
    print("   Parquet, OKF, Jena RDF, and Qdrant Vectors are fully initialized.")
    print("="*60)

if __name__ == "__main__":
    main()