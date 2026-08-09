from __future__ import annotations  # noqa: EXE002

import sqlite3
from pathlib import Path
from typing import Any

from qdrant_client.models import PointStruct

from src.config import load_settings
from src.vector.chunking import recursive_text_chunker
from src.vector.models import VectorPayloadSchema
from src.vector.qdrant_client import init_qdrant_collections

# Universal Embedder Singleton
_embedder_instance = None

class UniversalEmbedder:
    """
    Universal Embedding Factory.
    Dynamically loads and abstracts any HuggingFace, FastEmbed, or Jina model.
    """
    def __init__(self, provider: str, model_name: str, vector_size: int):
        self.provider = provider
        self.model_name = model_name
        self.vector_size = vector_size
        self._model = None
        self._load_model()

    def _load_model(self):
        print(f"🧠 Loading Vector Model: [{self.model_name}] (Dim: {self.vector_size})...")
        if self.provider == "fastembed":
            from fastembed import TextEmbedding
            self._model = TextEmbedding(model_name=self.model_name)
            self.is_multimodal = False
        else:
            # HuggingFace / Transformers (Supports Jina-CLIP, BGE-M3, Nomic, MXBAI, etc.)
            from transformers import AutoModel
            self._model = AutoModel.from_pretrained(self.model_name, trust_remote_code=True)
            # Check if model supports image encoding natively
            self.is_multimodal = hasattr(self._model, "encode_image") or "clip" in self.model_name.lower()

    def embed_text(self, texts: list[str]) -> list[list[float]]:
        if not texts: return []
        
        if self.provider == "fastembed":
            return [emb.tolist() for emb in self._model.embed(texts)]
        elif hasattr(self._model, "encode_text"):
            # Jina / Custom Transformer models
            embeddings = self._model.encode_text(texts)
            return [emb.tolist() if hasattr(emb, "tolist") else emb for emb in embeddings]
        else:
            # Standard SentenceTransformers / HuggingFace models
            from sentence_transformers import SentenceTransformer
            if not isinstance(self._model, SentenceTransformer):
                self._model = SentenceTransformer(self.model_name, trust_remote_code=True)
            return self._model.encode(texts, convert_to_numpy=True).tolist()

    def embed_image(self, image_path: Path) -> list[float] | None:
        if not self.is_multimodal:
            return None
            
        from PIL import Image
        image = Image.open(image_path).convert("RGB")
        
        if hasattr(self._model, "encode_image"):
            emb = self._model.encode_image([image])[0]
            return emb.tolist() if hasattr(emb, "tolist") else emb
        return None

def get_embedder() -> UniversalEmbedder:
    global _embedder_instance
    if _embedder_instance is None:
        settings = load_settings()
        vec_cfg = settings["vector"]
        _embedder_instance = UniversalEmbedder(
            provider=vec_cfg["provider"],
            model_name=vec_cfg["model_name"],
            vector_size=int(vec_cfg["vector_size"])
        )
    return _embedder_instance

def index_unprocessed_files(db_path: Path | str, nextcloud_mount: Path | str, qdrant_url: str = "http://localhost:6333", batch_size: int = 50) -> dict[str, Any]:
    """
    Parameterized Vector Pipeline:
    Embeds documents and images using whatever model is configured in settings.yaml!
    """
    db_path = Path(db_path)
    nextcloud_mount = Path(nextcloud_mount)
    settings = load_settings()
    
    client = init_qdrant_collections(qdrant_url)
    embedder = get_embedder()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("""
        SELECT id, nextcloud_path, blake3_hash, file_size 
        FROM production_inventory 
        WHERE vector_indexed = 0 
        LIMIT ?
    """, (batch_size,))
    unprocessed = cursor.fetchall()

    if not unprocessed:
        conn.close()
        return {"status": "up_to_date", "indexed_points": 0}

    points: list[PointStruct] = []
    indexed_file_ids, failed_file_ids = [], []

    for row in unprocessed:
        remote_path = str(row["nextcloud_path"])
        file_id = row["id"]
        content_hash = str(row["blake3_hash"])
        local_path = nextcloud_mount / "admin" / "files" / remote_path.lstrip("/")
        ext = local_path.suffix.lower()

        if not local_path.exists():
            failed_file_ids.append(file_id)
            continue

        try:
            # --- 1. DOCUMENTS ---
            if ext in [".txt", ".md", ".csv"]:
                text_content = local_path.read_text(encoding="utf-8", errors="ignore")
                chunks = recursive_text_chunker(text_content, chunk_size=1024, overlap=128)
                
                if chunks:
                    embeddings = embedder.embed_text(chunks)
                    for chunk_idx, (chunk_str, emb) in enumerate(zip(chunks, embeddings)):
                        payload = VectorPayloadSchema(
                            document_id=file_id,
                            source_path=remote_path,
                            filename=local_path.name,
                            extension=ext,
                            media_type="document",
                            chunk_id=chunk_idx,
                            total_chunks=len(chunks),
                            content_hash=content_hash,
                            taxonomy_category=str(local_path.parent.name),
                            embedding_model=embedder.model_name
                        ).model_dump()
                        
                        point_id = int(f"{file_id}{chunk_idx:03d}")
                        points.append(PointStruct(id=point_id, vector=emb, payload=payload))
                    indexed_file_ids.append(file_id)

            # --- 2. IMAGES (If model supports vision) ---
            elif ext in [".jpg", ".jpeg", ".png"] and embedder.is_multimodal:
                image_emb = embedder.embed_image(local_path)
                if image_emb:
                    payload = VectorPayloadSchema(
                        document_id=file_id,
                        source_path=remote_path,
                        filename=local_path.name,
                        extension=ext,
                        media_type="image",
                        content_hash=content_hash,
                        taxonomy_category=str(local_path.parent.name),
                        embedding_model=embedder.model_name
                    ).model_dump()

                    points.append(PointStruct(id=file_id * 1000, vector=image_emb, payload=payload))
                    indexed_file_ids.append(file_id)
            else:
                # Unsupported media type for current model
                failed_file_ids.append(file_id)

        except Exception as e:  # noqa: BLE001
            print(f"⚠️ [Poison Pill] Failed to index {remote_path}: {e}")
            failed_file_ids.append(file_id)

    if points:
        client.upsert(collection_name=settings["vector"]["collection_name"], points=points)

    for fid in indexed_file_ids:
        conn.execute("UPDATE production_inventory SET vector_indexed = 1 WHERE id = ?", (fid,))
    for fid in failed_file_ids:
        conn.execute("UPDATE production_inventory SET vector_indexed = -1 WHERE id = ?", (fid,))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "processed_files": len(unprocessed),
        "indexed_points": len(points),
        "poison_pills_isolated": len(failed_file_ids)
    }