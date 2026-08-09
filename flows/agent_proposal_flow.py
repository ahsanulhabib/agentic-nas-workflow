import json
import sqlite3
from pathlib import Path

from openai import OpenAI
from prefect import flow, task
from prefect.blocks.system import Secret
from src.config import load_settings, root_path

from src.state.schema import get_unified_staging_view


@task(name="Generate-Advisory-Taxonomy-Proposals")
def generate_advisory_proposals(db_path: Path, llm_client: OpenAI, model_name: str):
    """
    Advisory Agent: Evaluates unmapped staging files and generates proposals.
    STRICT RULE: Never moves files or writes to production_inventory!
    """
    settings = load_settings()
    cloud_sources = settings["ingestion"]["cloud_sources"]
    
    # 1. Fetch unmapped unique files from staging
    unmapped_files = get_unified_staging_view(db_path, list(cloud_sources.keys()))
    
    if not unmapped_files:
        print("✅ No unmapped files found. Taxonomy is fully covered.")
        return

    print(f"🧠 Advisory Agent analyzing {len(unmapped_files)} files for recommendations...")
    
    prompt = f"""
    You are an ADVISORY NAS Archivist. 
    Propose organized Nextcloud paths for these unmapped files.
    
    RULES:
    1. Prefer durable, high-inertia categories (e.g., /Documents/Financial/Invoices).
    2. These are PROPOSALS ONLY. A human will review and approve/override them.
    3. Return a JSON array: [{{"staging_id": 1, "source_table": "staging_gdrive", "proposed_path": "/Category/Path/file.pdf", "reasoning": "Explanation"}}]
    
    FILES TO EVALUATE:
    {unmapped_files}
    """

    response = llm_client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )

    try:
        proposals = json.loads(response.choices[0].message.content)
        conn = sqlite3.connect(db_path)
        
        staged_count = 0
        for p in proposals:
            conn.execute("""
                INSERT INTO pending_taxonomy_approvals (staging_id, source_table, proposed_path, reasoning, status)
                VALUES (?, ?, ?, ?, 'pending_approval')
            """, (p["staging_id"], p["source_table"], p["proposed_path"], p.get("reasoning", "")))
            staged_count += 1
            
        conn.commit()
        conn.close()
        print(f"✅ Staged {staged_count} advisory proposals in Streamlit review queue.")
        
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Failed to parse LLM advisory response: {e}")

@flow(name="Weekly-Advisory-Proposal-Flow", log_prints=True)
def agent_proposal_workflow():
    settings = load_settings()
    db_path = root_path(settings["paths"]["ledger_db"])

    llm_key = Secret.load(settings["llm"]["secret_blocks"]["gemini_api_key"]).get()
    llm_client = OpenAI(
        api_key=llm_key, 
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )

    generate_advisory_proposals(db_path, llm_client, settings["llm"]["model"])

if __name__ == "__main__":
    agent_proposal_workflow.serve(
        name="weekly-advisory-proposal-job",
        cron="0 1 * * 0",  # Runs weekly on Sunday at 1:00 AM
        tags=["advisory", "path-proposal"],
        description="Weekly advisory LLM evaluation to propose taxonomy improvements for human review."
    )