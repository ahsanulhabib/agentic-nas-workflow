from __future__ import annotations

from typing import Any

from rdflib import Graph

from src.kg.namespaces import NAS


def validate_graph(graph: Graph) -> dict[str, Any]:
    """Validates RDF Graph metrics and mandatory node class existence."""
    total_triples = len(graph)
    
    file_count = len(list(graph.subjects(predicate=None, object=NAS.File)))
    folder_count = len(list(graph.subjects(predicate=None, object=NAS.Folder)))
    
    has_files = file_count > 0 or total_triples == 1 # Allow empty graph initialization
    
    return {
        "total_triples": total_triples,
        "file_nodes": file_count,
        "folder_nodes": folder_count,
        "is_valid": total_triples > 0 and has_files
    }