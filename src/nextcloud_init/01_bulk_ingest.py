import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.append(str(repo_root))

from openai import OpenAI
from prefect.blocks.system import Secret
from webdav4.client import Client

from src.configs import load_settings, root_path
from src.elt.ingestion import execute_ingestion, trigger_nextcloud_occ_scan
from src.elt.scanner import scan_sources
from src.elt.strategy import generate_strategy
from src.state.schema import init_schema


def main():
    print("="*60)
    print("🚀 NEXTCLOUD INIT STEP 1: MASS INITIAL BULK INGESTION")
    print("="*60)

    settings = load_settings()
    db_path = root_path(settings["paths"]["ledger_db"])
    nextcloud_mount = Path("/nextcloud_data")
    cloud_sources = settings["ingestion"]["cloud_sources"]

    # 1. Fetch Auth from Vault
    print("\n🔐 Authenticating with Prefect Vault...")
    llm_key = Secret.load(settings["llm"]["secret_blocks"]["gemini_api_key"]).get()
    nc_user = Secret.load(settings["nextcloud"]["secret_blocks"]["username"]).get()
    nc_pass = Secret.load(settings["nextcloud"]["secret_blocks"]["password"]).get()

    llm_client = OpenAI(api_key=llm_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
    Client(settings["nextcloud"]["url"], auth=(nc_user, nc_pass))

    # 2. Phase 1: Scan
    print("\n🔍 Phase 1: Scanning Cloud Sources...")
    init_schema(db_path, list(cloud_sources.keys()))
    scan_sources(db_path, cloud_sources)

    # 3. Phase 2: Strategy
    print("\n🧠 Phase 2: Evaluating Taxonomy Strategy...")
    routings = generate_strategy(db_path, list(cloud_sources.keys()), llm_client, settings["llm"]["model"])

    # 4. Phase 3: Physical Ingestion
    print("\n🚀 Phase 3: Executing ZFS Physical Ingestion...")
    execute_ingestion(db_path, nextcloud_mount, routings)

    # 5. Nextcloud Database Sync
    print("\n🔄 Triggering Nextcloud OCC Scan...")
    trigger_nextcloud_occ_scan("ix-nextcloud-nextcloud-1")

    print("\n" + "="*60)
    print("🎉 Bulk Ingestion Complete.")
    print("="*60)

if __name__ == "__main__":
    main()