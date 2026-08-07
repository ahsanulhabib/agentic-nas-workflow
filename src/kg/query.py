#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from src.kg.fuseki import FusekiClient

# Pre-defined SPARQL query to count node types
COUNT_QUERY = """
SELECT ?class (COUNT(?s) AS ?count)
WHERE {
  ?s a ?class .
}
GROUP BY ?class
ORDER BY DESC(?count)
"""

def graph_counts(client: FusekiClient) -> dict[str, Any]:
    """Returns the count of instances per RDF class in the Knowledge Graph."""
    return client.query(COUNT_QUERY)

def neighbourhood(client: FusekiClient, resource_uri: str, limit: int = 100) -> dict[str, Any]:
    """
    Fetches the immediate neighbourhood (triples) of a specific URI.
    Used by the Streamlit Interactive KG Viewer to expand nodes.
    """
    query = f"""
    SELECT ?p ?o
    WHERE {{
      <{resource_uri}> ?p ?o .
    }}
    LIMIT {int(limit)}
    """
    return client.query(query)