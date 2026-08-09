from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from qdrant_client.models import PointStruct
from transformers import CLIPModel, CLIPProcessor

from src.vector.chunking import recursive_text_chunker
from src.vector.models import VectorPayloadSchema
from src.vector.qdrant_client import init_qdrant_collections

# Lazy-loaded model instances to save RAM
_text_model = None
_image_model = None
_image_processor = None

def _get_text_model():
    from fastembed import TextEmbedding
    global _text_model
    if _text_model is None:
        _text_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _text_model

def _get_image_model():
    global _image_model, _image_processor
    if _image_model is None:
        _image_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        _image_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    return _image_processor, _image_model

def process_and_index_vectors(db_path: Path | str, nextcloud_mount: Path | str, qdrant_url: str = "http://localhost:6333", batch_size: int = 50) -> dict[str, Any]:
    """
    Enterprise Multimodal Vector Pipeline:
    Batch processing, Poison-Pill isolation (vector_indexed = -1), and Pydantic Payload Validation.
    """
    db_path = Path(db_path)
    nextcloud_mount = Path(nextcloud_mount)
    client = init_qdrant_collections(qdrant_url)

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
    indexed_file_ids = []
    failed_file_ids = []

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
            # --- 1. DOCUMENTS (Text Chunking + Dense Embedding) ---
            if ext in [".txt", ".md", ".csv"]:
                text_content = local_path.read_text(encoding="utf-8", errors="ignore")
                chunks = recursive_text_chunker(text_content, chunk_size=512, overlap=64)
                text_model = _get_text_model()
                
                if chunks:
                    embeddings = list(text_model.embed(chunks))
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
                            embedding_model="BAAI/bge-small-en-v1.5"
                        ).model_dump()
                        
                        # Generate deterministic point integer ID
                        point_id = int(f"{file_id}{chunk_idx:03d}")
                        points.append(PointStruct(
                            id=point_id,
                            vector={"text_dense": emb.tolist()},
                            payload=payload
                        ))
                    indexed_file_ids.append(file_id)

            # --- 2. IMAGES (CLIP Vision Embedding) ---
            elif ext in [".jpg", ".jpeg", ".png"]:
                processor, model = _get_image_model()
                image = Image.open(local_path).convert("RGB")
                inputs = processor(images=image, return_tensors="pt")
                with torch.no_grad():
                    image_features = model.get_image_features(**inputs)
                
                emb = image_features[0].tolist()
                payload = VectorPayloadSchema(
                    document_id=file_id,
                    source_path=remote_path,
                    filename=local_path.name,
                    extension=ext,
                    media_type="image",
                    content_hash=content_hash,
                    taxonomy_category=str(local_path.parent.name),
                    embedding_model="openai/clip-vit-base-patch32"
                ).model_dump()

                points.append(PointStruct(
                    id=file_id * 1000,
                    vector={"image_clip": emb},
                    payload=payload
                ))
                indexed_file_ids.append(file_id)

            else:
                # Unsupported media type - mark as -1 so we don't retry forever
                failed_file_ids.append(file_id)

        except Exception as e:  # noqa: BLE001
            print(f"⚠️ [Poison Pill] Failed to index {remote_path}: {e}")
            failed_file_ids.append(file_id)

    # Batch Upsert to Qdrant
    if points:
        client.upsert(collection_name="nas_multimodal", points=points)

    # Database State Updates
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