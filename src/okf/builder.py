#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import yaml


class OKFBuilder:
    def __init__(self, db_path: Path, okf_dir: Path):
        self.db_path = db_path
        self.okf_dir = okf_dir
        self.folders_dir = self.okf_dir / "folders"
        self.okf_dir.mkdir(parents=True, exist_ok=True)
        self.folders_dir.mkdir(parents=True, exist_ok=True)

    def build(self):
        """Generates the OKF Markdown graph from the production inventory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Register the missing REVERSE function in SQLite
        conn.create_function("REVERSE", 1, lambda text: text[::-1] if text else "")

        # Execute query targeting the correct 'file_ledger' table
        cursor = conn.execute("""
            SELECT 
                SUBSTR(nextcloud_path, 1, LENGTH(nextcloud_path) - INSTR(REVERSE(nextcloud_path), '/')) AS folder_path, 
                COUNT(id) as file_count
            FROM file_ledger
            GROUP BY folder_path
            ORDER BY folder_path ASC;
        """)

        folders = cursor.fetchall()
        
        index_links = []
        for row in folders:
            folder_path = row['folder_path']
            if not folder_path: continue
                
            safe_name = folder_path.strip("/").replace("/", "-").replace(" ", "_").lower() or "root"
            filename = f"{safe_name}.md"
            
            frontmatter = {
                "type": "folder",
                "name": folder_path.split("/")[-1] or "Root",
                "source_path": folder_path,
                "file_count": row['file_count']
            }
            
            body = f"# Directory: {folder_path}\n\nThis directory contains {row['file_count']} files.\n"
            
            # Write Concept File
            with open(self.folders_dir / filename, "w", encoding="utf-8") as f:
                f.write(f"---\n{yaml.dump(frontmatter, sort_keys=False)}---\n\n{body}\n")
                
            index_links.append(f"- [[folders/{safe_name}]] ({row['file_count']} files)")

        # Write Master Index
        index_fm = {"type": "index", "name": "NAS Master Taxonomy", "generated_at": datetime.now(timezone.utc).isoformat()}
        with open(self.okf_dir / "index.md", "w", encoding="utf-8") as f:
            f.write(f"---\n{yaml.dump(index_fm, sort_keys=False)}---\n\n# NAS Master Taxonomy\n\n" + "\n".join(index_links))
            
        conn.close()
        print(f"✅ OKF Knowledge Base built at {self.okf_dir}")