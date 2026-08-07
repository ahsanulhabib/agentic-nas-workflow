#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.inventory.features import classify_extension, path_features
from src.ledger import LedgerReader

PATH_COLUMNS = ["path", "file_path", "filepath", "name"]
ID_COLUMNS = ["fileid", "file_id", "id"]
SIZE_COLUMNS = ["size", "filesize", "file_size"]
MTIME_COLUMNS = ["mtime", "modified", "modified_at"]
MIME_COLUMNS = ["mimetype", "mime_type", "mimetype_id"]

def _find(columns: list[str], candidates: list[str]) -> str | None:
    lower = {c.lower(): c for c in columns}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None

def build_inventory(db_path: str | Path, output: str | Path, table: str | None = None) -> pd.DataFrame:
    reader = LedgerReader(db_path)
    table, columns, rows = reader.read_rows(table)
    raw = pd.DataFrame(rows, columns=columns)
    
    path_col = _find(columns, PATH_COLUMNS)
    if not path_col:
        raise RuntimeError(f"No path column detected in {table}: {columns}")
        
    records = [path_features(v) for v in raw[path_col].tolist()]
    df = pd.DataFrame(records)
    
    for candidates, output_col in [
        (ID_COLUMNS, "file_id"),
        (SIZE_COLUMNS, "size"),
        (MTIME_COLUMNS, "mtime"),
        (MIME_COLUMNS, "mimetype"),
    ]:
        col = _find(columns, candidates)
        df[output_col] = raw[col].tolist() if col else None
        
    df["media_class"] = df["extension"].map(classify_extension)
    df["source_table"] = table
    df["source_row_count"] = len(raw)
    
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    
    profile = {
        "table": table,
        "rows": len(df),
        "columns": list(df.columns),
        "path_column": path_col,
    }
    profile_path = out.with_suffix(".profile.json")
    profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    
    return df