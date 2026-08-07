#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def create_snapshot(df: pd.DataFrame, root: str | Path) -> Path:
    root = Path(root)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = root / run_id
    target.mkdir(parents=True, exist_ok=False)
    
    df.to_parquet(target / "inventory.parquet", index=False)
    
    path_hash = hashlib.sha256(
        "\n".join(sorted(df["path"].astype(str))).encode()
    ).hexdigest()
    
    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file_count": len(df),
        "path_hash": path_hash,
    }
    
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return target

def list_snapshots(root: str | Path) -> list[Path]:
    root = Path(root)
    return sorted([p for p in root.iterdir() if p.is_dir()]) if root.exists() else []

def compare_snapshots(old: str | Path, new: str | Path) -> dict:
    old_df = pd.read_parquet(Path(old) / "inventory.parquet")
    new_df = pd.read_parquet(Path(new) / "inventory.parquet")
    
    old_paths = set(old_df["path"].astype(str))
    new_paths = set(new_df["path"].astype(str))
    
    added = sorted(new_paths - old_paths)
    removed = sorted(old_paths - new_paths)
    denominator = max(len(old_paths), 1)
    
    return {
        "old_files": len(old_paths),
        "new_files": len(new_paths),
        "added": len(added),
        "removed": len(removed),
        "change_rate": (len(added) + len(removed)) / denominator,
        "added_paths": added[:1000],
        "removed_paths": removed[:1000],
    }