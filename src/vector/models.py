from __future__ import annotations

from pydantic import BaseModel, Field


class VectorPayloadSchema(BaseModel):
    document_id: int
    source_path: str
    filename: str
    extension: str
    media_type: str  # document, image, audio, video
    chunk_id: int = 0
    total_chunks: int = 1
    content_hash: str
    taxonomy_category: str = "Unsorted"
    trust_tier: int = Field(default=1, description="Inherited OKF Trust Tier")
    tags: list[str] = Field(default_factory=list)
    embedding_model: str