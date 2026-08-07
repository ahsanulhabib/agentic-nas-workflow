#!/usr/bin/env python3
from pathlib import Path

from src.state.snapshot import compare_snapshots, list_snapshots


def run_snapshot_audit(snapshot_dir: Path) -> dict:
    """
    SRE Tool: Compares the two most recent NAS snapshots to detect massive deletion events or taxonomy churn.
    """
    print("\n" + "="*50)
    print("🛡️ Starting SRE Snapshot Audit")
    print("="*50)

    snapshots = list_snapshots(snapshot_dir)
    if len(snapshots) < 2:
        print("Not enough snapshots to compare.")
        return {"status": "insufficient_data"}

    latest = snapshots[-1]
    previous = snapshots[-2]

    print(f"Comparing {previous.name} -> {latest.name}")
    diff = compare_snapshots(previous, latest)
    
    print(f"Files Added: {diff['added']}")
    print(f"Files Removed: {diff['removed']}")
    print(f"Change Rate: {diff['change_rate']:.2%}")

    if diff['change_rate'] > 0.10: # 10% churn threshold
        print("\n⚠️ CRITICAL WARNING: Massive filesystem churn detected!")
        print("Recommendation: Halt ingestion and review Nextcloud trashbin.")
        
    return diff