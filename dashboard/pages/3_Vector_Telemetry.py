import streamlit as st
from qdrant_client import QdrantClient

st.set_page_config(page_title="Vector Telemetry", layout="wide")
st.title("👁️ Qdrant Multimodal Telemetry")

try:
    client = QdrantClient(url="http://localhost:6333")
    collections = client.get_collections().collections
    
    if not collections:
        st.warning("No collections found in Qdrant.")
    else:
        for col in collections:
            info = client.get_collection(col.name)
            st.subheader(f"Collection: {col.name}")
            st.metric("Total Vectors", info.points_count)
            st.json(info.config.params.vectors.model_dump())
            
except Exception as e:
    st.error(f"Failed to connect to Qdrant: {e}. Is the container running on port 6333?")