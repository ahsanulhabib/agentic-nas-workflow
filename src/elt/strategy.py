#!/usr/bin/env python3
import os
import sqlite3
from pathlib import Path

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field

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
    Phase 2: Uses a 2-Step Lookaside Cache (SQLite -> LLM Fallback) to route files.
    """
    unique_files = get_unified_staging_view(db_path, sources)
    
    if not unique_files:
        print("✅ No new unique files to route. System is fully synced.")
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    final_routings = []
    uncached_files = []
    cache_hits = 0

    # --- STEP 1: CACHE LOOKUP ---
    for file_record in unique_files:
        parent_dir = str(Path(file_record["original_path"]).parent)
        
        # Check if we have already learned how to route files from this parent directory
        cursor = conn.execute(
            "SELECT target_folder FROM taxonomy_cache WHERE source_parent_path = ?", 
            (parent_dir,)
        )
        cached_row = cursor.fetchone()
        
        if cached_row:
            # CACHE HIT! Generate the route without calling the LLM
            target_folder = cached_row["target_folder"]
            proposed_path = f"{target_folder}/{file_record['filename']}"
            
            final_routings.append(FileRoute(
                staging_id=file_record["staging_id"],
                source_table=file_record["source_table"],
                proposed_path=proposed_path,
                reasoning=f"Taxonomy Cache Hit (Path: {parent_dir})"
            ))
            
            # Increment telemetry hit counter
            conn.execute(
                "UPDATE taxonomy_cache SET hit_count = hit_count + 1 WHERE source_parent_path = ?", 
                (parent_dir,)
            )
            cache_hits += 1
        else:
            # CACHE MISS! Save for LLM evaluation
            uncached_files.append(file_record)

    conn.commit()
    
    print(f"📊 Taxonomy Cache Results | Hits: {cache_hits} | Misses (Sent to LLM): {len(uncached_files)}")

    # --- STEP 2: LLM FALLBACK FOR CACHE MISSES ---
    if uncached_files:
        print(f"🧠 Asking Agent to route {len(uncached_files)} unseen files...")
        
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
        3. The proposed_path MUST include the filename at the end.
        
        FILES TO ROUTE:
        {uncached_files}
        """
        
        instructor_client = instructor.from_openai(llm_client)
        strategy = instructor_client.chat.completions.create(
            model=model_name,
            response_model=TaxonomyStrategy,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        # --- STEP 3: CACHE WRITE ---
        for route in strategy.routings:
            final_routings.append(route)
            
            # Find the original parent dir for this routed file
            matching_record = next((f for f in uncached_files if f["staging_id"] == route.staging_id and f["source_table"] == route.source_table), None)
            if matching_record:
                parent_dir = os.path.dirname(matching_record["original_path"])
                target_folder = os.path.dirname(route.proposed_path)
                
                # Save the learned rule into SQLite for future runs
                conn.execute("""
                    INSERT INTO taxonomy_cache (source_parent_path, target_folder)
                    VALUES (?, ?)
                    ON CONFLICT(source_parent_path) DO UPDATE SET target_folder=excluded.target_folder
                """, (parent_dir, target_folder))
                
        conn.commit()

    conn.close()
    return final_routings