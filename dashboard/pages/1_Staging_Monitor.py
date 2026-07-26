import streamlit as st
import sqlite3
import pandas as pd
from src.config import load_settings, root_path
from src.pipeline.knowledge import run_knowledge_pipeline

st.set_page_config(page_title="Staging Monitor", layout="wide")
st.title("📥 ELT Staging Monitor")

settings = load_settings()
db_path = root_path(settings["paths"]["ledger_db"])

try:
    conn = sqlite3.connect(db_path)
    
    # Production Stats
    st.subheader("Production Inventory")
    prod_df = pd.read_sql_query("SELECT COUNT(*) as total_files, SUM(kg_indexed) as kg_synced, SUM(vector_indexed) as qdrant_synced FROM production_inventory", conn)
    st.dataframe(prod_df, use_container_width=True)

    # Staging Stats
    st.divider()
    st.subheader("Cloud Staging Zones")
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'staging_%'").fetchall()]
    
    if not tables:
        st.warning("No staging tables found. Run Phase 1 (Scanner).")
    else:
        cols = st.columns(len(tables))
        for i, table in enumerate(tables):
            with cols[i]:
                st.markdown(f"**{table.replace('staging_', '').upper()}**")
                df = pd.read_sql_query(f"SELECT status, COUNT(*) as count FROM {table} GROUP BY status", conn)
                st.dataframe(df, use_container_width=True)
                
    # Manual Trigger
    st.divider()
    if st.button("🚀 Force Rebuild Knowledge Substrate (Phase 4)"):
        with st.spinner("Building Parquet, OKF, KG, and Vectors..."):
            run_knowledge_pipeline(db_path, nextcloud_mount=root_path("/mnt/Tank/Nextcloud_Data"))
            st.success("Knowledge Substrate Updated! Check your artifacts folder.")

except Exception as e:
    st.error(f"Database error: {e}")
finally:
    if 'conn' in locals(): conn.close()