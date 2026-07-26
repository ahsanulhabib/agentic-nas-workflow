import os
import pytest
import sqlite3
from pathlib import Path

@pytest.fixture
def mock_env(tmp_path: Path):
    """Sets up a mock cloud environment with intentional duplicates."""
    gdrive = tmp_path / "gdrive"
    onedrive = tmp_path / "onedrive"
    nextcloud = tmp_path / "nextcloud"
    
    for d in [gdrive, onedrive, nextcloud]:
        d.mkdir()
        
    # Create unique files
    (gdrive / "unique_gdrive.txt").write_text("Hello Google")
    (onedrive / "unique_onedrive.txt").write_text("Hello Microsoft")
    
    # Create an EXACT duplicate across both drives
    (gdrive / "tax_2026.pdf").write_text("DUMMY TAX FILE")
    (onedrive / "tax_2026.pdf").write_text("DUMMY TAX FILE")
    
    return {
        "gdrive": str(gdrive),
        "onedrive": str(onedrive),
        "nextcloud": str(nextcloud),
        "db_path": tmp_path / "test_ledger.db"
    }