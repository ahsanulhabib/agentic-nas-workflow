import os
import sqlite3
from unittest.mock import MagicMock, patch
from src.elt.scanner import calculate_sha256
from src.elt.strategy import generate_strategy, FileRoute
from src.elt.ingestion import execute_ingestion
from src.state.schema import init_v5_schema, get_unified_staging_view

def test_calculate_sha256(mock_env):
    file_path = os.path.join(mock_env["gdrive"], "unique_gdrive.txt")
    file_hash = calculate_sha256(file_path)
    assert isinstance(file_hash, str)
    assert len(file_hash) == 64 # SHA-256 length

@patch("src.elt.strategy.instructor.from_openai")
def test_agentic_strategy(mock_instructor, mock_env):
    """Mocks the LLM to test the routing logic without hitting an API."""
    db_path = mock_env["db_path"]
    sources = ["Google Drive"]
    init_v5_schema(db_path, sources)
    
    # Mock the LLM response
    mock_client = MagicMock()
    mock_instructor.return_value = mock_client
    
    mock_strategy = MagicMock()
    mock_strategy.routings = [
        FileRoute(staging_id=1, source_table="staging_google_drive", proposed_path="/Docs/test.txt", reasoning="Test")
    ]
    mock_client.chat.completions.create.return_value = mock_strategy
    
    routings = generate_strategy(db_path, sources, MagicMock(), "test-model")
    
    assert len(routings) == 1
    assert routings[0].proposed_path == "/Docs/test.txt"

def test_physical_ingestion(mock_env):
    db_path = mock_env["db_path"]
    nc_mount = Path(mock_env["nextcloud"])
    
    # Setup state
    init_v5_schema(db_path, ["test_src"])
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO staging_test_src (original_path, filename, file_size, sha256_hash) VALUES (?, ?, ?, ?)",
                 (os.path.join(mock_env["gdrive"], "unique_gdrive.txt"), "unique_gdrive.txt", 100, "hash123"))
    conn.commit()
    conn.close()
    
    # Create fake routing
    routings = [FileRoute(staging_id=1, source_table="staging_test_src", proposed_path="/Auto/unique.txt", reasoning="")]
    
    # Execute Ingestion
    execute_ingestion(db_path, nc_mount, routings)
    
    # Verify Physical File Move
    assert (nc_mount / "admin" / "files" / "Auto" / "unique.txt").exists()
    
    # Verify Production Inventory Updated
    conn = sqlite3.connect(db_path)
    prod_count = conn.execute("SELECT COUNT(*) FROM production_inventory").fetchone()[0]
    staging_status = conn.execute("SELECT status FROM staging_test_src WHERE id=1").fetchone()[0]
    conn.close()
    
    assert prod_count == 1
    assert staging_status == "ingested"