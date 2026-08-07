#!/usr/bin/env python3
from pathlib import Path

from src.config import load_settings, root_path
from src.inventory.build import build_inventory
from src.kg.builder import build_rdf_graph
from src.kg.fuseki import FusekiClient
from src.okf.builder import OKFBuilder
from src.state.snapshot import create_snapshot
from src.vector.multimodal import index_unprocessed_files


def run_knowledge_pipeline(db_path: Path, nextcloud_mount: Path):
    """
    Phase 4: Builds Parquet, OKF Markdown, Apache Jena KG, and Qdrant Vectors.
    """
    print("\n" + "="*50)
    print("🧠 Starting Knowledge Substrate Pipeline")
    print("="*50)
    
    settings = load_settings()
    
    # 1. Inventory & Snapshot
    print("📊 1. Building Parquet & Temporal Snapshot...")
    inventory_path = root_path(settings["paths"]["inventory"])
    df = build_inventory(db_path, inventory_path, table="production_inventory")
    create_snapshot(df, root_path(settings["paths"]["snapshots"]))

    # 2. OKF Wiki
    print("📚 2. Generating OKF Markdown Wiki...")
    OKFBuilder(db_path, root_path(settings["paths"]["okf"])).build()

    # 3. Apache Jena KG
    print("🕸️ 3. Building & Publishing RDF Knowledge Graph...")
    ttl_path = root_path(settings["paths"]["kg_export"]) / "current.ttl"
    build_rdf_graph(db_path, ttl_path)
    
    fuseki = FusekiClient(settings["kg"]["fuseki_url"], settings["kg"]["dataset"])
    if fuseki.health():
        fuseki.replace_default_graph(ttl_path)

    # 4. Qdrant Vectors
    print("👁️ 4. Indexing Multimodal Vectors in Qdrant...")
    index_unprocessed_files(db_path, nextcloud_mount, "http://localhost:6333")

    print("\n✅ Knowledge Substrate is fully updated.")
    return {"status": "success"}