#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import load_settings, root_path
from src.inventory.analytics import summary
from src.inventory.build import build_inventory
from src.kg.builder import build_graph
from src.kg.fuseki import FusekiClient
from src.kg.query import graph_counts
from src.ledger import LedgerReader
from src.pipeline.stages import run_graph_rag, run_safe_pipeline
from src.state.snapshot import compare_snapshots, create_snapshot


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("inspect-schema")
    s.add_argument("--db", default=None)

    s = sub.add_parser("inventory")
    s.add_argument("--db", default=None)
    s.add_argument("--out", default=None)

    s = sub.add_parser("snapshot")
    s.add_argument("--inventory", default=None)

    s = sub.add_parser("compare")
    s.add_argument("old")
    s.add_argument("new")

    sub.add_parser("pipeline")
    sub.add_parser("kg-build")
    sub.add_parser("kg-publish")
    sub.add_parser("kg-counts")

    s = sub.add_parser("kg-query")
    s.add_argument("--query-file", required=True)

    s = sub.add_parser("graph-rag")
    s.add_argument("--question", required=True)

    args = parser.parse_args()
    settings = load_settings()

    if args.command == "inspect-schema":
        db = root_path(args.db or settings["paths"]["ledger_db"])
        print(json.dumps(LedgerReader(db).schema(), indent=2))

    elif args.command == "inventory":
        db = root_path(args.db or settings["paths"]["ledger_db"])
        out = root_path(args.out or settings["paths"]["inventory"])
        df = build_inventory(db, out)
        print(json.dumps(summary(df), indent=2))

    elif args.command == "snapshot":
        inventory = root_path(args.inventory or settings["paths"]["inventory"])
        df = __import__("pandas").read_parquet(inventory)
        path = create_snapshot(df, root_path(settings["paths"]["snapshots"]))
        print(path)

    elif args.command == "compare":
        print(json.dumps(compare_snapshots(args.old, args.new), indent=2))

    elif args.command == "pipeline":
        print(json.dumps(run_safe_pipeline(), indent=2, default=str))

    elif args.command == "kg-build":
        import pandas as pd
        df = pd.read_parquet(root_path(settings["paths"]["inventory"]))
        candidates_path = root_path(settings["paths"]["okf"]) / "candidates.json"
        candidates = json.loads(candidates_path.read_text()) if candidates_path.exists() else None
        out = root_path(settings["paths"]["kg_export"]) / "current.ttl"
        graph = build_graph(df, out, candidates)
        print(f"Built {len(graph)} triples at {out}")

    elif args.command == "kg-publish":
        client = FusekiClient(
            settings["kg"]["fuseki_url"],
            settings["kg"]["dataset"],
            int(settings["kg"]["request_timeout_seconds"]),
        )
        ttl = root_path(settings["paths"]["kg_export"]) / "current.ttl"
        if not client.health():
            raise SystemExit("Fuseki is not reachable.")
        client.replace_default_graph(ttl)
        print("Published current KG.")

    elif args.command == "kg-counts":
        client = FusekiClient(
            settings["kg"]["fuseki_url"],
            settings["kg"]["dataset"],
            int(settings["kg"]["request_timeout_seconds"]),
        )
        print(json.dumps(graph_counts(client), indent=2))

    elif args.command == "kg-query":
        query = Path(args.query_file).read_text(encoding="utf-8")
        client = FusekiClient(
            settings["kg"]["fuseki_url"],
            settings["kg"]["dataset"],
            int(settings["kg"]["request_timeout_seconds"]),
        )
        print(json.dumps(client.query(query), indent=2))

    elif args.command == "graph-rag":
        print(json.dumps(run_graph_rag(args.question), indent=2))

if __name__ == "__main__":
    main()
    
# import os
# import time
# from src.config import INGEST_DIR
# from src.dedupe.crypto import calculate_blake3
# from src.storage.webdav import create_webdav_client, upload_file
# from src.state.ledger import FileLedger
# from prefect import flow, task
# from prefect.cache_policies import NO_CACHE


# @task(retries=2, retry_delay_seconds=5)
# def task_hash_file(file_path: str) -> str:
#     return calculate_blake3(file_path)

# @task(retries=3, retry_delay_seconds=5, cache_policy=NO_CACHE)
# def task_upload_file(client, local_path: str, remote_path: str):
#     upload_file(client, local_path, remote_path)

# @flow(name="Agentic-NAS-Pipeline", log_prints=True)
# def run_pipeline():
#     print(f"Starting SRE Pipeline on directory: {INGEST_DIR}")
    
#     if not os.path.exists(INGEST_DIR):
#         print(f"ERROR: {INGEST_DIR} not found. Check TrueNAS volume mounts.")
#         return

#     # Dependency Injection
#     webdav_client = create_webdav_client()
    
#     # 2. Instantiate the Persistent SQLite Ledger (Replaces the ephemeral set)
#     ledger = FileLedger(db_path="data/ledger.db")
#     print("SCD2 Ledger successfully connected.")

#     stats = {"scanned": 0, "uploaded": 0, "duplicates": 0, "modifications": 0, "errors": 0, "bytes_uploaded": 0}
#     remote_base_dir = "/Documents/GDriveIngestionTest"

#     print(f"Scanning Ingest Directory: {INGEST_DIR}")
#     print("="*50)

#     start_time = time.time()
#     for root, _, files in os.walk(INGEST_DIR):
#         for file in files:
#             local_path = os.path.join(root, file)
#             file_size = os.path.getsize(local_path)
#             stats["scanned"] += 1
            
#             relative_path = os.path.relpath(local_path, INGEST_DIR)
#             remote_path = f"{remote_base_dir}/{relative_path}".replace("\\", "/")
            
#             print(f"\n📄 Testing File: {relative_path} ({(file_size / 1024 / 1024):.2f} MB)")
            
#             # --- TEST 1: Cryptographic Hashing ---
#             try:
#                 file_hash = task_hash_file(local_path)
                
#                 # 3. Consult the Persistent Ledger
#                 evaluation = ledger.evaluate_file(cloud_path=relative_path, file_hash=file_hash)
#                 status = evaluation["status"]
#                 print(f"   [Ledger] Status: {status} | {evaluation['msg']}")
                
#                 if status == "EXACT_MATCH":
#                     print("   [Action] Ignoring. Already synced.")
#                     continue
                    
#                 elif status == "DUPLICATE_PATH":
#                     print("   [Action] 🛑 DENIED. File is a duplicate copy. Skipping upload.")
#                     stats["duplicates"] += 1
#                     continue
                    
#             except Exception as e:
#                 print(f"   [Error] Hashing failed: {e}")
#                 stats["errors"] += 1
#                 continue 

#             # --- TEST 2: WebDAV Upload ---
#             if status in ["NEW", "MODIFIED"]:
#                 try:
#                     task_upload_file(webdav_client, local_path, remote_path)
                    
#                     # 4. Commit the transaction to the SQLite Ledger
#                     ledger.record_transaction(
#                         cloud_path=relative_path, 
#                         file_hash=file_hash, 
#                         nextcloud_path=remote_path, 
#                         status=status
#                     )
                    
#                     if status == "NEW":
#                         stats["uploaded"] += 1
#                     else:
#                         stats["modifications"] += 1
                        
#                     stats["bytes_uploaded"] += file_size
                    
#                 except Exception as e:
#                     print(f"   [Error] Upload failed: {e}")
#                     stats["errors"] += 1

#     # Print SRE Telemetry Summary
#     end_time = time.time()
#     duration = end_time - start_time
#     mb_uploaded = stats["bytes_uploaded"] / (1024 * 1024)

#     print("\n" + "="*50)
#     print("📊 PIPELINE EXECUTION TELEMETRY")
#     print("="*50)
#     print(f"⏱️  Total Time:       {duration:.2f} seconds")
#     print(f"📁 Files Scanned:    {stats['scanned']}")
#     print(f"✅ Files Uploaded:   {stats['uploaded']} ({mb_uploaded:.2f} MB)")
#     print(f"🔄 Files Updated:    {stats['modifications']}")
#     print(f"🛑 Duplicates Saved: {stats['duplicates']}")
#     print(f"⚠️  Errors:           {stats['errors']}")
#     print("="*50)

# if __name__ == "__main__":
#     run_pipeline()

#     # For nightly GitOps schedule:
#     run_pipeline.serve(
#         name="daily-dedupe-job",
#         cron="0 2 * * *",
#         tags=["production", "nas"],
#         description="Pulls from Google Drive and executes WebDAV deduplication."
#     )

