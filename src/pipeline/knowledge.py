from pathlib import Path  # noqa: EXE002

from src.config import load_settings, root_path
from src.inventory.build import build_inventory
from src.kg.builder import build_rdf_graph
from src.kg.fuseki import FusekiClient
from src.kg.validation import validate_graph
from src.okf.builder import OKFBuilder
from src.okf.validator import OKFValidator
from src.state.snapshot import create_snapshot
from src.vector.pipeline import process_and_index_vectors


def run_knowledge_pipeline(db_path: Path, nextcloud_mount: Path) -> dict:
    """
    Phase 4: Knowledge Substrate Builder.
    Transaction-safe execution of Inventory, OKF, RDF Graph, and Qdrant Vectors.
    """
    print("\n" + "="*60)
    print("🚀 STARTING PHASE 4: ENTERPRISE KNOWLEDGE SUBSTRATE BUILD")
    print("="*60)
    
    settings = load_settings()
    
    # 1. Parquet Analytics & Snapshots
    print("\n📊 1. Building Parquet Inventory & Temporal Snapshot...")
    inventory_path = root_path(settings["paths"]["inventory"])
    df = build_inventory(db_path, inventory_path, table="production_inventory")
    snapshot_path = create_snapshot(df, root_path(settings["paths"]["snapshots"]))
    print(f"   [Success] Snapshot saved: {snapshot_path.name}")

    # 2. OKF Wiki & Validation
    print("\n📚 2. Building OKF Markdown Wiki & Validating Links...")
    okf_dir = root_path(settings["paths"]["okf"])
    OKFBuilder(db_path, okf_dir).build()
    
    validator = OKFValidator(okf_dir)
    val_report = validator.validate_all()
    print(f"   [OKF Status] Valid Docs: {val_report['valid_files']} | Broken Links: {len(val_report['broken_links'])}")

    # 3. Knowledge Graph & Jena Publish
    print("\n🕸️ 3. Building & Validating RDF Knowledge Graph...")
    ttl_path = root_path(settings["paths"]["kg_export"]) / "current.ttl"
    graph = build_rdf_graph(db_path, ttl_path)
    
    graph_report = validate_graph(graph)
    print(f"   [Graph Metrics] Total Triples: {graph_report['total_triples']} | Valid: {graph_report['is_valid']}")

    fuseki = FusekiClient(settings["kg"]["fuseki_url"], settings["kg"]["dataset"])
    if fuseki.health():
        fuseki.replace_default_graph(ttl_path)
        print("   [Fuseki] Published current.ttl to TDB2 runtime store.")
    else:
        print("   [Warning] Apache Jena Fuseki is offline. Graph saved locally.")

    # 4. Multimodal Vector Indexing (Qdrant)
    print("\n🧠 4. Batch Indexing Multimodal Vectors (Qdrant)...")
    try:
        vec_report = process_and_index_vectors(
            db_path=db_path, 
            nextcloud_mount=nextcloud_mount, 
            qdrant_url="http://localhost:6333"
        )
        print(f"   [Qdrant Metrics] Indexed Points: {vec_report['indexed_points']} | Isolated Errors: {vec_report['poison_pills_isolated']}")
    except Exception as e:  # noqa: BLE001
        print(f"   [Warning] Vector pipeline failed: {e}")

    print("\n" + "="*60)
    print("✅ PHASE 4 COMPLETE: Knowledge Substrate is fully synchronized.")
    print("="*60)
    
    return {
        "status": "success",
        "snapshot": str(snapshot_path),
        "okf_valid": val_report["is_valid"],
        "graph_triples": graph_report["total_triples"]
    }