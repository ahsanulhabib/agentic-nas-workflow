from __future__ import annotations  # noqa: EXE002

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.okf.models import OKFFolderSchema, OKFIndexSchema, OKFMetrics


class OKFBuilder:
    """Enterprise OKF v0.2 Knowledge Base Generator."""
    
    def __init__(self, db_path: Path | str, okf_dir: Path | str):
        self.db_path = Path(db_path)
        self.okf_dir = Path(okf_dir)
        self.domains_dir = self.okf_dir / "domains"
        self.areas_dir = self.okf_dir / "areas"
        self.folders_dir = self.okf_dir / "folders"
        
        for d in [self.okf_dir, self.domains_dir, self.areas_dir, self.folders_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _determine_domain_and_area(self, folder_path: str) -> tuple[str, str]:
        parts = [p for p in folder_path.strip("/").split("/") if p]
        if not parts:
            return "root", "root"
        domain = parts[0].lower()
        area = parts[1].lower() if len(parts) > 1 else "general"
        return domain, area

    def build(self) -> dict[str, Any]:
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT 
                SUBSTR(nextcloud_path, 1, LENGTH(nextcloud_path) - INSTR(REVERSE(nextcloud_path), '/')) AS folder_path,
                COUNT(id) as file_count,
                SUM(file_size) as total_size,
                MIN(ingested_at) as first_seen,
                MAX(ingested_at) as last_updated
            FROM production_inventory
            WHERE nextcloud_path IS NOT NULL AND nextcloud_path != ''
            GROUP BY folder_path
            ORDER BY folder_path ASC;
        """)
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {"status": "empty", "folders_created": 0}

        total_files = 0
        domains_map: dict[str, list[str]] = {}

        for row in rows:
            folder_path = row['folder_path'] or "/Root"
            domain, area = self._determine_domain_and_area(folder_path)
            
            safe_name = folder_path.strip("/").replace("/", "-").replace(" ", "_").lower() or "root"
            filename = f"{safe_name}.md"
            
            metrics = OKFMetrics(
                file_count=row['file_count'],
                total_size_bytes=row['total_size'] or 0,
                first_seen=str(row['first_seen']),
                last_updated=str(row['last_updated'])
            )
            
            folder_meta = OKFFolderSchema(
                name=folder_path.split("/")[-1] or "Root",
                source_path=folder_path,
                domain=domain,
                area=area,
                metrics=metrics,
                tags=[domain, area]
            )
            
            # Markdown Body Construction
            body = f"# Folder Concept: {folder_meta.name}\n\n"
            body += f"Canonical Path: `{folder_path}`\n\n"
            body += f"## Domain & Area\n- **Domain:** [[domains/{domain}]]\n- **Area:** [[areas/{area}]]\n\n"
            body += "## Metrics\n"
            body += f"- Total Files: **{metrics.file_count}**\n"
            body += f"- Total Volume: **{metrics.total_size_bytes / (1024*1024):.2f} MB**\n\n"
            body += "## Sub-Concepts & Links\n*(Dynamically updated by taxonomy agent)*\n"

            # Write validated OKF document
            frontmatter_dict = folder_meta.model_dump()
            content = f"---\n{yaml.dump(frontmatter_dict, sort_keys=False)}---\n\n{body}"
            (self.folders_dir / filename).write_text(content, encoding="utf-8")

            total_files += metrics.file_count
            domains_map.setdefault(domain, []).append(f"[[folders/{safe_name}]]")

        # Build Domain index files
        for domain, links in domains_map.items():
            domain_body = f"# Domain: {domain.title()}\n\n## Folders in this domain:\n"
            domain_body += "\n".join(f"- {link}" for link in links)
            (self.domains_dir / f"{domain}.md").write_text(domain_body, encoding="utf-8")

        # Build Master Index
        index_meta = OKFIndexSchema(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_files_indexed=total_files,
            total_folders_indexed=len(rows)
        )
        index_body = f"# NAS Master Taxonomy Index\n\nTotal Files: **{total_files}** | Total Folders: **{len(rows)}**\n\n## Domains\n"
        index_body += "\n".join(f"- [[domains/{d}]] ({len(l)} folders)" for d, l in domains_map.items())

        content = f"---\n{yaml.dump(index_meta.model_dump(), sort_keys=False)}---\n\n{index_body}"
        (self.okf_dir / "index.md").write_text(content, encoding="utf-8")

        return {
            "status": "success",
            "files_indexed": total_files,
            "folders_created": len(rows),
            "domains_created": len(domains_map)
        }