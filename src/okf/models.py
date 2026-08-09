from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OKFMetrics(BaseModel):
    file_count: int = Field(ge=0)
    total_size_bytes: int = Field(ge=0)
    first_seen: str | None = None
    last_updated: str | None = None

class OKFFolderSchema(BaseModel):
    type: str = "folder"
    name: str
    status: str = "active"
    source: str = "nextcloud_inventory"
    source_path: str
    domain: str = "general"
    area: str = "uncategorized"
    metrics: OKFMetrics
    tags: list[str] = Field(default_factory=list)

class OKFIndexSchema(BaseModel):
    okf_version: str = "0.2"
    type: str = "index"
    name: str = "NAS Master Taxonomy"
    generated_at: str
    total_files_indexed: int
    total_folders_indexed: int