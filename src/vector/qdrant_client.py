#!/usr/bin/env python3
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


def init_qdrant(url: str = "http://localhost:6333", collection_name: str = "nas_multimodal"):
    """Initializes the Qdrant connection and ensures the collection exists."""
    client = QdrantClient(url=url)
    
    # Check if collection exists
    if not client.collection_exists(collection_name):
        print(f"Creating Qdrant Collection: {collection_name}")
        # We use size=512 for OpenAI CLIP (Images) and 384 for FastEmbed (Text).
        # Qdrant supports named vectors for multimodal in the same collection!
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "text": VectorParams(size=384, distance=Distance.COSINE),
                "image": VectorParams(size=512, distance=Distance.COSINE)
            }
        )
    return client