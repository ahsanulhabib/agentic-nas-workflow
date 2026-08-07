import streamlit as st

st.set_page_config(page_title="Agentic NAS v5", layout="wide")
st.title("🧠 Agentic NAS v5 Operations Hub")
st.markdown("""
Welcome to the v5 Control Plane. 
Use the sidebar to navigate your enterprise architecture:
* **1. Staging Monitor:** View ELT ingestion queues and deduplication stats.
* **2. KG Viewer:** Interactively explore your Apache Jena RDF graph.
* **3. Vector Telemetry:** Monitor Qdrant multimodal embedding health.
* **4. Hybrid Search:** Chat with your NAS using GraphRAG + Vector Fallback.
""")