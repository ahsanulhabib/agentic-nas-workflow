import streamlit as st
from src.retrieval.hybrid_search import HybridRetriever
from src.config import load_settings
from openai import OpenAI
from prefect.blocks.system import Secret

st.set_page_config(page_title="Hybrid Search", layout="wide")
st.title("🔍 Hybrid GraphRAG Search")
st.caption("Queries Apache Jena first. Falls back to Qdrant Multimodal Vectors.")

query = st.text_input("Ask your NAS a question:")
modality = st.radio("Target Modality", ["text", "image"], horizontal=True)

if st.button("Search") and query:
    with st.spinner("Traversing Knowledge Graph & Vector Space..."):
        try:
            settings = load_settings()
            llm_key = Secret.load("nas-gemini-api-key").get()
            llm_client = OpenAI(api_key=llm_key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
            
            retriever = HybridRetriever(
                fuseki_url=settings["kg"]["fuseki_url"],
                qdrant_url="http://localhost:6333",
                llm_client=llm_client,
                model_name=settings["llm"]["model"]
            )
            
            result = retriever.ask(query, target_modality=modality)
            
            st.markdown("### Answer")
            st.write(result["answer"])
            
            st.info(f"**Retrieval Source:** {result['source']}")
            with st.expander("View Grounding Evidence"):
                for ev in result["evidence"]:
                    st.code(ev)
        except Exception as e:
            st.error(f"Search failed: {e}")