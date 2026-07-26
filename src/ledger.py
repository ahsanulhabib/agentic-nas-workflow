
from __future__ import annotations
import sqlite3
from pathlib import Path

class LedgerReader:
    """Read-only SQLite ledger reader with conservative schema detection."""
    
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        if not self.db_path.exists():
            raise FileNotFoundError(self.db_path)
        uri = f"file:{self.db_path.resolve()}?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def tables(self) -> list[str]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            return [r[0] for r in rows]

    def columns(self, table: str) -> list[str]:
        with self.connect() as con:
            rows = con.execute(f'PRAGMA table_info("{table}")').fetchall()
            return [r[1] for r in rows]

    def schema(self) -> dict[str, list[str]]:
        return {table: self.columns(table) for table in self.tables()}

    def detect_table(self, preferred: list[str] | None = None) -> str:
        preferred = preferred or []
        tables = self.tables()
        lower = {t.lower(): t for t in tables}
        
        for name in preferred:
            if name.lower() in lower:
                return lower[name.lower()]
                
        candidates = []
        for table in tables:
            cols = {c.lower() for c in self.columns(table)}
            pathish = {"path", "file_path", "filepath", "name"} & cols
            idish = {"fileid", "file_id", "id"} & cols
            if pathish and idish:
                candidates.append(table)
                
        if not candidates:
            raise RuntimeError(f"Could not detect a file table. Tables: {tables}")
        return candidates[0]

    def read_rows(self, table: str | None = None, preferred: list[str] | None = None):
        table = table or self.detect_table(preferred)
        cols = self.columns(table)
        with self.connect() as con:
            query = f'SELECT * FROM "{table}"'
            return table, cols, con.execute(query).fetchall()