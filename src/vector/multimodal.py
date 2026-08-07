#!/usr/bin/env python3
import os
import sqlite3
from pathlib import Path

import torch
from PIL import Image
from qdrant_client.models import PointStruct
from transformers import CLIPModel, CLIPProcessor

from src.vector.qdrant_client import init_qdrant

# Lazy-loaded models to save RAM
_text_model = None
_image_model = None
_image_processor = None

def _get_text_model():
    from fastembed import TextEmbedding
    global _text_model
    if _text_model is None:
        print("Loading FastEmbed Text Model (BAAI/bge-small-en-v1.5)...")
        _text_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
    return _text_model

def _get_image_model():
    global _image_model, _image_processor
    if _image_model is None:
        print("Loading HuggingFace CLIP Image Model...")
        _image_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        _image_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    return _image_processor, _image_model

def index_unprocessed_files(db_path: Path, nextcloud_mount: Path, qdrant_url: str):
    """Generates embeddings for new files and uploads to Qdrant."""
    client = init_qdrant(url=qdrant_url)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    # Fetch files that haven't been vector indexed
    cursor = conn.execute("SELECT id, nextcloud_path, blake3_hash FROM production_inventory WHERE vector_indexed = 0")
    unprocessed = cursor.fetchall()
    
    if not unprocessed:
        print("✅ No new files require Vector Indexing.")
        return

    print(f"🧠 Generating Multimodal Embeddings for {len(unprocessed)} files...")
    points = []
    
    for row in unprocessed:
        remote_path = row["nextcloud_path"]
        local_path = nextcloud_mount / "admin" / "files" / remote_path.lstrip("/")
        ext = os.path.splitext(local_path)[1].lower()
        
        if not local_path.exists():
            continue

        payload = {"path": remote_path, "hash": row["blake3_hash"], "type": "unknown"}
        vectors = {}

        try:
            # --- TEXT EMBEDDING (Documents/Markdown/Txt) ---
            if ext in [".txt", ".md", ".csv"]:
                with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()[:2000] # Truncate for speed
                text_model = _get_text_model()
                embedding = next(iter(text_model.embed([text]))).tolist()
                vectors["text"] = embedding
                payload["type"] = "document"

            # --- IMAGE EMBEDDING (CLIP) ---
            elif ext in [".jpg", ".jpeg", ".png"]:
                
                processor, model = _get_image_model()
                image = Image.open(local_path).convert("RGB")
                inputs = processor(images=image, return_tensors="pt")
                with torch.no_grad():
                    image_features = model.get_image_features(**inputs)
                vectors["image"] = image_features[0].tolist()
                payload["type"] = "image"
                
            # --- AUDIO/VIDEO (Stub for future Whisper/FFMPEG integration) ---
            elif ext in [".mp4", ".mp3"]:
                print(f"   [Skip] Audio/Video embedding requires FFMPEG/Whisper pipeline: {remote_path}")
                continue

            if vectors:
                points.append(PointStruct(id=row["id"], vector=vectors, payload=payload))
                conn.execute("UPDATE production_inventory SET vector_indexed = 1 WHERE id = ?", (row["id"],))

        except Exception as e:  # noqa: BLE001
            print(f"   [Error] Failed to embed {remote_path}: {e}")

    if points:
        client.upsert(collection_name="nas_multimodal", points=points)
        conn.commit()
        print(f"✅ Successfully indexed {len(points)} vectors into Qdrant.")
        
    conn.close()