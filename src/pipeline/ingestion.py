#!/usr/bin/env python3
from pathlib import Path

from openai import OpenAI
from webdav4.client import Client

from src.elt.ingestion import execute_ingestion
from src.elt.scanner import scan_sources
from src.elt.strategy import generate_strategy
from src.state.schema import init_v5_schema


def run_ingestion_pipeline(db_path: Path, nextcloud_mount: Path, cloud_sources: dict[str, str], llm_client: OpenAI, webdav_client: Client, model_name: str, dry_run: bool = False):
    """
    Phases 1-3: Extracts from cloud staging, asks the LLM for taxonomy, and physically ingests.
    """
    print("\n" + "="*50)
    print(f"🚀 Starting ELT Ingestion Pipeline {'(DRY RUN)' if dry_run else ''}")
    print("="*50)

    # Phase 1: Ensure Schema & Scan
    init_v5_schema(db_path, list(cloud_sources.keys()))
    scan_sources(db_path, cloud_sources)

    # Phase 2: Agentic Strategy
    routings = generate_strategy(db_path, list(cloud_sources.keys()), llm_client, model_name)

    if not routings:
        print("✅ No files to ingest. Pipeline complete.")
        return {"status": "success", "ingested": 0}

    if dry_run:
        print("\n🛑 DRY RUN: The following moves would be executed:")
        for r in routings:
            print(f"   - Staging ID {r.staging_id} -> {r.proposed_path}")
        return {"status": "dry_run_complete", "proposed_moves": len(routings)}

    # Phase 3: Physical Ingestion
    execute_ingestion(db_path, nextcloud_mount, routings)
    return {"status": "success", "ingested": len(routings)}