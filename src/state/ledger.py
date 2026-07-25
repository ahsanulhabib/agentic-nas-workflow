import sqlite3
import os
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

class FileLedger:
    def __init__(self, db_path: str = None):
        # Force the database to always live in the exact same place
        if db_path is None:
            self.db_path = os.path.join(PROJECT_ROOT, "data", "ledger.db")
        else:
            self.db_path = db_path
            
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self):
        """SRE Best Practice: Enable WAL mode for concurrent read/writes."""
        conn = sqlite3.connect(self.db_path, timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute('pragma journal_mode=wal')
        return conn

    def _init_db(self):
        """Creates the SCD2 Schema if it doesn't exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cloud_path TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    nextcloud_path TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL CHECK (is_active IN (0, 1)),
                    valid_from DATETIME NOT NULL,
                    valid_to DATETIME,
                    action_taken TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cloud_path ON file_ledger(cloud_path)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON file_ledger(file_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_active ON file_ledger(is_active)")

    def evaluate_file(self, cloud_path: str, file_hash: str) -> dict:
        """Evaluates a file and returns the recommended action."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM file_ledger WHERE cloud_path = ? AND is_active = 1", 
                (cloud_path,)
            )
            active_record = cursor.fetchone()

            if active_record:
                if active_record['file_hash'] == file_hash:
                    return {"status": "EXACT_MATCH", "msg": "File is unchanged."}
                else:
                    return {"status": "MODIFIED", "msg": "File was edited in the cloud."}

            cursor = conn.execute(
                "SELECT * FROM file_ledger WHERE file_hash = ? AND is_active = 1", 
                (file_hash,)
            )
            duplicate_record = cursor.fetchone()

            if duplicate_record:
                return {
                    "status": "DUPLICATE_PATH", 
                    "msg": f"Exact file exists at different path: {duplicate_record['cloud_path']}"
                }

            return {"status": "NEW", "msg": "Net new file detected."}

    def record_transaction(self, cloud_path: str, file_hash: str, nextcloud_path: str, status: str):
        """Records the state change using SCD2 principles."""
        now = datetime.now(timezone.utc).isoformat()
        
        with self._get_connection() as conn:
            if status == "MODIFIED":
                conn.execute("""
                    UPDATE file_ledger 
                    SET is_active = 0, valid_to = ? 
                    WHERE cloud_path = ? AND is_active = 1
                """, (now, cloud_path))

            # SRE FIX: Added 'now' to the tuple to match the 5 bindings!
            conn.execute("""
                INSERT INTO file_ledger 
                (cloud_path, file_hash, nextcloud_path, is_active, valid_from, action_taken)
                VALUES (?, ?, ?, 1, ?, ?)
            """, (cloud_path, file_hash, nextcloud_path, now, status))