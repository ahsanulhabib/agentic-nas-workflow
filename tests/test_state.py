import sqlite3
from src.state.schema import init_v5_schema, get_unified_staging_view
from src.elt.scanner import scan_sources

def test_schema_initialization(mock_env):
    db_path = mock_env["db_path"]
    sources = ["Google Drive", "OneDrive"]
    
    init_v5_schema(db_path, sources)
    
    conn = sqlite3.connect(db_path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    conn.close()
    
    assert "production_inventory" in tables
    assert "staging_google_drive" in tables
    assert "staging_onedrive" in tables

def test_unified_staging_deduplication(mock_env):
    db_path = mock_env["db_path"]
    sources = {"Google Drive": mock_env["gdrive"], "OneDrive": mock_env["onedrive"]}
    
    init_v5_schema(db_path, list(sources.keys()))
    scan_sources(db_path, sources)  # Puts 4 files into staging (1 is a duplicate)
    
    # Test the CTE cross-table deduplication
    unified_view = get_unified_staging_view(db_path, list(sources.keys()))
    
    # We created 4 files, but 2 are identical. The view should only return 3!
    assert len(unified_view) == 3
    
    # Ensure all returned files have unique hashes
    hashes = [f["sha256_hash"] for f in unified_view]
    assert len(hashes) == len(set(hashes))