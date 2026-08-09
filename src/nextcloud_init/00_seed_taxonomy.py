import sqlite3
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

from src.configs import load_settings, root_path
from src.okf.builder import OKFBuilder
from src.state.schema import init_v5_schema


def main():
    print("="*60)
    print("🌱 NEXTCLOUD INIT STEP 0: INITIAL TAXONOMY & CACHE SEEDING")
    print("="*60)
    
    settings = load_settings()
    db_path = root_path(settings["paths"]["ledger_db"])
    okf_dir = root_path(settings["paths"]["okf"])
    cloud_sources = settings["ingestion"]["cloud_sources"]

    # 1. Initialize Schema
    init_v5_schema(db_path, list(cloud_sources.keys()))

    # 2. Seed taxonomy_cache from existing cloud folder structures
    conn = sqlite3.connect(db_path)
    seeded_count = 0
    
    print("\n🔍 Seeding taxonomy_cache from cloud directories...")
    for source_name, source_path_raw in cloud_sources.values():
        source_path = Path(source_path_raw)
        if not source_path.exists():
            continue
            
        for path_obj in source_path.rglob("*"):
            if path_obj.is_dir():
                parent_dir = str(path_obj)
                # Map source parent path to clean Nextcloud destination path
                rel_dir = "/" + str(path_obj.relative_to(source_path.parent)).replace("\\", "/")
                
                conn.execute("""
                    INSERT INTO taxonomy_cache (source_parent_path, target_folder)
                    VALUES (?, ?)
                    ON CONFLICT(source_parent_path) DO NOTHING
                """, (parent_dir, rel_dir))
                seeded_count += 1

    conn.commit()
    conn.close()
    print(f"   ✅ Seeded {seeded_count} directory patterns into taxonomy_cache.")

    # 3. Build Initial OKF Wiki
    print("\n📚 Generating Initial OKF Knowledge Base...")
    OKFBuilder(db_path, okf_dir).build()

    print("\n" + "="*60)
    print("🎉 Taxonomy Seeding Complete.")
    print("="*60)

if __name__ == "__main__":
    main()