import sqlite3
import pandas as pd
from src.inventory.build import build_inventory
from src.okf.builder import OKFBuilder
from src.kg.builder import build_rdf_graph

def setup_mock_production(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE production_inventory (id INTEGER PRIMARY KEY, nextcloud_path TEXT, sha256_hash TEXT, file_size INTEGER, kg_indexed BOOLEAN DEFAULT 0)")
    conn.execute("INSERT INTO production_inventory (nextcloud_path, sha256_hash, file_size) VALUES ('/Docs/file1.txt', 'h1', 100)")
    conn.execute("INSERT INTO production_inventory (nextcloud_path, sha256_hash, file_size) VALUES ('/Docs/file2.txt', 'h2', 200)")
    conn.commit()
    conn.close()

def test_inventory_builder(mock_env, tmp_path):
    db_path = mock_env["db_path"]
    setup_mock_production(db_path)
    
    out_path = tmp_path / "inv.parquet"
    df = build_inventory(db_path, out_path, table="production_inventory")
    
    assert len(df) == 2
    assert out_path.exists()
    assert "extension" in df.columns

def test_okf_builder(mock_env, tmp_path):
    db_path = mock_env["db_path"]
    setup_mock_production(db_path)
    okf_dir = tmp_path / "okf"
    
    OKFBuilder(db_path, okf_dir).build()
    
    assert (okf_dir / "index.md").exists()
    assert (okf_dir / "folders" / "docs.md").exists()

def test_kg_builder(mock_env, tmp_path):
    db_path = mock_env["db_path"]
    setup_mock_production(db_path)
    ttl_path = tmp_path / "graph.ttl"
    
    graph = build_rdf_graph(db_path, ttl_path)
    
    assert ttl_path.exists()
    assert len(graph) > 0 # Should have generated triples