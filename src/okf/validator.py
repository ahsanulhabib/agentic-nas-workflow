from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from src.okf.models import OKFFolderSchema, OKFIndexSchema


class OKFValidator:
    """Validates frontmatter schemas and broken wikilinks in OKF markdown."""
    
    def __init__(self, okf_dir: Path | str):
        self.okf_dir = Path(okf_dir)

    def validate_all(self) -> dict[str, Any]:
        errors = []
        valid_files = 0
        all_links = []

        for md_file in self.okf_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            if not content.startswith("---"):
                errors.append(f"{md_file.name}: Missing YAML frontmatter marker")
                continue

            try:
                parts = content.split("---", 2)
                frontmatter = yaml.safe_load(parts[1])
                
                # Schema Validation
                doc_type = frontmatter.get("type")
                if doc_type == "folder":
                    OKFFolderSchema.model_validate(frontmatter)
                elif doc_type == "index":
                    OKFIndexSchema.model_validate(frontmatter)

                # Collect Wikilinks [[target]] for link validation
                links = re.findall(r"\[\[(.*?)\]\]", parts[2])
                all_links.extend((md_file, target) for target in links)
                valid_files += 1

            except ValidationError as ve:
                errors.append(f"{md_file.name}: Schema Validation Error - {ve}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"{md_file.name}: Parse Error - {e}")

        # Broken Link Validation
        broken_links = []
        for source_file, target in all_links:
            target_path = self.okf_dir / f"{target}.md"
            if not target_path.exists():
                broken_links.append(f"{source_file.name} -> [[{target}]]")

        return {
            "valid_files": valid_files,
            "schema_errors": errors,
            "broken_links": broken_links,
            "is_valid": len(errors) == 0 and len(broken_links) == 0
        }