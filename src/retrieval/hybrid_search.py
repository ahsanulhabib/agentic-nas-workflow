import os
from qdrant_client import QdrantClient
from src.kg.fuseki import FusekiClient
from src.vector.multimodal import _get_text_model, _get_image_model
from openai import OpenAI
import instructor

class HybridRetriever:
    def __init__(self, fuseki_url: str, qdrant_url: str, llm_client: OpenAI, model_name: str):
        self.fuseki = FusekiClient(fuseki_url, "nas")
        self.qdrant = QdrantClient(url=qdrant_url)
        self.llm = instructor.from_openai(llm_client)
        self.model_name = model_name

    def _query_graph(self, query: str) -> list[str]:
        """Primary: High-precision SPARQL keyword search."""
        # Simple keyword extraction (in production, use an LLM to generate the SPARQL)
        keywords = [word for word in query.lower().split() if len(word) > 3]
        if not keywords: return []
        
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
        except Exception as e:
            print(f"Graph query failed: {e}")
            return []

    def _query_vector(self, query: str, modality: str = "text") -> list[str]:
        """Secondary: High-recall Qdrant Vector fallback."""
        print(f"⚠️ Graph evidence insufficient. Falling back to {modality.upper()} Vector Search...")
        try:
            if modality == "text":
                model = _get_text_model()
                vector = list(model.embed([query]))[0].tolist()
            else:
                # Use CLIP to embed the text query into the image vector space!
                processor, model = _get_image_model()
                import torch
                inputs = processor(text=[query], return_tensors="pt", padding=True)
                with torch.no_grad():
                    vector = model.get_text_features(**inputs)[0].tolist()

            search_result = self.qdrant.search(
                collection_name="nas_multimodal",
                query_vector=(modality, vector),
                limit=3
            )
            return [f"Vector Match [{hit.score:.2f}]: {hit.payload.get('path')}" for hit in search_result]
        except Exception as e:
            print(f"Vector search failed: {e}")
            return []

    def ask(self, question: str, target_modality: str = "text") -> dict:
        """The Agentic Hybrid Search Loop."""
        evidence = self._query_graph(question)
        source = "Knowledge Graph (Deterministic)"
        
        if not evidence:
            evidence = self._query_vector(question, modality=target_modality)
            source = "Qdrant Vector Space (Probabilistic)"

        if not evidence:
            return {"answer": "No evidence found in Graph or Vector stores.", "source": "None", "evidence": []}

        prompt = f"""
        Answer the user's question based strictly on the provided evidence.
        Question: {question}
        Evidence: {evidence}
        """
        
        response = self.llm.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        
        return {
            "answer": response.choices[0].message.content,
            "source": source,
            "evidence": evidence
        }