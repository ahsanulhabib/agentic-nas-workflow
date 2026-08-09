from __future__ import annotations  # noqa: EXE002

from typing import Any

import instructor
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from src.agent.prompts import load_prompts
from src.config import load_settings
from src.kg.fuseki import FusekiClient
from src.vector.multimodal import get_embedder


class HybridRetriever:
    """
    Resilient Hybrid Search Engine.
    Executes high-precision SPARQL queries on Apache Jena first.
    Falls back to Qdrant Universal Vector Search filtered by OKF tags/trust_tier.
    """
    def __init__(self, fuseki_url: str, qdrant_url: str, llm_client: OpenAI, model_name: str):
        settings = load_settings()
        dataset = settings["kg"]["dataset"]
        collection_name = settings["vector"]["collection_name"]
        
        self.fuseki = FusekiClient(fuseki_url, dataset)
        self.qdrant = QdrantClient(url=qdrant_url)
        self.collection_name = collection_name
        self.llm = instructor.from_openai(llm_client)
        self.model_name = model_name
        self.prompts = load_prompts()

    def _query_graph(self, query: str) -> list[str]:
        """Step 2: Graph RAG Contextualization via SPARQL."""
        keywords = [word for word in query.lower().split() if len(word) > 3]
        if not keywords: 
            return []
        
        filters = " || ".join([f'CONTAINS(LCASE(STR(?o)), "{kw}")' for kw in keywords])
        sparql = f"""
        SELECT ?s ?p ?o WHERE {{
            ?s ?p ?o .
            FILTER({filters})
        }} LIMIT 15
        """
        try:
            results = self.fuseki.query(sparql)
            bindings = results.get("results", {}).get("bindings", [])
            return [f"<{b['s']['value']}> <{b['p']['value']}> \"{b['o']['value']}\" [Trust Tier: 1]" for b in bindings]
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ Graph query failed: {e}")
            return []

    def _query_vector(self, query: str, tag_filter: str | None = None) -> list[str]:
        """Step 3: Vector RAG Grounding with OKF Tag Scoping."""
        print("⚠️ Graph evidence insufficient. Falling back to Scoped Vector Search...")
        try:
            embedder = get_embedder()
            query_vector = embedder.embed_text([query])[0]

            # OKF Tag Filtering
            q_filter = None
            if tag_filter:
                q_filter = Filter(
                    must=[FieldCondition(key="tags", match=MatchValue(value=tag_filter))]
                )

            search_result = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=q_filter,
                limit=5
            )
            return [
                f"Document Chunk [Match Score: {hit.score:.2f} | Trust Tier: {hit.payload.get('trust_tier', 1)} | "
                f"Source: {hit.payload.get('source_path')}]: {hit.payload.get('filename')}" 
                for hit in search_result
            ]
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ Vector search failed: {e}")
            return []

    def ask(self, question: str, tag_filter: str | None = None) -> dict[str, Any]:
        """Executes the OKF + Graph + Vector Synthesis Workflow."""
        # Step 1 & 2: Graph RAG
        evidence = self._query_graph(question)
        source_type = "Knowledge Graph (SPARQL)"
        
        # Step 3: Vector RAG Fallback
        if not evidence:
            evidence = self._query_vector(question, tag_filter=tag_filter)
            source_type = f"Qdrant Vector Space (Scoped Tag: {tag_filter or 'All'})"

        if not evidence:
            return {
                "question": question,
                "answer": "No evidence found in Knowledge Graph or Vector space.",
                "source": "None",
                "evidence": []
            }

        # Step 4: Response Generation Rules (Synthesise + Strict Provenance)
        system_instruction = self.prompts.get("graph_rag", {}).get("system", "Synthesise facts with citations.")
        prompt = f"""
        User Question: {question}
        
        Retrieved Grounded Evidence:
        {evidence}
        
        Synthesise an answer following the system rules. Provide inline citations for all facts.
        """
        
        response = self.llm.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1
        )
        
        return {
            "question": question,
            "answer": response.choices[0].message.content,
            "source": source_type,
            "evidence": evidence
        }