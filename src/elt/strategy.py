import sqlite3
from pathlib import Path
from pydantic import BaseModel, Field
import instructor
from openai import OpenAI
from src.state.schema import get_unified_staging_view

# --- STRICT PYDANTIC SCHEMAS ---
class FileRoute(BaseModel):
    staging_id: int = Field(description="The exact staging_id provided in the input.")
    source_table: str = Field(description="The source_table provided in the input.")
    proposed_path: str = Field(description="The stable Nextcloud path (e.g., /Documents/Financial/2026_Taxes.pdf)")
    reasoning: str = Field(description="Brief reasoning for this taxonomy placement.")

class TaxonomyStrategy(BaseModel):
    routings: list[FileRoute]

# --- THE AGENT ---
def generate_strategy(db_path: Path, sources: list[str], llm_client: OpenAI, model_name: str) -> list[FileRoute]:
    """
    Phase 2: LLM evaluates cross-table deduplicated files and generates a routing strategy.
    """
    # 1. Fetch unique files across ALL sources that aren't in production yet
    unique_files = get_unified_staging_view(db_path, sources)
    
    if not unique_files:
        print("✅ No new unique files to route. System is fully synced.")
        return []

    print(f"🧠 Asking Agent to route {len(unique_files)} unique files...")
    
    # Master Taxonomy (In v5, this would eventually be pulled from your OKF Markdown)
    master_taxonomy = [
        "/Documents/Financial/Invoices",
        "/Documents/Financial/Taxes",
        "/Media/Photos/Family",
        "/Documents/Legal",
        "/Documents/Work_Projects"
    ]
    
    prompt = f"""
    You are an expert Data Librarian managing an enterprise NAS.
    Route the following new files into our stable Nextcloud directory structure.
    
    APPROVED TAXONOMY:
    {master_taxonomy}
    
    RULES:
    1. Prefer the APPROVED TAXONOMY.
    2. If a file does not fit, propose a new, highly stable top-level category.
    3. Do not create overly generic folders like '/Misc' or '/Other'.
    4. The proposed_path MUST include the filename at the end.
    
    FILES TO ROUTE:
    {unique_files}
    """
    
    # SRE Magic: Instructor forces the LLM to return our Pydantic schema perfectly
    instructor_client = instructor.from_openai(llm_client)
    
    strategy = instructor_client.chat.completions.create(
        model=model_name,
        response_model=TaxonomyStrategy,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    
    return strategy.routings