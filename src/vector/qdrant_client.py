from __future__ import annotations  # noqa: EXE002

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from src.config import load_settings


def init_qdrant_collections(qdrant_url: str = "http://localhost:6333") -> QdrantClient:
    """
    Reads settings.yaml to dynamically configure vector dimensions and collection parameters.
    """
    settings = load_settings()
    vec_cfg = settings["vector"]
    collection_name = vec_cfg["collection_name"]
    target_dim = int(vec_cfg["vector_size"])
    
    metric = Distance.COSINE if vec_cfg.get("distance_metric") == "Cosine" else Distance.DOT

    client = QdrantClient(url=qdrant_url)
    
    # Auto-detect dimension changes
    if client.collection_exists(collection_name):
        info = client.get_collection(collection_name)
        current_dim = info.config.params.vectors.size if hasattr(info.config.params.vectors, 'size') else None
        
        if current_dim != target_dim:
            print(f"🔄 Dimension Mismatch Detected ({current_dim}d -> {target_dim}d). Re-creating collection '{collection_name}' for [{vec_cfg['model_name']}]...")
            client.delete_collection(collection_name)

    if not client.collection_exists(collection_name):
        print(f"✨ Creating Qdrant Collection '{collection_name}' | Model: [{vec_cfg['model_name']}] | Dim: {target_dim}")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=target_dim, distance=metric)
        )
        
    return client