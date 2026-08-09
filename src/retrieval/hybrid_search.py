from __future__ import annotations  # noqa: EXE002

from typing import Any

import instructor
from openai import OpenAI
from qdrant_client import QdrantClient

from src.config import load_settings
from src.kg.fuseki import FusekiClient
from src.vector.multimodal import get_embedder


class HybridRetriever:
    """
    Resilient Hybrid Search Engine.
    Executes high-precision SPARQL queries on Apache Jena first.
    Falls back to Qdrant Universal Vector Search if graph evidence is insufficient.
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

    def _query_graph(self, query: str) -> list[str]:
        """Primary: High-precision SPARQL keyword search on RDF Knowledge Graph."""
        keywords = [word for word in query.lower().split() if len(word) > 3]
        if not keywords: 
            return []
        
        filters = " || ".join([f'CONTAINS(LCASE(STR(?o)), "{kw}")' for kw in keywords])
        sparql = f"""
        SELECT ?s ?p ?o WHERE {{
            ?s ?p ?o .
            FILTER({filters})
        }} LIMIT 10
        """
        try:
            results = self.fuseki.query(sparql)
            bindings = results.get("results", {}).get("bindings", [])
            return [f"{b['s']['value']} -> {b['p']['value']} -> {b['o']['value']}" for b in bindings]
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ Graph query failed: {e}")
            return []

    def _query_vector(self, query: str, modality: str = "text") -> list[str]:
        """Secondary: High-recall Qdrant Vector fallback using Universal Embedder."""
        print("⚠️ Graph evidence insufficient. Falling back to Parameterized Vector Search...")
        try:
            embedder = get_embedder()
            query_vector = embedder.embed_text([query])[0]

            search_result = self.qdrant.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=3
            )
            return [
                f"Vector Match [{hit.score:.2f}]: {hit.payload.get('path')} "
                f"({hit.payload.get('media_type')} | Model: {hit.payload.get('embedding_model')})" 
                for hit in search_result
            ]
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ Vector search failed: {e}")
            return []

    def ask(self, question: str, target_modality: str = "text") -> dict[str, Any]:
        """The Agentic Hybrid Search Execution Loop."""
        evidence = self._query_graph(question)
        source = "Knowledge Graph (Deterministic SPARQL)"
        
        if not evidence:
            evidence = self._query_vector(question, modality=target_modality)
            source = f"Qdrant Vector Space (Probabilistic - {load_settings()['vector']['model_name']})"

        if not evidence:
            return {
                "question": question,
                "answer": "No evidence found in Knowledge Graph or Vector space.",
                "source": "None",
                "evidence": []
            }

        prompt = f"""
        You are an AI NAS Assistant. Answer the user's question based STRICTLY on the provided evidence.
        If the evidence does not contain enough information, state that clearly.
        
        User Question: {question}
        Grounded Evidence:
        {evidence}
        """
        
        response = self.llm.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        return {
            "question": question,
            "answer": response.choices[0].message.content,
            "source": source,
            "evidence": evidence
        }